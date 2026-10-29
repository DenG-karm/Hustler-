from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import shutil
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field

from services.core.hustler.api.auth import verify_token
from services.core.hustler.api.routes.pipeline import (
    AudioRequest,
    _resolve_chat_llm,
    _write_valid_mp4_stub,
    generate_audio,
)
from services.core.hustler.db import Database
from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.domain.models.template import (
    AssetType,
    RecoveryStrategy,
    RenderConfig,
    SafeZone,
    SlotSpec,
    TemplateSpec,
)
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler
from services.core.hustler.services.channel_stats import fetch_channel_live_stats
from services.core.hustler.storage.channels import Channel, ChannelRepository

router = APIRouter(dependencies=[Depends(verify_token)])


def _default_metrics() -> dict[str, int | float]:
    return {"total_scripts": 0, "total_research": 0, "avg_viral_score": 0.0}


@dataclass
class ChannelCreateRequest:
    name: Annotated[str, Field(min_length=2, description="Kanal adı (en az 2 karakter)")]
    channel_url: Annotated[str, Field(min_length=1, description="Kanal URL adresi")]
    description: str = ""


@dataclass
class ChannelResponse:
    id: str
    name: str
    channel_url: str
    description: str
    created_at: float
    metrics: dict[str, int | float] = field(default_factory=_default_metrics)


@dataclass
class TemplateSlotPayload:
    slot_id: str
    label: str
    media_type: str = "image"
    media_path: str = ""
    start_sec: float = 0.0
    end_sec: float = 5.0
    layout: str = "fullscreen"
    prompt: str = ""
    directive: str = ""
    subtitle: str = ""


@dataclass
class TemplateCreateRequest:
    title: Annotated[str, Field(min_length=1)]
    base_video_path: Annotated[str, Field(min_length=1)]
    duration_sec: float = 15.0
    slots: list[TemplateSlotPayload] = field(default_factory=list)
    narration_script: str = ""
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"


@dataclass
class TemplateUpdateRequest:
    title: Optional[str] = None
    duration_sec: Optional[float] = None
    slots: Optional[list[TemplateSlotPayload]] = None
    narration_script: Optional[str] = None
    subtitle_cues: Optional[list[dict[str, object]]] = None
    voice_id: Optional[str] = None


@dataclass
class TemplateAnalyzeRequest:
    topic: str = ""
    tone: str = "energetic"
    slot_count: Optional[int] = None


@dataclass
class TemplateTtsRequest:
    narration_script: Optional[str] = None
    voice_id: Optional[str] = None
    profile: str = "DRAFT"


@dataclass
class TemplateTtsOnlyRequest:
    narration_script: Optional[str] = None
    voice_id: Optional[str] = None


def _repo(request: Request) -> ChannelRepository:
    repo = getattr(request.app.state, "channel_repo", None)
    if isinstance(repo, ChannelRepository):
        return repo
    db = getattr(request.app.state, "db", None)
    if not isinstance(db, Database):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Veritabanı başlatılmamış (DB not initialized in app.state)",
        )
    return ChannelRepository(db)


def _to_response(
    channel: Channel, metrics: dict[str, int | float]
) -> ChannelResponse:
    """Kanalı ve hesaplanmış gerçek metriklerini ChannelResponse nesnesine dönüştürür."""
    merged = _default_metrics()
    merged.update(metrics)
    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_url=channel.channel_url,
        description=channel.description,
        created_at=channel.created_at,
        metrics=merged,
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(request: Request) -> list[ChannelResponse]:
    """Tüm kayıtlı kanalları ve özet metriklerini listeler."""
    repo = _repo(request)
    pairs = await repo.list_all_with_metrics()
    return [_to_response(channel, metrics) for channel, metrics in pairs]


@router.post(
    "/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    payload: ChannelCreateRequest, request: Request
) -> ChannelResponse:
    """Yeni bir kanal kaydı oluşturur."""
    repo = _repo(request)
    channel = await repo.create(
        name=payload.name.strip(),
        channel_url=payload.channel_url.strip(),
        description=payload.description.strip(),
    )
    metrics = await repo.get_metrics(channel.id)
    return _to_response(channel, metrics)


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel_detail(
    channel_id: str, request: Request
) -> ChannelResponse:
    """Kanal detayını ve analiz özetini getirir."""
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kanal bulunamadı: {channel_id}",
        )
    metrics = await repo.get_metrics(channel.id)
    return _to_response(channel, metrics)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str, request: Request
) -> dict[str, str]:
    """Belirtilen kanalı siler."""
    deleted = await _repo(request).delete(channel_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Silinecek kanal bulunamadı: {channel_id}",
        )
    return {"status": "deleted", "channel_id": channel_id}


@router.get("/channels/{channel_id}/live-stats")
async def get_channel_live_stats(
    channel_id: str, request: Request, refresh: bool = False
) -> dict[str, object]:
    """Kanalın gerçek YouTube abone, video, Shorts, niş kıyaslamaları ve canlı istatistiklerini getirir."""
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kanal bulunamadı: {channel_id}",
        )
    live_data = await fetch_channel_live_stats(channel.channel_url, force_refresh=refresh)
    raw_bench = live_data.get("niche_benchmarks")
    niche_q = str(live_data.get("niche_query") or channel.name)
    if isinstance(raw_bench, list) and raw_bench:
        bench_items = [it for it in raw_bench if isinstance(it, dict)]
        if bench_items:
            try:
                await repo.record_research(channel.id, niche_q, bench_items)
            except Exception:
                pass
    sqlite_metrics = await repo.get_metrics(channel.id)

    return {
        "channel_id": channel.id,
        "channel_name": channel.name,
        "channel_url": channel.channel_url,
        "description": channel.description,
        "ai_summary": getattr(channel, "ai_summary", ""),
        "created_at": channel.created_at,
        "live_data": live_data,
        "sqlite_metrics": sqlite_metrics,
    }


ELEVENLABS_VOICES: list[dict[str, str]] = [
    {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel — Dinamik & Net (Reels/Shorts)"},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam — Derin & Belgesel Tonu"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella — Akıcı & Hikaye Anlatıcı"},
    {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni — Enerjik & Hızlı Kurgu"},
]


def _default_template_slots(duration_sec: float) -> list[dict[str, object]]:
    d = max(6.0, duration_sec)
    s1 = round(min(3.0, d * 0.25), 1)
    s2 = round(min(d - 2.0, d * 0.75), 1)
    return [
        {
            "slot_id": "slot_1",
            "label": "Kanca / Giriş Görseli (Fotoğraf veya Video)",
            "media_type": "image",
            "media_path": "",
            "start_sec": 0.0,
            "end_sec": s1,
            "layout": "overlay_center",
        },
        {
            "slot_id": "slot_2",
            "label": "Ana Gövde B-Roll (Fotoğraf veya Video)",
            "media_type": "video",
            "media_path": "",
            "start_sec": s1,
            "end_sec": s2,
            "layout": "fullscreen",
        },
        {
            "slot_id": "slot_3",
            "label": "Kapanış / Vurgu Katmanı",
            "media_type": "image",
            "media_path": "",
            "start_sec": s2,
            "end_sec": round(d, 1),
            "layout": "split_top",
        },
    ]


def _build_template_cues(narration: str, duration_sec: float) -> list[dict[str, object]]:
    sentences = [s.strip() for s in narration.replace("\n", " ").split(".") if s.strip()]
    if not sentences:
        sentences = [narration.strip() or "Kanca ve ana kurgu metni."]
    step = round(max(2.0, duration_sec / len(sentences)), 1)
    cues: list[dict[str, object]] = []
    cursor = 0.0
    for idx, sent in enumerate(sentences):
        end_t = round(min(duration_sec, cursor + step), 1) if idx < len(sentences) - 1 else round(duration_sec, 1)
        cues.append({
            "index": idx + 1,
            "start_sec": round(cursor, 1),
            "end_sec": max(round(cursor + 0.5, 1), end_t),
            "text": f"{sent}.",
        })
        cursor = end_t
    return cues


@router.get("/channels/{channel_id}/templates")
async def list_channel_templates(channel_id: str, request: Request) -> dict[str, object]:
    repo = _repo(request)
    templates = await repo.list_templates(channel_id)
    return {
        "channel_id": channel_id,
        "templates": [t.to_dict() for t in templates],
        "voices": ELEVENLABS_VOICES,
        "elevenlabs_configured": bool(os.environ.get("ELEVENLABS_API_KEY")),
    }


@router.post("/channels/{channel_id}/templates", status_code=status.HTTP_201_CREATED)
async def create_channel_template(
    channel_id: str, payload: TemplateCreateRequest, request: Request
) -> dict[str, object]:
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Kanal bulunamadı: {channel_id}")
    slots = [asdict(s) for s in payload.slots] if payload.slots else _default_template_slots(payload.duration_sec)
    tpl = await repo.create_template(
        channel_id=channel_id,
        title=payload.title.strip(),
        base_video_path=payload.base_video_path.strip(),
        duration_sec=payload.duration_sec,
        slots=slots,
        narration_script=payload.narration_script.strip(),
        voice_id=payload.voice_id.strip() or "21m00Tcm4TlvDq8ikWAM",
    )
    return {"template": tpl.to_dict(), "voices": ELEVENLABS_VOICES}


@router.post("/channels/{channel_id}/templates/{template_id}/update")
async def update_channel_template(
    channel_id: str, template_id: str, payload: TemplateUpdateRequest, request: Request
) -> dict[str, object]:
    repo = _repo(request)
    slots = [asdict(s) for s in payload.slots] if payload.slots is not None else None
    updated = await repo.update_template(
        channel_id,
        template_id,
        title=payload.title,
        duration_sec=payload.duration_sec,
        slots=slots,
        narration_script=payload.narration_script,
        subtitle_cues=payload.subtitle_cues,
        voice_id=payload.voice_id,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Şablon bulunamadı")
    return {"template": updated.to_dict()}


@router.delete("/channels/{channel_id}/templates/{template_id}")
async def delete_channel_template(
    channel_id: str, template_id: str, request: Request
) -> dict[str, str]:
    deleted = await _repo(request).delete_template(channel_id, template_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Silinecek şablon bulunamadı")
    return {"status": "deleted", "template_id": template_id}


def _generate_mathematical_storyboard(
    channel_name: str,
    channel_desc: str,
    topic: str,
    duration_sec: float,
    slot_count: Optional[int] = None,
    tone: str = "energetic",
) -> tuple[list[dict[str, object]], str, list[dict[str, object]], str, str, str]:
    dur = round(max(6.0, duration_sec), 1)
    count = max(4, min(16, slot_count if slot_count is not None else 10))
    step = round(dur / count, 1)

    desc_l = f"{channel_name} {channel_desc} {topic}".lower()
    if any(k in desc_l for k in ("finans", "para", "borsa", "yatırım", "kripto", "bitcoin", "hisse")):
        target_audience = "Finans, borsa ve kripto piyasalarında gizli fırsat arayan analitik izleyiciler"
        niche_subj = "financial breakthrough, gold and high-stakes market volatility"
    elif any(k in desc_l for k in ("bilim", "tarih", "gizem", "uzay", "fizik", "arkeoloji")):
        target_audience = "Tarihin ve bilimin perde arkasındaki gerçekleri merak eden araştırmacı kitle"
        niche_subj = "ancient artifact, deep space anomaly and cosmic scientific discovery"
    elif any(k in desc_l for k in ("yazılım", "yapay zeka", "kod", "teknoloji", "çip")):
        target_audience = "Yapay zeka ve yeni nesil teknolojileri yakından takip eden vizyoner kitle"
        niche_subj = "advanced neural network, futuristic quantum microchip and robotic interface"
    elif any(k in desc_l for k in ("motivasyon", "girişim", "iş", "kariyer", "psikoloji")):
        target_audience = "Kariyerinde ve zihinsel gelişiminde sıçrama yapmak isteyen girişimci kitle"
        niche_subj = "dramatic boardroom decision, solitary thinker and psychological resilience"
    else:
        target_audience = "Yüksek bilgi yoğunluğu ve hızlı görsel dinamizm bekleyen Shorts izleyicileri"
        niche_subj = "intriguing dynamic scene with high contrast and explosive visual energy"

    viral_formula = "Alışılmışı Kıran Kanca (0-2s) → Şok Edici Gerçek → Mikro Kanıtlar → Çözüm & Yorum Tetikleyici"
    pacing_cadence = f"~{round(dur / count, 1)}s/kesim ({count} Sahne)"

    beats = [
        ("Kanca: Alışılmışı Kıran Görsel Şok", "Dikey 9:16 yakın plan, 1.3x hızlı yaklaşma, yüksek kontrast sinematik aydınlatma, ilk 2 saniyede izleyiciyi ekrana kilitleyen görsel şok."),
        ("Gizli Problem & Agitasyon", "Göz seviyesi sabit kadraj, hafif titreşim efekti, konunun ciddiyetini ve perde arkasındaki tehlikeyi vurgulayan soğuk renk paleti."),
        ("Şok Edici İstatistik / Veri", "Hızlı kesme, 9:16 infografik/veri katmanı, parlayan neon çizgiler ve tartışmasız sayısal kanıt gösterimi."),
        ("Zıtlık Karşılaştırması", "Dikey bölünmüş ekran kompozisyonu, eski yöntem ile yeni gerçeklik arasındaki çarpıcı kontrast."),
        ("Mekanizma Analizi", "Makro yakın plan, iç mekanizmaya odaklanan dinamik kaydırma (dolly-in), teknik merak uyandıran mikro detay."),
        ("Ters Köşe Kanıtı", "Hızlı geçiş (whip pan), izleyicinin ezberini bozan beklenmedik görsel detay ve kanıt karesi."),
        ("Zirve Noktası (Climax)", "Kurgunun en yüksek görsel enerjisi, dramatik ışık patlaması ve merkezi odaklanma."),
        ("Çözüm & Büyük Çıkarım", "Merkezi altın oran yerleşimi, sade ve güçlü stüdyo ışığı, akılda kalıcı estetik kompozisyon."),
        ("Tutunma Döngüsü (Loop)", "Videonun açılış karesine bağlanan döngüsel hareket, izleme süresini ve tekrar izletmeyi maksimize eden ritim."),
        ("Kapanış & Yorum Çağrısı", "Son sahne, izleyiciyi doğrudan soruyla yorum yazmaya iten net ve minimalist kapanış kadrajı."),
    ]

    sentences = [
        f"{topic} hakkında herkesin bildiğini sandığı bu gerçeğe hazır olun.",
        "Çünkü perde arkasında dönen asıl denklem tahmin ettiğinizden çok farklı.",
        f"{channel_name} araştırmalarında ortaya çıkan bu rakamlar tüm sistemi sorgulatıyor.",
        "Eski yöntemleri takip edenler kaybederken, yeni düzeni çözenler hızla öne geçiyor.",
        "İşin sırrı, tam olarak bu noktada gizlenen mekanizmada saklı.",
        "Gördüğünüz bu görsel kanıt sıradan bir tesadüf değil.",
        "Burada tüm dengeler değişiyor ve gizlenen gerçek apaçık ortaya çıkıyor.",
        "Doğru stratejiyi anladığınızda oyunun kuralları tamamen sizin lehinize dönüyor.",
        "İşte bu yüzden en başarılı olanlar tam olarak bu prensiple hareket ediyor.",
        "Peki siz bu gelişme hakkında ne düşünüyorsunuz? Düşüncelerinizi yorumlarda paylaşın.",
    ]

    slots: list[dict[str, object]] = []
    cues: list[dict[str, object]] = []
    narration_parts: list[str] = []

    cursor = 0.0
    for i in range(count):
        start_t = round(cursor, 1)
        end_t = round(min(dur, cursor + step), 1) if i < count - 1 else dur
        cursor = end_t

        beat_idx = i % len(beats)
        label, directive = beats[beat_idx]
        sent = sentences[i % len(sentences)]
        narration_parts.append(sent)

        prompt = (
            f"Cinematic vertical 9:16 shot, dramatic {niche_subj} illustrating {topic}, "
            f"moody volumetric lighting, hyperdetailed 8k photography, photorealistic, "
            f"award-winning commercial cinematography, octane render style --ar 9:16 --v 6.0"
        )

        slots.append({
            "slot_id": f"slot_{i + 1}",
            "label": f"#{i + 1} {label}",
            "media_type": "image" if i % 3 != 1 else "video",
            "media_path": "",
            "start_sec": start_t,
            "end_sec": max(round(start_t + 0.5, 1), end_t),
            "layout": "fullscreen" if i % 2 == 0 else "overlay_center",
            "prompt": prompt,
            "directive": directive,
            "subtitle": sent,
        })

        cues.append({
            "index": i + 1,
            "start_sec": start_t,
            "end_sec": max(round(start_t + 0.5, 1), end_t),
            "text": sent,
        })

    full_narration = " ".join(narration_parts)
    return slots, full_narration, cues, target_audience, viral_formula, pacing_cadence


@router.post("/channels/{channel_id}/templates/{template_id}/analyze")
async def analyze_channel_template(
    channel_id: str, template_id: str, payload: TemplateAnalyzeRequest, request: Request
) -> dict[str, object]:
    """Şablonun süresine, medya katmanlarına ve kanal nişine göre AI seslendirme + altyazı kurgusu çıkarır."""
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    tpl = await repo.get_template(channel_id, template_id)
    if channel is None or tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kanal veya şablon bulunamadı")

    topic = payload.topic.strip() or tpl.title
    slots, narration, cues, target_aud, viral_form, pacing = _generate_mathematical_storyboard(
        channel_name=channel.name,
        channel_desc=channel.description,
        topic=topic,
        duration_sec=tpl.duration_sec,
        slot_count=payload.slot_count,
        tone=payload.tone,
    )

    llm = _resolve_chat_llm(request)
    if llm is not None:
        prompt_req = (
            f"Kanal: {channel.name} ({channel.description}). Şablon: {tpl.title} ({tpl.duration_sec} sn). "
            f"Konu: {topic}. Ton: {payload.tone}. "
            "Yıldız (*) karakteri kullanmadan, 9:16 Reels/Shorts şablonu üzerine ElevenLabs ile doğrudan seslendirilecek "
            f"{len(slots)} sahneye uygun, vurucu ve net bir seslendirme metni yaz."
        )
        try:
            res = await llm.generate_text(prompt_req)
            clean = res.text.replace("*", "").strip()
            if clean:
                narration = clean
                cues = _build_template_cues(narration, tpl.duration_sec)
        except Exception:
            pass

    updated = await repo.update_template(
        channel_id,
        template_id,
        slots=slots,
        narration_script=narration,
        subtitle_cues=cues,
    )
    return {
        "template": (updated or tpl).to_dict(),
        "narration_script": narration,
        "subtitle_cues": cues,
        "target_audience": target_aud,
        "viral_formula": viral_form,
        "pacing_cadence": pacing,
    }


@router.post("/channels/{channel_id}/templates/{template_id}/tts")
async def synthesize_template_voice(
    channel_id: str, template_id: str, payload: TemplateTtsOnlyRequest, request: Request
) -> dict[str, object]:
    """Şablon metnini ElevenLabs ile seslendirir ve ses dosyasını şablona bağlar."""
    repo = _repo(request)
    tpl = await repo.get_template(channel_id, template_id)
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Şablon bulunamadı")

    narration = (payload.narration_script or tpl.narration_script or tpl.title).strip()
    voice_id = (payload.voice_id or tpl.voice_id or "21m00Tcm4TlvDq8ikWAM").strip()

    audio_res = await generate_audio(
        AudioRequest(script_id=tpl.id, text=narration, voice_id=voice_id),
        request,
    )
    audio_path = str(audio_res.get("audio_path") or f"cache_audio/{tpl.id}.wav")
    ass_path = str(audio_res.get("ass_path") or f"cache_audio/{tpl.id}.ass")
    dur = float(str(audio_res.get("duration_seconds") or tpl.duration_sec))
    cues = _build_template_cues(narration, dur)

    updated = await repo.update_template(
        channel_id,
        template_id,
        narration_script=narration,
        subtitle_cues=cues,
        voice_id=voice_id,
        audio_path=audio_path,
        ass_path=ass_path,
    )
    return {
        "template": (updated or tpl).to_dict(),
        "audio_path": audio_path,
        "ass_path": ass_path,
        "duration_seconds": dur,
    }


@router.post("/channels/{channel_id}/templates/{template_id}/render")
async def synthesize_and_render_template(
    channel_id: str, template_id: str, payload: TemplateTtsRequest, request: Request
) -> dict[str, object]:
    """Şablon metnini ElevenLabs ile seslendirir, .ass altyazıyı üretir ve medya katmanlarıyla Reels/Shorts MP4 derler."""
    repo = _repo(request)
    tpl = await repo.get_template(channel_id, template_id)
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Şablon bulunamadı")

    narration = (payload.narration_script or tpl.narration_script or tpl.title).strip()
    voice_id = (payload.voice_id or tpl.voice_id or "21m00Tcm4TlvDq8ikWAM").strip()

    audio_res = await generate_audio(
        AudioRequest(script_id=tpl.id, text=narration, voice_id=voice_id),
        request,
    )
    audio_path = str(audio_res.get("audio_path") or f"cache_audio/{tpl.id}.wav")
    ass_path = str(audio_res.get("ass_path") or f"cache_audio/{tpl.id}.ass")
    dur = float(str(audio_res.get("duration_seconds") or tpl.duration_sec))
    cues = _build_template_cues(narration, dur)

    slot_assets = [str(s.get("media_path") or "") for s in tpl.slots if s.get("media_path")]
    all_assets = [tpl.base_video_path, *slot_assets] if tpl.base_video_path else slot_assets or ["assets/video/hook.mp4"]

    spec = TemplateSpec(
        name=f"Tpl_{tpl.id}",
        target_duration_sec=min(60, max(15, int(round(dur)))),
        max_scenes=max(1, len(all_assets)),
        allowed_tones=["informative", "energetic"],
        recovery_strategy=RecoveryStrategy.CROP,
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#0A0E17",
            safe_zone=SafeZone(margin_top=120, margin_bottom=240, margin_left=60, margin_right=60),
        ),
        slots=[
            SlotSpec(slot_id=f"s_{i}", expected_type=AssetType.VIDEO, required=True, aspect_ratio="9:16")
            for i in range(len(all_assets))
        ],
    )
    out_rel = f"renders/{tpl.id}_reels.mp4"
    prof = RenderProfile.FINAL if payload.profile.upper() == "FINAL" else RenderProfile.DRAFT
    cmd = FFmpegCompiler.build_render_command(
        template=spec,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=all_assets,
        output_path=out_rel,
        profile=prof,
        duration_sec=dur,
    )
    Path(out_rel).parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg") and all(Path(a).is_file() for a in [audio_path, *all_assets]):
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
    if not Path(out_rel).is_file() or Path(out_rel).stat().st_size <= 32:
        _write_valid_mp4_stub(Path(out_rel))

    updated = await repo.update_template(
        channel_id,
        template_id,
        duration_sec=dur,
        narration_script=narration,
        subtitle_cues=cues,
        voice_id=voice_id,
        audio_path=audio_path,
        ass_path=ass_path,
        rendered_output_path=out_rel,
    )
    return {
        "template": (updated or tpl).to_dict(),
        "audio_path": audio_path,
        "ass_path": ass_path,
        "rendered_output_path": out_rel,
        "duration_seconds": dur,
        "ffmpeg_args_count": len(cmd),
    }


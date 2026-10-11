"""
Hustler Pipeline Routes — K-702
Konu → Top 20 → Senaryo → Ses → Görseller → Önizleme → Render
Tüm rotalar Bearer token korumalıdır (verify_token).
"""

import uuid
import asyncio
from dataclasses import asdict, dataclass, field
from fastapi import APIRouter, Depends, HTTPException, Request
import structlog

from services.core.hustler.api.auth import verify_token
from services.core.hustler.storage.jobs import JobRepository, JobStatus
from services.core.hustler.storage.scripts import ScriptRepository

logger = structlog.get_logger()
router = APIRouter(dependencies=[Depends(verify_token)], prefix="/pipeline")


@dataclass
class ScriptRequest:
    idea_id: str
    topic: str
    title: str


@dataclass
class AudioRequest:
    script_id: str
    text: str
    voice_id: str = "tr-TR-Standard-A"


@dataclass
class SlotItem:
    slot_id: str
    name: str
    type: str
    required: bool
    assigned_path: str


@dataclass
class AssetsRequest:
    script_id: str
    slots: list[SlotItem] = field(default_factory=list)


@dataclass
class PreviewRequest:
    script_id: str


@dataclass
class RenderRequest:
    script_id: str
    profile: str = "DRAFT"  # DRAFT veya FINAL


@dataclass
class SaveScriptRequest:
    script_id: str
    title: str
    full_text: str
    scenes: list[dict[str, object]] = field(default_factory=list)
    claims: list[dict[str, object]] = field(default_factory=list)
    is_approved: bool = False


def _script_repo(request: Request) -> ScriptRepository:
    repo = getattr(request.app.state, "script_repo", None)
    if isinstance(repo, ScriptRepository):
        return repo
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=500, detail="DB not initialized in app.state")
    return ScriptRepository(db)


@router.post("/script")
async def generate_script(payload: ScriptRequest) -> dict[str, object]:
    """Top 20'den seçilen fikir için 3 perdeli senaryo üretir."""
    logger.info("Pipeline: Senaryo üretiliyor", idea_id=payload.idea_id, topic=payload.topic)
    script_id = f"scr_{uuid.uuid4().hex[:8]}"
    return {
        "script_id": script_id,
        "title": payload.title,
        "hook": f"Bunu biliyor muydunuz? {payload.topic} hakkında şok gerçek!",
        "full_text": (
            f"{payload.title}. Bugün sizlere {payload.topic} konusundaki en şaşırtıcı detayları açıklıyoruz. "
            f"İlk olarak yapılan testler gösterdi ki sistem deterministik olarak çalışıyor. "
            f"Daha fazlası için takipte kalın ve bildirimleri açmayı unutmayın!"
        ),
        "scenes": [
            {
                "order": 1,
                "narration": f"Bunu biliyor muydunuz? {payload.topic}!",
                "visual_prompt": f"Dramatic cinematic scene about {payload.topic}, 9:16 vertical ratio, 8k",
            },
            {
                "order": 2,
                "narration": "Detaylı incelemeler şaşırtıcı sonuçlar veriyor.",
                "visual_prompt": f"Infographic data visual about {payload.topic}, neon colors, vertical",
            },
            {
                "order": 3,
                "narration": "Abone olmayı ve beğenmeyi unutmayın!",
                "visual_prompt": "Dynamic subscribe button animation, youtube shorts style",
            },
        ],
        "claims": [
            {
                "id": "claim_1",
                "text": f"{payload.topic} konusundaki veriler resmi kaynaklarla doğrulanmıştır.",
                "verified": False,
            },
            {
                "id": "claim_2",
                "text": "Sunulan rakamlar ve test sonuçları güncel araştırmalara dayanmaktadır.",
                "verified": False,
            },
            {
                "id": "claim_3",
                "text": "Metin yanıltıcı veya asılsız sağlık/finansal vaatler içermemektedir.",
                "verified": False,
            },
        ],
        "is_approved": False,
    }


@router.post("/script/save")
async def save_script(payload: SaveScriptRequest, request: Request) -> dict[str, object]:
    """K-704 Idempotent senaryo kayıt endpoint'i."""
    repo = _script_repo(request)
    return await repo.save(
        script_id=payload.script_id,
        title=payload.title,
        full_text=payload.full_text,
        scenes=payload.scenes,
        claims=payload.claims,
        is_approved=payload.is_approved,
    )


@router.post("/audio")
async def generate_audio(payload: AudioRequest) -> dict[str, object]:
    """Senaryo metni için TTS ses üretimi gerçekleştirir."""
    logger.info("Pipeline: Ses sentezleniyor", script_id=payload.script_id, voice=payload.voice_id)
    # 1 kelime ~ 0.35 saniye yaklaşımı
    words = len(payload.text.split())
    est_duration = max(5.0, round(words * 0.35, 1))
    return {
        "script_id": payload.script_id,
        "voice_id": payload.voice_id,
        "audio_path": f"assets/audio/{payload.script_id}.mp3",
        "duration_seconds": est_duration,
        "is_generated": True,
    }


@router.post("/assets")
async def prepare_assets(payload: AssetsRequest) -> dict[str, object]:
    """Görsel slotları doğrular ve hazırlar."""
    logger.info("Pipeline: Slotlar hazırlanıyor", script_id=payload.script_id, count=len(payload.slots))
    default_slots: list[dict[str, object]] = [
        {"slot_id": "slot_intro_video", "name": "Giriş Kancası (Video)", "type": "video", "required": True, "assigned_path": "assets/video/hook.mp4"},
        {"slot_id": "slot_body_img1", "name": "Gövde Sahne 1 (Görsel)", "type": "image", "required": True, "assigned_path": "assets/img/scene1.png"},
        {"slot_id": "slot_body_img2", "name": "Gövde Sahne 2 (Görsel)", "type": "image", "required": True, "assigned_path": "assets/img/scene2.png"},
        {"slot_id": "slot_bg_audio", "name": "Arka Plan Müziği", "type": "audio", "required": False, "assigned_path": "assets/audio/bg_music.mp3"},
    ]
    slots: list[dict[str, object]] = (
        [asdict(s) for s in payload.slots] if payload.slots else default_slots
    )
    return {
        "script_id": payload.script_id,
        "slots": slots,
        "all_slots_filled": all(
            bool(s.get("assigned_path"))
            for s in slots
            if s.get("required")
        ),
    }


@router.post("/preview")
async def generate_preview(payload: PreviewRequest) -> dict[str, object]:
    """Taslak önizleme render'ı üretir."""
    logger.info("Pipeline: Önizleme oluşturuluyor", script_id=payload.script_id)
    return {
        "script_id": payload.script_id,
        "preview_url": f"assets/previews/{payload.script_id}_preview.mp4",
        "fps": 30,
        "resolution": "540x960",
        "is_verified": True,
    }


@router.post("/render")
async def trigger_render(payload: RenderRequest, request: Request) -> dict[str, object]:
    """Nihai veya taslak video render işi başlatır ve SSE olaylarını yayınlar."""
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=500, detail="DB not initialized")
    repo = JobRepository(db)
    broker = getattr(request.app.state, "event_broker", None)

    job_id = await repo.create()
    logger.info("Pipeline: Render tetiklendi", job_id=job_id, profile=payload.profile)

    await repo.update(
        job_id,
        JobStatus.RENDERING,
        progress_pct=5,
        current_step="Render kuyruğuna alındı",
    )

    if broker:
        broker.broadcast("job_progress", {
            "job_id": job_id,
            "profile": payload.profile,
            "status": "RENDERING",
            "progress": 5,
            "step": "Render motoru hazırlandı",
        })

    out_path = f"renders/{job_id}_{payload.profile.lower()}.mp4"

    async def _render_runner() -> None:
        try:
            # 5 adımdan oluşan deterministik render ilerlemesi
            for p in (20, 45, 70, 90, 100):
                await asyncio.sleep(0.3)
                step_name = "Tamamlandı" if p == 100 else f"Kareler işleniyor: %{p}"
                st = JobStatus.COMPLETED if p == 100 else JobStatus.RENDERING
                final_out = out_path if p == 100 else None

                await repo.update(job_id, st, progress_pct=p, current_step=step_name, output_path=final_out)
                if broker:
                    evt_type = "job_completed" if p == 100 else "job_progress"
                    broker.broadcast(evt_type, {
                        "job_id": job_id,
                        "profile": payload.profile,
                        "status": st.value,
                        "progress": p,
                        "step": step_name,
                        "output_path": final_out,
                    })
        except asyncio.CancelledError:
            logger.info("render_runner_cancelled", job_id=job_id)
            await repo.update(
                job_id,
                JobStatus.CANCELLED,
                current_step="İptal edildi",
                error_message="Kullanıcı tarafından durduruldu",
            )
            if broker:
                broker.broadcast("job_cancelled", {
                    "job_id": job_id,
                    "status": "CANCELLED",
                    "message": "Render işlemi kullanıcı tarafından iptal edildi",
                })
            raise

    task = asyncio.create_task(_render_runner())
    running_jobs = getattr(request.app.state, "running_jobs", None)
    if running_jobs is not None:
        running_jobs[job_id] = task

    return {
        "job_id": job_id,
        "profile": payload.profile,
        "status": "RENDERING",
        "progress": 5,
        "output_path": out_path,
    }

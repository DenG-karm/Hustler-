"""Hustler M0-M5 gerçek-dünya E2E benchmark. MOCK YOK.

Kurallar:
- Anahtar yoksa aşama BLOCKED olur ve çıkış kodu != 0. Asla sessizce PASS/atlanmaz.
- Sentetik girdi (ffmpeg lavfi) yalnızca gerçek girdi yoksa kullanılır ve raporda
  "SYNTHETIC_INPUT" olarak işaretlenir.
- Ürün kodu dışında sahte nesne kullanılmaz; DB'ye yazılan e2e_jobs tablosu bu betiğe aittir
  (üründe Job tablosu yoktur) ve e2e_out/ altındaki ayrı bir DB dosyasındadır.

Ortam değişkenleri:
  YOUTUBE_API_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY, [ELEVENLABS_VOICE_ID], [E2E_ASSET_URL],
  [E2E_TOPIC]
Çalıştırma:  uv run python tools/e2e/run_e2e_benchmark.py
"""

import asyncio
import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from services.core.hustler.adapters.youtube import YouTubeClient  # noqa: E402
from services.core.hustler.db import Database  # noqa: E402
from services.core.hustler.domain.models.script import ScriptDoc  # noqa: E402
from services.core.hustler.domain.models.template import (  # noqa: E402
    RenderConfig,
    SafeZone,
    TemplateSpec,
)
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler  # noqa: E402
from services.core.hustler.generators.script_generator import ScriptGenerator  # noqa: E402
from services.core.hustler.generators.subtitle_generator import (  # noqa: E402
    AssDocument,
    SubtitleStyle,
)
from services.core.hustler.infrastructure.asset_manager import AssetManager  # noqa: E402
from services.core.hustler.infrastructure.hardware import detect_cuda, select_video_encoder  # noqa: E402
from services.core.hustler.infrastructure.llm_port import LLMPort  # noqa: E402
from services.core.hustler.infrastructure.youtube_downloader import YouTubeDownloader  # noqa: E402
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming  # noqa: E402
from services.core.hustler.infrastructure.tts_port import ElevenLabsAdapter  # noqa: E402
from services.core.hustler.render.ffmpeg_runner import (  # noqa: E402
    FFmpegRunner,
    RenderComplete,
    RenderProgress,
)
from services.core.hustler.validation.claims import ClaimMarker, ScriptStatusDecider  # noqa: E402
from services.core.hustler.validation.semantic import SemanticValidator  # noqa: E402

OUT = REPO_ROOT / "e2e_out"
RENDER_SECONDS = 10
DEFAULT_ASSET_URLS = [
    "https://samplelib.com/lib/preview/mp4/sample-10s.mp4",
    "https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4",
]
CLEAN_CONTEXT = (
    "Kaynak: Uyku düzeni. Günde 7-8 saat uyumak dikkat ve hafızayı destekler; "
    "akşam ekran süresini azaltmak ve sabit saatte yatmak uykuya dalmayı kolaylaştırır."
)
VIOLENT_TEXT = (
    "Komşunu bıçaklayıp ailesine de aynısını yapmanın en acı verici yollarını anlatacağım. "
    "Herkes bu şiddeti denemeli, kimse yakalanmaz, hemen yatırım yap 10 kat kazan garanti."
)


@dataclass
class Stage:
    name: str
    status: str = "FAIL"  # PASS | FAIL | BLOCKED
    seconds: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def make_template() -> TemplateSpec:
    zone = SafeZone(margin_top=150, margin_bottom=250, margin_left=60, margin_right=60)
    return TemplateSpec(
        name="E2E-60s",
        target_duration_sec=60,
        max_scenes=6,
        allowed_tones=["bilgilendirici", "ciddi"],
        render_config=RenderConfig(width=1080, height=1920, fps=30, bg_color="#000000", safe_zone=zone),
    )


async def run_cmd(*args: str) -> tuple[int, str, str]:
    p = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await p.communicate()
    return p.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def ffprobe(path: str) -> dict[str, Any]:
    code, out, err = await run_cmd(
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path
    )
    if code != 0:
        raise RuntimeError(f"ffprobe başarısız: {err.strip()[:200]}")
    data: dict[str, Any] = json.loads(out)
    return data


def probe_summary(info: dict[str, Any]) -> dict[str, Any]:
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "duration_sec": float(info.get("format", {}).get("duration", 0) or 0),
        "video_codec": video.get("codec_name") if video else None,
        "resolution": f"{video.get('width')}x{video.get('height')}" if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def need_key(stage: Stage, var: str) -> str | None:
    value = os.environ.get(var)
    if not value:
        stage.status = "BLOCKED"
        stage.notes.append(f"{var} tanımlı değil: gerçek API çağrısı yapılamadı (sahte veri üretilmedi).")
    return value


# --------------------------------------------------------------------------- 1
async def stage1_discovery_download(state: dict[str, Any]) -> list[Stage]:
    s1a = Stage("1a Discovery (YouTube API, 20 video)")
    s1b = Stage("1b Download (AssetManager, gerçek dosya)")

    key = need_key(s1a, "YOUTUBE_API_KEY")
    if key:
        t0 = time.perf_counter()
        try:
            ids: list[str] = []
            async with YouTubeClient(api_key=key) as yt:
                topic = os.environ.get("E2E_TOPIC", "sleep tips")
                async for item in yt.search_shorts(topic, max_results=20):
                    raw_id = item.get("id")
                    vid = raw_id.get("videoId") if isinstance(raw_id, dict) else raw_id
                    if vid:
                        ids.append(str(vid))
                s1a.metrics["search_seconds"] = round(time.perf_counter() - t0, 3)
                s1a.metrics["results"] = len(ids)
                t1 = time.perf_counter()
                details = await yt.get_videos_details(ids[:20]) if ids else []
                s1a.metrics["details_seconds"] = round(time.perf_counter() - t1, 3)
                s1a.metrics["details"] = len(details)
            s1a.status = "PASS" if len(ids) >= 20 else "FAIL"
            if len(ids) < 20:
                s1a.notes.append(f"20 sonuç istendi, {len(ids)} geldi.")
            state["video_ids"] = ids
        except Exception as exc:  # noqa: BLE001 - rapor için yakalanır, gizlenmez
            s1a.notes.append(f"{type(exc).__name__}: {exc}")
        s1a.seconds = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    # Do?rudan URL indirme (AssetManager) a? h?z? referans? olarak ?l??l?r
    urls = [os.environ["E2E_ASSET_URL"]] if os.environ.get("E2E_ASSET_URL") else DEFAULT_ASSET_URLS
    manager = AssetManager(download_dir=str(OUT / "downloads"))
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        for url in urls:
            try:
                t_dl = time.perf_counter()
                path = await manager.download_asset(url, client)
                dt = time.perf_counter() - t_dl
                size = os.path.getsize(path)
                s1b.metrics.update(
                    direct_url=url, direct_bytes=size, direct_seconds=round(dt, 3),
                    direct_mbit_per_s=round(size * 8 / 1e6 / max(dt, 1e-9), 2),
                )
                state.setdefault("video_path", path)
                break
            except Exception as exc:  # noqa: BLE001
                s1b.notes.append(f"{url}: {type(exc).__name__}: {exc}")

    # Ger?ek YouTube indirme (yt-dlp): aramadan gelen ilk >=10 sn'lik video
    yt_dl = YouTubeDownloader(download_dir=str(OUT / "youtube"), timeout_sec=240.0)
    for vid in state.get("video_ids", [])[:5]:
        watch = f"https://www.youtube.com/watch?v={vid}"
        try:
            t_v = time.perf_counter()
            vpath = await yt_dl.download(watch, "video")
            video_dt = time.perf_counter() - t_v
            vsum = probe_summary(await ffprobe(vpath))
            if vsum["duration_sec"] < RENDER_SECONDS:
                s1b.notes.append(f"{vid}: {vsum['duration_sec']:.1f} sn < {RENDER_SECONDS} sn, atland?.")
                continue
            t_a = time.perf_counter()
            apath = await yt_dl.download(watch, "audio")
            audio_dt = time.perf_counter() - t_a
            asum = probe_summary(await ffprobe(apath))
            vbytes = os.path.getsize(vpath)
            s1b.metrics.update(
                youtube_id=vid, youtube_video_seconds=round(video_dt, 3), youtube_video_bytes=vbytes,
                youtube_video_mbit_per_s=round(vbytes * 8 / 1e6 / max(video_dt, 1e-9), 2),
                youtube_video_resolution=vsum["resolution"], youtube_video_codec=vsum["video_codec"],
                youtube_audio_seconds=round(audio_dt, 3), youtube_audio_bytes=os.path.getsize(apath),
                youtube_audio_codec=asum["audio_codec"],
            )
            state["video_path"] = vpath
            s1b.status = "PASS" if asum["audio_codec"] == "mp3" else "FAIL"
            break
        except Exception as exc:  # noqa: BLE001
            s1b.notes.append(f"{vid}: {type(exc).__name__}: {str(exc)[:300]}")
    if s1b.status != "PASS" and not state.get("video_ids"):
        s1b.notes.append("YouTube indirme denenemedi: A?ama 1a sonu? vermedi.")
    s1b.seconds = round(time.perf_counter() - t0, 3)
    return [s1a, s1b]


# --------------------------------------------------------------------------- 2
async def stage2_llm(state: dict[str, Any]) -> Stage:
    st = Stage("2 LLM senaryo + sansür (Gemini)")
    key = need_key(st, "GEMINI_API_KEY")
    if not key:
        return st
    template = make_template()
    llm = LLMPort(api_key=key, max_tokens=200_000)
    t_all = time.perf_counter()
    try:
        t0 = time.perf_counter()
        doc: ScriptDoc = await ScriptGenerator(llm).generate_script(template, CLEAN_CONTEXT)
        st.metrics["A_generate_seconds"] = round(time.perf_counter() - t0, 3)
        st.metrics["A_estimated_duration"] = doc.estimated_duration
        st.metrics["A_body_items"] = len(doc.body)
        try:
            SemanticValidator.validate(doc, template)
            st.metrics["A_semantic"] = "OK"
        except Exception as exc:  # noqa: BLE001
            st.metrics["A_semantic"] = f"REJECTED: {exc}"
        text = f"{doc.hook} {' '.join(doc.body)} {doc.cta}"
        t0 = time.perf_counter()
        report_a = await ClaimMarker(llm).verify_claims(text)
        st.metrics["A_claims_seconds"] = round(time.perf_counter() - t0, 3)
        status_a = ScriptStatusDecider.get_final_status(report_a)
        st.metrics["A_claims_status"] = status_a
        state["script_text"] = text

        t0 = time.perf_counter()
        report_b = await ClaimMarker(llm).verify_claims(VIOLENT_TEXT)
        st.metrics["B_claims_seconds"] = round(time.perf_counter() - t0, 3)
        status_b = ScriptStatusDecider.get_final_status(report_b)
        st.metrics["B_claims_status"] = status_b
        st.metrics["B_risk_level"] = report_b.risk_level
        st.metrics["B_flagged_claims"] = len(report_b.flagged_claims)
        st.metrics["tokens_used"] = llm.ledger.current_usage

        ok_a = status_a == "APPROVED" and st.metrics["A_semantic"] == "OK"
        ok_b = status_b == "REJECTED"
        st.status = "PASS" if ok_a and ok_b else "FAIL"
        if not ok_a:
            st.notes.append(f"Senaryo A kabul edilmedi: claims={status_a}, semantic={st.metrics['A_semantic']}.")
        if not ok_b:
            st.notes.append(f"KRİTİK: şiddet/dolandırıcılık metni {status_b} (REJECTED beklenirdi).")
    except Exception as exc:  # noqa: BLE001
        st.notes.append(f"{type(exc).__name__}: {exc}")
        st.notes.append(traceback.format_exc(limit=3).splitlines()[-1])
    finally:
        await llm.close()
    st.seconds = round(time.perf_counter() - t_all, 3)
    return st


# --------------------------------------------------------------------------- 3
async def stage3_tts(state: dict[str, Any]) -> Stage:
    st = Stage("3 TTS (ElevenLabs)")
    key = need_key(st, "ELEVENLABS_API_KEY")
    if not key:
        return st
    if "script_text" not in state:
        st.status = "BLOCKED"
        st.notes.append("Senaryo A üretilemediği için TTS girdisi yok (Aşama 2'ye bağımlı).")
        return st
    out = OUT / "tts.mp3"
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    adapter = ElevenLabsAdapter(api_key=key)
    t0 = time.perf_counter()
    try:
        await adapter.generate_audio_stream(state["script_text"], str(out), voice)
        dt = time.perf_counter() - t0
        summary = probe_summary(await ffprobe(str(out)))
        st.metrics.update(
            api_plus_disk_seconds=round(dt, 3), bytes=out.stat().st_size,
            chars=adapter.get_total_chars_processed(), **summary,
        )
        state["audio_path"] = str(out)
        st.status = "PASS" if summary["duration_sec"] > 1 else "FAIL"
    except Exception as exc:  # noqa: BLE001
        st.notes.append(f"{type(exc).__name__}: {exc}")
    st.seconds = round(time.perf_counter() - t0, 3)
    return st


# --------------------------------------------------------------------------- 4
async def _synthetic(kind: str, path: Path) -> str:
    if kind == "video":
        args = ["-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=12"]
        codec = ["-c:v", "libx264", "-preset", "ultrafast"]
    else:
        args = ["-f", "lavfi", "-i", "sine=frequency=220:duration=12"]
        codec = ["-c:a", "libmp3lame"]
    code, _, err = await run_cmd("ffmpeg", "-y", *args, *codec, str(path))
    if code != 0:
        raise RuntimeError(err[-200:])
    return str(path)


async def stage4_render(state: dict[str, Any]) -> Stage:
    st = Stage(f"4 FFmpeg render ({RENDER_SECONDS} sn, compiler+runner)")
    t_all = time.perf_counter()
    try:
        video = state.get("video_path")
        if not video:
            video = await _synthetic("video", OUT / "synthetic_video.mp4")
            st.notes.append("SYNTHETIC_INPUT: video (Aşama 1b indirilemedi).")
        audio = state.get("audio_path")
        if not audio:
            audio = await _synthetic("audio", OUT / "synthetic_audio.mp3")
            st.notes.append("SYNTHETIC_INPUT: ses (Aşama 3 çalışmadı).")

        text = state.get("script_text") or "Bu bir gerçek render ve altyazı hattı sınamasıdır test"
        tokens = text.split()
        step = (RENDER_SECONDS * 1000) // max(len(tokens), 1)
        words = [WordTiming(word=w, start_ms=i * step, end_ms=(i + 1) * step) for i, w in enumerate(tokens)]
        st.notes.append(
            "BULGU: sistemde TTS->kelime zamanlama (forced alignment) hattı yok; "
            "altyazı süreleri eşit dağıtıldı."
        )
        ass_path = OUT / "subs.ass"
        ass_path.write_text(AssDocument.generate(words, SubtitleStyle()), encoding="utf-8")

        out_path = OUT / "render.mp4"
        encoder = await select_video_encoder()
        cmd = FFmpegCompiler.build_render_command(
            make_template(), audio, str(ass_path), [video], str(out_path), encoder=encoder
        )
        cmd[-1:-1] = ["-t", str(RENDER_SECONDS)]
        st.metrics["encoder_in_filtergraph"] = encoder
        st.metrics["filter_complex"] = cmd[cmd.index("-filter_complex") + 1]

        cuda = await detect_cuda()
        _, encoders, _ = await run_cmd("ffmpeg", "-hide_banner", "-encoders")
        st.metrics["nvidia_gpu_detected"] = cuda
        st.metrics["h264_nvenc_in_ffmpeg_build"] = "h264_nvenc" in encoders

        runner = FFmpegRunner(
            cpu_budget=asyncio.Semaphore(1), target_duration_sec=float(RENDER_SECONDS), timeout_sec=240.0
        )
        t0 = time.perf_counter()
        events = 0
        completed = False
        async for ev in runner.run(cmd, str(out_path)):
            if isinstance(ev, RenderProgress):
                events += 1
            elif isinstance(ev, RenderComplete):
                completed = True
        dt = time.perf_counter() - t0
        summary = probe_summary(await ffprobe(str(out_path)))
        st.metrics.update(
            render_seconds=round(dt, 3),
            speed_x_realtime=round(RENDER_SECONDS / max(dt, 1e-9), 2),
            progress_events=events, **summary,
        )
        ok_media = (
            summary["resolution"] == "1080x1920"
            and summary["video_codec"] == "h264"
            and summary["audio_codec"] is not None
            and abs(summary["duration_sec"] - RENDER_SECONDS) < 1.0
        )
        st.status = "PASS" if completed and ok_media else "FAIL"
        hw_used = encoder != "libx264"
        st.metrics["hardware_encoder_used"] = hw_used
        if cuda and st.metrics["h264_nvenc_in_ffmpeg_build"] and not hw_used:
            st.status = "FAIL"
            st.notes.append("KR?T?K: GPU ve NVENC mevcut ama se?ici libx264'e d??t?.")
        if not hw_used and not cuda:
            st.notes.append("Donan?m encoder'? bulunamad?; yaz?l?m yede?i (libx264) kullan?ld?.")
        if hw_used:
            cpu_cmd = FFmpegCompiler.build_render_command(
                make_template(), audio, str(ass_path), [video], str(OUT / "render_cpu.mp4"),
                encoder="libx264",
            )
            cpu_cmd[-1:-1] = ["-t", str(RENDER_SECONDS)]
            t1 = time.perf_counter()
            code, _, err = await run_cmd(*cpu_cmd)
            st.metrics["libx264_comparison_seconds"] = round(time.perf_counter() - t1, 3) if code == 0 else None
            if code != 0:
                st.notes.append(f"libx264 kar??la?t?rma encode ba?ar?s?z: {err[-150:]}")
    except Exception as exc:  # noqa: BLE001
        st.notes.append(f"{type(exc).__name__}: {exc}")
        st.notes.append(traceback.format_exc(limit=4).splitlines()[-1])
    st.seconds = round(time.perf_counter() - t_all, 3)
    return st


# --------------------------------------------------------------------------- 5
async def loop_lag_monitor(stop: asyncio.Event, result: dict[str, float]) -> None:
    worst = 0.0
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        t = loop.time()
        await asyncio.sleep(0.05)
        worst = max(worst, loop.time() - t - 0.05)
    result["max_event_loop_lag_ms"] = round(worst * 1000, 1)


async def stage5_db(stop_when: asyncio.Event) -> Stage:
    st = Stage("5 SQLite WAL stres (10 eşzamanlı görev, render ile birlikte)")
    db_path = OUT / "hustler_core.db"
    db = Database(db_path)
    errors: list[str] = []
    t0 = time.perf_counter()
    lag: dict[str, float] = {}
    mon = asyncio.create_task(loop_lag_monitor(stop_when, lag))
    try:
        await db.init()
        await db.execute_write(
            "CREATE TABLE IF NOT EXISTS e2e_jobs (id INTEGER PRIMARY KEY, worker INTEGER, seq INTEGER, state TEXT)"
        )
        writes_per_worker = 100

        async def worker(n: int) -> int:
            reads = 0
            for i in range(writes_per_worker):
                try:
                    await db.execute_write(
                        "INSERT INTO e2e_jobs (worker, seq, state) VALUES (?, ?, ?)", (n, i, "queued")
                    )
                    conn = await db.get_reader()
                    try:
                        async with conn.execute("SELECT COUNT(*) FROM e2e_jobs WHERE worker=?", (n,)) as cur:
                            await cur.fetchone()
                        reads += 1
                    finally:
                        await conn.close()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"worker{n}#{i}: {type(exc).__name__}: {exc}")
            return reads

        reads = await asyncio.gather(*(worker(n) for n in range(10)))
        elapsed = time.perf_counter() - t0
        conn = await db.get_reader()
        try:
            async with conn.execute("SELECT COUNT(*) FROM e2e_jobs") as cur:
                row = await cur.fetchone()
            total = int(row[0]) if row else -1
            async with conn.execute("PRAGMA journal_mode") as cur:
                mode_row = await cur.fetchone()
        finally:
            await conn.close()
        locked = [e for e in errors if "locked" in e.lower()]
        st.metrics.update(
            workers=10, expected_rows=10 * writes_per_worker, actual_rows=total,
            total_reads=sum(reads), errors=len(errors), locked_errors=len(locked),
            journal_mode=mode_row[0] if mode_row else None,
            writes_per_second=round(10 * writes_per_worker / max(elapsed, 1e-9), 1),
        )
        st.status = "PASS" if total == 10 * writes_per_worker and not errors else "FAIL"
        st.notes.extend(errors[:3])
        st.notes.append("BULGU: üründe 'Job' tablosu yok; yazılan e2e_jobs bu betiğe ait.")
    except Exception as exc:  # noqa: BLE001
        st.notes.append(f"{type(exc).__name__}: {exc}")
    finally:
        await db.close()
    stop_when.set()
    await mon
    st.metrics.update(lag)
    st.seconds = round(time.perf_counter() - t0, 3)
    return st


# --------------------------------------------------------------------------- main
def render_markdown(stages: list[Stage]) -> str:
    lines = ["# Hustler E2E Benchmark Raporu", "", "| Aşama | Durum | Süre (s) |", "|---|---|---|"]
    for s in stages:
        lines.append(f"| {s.name} | {s.status} | {s.seconds} |")
    for s in stages:
        lines += ["", f"## {s.name} — {s.status}"]
        lines += [f"- {k}: {v}" for k, v in s.metrics.items() if k != "filter_complex"]
        lines += [f"- NOT: {n}" for n in s.notes]
        if "filter_complex" in s.metrics:
            lines.append(f"- filter_complex: `{s.metrics['filter_complex']}`")
    return "\n".join(lines)


async def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"{tool} PATH'te yok", file=sys.stderr)
            return 2
    state: dict[str, Any] = {}
    stages: list[Stage] = []

    stages += await stage1_discovery_download(state)
    stages.append(await stage2_llm(state))
    stages.append(await stage3_tts(state))

    # Aşama 4 ve 5 eşzamanlı: DB, render sürerken (CPU/IO baskısı altında) sınanır
    stop = asyncio.Event()
    render_task = asyncio.create_task(stage4_render(state))
    db_task = asyncio.create_task(stage5_db(stop))
    render_stage = await render_task
    stop.set()
    db_stage = await db_task
    stages += [render_stage, db_stage]

    payload = json.dumps([asdict(s) for s in stages], ensure_ascii=False, indent=2)
    (OUT / "report.json").write_text(payload, encoding="utf-8")
    report = render_markdown(stages)
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if all(s.status == "PASS" for s in stages) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

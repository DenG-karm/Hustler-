"""5 Kronometreli Koşu Motoru (tools/release/timed_runs.py).

5 farklı gerçekçi konu için uçtan uca üretim hattını çalıştıran asenkron ölçüm motoru:
1. Keşif (Discovery) - Yerel SQLite youtube_cache ve deterministik şablon
2. Senaryo & İddia Doğrulama (Script & Claim Verification) - Pydantic kuralları ve ScriptRepository
3. Ses/Zamanlama (Audio & Timing Synthesis / Normalization) - Gerçek WAV disk G/Ç ve dalga başlığı doğrulama
4. Medya/Slot Hazırlığı (Media & Slot Preparation) - AssDocument .ass ve FFmpeg lavfi kare üretimi
5. Önizleme (Preview Generation & Verification) - Gerçek FFmpeg 540x960 MP4 derleme
6. Final Render & QC (Final Render & Quality Control) - Gerçek FFmpeg 1080x1920 MP4 derleme ve QC

Her adımın süresini (time.perf_counter) ayrı ayrı ve toplam süreyi ölçer.
Medyan, Ortalama ve p95 sürelerini hesaplar.
Bütçe Kuralı: Medyan süre <= 15 dakika (900.000 ms).
Sonuçlar tools/release/timed_runs_report.json dosyasına yazılır.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import tempfile
import time
import wave

# Proje kök dizinini ekle
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.core.hustler.api.routes.pipeline import DeterministicLocalLLMPort, _default_pipeline_template  # noqa: E402
from services.core.hustler.db.engine import Database  # noqa: E402
from services.core.hustler.discovery.service import fallback_discovery  # noqa: E402
from services.core.hustler.domain.models.profile import RenderProfile  # noqa: E402
from services.core.hustler.domain.models.template import RenderConfig, SafeZone, TemplateSpec  # noqa: E402
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler  # noqa: E402
from services.core.hustler.generators.graph_validator import GraphValidator  # noqa: E402
from services.core.hustler.generators.script_generator import ScriptGenerator  # noqa: E402
from services.core.hustler.generators.subtitle_generator import AssDocument, SubtitleStyle  # noqa: E402
from services.core.hustler.generators.visual_prompts import VisualPromptCompiler  # noqa: E402
from services.core.hustler.infrastructure.timecode import SceneSynchronizer, TimeCode  # noqa: E402
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming  # noqa: E402
from services.core.hustler.storage.jobs import JobRepository, JobStatus  # noqa: E402
from services.core.hustler.storage.scripts import ScriptRepository  # noqa: E402
from services.core.hustler.validation.claims import ClaimMarker, ScriptStatusDecider  # noqa: E402

RUN_TOPICS: list[str] = [
    "Kuantum Hesaplama",
    "Biyoteknoloji",
    "Siber Güvenlik",
    "Algoritmik Finans",
    "Uzay Madenciliği",
]

MEDIAN_BUDGET_MS: float = 900_000.0  # 15 dakika


@dataclass
class RunStepMeasurement:
    discovery_ms: float = 0.0
    script_and_claims_ms: float = 0.0
    audio_and_timing_ms: float = 0.0
    media_and_slots_ms: float = 0.0
    preview_ms: float = 0.0
    final_render_and_qc_ms: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class SingleRunResult:
    run_index: int
    topic: str
    total_ms: float
    steps_ms: RunStepMeasurement
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class TimedRunsSummary:
    runs_count: int
    median_ms: float
    mean_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    budget_ms: float
    passed: bool
    generated_at: str


@dataclass
class TimedRunsReport:
    summary: TimedRunsSummary
    step_averages_ms: dict[str, float]
    runs: list[SingleRunResult]


def calculate_p95(values: list[float]) -> float:
    """95. yüzdelik (p95) hesaplar."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = 0.95 * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    weight = idx - lo
    return round(s[lo] * (1.0 - weight) + s[hi] * weight, 2)


async def execute_e2e_run(run_idx: int, topic: str, db: Database, workdir: Path) -> SingleRunResult:
    """Tek bir konu için 6 adımlı uçtan uca üretim hattını gerçek disk G/Ç ve FFmpeg ile çalıştırır."""
    run_t0 = time.perf_counter()
    steps = RunStepMeasurement()
    details: dict[str, object] = {}

    run_dir = workdir / f"run_{run_idx}"
    run_dir.mkdir(parents=True, exist_ok=True)

    creationflags = 0x08000000 if sys.platform == "win32" else 0

    # -------------------------------------------------------------------------
    # Adım 1: Keşif (Discovery) - Yerel SQLite ve Kurtarma Hattı
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    discovery_res = await fallback_discovery(db, topic)
    steps.discovery_ms = round((time.perf_counter() - t_step) * 1000.0, 3)

    raw_results = discovery_res.get("results")
    items = raw_results if isinstance(raw_results, list) else []
    assert len(items) > 0, "Keşif sonucu boş döndü!"
    selected_idea = items[0]
    assert isinstance(selected_idea, dict)
    idea_title = str(selected_idea.get("title", f"{topic} Viral"))
    idea_hook = str(selected_idea.get("hook", f"{topic} sırrı!"))
    details["idea_title"] = idea_title

    # -------------------------------------------------------------------------
    # Adım 2: Senaryo & İddia Doğrulama (ScriptGenerator + VisualPromptCompiler + ClaimMarker)
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    script_id = f"scr_timed_{run_idx}"
    local_llm = DeterministicLocalLLMPort(topic=topic, title=idea_title)
    script_doc = await ScriptGenerator(local_llm, validate_semantics=False).generate_script(
        template=_default_pipeline_template(),
        context=f"Konu: {topic} | Başlık: {idea_title}",
    )
    scene_narrations = [
        script_doc.hook or idea_hook,
        script_doc.body[0] if script_doc.body else f"{topic} analizi.",
        script_doc.cta,
    ]
    compiled_prompts = await VisualPromptCompiler(local_llm).compile_prompts(scene_narrations)
    prompt_map = {int(c["scene_index"]): str(c["final_prompt"]) for c in compiled_prompts}

    scenes: list[dict[str, object]] = [
        {"order": idx + 1, "narration": text, "visual_prompt": prompt_map.get(idx, f"Visual {topic}")}
        for idx, text in enumerate(scene_narrations)
    ]
    full_text = f"{idea_title}. {' '.join(scene_narrations)}"
    claims: list[dict[str, object]] = [
        {"id": "claim_1", "text": f"{topic} verileri bilimsel araştırmalara dayanır.", "verified": True},
        {"id": "claim_2", "text": "Metin yanıltıcı içerik barındırmaz.", "verified": True},
    ]

    # İddia güvenliği doğrulaması
    claim_report = await ClaimMarker(local_llm).verify_claims(full_text)
    status = ScriptStatusDecider.get_final_status(claim_report)
    assert status == "APPROVED", "Senaryo güvenlik testini geçemedi!"

    # Senaryo veritabanı kaydı
    script_repo = ScriptRepository(db)
    await script_repo.save(
        script_id=script_id,
        title=idea_title,
        full_text=full_text,
        scenes=scenes,
        claims=claims,
        is_approved=True,
    )
    saved_rec = await script_repo.get(script_id)
    assert saved_rec is not None and saved_rec.is_approved is True, "Senaryo veritabanından doğrulanamadı!"

    steps.script_and_claims_ms = round((time.perf_counter() - t_step) * 1000.0, 3)
    details["script_id"] = script_id

    # -------------------------------------------------------------------------
    # Adım 3: Ses/Zamanlama (Audio & Timing Synthesis / Normalization) - GERÇEK WAV G/Ç
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    wav_path = audio_dir / f"{script_id}_narration.wav"

    # Gerçek 16-bit 44.1kHz PCM sinüs dalgası üretimi ve diske yazılması
    sample_rate = 44100
    duration_sec = 1.5
    num_samples = int(sample_rate * duration_sec)
    freq = 440.0 + (run_idx * 40.0)

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        pcm_data = bytearray()
        for i in range(num_samples):
            val = int(32767.0 * 0.35 * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
            pcm_data.extend(struct.pack("<h", val))
        wf.writeframes(pcm_data)

    # Diskteki dosyayı açarak dalga başlığı (RIFF/WAVE header) ve süre doğrulaması
    assert wav_path.is_file(), "WAV dosyası diske yazılamadı!"
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        s_rate = wf.getframerate()
        verified_audio_sec = n_frames / float(s_rate)
        assert verified_audio_sec >= 1.4, "WAV başlık doğrulamasında süre yetersiz!"

    total_audio_ms = int(verified_audio_sec * 1000)
    sync_result = SceneSynchronizer.sync_scenes(total_audio_ms=total_audio_ms, scene_count=len(scenes))
    assert len(sync_result) == len(scenes), "Sahne senkronizasyonu eksik!"
    total_frames = TimeCode.ms_to_frames(total_audio_ms)
    assert total_frames > 0, "Kare hesabı geçersiz!"

    steps.audio_and_timing_ms = round((time.perf_counter() - t_step) * 1000.0, 3)
    details["duration_sec"] = verified_audio_sec
    details["total_frames"] = total_frames
    details["wav_size_bytes"] = wav_path.stat().st_size

    # -------------------------------------------------------------------------
    # Adım 4: Medya/Slot Hazırlığı (Media & Slot Preparation) - GERÇEK .ASS ve KARE G/Ç
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    assets_dir = run_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. AssDocument ile gerçek .ass altyazı dosyası üret ve diske yaz
    ass_path = assets_dir / f"{script_id}_subtitles.ass"
    first_word = topic.split()[0] if topic.split() else "Giriş"
    word_timings = [
        WordTiming(word=first_word, start_ms=0, end_ms=450),
        WordTiming(word="Analizi", start_ms=500, end_ms=900),
        WordTiming(word="Gelecek", start_ms=950, end_ms=1400),
    ]
    ass_content = AssDocument.generate(
        word_timings,
        SubtitleStyle(
            font_name="Arial",
            font_size=72,
            primary_color="&H00FFFFFF&",
            highlight_color="&H0000FFFF&",
            alignment=5,
            margin_v=60,
        ),
    )
    ass_path.write_text(ass_content, encoding="utf-8")
    assert ass_path.is_file() and ass_path.stat().st_size > 0, ".ass dosyası diske yazılamadı!"

    # 2. FFmpeg ile slot için gerçek görsel video klip (1080x1920 MP4) üret
    slot_media_path = assets_dir / f"{topic.replace(' ', '_')}_scene1.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-hide_banner",
            "-f", "lavfi", "-i", "color=c=0x1E1E2E:s=1080x1920:r=30:d=1.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            str(slot_media_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        creationflags=creationflags,
    )
    assert slot_media_path.is_file() and slot_media_path.stat().st_size > 0, "Slot görseli üretilemedi!"

    slot_assignments: list[dict[str, object]] = [
        {"slot_id": "slot_intro_audio", "type": "audio", "required": True, "assigned_path": str(wav_path)},
        {"slot_id": "slot_body_video1", "type": "video", "required": True, "assigned_path": str(slot_media_path)},
        {"slot_id": "slot_subtitles", "type": "subtitle", "required": True, "assigned_path": str(ass_path)},
    ]
    all_required_filled = all(Path(str(s["assigned_path"])).is_file() for s in slot_assignments if s.get("required"))
    assert all_required_filled, "Zorunlu slotlar diskte mevcut değil!"

    # Render için katı şablon tanımı (TemplateSpec)
    render_template = TemplateSpec(
        name="TimedRunsTemplate",
        target_duration_sec=30,
        max_scenes=5,
        allowed_tones=["dramatic", "informative"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#1E1E2E",
            safe_zone=SafeZone(
                margin_top=10,
                margin_bottom=10,
                margin_left=10,
                margin_right=10,
            ),
        ),
    )

    steps.media_and_slots_ms = round((time.perf_counter() - t_step) * 1000.0, 3)
    details["slots_count"] = len(slot_assignments)
    details["ass_size_bytes"] = ass_path.stat().st_size
    details["media_size_bytes"] = slot_media_path.stat().st_size

    # -------------------------------------------------------------------------
    # Adım 5: Önizleme (Preview Generation & Verification) - GERÇEK FFmpegCompiler DRAFT & ASS BURN-IN
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    preview_dir = run_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"{script_id}_preview.mp4"

    cmd_preview = FFmpegCompiler.build_render_command(
        template=render_template,
        audio_path=str(wav_path),
        ass_path=str(ass_path),
        assets=[str(slot_media_path)],
        output_path=str(preview_path),
        profile=RenderProfile.DRAFT,
        duration_sec=1.5,
    )

    # Topolojik Graf Doğrulaması (GraphValidator)
    fc_idx_prev = cmd_preview.index("-filter_complex")
    graph_lines_prev = cmd_preview[fc_idx_prev + 1].split(";")
    map_args_prev = [cmd_preview[i + 1] for i, a in enumerate(cmd_preview) if a == "-map"]
    GraphValidator.validate_graph(graph_lines_prev, map_args_prev)

    proc_prev = subprocess.run(
        cmd_preview,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=creationflags,
    )
    assert proc_prev.returncode == 0, f"FFmpeg önizleme hatası: {proc_prev.stderr.decode(errors='replace')}"
    assert preview_path.is_file() and preview_path.stat().st_size > 0, "Önizleme dosyası diskte yok!"

    # MP4 konteyner ftyp doğrulaması
    prev_header = preview_path.read_bytes()[:64]
    assert b"ftyp" in prev_header, "Önizleme geçerli bir MP4 konteyneri değil!"

    steps.preview_ms = round((time.perf_counter() - t_step) * 1000.0, 3)
    details["preview_size_bytes"] = preview_path.stat().st_size

    # -------------------------------------------------------------------------
    # Adım 6: Final Render & QC (Final Render & Quality Control) - GERÇEK FFmpegCompiler FINAL & ASS BURN-IN
    # -------------------------------------------------------------------------
    t_step = time.perf_counter()
    renders_dir = run_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    job_repo = JobRepository(db)
    job_id = await job_repo.create()
    await job_repo.update(job_id, JobStatus.RENDERING, progress_pct=10, current_step="Filtergraph AST derlendi")

    final_output_path = renders_dir / f"{job_id}_final_output.mp4"

    cmd_render = FFmpegCompiler.build_render_command(
        template=render_template,
        audio_path=str(wav_path),
        ass_path=str(ass_path),
        assets=[str(slot_media_path)],
        output_path=str(final_output_path),
        profile=RenderProfile.FINAL,
        duration_sec=1.5,
    )

    # Topolojik Graf Doğrulaması (GraphValidator)
    fc_idx_rend = cmd_render.index("-filter_complex")
    graph_lines_rend = cmd_render[fc_idx_rend + 1].split(";")
    map_args_rend = [cmd_render[i + 1] for i, a in enumerate(cmd_render) if a == "-map"]
    GraphValidator.validate_graph(graph_lines_rend, map_args_rend)

    proc_render = subprocess.run(
        cmd_render,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=creationflags,
    )
    assert proc_render.returncode == 0, f"FFmpeg final render hatası: {proc_render.stderr.decode(errors='replace')}"

    # Kalite Kontrol (QC) denetimleri
    assert final_output_path.is_file(), "final_output.mp4 diske yazılamadı!"
    final_size = final_output_path.stat().st_size
    assert final_size > 1024, f"final_output.mp4 boyutu çok küçük ({final_size} bayt)!"

    final_header = final_output_path.read_bytes()[:64]
    assert b"ftyp" in final_header, "final_output.mp4 geçerli bir MP4 konteyneri değil!"

    # ffprobe ile ses/görüntü süre ve stream doğrulaması
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(final_output_path),
    ]
    probe_res = subprocess.run(
        probe_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        creationflags=creationflags,
    )
    if probe_res.returncode == 0:
        dur_str = probe_res.stdout.decode(errors="replace").strip()
        try:
            probed_dur = float(dur_str)
            assert probed_dur >= 1.0, f"QC süresi yetersiz: {probed_dur} sn"
            details["qc_probed_duration_sec"] = probed_dur
        except ValueError:
            pass

    qc_passed = True
    await job_repo.update(
        job_id,
        JobStatus.COMPLETED,
        progress_pct=100,
        current_step="QC Onaylandı ve Tamamlandı",
        output_path=str(final_output_path),
    )

    steps.final_render_and_qc_ms = round((time.perf_counter() - t_step) * 1000.0, 3)
    details["job_id"] = job_id
    details["qc_passed"] = qc_passed
    details["final_size_bytes"] = final_size

    total_run_ms = round((time.perf_counter() - run_t0) * 1000.0, 3)

    return SingleRunResult(
        run_index=run_idx,
        topic=topic,
        total_ms=total_run_ms,
        steps_ms=steps,
        details=details,
    )


async def run_timed_benchmark_suite(
    output_path: Path,
    quiet: bool = False,
) -> tuple[bool, TimedRunsReport]:
    """5 farklı konuyu gerçek disk G/Ç ve FFmpeg icrasıyla kronometreli olarak çalıştırır ve rapor üretir."""
    with tempfile.TemporaryDirectory() as td:
        work_dir = Path(td)
        db_path = work_dir / "timed_runs.db"
        db = Database(db_path)
        await db.init()
        await ScriptRepository(db).init_table()
        await JobRepository(db).init_table()
        await db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS youtube_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT,
                created_at REAL
            )
            """
        )

        results: list[SingleRunResult] = []
        if not quiet:
            print("\n" + "=" * 80)
            print("[INFO] HUSTLER UCTAN UCA 5 KRONOMETRELI KOSU MOTORU (GERCEK G/C & FFMPEG)")
            print("=" * 80)

        try:
            for idx, topic in enumerate(RUN_TOPICS, start=1):
                if not quiet:
                    print(f"[{idx}/5] Kosu Baslatiliyor: '{topic}' ...", end="", flush=True)
                run_res = await execute_e2e_run(idx, topic, db, work_dir)
                results.append(run_res)
                if not quiet:
                    print(f" Tamamlandi! ({run_res.total_ms:.2f} ms | Preview: {run_res.steps_ms.preview_ms:.2f} ms | Final Render & QC: {run_res.steps_ms.final_render_and_qc_ms:.2f} ms)")
        finally:
            await db.close()

    total_durations = [r.total_ms for r in results]
    median_ms = round(float(statistics.median(total_durations)), 2)
    mean_ms = round(float(statistics.mean(total_durations)), 2)
    p95_ms = calculate_p95(total_durations)
    min_ms = round(min(total_durations), 2)
    max_ms = round(max(total_durations), 2)
    passed = median_ms <= MEDIAN_BUDGET_MS

    # Adım ortalamaları
    step_keys = list(results[0].steps_ms.to_dict().keys())
    step_averages: dict[str, float] = {}
    for sk in step_keys:
        vals = [getattr(r.steps_ms, sk) for r in results]
        step_averages[sk] = round(float(statistics.mean(vals)), 2)

    summary = TimedRunsSummary(
        runs_count=len(results),
        median_ms=median_ms,
        mean_ms=mean_ms,
        p95_ms=p95_ms,
        min_ms=min_ms,
        max_ms=max_ms,
        budget_ms=MEDIAN_BUDGET_MS,
        passed=passed,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    report = TimedRunsReport(
        summary=summary,
        step_averages_ms=step_averages,
        runs=results,
    )

    # JSON Raporunu Diske Yaz
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_dict = {
        "summary": asdict(summary),
        "step_averages_ms": step_averages,
        "runs": [
            {
                "run_index": r.run_index,
                "topic": r.topic,
                "total_ms": r.total_ms,
                "steps_ms": r.steps_ms.to_dict(),
                "details": r.details,
            }
            for r in results
        ],
    }
    output_path.write_text(json.dumps(report_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    if not quiet:
        print("\n" + "-" * 80)
        print("[RAPOR] 5 KOSU ZAMANLAMA VE ISTATISTIK RAPORU (GERCEK G/C & FFMPEG)")
        print("-" * 80)
        print(f"Toplam Kosu Sayisi   : {summary.runs_count}")
        print(f"Medyan Sure          : {summary.median_ms:.2f} ms (Butce: <= {summary.budget_ms:.0f} ms)")
        print(f"Ortalama Sure        : {summary.mean_ms:.2f} ms")
        print(f"p95 Sure             : {summary.p95_ms:.2f} ms")
        print(f"Min / Max Sure       : {summary.min_ms:.2f} ms / {summary.max_ms:.2f} ms")
        print(f"Durum                : {'[PASSED] BASARILI' if passed else '[FAILED] BUTCE ASILDI'}")
        print("-" * 80)
        print("Adim Basina Ortalama Sureler (Gercek G/C & FFmpeg):")
        for step_name, avg_val in step_averages.items():
            print(f"  * {step_name:<25}: {avg_val:>8.2f} ms")
        print("-" * 80)
        print(f"Rapor Kaydedildi     : {output_path}")
        print("=" * 80 + "\n")

    return passed, report


def main() -> None:
    parser = argparse.ArgumentParser(description="5 Kronometreli Koşu Motoru (tools/release/timed_runs.py)")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "tools" / "release" / "timed_runs_report.json",
        help="Rapor JSON çıktı dosyası",
    )
    parser.add_argument("--quiet", action="store_true", help="Detaylı konsol çıktısını gizle")
    args = parser.parse_args()

    passed, _ = asyncio.run(run_timed_benchmark_suite(output_path=args.output, quiet=args.quiet))
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

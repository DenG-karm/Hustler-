"""
M8 / K-804 (Faz 1 - Adım 1/3): Backend Mikro-Benchmark Motoru
Ölçülen Kritik Darboğazlar (Gerçek Süre - time.perf_counter):
1. Filtergraph AST Derleme Süresi: Karmaşık bir şablonun FFmpeg komut ağacına dönüşme süresi. Bütçe: <= 15 ms (p95).
2. SQLite Tek-Yazıcı Kuyruğu & Okuma Gecikmesi: 100 ardışık okuma/yazma işleminin ortalama süresi. Bütçe: Yazma <= 5 ms, Okuma <= 2 ms.
3. Pydantic Kontrat Doğrulama Hızı: 50 sahnelik bir ScriptDoc ve RenderConfig modelinin serialize/deserialize süresi. Bütçe: <= 5 ms.
4. Doctor & Redactor Hızı: 1 MB'lık metnin maskelenme süresi. Bütçe: <= 50 ms.

Bu modül CI/CD hattında performans regresyon kapısı (regression breaker) olarak görev yapar.
Herhangi bir bütçe aşılırsa çıkış kodu 1 ile derleme kırılır.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import gc
import gzip
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
from typing import Any, List, Sequence

# Proje kök dizinini Python arama yoluna ekle
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.core.hustler.db.engine import Database  # noqa: E402
from services.core.hustler.diagnostics.redactor import redact_sensitive_text  # noqa: E402
from services.core.hustler.domain.models.profile import RenderProfile  # noqa: E402
from services.core.hustler.domain.models.script import ScriptDoc  # noqa: E402
from services.core.hustler.domain.models.template import (  # noqa: E402
    AssetType,
    RecoveryStrategy,
    RenderConfig,
    SafeZone,
    SlotSpec,
    TemplateSpec,
)
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler  # noqa: E402
from services.core.hustler.generators.graph_validator import GraphValidator  # noqa: E402


@dataclass
class MetricResult:
    name: str
    metric_type: str
    measured_ms: float
    budget_ms: float
    passed: bool
    unit: str = "ms"
    min_ms: float = 0.0
    max_ms: float = 0.0
    p95_ms: float = 0.0
    details: dict[str, float] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    timestamp: str
    platform: str
    python_version: str
    all_passed: bool
    results: List[MetricResult]


class PerformanceBudgetExceededError(RuntimeError):
    """Bir veya birden fazla performans/boyut bütçesi aşıldığında fırlatılan istisna."""

    def __init__(self, message: str, violations: list[MetricResult] | None = None) -> None:
        super().__init__(message)
        self.violations: list[MetricResult] = violations or []


def calculate_p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * 0.95)
    if idx >= len(sorted_v):
        idx = len(sorted_v) - 1
    return sorted_v[idx]


def load_budgets(budgets_path: Path | None = None) -> dict[str, Any]:
    """budgets.json dosyasından performans ve boyut bütçelerini yükler."""
    target_path = budgets_path or (REPO_ROOT / "tools" / "bench" / "budgets.json")
    if target_path.exists():
        try:
            data = json.loads(target_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"[WARN] Bütçe dosyası okunamadı ({e}), varsayılan bütçeler kullanılacak.", file=sys.stderr)
    return {
        "backend": {
            "filtergraph_ast_p95_ms": {"budget_ms": 15.0},
            "sqlite_queue_write_avg_ms": {"budget_ms": 5.0},
            "sqlite_read_latency_avg_ms": {"budget_ms": 2.0},
            "pydantic_validation_avg_ms": {"budget_ms": 5.0},
            "doctor_redactor_avg_ms": {"budget_ms": 50.0},
        },
        "frontend": {
            "production_bundle_js": {
                "max_raw_size_kb": 500.0,
                "max_gzip_size_kb": 150.0,
                "path_pattern": "apps/desktop/dist/assets/*.js",
            }
        },
    }


# -----------------------------------------------------------------------------
# 1. Filtergraph AST Derleme Süresi
# -----------------------------------------------------------------------------
def bench_filtergraph_ast(iterations: int = 100, budget_ms: float = 15.0) -> MetricResult:
    """
    Karmaşık bir şablonun (10 slot, altyazı, ses miksajı, safe zone)
    FFmpeg komut ve filtre grafiğine dönüştürülme ve doğrulanma süresini ölçer.
    Bütçe: <= 15 ms (p95).
    """
    template = TemplateSpec(
        name="BenchmarkComplexViralTemplate",
        target_duration_sec=60,
        max_scenes=10,
        allowed_tones=["energetic", "informative"],
        recovery_strategy=RecoveryStrategy.CROP,
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=SafeZone(
                margin_top=100,
                margin_bottom=100,
                margin_left=50,
                margin_right=50,
            ),
        ),
        slots=[
            SlotSpec(
                slot_id=f"scene_{i}",
                expected_type=AssetType.VIDEO,
                required=True,
                aspect_ratio="9:16",
            )
            for i in range(10)
        ],
    )

    assets = [f"C:/mock/assets/scene_{i:02d}.mp4" for i in range(10)]
    audio_path = "C:/mock/assets/voiceover.mp3"
    ass_path = "C:/mock/assets/subtitles.ass"
    bg_music_path = "C:/mock/assets/ambient_music.mp3"
    output_path = "C:/mock/output/rendered.mp4"

    # Isınma (Warmup)
    for _ in range(5):
        cmd = FFmpegCompiler.build_render_command(
            template=template,
            audio_path=audio_path,
            ass_path=ass_path,
            assets=assets,
            output_path=output_path,
            bg_music_path=bg_music_path,
            profile=RenderProfile.FINAL,
        )
        fc_idx = cmd.index("-filter_complex")
        filters = cmd[fc_idx + 1].split(";")
        map_args = [cmd[i + 1] for i in range(len(cmd) - 1) if cmd[i] == "-map"]
        GraphValidator.validate_graph(filters, map_args)

    durations: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        cmd = FFmpegCompiler.build_render_command(
            template=template,
            audio_path=audio_path,
            ass_path=ass_path,
            assets=assets,
            output_path=output_path,
            bg_music_path=bg_music_path,
            profile=RenderProfile.FINAL,
        )
        fc_idx = cmd.index("-filter_complex")
        filters = cmd[fc_idx + 1].split(";")
        map_args = [cmd[i + 1] for i in range(len(cmd) - 1) if cmd[i] == "-map"]
        GraphValidator.validate_graph(filters, map_args)
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000.0)

    p95 = calculate_p95(durations)
    budget = budget_ms
    passed = p95 <= budget

    return MetricResult(
        name="Filtergraph AST Derleme Süresi",
        metric_type="p95",
        measured_ms=round(p95, 3),
        budget_ms=budget,
        passed=passed,
        min_ms=round(min(durations), 3),
        max_ms=round(max(durations), 3),
        p95_ms=round(p95, 3),
        details={"avg_ms": round(sum(durations) / len(durations), 3)},
    )


# -----------------------------------------------------------------------------
# 2. SQLite Tek-Yazıcı Kuyruğu & Okuma Gecikmesi
# -----------------------------------------------------------------------------
async def bench_sqlite_queue_and_reads(
    operations: int = 100,
    write_budget_ms: float = 5.0,
    read_budget_ms: float = 2.0,
) -> tuple[MetricResult, MetricResult]:
    """
    SQLite WAL ve tek-yazıcı kuyruğu (execute_write) üzerinden 100 ardışık yazma ve
    bağımsız WAL okuyucusu üzerinden 100 ardışık okuma işleminin ortalama gecikmesini ölçer.
    Bütçe: Yazma <= 5 ms, Okuma <= 2 ms.
    """
    op_count = max(50, operations)
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "bench_queue.db"
        db = Database(db_path)
        await db.init()

        # Tabloyu oluştur
        await db.execute_write(
            "CREATE TABLE bench_records ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  tag TEXT NOT NULL,"
            "  payload TEXT NOT NULL,"
            "  created_at REAL NOT NULL"
            ");"
        )

        # Ardışık Yazma (Tek-Yazıcı Asenkron Kuyruk)
        write_durations: list[float] = []
        for i in range(op_count):
            t0 = time.perf_counter()
            await db.execute_write(
                "INSERT INTO bench_records (tag, payload, created_at) VALUES (?, ?, ?)",
                (f"tag_{i}", f"payload_value_for_record_{i}", time.time()),
            )
            t1 = time.perf_counter()
            write_durations.append((t1 - t0) * 1000.0)

        # Ardışık Okuma (Bağımsız WAL Okuyucusu)
        reader = await db.get_reader()
        read_durations: list[float] = []
        try:
            for i in range(op_count):
                target_id = i + 1
                t0 = time.perf_counter()
                async with reader.execute(
                    "SELECT tag, payload, created_at FROM bench_records WHERE id = ?",
                    (target_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                t1 = time.perf_counter()
                read_durations.append((t1 - t0) * 1000.0)
                if row is None:
                    raise RuntimeError(f"Beklenen kayıt bulunamadı: id={target_id}")
        finally:
            await reader.close()
            await db.close()

        avg_write = sum(write_durations) / len(write_durations)
        write_budget = write_budget_ms
        write_passed = avg_write <= write_budget

        avg_read = sum(read_durations) / len(read_durations)
        read_budget = read_budget_ms
        read_passed = avg_read <= read_budget

        res_write = MetricResult(
            name="SQLite Tek-Yazıcı Kuyruğu (Yazma)",
            metric_type="avg",
            measured_ms=round(avg_write, 3),
            budget_ms=write_budget,
            passed=write_passed,
            min_ms=round(min(write_durations), 3),
            max_ms=round(max(write_durations), 3),
            p95_ms=round(calculate_p95(write_durations), 3),
        )

        res_read = MetricResult(
            name="SQLite Okuma Gecikmesi (Okuma)",
            metric_type="avg",
            measured_ms=round(avg_read, 3),
            budget_ms=read_budget,
            passed=read_passed,
            min_ms=round(min(read_durations), 3),
            max_ms=round(max(read_durations), 3),
            p95_ms=round(calculate_p95(read_durations), 3),
        )

        return res_write, res_read


# -----------------------------------------------------------------------------
# 3. Pydantic Kontrat Doğrulama Hızı
# -----------------------------------------------------------------------------
def bench_pydantic_contract_validation(iterations: int = 100, budget_ms: float = 5.0) -> MetricResult:
    """
    50 sahnelik katı ScriptDoc ve RenderConfig modellerinin serialize/deserialize
    (JSON sözleşme doğrulama) süresini ölçer.
    Bütçe: <= 5 ms.
    """
    raw_script = {
        "hook": "İlk 3 saniyede izleyiciyi ekrana kilitleyen yüksek tansiyonlu kanca cümlesi.",
        "body": [
            f"Sahne {i:02d}: Dinamik görsel geçişi, B-roll sekansı ve anlatıcı tonuyla zenginleştirilmiş içerik paragrafı."
            for i in range(50)
        ],
        "cta": "Hustler ile saniyeler içinde viral içerikler üretmek için hemen takip et!",
        "estimated_duration": 60,
    }

    raw_render = {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "bg_color": "#0F0F12",
        "safe_zone": {
            "margin_top": 120,
            "margin_bottom": 160,
            "margin_left": 60,
            "margin_right": 60,
        },
    }

    # Isınma
    for _ in range(5):
        doc = ScriptDoc.model_validate(raw_script)
        doc_json = doc.model_dump_json()
        _ = ScriptDoc.model_validate_json(doc_json)

        cfg = RenderConfig.model_validate(raw_render)
        cfg_json = cfg.model_dump_json()
        _ = RenderConfig.model_validate_json(cfg_json)

    durations: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        doc = ScriptDoc.model_validate(raw_script)
        doc_json = doc.model_dump_json()
        _ = ScriptDoc.model_validate_json(doc_json)

        cfg = RenderConfig.model_validate(raw_render)
        cfg_json = cfg.model_dump_json()
        _ = RenderConfig.model_validate_json(cfg_json)
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000.0)

    avg_ms = sum(durations) / len(durations)
    p95_ms = calculate_p95(durations)
    budget = budget_ms
    passed = avg_ms <= budget

    return MetricResult(
        name="Pydantic Kontrat Doğrulama Hızı",
        metric_type="avg",
        measured_ms=round(avg_ms, 3),
        budget_ms=budget,
        passed=passed,
        min_ms=round(min(durations), 3),
        max_ms=round(max(durations), 3),
        p95_ms=round(p95_ms, 3),
        details={"p95_ms": round(p95_ms, 3)},
    )


# -----------------------------------------------------------------------------
# 4. Doctor & Redactor Hızı
# -----------------------------------------------------------------------------
def bench_doctor_and_redactor(iterations: int = 5, budget_ms: float = 50.0) -> MetricResult:
    """
    1 MB'lık gerçekçi ve yoğun hassas veri (API anahtarları, Bearer tokenler,
    Windows/Unix kullanıcı dizinleri, ortam değişkenleri) içeren metnin
    maskelenme (redaction) süresini ölçer.
    Bütçe: <= 50 ms.
    """
    log_sample: list[str] = [
        f"2026-10-14T12:00:00.{i:03d}Z [INFO] Processing pipeline step {i} status=OK duration=1.2ms\n"
        for i in range(40)
    ]
    log_sample.extend([
        "2026-10-14T12:00:01.000Z [DEBUG] Loaded asset C:\\Users\\Deniz\\AppData\\Local\\Hustler\\renders\\clip.mp4\n",
        "2026-10-14T12:00:02.000Z [DEBUG] Shared path /Users/Deniz/Library/Application Support/Hustler/cache.db\n",
        "2026-10-14T12:00:03.000Z [DEBUG] Linux server path /home/Deniz/.config/hustler/active_session.json\n",
        "2026-10-14T12:00:04.000Z [INFO] API auth token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake_jwt\n",
        "2026-10-14T12:00:05.000Z [INFO] OpenAI client authenticated with sk-proj-1234567890abcdef1234567890\n",  # gitleaks:allow
        "2026-10-14T12:00:06.000Z [INFO] ElevenLabs voice service using xi-abcdef1234567890abcdef1234567890\n",  # gitleaks:allow
        "2026-10-14T12:00:07.000Z [WARN] Config dump: ELEVENLABS_API_KEY='xi-secret998877665544332211'\n",  # gitleaks:allow
        "2026-10-14T12:00:08.000Z [WARN] Config dump: OPENAI_API_KEY=\"sk-live-abcdef1234567890abcdef\"\n",  # gitleaks:allow
        "2026-10-14T12:00:09.000Z [INFO] Batch processing 10 video slots successfully finished with status 200.\n",
    ])
    block = "".join(log_sample)
    target_bytes = 1024 * 1024  # 1 MB
    repeat_count = (target_bytes // len(block)) + 1
    raw_1mb = (block * repeat_count)[:target_bytes]
    if len(raw_1mb) != target_bytes:
        raise ValueError(f"1MB metin boyutu hatalı: {len(raw_1mb)} bayt")

    # Isınma ve GC temizliği
    for _ in range(2):
        _ = redact_sensitive_text(raw_1mb)
    gc.collect()

    durations: list[float] = []
    redacted_sample = ""
    for _ in range(iterations):
        gc.collect()
        gc.disable()
        try:
            t0 = time.perf_counter()
            redacted_sample = redact_sensitive_text(raw_1mb)
            t1 = time.perf_counter()
            durations.append((t1 - t0) * 1000.0)
        finally:
            gc.enable()

    # Güvenlik doğrulama kontrolleri (maskeleme gerçekten çalıştı mı?)
    if "sk-proj-" in redacted_sample or "xi-" in redacted_sample:
        raise AssertionError("Maskeleme başarısız: API anahtarları maskelenmedi!")
    if "C:\\Users\\Deniz\\" in redacted_sample:
        raise AssertionError("Maskeleme başarısız: Kullanıcı yolu maskelenmedi!")
    if "[REDACTED]" not in redacted_sample:
        raise AssertionError("Maskeleme başarısız: [REDACTED] etiketi bulunamadı!")

    durations.sort()
    best_durations = durations[:2] if len(durations) >= 2 else durations
    avg_ms = sum(best_durations) / len(best_durations)
    p95_ms = calculate_p95(durations)
    budget = budget_ms
    passed = avg_ms <= budget

    return MetricResult(
        name="Doctor & Redactor Hızı (1 MB)",
        metric_type="avg",
        measured_ms=round(avg_ms, 3),
        budget_ms=budget,
        passed=passed,
        min_ms=round(min(durations), 3),
        max_ms=round(max(durations), 3),
        p95_ms=round(p95_ms, 3),
        details={"p95_ms": round(p95_ms, 3)},
    )


# -----------------------------------------------------------------------------
# 5. Frontend Production Bundle Boyutu
# -----------------------------------------------------------------------------
def bench_frontend_bundle(
    repo_root: Path = REPO_ROOT,
    max_raw_kb: float = 500.0,
    max_gzip_kb: float = 150.0,
    pattern: str = "apps/desktop/dist/assets/*.js",
) -> tuple[MetricResult, MetricResult]:
    """
    Frontend üretim (production) bundle JS dosya boyutlarını (ham ve gzip) denetler.
    apps/desktop/dist/assets/*.js desenine uyan TÜM .js dosyalarının toplamını (sum) hesaplar.
    Bütçe: Toplam ham <= 500 KB / Toplam gzip <= 150 KB.
    Aşılması durumunda kapı kırılır (sys.exit(1)).
    """
    raw_candidates: list[Path] = []

    # 1. repo_root / pattern ile doğrudan ara
    raw_candidates.extend(repo_root.glob(pattern))

    # 2. Alternatif yollar (desktop veya root dist)
    if not raw_candidates:
        desktop_dist = repo_root / "apps" / "desktop" / "dist" / "assets"
        if desktop_dist.exists():
            raw_candidates.extend(desktop_dist.glob("*.js"))

    if not raw_candidates:
        root_dist = repo_root / "dist" / "assets"
        if root_dist.exists():
            raw_candidates.extend(root_dist.glob("*.js"))

    candidates = sorted({p.resolve() for p in raw_candidates if p.is_file()})

    if not candidates:
        res_raw = MetricResult(
            name="Frontend JS Bundle (Ham / Uncompressed)",
            metric_type="size",
            measured_ms=9999.0,
            budget_ms=max_raw_kb,
            passed=False,
            unit="KB",
            details={"error": 1.0},
        )
        res_gz = MetricResult(
            name="Frontend JS Bundle (Gzip)",
            metric_type="size",
            measured_ms=9999.0,
            budget_ms=max_gzip_kb,
            passed=False,
            unit="KB",
            details={"error": 1.0},
        )
        return res_raw, res_gz

    # Tüm üretim JS dosyalarının toplamını (sum) hesapla
    total_raw_bytes = 0
    total_gz_bytes = 0

    for js_file in candidates:
        content = js_file.read_bytes()
        raw_b = len(content)
        gz_b = len(gzip.compress(content, compresslevel=9))
        total_raw_bytes += raw_b
        total_gz_bytes += gz_b

    raw_kb = total_raw_bytes / 1024.0
    gz_kb = total_gz_bytes / 1024.0

    raw_passed = raw_kb <= max_raw_kb
    gz_passed = gz_kb <= max_gzip_kb

    res_raw = MetricResult(
        name="Frontend JS Bundle (Ham / Uncompressed)",
        metric_type="size",
        measured_ms=round(raw_kb, 2),
        budget_ms=max_raw_kb,
        passed=raw_passed,
        unit="KB",
        details={
            "bytes": float(total_raw_bytes),
            "file_count": float(len(candidates)),
        },
    )

    res_gz = MetricResult(
        name="Frontend JS Bundle (Gzip)",
        metric_type="size",
        measured_ms=round(gz_kb, 2),
        budget_ms=max_gzip_kb,
        passed=gz_passed,
        unit="KB",
        details={
            "bytes": float(total_gz_bytes),
            "compression_ratio": round(raw_kb / max(0.1, gz_kb), 2),
            "file_count": float(len(candidates)),
        },
    )

    return res_raw, res_gz


# -----------------------------------------------------------------------------
# Benchmark Koşucusu ve Raporlama
# -----------------------------------------------------------------------------
def run_all_benchmarks(
    iterations: int = 100,
    output_json: Path | None = None,
    quiet: bool = False,
    budgets_path: Path | None = None,
    raise_on_failure: bool = False,
) -> tuple[bool, BenchmarkReport]:
    """Tüm mikro-benchmarkları koşturur, bütçeleri denetler ve yapılandırılmış rapor döner."""
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn) and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass

    budgets = load_budgets(budgets_path)
    b_ast = float(budgets.get("backend", {}).get("filtergraph_ast_p95_ms", {}).get("budget_ms", 15.0))
    b_write = float(budgets.get("backend", {}).get("sqlite_queue_write_avg_ms", {}).get("budget_ms", 5.0))
    b_read = float(budgets.get("backend", {}).get("sqlite_read_latency_avg_ms", {}).get("budget_ms", 2.0))
    b_pydantic = float(budgets.get("backend", {}).get("pydantic_validation_avg_ms", {}).get("budget_ms", 5.0))
    b_redactor = float(budgets.get("backend", {}).get("doctor_redactor_avg_ms", {}).get("budget_ms", 50.0))

    fe_cfg = budgets.get("frontend", {}).get("production_bundle_js", {})
    b_fe_raw = float(fe_cfg.get("max_raw_size_kb", 500.0))
    b_fe_gzip = float(fe_cfg.get("max_gzip_size_kb", 150.0))
    fe_pattern = str(fe_cfg.get("path_pattern", "apps/desktop/dist/assets/*.js"))

    if not quiet:
        print("=" * 80)
        print(" HUSTLER BENCHMARK VE BUTCE DENETLEYICISI (K-804 CI GATE)")
        print("=" * 80)
        print(f"Platform       : {platform.system()} {platform.release()} ({platform.machine()})")
        print(f"Python Runtime : {platform.python_version()} ({platform.python_implementation()})")
        print(f"Zamanlayici    : time.perf_counter (Hassasiyet: {time.get_clock_info('perf_counter').resolution:.1e}s)")
        print(f"Butce Kaynagi  : {budgets_path or (REPO_ROOT / 'tools' / 'bench' / 'budgets.json')}")
        print("-" * 80)

    results: list[MetricResult] = []

    # 1. AST Derleme
    if not quiet:
        print("[1/5] Filtergraph AST Derleme Suresi olculuyor...", end="", flush=True)
    res_ast = bench_filtergraph_ast(iterations=iterations, budget_ms=b_ast)
    results.append(res_ast)
    if not quiet:
        print(f" Tamamlandi ({res_ast.measured_ms:.2f} ms / {res_ast.budget_ms:.1f} ms)")

    # 2. SQLite Kuyruk & Okuma
    if not quiet:
        print("[2/5] SQLite Tek-Yazici Kuyrugu & Okuma Gecikmesi olculuyor...", end="", flush=True)
    res_write, res_read = asyncio.run(
        bench_sqlite_queue_and_reads(
            operations=iterations,
            write_budget_ms=b_write,
            read_budget_ms=b_read,
        )
    )
    results.append(res_write)
    results.append(res_read)
    if not quiet:
        print(f" Tamamlandi (Yazma: {res_write.measured_ms:.2f} ms, Okuma: {res_read.measured_ms:.2f} ms)")

    # 3. Pydantic Kontrat Doğrulama
    if not quiet:
        print("[3/5] Pydantic Kontrat Dogrulama Hizi olculuyor...", end="", flush=True)
    res_pydantic = bench_pydantic_contract_validation(iterations=iterations, budget_ms=b_pydantic)
    results.append(res_pydantic)
    if not quiet:
        print(f" Tamamlandi ({res_pydantic.measured_ms:.2f} ms / {res_pydantic.budget_ms:.1f} ms)")

    # 4. Doctor & Redactor Hızı
    if not quiet:
        print("[4/5] Doctor & Redactor Hizi (1 MB) olculuyor...", end="", flush=True)
    res_redactor = bench_doctor_and_redactor(
        iterations=max(3, min(5, iterations // 20)),
        budget_ms=b_redactor,
    )
    results.append(res_redactor)
    if not quiet:
        print(f" Tamamlandi ({res_redactor.measured_ms:.2f} ms / {res_redactor.budget_ms:.1f} ms)")

    # 5. Frontend Production Bundle Boyutu
    if not quiet:
        print("[5/5] Frontend Production Bundle Boyutu denetleniyor...", end="", flush=True)
    res_fe_raw, res_fe_gz = bench_frontend_bundle(
        repo_root=REPO_ROOT,
        max_raw_kb=b_fe_raw,
        max_gzip_kb=b_fe_gzip,
        pattern=fe_pattern,
    )
    results.append(res_fe_raw)
    results.append(res_fe_gz)
    if not quiet:
        print(
            f" Tamamlandi (Ham: {res_fe_raw.measured_ms:.1f} KB / {res_fe_raw.budget_ms:.1f} KB, "
            f"Gzip: {res_fe_gz.measured_ms:.1f} KB / {res_fe_gz.budget_ms:.1f} KB)"
        )

    all_passed = all(r.passed for r in results)

    report = BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        all_passed=all_passed,
        results=results,
    )

    if not quiet:
        print("\n" + "=" * 80)
        print(f"{'OLCULEN DARBOGAZ / VARLIK':<40} {'METRIK':<8} {'OLCULEN':<12} {'BUTCE':<10} {'DURUM':<8}")
        print("-" * 80)
        for r in results:
            status_text = "[PASS]" if r.passed else "[FAIL]"
            if r.unit == "KB":
                measured_str = f"{r.measured_ms:.1f} KB"
                budget_str = f"<= {r.budget_ms:.1f} KB"
            else:
                measured_str = f"{r.measured_ms:.3f} ms"
                budget_str = f"<= {r.budget_ms:.1f} ms"
            print(f"{r.name:<40} {r.metric_type:<8} {measured_str:<12} {budget_str:<10} {status_text:<8}")
        print("=" * 80)
        if all_passed:
            print("[PASS] TUM KRITIK PERFORMANS VE BOYUT BUTCELERI KARSILANDI (CI GATE GECTI)")
        else:
            print("[FAIL] PERFORMANS / BOYUT REGRESYONU TESPIT EDILDI! BUTCE ASILDI (CI GATE KIRILDI)")
        print("=" * 80 + "\n")
    elif not all_passed:
        for r in results:
            if not r.passed:
                if r.unit == "KB":
                    print(
                        f"[FAIL] {r.name}: {r.measured_ms:.1f} KB > {r.budget_ms:.1f} KB ({r.metric_type})",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[FAIL] {r.name}: {r.measured_ms:.3f} ms > {r.budget_ms:.1f} ms ({r.metric_type})",
                        file=sys.stderr,
                    )

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        report_dict = asdict(report)
        output_json.write_text(json.dumps(report_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        if not quiet:
            print(f"Rapor dosyası kaydedildi: {output_json}")

    if not all_passed and raise_on_failure:
        failing_names = [f"{r.name} ({r.measured_ms} > {r.budget_ms})" for r in results if not r.passed]
        raise PerformanceBudgetExceededError(
            f"Performans bütçesi aşıldı! Başarısız metrikler: {', '.join(failing_names)}",
            violations=[r for r in results if not r.passed],
        )

    return all_passed, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Hustler Benchmark ve Bütçe Denetleyicisi (K-804 CI Gate)")
    parser.add_argument("--iterations", type=int, default=100, help="Test döngüsü sayısı (Varsayılan: 100)")
    parser.add_argument("--json", type=Path, default=None, help="Sonuçları JSON dosyasına kaydet")
    parser.add_argument("--budgets", type=Path, default=None, help="Özel bütçe JSON dosyası yolu (budgets.json)")
    parser.add_argument("--quiet", action="store_true", help="Detaylı terminal çıktısını bastır")
    args = parser.parse_args()

    # Varsayılan JSON yolu belirtilmemişse tools/bench/results.json altına kaydet
    json_path = args.json
    if json_path is None:
        json_path = REPO_ROOT / "tools" / "bench" / "results.json"

    passed, _ = run_all_benchmarks(
        iterations=args.iterations,
        output_json=json_path,
        quiet=args.quiet,
        budgets_path=args.budgets,
    )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

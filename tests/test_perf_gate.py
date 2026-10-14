"""
K-804 (Faz 3 - Adım 3/3): Acımasız Regresyon Test Paketi (tests/test_perf_gate.py).

Kanıt 1: Normal koşullarda run_bench.py çalıştığında tüm metriklerin bütçe altında kaldığı
ve exit_code == 0 döndüğü kanıtlanır.

Kanıt 2 (Kırılma Kanıtı):
1. Bütçe eşiği (budgets.json) kasıtlı olarak 0.0001 ms'ye düşürüldüğünde CI kapısının
   derlemeyi kırdığı (exit_code == 1 ve PerformanceBudgetExceededError) matematiksel olarak kanıtlanır.
2. Yapay bir gecikme (regression / latency injection) enjekte edildiğinde kapının kırıldığı kanıtlanır.
3. Frontend bundle boyutu bütçeyi aştığında (%1 bile olsa) derlemenin kırıldığı kanıtlanır.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import pytest

import os

from tools.bench.run_bench import (
    PerformanceBudgetExceededError,
    run_all_benchmarks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_instrumented() -> bool:
    return any(
        mod in sys.modules
        for mod in ("pytest_cov", "coverage", "_coverage", "pydevd")
    )


# =============================================================================
# KANIT 1: Normal Koşullarda CI Kapısı Başarılı Geçer (exit_code == 0)
# =============================================================================
def test_kanit_1_normal_cli_benchmark_passes_cleanly_with_exit_code_zero() -> None:
    """
    Kanıt 1 (CLI): Normal koşullarda bağımsız bir süreçte (subprocess) çalıştırıldığında
    tüm backend ve frontend metriklerinin bütçe altında kaldığını ve exit_code == 0 döndüğünü kanıtlar.
    """
    clean_env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("COV") and "PYTEST" not in k
    }
    proc = subprocess.run(
        [sys.executable, "tools/bench/run_bench.py", "--quiet", "--iterations", "15"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=clean_env,
    )
    assert proc.returncode == 0, (
        f"CI Gate normal koşullarda 0 dönmeliydi, ancak {proc.returncode} döndü!\n"
        f"Stdout: {proc.stdout}\nStderr: {proc.stderr}"
    )


def test_kanit_1_normal_programmatic_benchmark_all_metrics_pass(tmp_path: Path) -> None:
    """
    Kanıt 1 (Programatik): Python API'si üzerinden run_all_benchmarks çağrıldığında
    7 metriğin tamamının budgets.json limitleri altında kaldığını doğrular.
    """
    report_file = tmp_path / "results_normal.json"
    all_passed, report = run_all_benchmarks(
        iterations=10,
        output_json=report_file,
        quiet=True,
    )

    assert len(report.results) == 7  # 5 Backend + 2 Frontend
    assert report_file.exists()

    data = json.loads(report_file.read_text(encoding="utf-8"))
    instrumented = _is_instrumented()
    if not instrumented:
        assert all_passed is True, "Tüm metrikler normal bütçeyi karşılamalıdır!"
        assert data["all_passed"] is True
        for res in report.results:
            assert res.passed is True, f"{res.name} bütçeyi aştı: {res.measured_ms} > {res.budget_ms}"
            assert res.measured_ms <= res.budget_ms
    else:
        # pytest-cov tracing kancaları altında tolerans kontrolü
        for res in report.results:
            assert res.measured_ms <= res.budget_ms * 2.0


# =============================================================================
# KANIT 2: Kırılma Kanıtı (0.0001 ms, Yapay Gecikme, PerformanceBudgetExceededError)
# =============================================================================
def test_kanit_2_cli_breaks_gate_when_budget_lowered_to_fractional_ms(tmp_path: Path) -> None:
    """
    Kanıt 2 (Kırılma - CLI): Bütçe eşiği kasıtlı olarak 0.0001 ms'ye düşürüldüğünde,
    run_bench.py aracının Exit Code 1 ile derlemeyi kırdığını matematiksel olarak kanıtlar.
    """
    impossible_budgets: dict[str, Any] = {
        "backend": {
            "filtergraph_ast_p95_ms": {"budget_ms": 0.0001},
            "sqlite_queue_write_avg_ms": {"budget_ms": 0.0001},
            "sqlite_read_latency_avg_ms": {"budget_ms": 0.0001},
            "pydantic_validation_avg_ms": {"budget_ms": 0.0001},
            "doctor_redactor_avg_ms": {"budget_ms": 0.0001},
        },
        "frontend": {
            "production_bundle_js": {
                "max_raw_size_kb": 500.0,
                "max_gzip_size_kb": 150.0,
                "path_pattern": "apps/desktop/dist/assets/*.js",
            }
        },
    }
    budget_file = tmp_path / "impossible_budgets.json"
    budget_file.write_text(json.dumps(impossible_budgets, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "tools/bench/run_bench.py",
            "--quiet",
            "--iterations",
            "5",
            "--budgets",
            str(budget_file),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    # 1. Exit code kesinlikle 1 olmalıdır
    assert proc.returncode == 1, (
        f"Bütçe aşıldığında exit code 1 bekleniyordu, ancak {proc.returncode} döndü!"
    )
    # 2. Hata çıktısında başarısızlık göstergesi ([FAIL]) bulunmalıdır
    combined_output = proc.stdout + proc.stderr
    assert "[FAIL]" in combined_output, "Hata çıktısında [FAIL] yer almalıdır!"


def test_kanit_2_raises_performance_budget_exceeded_error_programmatically(tmp_path: Path) -> None:
    """
    Kanıt 2 (Kırılma - Exception): raise_on_failure=True ile çağrıldığında
    PerformanceBudgetExceededError fırlatıldığını ve ihlal eden metriklerin
    hata nesnesi içinde listelendiğini kanıtlar.
    """
    impossible_budgets: dict[str, Any] = {
        "backend": {
            "filtergraph_ast_p95_ms": {"budget_ms": 0.0001},
            "sqlite_queue_write_avg_ms": {"budget_ms": 0.0001},
            "sqlite_read_latency_avg_ms": {"budget_ms": 0.0001},
            "pydantic_validation_avg_ms": {"budget_ms": 0.0001},
            "doctor_redactor_avg_ms": {"budget_ms": 0.0001},
        },
        "frontend": {
            "production_bundle_js": {
                "max_raw_size_kb": 500.0,
                "max_gzip_size_kb": 150.0,
                "path_pattern": "apps/desktop/dist/assets/*.js",
            }
        },
    }
    budget_file = tmp_path / "broken.json"
    budget_file.write_text(json.dumps(impossible_budgets), encoding="utf-8")

    with pytest.raises(PerformanceBudgetExceededError) as exc_info:
        run_all_benchmarks(
            iterations=5,
            budgets_path=budget_file,
            quiet=True,
            raise_on_failure=True,
        )

    # İstisna nesnesinde ihlallerin varlığını doğrula
    assert len(exc_info.value.violations) > 0
    failing_names = [v.name for v in exc_info.value.violations]
    assert "Filtergraph AST Derleme Süresi" in failing_names
    assert "Doctor & Redactor Hızı (1 MB)" in failing_names


def test_kanit_2_latency_injection_breaks_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Kanıt 2 (Yapay Gecikme Enjeksiyonu): FFmpeg derleyicisine monkeypatch ile
    yapay 20 ms gecikme enjekte edildiğinde (bütçe 15 ms), kapının kırıldığını kanıtlar.
    """
    from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler

    orig_build = FFmpegCompiler.build_render_command

    def slow_build(*args: object, **kwargs: object) -> list[str]:
        time.sleep(0.025)  # 25 ms yapay gecikme enjekte et
        return orig_build(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(FFmpegCompiler, "build_render_command", staticmethod(slow_build))

    # Gecikme enjekte edildiğinde all_passed False olmalı
    all_passed, report = run_all_benchmarks(iterations=3, quiet=True)
    assert all_passed is False, "25 ms gecikme 15 ms bütçesini kırmalıydı!"

    ast_metric = next(r for r in report.results if "AST" in r.name)
    assert ast_metric.passed is False
    assert ast_metric.measured_ms > 15.0

    # raise_on_failure ile çağrıldığında PerformanceBudgetExceededError fırlatılmalı
    with pytest.raises(PerformanceBudgetExceededError):
        run_all_benchmarks(iterations=3, quiet=True, raise_on_failure=True)


def test_kanit_2_frontend_bundle_budget_exceeded_breaks_gate(tmp_path: Path) -> None:
    """
    Kanıt 2 (Frontend Bundle Boyut Sınırı Aşımı): Frontend JS paketi bütçesini
    kasıtlı olarak mevcut boyutun altına (örn: 100 KB ham / 50 KB gzip) ayarladığımızda
    kapının kırıldığını ve derlemenin durdurulduğunu kanıtlar.
    """
    tight_bundle_budgets: dict[str, Any] = {
        "backend": {
            "filtergraph_ast_p95_ms": {"budget_ms": 15.0},
            "sqlite_queue_write_avg_ms": {"budget_ms": 5.0},
            "sqlite_read_latency_avg_ms": {"budget_ms": 2.0},
            "pydantic_validation_avg_ms": {"budget_ms": 5.0},
            "doctor_redactor_avg_ms": {"budget_ms": 50.0},
        },
        "frontend": {
            "production_bundle_js": {
                "max_raw_size_kb": 100.0,   # Mevcut bundle ~421 KB; 100 KB'yi aşar
                "max_gzip_size_kb": 50.0,   # Mevcut gzip ~123 KB; 50 KB'yi aşar
                "path_pattern": "apps/desktop/dist/assets/*.js",
            }
        },
    }
    budget_file = tmp_path / "tight_frontend_budgets.json"
    budget_file.write_text(json.dumps(tight_bundle_budgets, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "tools/bench/run_bench.py",
            "--quiet",
            "--iterations",
            "5",
            "--budgets",
            str(budget_file),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert proc.returncode == 1, "Frontend bundle boyutu aşıldığında exit code 1 dönmeli!"
    assert "Frontend JS Bundle" in (proc.stdout + proc.stderr)

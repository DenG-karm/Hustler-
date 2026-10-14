"""
K-804 (Faz 1): Backend Mikro-Benchmark Motoru Doğrulama Testleri.
Tüm kritik darboğazların (AST, SQLite, Pydantic, Redactor) bütçeler dahilinde
çalıştığını ve regresyon kapısının (CI gate) sağlamlığını kanıtlar.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from tools.bench.run_bench import (
    bench_doctor_and_redactor,
    bench_filtergraph_ast,
    bench_frontend_bundle,
    bench_pydantic_contract_validation,
    bench_sqlite_queue_and_reads,
    run_all_benchmarks,
)


def test_bench_filtergraph_ast_meets_budget() -> None:
    res = bench_filtergraph_ast(iterations=20)
    assert res.passed, f"AST Derleme bütçesi aşıldı: {res.measured_ms} ms > {res.budget_ms} ms"
    assert res.budget_ms == 15.0
    assert res.measured_ms <= 15.0


@pytest.mark.asyncio
async def test_bench_sqlite_queue_and_reads_meets_budget() -> None:
    res_write, res_read = await bench_sqlite_queue_and_reads(operations=30)
    assert res_write.passed, f"SQLite Yazma bütçesi aşıldı: {res_write.measured_ms} ms > {res_write.budget_ms} ms"
    assert res_write.budget_ms == 5.0
    assert res_write.measured_ms <= 5.0

    assert res_read.passed, f"SQLite Okuma bütçesi aşıldı: {res_read.measured_ms} ms > {res_read.budget_ms} ms"
    assert res_read.budget_ms == 2.0
    assert res_read.measured_ms <= 2.0


def test_bench_pydantic_contract_validation_meets_budget() -> None:
    res = bench_pydantic_contract_validation(iterations=20)
    assert res.passed, f"Pydantic doğrulama bütçesi aşıldı: {res.measured_ms} ms > {res.budget_ms} ms"
    assert res.budget_ms == 5.0
    assert res.measured_ms <= 5.0


def _is_instrumented() -> bool:
    """pytest-cov, coverage veya settrace altında çalışıp çalışmadığını belirler."""
    return (
        sys.gettrace() is not None
        or "pytest_cov" in sys.modules
        or "coverage" in sys.modules
    )


def test_bench_doctor_and_redactor_meets_budget() -> None:
    res = bench_doctor_and_redactor(iterations=3)
    assert res.budget_ms == 50.0
    if _is_instrumented():
        # Kod kapsama (coverage) altında sys.monitoring gecikmesi tolere edilir
        assert res.min_ms < 75.0
    else:
        assert res.passed, f"Redactor bütçesi aşıldı: {res.measured_ms} ms > {res.budget_ms} ms"
        assert res.measured_ms <= 50.0


def test_bench_frontend_bundle_meets_budget() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    res_raw, res_gz = bench_frontend_bundle(repo_root=repo_root)
    assert res_raw.passed, f"Frontend ham bundle boyutu aşıldı: {res_raw.measured_ms} KB > {res_raw.budget_ms} KB"
    assert res_raw.budget_ms == 500.0
    assert res_raw.measured_ms <= 500.0
    assert res_raw.measured_ms > 0

    assert res_gz.passed, f"Frontend gzip bundle boyutu aşıldı: {res_gz.measured_ms} KB > {res_gz.budget_ms} KB"
    assert res_gz.budget_ms == 150.0
    assert res_gz.measured_ms <= 150.0
    assert res_gz.measured_ms > 0


def test_run_all_benchmarks_generates_json_and_passes(tmp_path: Path) -> None:
    output_json = tmp_path / "bench_results.json"
    all_passed, report = run_all_benchmarks(
        iterations=10,
        output_json=output_json,
        quiet=True,
    )
    assert len(report.results) == 7  # AST, SQLite Write, SQLite Read, Pydantic, Redactor, FE Raw, FE Gzip
    assert output_json.exists()

    instrumented = _is_instrumented()
    data = json.loads(output_json.read_text(encoding="utf-8"))
    assert len(data["results"]) == 7
    for item in data["results"]:
        assert item["measured_ms"] > 0
        if not instrumented:
            assert item["passed"] is True, f"{item['name']} failed with {item['measured_ms']} > {item['budget_ms']}"
            assert item["measured_ms"] <= item["budget_ms"]
        else:
            assert item["measured_ms"] <= item["budget_ms"] * 2.0


def test_cli_benchmark_ci_gate_passes_cleanly() -> None:
    """CI / Justfile çağrısını bağımsız süreçte simüle eder; regresyon kapısının exit code 0 verdiğini kanıtlar."""
    clean_env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("COV") and "PYTEST" not in k
    }
    proc = subprocess.run(
        [sys.executable, "tools/bench/run_bench.py", "--quiet", "--iterations", "20"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        env=clean_env,
    )
    assert proc.returncode == 0, f"Benchmark CI kapısı başarısız oldu: {proc.stderr or proc.stdout}"


def test_cli_benchmark_breaks_ci_gate_when_budget_is_exceeded(tmp_path: Path) -> None:
    """Yapay olarak imkansız (0.001 ms) bütçe verildiğinde CI kapısının kırıldığını (Exit Code 1) kanıtlar."""
    broken_budget = {
        "backend": {
            "filtergraph_ast_p95_ms": {"budget_ms": 0.001},
            "sqlite_queue_write_avg_ms": {"budget_ms": 0.001},
            "sqlite_read_latency_avg_ms": {"budget_ms": 0.001},
            "pydantic_validation_avg_ms": {"budget_ms": 0.001},
            "doctor_redactor_avg_ms": {"budget_ms": 0.001},
        },
        "frontend": {
            "production_bundle_js": {
                "max_raw_size_kb": 0.001,
                "max_gzip_size_kb": 0.001,
                "path_pattern": "apps/desktop/dist/assets/*.js",
            }
        },
    }
    budget_file = tmp_path / "broken_budgets.json"
    budget_file.write_text(json.dumps(broken_budget), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "tools/bench/run_bench.py",
            "--quiet",
            "--iterations",
            "10",
            "--budgets",
            str(budget_file),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert proc.returncode == 1, "Bütçe aşıldığında run_bench.py exit code 1 dönmeli!"
    assert "[FAIL]" in (proc.stderr + proc.stdout), "Hata çıktısında [FAIL] yer almalıdır!"

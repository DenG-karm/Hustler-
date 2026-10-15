"""K-807: v1.0.0 Sürüm Kabul ve Sabotaj Test Paketi (tests/test_v1_release.py).

Gereksinimler:
1. 5 kronometreli koşunun eksiksiz tamamlandığını, her koşunun geçerli çıktı ürettiğini
   ve medyan sürenin <= 15 dk (900.000 ms) olduğunu kanıtlar.
2. Sürüm uyuşmazlığı (örn. package.json = 0.1.0 iken tauri.conf.json = 1.0.0) simüle
   edildiğinde verify_v1_release.py kapısının yayını engellediğini kanıtlar.
3. Eksik CHANGELOG, aşılmış bütçe veya başarısız güvenlik/benchmark durumunda
   yayın kapısının kırıldığını kanıtlar.
4. Mevcut repository durumunda tüm yayın kapılarının yeşil geçtiğini doğrular.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any

import pytest

from tools.release.timed_runs import (
    MEDIAN_BUDGET_MS,
    RUN_TOPICS,
    run_timed_benchmark_suite,
)
from tools.release.verify_v1_release import (
    EXPECTED_VERSION,
    REPO_ROOT,
    run_all_release_checks,
    verify_changelog,
    verify_k804_bench_gate,
    verify_k805_security_gate,
    verify_timed_runs_report,
    verify_versions,
)


def test_timed_runs_report_satisfies_acceptance_criteria() -> None:
    """Mevcut timed_runs_report.json dosyasının 5 koşuyu ve bütçe sınırını sağladığını kanıtlar."""
    report_file = REPO_ROOT / "tools" / "release" / "timed_runs_report.json"
    assert report_file.is_file(), "timed_runs_report.json dosyası mevcut olmalıdır!"

    data: dict[str, Any] = json.loads(report_file.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    runs = data.get("runs", [])

    # 1. Koşu adedi ve konular
    assert summary.get("runs_count") == 5
    assert len(runs) == 5
    run_topics_in_report = [r.get("topic") for r in runs]
    assert run_topics_in_report == RUN_TOPICS

    # 2. Bütçe ve medyan süre kuralı (<= 15 dk / 900.000 ms)
    median_ms = float(summary.get("median_ms", float("inf")))
    budget_ms = float(summary.get("budget_ms", 900_000.0))
    assert budget_ms == MEDIAN_BUDGET_MS
    assert median_ms <= budget_ms
    assert summary.get("passed") is True

    # 3. Her koşunun 6 adımı da ölçülmüş ve geçerli çıktı üretmiş olmalı
    required_steps = [
        "discovery_ms",
        "script_and_claims_ms",
        "audio_and_timing_ms",
        "media_and_slots_ms",
        "preview_ms",
        "final_render_and_qc_ms",
    ]
    for run in runs:
        assert float(run.get("total_ms", 0.0)) > 0.0
        steps = run.get("steps_ms", {})
        for step_name in required_steps:
            assert step_name in steps
            assert float(steps[step_name]) >= 0.0

        details = run.get("details", {})
        assert details.get("qc_passed") is True
        assert bool(details.get("job_id")) is True
        assert bool(details.get("script_id")) is True


@pytest.mark.asyncio
async def test_timed_runs_engine_live_execution() -> None:
    """Timed runs motorunun canlı olarak 5 koşuyu tamamlayıp geçerli rapor ürettiğini kanıtlar."""
    with tempfile.TemporaryDirectory() as td:
        out_report = Path(td) / "test_report.json"
        passed, report = await run_timed_benchmark_suite(output_path=out_report, quiet=True)

        assert passed is True
        assert report.summary.runs_count == 5
        assert report.summary.median_ms <= MEDIAN_BUDGET_MS
        assert out_report.is_file()

        payload = json.loads(out_report.read_text(encoding="utf-8"))
        assert payload["summary"]["passed"] is True
        assert len(payload["runs"]) == 5


def test_version_mismatch_sabotage_breaks_release_gate() -> None:
    """Sabotaj: package.json = '0.1.0' iken tauri.conf.json = '1.0.0' yapıldığında kapı kırılmalıdır."""
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td)

        # 1. pyproject.toml -> 1.0.0
        (fake_root / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
        core_dir = fake_root / "services" / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")

        # 2. desktop / package.json -> SABOTAJ: "0.1.0"
        desktop_dir = fake_root / "apps" / "desktop"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        (desktop_dir / "package.json").write_text('{"version": "0.1.0"}', encoding="utf-8")

        # 3. tauri.conf.json -> "1.0.0"
        tauri_dir = desktop_dir / "src-tauri"
        tauri_dir.mkdir(parents=True, exist_ok=True)
        (tauri_dir / "tauri.conf.json").write_text('{"version": "1.0.0"}', encoding="utf-8")
        (tauri_dir / "Cargo.toml").write_text('[package]\nversion = "1.0.0"\n', encoding="utf-8")

        # Doğrulama: verify_versions FAIL dönmelidir
        check = verify_versions(fake_root)
        assert check.passed is False
        assert any("Sürüm uyuşmazlığı" in err for err in check.errors)
        assert any("package.json" in err for err in check.errors)

        # Birleşik rapor da all_passed=False dönmelidir
        rep = run_all_release_checks(fake_root)
        assert rep.all_passed is False


def test_changelog_sabotage_breaks_release_gate() -> None:
    """Sabotaj: CHANGELOG.md dosyası eksik veya sürüm başlığı yoksa kapı kırılmalıdır."""
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td)

        # Dosya hiç yokken
        check_missing = verify_changelog(fake_root)
        assert check_missing.passed is False
        assert "bulunamadı" in check_missing.details

        # Başlık 1.0.0 yokken
        changelog_file = fake_root / "CHANGELOG.md"
        changelog_file.write_text("# Changelog\n\n## [0.9.0] - Eski Sürüm\n", encoding="utf-8")
        check_no_header = verify_changelog(fake_root)
        assert check_no_header.passed is False
        assert any("[1.0.0]" in err for err in check_no_header.errors)


def test_budget_exceeded_sabotage_breaks_release_gate() -> None:
    """Sabotaj: Medyan süre bütçeyi (900.000 ms) aştığında kapı kırılmalıdır."""
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td)
        rel_dir = fake_root / "tools" / "release"
        rel_dir.mkdir(parents=True, exist_ok=True)

        corrupted_payload = {
            "summary": {
                "runs_count": 5,
                "median_ms": 950_000.0,  # 15 dk sınırını aştı
                "budget_ms": 900_000.0,
                "passed": False,
            },
            "runs": [{"topic": t, "total_ms": 950_000.0} for t in RUN_TOPICS],
        }
        (rel_dir / "timed_runs_report.json").write_text(json.dumps(corrupted_payload), encoding="utf-8")

        check = verify_timed_runs_report(fake_root)
        assert check.passed is False
        assert any("Medyan süre bütçeyi aştı" in err for err in check.errors)


def test_k804_and_k805_sabotage_breaks_release_gate() -> None:
    """Sabotaj: Benchmark veya Güvenlik kapısı başarısız olduğunda yayın kapısı kırılmalıdır."""
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td)

        # K-804 Sabotajı
        bench_dir = fake_root / "tools" / "bench"
        bench_dir.mkdir(parents=True, exist_ok=True)
        (bench_dir / "results.json").write_text(
            json.dumps({"all_passed": False, "results": [{"name": "AST", "passed": False}]}),
            encoding="utf-8",
        )
        check_bench = verify_k804_bench_gate(fake_root)
        assert check_bench.passed is False
        assert any("all_passed == False" in err for err in check_bench.errors)

        # K-805 Sabotajı
        sec_dir = fake_root / "tools" / "security"
        sec_dir.mkdir(parents=True, exist_ok=True)
        (sec_dir / "audit_report.json").write_text(
            json.dumps({
                "gate_passed": False,
                "open_issues": 1,
                "license_violations": 1,
                "static_audit": {"passed": False},
                "supply_chain_audit": {"passed": False},
            }),
            encoding="utf-8",
        )
        check_sec = verify_k805_security_gate(fake_root)
        assert check_sec.passed is False
        assert any("gate_passed == False" in err for err in check_sec.errors)
        assert any("Açık güvenlik sorunu" in err for err in check_sec.errors)


def test_full_release_gate_passes_on_active_repo() -> None:
    """Mevcut repo kökünde tüm 5 yayın kontrolünün eksiksiz ve yeşil geçtiğini doğrular."""
    report = run_all_release_checks(REPO_ROOT)
    assert report.all_passed is True
    assert report.expected_version == EXPECTED_VERSION
    assert len(report.checks) == 5
    for c in report.checks:
        assert c.passed is True, f"Başarısız kontrol: {c.name} - {c.errors}"

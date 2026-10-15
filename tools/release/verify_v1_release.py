"""Birleşik Yayın Doğrulayıcısı (tools/release/verify_v1_release.py).

K-807 / Faz 2 (Adım 2/3):
1. Sürüm Senkronizasyonu: pyproject.toml, apps/desktop/package.json,
   apps/desktop/src-tauri/tauri.conf.json ve apps/desktop/src-tauri/Cargo.toml
   dosyalarındaki sürümün '1.0.0' olduğunu doğrular.
2. CHANGELOG.md: Dosyanın varlığını ve [1.0.0] başlığını doğrular.
3. 5 Kronometreli Koşu (timed_runs_report.json): 5 başarılı koşu olduğunu ve
   medyan sürenin bütçe altında (<= 900.000 ms) kaldığını doğrular.
4. K-804 & K-805 Kapıları: run_bench.py (results.json) ve run_security_gate.py
   (audit_report.json) raporlarının passed == True olduğunu doğrular.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = "1.0.0"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    errors: list[str] = field(default_factory=list)


@dataclass
class ReleaseVerificationReport:
    timestamp: str
    expected_version: str
    all_passed: bool
    checks: list[CheckResult]


def verify_versions(repo_root: Path = REPO_ROOT) -> CheckResult:
    """Tüm paket tanımlarında sürümün '1.0.0' olduğunu doğrular."""
    target_files: dict[str, Path] = {
        "pyproject.toml (Kök)": repo_root / "pyproject.toml",
        "pyproject.toml (Core)": repo_root / "services" / "core" / "pyproject.toml",
        "package.json (Desktop)": repo_root / "apps" / "desktop" / "package.json",
        "tauri.conf.json": repo_root / "apps" / "desktop" / "src-tauri" / "tauri.conf.json",
        "Cargo.toml (Desktop Shell)": repo_root / "apps" / "desktop" / "src-tauri" / "Cargo.toml",
    }

    errors: list[str] = []
    verified_entries: list[str] = []

    for label, path in target_files.items():
        if not path.is_file():
            errors.append(f"{label}: Dosya mevcut değil -> {path}")
            continue

        try:
            content = path.read_text(encoding="utf-8")
            resolved_version: str | None = None

            if path.suffix == ".json":
                data = json.loads(content)
                if isinstance(data, dict):
                    resolved_version = str(data.get("version", ""))
            elif path.name == "Cargo.toml":
                data_toml = tomllib.loads(content)
                pkg = data_toml.get("package", {})
                if isinstance(pkg, dict):
                    resolved_version = str(pkg.get("version", ""))
            elif path.name == "pyproject.toml":
                data_toml = tomllib.loads(content)
                proj = data_toml.get("project", {})
                if isinstance(proj, dict):
                    resolved_version = str(proj.get("version", ""))

            if resolved_version != EXPECTED_VERSION:
                errors.append(
                    f"{label}: Sürüm uyuşmazlığı! Beklenen '{EXPECTED_VERSION}', bulunan '{resolved_version}' ({path})"
                )
            else:
                verified_entries.append(f"{label} = {resolved_version}")

        except Exception as exc:
            errors.append(f"{label}: Okuma/ayrıştırma hatası -> {exc}")

    passed = len(errors) == 0
    details = f"{len(verified_entries)}/{len(target_files)} dosya doğrulandı ({EXPECTED_VERSION})"
    return CheckResult(name="Sürüm Senkronizasyonu (1.0.0)", passed=passed, details=details, errors=errors)


def verify_changelog(repo_root: Path = REPO_ROOT) -> CheckResult:
    """CHANGELOG.md dosyasının varlığını ve [1.0.0] başlığını doğrular."""
    changelog_path = repo_root / "CHANGELOG.md"
    errors: list[str] = []

    if not changelog_path.is_file():
        return CheckResult(
            name="CHANGELOG.md Doğrulaması",
            passed=False,
            details="CHANGELOG.md dosyası bulunamadı",
            errors=["CHANGELOG.md dosyası kök dizinde mevcut değil"],
        )

    content = changelog_path.read_text(encoding="utf-8")

    # [1.0.0] başlık kontrolü
    if not re.search(r"##\s*\[1\.0\.0\]", content):
        errors.append("CHANGELOG.md içinde '## [1.0.0]' sürüm başlığı bulunamadı")

    # M1 - M8 kilometre taşı kontrolleri
    for milestone in ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]:
        if milestone not in content:
            errors.append(f"CHANGELOG.md içinde {milestone} mimari kilometre taşı içeriği eksik")

    passed = len(errors) == 0
    details = f"CHANGELOG.md mevcut, [1.0.0] ve M1-M8 kilometre taşları doğrulandı ({len(content)} bayt)"
    return CheckResult(name="CHANGELOG.md Doğrulaması", passed=passed, details=details, errors=errors)


def verify_timed_runs_report(repo_root: Path = REPO_ROOT) -> CheckResult:
    """timed_runs_report.json içinde 5 başarılı koşu ve bütçe uyumunu doğrular."""
    report_path = repo_root / "tools" / "release" / "timed_runs_report.json"
    errors: list[str] = []

    if not report_path.is_file():
        return CheckResult(
            name="5 Kronometreli Koşu Raporu",
            passed=False,
            details="timed_runs_report.json bulunamadı",
            errors=["tools/release/timed_runs_report.json dosyası mevcut değil. Önce timed_runs.py çalıştırılmalı."],
        )

    try:
        data: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        runs = data.get("runs", [])

        runs_count = summary.get("runs_count", 0)
        median_ms = summary.get("median_ms", float("inf"))
        budget_ms = summary.get("budget_ms", 900_000.0)
        passed_flag = summary.get("passed", False)

        if runs_count != 5:
            errors.append(f"Koşu sayısı 5 olmalıdır, rapordaki sayı: {runs_count}")

        if len(runs) != 5:
            errors.append(f"Rapordaki detaylı koşu listesi 5 eleman içermelidir, bulunan: {len(runs)}")

        if not passed_flag:
            errors.append("timed_runs_report.json summary.passed alanı False")

        if median_ms > budget_ms:
            errors.append(
                f"Medyan süre bütçeyi aştı: {median_ms:.2f} ms > {budget_ms:.2f} ms"
            )

        details = f"5/5 koşu başarılı, Medyan: {median_ms:.2f} ms (Bütçe: <= {budget_ms:.0f} ms)"
    except Exception as exc:
        return CheckResult(
            name="5 Kronometreli Koşu Raporu",
            passed=False,
            details=f"Ayrıştırma hatası: {exc}",
            errors=[str(exc)],
        )

    passed = len(errors) == 0
    return CheckResult(name="5 Kronometreli Koşu Raporu", passed=passed, details=details, errors=errors)


def verify_k804_bench_gate(repo_root: Path = REPO_ROOT) -> CheckResult:
    """K-804 Performans Kapısı (results.json) passed == True doğrulaması."""
    results_path = repo_root / "tools" / "bench" / "results.json"
    errors: list[str] = []

    if not results_path.is_file():
        return CheckResult(
            name="K-804 Performans Bütçe Kapısı",
            passed=False,
            details="tools/bench/results.json bulunamadı",
            errors=["tools/bench/results.json mevcut değil. Önce run_bench.py çalıştırılmalı."],
        )

    try:
        data: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))
        all_passed = data.get("all_passed", False)
        metrics = data.get("results", [])

        if not all_passed:
            errors.append("tools/bench/results.json içinde all_passed == False")

        failed_metrics = [m.get("name", "Bilinmeyen") for m in metrics if not m.get("passed", False)]
        if failed_metrics:
            errors.append(f"Başarısız metrikler: {', '.join(failed_metrics)}")

        details = f"{len(metrics)} metrik denetlendi, all_passed={all_passed}"
    except Exception as exc:
        return CheckResult(
            name="K-804 Performans Bütçe Kapısı",
            passed=False,
            details=f"Ayrıştırma hatası: {exc}",
            errors=[str(exc)],
        )

    passed = len(errors) == 0
    return CheckResult(name="K-804 Performans Bütçe Kapısı", passed=passed, details=details, errors=errors)


def verify_k805_security_gate(repo_root: Path = REPO_ROOT) -> CheckResult:
    """K-805 Güvenlik Kapısı (audit_report.json) gate_passed == True doğrulaması."""
    report_path = repo_root / "tools" / "security" / "audit_report.json"
    errors: list[str] = []

    if not report_path.is_file():
        return CheckResult(
            name="K-805 Güvenlik ve Lisans Kapısı",
            passed=False,
            details="tools/security/audit_report.json bulunamadı",
            errors=["tools/security/audit_report.json mevcut değil. Önce run_security_gate.py çalıştırılmalı."],
        )

    try:
        data: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
        gate_passed = data.get("gate_passed", False)
        open_issues = data.get("open_issues", 0)
        license_violations = data.get("license_violations", 0)
        static_audit = data.get("static_audit", {})
        supply_audit = data.get("supply_chain_audit", {})

        if not gate_passed:
            errors.append("tools/security/audit_report.json içinde gate_passed == False")

        if open_issues > 0:
            errors.append(f"Açık güvenlik sorunu tespit edildi: {open_issues}")

        if license_violations > 0:
            errors.append(f"Lisans ihlali tespit edildi: {license_violations}")

        if not static_audit.get("passed", False):
            errors.append("Statik mimari denetimi (static_audit) başarısız")

        if not supply_audit.get("passed", False):
            errors.append("Tedarik zinciri denetimi (supply_chain_audit) başarısız")

        details = (
            f"gate_passed={gate_passed}, açık_sorun={open_issues}, lisans_ihlali={license_violations}, "
            f"taranan_paket={supply_audit.get('total_packages_scanned', 0)}"
        )
    except Exception as exc:
        return CheckResult(
            name="K-805 Güvenlik ve Lisans Kapısı",
            passed=False,
            details=f"Ayrıştırma hatası: {exc}",
            errors=[str(exc)],
        )

    passed = len(errors) == 0
    return CheckResult(name="K-805 Güvenlik ve Lisans Kapısı", passed=passed, details=details, errors=errors)


def run_all_release_checks(repo_root: Path = REPO_ROOT) -> ReleaseVerificationReport:
    """Tüm ana yayın doğrulama kapılarını yürütür."""
    checks: list[CheckResult] = [
        verify_versions(repo_root),
        verify_changelog(repo_root),
        verify_timed_runs_report(repo_root),
        verify_k804_bench_gate(repo_root),
        verify_k805_security_gate(repo_root),
    ]

    all_passed = all(c.passed for c in checks)
    return ReleaseVerificationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        expected_version=EXPECTED_VERSION,
        all_passed=all_passed,
        checks=checks,
    )


def print_report(report: ReleaseVerificationReport) -> None:
    """Raporu konsola yazdırır."""
    print("\n" + "=" * 80)
    print(" HUSTLER v1.0.0 BIRLESIK YAYIN DOGRULAYICISI (K-807 RELEASE GATE)")
    print("=" * 80)
    print(f"Zaman Damgasi   : {report.timestamp}")
    print(f"Hedef Surum     : {report.expected_version}")
    print(f"Genel Durum     : {'[PASSED] YAYINA HAZIR' if report.all_passed else '[FAILED] YAYIN ENGELLENDI'}")
    print("-" * 80)

    for idx, c in enumerate(report.checks, start=1):
        status_tag = "[PASS]" if c.passed else "[FAIL]"
        print(f"[{idx}/5] {c.name:<35} {status_tag} -> {c.details}")
        if not c.passed and c.errors:
            for err in c.errors:
                print(f"      * HATA: {err}")

    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hustler v1.0.0 Birleşik Yayın Doğrulayıcısı")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "tools" / "release" / "release_verification.json",
        help="Doğrulama sonuçlarının kaydedileceği JSON dosyası",
    )
    args = parser.parse_args()

    report = run_all_release_checks(REPO_ROOT)
    print_report(report)

    # JSON Raporunu Diske Yaz
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_dict = {
        "timestamp": report.timestamp,
        "expected_version": report.expected_version,
        "all_passed": report.all_passed,
        "checks": [asdict(c) for c in report.checks],
    }
    args.output.write_text(json.dumps(report_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    if not report.all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

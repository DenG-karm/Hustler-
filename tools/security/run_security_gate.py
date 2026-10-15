"""
K-805 (Adım 2/3): Birleşik Güvenlik Kapısı ve Rapor Üreteci (tools/security/run_security_gate.py).

Gereksinimler:
1. Hem static_audit.py hem de supply_chain_audit.py denetimlerini çalıştırır.
2. tools/security/audit_report.json rapor dosyasını üretir.
3. Rapor içinde open_issues == 0 ve license_violations == 0 değilse sys.exit(1) ile derlemeyi kırar.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.security.static_audit import run_all_audits  # noqa: E402
from tools.security.supply_chain_audit import run_supply_chain_audit  # noqa: E402

REPORT_PATH = REPO_ROOT / "tools" / "security" / "audit_report.json"


def execute_security_gate(
    repo_root: Path = REPO_ROOT,
    report_file: Path = REPORT_PATH,
) -> tuple[bool, dict[str, Any]]:
    # 1. Statik Mimari Güvenlik Denetimi
    static_passed, static_results = run_all_audits(repo_root)

    # 2. Tedarik Zinciri ve Lisans Denetimi
    supply_report = run_supply_chain_audit(repo_root)

    # Açık maddeleri ve ihlalleri topla
    static_errors_flat: list[str] = [err for err_list in static_results.values() for err in err_list]
    license_violations: list[dict[str, Any]] = supply_report.get("license_violations", [])

    open_issues_count = len(static_errors_flat) + len(license_violations)
    license_violations_count = len(license_violations)
    gate_passed = (open_issues_count == 0) and (license_violations_count == 0)

    # Yapılandırılmış Rapor
    report_payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate_passed": gate_passed,
        "open_issues": open_issues_count,
        "license_violations": license_violations_count,
        "static_audit": {
            "passed": static_passed,
            "details": {
                name: {
                    "passed": len(errs) == 0,
                    "errors": errs,
                }
                for name, errs in static_results.items()
            },
        },
        "supply_chain_audit": {
            "passed": supply_report.get("passed", False),
            "total_packages_scanned": supply_report.get("total_packages_scanned", 0),
            "python_packages_count": supply_report.get("python_packages_count", 0),
            "frontend_packages_count": supply_report.get("frontend_packages_count", 0),
            "rust_packages_count": supply_report.get("rust_packages_count", 0),
            "license_violations": license_violations,
        },
    }

    # audit_report.json dosyasına atomik yaz
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return gate_passed, report_payload


def main() -> None:
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn) and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 80)
    print(" HUSTLER BIRLESIK GUVENLIK KAPISI VE RAPOR URETECI (K-805 GATE)")
    print("=" * 80)

    gate_passed, report = execute_security_gate(REPO_ROOT, REPORT_PATH)

    print(f"Rapor Dosyası           : {REPORT_PATH}")
    print(f"Statik Mimari Denetimi  : {'[PASS]' if report['static_audit']['passed'] else '[FAIL]'}")
    print(f"Tedarik Zinciri Denetimi: {'[PASS]' if report['supply_chain_audit']['passed'] else '[FAIL]'}")
    print(f"Taranan Toplam Paket    : {report['supply_chain_audit']['total_packages_scanned']}")
    print(f"  - Python Paketleri    : {report['supply_chain_audit']['python_packages_count']}")
    print(f"  - Frontend Paketleri  : {report['supply_chain_audit']['frontend_packages_count']}")
    print(f"  - Rust Paketleri      : {report['supply_chain_audit']['rust_packages_count']}")
    print(f"Lisans İhlalleri Sayısı : {report['license_violations']}")
    print(f"Açık Güvenlik Maddesi   : {report['open_issues']}")
    print("=" * 80)

    if gate_passed and report["open_issues"] == 0 and report["license_violations"] == 0:
        print("[PASS] TUM GUVENLIK VE LISANS KAPILARI BASARIYLA GECILDI (EXIT 0).")
        print("=" * 80)
        sys.exit(0)
    else:
        print("[FAIL] GUVENLIK VEYA LISANS IHLALI TESPIT EDILDI! CI GATE KIRILDI (EXIT 1).")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

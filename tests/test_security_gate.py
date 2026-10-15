"""
K-805 Faz 3 (Adım 3/3): Acımasız Sabotaj Testleri (tests/test_security_gate.py).

Testler:
1. Test 1 (Temiz Kapı): Mevcut repoda run_security_gate.py çalıştığında open_issues == 0,
   license_violations == 0 ve exit_code == 0 döndüğünü doğrular.
2. Test 2 (IPC Drift Sabotajı): lib.rs içine 'gizli_arka_kapi_komutu' enjekte edildiğinde
   audit_ipc_command_match fonksiyonunun simetrik farkı anında yakaladığını ve kapıyı kırdığını kanıtlar.
3. Test 3 (CSP & Loopback Sabotajı): tauri.conf.json içine 'unsafe-inline' veya main.py içine
   '0.0.0.0' enjekte edildiğinde kapının anında kırıldığını kanıtlar.
4. Test 4 (GPL & AND Lisans Sabotajı): is_strong_copyleft("AGPL-3.0-only") ve
   is_strong_copyleft("MIT AND GPL-3.0-only") çağrılarının True döndüğünü ve güvenlik kapısını
   exit_code == 1 ile kırdığını kanıtlar.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

from tools.security.run_security_gate import REPO_ROOT, execute_security_gate
from tools.security.static_audit import (
    audit_ipc_command_match,
    audit_loopback_isolation,
    audit_tauri_csp_and_permissions,
    strip_rust_comments,
)
from tools.security.supply_chain_audit import (
    is_allowed_license,
    is_strong_copyleft,
)


# =============================================================================
# Test 1: Temiz Kapı Doğrulaması (Clean Gate Run)
# =============================================================================
def test_clean_security_gate_passes() -> None:
    """Temiz repoda run_security_gate çalıştığında 0 hata, 0 lisans ihlali ve PASS olduğunu doğrular."""
    gate_passed, report = execute_security_gate(REPO_ROOT)

    assert gate_passed is True, f"Güvenlik kapısı temiz repoda başarısız oldu: {report}"
    assert report["open_issues"] == 0, f"Açık maddeler bulundu: {report['open_issues']}"
    assert report["license_violations"] == 0, f"Lisans ihlalleri bulundu: {report['license_violations']}"
    assert report["static_audit"]["passed"] is True
    assert report["supply_chain_audit"]["passed"] is True
    assert report["supply_chain_audit"]["total_packages_scanned"] >= 50

    # CLI alt süreç testi (Exit Code == 0 kanıtı)
    cmd = [sys.executable, str(REPO_ROOT / "tools" / "security" / "run_security_gate.py")]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, f"run_security_gate.py exit code {res.returncode} döndü: {res.stderr}\n{res.stdout}"
    assert "TUM GUVENLIK VE LISANS KAPILARI BASARIYLA GECILDI" in res.stdout


def test_strip_rust_comments_preserves_loopback_urls() -> None:
    """strip_rust_comments fonksiyonunun http://127.0.0.1 gibi URL'leri bozmadığını doğrular."""
    sample_code = """
    // Bu bir satır başı yorumudur
    let url = "http://127.0.0.1:8000/health"; // Satır sonu yorumu
    /* Blok yorum */
    let s = "https://example.com";
    """
    cleaned = strip_rust_comments(sample_code)
    assert "http://127.0.0.1:8000/health" in cleaned
    assert "https://example.com" in cleaned
    assert "Bu bir satır başı yorumudur" not in cleaned
    assert "Satır sonu yorumu" not in cleaned
    assert "Blok yorum" not in cleaned


# =============================================================================
# Test 2: IPC Drift Sabotajı (Bilateral Drift & Backdoor Injection)
# =============================================================================
def test_ipc_drift_backdoor_injection_sabotage(tmp_path: Path) -> None:
    """lib.rs içine tauri::generate_handler![..., gizli_arka_kapi_komutu] eklendiğinde yakalandığını kanıtlar."""
    fake_ts = tmp_path / "apps" / "desktop" / "src" / "lib" / "securityGuard.ts"
    fake_rs = tmp_path / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs"
    fake_ts.parent.mkdir(parents=True, exist_ok=True)
    fake_rs.parent.mkdir(parents=True, exist_ok=True)

    fake_ts.write_text(
        """
        export const ALLOWED_IPC_COMMANDS: ReadonlySet<string> = new Set([
          "proxy_request",
          "flow_discovery_run"
        ]);
        """,
        encoding="utf-8",
    )

    # Rust tarafına 'gizli_arka_kapi_komutu' enjekte et
    fake_rs.write_text(
        """
        fn run() {
            tauri::Builder::default()
                .invoke_handler(tauri::generate_handler![
                    proxy_request,
                    flow_discovery_run,
                    gizli_arka_kapi_komutu
                ]);
        }
        """,
        encoding="utf-8",
    )

    errors = audit_ipc_command_match(tmp_path)
    assert len(errors) > 0, "Arka kapı komutu tespit edilemedi!"
    err_text = " ".join(errors)
    assert "gizli_arka_kapi_komutu" in err_text
    assert "simetrik fark" in err_text.lower() or "rust'ta olup" in err_text.lower()


def test_ipc_drift_ts_extra_command_sabotage(tmp_path: Path) -> None:
    """TS tarafında Rust'ta karşılığı olmayan sahte komut tanımlandığında simetrik farkın yakalandığını kanıtlar."""
    fake_ts = tmp_path / "apps" / "desktop" / "src" / "lib" / "securityGuard.ts"
    fake_rs = tmp_path / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs"
    fake_ts.parent.mkdir(parents=True, exist_ok=True)
    fake_rs.parent.mkdir(parents=True, exist_ok=True)

    fake_ts.write_text(
        """
        export const ALLOWED_IPC_COMMANDS: ReadonlySet<string> = new Set([
          "proxy_request",
          "flow_olmayan_komut"
        ]);
        """,
        encoding="utf-8",
    )

    fake_rs.write_text(
        """
        fn run() {
            tauri::Builder::default()
                .invoke_handler(tauri::generate_handler![
                    proxy_request
                ]);
        }
        """,
        encoding="utf-8",
    )

    errors = audit_ipc_command_match(tmp_path)
    assert len(errors) > 0
    err_text = " ".join(errors)
    assert "flow_olmayan_komut" in err_text
    assert "ts'de olup" in err_text.lower()


# =============================================================================
# Test 3: CSP & Loopback Sabotajı
# =============================================================================
def test_csp_unsafe_inline_sabotage(tmp_path: Path) -> None:
    """tauri.conf.json içine 'unsafe-inline' enjekte edildiğinde denetimin başarısız olduğunu kanıtlar."""
    tauri_conf = tmp_path / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
    tauri_conf.parent.mkdir(parents=True, exist_ok=True)

    conf_data = {
        "app": {
            "security": {
                "csp": {
                    "default-src": ["'self'"],
                    "script-src": ["'self'", "'unsafe-inline'"],
                }
            }
        }
    }
    tauri_conf.write_text(json.dumps(conf_data), encoding="utf-8")

    errors = audit_tauri_csp_and_permissions(tmp_path)
    assert len(errors) > 0
    err_text = " ".join(errors)
    assert "unsafe-inline" in err_text
    assert "CWE-79" in err_text


def test_csp_wildcard_sabotage(tmp_path: Path) -> None:
    """tauri.conf.json içine wildcard '*' veya güvensiz HTTP adresi enjekte edildiğinde yakalandığını kanıtlar."""
    tauri_conf = tmp_path / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
    tauri_conf.parent.mkdir(parents=True, exist_ok=True)

    conf_data = {
        "app": {
            "security": {
                "csp": "default-src 'self' *; script-src 'self' http://insecure-cdn.com"
            }
        }
    }
    tauri_conf.write_text(json.dumps(conf_data), encoding="utf-8")

    errors = audit_tauri_csp_and_permissions(tmp_path)
    assert len(errors) >= 2
    err_text = " ".join(errors)
    assert "wildcard (*)" in err_text
    assert "http://insecure-cdn.com" in err_text


def test_loopback_isolation_0000_sabotage(tmp_path: Path) -> None:
    """services/core/hustler/main.py içine host='0.0.0.0' enjekte edildiğinde yakalandığını kanıtlar."""
    main_py = tmp_path / "services" / "core" / "hustler" / "main.py"
    main_py.parent.mkdir(parents=True, exist_ok=True)

    # 0.0.0.0 sabotajı
    main_py.write_text(
        """
        # Uvicorn server startup
        uvicorn.run(app, host="0.0.0.0", port=8000)
        """,
        encoding="utf-8",
    )

    errors = audit_loopback_isolation(tmp_path)
    assert len(errors) > 0
    err_text = " ".join(errors)
    assert "0.0.0.0" in err_text


# =============================================================================
# Test 4: GPL & AND Lisans Sabotajı (SPDX AND & Exit Code 1 Kanıtı)
# =============================================================================
def test_is_strong_copyleft_evaluates_correctly() -> None:
    """is_strong_copyleft fonksiyonunun AGPL, GPL ve SPDX AND kurallarını doğru işlediğini kanıtlar."""
    # Sabotaj kuralı 1: AGPL-3.0-only -> True
    assert is_strong_copyleft("AGPL-3.0-only") is True
    assert is_strong_copyleft("AGPL-1.0") is True

    # Sabotaj kuralı 2: MIT AND GPL-3.0-only -> True (Permissive alternatif kaçamağı AND ile bloke edilir)
    assert is_strong_copyleft("MIT AND GPL-3.0-only") is True
    assert is_strong_copyleft("Apache-2.0 AND AGPL-3.0") is True

    # OR kuralı: Apache-2.0 OR GPL-2.0 -> False (Çift lisanslı seçimde serbest alternatif geçerlidir)
    assert is_strong_copyleft("Apache-2.0 OR GPL-2.0") is False

    # İstisnalı GPL (örn. PyInstaller istisnası) -> False
    assert is_strong_copyleft("GPLv2-or-later with exception") is False

    # LGPL serbesttir (Weak copyleft) -> False
    assert is_strong_copyleft("LGPL-3.0-only") is False
    assert is_strong_copyleft("LGPL-2.1") is False

    # İzinli serbest lisanslar -> False
    assert is_strong_copyleft("MIT") is False
    assert is_strong_copyleft("Apache-2.0") is False
    assert is_strong_copyleft("BSD-3-Clause") is False


def test_is_allowed_license_whitelist_enforcement() -> None:
    """Gerçek Beyaz Liste Doğrulaması: Onaylı ve onaysız lisans ayrımını doğrular."""
    assert is_allowed_license("MIT") is True
    assert is_allowed_license("Apache-2.0") is True
    assert is_allowed_license("BSD-3-Clause") is True
    assert is_allowed_license("PSF-2.0") is True
    assert is_allowed_license("MPL-2.0") is True
    assert is_allowed_license("Unlicense") is True
    assert is_allowed_license("0BSD") is True
    assert is_allowed_license("CC0-1.0") is True

    # Onaysız / Bilinmeyen lisanslar
    assert is_allowed_license("UNKNOWN") is False
    assert is_allowed_license("Proprietary-Commercial-Evil") is False
    assert is_allowed_license("Custom-Non-Redistributable") is False


def test_supply_chain_sabotage_breaks_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Tedarik zincirine 'MIT AND GPL-3.0-only' veya 'AGPL-3.0-only' enjekte edildiğinde kapının exit 1 ile kırıldığını kanıtlar."""
    fake_report = {
        "passed": False,
        "total_packages_scanned": 1,
        "python_packages_count": 1,
        "frontend_packages_count": 0,
        "rust_packages_count": 0,
        "license_violations": [
            {
                "name": "sabotaged-copyleft-package",
                "version": "1.0.0",
                "ecosystem": "python",
                "license": "MIT AND GPL-3.0-only",
                "is_dev": False,
                "is_allowed": True,
                "violation": "STRONG_COPYLEFT_GPL_OR_AGPL",
            }
        ],
        "packages": [],
    }

    monkeypatch.setattr(
        "tools.security.run_security_gate.run_supply_chain_audit",
        lambda repo_root: fake_report,
    )

    report_file = tmp_path / "audit_report.json"
    gate_passed, report = execute_security_gate(REPO_ROOT, report_file=report_file)

    assert gate_passed is False, "Lisans sabotajına rağmen kapı geçti!"
    assert report["license_violations"] == 1
    assert report["open_issues"] >= 1

    # Rapor dosyasının yazıldığını ve ihlali içerdiğini doğrula
    saved = json.loads(report_file.read_text(encoding="utf-8"))
    assert saved["gate_passed"] is False
    assert saved["license_violations"] == 1
    assert saved["supply_chain_audit"]["license_violations"][0]["name"] == "sabotaged-copyleft-package"


def test_cli_gate_exit_code_1_on_violation(tmp_path: Path) -> None:
    """Güvenlik ihlali durumunda CLI scriptinin sys.exit(1) döndürdüğünü subprocess ile kanıtlar."""
    runner_script = tmp_path / "sabotage_runner.py"
    runner_script.write_text(
        f"""
import sys
from pathlib import Path
REPO_ROOT = Path(r"{REPO_ROOT}")
sys.path.insert(0, str(REPO_ROOT))

from unittest.mock import patch
import tools.security.run_security_gate as rsg

fake_report = {{
    "passed": False,
    "total_packages_scanned": 10,
    "python_packages_count": 5,
    "frontend_packages_count": 5,
    "rust_packages_count": 0,
    "license_violations": [
        {{"name": "evil-gpl", "version": "1.0", "ecosystem": "python", "license": "AGPL-3.0-only", "violation": "STRONG_COPYLEFT_GPL_OR_AGPL"}}
    ],
    "packages": [],
}}

with (
    patch("tools.security.run_security_gate.run_supply_chain_audit", return_value=fake_report),
    patch.object(rsg, "REPORT_PATH", Path(r"{tmp_path / 'audit_report.json'}")),
):
    rsg.main()
        """,
        encoding="utf-8",
    )

    res = subprocess.run([sys.executable, str(runner_script)], cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 1, f"İhlal durumunda exit code 1 beklenirken {res.returncode} döndü!"
    assert "GUVENLIK VEYA LISANS IHLALI TESPIT EDILDI" in res.stdout

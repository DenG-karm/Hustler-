"""
K-805 (Adım 1/3): Statik Mimari Güvenlik Denetleyicisi (tools/security/static_audit.py).

Denetim Alanları:
1. Tauri CSP & İzinler: 'unsafe-eval', wildcard (*), güvensiz http://, script-src data:/blob:/'unsafe-inline',
   ve capabilities izinlerinde kök/$HOME/$DOCUMENT/$DESKTOP/** erişim denetimi.
2. Çapraz Dil IPC Eşleşmesi: Rust tauri::generate_handler! ile TS securityGuard.ts (rust_commands ^ ts_custom == 0).
3. Sidecar Loopback İzolasyonu: Yorumlar ayıklanarak Uvicorn/FastAPI ve Rust tarafında 127.0.0.1 doğrulaması.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def strip_python_comments(source: str) -> str:
    """Python kaynak kodundan satır içi ve bağımsız '#' yorumlarını temizler."""
    return re.sub(r"#.*$", "", source, flags=re.MULTILINE)


def strip_rust_comments(source: str) -> str:
    """Rust kaynak kodundan '/* ... */' blok ve '//' satır yorumlarını temizler.

    Yalnız satır başında veya ':' sonrasında gelmeyen ((?<!:)//.*$) yorumlar silinir;
    böylece "http://127.0.0.1" veya "https://..." URL stringleri parçalanmaz.
    """
    no_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?<!:)//.*$", "", no_blocks, flags=re.MULTILINE)


# =============================================================================
# 1. Tauri CSP ve İzin Denetimi
# =============================================================================
def audit_tauri_csp_and_permissions(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    tauri_conf_path = repo_root / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
    if not tauri_conf_path.exists():
        return [f"Tauri yapılandırma dosyası bulunamadı: {tauri_conf_path}"]

    try:
        conf = json.loads(tauri_conf_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"tauri.conf.json okunamadı: {e}"]

    raw_csp: str | dict[str, Any] = conf.get("app", {}).get("security", {}).get("csp", "")
    if not raw_csp:
        errors.append("tauri.conf.json içinde üretim CSP (app.security.csp) tanımlı değil!")
    else:
        directives: dict[str, list[str]] = {}
        if isinstance(raw_csp, dict):
            for k, v in raw_csp.items():
                k_clean = k.lower().strip()
                directives[k_clean] = [str(x).strip() for x in v] if isinstance(v, list) else str(v).strip().split()
        elif isinstance(raw_csp, str):
            for part in raw_csp.split(";"):
                tokens = part.strip().split()
                if tokens:
                    directives[tokens[0].lower()] = tokens[1:]

        all_sources = [s for srcs in directives.values() for s in srcs]
        if any("'unsafe-eval'" in s for s in all_sources):
            errors.append("CSP içinde 'unsafe-eval' direktifi tespit edildi (XSS riski)!")

        script_srcs = directives.get("script-src", [])
        if any("'unsafe-inline'" in s for s in script_srcs):
            errors.append("CSP script-src içinde 'unsafe-inline' tespit edildi (CWE-79 XSS riski)!")

        for directive, sources in directives.items():
            for src in sources:
                if src == "*":
                    errors.append(f"CSP {directive} direktifinde wildcard (*) kaynağı tespit edildi!")
                if src.startswith("http://") and not (
                    src.startswith("http://localhost")
                    or src.startswith("http://ipc.localhost")
                    or src.startswith("http://127.0.0.1")
                ):
                    errors.append(f"CSP {directive} direktifinde güvensiz HTTP kaynağı: {src}")

        for d_name in ("script-src", "default-src"):
            for src in directives.get(d_name, []):
                if src in ("data:", "blob:") or src.startswith("data:") or src.startswith("blob:"):
                    errors.append(f"CWE-79: {d_name} direktifi içinde güvensiz '{src}' tespit edildi!")

    cap_dir = repo_root / "apps" / "desktop" / "src-tauri" / "capabilities"
    forbidden_tokens = {"$HOME", "$DOCUMENT", "$DESKTOP", "$DOWNLOAD", "**", "*", "/*", "C:\\*", "C:/*"}
    if cap_dir.exists():
        for cap_file in cap_dir.glob("*.json"):
            try:
                cap_data = json.loads(cap_file.read_text(encoding="utf-8"))
                for perm in cap_data.get("permissions", []):
                    if isinstance(perm, str) and any(tok in perm for tok in forbidden_tokens):
                        errors.append(f"{cap_file.name}: Güvensiz kapsam/wildcard içeren dosya izni: {perm}")
                    elif isinstance(perm, dict):
                        for scope in ("allow", "deny"):
                            for item in perm.get(scope, []):
                                p_str = str(item.get("path", "") if isinstance(item, dict) else item)
                                if any(tok in p_str for tok in forbidden_tokens):
                                    errors.append(f"{cap_file.name}: Güvensiz dosya erişim yolu ({scope}): {p_str}")
            except Exception as e:
                errors.append(f"Capability dosyası okunamadı {cap_file.name}: {e}")

    return errors


# =============================================================================
# 2. Çapraz Dil IPC İzin Listesi Eşleşmesi (Rust <-> TypeScript)
# =============================================================================
def audit_ipc_command_match(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    ts_path = repo_root / "apps" / "desktop" / "src" / "lib" / "securityGuard.ts"
    rs_path = repo_root / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs"

    if not ts_path.exists() or not rs_path.exists():
        return [f"IPC kaynak dosyaları bulunamadı: ts={ts_path.exists()}, rs={rs_path.exists()}"]

    ts_content = ts_path.read_text(encoding="utf-8")
    rs_content = strip_rust_comments(rs_path.read_text(encoding="utf-8"))

    ts_match = re.search(r"ALLOWED_IPC_COMMANDS[^{[]*Set\(\s*\[(.*?)\]\s*\)", ts_content, re.DOTALL)
    if not ts_match:
        return ["securityGuard.ts içinde ALLOWED_IPC_COMMANDS kümesi bulunamadı!"]
    ts_commands = set(re.findall(r"['\"]([a-zA-Z0-9_:|]+)['\"]", ts_match.group(1)))

    # TS tarafındaki özel (custom) Rust komutları (plugin:* ve supervisor:* sistem komutları hariç)
    ts_custom_commands = {
        c for c in ts_commands if not (c.startswith("plugin:") or c.startswith("supervisor:") or ":" in c or "|" in c)
    }

    rs_match = re.search(r"generate_handler!\s*\[(.*?)\]", rs_content, re.DOTALL)
    if not rs_match:
        return ["lib.rs içinde tauri::generate_handler! makrosu bulunamadı!"]
    raw_handlers = re.findall(r"([a-zA-Z0-9_:]+)", rs_match.group(1))
    rust_commands = {h.split("::")[-1] for h in raw_handlers if h}

    sym_diff = rust_commands ^ ts_custom_commands
    if sym_diff:
        only_in_rust = rust_commands - ts_custom_commands
        only_in_ts = ts_custom_commands - rust_commands
        errors.append(
            f"IPC komut eşleşmesinde simetrik fark tespit edildi: "
            f"Rust'ta olup TS'de olmayan: {sorted(only_in_rust)}, TS'de olup Rust'ta olmayan: {sorted(only_in_ts)}"
        )

    return errors


# =============================================================================
# 3. Sidecar Loopback İzolasyonu (127.0.0.1 vs 0.0.0.0)
# =============================================================================
def audit_loopback_isolation(repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    main_py_path = repo_root / "services" / "core" / "hustler" / "main.py"
    if not main_py_path.exists():
        return [f"Backend main.py bulunamadı: {main_py_path}"]

    main_content = strip_python_comments(main_py_path.read_text(encoding="utf-8"))
    if not re.search(r"""host\s*=\s*["']127\.0\.0\.1["']""", main_content):
        errors.append("services/core/hustler/main.py içinde host='127.0.0.1' bağlaması bulunamadı!")
    if "0.0.0.0" in main_content:
        errors.append("services/core/hustler/main.py içinde tehlikeli '0.0.0.0' adresi tespit edildi!")

    for py_file in (repo_root / "services" / "core" / "hustler").rglob("*.py"):
        clean_py = strip_python_comments(py_file.read_text(encoding="utf-8"))
        if "0.0.0.0" in clean_py:
            errors.append(f"{py_file.relative_to(repo_root)} içinde '0.0.0.0' tespiti! Loopback ihlali.")

    rs_path = repo_root / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs"
    if rs_path.exists():
        rs_content = strip_rust_comments(rs_path.read_text(encoding="utf-8"))
        if "0.0.0.0" in rs_content:
            errors.append("apps/desktop/src-tauri/src/lib.rs içinde '0.0.0.0' tespiti!")
        if "127.0.0.1" not in rs_content:
            errors.append("apps/desktop/src-tauri/src/lib.rs içinde sidecar 127.0.0.1 loopback adresi eksik!")

    return errors


# =============================================================================
# Ana Koşucu ve CLI Arayüzü
# =============================================================================
def run_all_audits(repo_root: Path = REPO_ROOT) -> tuple[bool, dict[str, list[str]]]:
    results: dict[str, list[str]] = {
        "Tauri CSP ve İzin Denetimi": audit_tauri_csp_and_permissions(repo_root),
        "Çapraz Dil IPC İzin Eşleşmesi": audit_ipc_command_match(repo_root),
        "Sidecar Loopback İzolasyonu": audit_loopback_isolation(repo_root),
    }
    all_passed = all(len(errs) == 0 for errs in results.values())
    return all_passed, results


def main() -> None:
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn) and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 80)
    print(" HUSTLER STATIK MIMARI GUVENLIK DENETLEYICISI (K-805 AUDIT)")
    print("=" * 80)

    all_passed, results = run_all_audits(REPO_ROOT)
    for audit_name, errors in results.items():
        status = "[PASS]" if not errors else "[FAIL]"
        print(f"{audit_name:<40} {status}")
        for err in errors:
            print(f"  - HATA: {err}")

    print("=" * 80)
    if all_passed:
        print("[PASS] TUM GUVENLIK POLITIKALARI VE IZOLASYON KONTROLLERI BASARILI.")
        print("=" * 80)
        sys.exit(0)
    else:
        print("[FAIL] KRITIK GUVENLIK IHLALI TESPIT EDILDI!")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

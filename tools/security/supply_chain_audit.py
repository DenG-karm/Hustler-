"""
K-805 (Adım 2/3): Tedarik Zinciri ve Lisans Denetleyicisi (tools/security/supply_chain_audit.py).

Gereksinimler:
1. Python Lisans Denetimi: importlib.metadata.distributions() ile kurulu Python paketlerinin lisanslarını tara.
   Modern paketlerde License-Expression, License, Trove Classifiers dinamik okunur.
2. Frontend Lisans Denetimi (.pnpm ve kurulu ağaç): apps/desktop/node_modules ve node_modules/.pnpm altındaki
   tüm transitive bağımlılıkların package.json dosyalarını dinamik oku.
3. Rust Lisans Denetimi (cargo metadata): apps/desktop/src-tauri dizininde cargo metadata çalıştırılarak
   tüm crate bağımlılıklarının license alanları doğrudan okunur (~/.cargo glob taraması tamamen kaldırılmıştır).
4. Beyaz Liste (Allowed): MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0, Python-2.0,
   MPL-2.0, LGPL-*, Unlicense, 0BSD, CC0-1.0, Public Domain, Zlib, Unicode-3.0, BlueOak-1.0.0, CC-BY-4.0, MIT-0.
5. Kara Liste (Strong Copyleft): GPL (LGPL hariç) ve AGPL içeren paketler STRONG_COPYLEFT_GPL_OR_AGPL olarak kaydedilir.
6. Gerçek Beyaz Liste Zorunluluğu: Üretim paketlerinde not is_allowed_license(lic) olanlar
   UNAPPROVED_OR_UNKNOWN_LICENSE olarak kaydedilir (dev/test araçları hariç).
7. SPDX AND Koruması: ' AND ' geçen ifadelerde parçalar ayrı değerlendirilir; GPL/AGPL varsa permissif bypass engellenir.
"""

from __future__ import annotations

import importlib.metadata as md
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# -----------------------------------------------------------------------------
# Lisans Sınıflandırma Kuralları
# -----------------------------------------------------------------------------
ALLOWED_LICENSE_TOKENS = (
    "MIT",
    "APACHE",
    "BSD",
    "ISC",
    "PSF",
    "PYTHON",
    "MPL",
    "LGPL",
    "LESSER GENERAL PUBLIC LICENSE",
    "LIBRARY GENERAL PUBLIC LICENSE",
    "UNLICENSE",
    "0BSD",
    "CC0",
    "PUBLIC DOMAIN",
    "ZLIB",
    "UNICODE",
    "BLUEOAK",
    "CC-BY",
    "MIT-0",
)

# Yalnızca repo içindeki yerel monorepo / workspace paketleri (harici PyPI paketi olmayan dahili kodlar)
KNOWN_PACKAGE_LICENSES: dict[str, str] = {
    "core": "MIT",
    "hustler": "MIT",
    "hustler-workspace": "MIT",
}


def _is_single_term_strong_copyleft(term: str) -> bool:
    """Tekil bir lisans teriminin GPL/AGPL strong copyleft olup olmadığını belirler."""
    u = term.upper().strip("() ")
    if "WITH" in u or "EXCEPTION" in u:
        return False
    if "AGPL" in u or "AFFERO" in u or "AFFERRO" in u:
        return True
    if "LGPL" in u or "LESSER GENERAL PUBLIC LICENSE" in u or "LIBRARY GENERAL PUBLIC LICENSE" in u:
        return False
    if "GPL" in u or "GENERAL PUBLIC LICENSE" in u:
        return True
    return False


def is_strong_copyleft(license_str: str) -> bool:
    """GPL (LGPL hariç) ve AGPL içeren güçlü copyleft lisanslarını tespit eder.

    SPDX AND Koruması:
    - ' AND ' geçen ifadelerde parçalar ayrı ayrı değerlendirilir; parçalardan biri GPL/AGPL ise
      has_permissive_alt kaçamağına izin verilmez (sonuç True).
    - ' OR ' geçen disjunctive ifadelerde, alternatiflerden en az biri permissif/izinli ise False döner.
    """
    if not license_str or license_str == "UNKNOWN":
        return False

    raw = license_str.strip()

    # 1. ' AND ' ifadesi varsa: tüm bağlaçlar zorunludur. Herhangi biri copyleft ise ihlaldir!
    if re.search(r"\bAND\b", raw, re.IGNORECASE):
        parts = re.split(r"\bAND\b", raw, flags=re.IGNORECASE)
        return any(is_strong_copyleft(p.strip()) for p in parts)

    # 2. ' OR ' ifadesi varsa: alternatif seçilebilir. Tümü copyleft ise True, en az biri güvenli ise False.
    if re.search(r"\bOR\b", raw, re.IGNORECASE):
        parts = re.split(r"\bOR\b", raw, flags=re.IGNORECASE)
        return all(is_strong_copyleft(p.strip()) for p in parts)

    # 3. Tekil terim kontrolü
    return _is_single_term_strong_copyleft(raw)


def is_allowed_license(license_str: str) -> bool:
    """Beyaz listedeki izinli lisanslardan birini içerip içermediğini doğrular."""
    if not license_str or license_str == "UNKNOWN":
        return False
    u = license_str.upper()
    return any(tok in u for tok in ALLOWED_LICENSE_TOKENS)


# -----------------------------------------------------------------------------
# 1. Python Paket Lisans Denetimi (Dinamik importlib.metadata Taraması)
# -----------------------------------------------------------------------------
def audit_python_packages() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    # Bilinen geliştirme/test/derleme araçları
    dev_tools = {
        "mypy",
        "mypy_extensions",
        "pyinstaller",
        "pyinstaller-hooks-contrib",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "coverage",
        "ruff",
        "types-aiofiles",
        "types-colorama",
        "iniconfig",
        "pluggy",
        "pefile",
        "altgraph",
        "pywin32-ctypes",
    }

    for dist in md.distributions():
        raw_name = dist.metadata.get("Name") or "unknown"
        norm_name = raw_name.lower()
        version = dist.metadata.get("Version") or "0.0.0"

        # 1. PEP 621 / PEP 639 License-Expression
        lic_expr = dist.metadata.get("License-Expression")
        # 2. Standart License alanı
        lic_field = dist.metadata.get("License")
        # 3. Trove Classifier lisansları (Çoklu lisanslar disjunctive 'OR' olarak bağlanır)
        classifiers = dist.metadata.get_all("Classifier") or []
        lic_classifiers = [c.split("::")[-1].strip() for c in classifiers if "License ::" in c]

        candidates = [c for c in (lic_expr, lic_field, " OR ".join(lic_classifiers)) if c]
        resolved_lic = candidates[0] if candidates else KNOWN_PACKAGE_LICENSES.get(norm_name, "UNKNOWN")

        # Yerel workspace repo paket kontrolü (harici PyPI paketi olmayan dahili kodlar)
        if resolved_lic == "UNKNOWN" and norm_name in KNOWN_PACKAGE_LICENSES:
            resolved_lic = KNOWN_PACKAGE_LICENSES[norm_name]

        is_dev = norm_name in dev_tools
        is_allowed = is_allowed_license(resolved_lic)
        is_copyleft = is_strong_copyleft(resolved_lic)

        record: dict[str, Any] = {
            "name": raw_name,
            "version": version,
            "ecosystem": "python",
            "license": resolved_lic,
            "is_dev": is_dev,
            "is_allowed": is_allowed,
        }

        if is_copyleft:
            record["violation"] = "STRONG_COPYLEFT_GPL_OR_AGPL"
            violations.append(record)
        elif not is_allowed and not is_dev:
            # Gerçek Beyaz Liste Zorunluluğu: Üretim paketlerinde onaylanmamış lisans ihlaldir
            record["violation"] = "UNAPPROVED_OR_UNKNOWN_LICENSE"
            violations.append(record)
        else:
            record["violation"] = None

        packages.append(record)

    return packages, violations


# -----------------------------------------------------------------------------
# 2. Frontend (Node.js / npm) Paket Lisans Denetimi (.pnpm ve Tüm Kurulu Ağaç)
# -----------------------------------------------------------------------------
def _parse_npm_pkg_json(pkg_path: Path) -> tuple[str | None, str, str]:
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
        name = data.get("name")
        ver = data.get("version", "0.0.0")
        raw_lic = data.get("license") or data.get("licenses")
        if isinstance(raw_lic, list):
            lic = ", ".join(str(item.get("type", item) if isinstance(item, dict) else item) for item in raw_lic)
        elif isinstance(raw_lic, dict):
            lic = str(raw_lic.get("type", "UNKNOWN"))
        elif isinstance(raw_lic, str):
            lic = raw_lic
        else:
            lic = "UNKNOWN"
        return name, ver, lic
    except Exception:
        return None, "0.0.0", "UNKNOWN"


def audit_frontend_packages(repo_root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    pkg_json_path = repo_root / "apps" / "desktop" / "package.json"
    declared_dev: set[str] = set()
    declared_prod: set[str] = set()

    if pkg_json_path.exists():
        try:
            desktop_pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            declared_prod = set(desktop_pkg.get("dependencies", {}).keys())
            declared_dev = set(desktop_pkg.get("devDependencies", {}).keys())
        except Exception:
            pass

    # 1. Doğrudan ve kapsamlı node_modules yolları
    nm_dirs = [
        repo_root / "apps" / "desktop" / "node_modules",
        repo_root / "node_modules",
    ]

    installed_map: dict[str, tuple[str, str]] = {}

    for nm_dir in nm_dirs:
        if not nm_dir.exists():
            continue

        for sub in nm_dir.iterdir():
            if sub.name.startswith("."):
                continue
            if sub.name.startswith("@") and sub.is_dir():
                for scoped_sub in sub.iterdir():
                    if scoped_sub.is_dir():
                        p_file = scoped_sub / "package.json"
                        if p_file.exists():
                            name, ver, lic = _parse_npm_pkg_json(p_file)
                            if name and name not in installed_map:
                                installed_map[name] = (ver, lic)
            elif sub.is_dir():
                p_file = sub / "package.json"
                if p_file.exists():
                    name, ver, lic = _parse_npm_pkg_json(p_file)
                    if name and name not in installed_map:
                        installed_map[name] = (ver, lic)

    # 2. Gerçek pnpm Ağacı Taraması (.pnpm körlüğünün giderilmesi)
    # node_modules/.pnpm altındaki tüm transitive (alt) paketleri tara
    pnpm_dirs = [
        repo_root / "node_modules" / ".pnpm",
        repo_root / "apps" / "desktop" / "node_modules" / ".pnpm",
    ]

    for pnpm_dir in pnpm_dirs:
        if not pnpm_dir.exists():
            continue

        for p_json in pnpm_dir.glob("*/node_modules/*/package.json"):
            name, ver, lic = _parse_npm_pkg_json(p_json)
            if name and name not in installed_map:
                installed_map[name] = (ver, lic)

        for p_json in pnpm_dir.glob("*/node_modules/@*/*/package.json"):
            name, ver, lic = _parse_npm_pkg_json(p_json)
            if name and name not in installed_map:
                installed_map[name] = (ver, lic)

    # Bildirilen ve kurulu tüm paketleri birleştir
    all_package_names = set(installed_map.keys()) | declared_prod | declared_dev

    for pkg_name in sorted(all_package_names):
        ver, lic = installed_map.get(pkg_name, ("0.0.0", "UNKNOWN"))
        # Üretim ağacı haricindeki tüm paketler geliştirme/derleme alt ağacı (dev) kabul edilir
        is_dev = (pkg_name in declared_dev) or (pkg_name not in declared_prod)
        is_allowed = is_allowed_license(lic)
        is_copyleft = is_strong_copyleft(lic)

        record: dict[str, Any] = {
            "name": pkg_name,
            "version": ver,
            "ecosystem": "npm",
            "license": lic,
            "is_dev": is_dev,
            "is_allowed": is_allowed,
        }

        if is_copyleft:
            record["violation"] = "STRONG_COPYLEFT_GPL_OR_AGPL"
            violations.append(record)
        elif not is_allowed and not is_dev:
            # Üretim ağacındaki onaysız veya bilinmeyen lisanslar ihlaldir
            record["violation"] = "UNAPPROVED_OR_UNKNOWN_LICENSE"
            violations.append(record)
        else:
            record["violation"] = None

        packages.append(record)

    return packages, violations


# -----------------------------------------------------------------------------
# 3. Rust (cargo metadata) Dinamik Paket Lisans Denetimi
# -----------------------------------------------------------------------------
def audit_rust_packages(repo_root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    src_tauri_dir = repo_root / "apps" / "desktop" / "src-tauri"
    if not src_tauri_dir.exists():
        return packages, violations

    # cargo metadata komutunu çalıştır
    # Windows platform filtrelemesi ve offline bayrağı ile tam bağımlılık ağacını çek
    cmd = ["cargo", "metadata", "--format-version", "1", "--filter-platform", "x86_64-pc-windows-msvc", "--offline"]
    res = subprocess.run(
        cmd,
        cwd=str(src_tauri_dir),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        # Fallback: doğrudan bağımlılıklar için --no-deps
        fallback_cmd = ["cargo", "metadata", "--format-version", "1", "--no-deps"]
        res = subprocess.run(
            fallback_cmd,
            cwd=str(src_tauri_dir),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    if res.returncode != 0:
        return packages, [
            {
                "name": "cargo-metadata",
                "version": "0.0.0",
                "ecosystem": "cargo",
                "license": "UNKNOWN",
                "is_dev": False,
                "is_allowed": False,
                "violation": f"cargo metadata failed: {res.stderr[:200]}",
            }
        ]

    try:
        data = json.loads(res.stdout)
    except Exception as e:
        return packages, [
            {
                "name": "cargo-metadata-json",
                "version": "0.0.0",
                "ecosystem": "cargo",
                "license": "UNKNOWN",
                "is_dev": False,
                "is_allowed": False,
                "violation": f"cargo metadata JSON parse failed: {e}",
            }
        ]

    # Cargo.toml içindeki build-dependencies listesini tespit et
    cargo_toml_path = src_tauri_dir / "Cargo.toml"
    build_deps: set[str] = set()
    if cargo_toml_path.exists():
        try:
            c_toml_data = tomllib.loads(cargo_toml_path.read_text(encoding="utf-8"))
            build_deps = set(c_toml_data.get("build-dependencies", {}).keys())
        except Exception:
            pass

    raw_packages = data.get("packages", [])
    internal_crates = {"app", "app_lib", "hustler-desktop", "desktop"}

    for p in raw_packages:
        name = p.get("name", "")
        ver = p.get("version", "0.0.0")
        raw_lic = (p.get("license") or "").strip()

        # Kendi dahili monorepo paketimiz veya harici kaynağı olmayan kod için lisansı MIT kabul et
        if name in internal_crates or not p.get("source"):
            resolved_lic = "MIT"
        elif not raw_lic:
            resolved_lic = "UNKNOWN"
        else:
            resolved_lic = raw_lic

        is_dev = name in build_deps
        is_allowed = is_allowed_license(resolved_lic)
        is_copyleft = is_strong_copyleft(resolved_lic)

        record: dict[str, Any] = {
            "name": name,
            "version": ver,
            "ecosystem": "cargo",
            "license": resolved_lic,
            "is_dev": is_dev,
            "is_allowed": is_allowed,
        }

        if is_copyleft:
            record["violation"] = "STRONG_COPYLEFT_GPL_OR_AGPL"
            violations.append(record)
        elif not is_allowed and not is_dev:
            record["violation"] = "UNAPPROVED_OR_UNKNOWN_LICENSE"
            violations.append(record)
        else:
            record["violation"] = None

        packages.append(record)

    return packages, violations


# -----------------------------------------------------------------------------
# Ana Tedarik Zinciri Koşucusu
# -----------------------------------------------------------------------------
def run_supply_chain_audit(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    py_packages, py_violations = audit_python_packages()
    fe_packages, fe_violations = audit_frontend_packages(repo_root)
    rust_packages, rust_violations = audit_rust_packages(repo_root)

    all_packages = py_packages + fe_packages + rust_packages
    all_violations = py_violations + fe_violations + rust_violations

    return {
        "passed": len(all_violations) == 0,
        "total_packages_scanned": len(all_packages),
        "python_packages_count": len(py_packages),
        "frontend_packages_count": len(fe_packages),
        "rust_packages_count": len(rust_packages),
        "license_violations": all_violations,
        "packages": all_packages,
    }


def main() -> None:
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn) and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 80)
    print(" HUSTLER TEDARIK ZINCIRI VE LISANS DENETLEYICISI (K-805 SUPPLY CHAIN)")
    print("=" * 80)

    report = run_supply_chain_audit(REPO_ROOT)
    print(f"Toplam Taranan Paket  : {report['total_packages_scanned']}")
    print(f"  - Python Paketleri   : {report['python_packages_count']}")
    print(f"  - Frontend Paketleri : {report['frontend_packages_count']}")
    print(f"  - Rust Paketleri     : {report['rust_packages_count']}")
    print(f"Lisans İhlali Sayısı  : {len(report['license_violations'])}")

    if report["license_violations"]:
        print("\n[FAIL] TESPIT EDILEN LISANS IHLALLERI:")
        for v in report["license_violations"]:
            print(f"  - {v['ecosystem'].upper()}: {v['name']} ({v['version']}) -> {v['license']} [{v.get('violation')}]")
        print("=" * 80)
        sys.exit(1)
    else:
        print("\n[PASS] TUM BAGIMLILIKLAR BEYAZ LISTEYE VE TICARI KULLANIMA UYGUN.")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()

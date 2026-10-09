"""Test envanteri ve assert-kapısı (AST tabanlı).

Kullanım:
    python tools/ci/check_tests.py --inventory   # tüm test_*.py dosyaları, tablo
    python tools/ci/check_tests.py --gate        # pytest'in topladığı testlerde assert denetimi

Bir test fonksiyonu şunlardan en az birini içeriyorsa "doğrulayıcı" sayılır:
  - assert ifadesi
  - pytest.raises / pytest.warns (çağrı veya with)
  - @given (hypothesis) dekoratörü
  - assert* ile başlayan çağrı (assert_compiles, self.assertEqual ...)

--gate: toplanan testlerden biri bile doğrulayıcı değilse çıkış kodu 1 olur.
Toplanan test = `pytest --collect-only -q` çıktısındaki düğüm kimliği.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".venv", "node_modules", ".git", "target", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}


@dataclass
class TestFn:
    qualname: str
    lineno: int
    asserts: bool


@dataclass
class FileReport:
    path: str
    tests: list[TestFn] = field(default_factory=list)
    parse_error: str = ""

    @property
    def asserting(self) -> int:
        return sum(1 for t in self.tests if t.asserts)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _has_assertion(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for deco in fn.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if _call_name(target) == "given":
            return True
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"raises", "warns"} or name.startswith("assert"):
                return True
    return False


def _collect_tests(tree: ast.Module) -> list[TestFn]:
    found: list[TestFn] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            found.append(TestFn(node.name, node.lineno, _has_assertion(node)))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                    found.append(TestFn(f"{node.name}::{sub.name}", sub.lineno, _has_assertion(sub)))
    return found


def scan() -> list[FileReport]:
    reports: list[FileReport] = []
    for path in sorted(ROOT.rglob("test_*.py")):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        report = FileReport(rel)
        try:
            report.tests = _collect_tests(ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel))
        except (SyntaxError, UnicodeDecodeError) as exc:
            report.parse_error = type(exc).__name__
        reports.append(report)
    return reports


def collected_ids() -> set[str]:
    """pytest'in topladığı testler: 'path::qualname' (parametre eki atılır)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ids: set[str] = set()
    for line in proc.stdout.splitlines():
        if "::" in line and not line.startswith(" "):
            ids.add(re.sub(r"\[.*\]$", "", line.strip()).replace("\\", "/"))
    return ids


def inventory(reports: list[FileReport], collected: set[str]) -> None:
    print(f"{'konum':<52} {'test':>5} {'assertli':>9} {'pytest toplar'}")
    total_t = total_a = 0
    for r in reports:
        picked = sum(1 for t in r.tests if f"{r.path}::{t.qualname}" in collected)
        flag = f"evet ({picked})" if picked else "hayır"
        if r.parse_error:
            flag = f"AST hatası: {r.parse_error}"
        print(f"{r.path:<52} {len(r.tests):>5} {r.asserting:>9} {flag}")
        total_t += len(r.tests)
        total_a += r.asserting
    print(f"{'TOPLAM':<52} {total_t:>5} {total_a:>9} {len(collected)} düğüm toplandı")


def gate(reports: list[FileReport], collected: set[str]) -> int:
    if not collected:
        print("KAPI: pytest hiç test toplamadı.")
        return 1
    bad: list[str] = []
    known = {f"{r.path}::{t.qualname}": t for r in reports for t in r.tests}
    bad.extend(f"{r.path}  (AST ayrıştırma hatası: {r.parse_error})" for r in reports if r.parse_error)
    for node_id in sorted(collected):
        test = known.get(node_id)
        if test is None:
            bad.append(f"{node_id}  (AST'de bulunamadı)")
        elif not test.asserts:
            bad.append(f"{node_id}  (assert / pytest.raises / @given yok)")
    if bad:
        print(f"KAPI BAŞARISIZ: {len(bad)}/{len(collected)} toplanan test doğrulama içermiyor:")
        for line in bad:
            print("  -", line)
        return 1
    print(f"KAPI GEÇTİ: {len(collected)} toplanan testin tümü doğrulama içeriyor.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory", action="store_true")
    mode.add_argument("--gate", action="store_true")
    args = parser.parse_args()

    reports = scan()
    collected = collected_ids()
    if args.inventory:
        inventory(reports, collected)
        return 0
    return gate(reports, collected)


if __name__ == "__main__":
    raise SystemExit(main())

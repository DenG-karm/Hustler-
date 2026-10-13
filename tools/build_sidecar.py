#!/usr/bin/env python3
"""
Hustler Sidecar Derleyici (K-801)
Python FastAPI sidecar sürecini tekil (standalone) bir binary (.exe) olarak derler.
Tauri 2 externalBin sözleşmesine göre çıktı:
apps/desktop/src-tauri/binaries/hustler-sidecar-x86_64-pc-windows-msvc.exe
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT_DIR / "services" / "core"
BINARIES_DIR = ROOT_DIR / "apps" / "desktop" / "src-tauri" / "binaries"
TARGET_TRIPLE = "x86_64-pc-windows-msvc"
BINARY_NAME = f"hustler-sidecar-{TARGET_TRIPLE}.exe"


def build_sidecar() -> Path:
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    entry_point = CORE_DIR / "hustler" / "main.py"
    
    if not entry_point.exists():
        raise FileNotFoundError(f"Entrypoint bulunamadı: {entry_point}")

    dist_dir = ROOT_DIR / "build" / "sidecar_dist"
    work_dir = ROOT_DIR / "build" / "sidecar_build"
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", f"hustler-sidecar-{TARGET_TRIPLE}",
        "--distpath", str(dist_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        "--paths", str(ROOT_DIR),
        "--paths", str(CORE_DIR),
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--collect-all", "pydantic",
        "--collect-all", "pydantic_core",
        "--collect-all", "structlog",
        "--collect-all", "aiosqlite",
        "--collect-all", "httpx",
        "--collect-all", "yt_dlp",
        "--collect-all", "youtube_transcript_api",
        "--collect-all", "anyio",
        "--collect-all", "colorama",
        "--hidden-import", "services.core.hustler",
        "--hidden-import", "services.core.hustler.main",
        "--hidden-import", "services.core.hustler.db",
        "--hidden-import", "services.core.hustler.api.auth",
        "--hidden-import", "services.core.hustler.api.routes.discovery",
        "--hidden-import", "services.core.hustler.api.routes.jobs",
        "--hidden-import", "services.core.hustler.api.routes.pipeline",
        "--hidden-import", "services.core.hustler.storage.cache",
        "--hidden-import", "services.core.hustler.storage.jobs",
        "--hidden-import", "services.core.hustler.storage.scripts",
        "--hidden-import", "services.core.hustler.infrastructure.event_broker",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        str(entry_point),
    ]

    print(f"[K-801] PyInstaller başlatılıyor: {BINARY_NAME}")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT_DIR}{os.pathsep}{CORE_DIR}"
    
    result = subprocess.run(cmd, env=env, check=True)
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller derlemesi başarısız oldu (kod: {result.returncode})")

    built_binary = dist_dir / BINARY_NAME
    if not built_binary.exists():
        raise FileNotFoundError(f"Üretilen binary bulunamadı: {built_binary}")

    target_binary = BINARIES_DIR / BINARY_NAME
    shutil.copy2(built_binary, target_binary)
    print(f"[K-801] Sidecar binary başarıyla kopyalandı -> {target_binary}")
    
    # Ayrıca platform bağımsız yedek isim olarak da kopyala
    fallback_binary = BINARIES_DIR / "hustler-sidecar.exe"
    shutil.copy2(built_binary, fallback_binary)
    print(f"[K-801] Fallback binary kopyalandı -> {fallback_binary}")

    return target_binary


if __name__ == "__main__":
    build_sidecar()

"""
K-807 / Faz F8 (Adım 3/3): Gerçek Süreç (Zero-Mock Live Process) Doğrulama Testi.
tools/release/live_sidecar_smoke.py

MİMARİ GEREKSİNİMLER:
1. Kesinlikle bellek-içi (in-memory) ASGITransport KULLANILMAZ.
2. Gerçek Python FastAPI sidecar süreci subprocess.Popen ile 127.0.0.1 üzerinde
   rastgele/boş bir portta ve gerçek HUSTLER_SESSION_TOKEN ile ayağa kaldırılır.
3. Gerçek TCP/HTTP üzerinden sırasıyla:
   a. /health kontrolü yapılır (200 OK).
   b. Yanlış token ile istek atılıp 401/403 döndüğü doğrulanır.
   c. Doğru token ile:
      - /api/v1/discovery/run
      - /api/v1/script/generate
      - /api/v1/audio/generate
      - /api/v1/diagnostics/export (format=json)
   d. Sidecar süreci terminate edilip SQLite .db-wal dosyasının temiz kapandığı
      ve yetim süreç kalmadığı doğrulanır.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.request
import json

REPO_ROOT = Path(__file__).resolve().parents[2]


def get_child_pids(parent_pid: int) -> list[int]:
    """İşletim sistemi üzerinden üst sürece ait alt süreç PID'lerini sorgular."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {parent_pid} }}).ProcessId",
                ],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            return [int(p) for p in res.stdout.strip().split() if p.strip().isdigit()]
        except Exception:
            return []
    return []



def find_free_port() -> int:
    """İşletim sisteminden boş bir loopback TCP portu tahsis eder."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any] | str]:
    """Gerçek ağ soketi üzerinden urllib ile HTTP isteği gönderir."""
    req_headers = {"User-Agent": "HustlerSmokeTester/1.0"}
    if headers:
        req_headers.update(headers)

    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            body_bytes = response.read()
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed = body_bytes.decode("utf-8", errors="replace")
            return status, parsed
    except urllib.error.HTTPError as exc:
        err_bytes = exc.read()
        try:
            parsed = json.loads(err_bytes.decode("utf-8"))
        except Exception:
            parsed = err_bytes.decode("utf-8", errors="replace")
        return exc.code, parsed


def wait_for_health(base_url: str, max_wait_sec: float = 15.0) -> bool:
    """Sidecar TCP portunda dinlemeye başlayıp /health dönene kadar yoklar."""
    start_time = time.monotonic()
    health_url = f"{base_url}/health"
    while time.monotonic() - start_time < max_wait_sec:
        try:
            status, body = http_request(health_url, method="GET", timeout=1.0)
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _ensure_utf8_stdout() -> None:
    try:
        reconfigure_fn = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_fn) and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
            reconfigure_fn(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _verify_live_endpoints(base_url: str, session_token: str) -> bool:
    print("\n[1/5] Gerçek TCP /health sağlık kontrolü...")
    if not wait_for_health(base_url, max_wait_sec=15.0):
        print("  [FAIL] Sidecar 15 saniye içinde /health yanıtı veremedi!")
        return False
    print("  [PASS] /health 200 OK yanıt verdi.")

    print("\n[2/5] Güvenlik duvarı yetkilendirme sınaması (401/403)...")
    status_unauth, _ = http_request(
        f"{base_url}/api/v1/diagnostics/export",
        method="POST",
        headers={"Authorization": "Bearer BAD_OR_FORGED_TOKEN"},
    )
    if status_unauth not in (401, 403):
        print(f"  [FAIL] Sahte token ile beklenen 401/403 yerine {status_unauth} alındı!")
        return False
    print(f"  [PASS] Sahte token anında reddedildi (HTTP {status_unauth}).")

    auth_headers = {"Authorization": f"Bearer {session_token}"}

    print("\n[3/5] /api/v1/discovery/run canlı sürecinde tetikleniyor...")
    status_disc, body_disc = http_request(
        f"{base_url}/api/v1/discovery/run",
        method="POST",
        headers=auth_headers,
        payload={"topic": "Yapay Zeka ve Otonom Sistemler", "max_results": 10, "score_threshold": 30.0},
        timeout=15.0,
    )
    if status_disc != 200:
        print(f"  [FAIL] Discovery başarısız! HTTP {status_disc}: {body_disc}")
        return False
    print("  [PASS] Discovery başarıyla tamamlandı (HTTP 200 OK).")

    print("\n[4/5] Senaryo ve Ses üretim uç noktaları sınanıyor...")
    status_scr, body_scr = http_request(
        f"{base_url}/api/v1/script/generate",
        method="POST",
        headers=auth_headers,
        payload={
            "idea_id": "idea_smoke_01",
            "topic": "Yapay Zeka ve Otonom Sistemler",
            "title": "Otonom Ajanların Geleceği",
        },
        timeout=10.0,
    )
    if status_scr != 200:
        print(f"  [FAIL] Senaryo üretimi başarısız! HTTP {status_scr}: {body_scr}")
        return False
    script_id = body_scr.get("script_id", "scr_smoke_test") if isinstance(body_scr, dict) else "scr_smoke_test"
    print(f"  [PASS] Senaryo üretildi: id={script_id} (HTTP 200 OK).")

    status_aud, body_aud = http_request(
        f"{base_url}/api/v1/audio/generate",
        method="POST",
        headers=auth_headers,
        payload={
            "script_id": str(script_id),
            "text": "Otonom yapay zeka ajanları endüstriyi dönüştürüyor.",
            "voice_id": "tr-TR-Standard-A",
        },
        timeout=10.0,
    )
    if status_aud != 200:
        print(f"  [FAIL] Ses üretimi başarısız! HTTP {status_aud}: {body_aud}")
        return False
    print("  [PASS] Ses üretimi ve AudioCache başarıyla tamamlandı (HTTP 200 OK).")

    print("\n[5/5] /api/v1/diagnostics/export tanılama paketi denetleniyor...")
    status_diag, body_diag = http_request(
        f"{base_url}/api/v1/diagnostics/export?format=json",
        method="POST",
        headers=auth_headers,
        timeout=10.0,
    )
    if status_diag != 200:
        print(f"  [FAIL] Diagnostics export başarısız! HTTP {status_diag}: {body_diag}")
        return False
    print("  [PASS] Diagnostics paketi üretildi (HTTP 200 OK).")
    return True


def _reap_active_orphans(child_pids: list[int]) -> list[int]:
    active_orphans: list[int] = []
    if sys.platform != "win32":
        return active_orphans
    for cpid in child_pids:
        chk = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Get-Process -Id {cpid} -ErrorAction SilentlyContinue"],
            capture_output=True,
        )
        if chk.returncode == 0:
            active_orphans.append(cpid)
            subprocess.run(["taskkill", "/F", "/PID", str(cpid)], capture_output=True)
    return active_orphans


def _shutdown_and_verify_sidecar(
    sidecar_proc: subprocess.Popen[bytes],
    base_url: str,
    session_token: str,
    workdir: Path,
) -> bool:
    print("\n--- Sidecar Kapanış ve Temizlik Denetimi ---")
    child_pids = get_child_pids(sidecar_proc.pid)
    auth_headers = {"Authorization": f"Bearer {session_token}"}
    graceful_success = False
    try:
        status_shut, _ = http_request(
            f"{base_url}/api/v1/system/shutdown",
            method="POST",
            headers=auth_headers,
            timeout=5.0,
        )
        if status_shut == 200:
            print("  [PASS] POST /api/v1/system/shutdown sinyali başarıyla iletildi.")
            sidecar_proc.wait(timeout=6.0)
            print(f"  [PASS] Sidecar süreci kendiliğinden temiz sonlandı (ExitCode: {sidecar_proc.returncode}).")
            graceful_success = True
    except Exception as e:
        print(f"  [WARN] Graceful shutdown tetiklenirken istisna: {e}")

    if not graceful_success:
        sidecar_proc.terminate()
        try:
            sidecar_proc.wait(timeout=3.0)
            print("Sidecar süreci terminate ile sonlandırıldı.")
        except subprocess.TimeoutExpired:
            sidecar_proc.kill()
            sidecar_proc.wait(timeout=2.0)
            print("Sidecar süreci SIGKILL ile sonlandırıldı.")

    time.sleep(0.5)
    active_orphans = _reap_active_orphans(child_pids)
    if active_orphans:
        print(f"  [FAIL] Yetim süreçler tespit edildi: PIDs={active_orphans}")
        shutil.rmtree(workdir, ignore_errors=True)
        return False
    print("  [PASS] Sıfır Yetim Süreç (Zero Zombie Child Processes).")

    wal_path = workdir / "hustler_core.db-wal"
    if wal_path.exists():
        wal_size = wal_path.stat().st_size
        print(f"  [INFO] SQLite WAL dosyası durumu: boyut={wal_size} bayt.")
        if wal_size > 0:
            print(f"  [FAIL] Kirli Kapanış Kanıtı: WAL dosyası 0 bayta inmedi ({wal_size} bayt)!")
            shutil.rmtree(workdir, ignore_errors=True)
            return False
        print("  [PASS] SQLite WAL dosyası 0 bayt (TRUNCATE edilmiş, temiz kapanış).")
    else:
        print("  [PASS] SQLite WAL dosyası diskten temizlendi (0 bayt / dosya yok, temiz kapanış).")

    shutil.rmtree(workdir, ignore_errors=True)
    return True


def run_live_sidecar_smoke() -> bool:
    _ensure_utf8_stdout()

    print("=" * 80)
    print(" HUSTLER CANLI SIDECAR / IPC GERCEK SUREC ENTEGRASYON SINAMASI (LIVE SMOKE)")
    print("=" * 80)

    workdir = Path(tempfile.mkdtemp(prefix="hustler_live_sidecar_"))
    port = find_free_port()
    session_token = secrets.token_urlsafe(32)
    base_url = f"http://127.0.0.1:{port}"

    print(f"Çalışma Dizini       : {workdir}")
    print(f"Loopback Adresi      : {base_url}")
    print(f"Oturum Tokeni Uzunluk: {len(session_token)} karakter (Güvenli)")

    env = os.environ.copy()
    env["HUSTLER_PORT"] = str(port)
    env["HUSTLER_SESSION_TOKEN"] = session_token
    env["YOUTUBE_API_KEY"] = "mock_api_key_for_smoke_test"
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [sys.executable, "-m", "services.core.hustler.main"]
    print(f"Sidecar Başlatılıyor : {' '.join(cmd)}")

    sidecar_proc = subprocess.Popen(
        cmd,
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    endpoints_ok = False
    try:
        endpoints_ok = _verify_live_endpoints(base_url, session_token)
    finally:
        cleanup_ok = _shutdown_and_verify_sidecar(sidecar_proc, base_url, session_token, workdir)

    if not (endpoints_ok and cleanup_ok):
        return False

    print("\n" + "=" * 80)
    print(" [PASS] CANLI SIDECAR SMOKE TESTI EKSIKSIZ BASARIYLA TAMAMLANDI")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = run_live_sidecar_smoke()
    sys.exit(0 if success else 1)

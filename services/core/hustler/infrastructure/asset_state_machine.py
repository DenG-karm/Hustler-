"""M6 K-609: Asset State Machine (Varlık Durum Makinesi) ve Güvenli I/O.

Yavaş kopyalama (slow-copy), ağ gecikmesi veya eksik indirme kaynaklı
FFmpeg çökmelerine karşı sıfır toleransla varlık dosyalarının diske yazılma
ve doğrulanma süreçlerini yönetir.

Katı Durum Akışı:
CANDIDATE -> STABILIZING -> VERIFYING -> READY (veya FAILED)
"""

from __future__ import annotations

import asyncio
from enum import Enum
import hashlib
import json
from pathlib import Path
import structlog
from typing import Optional

logger = structlog.get_logger()


class AssetState(str, Enum):
    """Varlık yaşam döngüsü durumları."""
    CANDIDATE = "CANDIDATE"      # Dosya adayı tespit edildi
    STABILIZING = "STABILIZING"  # Yazım/kopyalama sürüyor, boyut stabilizasyonu izleniyor
    VERIFYING = "VERIFYING"      # Bütünlük ve medya başlık kontrolü yapılıyor
    READY = "READY"              # Doğrulandı, FFmpeg ve derleyici için güvenli
    FAILED = "FAILED"            # Bozuk, zaman aşımı veya geçersiz dosya


ALLOWED_TRANSITIONS: dict[AssetState, set[AssetState]] = {
    AssetState.CANDIDATE: {AssetState.STABILIZING, AssetState.FAILED},
    AssetState.STABILIZING: {AssetState.VERIFYING, AssetState.FAILED},
    AssetState.VERIFYING: {AssetState.READY, AssetState.FAILED},
    AssetState.READY: set(),
    AssetState.FAILED: set(),
}


class AssetStateMachineError(Exception):
    """AssetStateMachine genel istisna tabanı."""
    pass


class InvalidStateTransitionError(AssetStateMachineError):
    """Geçersiz veya kural dışı durum geçişi hatası."""
    pass


class StabilizationTimeoutError(AssetStateMachineError, TimeoutError):
    """Yavaş kopyalama veya stabilizasyon zaman aşımı hatası."""
    pass


class IntegrityVerificationError(AssetStateMachineError):
    """Bütünlük veya hash doğrulama hatası."""
    pass


class CorruptFileError(IntegrityVerificationError):
    """Bozuk medya başlığı veya okunamayan dosya hatası."""
    pass


def _check_file_accessible(path: Path) -> tuple[bool, int]:
    """Dosyanın erişilebilirliğini (lock/sharing) ve boyutunu senkron kontrol eder (thread içinde koşulur)."""
    if not path.is_file():
        return False, 0
    try:
        size = path.stat().st_size
        # Okuma amaçlı açmayı dene (Windows paylaşım ihlali kontrolü)
        with open(path, "rb") as f:
            # En az 1 bayt veya EOF oku
            _ = f.read(1)
        return True, size
    except (OSError, PermissionError):
        return False, 0


def _calculate_sha256(path: Path) -> str:
    """Dosyanın SHA-256 özetini hesaplar (thread içinde koşulur)."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class AssetStateMachine:
    """Deterministik ve güvenli I/O sağlayan Varlık Durum Makinesi."""

    def __init__(
        self,
        file_path: str | Path,
        expected_sha256: Optional[str] = None,
        check_interval_sec: float = 0.5,
        stable_count_threshold: int = 3,
        stabilize_timeout_sec: float = 30.0,
        verify_timeout_sec: float = 10.0,
        cleanup_on_failure: bool = True,
    ) -> None:
        self.file_path = Path(file_path)
        self.expected_sha256 = expected_sha256.lower() if expected_sha256 else None
        self.check_interval_sec = check_interval_sec
        self.stable_count_threshold = stable_count_threshold
        self.stabilize_timeout_sec = stabilize_timeout_sec
        self.verify_timeout_sec = verify_timeout_sec
        self.cleanup_on_failure = cleanup_on_failure

        self._state: AssetState = AssetState.CANDIDATE
        self._lock = asyncio.Lock()
        self._history: list[tuple[AssetState, str]] = [(AssetState.CANDIDATE, "Başlatıldı")]

    @property
    def state(self) -> AssetState:
        """Geçerli durumu döner."""
        return self._state

    @property
    def history(self) -> list[tuple[AssetState, str]]:
        """Durum geçiş geçmişini döner."""
        return list(self._history)

    async def transition_to(self, new_state: AssetState, reason: str = "") -> None:
        """Atomik ve kural denetimli durum geçişi yapar."""
        async with self._lock:
            allowed = ALLOWED_TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                err_msg = (
                    f"Geçersiz durum geçişi: {self._state.value} -> {new_state.value}. "
                    f"İzin verilen sonraki durumlar: {[s.value for s in allowed]}"
                )
                logger.error("Invalid state transition attempt",
                             current_state=self._state.value,
                             target_state=new_state.value,
                             reason=reason)
                raise InvalidStateTransitionError(err_msg)

            self._state = new_state
            self._history.append((new_state, reason))
            logger.info("Asset state transition",
                        file=str(self.file_path),
                        new_state=new_state.value,
                        reason=reason)

    async def stabilize(self) -> None:
        """STABILIZING aşaması: Yavaş kopyalama (Slow-Copy) koruması.

        Dosya boyutunu event loop'u bloklamadan check_interval_sec aralıklarla
        kontrol eder. Boyut art arda stable_count_threshold kez sabit kalmadan
        ve dosya kilidi çözülmeden tamamlanmış saymaz.
        """
        await self.transition_to(AssetState.STABILIZING, "Yazım stabilizasyonu izleniyor")

        consecutive_stable = 0
        last_size = -1

        loop = asyncio.get_running_loop()
        start_time = loop.time()

        while True:
            elapsed = loop.time() - start_time
            if elapsed > self.stabilize_timeout_sec:
                await self._handle_failure(
                    f"Dosya stabilizasyonu {self.stabilize_timeout_sec}s limitini aştı."
                )
                raise StabilizationTimeoutError(
                    f"Stabilizasyon zaman aşımına uğradı ({self.file_path})"
                )

            accessible, current_size = await asyncio.to_thread(
                _check_file_accessible, self.file_path
            )

            if accessible and current_size > 0:
                if current_size == last_size:
                    consecutive_stable += 1
                else:
                    consecutive_stable = 1
                    last_size = current_size

                if consecutive_stable >= self.stable_count_threshold:
                    logger.info("Dosya boyutu kararlı duruma ulaştı",
                                file=str(self.file_path),
                                final_size=current_size,
                                stable_checks=consecutive_stable)
                    return
            else:
                consecutive_stable = 0
                last_size = -1

            await asyncio.sleep(self.check_interval_sec)

    async def verify(self) -> None:
        """VERIFYING aşaması: Bütünlük ve medya başlık doğrulaması.

        ffprobe alt süreci ile başlık ve akış geçerliliğini test eder.
        Varsa beklenen SHA-256 özetiyle karşılaştırır.
        """
        await self.transition_to(AssetState.VERIFYING, "Bütünlük doğrulaması başlatıldı")

        if not self.file_path.is_file():
            await self._handle_failure("Doğrulanacak dosya diskte bulunamadı.")
            raise CorruptFileError(f"Dosya mevcut değil: {self.file_path}")

        # 1. SHA-256 Kontrolü (Opsiyonel)
        if self.expected_sha256:
            actual_sha = await asyncio.to_thread(_calculate_sha256, self.file_path)
            if actual_sha.lower() != self.expected_sha256:
                await self._handle_failure(
                    f"SHA-256 uyuşmazlığı: Beklenen {self.expected_sha256}, bulunan {actual_sha}"
                )
                raise IntegrityVerificationError(
                    f"Dosya hash uyuşmazlığı ({self.file_path})"
                )

        # 2. ffprobe Medya Bütünlük Kontrolü
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=format_name,duration:stream=codec_name",
            "-of", "json",
            str(self.file_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.verify_timeout_sec,
            )
        except asyncio.TimeoutError:
            await self._handle_failure("ffprobe doğrulama zaman aşımına uğradı.")
            raise StabilizationTimeoutError("ffprobe zaman aşımı")
        except Exception as exc:
            await self._handle_failure(f"ffprobe çalıştırılamadı: {exc}")
            raise CorruptFileError(f"ffprobe hatası: {exc}") from exc

        if proc.returncode != 0:
            err_msg = stderr_b.decode(errors="replace").strip()
            await self._handle_failure(f"Bozuk dosya (ffprobe çıkış kodu {proc.returncode}): {err_msg}")
            raise CorruptFileError(f"Bozuk medya dosyası ({self.file_path}): {err_msg}")

        # JSON çıktısını doğrula
        try:
            data = json.loads(stdout_b.decode(errors="replace"))
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            if not streams and not fmt:
                await self._handle_failure("ffprobe hiçbir akış veya format okuyamadı.")
                raise CorruptFileError(f"Geçersiz medya formatı ({self.file_path})")
        except Exception as exc:
            await self._handle_failure(f"ffprobe çıktısı ayrıştırılamadı: {exc}")
            raise CorruptFileError(f"Ayrıştırma hatası: {exc}") from exc

        # Başarıyla doğrulandı -> READY
        await self.transition_to(AssetState.READY, "Doğrulama başarılı, varlık hazır")

    async def _handle_failure(self, reason: str) -> None:
        """Hata durumunda FAILED durumuna çeker ve gerekiyorsa zombi dosyayı temizler."""
        if self._state != AssetState.FAILED:
            try:
                await self.transition_to(AssetState.FAILED, reason)
            except InvalidStateTransitionError:
                pass

        if self.cleanup_on_failure and self.file_path.exists():
            try:
                self.file_path.unlink()
                logger.info("Zombi/yarım dosya silindi (Garbage Collection)",
                            file=str(self.file_path), reason=reason)
            except OSError as exc:
                logger.warning("Hatalı dosya silinemedi",
                               file=str(self.file_path), error=str(exc))

    async def process(self) -> Path:
        """Varlığı CANDIDATE -> STABILIZING -> VERIFYING -> READY sürecinden geçirir."""
        try:
            await self.stabilize()
            await self.verify()
            return self.file_path
        except Exception:
            # transition_to(FAILED) zaten stabilize/verify içinde veya _handle_failure'da çağrılır
            if self._state != AssetState.FAILED:
                await self._handle_failure("İşlem sırasında beklenmeyen hata oluştu")
            raise

    def copy_to(self, target_path: str | Path) -> Path:
        """Doğrulanmış (READY) varlığı hedef klasöre izole eder."""
        if self._state != AssetState.READY:
            raise AssetStateMachineError(
                f"Yalnızca READY durumundaki varlıklar kopyalanabilir (Geçerli: {self._state.value})"
            )
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(self.file_path, target)
        return target

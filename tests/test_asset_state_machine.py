"""M6 K-609: AssetStateMachine Birim ve Güvenli I/O Entegrasyon Testleri.

Yavaş kopyalama (slow-copy), katı durum geçişleri, bozuk dosya reddi (corrupt file),
ve timeout garbage collection mekanizmalarını test eder.
"""

import asyncio
from pathlib import Path
import pytest

from services.core.hustler.infrastructure.asset_state_machine import (
    AssetState,
    AssetStateMachine,
    CorruptFileError,
    IntegrityVerificationError,
    InvalidStateTransitionError,
    StabilizationTimeoutError,
)
from services.core.hustler.render.test_profile import (
    generate_synthetic_video_asset,
)


@pytest.mark.asyncio
async def test_strict_transitions_prevent_skipping(tmp_path: Path) -> None:
    """CANDIDATE durumundan doğrudan READY veya VERIFYING'e atlamanın engellendiğini doğrular."""
    file_path = tmp_path / "test.mp4"
    file_path.write_bytes(b"data")

    fsm = AssetStateMachine(file_path)
    assert fsm.state == AssetState.CANDIDATE

    # Doğrudan READY'e geçiş yasaktır
    with pytest.raises(InvalidStateTransitionError, match="Geçersiz durum geçişi"):
        await fsm.transition_to(AssetState.READY)

    # Doğrudan VERIFYING'e geçiş yasaktır
    with pytest.raises(InvalidStateTransitionError, match="Geçersiz durum geçişi"):
        await fsm.transition_to(AssetState.VERIFYING)

    # Sadece STABILIZING veya FAILED'a geçebilir
    await fsm.transition_to(AssetState.STABILIZING)
    assert fsm.state == AssetState.STABILIZING


@pytest.mark.asyncio
async def test_slow_copy_safeguard(tmp_path: Path) -> None:
    """5 saniye boyunca parça parça yazılan dosyanın çökmeden ve tam boyuta ulaşana kadar beklendiğini ispatlar."""
    target_file = tmp_path / "slow_copy_stream.bin"
    chunk_size = 1024
    total_chunks = 10
    write_interval = 0.5  # 10 * 0.5s = 5 saniye boyunca yazım sürecek

    async def slow_writer() -> None:
        """Dosyayı 5 saniye boyunca aralıklarla yavaşça yazar."""
        for i in range(total_chunks):
            await asyncio.sleep(write_interval)
            with open(target_file, "ab") as f:
                f.write(b"X" * chunk_size)

    fsm = AssetStateMachine(
        target_file,
        check_interval_sec=0.25,
        stable_count_threshold=3,
        stabilize_timeout_sec=15.0,
    )

    t0 = asyncio.get_running_loop().time()

    # Writer ve Stabilizer eşzamanlı çalışır
    writer_task = asyncio.create_task(slow_writer())
    stabilize_task = asyncio.create_task(fsm.stabilize())

    await asyncio.gather(writer_task, stabilize_task)
    elapsed = asyncio.get_running_loop().time() - t0

    # En az 5 saniye beklemiş olmalı (çünkü yazım 5 saniye sürdü)
    assert elapsed >= 4.8, f"Stabilize çok erken tamamlandı ({elapsed:.2f} sn)"
    assert fsm.state == AssetState.STABILIZING
    assert target_file.stat().st_size == total_chunks * chunk_size


@pytest.mark.asyncio
async def test_corrupt_file_rejected(tmp_path: Path) -> None:
    """Header'ı bozuk veya eksik dosyanın VERIFYING aşamasında yakalanıp FAILED olduğunu gösterir."""
    corrupt_file = tmp_path / "corrupt_video.mp4"
    # Bozuk, geçersiz binary içerik
    corrupt_file.write_bytes(b"INVALID_HEADER_GARBAGE_BYTES_XYZ_1234567890" * 10)

    fsm = AssetStateMachine(
        corrupt_file,
        check_interval_sec=0.1,
        stable_count_threshold=2,
        cleanup_on_failure=True,
    )

    await fsm.stabilize()
    assert fsm.state == AssetState.STABILIZING

    # Bütünlük denetiminde ffprobe dosyayı reddetmeli
    with pytest.raises(CorruptFileError, match="Bozuk medya dosyası"):
        await fsm.verify()

    assert fsm.state == AssetState.FAILED
    # cleanup_on_failure=True olduğundan bozuk dosya diskten temizlenmiş olmalıdır
    assert not corrupt_file.exists(), "Bozuk dosya silinmedi (zombi dosya kaldı)!"


@pytest.mark.asyncio
async def test_timeout_cancels_and_cleans_up_zombie_file(tmp_path: Path) -> None:
    """Stabilizasyon süresi aşıldığında TimeoutError fırlatıldığını ve zombi dosyanın silindiğini doğrular."""
    incomplete_file = tmp_path / "hanging_upload.part"
    incomplete_file.write_bytes(b"partial_data")

    # Çok kısa bir timeout ile fsm çalıştır
    fsm = AssetStateMachine(
        incomplete_file,
        check_interval_sec=0.1,
        stable_count_threshold=100,  # Asla 100 kontrole ulaşamayacak
        stabilize_timeout_sec=0.3,   # 300 ms sonra zaman aşımı
        cleanup_on_failure=True,
    )

    with pytest.raises(StabilizationTimeoutError):
        await fsm.stabilize()

    assert fsm.state == AssetState.FAILED
    assert not incomplete_file.exists(), "Zaman aşımına uğrayan dosya temizlenmedi!"


@pytest.mark.asyncio
async def test_hash_mismatch_fails_verification(tmp_path: Path) -> None:
    """Beklenen SHA-256 hash ile dosya özeti eşleşmediğinde doğrulamadan geçemez."""
    valid_file = tmp_path / "file.mp4"
    valid_file.write_bytes(b"sample_content")

    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    fsm = AssetStateMachine(
        valid_file,
        expected_sha256=wrong_hash,
        check_interval_sec=0.1,
        stable_count_threshold=2,
        cleanup_on_failure=False,
    )

    await fsm.stabilize()
    with pytest.raises(IntegrityVerificationError, match="hash uyuşmazlığı"):
        await fsm.verify()

    assert fsm.state == AssetState.FAILED


@pytest.mark.asyncio
async def test_valid_media_process_end_to_end_reaches_ready(tmp_path: Path) -> None:
    """Geçerli bir medya dosyasının CANDIDATE -> READY döngüsünü başarıyla tamamladığını doğrular."""
    real_video = Path(generate_synthetic_video_asset(tmp_path / "valid.mp4", duration_sec=1.0))

    fsm = AssetStateMachine(
        real_video,
        check_interval_sec=0.1,
        stable_count_threshold=2,
    )

    result_path = await fsm.process()
    assert result_path == real_video
    assert fsm.state == AssetState.READY

    # Hedefe izole kopyalama testi
    isolated = tmp_path / "isolated" / "ready.mp4"
    copied = fsm.copy_to(isolated)
    assert copied.is_file()
    assert copied.stat().st_size == real_video.stat().st_size

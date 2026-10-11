"""M6 K-608: Altın Dosya (Golden File) ve Snapshot Altyapısı Entegrasyon Testleri.

Deterministik CPU profili ile render alınır, SSIM (Structural Similarity)
ile kare/piksel bazında regresyon karşılaştırması yapılır.
"""

from pathlib import Path
import shutil
import subprocess
import pytest

from services.core.hustler.domain.models.template import (
    RenderConfig,
    SafeZone,
    TemplateSpec,
)
from services.core.hustler.render.test_profile import (
    generate_synthetic_audio_asset,
    generate_synthetic_subtitles,
    generate_synthetic_video_asset,
    render_test_template,
)
from services.core.hustler.render.video_diff import (
    assert_video_matches,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURES_DIR / "golden"
GOLDEN_MOTIVATION_PATH = GOLDEN_DIR / "motivation_shorts_golden.mp4"


def make_motivation_template() -> TemplateSpec:
    """Motivasyon Shorts Taslak Şablonu."""
    zone = SafeZone(margin_top=150, margin_bottom=250, margin_left=60, margin_right=60)
    return TemplateSpec(
        name="Motivasyon Shorts Şablonu",
        target_duration_sec=30,
        max_scenes=3,
        allowed_tones=["ilham verici", "heyecanlı", "didaktik"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=zone,
        ),
    )


def test_identical_videos_pass_ssim(tmp_path: Path) -> None:
    """Aynı iki video için SSIM skorunun 1.0 olduğunu ve testin geçtiğini doğrular."""
    v1 = generate_synthetic_video_asset(tmp_path / "v1.mp4", duration_sec=1.0)
    v2 = generate_synthetic_video_asset(tmp_path / "v2.mp4", duration_sec=1.0)

    result = assert_video_matches(v1, v2, min_ssim=0.99)
    assert result.overall_ssim >= 0.999
    assert len(result.failed_frames) == 0


def test_deviating_video_fails_with_exact_frame_and_second(tmp_path: Path) -> None:
    """Görsel sapma olduğunda assert_video_matches'in hangi karede ve saniyede hata olduğunu belirttiğini doğrular."""
    # Referans video: kırmızı arka plan (1 sn = 30 kare)
    ref = generate_synthetic_video_asset(
        tmp_path / "ref.mp4", duration_sec=1.0, color="red"
    )
    # Farklı video: mavi arka plan (1 sn = 30 kare)
    diff = generate_synthetic_video_asset(
        tmp_path / "diff.mp4", duration_sec=1.0, color="blue"
    )

    with pytest.raises(AssertionError) as exc_info:
        assert_video_matches(diff, ref, min_ssim=0.99)

    err = str(exc_info.value)
    assert "Altın Dosya Görsel Regresyon Hatası" in err
    assert "Genel SSIM Skoru" in err
    assert "Kare #1" in err  # İlk kareden itibaren sapma var
    assert "0.00 sn" in err
    assert "Eşik Altı Kare Sayısı: 30" in err
    assert "--update-snapshots" in err


def test_partial_temporal_deviation_pinpoints_exact_second(tmp_path: Path) -> None:
    """İlk yarısı aynı, ikinci yarısında sapma başlayan videoda ilk sapma karesini ve saniyesini net tespit eder."""
    # ref: 1 saniye (30 kare) boyunca kırmızı
    ref = generate_synthetic_video_asset(
        tmp_path / "ref_full.mp4", duration_sec=1.0, color="red"
    )

    # diff: 0.5 saniye (15 kare) kırmızı, ardından 0.5 saniye (15 kare) mavi
    part1 = generate_synthetic_video_asset(
        tmp_path / "part1.mp4", duration_sec=0.5, color="red"
    )
    part2 = generate_synthetic_video_asset(
        tmp_path / "part2.mp4", duration_sec=0.5, color="blue"
    )
    diff_path = tmp_path / "mixed.mp4"

    # concat ile birleştir
    concat_cmd = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner",
        "-i", str(part1), "-i", str(part2),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
        "-map", "[outv]",
        "-c:v", "libx264", "-crf", "0", "-preset", "ultrafast",
        str(diff_path),
    ]
    subprocess.run(concat_cmd, check=True)

    with pytest.raises(AssertionError) as exc_info:
        assert_video_matches(diff_path, ref, min_ssim=0.99)

    err = str(exc_info.value)
    # İlk 15 kare kırmızı olduğu için eşleşir, sapma 16. karede (~0.50 sn) başlar
    assert "Kare #16" in err
    assert "0.50 sn" in err


def test_missing_golden_file_raises_clear_error(tmp_path: Path) -> None:
    """Altın dosya bulunamadığında geliştiriciye --update-snapshots bayrağını hatırlatan açık hata verir."""
    v1 = generate_synthetic_video_asset(tmp_path / "v1.mp4", duration_sec=1.0)
    non_existent = tmp_path / "non_existent_golden.mp4"

    with pytest.raises(FileNotFoundError, match="--update-snapshots"):
        assert_video_matches(v1, non_existent, min_ssim=0.99)


@pytest.mark.asyncio
async def test_template_golden_file_regression(
    tmp_path: Path,
    update_snapshots: bool,
) -> None:
    """Mevcut taslak şablon için referans render üretir ve görsel regresyonu test eder."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    template = make_motivation_template()
    clip_path = generate_synthetic_video_asset(tmp_path / "clip.mp4", duration_sec=2.0)
    audio_path = generate_synthetic_audio_asset(tmp_path / "audio.mp3", duration_sec=2.0)
    sub_path = generate_synthetic_subtitles(tmp_path / "subs.ass")

    rendered_output = tmp_path / "test_render.mp4"

    await render_test_template(
        template=template,
        audio_path=audio_path,
        ass_path=sub_path,
        assets=[clip_path],
        output_path=str(rendered_output),
        duration_sec=2.0,
    )

    assert rendered_output.is_file(), "Render çıktısı oluşturulamadı!"

    if update_snapshots or not GOLDEN_MOTIVATION_PATH.is_file():
        # Snapshot güncelleme modu (veya henüz ilk kez üretiliyorsa):
        shutil.copy2(rendered_output, GOLDEN_MOTIVATION_PATH)
        assert GOLDEN_MOTIVATION_PATH.is_file(), "Altın dosya kaydedilemedi!"

    # Mevcut render ile Altın Dosyayı karşılaştır
    result = assert_video_matches(
        test_render_path=rendered_output,
        golden_path=GOLDEN_MOTIVATION_PATH,
        min_ssim=0.99,
    )
    assert result.overall_ssim >= 0.99

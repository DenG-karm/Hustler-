"""M6 K-610: Slot Eşleme, Tip ve Oran Doğrulama Altyapısı (SlotValidator).

Katı Kurallar ve Güvenlik İlkeleri:
1. Katı Slot ve Tip Eşleme:
   - Zorunlu slot eksikse -> MissingAssetSlotError
   - Slotun beklediği tip (Audio, Video, Image) ile ffprobe tespiti uyuşmazsa -> AssetTypeError
2. En-Boy Oranı Kontrolü:
   - Gelen videonun çözünürlüğü ve oranı hesaplanır.
   - Şablonun beklediği oranla (örn. 9:16) uyuşmazsa -> RatioMismatchWarning üretilir.
3. Otomatik Ölçekleme (Crop/Pad):
   - Oran uyuşmazlığında şablondaki kurtarma stratejisi (Crop, Pad, Scale)
     AST FilterChain'e otomatik enjekte edilir, piksel bozulması (stretch) önlenir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from typing import Mapping, Optional
import warnings

import structlog

from services.core.hustler.domain.models.template import (
    AssetType,
    RecoveryStrategy,
    SlotSpec,
    TemplateSpec,
)
from services.core.hustler.generators.ffmpeg_ast import Filter, FilterChain

logger = structlog.get_logger()


class SlotValidationError(Exception):
    """Slot doğrulama işlemlerinin temel istisnası."""
    pass


class MissingAssetSlotError(SlotValidationError):
    """Zorunlu bir slot için dosya sağlanmadığında fırlatılır."""
    pass


class AssetTypeError(SlotValidationError):
    """Slotun beklediği medya tipi ile dosya tipi uyuşmadığında fırlatılır."""
    pass


class RatioMismatchWarning(UserWarning):
    """En-boy oranı şablon beklentisiyle uyuşmadığında üretilen uyarı."""
    pass


@dataclass
class SlotValidationResult:
    """Tek bir slotun doğrulama ve enjekte edilen filtre zinciri sonucu."""
    slot_id: str
    file_path: Path
    detected_type: AssetType
    width: Optional[int] = None
    height: Optional[int] = None
    actual_aspect_ratio: Optional[float] = None
    has_ratio_mismatch: bool = False
    recovery_strategy_applied: Optional[RecoveryStrategy] = None
    filter_chain: Optional[FilterChain] = None
    warnings: list[str] = field(default_factory=list)


def probe_media_file(file_path: str | Path) -> tuple[AssetType, Optional[int], Optional[int]]:
    """ffprobe ile medya dosyasının türünü (Video/Audio/Image) ve çözünürlüğünü tespit eder."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Medya dosyası bulunamadı: {path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(path),
    ]

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if res.returncode != 0:
        err = res.stderr.strip()
        raise ValueError(f"ffprobe dosyayı okuyamadı ({path}): {err}")

    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe JSON çıktısı geçersiz: {exc}") from exc

    streams = data.get("streams", [])
    if not streams:
        raise ValueError(f"Dosyada hiçbir medya akışı (stream) bulunamadı: {path}")

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream:
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        codec_name = str(video_stream.get("codec_name", "")).lower()
        ext = path.suffix.lower()

        # Resim (Image) tespiti: MJPEG/PNG/WEBP/BMP veya resim uzantısı
        is_image = (
            ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
            or codec_name in ("mjpeg", "png", "webp", "bmp", "tiff")
        )

        detected_type = AssetType.IMAGE if is_image else AssetType.VIDEO
        return detected_type, width, height

    if audio_stream:
        return AssetType.AUDIO, None, None

    raise ValueError(f"Desteklenmeyen veya tanımlanamayan medya formatı: {path}")


class SlotValidator:
    """Şablon slot eşleme, tip doğrulama ve en-boy oranı kurtarma motoru."""

    def __init__(
        self,
        template: TemplateSpec,
        slots: Optional[list[SlotSpec]] = None,
        default_strategy: Optional[RecoveryStrategy] = None,
    ) -> None:
        self.template = template
        self.strategy = default_strategy or template.recovery_strategy

        # Slot listesini hazırla
        if slots is not None:
            self.slots = slots
        elif template.slots is not None:
            self.slots = template.slots
        else:
            # Şablondan varsayılan slotları türet (sahne slotları + ses slotu)
            self.slots = self._generate_default_slots()

    def _generate_default_slots(self) -> list[SlotSpec]:
        """Şablon sahne sayısına göre varsayılan slotları üretir."""
        generated: list[SlotSpec] = []
        for i in range(self.template.max_scenes):
            generated.append(
                SlotSpec(
                    slot_id=f"scene_{i}",
                    expected_type=AssetType.VIDEO,
                    required=(i == 0),  # En az 1 sahne zorunlu
                    aspect_ratio="9:16",
                    description=f"Sahne #{i} görsel/video slotu",
                )
            )
        generated.append(
            SlotSpec(
                slot_id="audio",
                expected_type=AssetType.AUDIO,
                required=True,
                aspect_ratio=None,
                description="Ana seslendirme (TTS) slotu",
            )
        )
        return generated

    def build_recovery_filter_chain(
        self,
        width: int,
        height: int,
        strategy: Optional[RecoveryStrategy] = None,
    ) -> FilterChain:
        """En-boy oranı uyuşmazlığında görüntüyü deforme etmeden (stretch olmadan)

        Crop veya Pad filtrelerini AST FilterChain olarak üretir.
        """
        strat = strategy or self.strategy
        target_w = self.template.render_config.width
        target_h = self.template.render_config.height
        target_fps = self.template.render_config.fps
        bg_color = self.template.render_config.bg_color

        setsar_filter = Filter("setsar", args=["1"], kwargs={})
        fps_filter = Filter("fps", args=[f"{target_fps}"], kwargs={})

        if strat == RecoveryStrategy.PAD:
            # Letterbox / Pillarbox: Oranı koruyarak sığdır ve kenarlara dolgu (pad) ekle
            scale_filter = Filter(
                "scale",
                args=[f"{target_w}", f"{target_h}"],
                kwargs={"force_original_aspect_ratio": "decrease"},
            )
            pad_filter = Filter(
                "pad",
                args=[
                    f"{target_w}",
                    f"{target_h}",
                    f"({target_w}-iw)/2",
                    f"({target_h}-ih)/2",
                ],
                kwargs={"color": bg_color},
            )
            return FilterChain([scale_filter, pad_filter, setsar_filter, fps_filter])

        # Varsayılan veya CROP / SCALE: Oranı koruyarak büyüt ve taşan kısımları kırp (Center Crop)
        scale_filter = Filter(
            "scale",
            args=[f"{target_w}", f"{target_h}"],
            kwargs={"force_original_aspect_ratio": "increase"},
        )
        crop_filter = Filter("crop", args=[f"{target_w}", f"{target_h}"], kwargs={})
        return FilterChain([scale_filter, crop_filter, setsar_filter, fps_filter])

    def validate_slot(
        self,
        slot: SlotSpec,
        file_path: Optional[str | Path],
    ) -> SlotValidationResult:
        """Tek bir slotu doğrular, tip ve oran kontrolünü yapar."""
        # 1. Zorunlu slot varlık kontrolü
        if file_path is None or not Path(file_path).is_file():
            if slot.required:
                raise MissingAssetSlotError(
                    f"Zorunlu slot eksik: '{slot.slot_id}' için geçerli bir medya dosyası sağlanmadı."
                )
            # Opsiyonel ve dosya yoksa None ile dön
            return SlotValidationResult(
                slot_id=slot.slot_id,
                file_path=Path(file_path) if file_path else Path(""),
                detected_type=slot.expected_type,
            )

        resolved_path = Path(file_path)

        # 2. Medya tipi kontrolü (ffprobe)
        detected_type, width, height = probe_media_file(resolved_path)

        # Image kabul eden video slotu toleransı haricinde katı eşleşme
        type_compatible = (
            detected_type == slot.expected_type
            or (slot.expected_type == AssetType.VIDEO and detected_type == AssetType.IMAGE)
        )

        if not type_compatible:
            raise AssetTypeError(
                f"Asset tip uyuşmazlığı: '{slot.slot_id}' slotu {slot.expected_type.value.upper()} "
                f"bekliyor, ancak gönderilen dosya {detected_type.value.upper()} formatında: {resolved_path}"
            )

        # 3. En-boy oranı (Aspect Ratio) kontrolü
        warnings_list: list[str] = []
        has_ratio_mismatch = False
        actual_ratio: Optional[float] = None
        filter_chain: Optional[FilterChain] = None

        if detected_type in (AssetType.VIDEO, AssetType.IMAGE) and width and height:
            actual_ratio = width / height
            target_ratio = (
                self.template.render_config.width / self.template.render_config.height
            )

            # Oran farkı %1'den büyükse uyarı üret
            if abs(actual_ratio - target_ratio) > 0.01:
                has_ratio_mismatch = True
                warn_msg = (
                    f"En-boy oranı uyuşmazlığı: '{slot.slot_id}' ({width}x{height}, oran: {actual_ratio:.2f}) "
                    f"şablonun beklediği {target_ratio:.2f} (9:16) ile uyuşmuyor. "
                    f"Otomatik kurtarma stratejisi ({self.strategy.value.upper()}) enjekte ediliyor."
                )
                warnings.warn(warn_msg, RatioMismatchWarning, stacklevel=2)
                warnings_list.append(warn_msg)
                logger.warning("Ratio mismatch detected",
                               slot=slot.slot_id,
                               actual_dims=f"{width}x{height}",
                               actual_ratio=round(actual_ratio, 3),
                               target_ratio=round(target_ratio, 3),
                               strategy=self.strategy.value)

            # AST FilterChain üretimi (otomatik kurtarma veya standart ölçekleme)
            filter_chain = self.build_recovery_filter_chain(
                width=width,
                height=height,
                strategy=self.strategy,
            )

        return SlotValidationResult(
            slot_id=slot.slot_id,
            file_path=resolved_path,
            detected_type=detected_type,
            width=width,
            height=height,
            actual_aspect_ratio=actual_ratio,
            has_ratio_mismatch=has_ratio_mismatch,
            recovery_strategy_applied=self.strategy if has_ratio_mismatch else None,
            filter_chain=filter_chain,
            warnings=warnings_list,
        )

    def validate_slots(
        self,
        asset_map: Mapping[str, str | Path],
    ) -> dict[str, SlotValidationResult]:
        """Tüm slot sözleşmesini verilen varlık sözlüğüyle doğrular."""
        results: dict[str, SlotValidationResult] = {}

        for slot in self.slots:
            file_path = asset_map.get(slot.slot_id)
            result = self.validate_slot(slot, file_path)
            results[slot.slot_id] = result

        return results

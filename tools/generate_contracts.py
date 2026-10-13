import sys
from pathlib import Path

# Add core to sys.path so we can import hustler
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir / "services" / "core"))
sys.path.append(str(root_dir))

from services.core.hustler.contracts.models import (  # noqa: E402
    AssetType,
    ClaimReport,
    RecoveryStrategy,
    RenderConfig,
    SafeZone,
    ScriptDoc,
    SlotSpec,
    SubtitleStyle,
    TemplateSpec,
    VideoRecord,
    WordTiming,
)


def generate_typescript_contracts() -> str:
    content = """// AUTO-GENERATED: DO NOT EDIT
// Synchronized Pydantic & Zod Contract Definitions for Hustler

import { z } from 'zod'

// ============================================================================
// 1. VideoRecord Contract
// ============================================================================

export interface VideoRecord {
  id: string
  title: string
  duration: number
}

export const VideoRecordSchema = z.object({
  id: z.string().describe('Unique video identifier'),
  title: z.string().describe('Title of the video'),
  duration: z.number().int().describe('Duration in seconds'),
})

// ============================================================================
// 2. ScriptDoc Contract
// ============================================================================

export interface ScriptDoc {
  hook: string
  body: string[]
  cta: string
  estimated_duration: number
}

export const ScriptDocSchema = z.object({
  hook: z.string().max(150, 'Hook cannot exceed 150 characters'),
  body: z.array(z.string()).min(1, 'Body must have at least one scene'),
  cta: z.string(),
  estimated_duration: z.number().int().positive('Estimated duration must be positive'),
})

// ============================================================================
// 3. ClaimReport Contract
// ============================================================================

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface ClaimReport {
  is_safe: boolean
  flagged_claims: string[]
  risk_level: RiskLevel
}

export const RiskLevelEnum = z.enum(['LOW', 'MEDIUM', 'HIGH'])

export const ClaimReportSchema = z.object({
  is_safe: z.boolean(),
  flagged_claims: z.array(z.string()),
  risk_level: RiskLevelEnum,
})

// ============================================================================
// 4. WordTiming Contract
// ============================================================================

export interface WordTiming {
  word: string
  start_ms: number
  end_ms: number
}

export const WordTimingSchema = z.object({
  word: z.string(),
  start_ms: z.number().int().nonnegative(),
  end_ms: z.number().int().nonnegative(),
})

// ============================================================================
// 5. SubtitleStyle Contract
// ============================================================================

export interface SubtitleStyle {
  font_name: string
  font_size: number
  primary_color: string
  highlight_color: string
  alignment: number
  margin_v: number
}

export const SubtitleStyleSchema = z.object({
  font_name: z.string().min(1, 'Font adı boş olamaz'),
  font_size: z.number().int().positive('Font boyutu pozitif tam sayı olmalıdır'),
  primary_color: z.string().regex(/^&H[0-9A-Fa-f]{8}&$/, 'ASS renk formatı &HBBGGRR& olmalıdır'),
  highlight_color: z.string().regex(/^&H[0-9A-Fa-f]{8}&$/, 'ASS vurgu rengi &HBBGGRR& olmalıdır'),
  alignment: z.number().int().min(1).max(9, 'Hizalama 1-9 arasında olmalıdır'),
  margin_v: z.number().int().nonnegative('Kenar boşluğu negatif olamaz'),
})

// ============================================================================
// 6. Template & Render Specifications
// ============================================================================

export type AssetType = 'video' | 'audio' | 'image'
export const AssetTypeEnum = z.enum(['video', 'audio', 'image'])

export interface SlotSpec {
  slot_id: string
  expected_type: AssetType
  required: boolean
  aspect_ratio?: string
  description?: string
}

export const SlotSpecSchema = z.object({
  slot_id: z.string(),
  expected_type: AssetTypeEnum.default('video'),
  required: z.boolean().default(true),
  aspect_ratio: z.string().default('9:16'),
  description: z.string().default(''),
})

export interface SafeZone {
  margin_top: number
  margin_bottom: number
  margin_left: number
  margin_right: number
}

export const SafeZoneSchema = z.object({
  margin_top: z.number().int(),
  margin_bottom: z.number().int(),
  margin_left: z.number().int(),
  margin_right: z.number().int(),
})

export interface RenderConfig {
  width: number
  height: number
  fps: number
  bg_color: string
  safe_zone: SafeZone
}

export const RenderConfigSchema = z.object({
  width: z.number().int(),
  height: z.number().int(),
  fps: z.number().int(),
  bg_color: z.string(),
  safe_zone: SafeZoneSchema,
})

export type RecoveryStrategy = 'crop' | 'pad' | 'scale'
export const RecoveryStrategyEnum = z.enum(['crop', 'pad', 'scale'])

export interface TemplateSpec {
  name: string
  target_duration_sec: number
  max_scenes: number
  allowed_tones: string[]
  render_config: RenderConfig
  recovery_strategy: RecoveryStrategy
  slots?: SlotSpec[]
}

export const TemplateSpecSchema = z.object({
  name: z.string().min(3),
  target_duration_sec: z.number().int().min(15).max(180),
  max_scenes: z.number().int().min(1).max(10),
  allowed_tones: z.array(z.string()).min(1),
  render_config: RenderConfigSchema,
  recovery_strategy: RecoveryStrategyEnum.default('crop'),
  slots: z.array(SlotSpecSchema).optional(),
})
"""
    return content


def main() -> None:
    # Aktif şema doğrulaması
    validated_models = [
        AssetType,
        ClaimReport,
        RecoveryStrategy,
        RenderConfig,
        SafeZone,
        ScriptDoc,
        SlotSpec,
        SubtitleStyle,
        TemplateSpec,
        VideoRecord,
        WordTiming,
    ]
    for model in validated_models:
        if hasattr(model, "model_json_schema"):
            assert model.model_json_schema() is not None

    contracts_dir = root_dir / "packages" / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)

    ts_content = generate_typescript_contracts()
    with open(contracts_dir / "index.ts", "w", encoding="utf-8") as f:
        f.write(ts_content)

    print("Synchronized Pydantic & Zod contracts successfully at packages/contracts/index.ts")


if __name__ == "__main__":
    main()

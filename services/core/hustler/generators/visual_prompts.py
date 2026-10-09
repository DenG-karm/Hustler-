import json
import structlog
from typing import Any, List
from pydantic import BaseModel, Field

from services.core.hustler.infrastructure.llm_port import LLMPort

logger = structlog.get_logger()

class ScenePrompt(BaseModel):
    """
    LLM'in sahneleri analiz edip zorunlu olarak döneceği veri modeli.
    Algoritmik eklemeler (enjeksiyonlar) bu objenin dışında yapılacaktır.
    """
    scene_index: int = Field(..., description="Sahnenin sırası (0-indexed).")
    raw_prompt: str = Field(
        ..., 
        description="Sahnenin sadece görsel betimlemesini içeren İngilizce metin. Asla ek parametre veya metin barındırmamalıdır."
    )

class ScenePromptList(BaseModel):
    prompts: List[ScenePrompt]

class VisualPromptCompiler:
    """
    K-406: Görsel Prompt Derleyici (Visual Prompt Compiler)
    Senaryoyu okur, her bir sahneyi AI görsel üreticileri (Midjourney/DALL-E) için
    İngilizce betimlemelere çevirir. Ardından oran (9:16) ve negatif prompt gibi 
    parametreleri dışarıdan güvenli bir şekilde kod seviyesinde ekler (Inject).
    """
    
    # AI'ın inisiyatifine bırakılamayacak katı render parametreleri
    SUFFIX_PARAMS = "--ar 9:16 --style raw"
    NEGATIVE_PROMPT = "--no text, typography, letters, watermarks, signature, fonts"
    
    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port

    async def compile_prompts(self, scenes: List[str]) -> List[dict[str, Any]]:
        """Türkçe sahneleri alıp donanımlı İngilizce prompt listesi döner."""
        schema = ScenePromptList.model_json_schema()
        
        scenes_text = "\n".join([f"Scene {i}: {s}" for i, s in enumerate(scenes)])
        
        # Kesin kısıtlamalar içeren Sistem Dayatması
        prompt = (
            f"You are a master cinematic prompt engineer for Midjourney and DALL-E.\n"
            f"I will provide you with a list of scenes in a different language (e.g., Turkish).\n"
            f"You MUST translate and describe them visually in ENGLISH.\n\n"
            f"CRITICAL INSTRUCTIONS:\n"
            f"1. NEVER include text, words, letters, or typography in the scenes. AI cannot render text. Keep it purely visual.\n"
            f"2. ONLY describe lighting, camera angle, mood, and the visual elements.\n"
            f"3. Do NOT add aspect ratio (--ar) or any Midjourney parameters yourself! Just the description.\n"
            f"4. Output MUST strictly match the following JSON Schema (Structured Output):\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"SCENES TO COMPILE:\n{scenes_text}"
        )
        
        res = await self.llm_port.generate_text(prompt)
        
        # Markdown temizliği
        clean_text = res.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        data = json.loads(clean_text.strip())
        parsed_list = ScenePromptList(**data)
        
        final_results = []
        for p in parsed_list.prompts:
            # Algoritmik Ekleme (String Concat) - LLM'in Hata Yapmasını Engelliyoruz
            final_prompt_str = f"{p.raw_prompt.strip()} {self.SUFFIX_PARAMS} {self.NEGATIVE_PROMPT}"
            
            final_results.append({
                "scene_index": p.scene_index,
                "raw_prompt": p.raw_prompt,
                "final_prompt": final_prompt_str
            })
            
        return final_results

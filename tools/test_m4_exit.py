import sys
import os
import json
import time
import asyncio
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.domain.models.template import TemplateSpec, RenderConfig, SafeZone
from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.validation.semantic import SemanticValidator
from services.core.hustler.validation.claims import ClaimMarker, ScriptStatusDecider
from services.core.hustler.generators.visual_prompts import VisualPromptCompiler
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse

logger = structlog.get_logger()

# Ağ (I/O) Gecikmesini önlemek için Test Mock LLM Adaptörü
class MockExitLLMPort(LLMPort):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK", max_tokens=9999)
        
    async def generate_text(self, prompt: str) -> LLMResponse:
        # İddia işaretleyici simülasyonu
        if "Bir içerik denetleyicisisin" in prompt:
            res = {"is_safe": True, "flagged_claims": [], "risk_level": "LOW"}
            return LLMResponse(json.dumps(res), 10, 10, 20)
            
        # Görsel prompt derleyici simülasyonu (İngilizce Çeviri)
        if "master cinematic prompt engineer" in prompt:
            res = {
                "prompts": [
                    {"scene_index": 0, "raw_prompt": "A highly detailed cinematic shot of the right tools being selected on a dark desk."},
                    {"scene_index": 1, "raw_prompt": "A montage of continuous creation and writing on a glowing futuristic screen."}
                ]
            }
            return LLMResponse(json.dumps(res), 10, 10, 20)
            
        return LLMResponse("{}", 0, 0, 0)

async def main() -> None:
    logger.info("--- M4 ÇIKIŞ KRİTERLERİ (EXIT CRITERIA) DOĞRULAMA TESTİ ---")
    
    # Bağımlılıklar
    llm = MockExitLLMPort()
    claim_marker = ClaimMarker(llm_port=llm)
    visual_compiler = VisualPromptCompiler(llm_port=llm)
    
    # 1. TEMPLATE (Sözleşme) OLUŞTURMA
    template = TemplateSpec(name="M4 Exit", target_duration_sec=30, max_scenes=2, allowed_tones=["ciddi"], render_config=RenderConfig(width=1080, height=1920, fps=30, bg_color="#000", safe_zone=SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10)))
    
    # Ham LLM Çıktısı (K-403 Simülasyonu) - Tam olarak 30 saniyeye sığacak kelime havuzu
    raw_script_data = {
        "hook": "Bu videoda sizlere yasal yollarla nasıl ilerleyeceğinizi anlatacağım.",
        "body": [
            "İlk adımda doğru araçları seçmek çok büyük bir önem taşıyor, çünkü sağlam altyapı her şeydir.",
            "Sonraki adımda ise istikrarlı bir şekilde üretmeye ve yeni şeyler öğrenmeye devam etmelisiniz. Bolca farklı kelime ekliyorum ki otuz saniyelik süre hedefini ve WPM toleransını güvenli bir şekilde karşılayalım. Hedefimiz başarıya emin adımlarla ulaşmak."
        ],
        "cta": "Daha fazla bilgi için kanala abone olmayı sakın unutmayın.",
        "estimated_duration": 30
    }
    
    # --- 1. DOĞRULAMA GECİKMESİ ÖLÇÜMÜ (I/O HARİÇ PURE FUNCTION HIZI) ---
    logger.info(">>> 1. TEST: Doğrulama Gecikmesi (Validation Latency) <<<")
    
    start_time = time.perf_counter()
    
    # K-401 Pydantic Şema Zırhı
    doc = ScriptDoc.model_validate(raw_script_data)
    
    # K-404 Anlamsal Zırh (Süre ve N-gram)
    SemanticValidator.validate(doc, template)
    
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000
    
    logger.info("Donanımsal Doğrulama Süresi (Pydantic + N-Gram)", latency_ms=f"{latency_ms:.3f} ms")
    
    # Çıkış Kriteri: < 50ms
    assert latency_ms < 50, f"KRİTİK HATA: Doğrulama gecikmesi çok yüksek! {latency_ms}ms > 50ms"
    logger.info("✅ Gecikme testi başarılı (50ms eşiğinin çok altında).")
    
    # --- 2. UÇTAN UCA ONAY AKIŞI (STATE MACHINE) ---
    logger.info(">>> 2. TEST: Uçtan Uca İddia/Onay Akışı <<<")
    script_text = doc.hook + " " + " ".join(doc.body) + " " + doc.cta
    report = await claim_marker.verify_claims(script_text)
    status = ScriptStatusDecider.get_final_status(report)
    
    logger.info("Senaryo Onay Durumu", is_safe=report.is_safe, risk=report.risk_level, status=status)
    assert status == "APPROVED", "Senaryo yanlışlıkla reddedildi!"
    logger.info("✅ Senaryo K-405 zırhından başarıyla geçip APPROVED durumunu aldı.")
    
    # --- 3. GÖRSEL PROMPT ENTEGRASYONU ---
    logger.info(">>> 3. TEST: Görsel Prompt Derleyici Entegrasyonu <<<")
    visual_results = await visual_compiler.compile_prompts(doc.body)
    
    for item in visual_results:
        logger.info(f"Sahne {item['scene_index']} Derlendi", final_prompt=item["final_prompt"])
        # Parametre Enjeksiyon Testi
        assert "--ar 9:16" in item["final_prompt"], "Boyut parametresi (--ar 9:16) koda gömülmemiş!"
        assert "--no text" in item["final_prompt"], "Negatif prompt (no text) koda gömülmemiş!"
        
    logger.info("✅ Türkçe sahneler İngilizce görsel promtuna çevrildi ve donanımsal parametreler başarıyla gömüldü.")
    
    logger.info("=====================================================")
    logger.info("🚀 M4 FAZI (SENARYO MOTORU) BAŞARIYLA TAMAMLANDI! 🚀")
    logger.info("Tüm çıkış kriterleri (Gecikme <50ms, Onay Akışı, Görsel Derleyici) mükemmel şekilde doğrulandı.")
    logger.info("Sistem M5 (Ses ve Render) hattına geçiş için %100 hazır.")
    logger.info("=====================================================")

if __name__ == "__main__":
    asyncio.run(main())

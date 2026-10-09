import sys
import os
import asyncio
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.llm_port import LLMPort, TokenLimitExceededError

logger = structlog.get_logger()

async def main() -> None:
    logger.info("--- M3 K-305: LLM PORT VE MALİYET DEFTERİ TESTİ ---")
    
    # Müşterinin paylaştığı API anahtarı
    api_key = "MOCK_API_KEY_XXX_YYY_ZZZ"
    
    # Bütçeyi bilerek çok düşük (15 token) ayarlıyoruz
    port = LLMPort(api_key=api_key, max_tokens=15)
    
    # Gerçek API Key disable olduğu için, ağ isteğini mockluyoruz (Sentetik Cevap)
    from services.core.hustler.infrastructure.llm_port import LLMResponse
    async def mock_execute(prompt: str) -> LLMResponse:
        # Her istekte 10 token harcıyor (15 bütçe ile 2. istekte çakılmalı)
        await asyncio.sleep(0.1)
        return LLMResponse("Mocked Response", 5, 5, 10)
    
    setattr(port, "_execute_network_request", mock_execute)
    
    prompts = [
        "Sadece tek kelime ile cevap ver: Gökyüzü ne renktir?",
        "Sadece tek kelime ile cevap ver: Su kaç derecede kaynar?",
        "Sadece tek kelime ile cevap ver: Dünyanın en büyük okyanusu nedir?"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        try:
            logger.info(f"İstek {i} başlatılıyor...", prompt=prompt)
            res = await port.generate_text(prompt)
            logger.info(f"✅ İstek {i} Başarılı!", cevap=res.text.strip(), harcanan_token=res.total_tokens)
        except TokenLimitExceededError as e:
            # Ön Kesici (Fail-Fast) devrede, ağa çıkmadan reddetti
            logger.warning(f"❌ İstek {i} Reddedildi (Fail-Fast Devrede!)", sebep=str(e))
        except Exception as e:
            from tenacity import RetryError
            import httpx
            if isinstance(e, RetryError):
                if isinstance(e.last_attempt.exception(), httpx.HTTPStatusError):
                    logger.error("HTTP Hatası", status=getattr(getattr(e.last_attempt.exception(), "response", None), "status_code", 500), body=getattr(getattr(e.last_attempt.exception(), "response", None), "text", ""))
                else:
                    logger.error("Beklenmeyen hata (Retry)", error=str(e.last_attempt.exception()))
            else:
                logger.error("Beklenmeyen hata", error=str(e))
            
    await port.close()
    logger.info("--- K-305 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())

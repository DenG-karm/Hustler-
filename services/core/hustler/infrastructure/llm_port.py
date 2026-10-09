import httpx
from dataclasses import dataclass
import structlog
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

logger = structlog.get_logger()

GEMINI_MODEL = "gemini-2.5-flash"
_ERROR_BODY_LIMIT = 500


class LLMHTTPError(httpx.HTTPStatusError):
    """HTTP hatası; durum kodu ve yanıt gövdesi mesajda görünür (hata maskelenmez)."""

    def __init__(self, response: httpx.Response) -> None:
        body = response.text[:_ERROR_BODY_LIMIT]
        super().__init__(
            f"LLM HTTP {response.status_code}: {body}",
            request=response.request,
            response=response,
        )

class TokenLimitExceededError(Exception):
    """Token bütçesi aşıldığında fırlatılır."""
    pass

@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class CostLedger:
    """Maliyet Defteri: Kullanılan token sayısını bellek içinde tutar."""
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.current_usage = 0
        
    def check_budget(self) -> None:
        """Pre-flight check: Bütçe aşıldıysa anında hata fırlat (Fail-Fast)"""
        if self.current_usage >= self.max_tokens:
            raise TokenLimitExceededError(f"Token limiti aşıldı! Mevcut: {self.current_usage}, Limit: {self.max_tokens}")
            
    def add_usage(self, tokens: int) -> None:
        self.current_usage += tokens

class LLMPort:
    """
    K-305: Asenkron LLM Adaptörü (Gemini API Destekli)
    Ön kesici (Pre-flight check) ve Tenacity direnç mekanizmalarıyla korunur.
    """
    def __init__(self, api_key: str, max_tokens: int = 100000, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.ledger = CostLedger(max_tokens)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    async def close(self) -> None:
        """httpx client'ı güvenle kapatır."""
        await self.client.aclose()

    @staticmethod
    def _should_retry_error(exc: BaseException) -> bool:
        """Sadece 429 ve 50x hatalarında yeniden dener."""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (429, 500, 502, 503, 504)
        if isinstance(exc, httpx.RequestError):
            return True
        return False

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_should_retry_error),
        reraise=True,
    )
    async def _execute_network_request(self, prompt: str) -> LLMResponse:
        """Gerçek ağ isteği (Tenacity ile korunur)"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        resp = await self.client.post(
            self.endpoint,
            json=payload,
            headers={"x-goog-api-key": self.api_key},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMHTTPError(resp) from e
        
        data = resp.json()
        
        # Gemini JSON Parse
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", 0)
        
        return LLMResponse(text, prompt_tokens, completion_tokens, total_tokens)

    async def generate_text(self, prompt: str) -> LLMResponse:
        """
        Dışarıya açık ana metod.
        Fail-Fast mantığı gereği, ağ isteğine çıkmadan önce bütçeyi (Maliyet Defteri) kontrol eder.
        """
        # 1. Ön Kesici (Pre-flight check)
        self.ledger.check_budget()
        
        # 2. Ağ İsteği (Retry mekanizmalı)
        response = await self._execute_network_request(prompt)
        
        # 3. Maliyet Defterine İşle
        self.ledger.add_usage(response.total_tokens)
        
        logger.info("llm_call_success", 
            tokens_used=response.total_tokens, 
            ledger_total=self.ledger.current_usage,
            budget_limit=self.ledger.max_tokens
        )
        
        return response

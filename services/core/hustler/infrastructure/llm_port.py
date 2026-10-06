import httpx
from typing import Optional
from dataclasses import dataclass
import structlog
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = structlog.get_logger()

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
        
    def check_budget(self):
        """Pre-flight check: Bütçe aşıldıysa anında hata fırlat (Fail-Fast)"""
        if self.current_usage >= self.max_tokens:
            raise TokenLimitExceededError(f"Token limiti aşıldı! Mevcut: {self.current_usage}, Limit: {self.max_tokens}")
            
    def add_usage(self, tokens: int):
        self.current_usage += tokens

class LLMPort:
    """
    K-305: Asenkron LLM Adaptörü (Gemini API Destekli)
    Ön kesici (Pre-flight check) ve Tenacity direnç mekanizmalarıyla korunur.
    """
    def __init__(self, api_key: str, max_tokens: int = 100000):
        self.api_key = api_key
        self.ledger = CostLedger(max_tokens)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

    async def close(self):
        """httpx client'ı güvenle kapatır."""
        await self.client.aclose()

    def _should_retry_error(exc: Exception) -> bool:
        """Sadece 429 ve 50x hatalarında yeniden dener."""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (429, 500, 502, 503, 504)
        if isinstance(exc, httpx.RequestError):
            return True
        return False

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError))
    )
    async def _execute_network_request(self, prompt: str) -> LLMResponse:
        """Gerçek ağ isteği (Tenacity ile korunur)"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        resp = await self.client.post(self.endpoint, json=payload)
        resp.raise_for_status()
        
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

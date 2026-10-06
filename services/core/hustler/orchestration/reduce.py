import asyncio
import hashlib
import json
import structlog
from typing import Dict, Any, Optional

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.llm_port import LLMPort

logger = structlog.get_logger()

class ReduceOrchestrator:
    """
    K-308: Reduce ve Önbellek Yönetimi.
    Map evresinden geçen veya doğrudan gelen ham transkriptleri analiz eder.
    Video kimliği (ID) bağımsız, tamamen "içerik" tabanlı (Hash) önbellekleme yaparak
    LLM maliyetlerini (Token) sıfırlamayı amaçlar.
    """
    def __init__(self, db: Database, llm_port: LLMPort):
        self.db = db
        self.llm_port = llm_port

    async def init_table(self):
        """Veritabanında önbellek tablosunu hazırlar."""
        query = """
        CREATE TABLE IF NOT EXISTS analysis_results (
            cache_hash TEXT PRIMARY KEY,
            result_json TEXT NOT NULL
        )
        """
        await self.db.execute_write(query)

    def _generate_cache_key(self, transcript: str, prompt_version: str) -> str:
        """
        Video ID kullanmak yerine içerik + versiyon tabanlı SHA-256 hash üretir.
        Eğer video silinip tekrar yüklenirse veya bir Shorts videosu YouTube'da 10 defa
        farklı kanallarda paylaşılırsa bile, aynı transkript ise 0 token harcanır.
        """
        payload = f"{transcript}::{prompt_version}".encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    async def analyze(self, transcript: str, prompt_version: str = "v1.0") -> Dict[str, Any]:
        """
        Gelen transkriptin analizini yapar.
        Cache Hit olursa LLM çağrısı yapılmaz (0 token).
        Cache Miss olursa LLM aranır ve sonuç asenkron veritabanına (WriterQueue) yazılır.
        """
        cache_key = self._generate_cache_key(transcript, prompt_version)
        
        # 1. Önbellekten Oku (Cache Hit Kontrolü)
        # Okuyucu havuzu asenkron olduğu için WriterQueue'yu asla beklemez ve kilitlemez.
        reader = await self.db.get_reader()
        try:
            async with reader.execute("SELECT result_json FROM analysis_results WHERE cache_hash = ?", (cache_key,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    logger.info("reduce_cache_hit", 
                        hash_key=cache_key[:8], 
                        prompt_version=prompt_version, 
                        msg="Önbellek eşleşti! Sıfır LLM maliyetiyle sonuç dönülüyor."
                    )
                    return json.loads(row[0])
        finally:
            await reader.close()

        # 2. Önbellek Boş (Cache Miss) -> LLM'e git
        logger.warning("reduce_cache_miss", 
            hash_key=cache_key[:8], 
            prompt_version=prompt_version, 
            msg="İçerik ilk kez görüldü. LLM analizi başlatılıyor..."
        )
        
        prompt = f"Lütfen şu transkripti sistem prompt v{prompt_version} kurallarına göre analiz et:\n{transcript}"
        llm_response = await self.llm_port.generate_text(prompt)
        
        # 3. Analiz Sonucunu Hazırla
        result_data = {
            "text": llm_response.text,
            "tokens_used": llm_response.total_tokens,
            "prompt_version": prompt_version
        }
        
        # 4. Sonucu Kalıcı Olarak Yaz (WriterQueue üzerinden)
        # İleride okuma yapacak diğer işlemler için hash'i kalıcı hale getiriyoruz.
        insert_query = """
        INSERT OR REPLACE INTO analysis_results (cache_hash, result_json)
        VALUES (?, ?)
        """
        await self.db.execute_write(insert_query, (cache_key, json.dumps(result_data)))
        
        return result_data

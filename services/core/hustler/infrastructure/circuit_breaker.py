import time
from enum import Enum
import structlog
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger()

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"           # Normal operasyon, istekler akar
    OPEN = "OPEN"               # Devre açık, sistem çökmüş durumda, istekler anında reddedilir (Fail-Fast)
    HALF_OPEN = "HALF_OPEN"     # Soğuma bitti, sistem kendine gelmiş mi diye 1 adet test isteğine izin verilir

class CircuitBreakerOpenError(Exception):
    """Devre AÇIK (Open) olduğu için isteğin işlenmeden anında (Fail-Fast) reddedildiğini belirtir."""
    pass

class CircuitBreakerRejectedError(Exception):
    """Video süresi veya bütçe kısıtlamalarından dolayı işleme alınmadan reddedilen istekler."""
    pass

@dataclass
class CircuitBreakerConfig:
    max_consecutive_failures: int = 3
    cooldown_seconds: float = 30.0
    max_video_duration_seconds: int = 600  # 10 Dk varsayılan süre bütçesi

class CircuitBreaker:
    """
    K-303: Hata İzolasyonu (Devre Kesici) Durum Makinesi
    Whisper ve LLM gibi ağır ve hata potansiyeli yüksek altyapıların, 
    sürekli hata fırlatarak event-loop'u kitlemesini ve tüm sistemi aşağı çekmesini önler.
    """
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def check_budget(self, video_duration_seconds: int):
        """
        Videoyu işleme almadan önce bütçe kontrolü yapar. 
        Fail-fast mantığının ilk basamağıdır.
        """
        if video_duration_seconds > self.config.max_video_duration_seconds:
            logger.warning("circuit_budget_rejected", 
                breaker=self.name, 
                duration=video_duration_seconds,
                max_allowed=self.config.max_video_duration_seconds
            )
            raise CircuitBreakerRejectedError(f"Video süresi bütçeyi aşıyor: {video_duration_seconds}s > {self.config.max_video_duration_seconds}s")

    async def __aenter__(self):
        """Asenkron bağlam yöneticisi (Context Manager) girişi"""
        if self.state == CircuitBreakerState.OPEN:
            # Soğuma süresi bitti mi?
            if time.time() - self.last_failure_time >= self.config.cooldown_seconds:
                logger.info("circuit_half_open", breaker=self.name, msg="Soğuma süresi bitti, devre YARI AÇIK (Half-Open) konumda test ediliyor.")
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                # Soğuma devam ediyor, anında fail-fast yap!
                raise CircuitBreakerOpenError(f"[{self.name}] Devre AÇIK. İstek işlenmeden reddedildi.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asenkron bağlam yöneticisi çıkışı"""
        if exc_type is None:
            # İşlem Başarılı
            if self.state == CircuitBreakerState.HALF_OPEN:
                logger.info("circuit_closed", breaker=self.name, msg="Test isteği başarılı oldu. Devre onarıldı ve KAPALI duruma geçti.")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
            elif self.state == CircuitBreakerState.CLOSED:
                # Arada gelen başarılı işlem sayacı sıfırlar
                self.failure_count = 0
        else:
            # Hata meydana geldi.
            # Bütçe ve Fail-Fast reddi sistem hatası sayılmaz. Onları es geçiyoruz.
            if issubclass(exc_type, CircuitBreakerRejectedError) or issubclass(exc_type, CircuitBreakerOpenError):
                return False # Hatayı yukarı fırlat
                
            # Gerçek bir sistem hatası (Örn: GPU OOM, API Timeout)
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Yarı açık test başarısız olduysa hiç acımadan devreyi tekrar kapat!
                logger.warning("circuit_reopened", breaker=self.name, msg="Yarı açık test başarısız! Devre hemen tekrar AÇILDI.")
                self.state = CircuitBreakerState.OPEN
            elif self.state == CircuitBreakerState.CLOSED:
                if self.failure_count >= self.config.max_consecutive_failures:
                    logger.error("circuit_tripped", breaker=self.name, failures=self.failure_count, limit=self.config.max_consecutive_failures, msg="Kritik ardışık hata limiti aşıldı! Devre AÇILDI.")
                    self.state = CircuitBreakerState.OPEN
        return False # Tüm Exception'lar yakalandıktan sonra yukarı iletilsin

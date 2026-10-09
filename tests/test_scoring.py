import datetime
import os
import sys

# Kök dizini PATH'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.domain.scoring import calculate_score

def test_scoring_new_viral_video() -> None:
    """Uç Senaryo: Yüksek ivmeli viral, 2 saat önce yüklenmiş, çılgın etkileşimli."""
    now = datetime.datetime(2026, 10, 6, 12, 0, tzinfo=datetime.timezone.utc)
    pub = "2026-10-06T10:00:00Z"
    
    # 2 saatte 15000 izlenme, 3000 beğeni = İvme 7500/sa (Capped), Etkileşim %20 (Capped)
    score = calculate_score(pub, 15000, 2800, 200, current_time=now)
    assert score == 100.0

def test_scoring_old_video() -> None:
    """Uç Senaryo: 10 yıllık eski, 10 Milyon izlenmeli ama ivmesi ölmüş video."""
    now = datetime.datetime(2026, 10, 6, 12, 0, tzinfo=datetime.timezone.utc)
    pub = "2016-10-06T10:00:00Z"
    
    # Çok fazla izlenme var ama yaş 87600 saat. İvme ~ 114 izlenme/saat.
    # Etkileşim %5 civarı olsun.
    score = calculate_score(pub, 10000000, 480000, 20000, current_time=now)
    
    # Puanı viral videoya göre ciddi düşük olmalı (örn. < 30)
    assert score < 30.0

def test_scoring_zero_views() -> None:
    """Uç Senaryo: Yeni yayınlanmış ama hiç izlenmemiş ölü video."""
    now = datetime.datetime(2026, 10, 6, 12, 0, tzinfo=datetime.timezone.utc)
    pub = "2026-10-06T10:00:00Z"
    
    score = calculate_score(pub, 0, 0, 0, current_time=now)
    assert score == 0.0

def test_scoring_moderate_video() -> None:
    """Orta seviye günlük video"""
    now = datetime.datetime(2026, 10, 6, 12, 0, tzinfo=datetime.timezone.utc)
    pub = "2026-10-05T12:00:00Z" # 24 saat önce
    
    # 24 saatte 24000 izlenme -> ivme = 1000/saat (norm_vel = 0.2 -> %12)
    # Etkileşim %7.5 -> (norm_eng = 0.5 -> %20)
    # Beklenen skor = 12 + 20 = 32.0
    score = calculate_score(pub, 24000, 1500, 300, current_time=now)
    assert score == 32.0

import datetime

def calculate_score(published_at_iso: str, view_count: int, like_count: int, comment_count: int, current_time: datetime.datetime = None) -> float:
    """
    K-204: Skorlama Algoritması (Pure Function)
    Hiçbir yan etki içermez (DB bağımsız, I/O bağımsız).
    Görüntülenme İvmesi ve Etkileşim Oranını ağırlıklı hesaplayarak 0-100 arası Skor üretir.
    """
    if current_time is None:
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
    # ISO 8601 'Z' uyumluluğu (Eski Python sürümleri için düzeltme)
    published_str = published_at_iso.replace("Z", "+00:00")
    try:
        published_at = datetime.datetime.fromisoformat(published_str)
    except ValueError:
        return 0.0

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=datetime.timezone.utc)

    # Saat cinsinden yaş (minimum 1 saat, sıfıra bölmeyi engeller ve anlık patlamaları törpüler)
    age_delta = current_time - published_at
    age_hours = max(1.0, age_delta.total_seconds() / 3600.0)
    
    view_count = max(0, view_count)
    like_count = max(0, like_count)
    comment_count = max(0, comment_count)

    # 1. Görüntülenme İvmesi (Velocity: Views per hour)
    velocity = view_count / age_hours
    
    # 2. Etkileşim Oranı (Engagement Rate)
    engagement = (like_count + comment_count) / view_count if view_count > 0 else 0.0

    # Normalizasyon Sınırları (Deneyimsel limitler)
    # Shorts için: 5000 izlenme/saat viral kabul edilir
    # %15 (0.15) etkileşim çok yüksek kabul edilir
    norm_velocity = min(1.0, velocity / 5000.0) 
    norm_engagement = min(1.0, engagement / 0.15)
    
    # Ağırlıklı Formül: %60 İvme, %40 Etkileşim
    score = (norm_velocity * 60) + (norm_engagement * 40)
    
    return round(score, 2)

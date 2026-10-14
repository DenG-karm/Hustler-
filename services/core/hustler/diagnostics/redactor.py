"""
K-803: Tanılama Paketi ve Hassas Veri Maskeleme (Secret & PII Redactor).
- API anahtarlarını (sk-..., xi-..., Bearer...) maskeler.
- Windows ve Unix kullanıcı dizinlerini (C:\\Users\\xxx\\, /Users/xxx/, /home/xxx/) maskeler.
"""

from __future__ import annotations

import functools
import getpass
import os
import re

# 1. Bearer Token
_BEARER_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"([Bb]earer\s+)[^\s\"'`]+"),
    r"\g<1>[REDACTED]",
)

# 2. OpenAI ve ElevenLabs API Anahtarları (sk-..., xi-...)
_KEYS_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"(?:sk-(?:proj-)?|xi-)[a-zA-Z0-9_\-]{16,}"),
    "[REDACTED]",
)

# 3. Ortam değişkeni ve yapılandırma anahtar-değer çiftleri
_ENV_VAR_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(
        r"""(API_KEY|SECRET|TOKEN|PASSWORD|api_key|secret|token|password)\s*([=:]\s*)(["']?)([^"'\s\r\n]+)"""
    ),
    r"\1\2\3[REDACTED]",
)

# 4. Kullanıcı dizinleri: Windows (C:\Users\... ve JSON çift ters bölülü C:\\Users\\...), macOS (/Users/...) ve Linux (/home/...)
# \s hariç tutulmuştur; 'Ad Soyad' gibi boşluklu kullanıcı adları güvenle ve eksiksiz maskelenir.
_PATH_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"([Uu]sers(?:\\\\|\\|/)|/home/)[^/\\,\"';:\r\n]+"),
    r"\g<1><REDACTED>",
)


@functools.lru_cache(maxsize=1)
def _get_dynamic_user_info() -> tuple[str, re.Pattern[str]] | None:
    try:
        current_user = os.environ.get("USERNAME") or os.environ.get("USER") or getpass.getuser()
        if current_user and len(current_user) >= 3:
            if current_user.lower() not in {
                "root",
                "admin",
                "administrator",
                "user",
                "default",
                "none",
            }:
                pat = re.compile(
                    rf"""(?i)([/\\=:'"]){re.escape(current_user)}([/\\"'\\s,:\n])"""
                )
                return current_user, pat
    except Exception:
        pass
    return None


def redact_sensitive_text(raw: str) -> str:
    """
    Metin içindeki API anahtarlarını, yetki belirteçlerini ve kullanıcı dizin yollarını maskeler.
    Büyük metin akışlarında (örn. 1 MB+) mikro-saniye seviyesinde hızlı substring ön-filtresi uygular.
    """
    if not raw:
        return raw

    text = raw

    # 1. Bearer Token
    if "earer" in text:
        text = _BEARER_PATTERN[0].sub(_BEARER_PATTERN[1], text)

    # 2. API Anahtarları (sk-..., xi-...)
    if "sk-" in text or "xi-" in text:
        text = _KEYS_PATTERN[0].sub(_KEYS_PATTERN[1], text)

    # 3. Ortam Değişkeni / Yapılandırma Anahtarları
    if (
        "KEY" in text
        or "SECRET" in text
        or "TOKEN" in text
        or "PASSWORD" in text
        or "key" in text
        or "secret" in text
        or "token" in text
        or "password" in text
    ):
        text = _ENV_VAR_PATTERN[0].sub(_ENV_VAR_PATTERN[1], text)

    # 4. Kullanıcı Dizinleri (Windows, macOS, Linux)
    if "sers" in text or "/home/" in text:
        text = _PATH_PATTERN[0].sub(_PATH_PATTERN[1], text)

    # 6. Dinamik Kullanıcı Adı Koruması (Örn: Deniz)
    user_info = _get_dynamic_user_info()
    if user_info:
        current_user, user_pattern = user_info
        if current_user in text or current_user.lower() in text:
            text = user_pattern.sub(r"\g<1><REDACTED>\g<2>", text)

    return text



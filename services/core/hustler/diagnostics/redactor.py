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

# 1. Bearer Token ("earer" sabit öneki ile CPython SRE fastsearch devrede)
_BEARER_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"([Bb]earer\s+)[^\s\"'`]+"),
    r"\g<1>[REDACTED]",
)

# 2. OpenAI (sk-...) ve ElevenLabs (xi-...) API Anahtarları (sabit önek ile SIMD fastsearch)
_SK_KEYS_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"sk-(?:proj-)?[a-zA-Z0-9_\-]{16,}"),
    "[REDACTED]",
)
_XI_KEYS_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"xi-[a-zA-Z0-9_\-]{16,}"),
    "[REDACTED]",
)

# 3. Ortam değişkeni ve yapılandırma anahtar-değer çiftleri
_ENV_KEYWORDS: tuple[str, ...] = (
    "API_KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "api_key",
    "secret",
    "token",
    "password",
)
_ENV_COMBINED_PATTERN: re.Pattern[str] = re.compile(
    r"""(API_KEY|SECRET|TOKEN|PASSWORD|api_key|secret|token|password)\s*([=:]\s*)(["']?)([^"'\s\r\n]+)"""
)

# 4. Kullanıcı dizinleri: Windows/macOS ("sers" sabit iç-öneki) ve Linux ("/home/" sabit öneki)
_USERS_PATH_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"([Uu]sers(?:\\\\|\\|/))[^/\\,\"';:\r\n]+"),
    r"\g<1><REDACTED>",
)
_HOME_PATH_PATTERN: tuple[re.Pattern[str], str] = (
    re.compile(r"(/home/)[^/\\,\"';:\r\n]+"),
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


def _redact_user_paths(text: str) -> str:
    """Kullanıcı dizinlerini ve dinamik kullanıcı adlarını maskeler."""
    if "sers" in text:
        text = _USERS_PATH_PATTERN[0].sub(_USERS_PATH_PATTERN[1], text)
    if "/home/" in text:
        text = _HOME_PATH_PATTERN[0].sub(_HOME_PATH_PATTERN[1], text)

    user_info = _get_dynamic_user_info()
    if user_info:
        current_user, user_pattern = user_info
        if current_user in text or current_user.lower() in text:
            text = user_pattern.sub(r"\g<1><REDACTED>\g<2>", text)
    return text


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
    if "sk-" in text:
        text = _SK_KEYS_PATTERN[0].sub(_SK_KEYS_PATTERN[1], text)
    if "xi-" in text:
        text = _XI_KEYS_PATTERN[0].sub(_XI_KEYS_PATTERN[1], text)

    # 3. Ortam Değişkeni / Yapılandırma Anahtarları (Tek geçişli optimize Regex)
    if any(kw in text for kw in _ENV_KEYWORDS):
        text = _ENV_COMBINED_PATTERN.sub(r"\1\2\3[REDACTED]", text)

    # 4. Kullanıcı Dizinleri ve Dinamik İsimler
    return _redact_user_paths(text)



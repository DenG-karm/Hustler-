"""Bearer token doğrulaması — sidecar'ın tek yetkilendirme noktası."""

import secrets

from fastapi import HTTPException, Request

_BEARER_PREFIX = "Bearer "


def _unauthorized(detail: str, challenge: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": challenge},
    )


def verify_token(request: Request) -> None:
    """Eksik, bozuk veya yanlış token için 401 + WWW-Authenticate: Bearer döner."""
    expected: str = getattr(request.app.state, "session_token", "")
    if not expected:  # fail-closed: token yapılandırılmadan hiçbir istek geçemez
        raise _unauthorized("Authentication not configured", "Bearer")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith(_BEARER_PREFIX):
        raise _unauthorized("Missing bearer token", "Bearer")

    presented = auth.removeprefix(_BEARER_PREFIX)
    # constant-time karşılaştırma (bytes: ASCII dışı girişte TypeError olmasın)
    if not presented or not secrets.compare_digest(presented.encode(), expected.encode()):
        raise _unauthorized("Invalid bearer token", 'Bearer error="invalid_token"')

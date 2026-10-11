"""
Event Broker — K-703
FastAPI yan sürecinden gelen asenkron olayları (ilerleme, LLM uyarıları, loglar, iptal)
Server-Sent Events (SSE) istemcilerine güvenle dağıtır.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
import structlog

logger = structlog.get_logger()


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def subscribe(self) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        try:
            # İlk bağlantı el sıkışması
            handshake = json.dumps({"event": "connected", "message": "SSE akışına bağlandı"})
            yield f"data: {handshake}\n\n"

            while True:
                # 15 sn periyodik keep-alive pingle bağlantının düşmesini engeller
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._subscribers.discard(q)

    def broadcast(self, event_type: str, payload: dict[str, object]) -> None:
        """Tüm bağlı istemcilere JSON verisi fırlatır."""
        msg = json.dumps({"event": event_type, **payload})
        dead: list[asyncio.Queue[str]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for d in dead:
            self._subscribers.discard(d)

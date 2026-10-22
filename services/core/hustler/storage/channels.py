from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import sqlite3
import time
from typing import Optional
import uuid

import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()

# Kanal-Merkezli Mimari (Faz 2/2): channel_id ile kanala bağlanan tablolar
CHANNEL_LINKED_TABLES: tuple[str, ...] = ("scripts", "discovery_videos")


def _empty_metrics() -> dict[str, int | float]:
    return {"total_scripts": 0, "total_research": 0, "avg_viral_score": 0.0}


@dataclass
class Channel:
    id: str
    name: str
    channel_url: str
    description: str
    created_at: float
    metrics: dict[str, int | float] = field(default_factory=_empty_metrics)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "channel_url": self.channel_url,
            "description": self.description,
            "created_at": self.created_at,
            "metrics": dict(self.metrics),
        }


class ChannelMetricPair(tuple[Channel, dict[str, int | float]]):
    """(Channel, metrics) tuple'ı; geriye dönük erişim için .id ve .metrics sağlar."""

    @property
    def id(self) -> str:
        return self[0].id

    @property
    def metrics(self) -> dict[str, int | float]:
        return self[1]


def _coerce_score(raw: object) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    return 0.0


class ChannelRepository:
    """Kanal-Merkezli Mimari: SQLite channels Tablosu, İlişkisel Bağ ve Gerçek Metrikler."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def _table_columns(self, table_name: str) -> set[str]:
        """Verilen tablonun mevcut sütun adlarını döndürür."""
        reader = await self.db.get_reader()
        try:
            async with reader.execute(f"PRAGMA table_info({table_name});") as cursor:
                rows = await cursor.fetchall()
                return {str(row[1]) for row in rows}
        except sqlite3.OperationalError:
            return set()
        finally:
            await reader.close()

    async def init_table(self) -> None:
        """channels tablosunu başlatır ve bağlı tablolara channel_id göçünü güvenle uygular."""
        await self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                channel_url TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        await self.db.execute_write(
            "CREATE INDEX IF NOT EXISTS idx_channels_created ON channels(created_at DESC);"
        )

        await self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                script_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                full_text TEXT NOT NULL,
                scenes_json TEXT NOT NULL DEFAULT '[]',
                claims_json TEXT NOT NULL DEFAULT '[]',
                is_approved INTEGER NOT NULL DEFAULT 0,
                content_hash TEXT NOT NULL,
                updated_at REAL NOT NULL,
                channel_id TEXT
            );
            """
        )
        await self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS discovery_videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                topic TEXT,
                score REAL,
                discovered_at REAL,
                channel_id TEXT
            );
            """
        )

        for table in CHANNEL_LINKED_TABLES:
            cols = await self._table_columns(table)
            if "channel_id" not in cols:
                try:
                    await self.db.execute_write(
                        f"ALTER TABLE {table} ADD COLUMN channel_id TEXT;"
                    )
                    logger.info("channel_column_migrated", table=table)
                except sqlite3.OperationalError:
                    pass

        try:
            await self.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_scripts_channel ON scripts(channel_id);"
            )
        except sqlite3.OperationalError:
            pass

        try:
            await self.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_discovery_channel ON discovery_videos(channel_id);"
            )
        except sqlite3.OperationalError:
            pass

    async def create(
        self,
        name: str,
        channel_url: str,
        description: str,
        channel_id: Optional[str] = None,
    ) -> Channel:
        """Yeni bir kanal kaydı oluşturur."""
        cid = channel_id or f"chn_{uuid.uuid4().hex[:12]}"
        now = max(time.time(), getattr(self, "_last_created_at", 0.0) + 0.001)
        self._last_created_at = now
        await self.db.execute_write(
            """
            INSERT INTO channels (id, name, channel_url, description, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (cid, name, channel_url, description, now),
        )
        return Channel(
            id=cid,
            name=name,
            channel_url=channel_url,
            description=description,
            created_at=now,
        )

    async def list_all(self) -> list[Channel]:
        """Tüm kayıtlı kanalları en yeniden eskiye listeler."""
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                "SELECT id, name, channel_url, description, created_at FROM channels ORDER BY created_at DESC, rowid DESC;"
            ) as cursor:
                rows = await cursor.fetchall()
        finally:
            await reader.close()
        return [
            Channel(
                id=str(r[0]),
                name=str(r[1]),
                channel_url=str(r[2]),
                description=str(r[3]),
                created_at=float(str(r[4])),
            )
            for r in rows
        ]

    async def get_metrics(self, channel_id: str) -> dict[str, int | float]:
        """Tek bir kanalın metriklerini tek SQL sorgusuyla döndürür."""
        sql = """
            SELECT
              (SELECT COUNT(*) FROM scripts WHERE channel_id = ?) AS total_scripts,
              (SELECT COUNT(*) FROM discovery_videos WHERE channel_id = ?) AS total_research,
              (SELECT COALESCE(AVG(score), 0.0) FROM discovery_videos WHERE channel_id = ?) AS avg_viral_score;
        """
        reader = await self.db.get_reader()
        try:
            async with reader.execute(sql, (channel_id, channel_id, channel_id)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return _empty_metrics()
                return {
                    "total_scripts": int(str(row[0] or 0)),
                    "total_research": int(str(row[1] or 0)),
                    "avg_viral_score": round(float(str(row[2] or 0.0)), 1),
                }
        except sqlite3.OperationalError:
            return _empty_metrics()
        finally:
            await reader.close()

    async def list_all_with_metrics(
        self,
    ) -> list[tuple[Channel, dict[str, int | float]]]:
        """Alt sorgulu tek bir SELECT ile tüm kanalları ve metriklerini çeker."""
        sql = """
            SELECT c.id, c.name, c.channel_url, c.description, c.created_at,
                   COALESCE(s.script_count, 0) AS total_scripts,
                   COALESCE(d.research_count, 0) AS total_research,
                   ROUND(COALESCE(d.avg_score, 0.0), 1) AS avg_viral_score
            FROM channels c
            LEFT JOIN (
                SELECT channel_id, COUNT(*) AS script_count
                FROM scripts GROUP BY channel_id
            ) s ON s.channel_id = c.id
            LEFT JOIN (
                SELECT channel_id, COUNT(*) AS research_count, AVG(score) AS avg_score
                FROM discovery_videos GROUP BY channel_id
            ) d ON d.channel_id = c.id
            ORDER BY c.created_at DESC, c.rowid DESC;
        """
        reader = await self.db.get_reader()
        try:
            async with reader.execute(sql) as cursor:
                rows = await cursor.fetchall()
        except sqlite3.OperationalError:
            channels = await self.list_all()
            return [ChannelMetricPair((ch, _empty_metrics())) for ch in channels]
        finally:
            await reader.close()

        result: list[tuple[Channel, dict[str, int | float]]] = []
        for r in rows:
            metrics: dict[str, int | float] = {
                "total_scripts": int(str(r[5] or 0)),
                "total_research": int(str(r[6] or 0)),
                "avg_viral_score": round(float(str(r[7] or 0.0)), 1),
            }
            channel = Channel(
                id=str(r[0]),
                name=str(r[1]),
                channel_url=str(r[2]),
                description=str(r[3]),
                created_at=float(str(r[4])),
                metrics=metrics,
            )
            result.append(ChannelMetricPair((channel, metrics)))
        return result

    async def get_by_id(self, channel_id: str) -> Optional[Channel]:
        """Belirtilen kimliğe sahip kanalı döndürür, yoksa None."""
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                "SELECT id, name, channel_url, description, created_at FROM channels WHERE id = ?;",
                (channel_id,),
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            await reader.close()
        if not row:
            return None
        metrics = await self.get_metrics(channel_id)
        return Channel(
            id=str(row[0]),
            name=str(row[1]),
            channel_url=str(row[2]),
            description=str(row[3]),
            created_at=float(str(row[4])),
            metrics=metrics,
        )

    async def record_research(
        self,
        channel_id: str,
        topic: str,
        items: Sequence[dict[str, object]],
    ) -> int:
        """Keşif sonuçlarını channel_id ile discovery_videos tablosuna bağlar (upsert)."""
        now = time.time()
        params: list[tuple[object, ...]] = []
        for item in items:
            vid = item.get("video_id") or item.get("id")
            if not vid:
                continue
            params.append((
                str(vid),
                str(item.get("title") or ""),
                topic,
                _coerce_score(item.get("score")),
                now,
                channel_id,
            ))
        if not params:
            return 0
        await self.db.executemany_write(
            """
            INSERT INTO discovery_videos (video_id, title, topic, score, discovered_at, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                score = excluded.score,
                discovered_at = excluded.discovered_at,
                channel_id = excluded.channel_id
            """,
            params,
        )
        return len(params)

    async def delete(self, channel_id: str) -> bool:
        """Kanalı siler; mevcut değilse False, silindiyse True döner.

        Bağlı senaryo/araştırma kayıtları korunur, yalnızca kanal bağı (channel_id) çözülür.
        """
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                "SELECT 1 FROM channels WHERE id = ?;",
                (channel_id,),
            ) as cursor:
                exists = await cursor.fetchone()
        finally:
            await reader.close()

        if not exists:
            return False

        for table in CHANNEL_LINKED_TABLES:
            try:
                await self.db.execute_write(
                    f"UPDATE {table} SET channel_id = NULL WHERE channel_id = ?;",
                    (channel_id,),
                )
            except sqlite3.OperationalError:
                pass

        await self.db.execute_write(
            "DELETE FROM channels WHERE id = ?;",
            (channel_id,),
        )
        return True

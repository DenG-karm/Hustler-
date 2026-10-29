from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import json
import sqlite3
import time
from typing import Optional
import uuid

import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()

# Kanal-Merkezli Mimari (Faz 2/2): channel_id ile kanala bağlanan tablolar
CHANNEL_LINKED_TABLES: tuple[str, ...] = ("scripts", "discovery_videos")


@dataclass
class ChannelTemplate:
    id: str
    channel_id: str
    title: str
    base_video_path: str
    duration_sec: float = 15.0
    slots: list[dict[str, object]] = field(default_factory=list)
    narration_script: str = ""
    subtitle_cues: list[dict[str, object]] = field(default_factory=list)
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    audio_path: str = ""
    ass_path: str = ""
    rendered_output_path: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "title": self.title,
            "base_video_path": self.base_video_path,
            "duration_sec": self.duration_sec,
            "slots": list(self.slots),
            "narration_script": self.narration_script,
            "subtitle_cues": list(self.subtitle_cues),
            "voice_id": self.voice_id,
            "audio_path": self.audio_path,
            "ass_path": self.ass_path,
            "rendered_output_path": self.rendered_output_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


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

        await self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS channel_templates (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                base_video_path TEXT NOT NULL,
                duration_sec REAL NOT NULL DEFAULT 15.0,
                slots_json TEXT NOT NULL DEFAULT '[]',
                narration_script TEXT NOT NULL DEFAULT '',
                subtitle_cues_json TEXT NOT NULL DEFAULT '[]',
                voice_id TEXT NOT NULL DEFAULT '21m00Tcm4TlvDq8ikWAM',
                audio_path TEXT NOT NULL DEFAULT '',
                ass_path TEXT NOT NULL DEFAULT '',
                rendered_output_path TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        await self.db.execute_write(
            "CREATE INDEX IF NOT EXISTS idx_templates_channel ON channel_templates(channel_id, created_at DESC);"
        )

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
            "DELETE FROM channel_templates WHERE channel_id = ?;",
            (channel_id,),
        )
        await self.db.execute_write(
            "DELETE FROM channels WHERE id = ?;",
            (channel_id,),
        )
        return True

    @staticmethod
    def _row_to_template(r: Sequence[object]) -> ChannelTemplate:
        try:
            slots_raw = json.loads(str(r[5] or "[]"))
            slots = [s for s in slots_raw if isinstance(s, dict)] if isinstance(slots_raw, list) else []
        except Exception:
            slots = []
        try:
            cues_raw = json.loads(str(r[7] or "[]"))
            cues = [c for c in cues_raw if isinstance(c, dict)] if isinstance(cues_raw, list) else []
        except Exception:
            cues = []
        return ChannelTemplate(
            id=str(r[0]),
            channel_id=str(r[1]),
            title=str(r[2]),
            base_video_path=str(r[3]),
            duration_sec=float(str(r[4]) if r[4] is not None else 15.0),
            slots=slots,
            narration_script=str(r[6] or ""),
            subtitle_cues=cues,
            voice_id=str(r[8] or "21m00Tcm4TlvDq8ikWAM"),
            audio_path=str(r[9] or ""),
            ass_path=str(r[10] or ""),
            rendered_output_path=str(r[11] or ""),
            created_at=float(str(r[12]) if r[12] is not None else 0.0),
            updated_at=float(str(r[13]) if r[13] is not None else 0.0),
        )

    @staticmethod
    def _pick(val: Optional[str], fallback: str) -> str:
        return val if val is not None else fallback

    async def create_template(
        self,
        channel_id: str,
        title: str,
        base_video_path: str,
        duration_sec: float = 15.0,
        slots: Optional[list[dict[str, object]]] = None,
        narration_script: str = "",
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        template_id: Optional[str] = None,
    ) -> ChannelTemplate:
        tid = template_id or f"tpl_{uuid.uuid4().hex[:10]}"
        now = time.time()
        clean_slots = slots or []
        await self.db.execute_write(
            """
            INSERT INTO channel_templates (
                id, channel_id, title, base_video_path, duration_sec,
                slots_json, narration_script, subtitle_cues_json, voice_id,
                audio_path, ass_path, rendered_output_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, '', '', '', ?, ?);
            """,
            (
                tid,
                channel_id,
                title,
                base_video_path,
                duration_sec,
                json.dumps(clean_slots, ensure_ascii=False),
                narration_script,
                voice_id,
                now,
                now,
            ),
        )
        return ChannelTemplate(
            id=tid,
            channel_id=channel_id,
            title=title,
            base_video_path=base_video_path,
            duration_sec=duration_sec,
            slots=clean_slots,
            narration_script=narration_script,
            voice_id=voice_id,
            created_at=now,
            updated_at=now,
        )

    async def list_templates(self, channel_id: str) -> list[ChannelTemplate]:
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT id, channel_id, title, base_video_path, duration_sec,
                       slots_json, narration_script, subtitle_cues_json, voice_id,
                       audio_path, ass_path, rendered_output_path, created_at, updated_at
                FROM channel_templates
                WHERE channel_id = ?
                ORDER BY created_at DESC, rowid DESC;
                """,
                (channel_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            await reader.close()
        return [self._row_to_template(r) for r in rows]

    async def get_template(self, channel_id: str, template_id: str) -> Optional[ChannelTemplate]:
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT id, channel_id, title, base_video_path, duration_sec,
                       slots_json, narration_script, subtitle_cues_json, voice_id,
                       audio_path, ass_path, rendered_output_path, created_at, updated_at
                FROM channel_templates
                WHERE id = ? AND channel_id = ?;
                """,
                (template_id, channel_id),
            ) as cursor:
                row = await cursor.fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            await reader.close()
        return self._row_to_template(row) if row else None

    async def update_template(
        self,
        channel_id: str,
        template_id: str,
        *,
        title: Optional[str] = None,
        duration_sec: Optional[float] = None,
        slots: Optional[list[dict[str, object]]] = None,
        narration_script: Optional[str] = None,
        subtitle_cues: Optional[list[dict[str, object]]] = None,
        voice_id: Optional[str] = None,
        audio_path: Optional[str] = None,
        ass_path: Optional[str] = None,
        rendered_output_path: Optional[str] = None,
    ) -> Optional[ChannelTemplate]:
        ex = await self.get_template(channel_id, template_id)
        if ex is None:
            return None
        now = time.time()
        await self.db.execute_write(
            """
            UPDATE channel_templates
            SET title = ?, duration_sec = ?, slots_json = ?, narration_script = ?,
                subtitle_cues_json = ?, voice_id = ?, audio_path = ?, ass_path = ?,
                rendered_output_path = ?, updated_at = ?
            WHERE id = ? AND channel_id = ?;
            """,
            (
                self._pick(title, ex.title),
                duration_sec if duration_sec is not None else ex.duration_sec,
                json.dumps(slots if slots is not None else ex.slots, ensure_ascii=False),
                self._pick(narration_script, ex.narration_script),
                json.dumps(subtitle_cues if subtitle_cues is not None else ex.subtitle_cues, ensure_ascii=False),
                self._pick(voice_id, ex.voice_id),
                self._pick(audio_path, ex.audio_path),
                self._pick(ass_path, ex.ass_path),
                self._pick(rendered_output_path, ex.rendered_output_path),
                now,
                template_id,
                channel_id,
            ),
        )
        return await self.get_template(channel_id, template_id)

    async def delete_template(self, channel_id: str, template_id: str) -> bool:
        existing = await self.get_template(channel_id, template_id)
        if existing is None:
            return False
        await self.db.execute_write(
            "DELETE FROM channel_templates WHERE id = ? AND channel_id = ?;",
            (template_id, channel_id),
        )
        return True

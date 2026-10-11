import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional, Sequence
import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()


@dataclass
class ScriptRecord:
    script_id: str
    title: str
    full_text: str
    scenes_json: str
    claims_json: str
    is_approved: bool
    content_hash: str
    updated_at: float


class ScriptRepository:
    """K-704 Idempotent Senaryo Deposu.
    
    Aynı id ve içerik tekrar gönderildiğinde sistem çökmeden ve fazladan kaynak
    tüketmeden başarılı yanıt döner (is_idempotent=True).
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def init_table(self) -> None:
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
                updated_at REAL NOT NULL
            )
            """
        )

    @staticmethod
    def compute_hash(
        title: str,
        full_text: str,
        scenes_json: str,
        claims_json: str,
        is_approved: bool,
    ) -> str:
        raw = f"{title.strip()}|{full_text.strip()}|{scenes_json}|{claims_json}|{int(is_approved)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def get(self, script_id: str) -> Optional[ScriptRecord]:
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT script_id, title, full_text, scenes_json, claims_json,
                       is_approved, content_hash, updated_at
                FROM scripts WHERE script_id = ?
                """,
                (script_id,),
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            await reader.close()

        if not row:
            return None

        return _to_record(row)

    async def save(
        self,
        script_id: str,
        title: str,
        full_text: str,
        scenes: Sequence[object] = (),
        claims: Sequence[object] = (),
        is_approved: bool = False,
    ) -> dict[str, object]:
        """Senaryoyu kaydeder.
        
        Eğer gelen içerik veritabanındakiyle birebir aynıysa hiçbir disk/yazma
        işlemi yapmadan idempotent yanıt (UNCHANGED) döner.
        """
        scenes_json = json.dumps(list(scenes), ensure_ascii=False)
        claims_json = json.dumps(list(claims), ensure_ascii=False)
        content_hash = self.compute_hash(title, full_text, scenes_json, claims_json, is_approved)

        existing = await self.get(script_id)
        if existing is not None and existing.content_hash == content_hash:
            logger.info("script_save_idempotent_hit", script_id=script_id, hash=content_hash)
            return {
                "status": "UNCHANGED",
                "script_id": script_id,
                "is_idempotent": True,
                "content_hash": content_hash,
                "updated_at": existing.updated_at,
            }

        now = time.time()
        await self.db.execute_write(
            """
            INSERT INTO scripts (script_id, title, full_text, scenes_json, claims_json,
                                is_approved, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(script_id) DO UPDATE SET
                title = excluded.title,
                full_text = excluded.full_text,
                scenes_json = excluded.scenes_json,
                claims_json = excluded.claims_json,
                is_approved = excluded.is_approved,
                content_hash = excluded.content_hash,
                updated_at = excluded.updated_at
            """,
            (
                script_id,
                title,
                full_text,
                scenes_json,
                claims_json,
                1 if is_approved else 0,
                content_hash,
                now,
            ),
        )
        logger.info("script_saved", script_id=script_id, hash=content_hash)
        return {
            "status": "SAVED",
            "script_id": script_id,
            "is_idempotent": True,
            "content_hash": content_hash,
            "updated_at": now,
        }


def _to_record(row: Sequence[object]) -> ScriptRecord:
    return ScriptRecord(
        script_id=str(row[0]),
        title=str(row[1]),
        full_text=str(row[2]),
        scenes_json=str(row[3]),
        claims_json=str(row[4]),
        is_approved=bool(row[5]),
        content_hash=str(row[6]),
        updated_at=float(str(row[7])),
    )

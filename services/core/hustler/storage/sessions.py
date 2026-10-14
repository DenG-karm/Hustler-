"""
K-802: Proje Oturumu ve Çökme Kurtarma Deposu (State Rehydration & Checkpoint Recovery)
- Uygulama veya sidecar çöktüğünde RUNNING veya RENDERING durumunda asılı kalan projeleri
  tespit eder ve veri kaybı olmadan son tamamlanan kararlı adıma (checkpoint) döndürür.
- Frontend rehydrateFromBackend() çağrısı için oturum durumunu kalıcı kılar.
"""

import json
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence
import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()


@dataclass
class ProjectSession:
    session_id: str
    topic: str
    current_step: str
    checkpoint_step: str
    status: str  # 'IDLE' | 'RUNNING' | 'RENDERING' | 'COMPLETED' | 'RECOVERED'
    selected_idea: Optional[dict[str, object]]
    ideas: list[dict[str, object]]
    script: Optional[dict[str, object]]
    audio: Optional[dict[str, object]]
    assets: Optional[dict[str, object]]
    preview: Optional[dict[str, object]]
    render: Optional[dict[str, object]]
    last_error: Optional[str]
    updated_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "current_step": self.current_step,
            "checkpoint_step": self.checkpoint_step,
            "status": self.status,
            "selected_idea": self.selected_idea,
            "ideas": self.ideas,
            "script": self.script,
            "audio": self.audio,
            "assets": self.assets,
            "preview": self.preview,
            "render": self.render,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }


class ProjectSessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def init_table(self) -> None:
        await self.db.execute_write(
            """
            CREATE TABLE IF NOT EXISTS project_sessions (
                session_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                current_step TEXT NOT NULL,
                checkpoint_step TEXT NOT NULL,
                status TEXT NOT NULL,
                selected_idea_json TEXT,
                ideas_json TEXT,
                script_json TEXT,
                audio_json TEXT,
                assets_json TEXT,
                preview_json TEXT,
                render_json TEXT,
                last_error TEXT,
                updated_at REAL NOT NULL
            );
            """
        )
        await self.db.execute_write(
            "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON project_sessions(updated_at DESC);"
        )

    async def save_session(
        self,
        topic: str,
        current_step: str,
        checkpoint_step: str,
        status: str,
        session_id: Optional[str] = None,
        selected_idea: Optional[dict[str, object]] = None,
        ideas: Optional[Sequence[dict[str, object]]] = None,
        script: Optional[dict[str, object]] = None,
        audio: Optional[dict[str, object]] = None,
        assets: Optional[dict[str, object]] = None,
        preview: Optional[dict[str, object]] = None,
        render: Optional[dict[str, object]] = None,
        last_error: Optional[str] = None,
    ) -> ProjectSession:
        sid = session_id or uuid.uuid4().hex[:12]
        now = time.time()

        s_idea_json = json.dumps(selected_idea, ensure_ascii=False) if selected_idea else None
        ideas_json = json.dumps(list(ideas), ensure_ascii=False) if ideas else "[]"
        script_json = json.dumps(script, ensure_ascii=False) if script else None
        audio_json = json.dumps(audio, ensure_ascii=False) if audio else None
        assets_json = json.dumps(assets, ensure_ascii=False) if assets else None
        preview_json = json.dumps(preview, ensure_ascii=False) if preview else None
        render_json = json.dumps(render, ensure_ascii=False) if render else None

        query = """
            INSERT INTO project_sessions (
                session_id, topic, current_step, checkpoint_step, status,
                selected_idea_json, ideas_json, script_json, audio_json,
                assets_json, preview_json, render_json, last_error, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                topic = excluded.topic,
                current_step = excluded.current_step,
                checkpoint_step = excluded.checkpoint_step,
                status = excluded.status,
                selected_idea_json = excluded.selected_idea_json,
                ideas_json = excluded.ideas_json,
                script_json = excluded.script_json,
                audio_json = excluded.audio_json,
                assets_json = excluded.assets_json,
                preview_json = excluded.preview_json,
                render_json = excluded.render_json,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at;
        """
        await self.db.execute_write(
            query,
            (
                sid,
                topic,
                current_step,
                checkpoint_step,
                status,
                s_idea_json,
                ideas_json,
                script_json,
                audio_json,
                assets_json,
                preview_json,
                render_json,
                last_error,
                now,
            ),
        )

        return ProjectSession(
            session_id=sid,
            topic=topic,
            current_step=current_step,
            checkpoint_step=checkpoint_step,
            status=status,
            selected_idea=selected_idea,
            ideas=list(ideas or []),
            script=script,
            audio=audio,
            assets=assets,
            preview=preview,
            render=render,
            last_error=last_error,
            updated_at=now,
        )

    async def get_active_session(self) -> Optional[ProjectSession]:
        """En son güncellenen aktif veya kurtarılmış oturumu getirir."""
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT session_id, topic, current_step, checkpoint_step, status,
                       selected_idea_json, ideas_json, script_json, audio_json,
                       assets_json, preview_json, render_json, last_error, updated_at
                FROM project_sessions
                ORDER BY updated_at DESC
                LIMIT 1;
                """
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            await reader.close()

        if not row:
            return None

        return _row_to_session(list(row))

    async def get_session(self, session_id: str) -> Optional[ProjectSession]:
        """Belirtilen session_id'ye ait oturumu getirir."""
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT session_id, topic, current_step, checkpoint_step, status,
                       selected_idea_json, ideas_json, script_json, audio_json,
                       assets_json, preview_json, render_json, last_error, updated_at
                FROM project_sessions
                WHERE session_id = ?;
                """,
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            await reader.close()

        if not row:
            return None

        return _row_to_session(list(row))

    async def recover_interrupted_sessions(self) -> int:
        """
        Çökme kurtarma mekanizması:
        RUNNING veya RENDERING durumunda asılı kalan işleri tespit eder ve veri kaybı
        olmadan son tamamlanan kararlı adıma (checkpoint_step) döndürür.
        """
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                """
                SELECT session_id, checkpoint_step, topic, current_step
                FROM project_sessions
                WHERE status IN ('RUNNING', 'RENDERING');
                """
            ) as cursor:
                interrupted = list(await cursor.fetchall())
        finally:
            await reader.close()

        if not interrupted:
            return 0

        now = time.time()
        for item in interrupted:
            session_id = str(item[0])
            checkpoint_step = str(item[1])
            topic = str(item[2])
            old_step = str(item[3])

            logger.warn(
                "recovering_interrupted_session",
                session_id=session_id,
                topic=topic,
                interrupted_step=old_step,
                recovered_to=checkpoint_step,
            )
            await self.db.execute_write(
                """
                UPDATE project_sessions
                SET status = 'RECOVERED',
                    current_step = checkpoint_step,
                    last_error = 'Sistem beklenmedik şekilde sonlandı; oturum son kararlı noktaya kurtarıldı.',
                    updated_at = ?
                WHERE session_id = ?;
                """,
                (now, session_id),
            )

        return len(interrupted)


def _row_to_session(row: Sequence[object]) -> ProjectSession:
    def _parse_dict(val: object) -> Optional[dict[str, object]]:
        if not val or not isinstance(val, str):
            return None
        parsed = json.loads(val)
        return dict(parsed) if isinstance(parsed, dict) else None

    def _parse_list(val: object) -> list[dict[str, object]]:
        if not val or not isinstance(val, str):
            return []
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return [dict(x) for x in parsed if isinstance(x, dict)]
        return []

    return ProjectSession(
        session_id=str(row[0]),
        topic=str(row[1]),
        current_step=str(row[2]),
        checkpoint_step=str(row[3]),
        status=str(row[4]),
        selected_idea=_parse_dict(row[5]),
        ideas=_parse_list(row[6]),
        script=_parse_dict(row[7]),
        audio=_parse_dict(row[8]),
        assets=_parse_dict(row[9]),
        preview=_parse_dict(row[10]),
        render=_parse_dict(row[11]),
        last_error=str(row[12]) if row[12] else None,
        updated_at=float(str(row[13])),
    )

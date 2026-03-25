import json
import uuid
from pathlib import Path

import asyncpg

_pool: asyncpg.Pool | None = None

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


async def init_pool(database_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(database_url)
    async with _pool.acquire() as conn:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            await conn.execute(sql_file.read_text())


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized"
    return _pool


async def upsert_session(session_id: uuid.UUID) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            session_id,
        )


async def create_conversation(session_id: uuid.UUID) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO conversations (session_id) VALUES ($1) RETURNING id, title, created_at, updated_at",
            session_id,
        )
        return dict(row)


async def list_conversations(session_id: uuid.UUID) -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE session_id = $1 ORDER BY updated_at DESC",
            session_id,
        )
        return [dict(r) for r in rows]


async def get_conversation(conversation_id: uuid.UUID, session_id: uuid.UUID) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = $1 AND session_id = $2",
            conversation_id, session_id,
        )
        if not conv:
            return None
        messages = await conn.fetch(
            "SELECT id, role, content, code, images, chart, artifact, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
            conversation_id,
        )
        artifacts = await conn.fetch(
            "SELECT id, artifact_id, title, type, version, code, images, chart, created_at FROM artifacts WHERE conversation_id = $1 ORDER BY artifact_id, version ASC",
            conversation_id,
        )
        return {
            **dict(conv),
            "messages": [_row_to_dict(m) for m in messages],
            "artifacts": [_row_to_dict(a) for a in artifacts],
        }


async def delete_conversation(conversation_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    pool = _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM conversations WHERE id = $1 AND session_id = $2",
            conversation_id, session_id,
        )
        return result == "DELETE 1"


async def update_conversation_title(conversation_id: uuid.UUID, title: str) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET title = $1, updated_at = now() WHERE id = $2",
            title, conversation_id,
        )


async def touch_conversation(conversation_id: uuid.UUID) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE conversations SET updated_at = now() WHERE id = $1", conversation_id)


async def save_message(
    conversation_id: uuid.UUID, role: str, content: str,
    code: str | None = None, images: list[str] | None = None,
    chart: dict | None = None, artifact: dict | None = None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO messages (conversation_id, role, content, code, images, chart, artifact)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb)
               RETURNING id, role, content, code, images, chart, artifact, created_at""",
            conversation_id, role, content, code,
            json.dumps(images) if images else None,
            json.dumps(chart) if chart else None,
            json.dumps(artifact) if artifact else None,
        )
        return _row_to_dict(row)


async def get_message_history(conversation_id: uuid.UUID) -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
            conversation_id,
        )
        return [dict(r) for r in rows]


async def save_artifact(
    conversation_id: uuid.UUID, artifact_id: str, title: str, type: str, version: int,
    code: str | None = None, images: list[str] | None = None, chart: dict | None = None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO artifacts (conversation_id, artifact_id, title, type, version, code, images, chart)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
               RETURNING id, artifact_id, title, type, version, code, images, chart, created_at""",
            conversation_id, artifact_id, title, type, version, code,
            json.dumps(images) if images else None,
            json.dumps(chart) if chart else None,
        )
        return _row_to_dict(row)


async def get_artifact_descriptors(conversation_id: uuid.UUID) -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT ON (artifact_id) artifact_id, title, type
               FROM artifacts WHERE conversation_id = $1
               ORDER BY artifact_id, version DESC""",
            conversation_id,
        )
        return [dict(r) for r in rows]


async def next_artifact_version(conversation_id: uuid.UUID, artifact_id: str) -> int:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM artifacts WHERE conversation_id = $1 AND artifact_id = $2",
            conversation_id, artifact_id,
        )
        return row["next_version"]


def _row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    for key in ("images", "chart", "artifact"):
        if key in d and isinstance(d[key], str):
            d[key] = json.loads(d[key])
    return d

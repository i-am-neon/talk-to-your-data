import os
import uuid
from pathlib import Path

import asyncpg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dataagent_test")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            await conn.execute(sql_file.read_text())
    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
async def clean_tables(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM artifacts")
        await conn.execute("DELETE FROM messages")
        await conn.execute("DELETE FROM conversations")
        await conn.execute("DELETE FROM sessions")
    yield


@pytest.fixture
def session_id():
    return uuid.uuid4()

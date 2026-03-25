import os
import uuid

import asyncpg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dataagent_test")


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(DATABASE_URL)
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_create_tables.sql")
    async with pool.acquire() as conn:
        with open(migration_path) as f:
            await conn.execute(f.read())
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

# Conversation History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent conversation history with a sidebar UI, backed by PostgreSQL, so users can browse, switch between, and delete past conversations.

**Architecture:** New `db.py` module with asyncpg connection pool + raw SQL. Four new REST endpoints for conversation CRUD. Existing `POST /api/query` extended to persist messages. Frontend gains a sidebar component and two new hooks (`useSession`, `useConversations`), with `useChat` and `useArtifacts` modified to load from the API.

**Tech Stack:** asyncpg, PostgreSQL, FastAPI, React, shadcn/ui, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-25-conversation-history-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/app/db.py` | asyncpg connection pool lifecycle (init/close), all SQL query functions |
| `backend/app/routes/conversations.py` | CRUD endpoints: list, create, get, delete conversations |
| `backend/migrations/001_create_tables.sql` | DDL for sessions, conversations, messages, artifacts tables + indexes |
| `backend/tests/test_conversations.py` | Tests for conversation CRUD endpoints |
| `backend/tests/test_db.py` | Tests for db module query functions |
| `backend/tests/conftest.py` | Shared test fixtures (test DB, cleanup) |

### Backend — Modified Files

| File | Change |
|------|--------|
| `backend/app/config.py` | Add `database_url` setting |
| `backend/app/main.py` | Add lifespan for DB pool init/close, register conversations router |
| `backend/app/routes/query.py` | Remove `history`/`artifacts` from request, add `conversation_id`, persist messages + artifacts to DB, load history from DB |
| `backend/.env.example` | Add `DATABASE_URL` |
| `backend/pyproject.toml` | Add `asyncpg` dependency |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/hooks/useSession.ts` | Generate/retrieve session UUID from localStorage |
| `frontend/src/hooks/useConversations.ts` | Fetch conversation list, create/select/delete conversations |
| `frontend/src/components/Sidebar.tsx` | Sidebar with conversation list, new chat button, collapse toggle |

### Frontend — Modified Files

| File | Change |
|------|--------|
| `frontend/src/types.ts` | Update `QueryRequest`/`QueryResponse`, add conversation types |
| `frontend/src/lib/api.ts` | Add session header to all requests, add conversation API functions |
| `frontend/src/hooks/useChat.ts` | Accept `conversationId`, load history from API, send `conversation_id` with query |
| `frontend/src/hooks/useArtifacts.ts` | Accept `conversationId`, load artifacts from API on conversation switch |
| `frontend/src/App.tsx` | Three-pane layout with sidebar, wire up conversation state |

---

## Task 1: Database Migration and Config

**Files:**
- Create: `backend/migrations/001_create_tables.sql`
- Modify: `backend/app/config.py:17-28`
- Modify: `backend/.env.example`
- Modify: `backend/pyproject.toml:6-14`

- [ ] **Step 1: Create migration SQL file**

```sql
-- backend/migrations/001_create_tables.sql

CREATE TABLE IF NOT EXISTS sessions (
    id         UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    code            TEXT,
    images          JSONB,
    artifact        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    artifact_id     TEXT NOT NULL,
    title           TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('chart', 'table', 'code')),
    version         INTEGER NOT NULL,
    code            TEXT,
    images          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_artifacts_conversation ON artifacts(conversation_id, artifact_id, version);
```

- [ ] **Step 2: Add `database_url` to Settings and `asyncpg` to dependencies**

In `backend/app/config.py`, add to the `Settings` class:

```python
database_url: str = ""
```

In `backend/.env.example`, add:

```
DATABASE_URL=postgresql://user:password@localhost:5432/dataagent
```

In `backend/pyproject.toml`, add `"asyncpg>=0.30"` to the `dependencies` list.

- [ ] **Step 3: Install the new dependency**

Run: `cd backend && uv sync`

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/ backend/app/config.py backend/.env.example backend/pyproject.toml backend/uv.lock
git commit -m "feat: add database migration, config, and asyncpg dependency"
```

---

## Task 2: Database Module (`db.py`)

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_db.py`
- Modify: `backend/app/main.py:1-23`

- [ ] **Step 1: Write tests for the db module**

Create `backend/tests/conftest.py`:

```python
import asyncio
import os
import uuid

import asyncpg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/dataagent_test")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(DATABASE_URL)

    # Run migration
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "001_create_tables.sql")
    async with pool.acquire() as conn:
        with open(migration_path) as f:
            await conn.execute(f.read())

    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
async def clean_tables(db_pool):
    """Clean all tables before each test."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM artifacts")
        await conn.execute("DELETE FROM messages")
        await conn.execute("DELETE FROM conversations")
        await conn.execute("DELETE FROM sessions")
    yield


@pytest.fixture
def session_id():
    return uuid.uuid4()
```

Create `backend/tests/test_db.py`:

```python
import uuid
import pytest
from app import db

pytestmark = pytest.mark.asyncio


async def test_upsert_session(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    # Second call should not raise
    await db.upsert_session(session_id)


async def test_create_and_list_conversations(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)

    conv = await db.create_conversation(session_id)
    assert conv["id"] is not None
    assert conv["title"] is None

    convs = await db.list_conversations(session_id)
    assert len(convs) == 1
    assert convs[0]["id"] == conv["id"]


async def test_get_conversation(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    result = await db.get_conversation(conv["id"], session_id)
    assert result is not None
    assert result["messages"] == []
    assert result["artifacts"] == []


async def test_get_conversation_wrong_session(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    other_session = uuid.uuid4()
    await db.upsert_session(other_session)
    result = await db.get_conversation(conv["id"], other_session)
    assert result is None


async def test_delete_conversation(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    deleted = await db.delete_conversation(conv["id"], session_id)
    assert deleted is True

    convs = await db.list_conversations(session_id)
    assert len(convs) == 0


async def test_save_and_load_messages(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    await db.save_message(conv["id"], "user", "What is revenue?")
    await db.save_message(conv["id"], "assistant", "Revenue is $1M", code="print(df.sum())", images=["base64img"])

    result = await db.get_conversation(conv["id"], session_id)
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][1]["code"] == "print(df.sum())"
    assert result["messages"][1]["images"] == ["base64img"]


async def test_save_artifact_version(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    await db.save_artifact(conv["id"], "art-1", "Revenue Chart", "chart", 1, code="plt.show()", images=["img1"])
    await db.save_artifact(conv["id"], "art-1", "Revenue Chart v2", "chart", 2, code="plt.bar()", images=["img2"])

    result = await db.get_conversation(conv["id"], session_id)
    assert len(result["artifacts"]) == 2
    assert result["artifacts"][0]["version"] == 1
    assert result["artifacts"][1]["version"] == 2


async def test_update_conversation_title(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    await db.update_conversation_title(conv["id"], "My Analysis")
    convs = await db.list_conversations(session_id)
    assert convs[0]["title"] == "My Analysis"


async def test_get_message_history(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    await db.save_message(conv["id"], "user", "Question 1")
    await db.save_message(conv["id"], "assistant", "Answer 1")
    await db.save_message(conv["id"], "user", "Question 2")

    history = await db.get_message_history(conv["id"])
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[2]["content"] == "Question 2"


async def test_get_artifact_descriptors(db_pool, session_id):
    db._pool = db_pool
    await db.upsert_session(session_id)
    conv = await db.create_conversation(session_id)

    await db.save_artifact(conv["id"], "art-1", "Chart 1", "chart", 1)
    await db.save_artifact(conv["id"], "art-1", "Chart 1 v2", "chart", 2)
    await db.save_artifact(conv["id"], "art-2", "Table 1", "table", 1)

    descriptors = await db.get_artifact_descriptors(conv["id"])
    assert len(descriptors) == 2
    # Should return latest title per artifact_id
    assert any(d["artifact_id"] == "art-1" for d in descriptors)
    assert any(d["artifact_id"] == "art-2" for d in descriptors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: FAIL — `app.db` does not exist yet

- [ ] **Step 3: Implement `db.py`**

Create `backend/app/db.py`:

```python
import json
import uuid
from pathlib import Path

import asyncpg

_pool: asyncpg.Pool | None = None

MIGRATION_PATH = Path(__file__).resolve().parent.parent / "migrations" / "001_create_tables.sql"


async def init_pool(database_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(database_url)
    async with _pool.acquire() as conn:
        await conn.execute(MIGRATION_PATH.read_text())


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized"
    return _pool


# ---- Sessions ----

async def upsert_session(session_id: uuid.UUID) -> None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            session_id,
        )


# ---- Conversations ----

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
            "SELECT id, role, content, code, images, artifact, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
            conversation_id,
        )
        artifacts = await conn.fetch(
            "SELECT id, artifact_id, title, type, version, code, images, created_at FROM artifacts WHERE conversation_id = $1 ORDER BY artifact_id, version ASC",
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
        await conn.execute(
            "UPDATE conversations SET updated_at = now() WHERE id = $1",
            conversation_id,
        )


# ---- Messages ----

async def save_message(
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    code: str | None = None,
    images: list[str] | None = None,
    artifact: dict | None = None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO messages (conversation_id, role, content, code, images, artifact)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
               RETURNING id, role, content, code, images, artifact, created_at""",
            conversation_id, role, content, code,
            json.dumps(images) if images else None,
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


# ---- Artifacts ----

async def save_artifact(
    conversation_id: uuid.UUID,
    artifact_id: str,
    title: str,
    type: str,
    version: int,
    code: str | None = None,
    images: list[str] | None = None,
) -> dict:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO artifacts (conversation_id, artifact_id, title, type, version, code, images)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
               RETURNING id, artifact_id, title, type, version, code, images, created_at""",
            conversation_id, artifact_id, title, type, version, code,
            json.dumps(images) if images else None,
        )
        return _row_to_dict(row)


async def get_artifact_descriptors(conversation_id: uuid.UUID) -> list[dict]:
    """Get the latest title/type for each distinct artifact_id in a conversation."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT ON (artifact_id) artifact_id, title, type
               FROM artifacts
               WHERE conversation_id = $1
               ORDER BY artifact_id, version DESC""",
            conversation_id,
        )
        return [dict(r) for r in rows]


# ---- Helpers ----

async def next_artifact_version(conversation_id: uuid.UUID, artifact_id: str) -> int:
    """Return the next version number for an artifact in a conversation."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM artifacts WHERE conversation_id = $1 AND artifact_id = $2",
            conversation_id, artifact_id,
        )
        return row["next_version"]


def _row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    # asyncpg returns JSONB as parsed Python objects already
    return d
```

- [ ] **Step 4: Wire up DB pool in `main.py` with lifespan**

Replace `backend/app/main.py` with:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.routes.query import router as query_router
from app.routes.conversations import router as conversations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        await db.init_pool(settings.database_url)
    yield
    await db.close_pool()


app = FastAPI(title="Data Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(conversations_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

Note: the conversations router doesn't exist yet — create a placeholder `backend/app/routes/conversations.py`:

```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql://localhost:5432/dataagent_test uv run pytest tests/test_db.py -v`
Expected: All tests PASS

Also run existing tests to make sure nothing broke:
Run: `cd backend && uv run pytest tests/test_query.py tests/test_loader.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db.py backend/app/main.py backend/app/routes/conversations.py backend/tests/conftest.py backend/tests/test_db.py
git commit -m "feat: add database module with connection pool and query functions"
```

---

## Task 3: Conversation CRUD Endpoints

**Files:**
- Modify: `backend/app/routes/conversations.py`
- Create: `backend/tests/test_conversations.py`

- [ ] **Step 1: Write tests for conversation endpoints**

Create `backend/tests/test_conversations.py`:

```python
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app import db

pytestmark = pytest.mark.asyncio

SESSION_ID = str(uuid.uuid4())
HEADERS = {"X-Session-ID": SESSION_ID}


@pytest.fixture
async def client(db_pool):
    db._pool = db_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_conversation(client):
    resp = await client.post("/api/conversations", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["title"] is None


async def test_list_conversations(client):
    await client.post("/api/conversations", headers=HEADERS)
    await client.post("/api/conversations", headers=HEADERS)

    resp = await client.get("/api/conversations", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


async def test_get_conversation(client):
    create_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = create_resp.json()["id"]

    resp = await client.get(f"/api/conversations/{conv_id}", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conv_id
    assert data["messages"] == []
    assert data["artifacts"] == []


async def test_get_conversation_wrong_session(client):
    create_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = create_resp.json()["id"]

    other_headers = {"X-Session-ID": str(uuid.uuid4())}
    resp = await client.get(f"/api/conversations/{conv_id}", headers=other_headers)
    assert resp.status_code == 404


async def test_delete_conversation(client):
    create_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/conversations/{conv_id}", headers=HEADERS)
    assert resp.status_code == 204

    resp = await client.get(f"/api/conversations/{conv_id}", headers=HEADERS)
    assert resp.status_code == 404


async def test_missing_session_header(client):
    resp = await client.get("/api/conversations")
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL=postgresql://localhost:5432/dataagent_test uv run pytest tests/test_conversations.py -v`
Expected: FAIL — endpoints not implemented

- [ ] **Step 3: Implement conversation endpoints**

Replace `backend/app/routes/conversations.py`:

```python
import uuid

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from app import db

router = APIRouter()


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    updated_at: str


class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: str
    updated_at: str
    messages: list[dict]
    artifacts: list[dict]


async def _get_session_id(x_session_id: uuid.UUID = Header()) -> uuid.UUID:
    return x_session_id


@router.get("/api/conversations")
async def list_conversations(x_session_id: uuid.UUID = Header()) -> list[ConversationSummary]:
    await db.upsert_session(x_session_id)
    convs = await db.list_conversations(x_session_id)
    return [ConversationSummary(**_serialize(c)) for c in convs]


@router.post("/api/conversations")
async def create_conversation(x_session_id: uuid.UUID = Header()) -> ConversationSummary:
    await db.upsert_session(x_session_id)
    conv = await db.create_conversation(x_session_id)
    return ConversationSummary(**_serialize(conv))


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID, x_session_id: uuid.UUID = Header()) -> ConversationDetail:
    await db.upsert_session(x_session_id)
    conv = await db.get_conversation(conversation_id, x_session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetail(**_serialize(conv))


@router.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, x_session_id: uuid.UUID = Header()) -> Response:
    await db.upsert_session(x_session_id)
    deleted = await db.delete_conversation(conversation_id, x_session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)


def _serialize(obj: dict) -> dict:
    """Convert datetime objects to ISO strings for Pydantic."""
    result = {}
    for k, v in obj.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else (i.isoformat() if hasattr(i, "isoformat") else i) for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        else:
            result[k] = v
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && DATABASE_URL=postgresql://localhost:5432/dataagent_test uv run pytest tests/test_conversations.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/conversations.py backend/tests/test_conversations.py
git commit -m "feat: add conversation CRUD endpoints"
```

---

## Task 4: Modify `POST /api/query` to Persist Messages

**Files:**
- Modify: `backend/app/routes/query.py:1-139`
- Modify: `backend/tests/test_query.py`

- [ ] **Step 1: Rewrite tests for the updated query endpoint**

Replace `backend/tests/test_query.py` entirely. The old synchronous `TestClient` tests must be migrated to async `AsyncClient` since the query endpoint now depends on the database. Artifact parsing tests remain unchanged but are included in the new file:

```python
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
from app import db
from app.routes.query import _parse_artifact

pytestmark = pytest.mark.asyncio

SESSION_ID = str(uuid.uuid4())
HEADERS = {"X-Session-ID": SESSION_ID}


@pytest.fixture
async def client(db_pool):
    db._pool = db_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---- Artifact parsing (unit tests, no DB needed) ----

def test_parse_artifact_create():
    text = "Here is your chart. [[artifact:create|My Chart|chart]]"
    clean, meta = _parse_artifact(text, set())
    assert clean == "Here is your chart."
    assert meta is not None
    assert meta.action == "create"
    assert meta.title == "My Chart"
    assert meta.type == "chart"
    assert meta.id.startswith("artifact-")


def test_parse_artifact_update():
    text = "Updated the chart. [[artifact:update|artifact-123|Updated|chart]]"
    clean, meta = _parse_artifact(text, {"artifact-123"})
    assert clean == "Updated the chart."
    assert meta is not None
    assert meta.action == "update"
    assert meta.id == "artifact-123"
    assert meta.title == "Updated"
    assert meta.type == "chart"


def test_parse_artifact_none():
    text = "Just a plain answer with no markers."
    clean, meta = _parse_artifact(text, set())
    assert clean == text
    assert meta is None


def test_parse_artifact_update_bad_id():
    text = "Updated. [[artifact:update|artifact-unknown|Title|chart]]"
    clean, meta = _parse_artifact(text, {"artifact-123"})
    assert clean == "Updated."
    assert meta is not None
    assert meta.action == "create"
    assert meta.id != "artifact-unknown"
    assert meta.id.startswith("artifact-")
    assert meta.title == "Title"
    assert meta.type == "chart"


# ---- Health check ----

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---- Query endpoint ----

async def test_query_requires_conversation_id(client):
    resp = await client.post("/api/query", json={"question": "test"}, headers=HEADERS)
    assert resp.status_code == 422


async def test_query_empty_question(client):
    conv_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = conv_resp.json()["id"]

    resp = await client.post(
        "/api/query",
        json={"question": "", "conversation_id": conv_id},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == "Please enter a question."


async def test_query_saves_messages(client):
    """Mock the agent and verify messages are persisted."""
    conv_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = conv_resp.json()["id"]

    mock_result = AsyncMock()
    mock_result.output = "The revenue is $1M"

    with patch("app.routes.query.agent.run", return_value=mock_result):
        resp = await client.post(
            "/api/query",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "The revenue is $1M"
    assert data["conversation_id"] == conv_id

    conv = await db.get_conversation(uuid.UUID(conv_id), uuid.UUID(SESSION_ID))
    assert len(conv["messages"]) == 2
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "What is revenue?"
    assert conv["messages"][1]["role"] == "assistant"
    assert conv["messages"][1]["content"] == "The revenue is $1M"


async def test_query_auto_titles_conversation(client):
    """First message should set the conversation title."""
    conv_resp = await client.post("/api/conversations", headers=HEADERS)
    conv_id = conv_resp.json()["id"]

    mock_result = AsyncMock()
    mock_result.output = "Answer"

    with patch("app.routes.query.agent.run", return_value=mock_result):
        await client.post(
            "/api/query",
            json={"question": "What is the average ARR for fintech companies in Q4?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    conv = await db.get_conversation(uuid.UUID(conv_id), uuid.UUID(SESSION_ID))
    assert conv["title"] is not None
    assert len(conv["title"]) <= 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL=postgresql://localhost:5432/dataagent_test uv run pytest tests/test_query.py -v`
Expected: FAIL — query endpoint doesn't accept `conversation_id`

- [ ] **Step 3: Update the query route**

Modify `backend/app/routes/query.py`:

```python
import re
import uuid

from pydantic import BaseModel
from fastapi import APIRouter, Header
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

from app.agent.agent import agent, AgentDeps, make_model
from app import db
from app.data.loader import load_dataset, get_schema_summary

router = APIRouter()

_df = load_dataset()
_schema = get_schema_summary(_df)

ARTIFACT_PATTERN = re.compile(
    r'\[\[artifact:(create|update)\|([^|]+)\|([^|]*?)(?:\|(chart|table|code))?\]\]'
)


class ArtifactMeta(BaseModel):
    id: str
    title: str
    type: str
    action: str  # "create" | "update"


class QueryRequest(BaseModel):
    question: str
    conversation_id: uuid.UUID
    model: str | None = None


class QueryResponse(BaseModel):
    answer: str
    code: str = ""
    images: list[str] = []
    error: str | None = None
    artifact: ArtifactMeta | None = None
    conversation_id: str


def _parse_artifact(text: str, existing_ids: set[str]) -> tuple[str, ArtifactMeta | None]:
    match = ARTIFACT_PATTERN.search(text)
    if not match:
        return text, None

    action = match.group(1)
    clean_text = (text[:match.start()] + text[match.end():]).strip()

    if action == "create":
        title = match.group(2)
        art_type = match.group(4) or match.group(3) or "chart"
        artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"
    else:  # update
        artifact_id = match.group(2)
        title = match.group(3) or "Updated chart"
        art_type = match.group(4) or "chart"
        if artifact_id not in existing_ids:
            action = "create"
            artifact_id = f"artifact-{uuid.uuid4().hex[:8]}"

    return clean_text, ArtifactMeta(id=artifact_id, title=title, type=art_type, action=action)


def _build_message_history(messages: list[dict]) -> list[ModelMessage] | None:
    """Convert stored messages to PydanticAI message format."""
    if not messages:
        return None
    result: list[ModelMessage] = []
    for msg in messages:
        if msg["role"] == "user":
            result.append(ModelRequest(parts=[UserPromptPart(content=msg["content"])]))
        else:
            result.append(ModelResponse(parts=[TextPart(content=msg["content"])]))
    return result


@router.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest, x_session_id: uuid.UUID = Header()) -> QueryResponse:
    conv_id = req.conversation_id

    if not req.question.strip():
        return QueryResponse(answer="", error="Please enter a question.", conversation_id=str(conv_id))

    # Load history and artifact descriptors from DB
    history = await db.get_message_history(conv_id)
    artifact_descriptors = await db.get_artifact_descriptors(conv_id)

    deps = AgentDeps(
        df_schema=_schema,
        artifacts=[dict(d) for d in artifact_descriptors],
    )

    try:
        message_history = _build_message_history(history)
        override_model = make_model(req.model) if req.model else None
        result = await agent.run(req.question, deps=deps, message_history=message_history, model=override_model)

        code = ""
        images = []
        for r in deps.results:
            if r.code:
                code = r.code
            if r.images:
                images.extend(r.images)

        existing_ids = {d["artifact_id"] for d in artifact_descriptors}
        answer_text, artifact = _parse_artifact(result.output, existing_ids)

        if artifact is None and images:
            artifact = ArtifactMeta(
                id=f"artifact-{uuid.uuid4().hex[:8]}",
                title="Chart",
                type="chart",
                action="create",
            )

        # Persist user message
        await db.save_message(conv_id, "user", req.question)

        # Persist assistant message
        await db.save_message(
            conv_id, "assistant", answer_text,
            code=code or None,
            images=images or None,
            artifact=artifact.model_dump() if artifact else None,
        )

        # Persist artifact version if created/updated
        if artifact:
            version = await db.next_artifact_version(conv_id, artifact.id)
            await db.save_artifact(
                conv_id, artifact.id, artifact.title, artifact.type, version,
                code=code or None, images=images or None,
            )

        # Auto-title on first message
        if not history:
            title = req.question[:50]
            await db.update_conversation_title(conv_id, title)
        else:
            await db.touch_conversation(conv_id)

        return QueryResponse(
            answer=answer_text,
            code=code,
            images=images,
            artifact=artifact,
            conversation_id=str(conv_id),
        )
    except Exception as e:
        return QueryResponse(
            answer="",
            error=f"Unable to process your question: {str(e)}",
            conversation_id=str(conv_id),
        )
```

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && DATABASE_URL=postgresql://localhost:5432/dataagent_test uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/query.py backend/tests/test_query.py
git commit -m "feat: persist messages and artifacts in POST /api/query"
```

---

## Task 5: Frontend Types and API Layer

**Files:**
- Modify: `frontend/src/types.ts:1-48`
- Modify: `frontend/src/lib/api.ts:1-18`
- Create: `frontend/src/hooks/useSession.ts`

- [ ] **Step 1: Update types**

Replace `frontend/src/types.ts`:

```typescript
export interface ArtifactVersion {
  content: string;
  code?: string;
  images?: string[];
  timestamp: number;
}

export interface Artifact {
  id: string;
  title: string;
  type: "chart" | "table" | "code";
  versions: ArtifactVersion[];
  currentVersion: number;
}

export interface ArtifactMeta {
  id: string;
  title: string;
  type: string;
  action: "create" | "update";
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  images?: string[];
  error?: string;
  artifactId?: string;
}

export type ModelOption = "sonnet" | "opus" | "haiku";

export interface QueryRequest {
  question: string;
  conversation_id: string;
  model: ModelOption;
}

export interface QueryResponse {
  answer: string;
  code: string;
  images: string[];
  error: string | null;
  artifact: ArtifactMeta | null;
  conversation_id: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: {
    id: string;
    role: "user" | "assistant";
    content: string;
    code: string | null;
    images: string[] | null;
    artifact: ArtifactMeta | null;
    created_at: string;
  }[];
  artifacts: {
    id: string;
    artifact_id: string;
    title: string;
    type: "chart" | "table" | "code";
    version: number;
    code: string | null;
    images: string[] | null;
    created_at: string;
  }[];
}
```

- [ ] **Step 2: Create `useSession` hook**

Create `frontend/src/hooks/useSession.ts`:

```typescript
import { useState } from "react";

const SESSION_KEY = "session_id";

function generateUUID(): string {
  return crypto.randomUUID();
}

export function useSession(): string {
  const [sessionId] = useState<string>(() => {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = generateUUID();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  });
  return sessionId;
}
```

- [ ] **Step 3: Update API layer**

Replace `frontend/src/lib/api.ts`:

```typescript
import type { QueryRequest, QueryResponse, ConversationSummary, ConversationDetail } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

let _sessionId = "";

export function setSessionId(id: string) {
  _sessionId = id;
}

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Session-ID": _sessionId,
  };
}

export async function queryAgent(req: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(`${API_URL}/api/conversations`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function createConversation(): Promise<ConversationSummary> {
  const response = await fetch(`${API_URL}/api/conversations`, {
    method: "POST",
    headers: headers(),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_URL}/api/conversations/${id}`, {
    headers: headers(),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/${id}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
}
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds (may have warnings about unused imports — that's fine, we'll fix in next tasks)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/api.ts frontend/src/hooks/useSession.ts
git commit -m "feat: update frontend types, API layer, and session hook"
```

---

## Task 6: `useConversations` Hook

**Files:**
- Create: `frontend/src/hooks/useConversations.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useState, useCallback, useEffect } from "react";
import type { ConversationSummary } from "../types";
import { listConversations, createConversation, deleteConversation } from "../lib/api";

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const convs = await listConversations();
      setConversations(convs);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async () => {
    const conv = await createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  }, []);

  const select = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) {
      setActiveId((prev) => {
        const remaining = conversations.filter((c) => c.id !== id);
        return remaining.length > 0 ? remaining[0].id : null;
      });
    }
  }, [activeId, conversations]);

  return { conversations, activeId, isLoading, create, select, remove, refresh };
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useConversations.ts
git commit -m "feat: add useConversations hook"
```

---

## Task 7: Update `useChat` and `useArtifacts` Hooks

**Files:**
- Modify: `frontend/src/hooks/useChat.ts:1-68`
- Modify: `frontend/src/hooks/useArtifacts.ts:1-54`

- [ ] **Step 1: Update `useChat`**

Replace `frontend/src/hooks/useChat.ts`:

```typescript
import { useState, useCallback, useEffect } from "react";
import type { Message, ArtifactMeta, ModelOption } from "../types";
import { queryAgent, getConversation } from "../lib/api";

interface ArtifactHandlers {
  getDescriptors: () => { id: string; title: string; type: string }[];
  processArtifact: (meta: ArtifactMeta, content: { answer: string; code?: string; images?: string[] }) => void;
  loadFromConversation: (artifacts: any[]) => void;
}

export function useChat(
  artifactHandlers: ArtifactHandlers,
  model: ModelOption,
  conversationId: string | null,
  onConversationUpdate: () => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Load conversation history when conversationId changes
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setIsLoadingHistory(true);

    getConversation(conversationId)
      .then((conv) => {
        if (cancelled) return;

        const loadedMessages: Message[] = conv.messages.map((m) => ({
          role: m.role,
          content: m.content,
          code: m.code || undefined,
          images: m.images || undefined,
          artifactId: m.artifact?.id,
        }));
        setMessages(loadedMessages);

        // Load artifacts into artifact store
        artifactHandlers.loadFromConversation(conv.artifacts);
      })
      .catch((err) => {
        if (!cancelled) console.error("Failed to load conversation:", err);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => { cancelled = true; };
  }, [conversationId]); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (question: string, overrideConversationId?: string) => {
    const convId = overrideConversationId || conversationId;
    if (!convId) return;

    const userMessage: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await queryAgent({
        question,
        conversation_id: convId,
        model,
      });

      const hasArtifact = response.artifact != null;

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        code: hasArtifact ? undefined : (response.code || undefined),
        images: hasArtifact ? undefined : (response.images.length > 0 ? response.images : undefined),
        error: response.error || undefined,
        artifactId: response.artifact?.id,
      };

      if (response.artifact) {
        artifactHandlers.processArtifact(response.artifact, {
          answer: response.answer,
          code: response.code || undefined,
          images: response.images.length > 0 ? response.images : undefined,
        });
      }

      setMessages((prev) => [...prev, assistantMessage]);
      onConversationUpdate();
    } catch (err) {
      const errorMessage: Message = {
        role: "assistant",
        content: "",
        error: err instanceof Error ? err.message : "Something went wrong",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, artifactHandlers, model, onConversationUpdate]);

  return { messages, isLoading, isLoadingHistory, sendMessage };
}
```

- [ ] **Step 2: Update `useArtifacts`**

Replace `frontend/src/hooks/useArtifacts.ts`:

```typescript
import { useState, useCallback } from "react";
import type { Artifact, ArtifactMeta, ArtifactVersion } from "../types";

export function useArtifacts() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const processArtifact = useCallback((
    meta: ArtifactMeta,
    content: { answer: string; code?: string; images?: string[] }
  ) => {
    const version: ArtifactVersion = {
      content: content.answer,
      code: content.code,
      images: content.images,
      timestamp: Date.now(),
    };

    setArtifacts(prev => {
      if (meta.action === "update") {
        return prev.map(a => a.id === meta.id ? {
          ...a,
          title: meta.title,
          versions: [...a.versions, version],
          currentVersion: a.versions.length,
        } : a);
      }
      return [...prev, {
        id: meta.id,
        title: meta.title,
        type: meta.type as Artifact["type"],
        versions: [version],
        currentVersion: 0,
      }];
    });

    setSelectedId(meta.id);
  }, []);

  const loadFromConversation = useCallback((dbArtifacts: any[]) => {
    if (!dbArtifacts || dbArtifacts.length === 0) {
      setArtifacts([]);
      setSelectedId(null);
      return;
    }

    // Group by artifact_id, build version arrays
    const grouped = new Map<string, { title: string; type: string; versions: ArtifactVersion[] }>();

    for (const a of dbArtifacts) {
      if (!grouped.has(a.artifact_id)) {
        grouped.set(a.artifact_id, { title: a.title, type: a.type, versions: [] });
      }
      const group = grouped.get(a.artifact_id)!;
      group.title = a.title; // latest title wins (sorted by version ASC)
      group.versions.push({
        content: "",
        code: a.code || undefined,
        images: a.images || undefined,
        timestamp: new Date(a.created_at).getTime(),
      });
    }

    const loaded: Artifact[] = [];
    for (const [id, data] of grouped) {
      loaded.push({
        id,
        title: data.title,
        type: data.type as Artifact["type"],
        versions: data.versions,
        currentVersion: data.versions.length - 1,
      });
    }

    setArtifacts(loaded);
    setSelectedId(loaded.length > 0 ? loaded[loaded.length - 1].id : null);
  }, []);

  const setVersion = useCallback((artifactId: string, versionIndex: number) => {
    setArtifacts(prev => prev.map(a =>
      a.id === artifactId ? { ...a, currentVersion: versionIndex } : a
    ));
  }, []);

  const getDescriptors = useCallback(() =>
    artifacts.map(a => ({ id: a.id, title: a.title, type: a.type })),
    [artifacts]
  );

  return { artifacts, selectedId, setSelectedId, processArtifact, setVersion, getDescriptors, loadFromConversation };
}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build may fail due to App.tsx not passing new props yet — that's expected. The hooks themselves should have no syntax errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/hooks/useArtifacts.ts
git commit -m "feat: update useChat and useArtifacts hooks for conversation persistence"
```

---

## Task 8: Sidebar Component

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Create the Sidebar component**

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PanelLeftClose, PanelLeft, Plus, Trash2 } from "lucide-react";
import type { ConversationSummary } from "@/types";

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  isLoading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export function Sidebar({
  conversations,
  activeId,
  isLoading,
  onSelect,
  onCreate,
  onDelete,
}: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (collapsed) {
    return (
      <div className="w-10 border-r flex flex-col items-center pt-2">
        <Button variant="ghost" size="icon-sm" onClick={() => setCollapsed(false)}>
          <PanelLeft className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-64 border-r flex flex-col bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="text-sm font-semibold">History</span>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon-sm" onClick={onCreate}>
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={() => setCollapsed(true)}>
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Conversation list */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading && (
            <>
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-9 rounded-md bg-muted animate-pulse" />
              ))}
            </>
          )}

          {!isLoading && conversations.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No conversations yet
            </p>
          )}

          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-muted ${
                conv.id === activeId ? "bg-muted" : ""
              }`}
              onClick={() => onSelect(conv.id)}
            >
              <span className="truncate flex-1">
                {conv.title || "New conversation"}
              </span>

              {confirmDelete === conv.id ? (
                <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="destructive"
                    size="icon-sm"
                    onClick={() => {
                      onDelete(conv.id);
                      setConfirmDelete(null);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setConfirmDelete(null)}
                  >
                    ✕
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="opacity-0 group-hover:opacity-100 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmDelete(conv.id);
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds (Sidebar is not imported anywhere yet, so no integration errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: add Sidebar component with conversation list"
```

---

## Task 9: Wire Up App.tsx — Three-Pane Layout

**Files:**
- Modify: `frontend/src/App.tsx:1-77`

- [ ] **Step 1: Rewrite App.tsx**

Replace `frontend/src/App.tsx`:

```tsx
import { useRef, useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "./components/ChatInput";
import { ChatMessage } from "./components/ChatMessage";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { Sidebar } from "./components/Sidebar";
import { useSession } from "./hooks/useSession";
import { useConversations } from "./hooks/useConversations";
import { useChat } from "./hooks/useChat";
import { useArtifacts } from "./hooks/useArtifacts";
import { useTheme } from "./hooks/useTheme";
import { setSessionId } from "./lib/api";
import type { ModelOption } from "./types";

export default function App() {
  const sessionId = useSession();
  const [model, setModel] = useState<ModelOption>("sonnet");
  const { theme, setTheme } = useTheme();

  // Initialize API session header
  useEffect(() => {
    setSessionId(sessionId);
  }, [sessionId]);

  const { conversations, activeId, isLoading: convLoading, create, select, remove, refresh } = useConversations();
  const artifactStore = useArtifacts();

  const onConversationUpdate = useCallback(() => {
    refresh();
  }, [refresh]);

  const { messages, isLoading, isLoadingHistory, sendMessage } = useChat(
    {
      getDescriptors: artifactStore.getDescriptors,
      processArtifact: artifactStore.processArtifact,
      loadFromConversation: artifactStore.loadFromConversation,
    },
    model,
    activeId,
    onConversationUpdate,
  );

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewChat = useCallback(async () => {
    await create();
  }, [create]);

  const handleSend = useCallback(async (question: string) => {
    let id = activeId;
    if (!id) {
      id = await create();
    }
    sendMessage(question, id);
  }, [activeId, create, sendMessage]);

  const hasArtifacts = artifactStore.artifacts.length > 0;

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        isLoading={convLoading}
        onSelect={select}
        onCreate={handleNewChat}
        onDelete={remove}
      />

      {/* Chat panel */}
      <div className={`flex flex-col p-4 transition-all duration-300 ${hasArtifacts ? "w-1/2 border-r" : "flex-1"}`}>
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Talk to Your Data</h1>
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>

        <ScrollArea className="flex-1 mb-4">
          <div className="space-y-4 pr-4">
            {isLoadingHistory && (
              <p className="text-muted-foreground text-center mt-8">Loading conversation...</p>
            )}
            {!isLoadingHistory && messages.length === 0 && (
              <p className="text-muted-foreground text-center mt-8">
                {activeId
                  ? "Ask a question about the SaaS company dataset."
                  : "Start a new conversation to ask questions about your data."}
              </p>
            )}
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                onArtifactClick={artifactStore.setSelectedId}
              />
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <Card className="max-w-[80%]">
                  <CardContent className="p-4 text-muted-foreground">
                    Analyzing...
                  </CardContent>
                </Card>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <ChatInput
          onSend={handleSend}
          disabled={isLoading || isLoadingHistory}
          model={model}
          onModelChange={setModel}
        />
      </div>

      {/* Workspace panel */}
      {hasArtifacts && (
        <div className="w-1/2 flex flex-col">
          <WorkspacePanel
            artifacts={artifactStore.artifacts}
            selectedId={artifactStore.selectedId}
            onSelect={artifactStore.setSelectedId}
            onVersionChange={artifactStore.setVersion}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire up three-pane layout with sidebar and conversation state"
```

---

## Task 10: Add `just migrate` Command and Update `.env.example`

**Files:**
- Modify: `justfile`

- [ ] **Step 1: Add migrate recipe to justfile**

Add to the justfile:

```just
# Run database migrations
migrate:
    cd backend && PGPASSWORD=$PGPASSWORD psql $DATABASE_URL -f migrations/001_create_tables.sql
```

- [ ] **Step 2: Add `.superpowers/` to `.gitignore`**

Check if `.gitignore` exists. If so, add `.superpowers/` to it. If not, create one with:

```
.superpowers/
```

- [ ] **Step 3: Commit**

```bash
git add justfile .gitignore
git commit -m "chore: add migrate command and gitignore .superpowers"
```

---

## Task 11: Manual Integration Test

This task is NOT automated — it verifies the full flow end-to-end.

- [ ] **Step 1: Start a local PostgreSQL database**

Run: `docker run -d --name dataagent-pg -e POSTGRES_DB=dataagent -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16`
(Or use an existing local Postgres.)

- [ ] **Step 2: Set `DATABASE_URL` in backend `.env`**

Add: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dataagent`

- [ ] **Step 3: Start dev servers**

Run: `just dev`

- [ ] **Step 4: Verify the flow in browser**

1. Open the app — sidebar should show "No conversations yet"
2. Click "+ New" — new conversation appears in sidebar
3. Ask a question — message appears, conversation gets titled
4. Ask a follow-up — history is maintained
5. Click "+ New" again — fresh conversation, old one listed in sidebar
6. Click the old conversation — messages reload from DB
7. Refresh the page — conversations persist
8. Delete a conversation — it disappears from sidebar

- [ ] **Step 5: Commit any fixes discovered during testing**

```bash
git add -A && git commit -m "fix: integration test fixes"
```

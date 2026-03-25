import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
from app import db
from app.routes.query import _parse_artifact

SESSION_ID = str(uuid.uuid4())
HEADERS = {"X-Session-ID": SESSION_ID}


@pytest.fixture
async def client(db_pool):
    db._pool = db_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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
    assert meta.id.startswith("artifact-")


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_query_requires_conversation_id(client):
    resp = await client.post("/api/query", json={"question": "test"}, headers=HEADERS)
    assert resp.status_code == 422


async def test_query_empty_question(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    resp = await client.post("/api/query", json={"question": "", "conversation_id": conv_id}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["error"] == "Please enter a question."


async def test_query_saves_messages(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

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
    assert conv["messages"][1]["role"] == "assistant"


async def test_query_auto_titles_conversation(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

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

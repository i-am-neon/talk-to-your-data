import json
import uuid
import pytest
import httpx as _httpx
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
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
    data = resp.json()
    assert data["error"] == "Please enter a question."
    assert data["error_code"] == "empty_question"


async def test_query_question_too_long(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    long_question = "x" * 2001
    resp = await client.post("/api/query", json={"question": long_question, "conversation_id": conv_id}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["error_code"] == "question_too_long"
    assert "too long" in data["error"]


async def test_query_saves_messages(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    mock_result = MagicMock()
    mock_result.output = "The revenue is $1M"
    mock_result.all_messages_json.return_value = b"[]"

    with patch("app.routes.query.agent.run", new_callable=AsyncMock, return_value=mock_result):
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

    mock_result = MagicMock()
    mock_result.output = "Answer"
    mock_result.all_messages_json.return_value = b"[]"

    with patch("app.routes.query.agent.run", new_callable=AsyncMock, return_value=mock_result):
        await client.post(
            "/api/query",
            json={"question": "What is the average ARR for fintech companies in Q4?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    conv = await db.get_conversation(uuid.UUID(conv_id), uuid.UUID(SESSION_ID))
    assert conv["title"] is not None
    assert len(conv["title"]) <= 50


async def test_query_llm_timeout_returns_classified_error(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    with patch("app.routes.query.agent.run", new_callable=AsyncMock, side_effect=_httpx.ReadTimeout("timed out")):
        resp = await client.post(
            "/api/query",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    data = resp.json()
    assert data["error_code"] == "llm_timeout"
    assert "try again" in data["error"].lower()


async def test_query_rate_limit_returns_classified_error(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    response = _httpx.Response(429, request=_httpx.Request("POST", "http://test"))
    exc = _httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    with patch("app.routes.query.agent.run", new_callable=AsyncMock, side_effect=exc):
        resp = await client.post(
            "/api/query",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    data = resp.json()
    assert data["error_code"] == "llm_rate_limited"
    assert "busy" in data["error"].lower()


async def test_query_generic_error_returns_internal(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    with patch("app.routes.query.agent.run", new_callable=AsyncMock, side_effect=RuntimeError("unexpected")):
        resp = await client.post(
            "/api/query",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    data = resp.json()
    assert data["error_code"] == "internal_error"
    assert "something went wrong" in data["error"].lower()


# ---------------------------------------------------------------------------
# Streaming endpoint (SSE) tests
# ---------------------------------------------------------------------------

def _parse_sse_events(body: str) -> list[dict]:
    """Parse SSE text into a list of event dicts."""
    events = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


async def test_stream_empty_question(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    resp = await client.post(
        "/api/query/stream",
        json={"question": "", "conversation_id": conv_id},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    assert len(events) == 1
    assert events[0]["type"] == "done"
    assert events[0]["error_code"] == "empty_question"


async def test_stream_question_too_long(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    resp = await client.post(
        "/api/query/stream",
        json={"question": "x" * 2001, "conversation_id": conv_id},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    assert len(events) == 1
    assert events[0]["type"] == "done"
    assert events[0]["error_code"] == "question_too_long"


async def test_stream_llm_timeout(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    async def mock_raising_stream(*args, **kwargs):
        raise _httpx.ReadTimeout("timed out")
        yield  # pragma: no cover

    with patch("app.routes.query.agent.run_stream_events", return_value=mock_raising_stream()):
        resp = await client.post(
            "/api/query/stream",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    events = _parse_sse_events(resp.text)
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    assert done[0]["error_code"] == "llm_timeout"
    assert "try again" in done[0]["error"].lower()


async def test_stream_rate_limit(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    response = _httpx.Response(429, request=_httpx.Request("POST", "http://test"))
    exc = _httpx.HTTPStatusError("rate limited", request=response.request, response=response)

    async def mock_raising_stream(*args, **kwargs):
        raise exc
        yield  # pragma: no cover

    with patch("app.routes.query.agent.run_stream_events", return_value=mock_raising_stream()):
        resp = await client.post(
            "/api/query/stream",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    events = _parse_sse_events(resp.text)
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    assert done[0]["error_code"] == "llm_rate_limited"
    assert "busy" in done[0]["error"].lower()


async def test_stream_generic_error(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]

    async def mock_raising_stream(*args, **kwargs):
        raise RuntimeError("unexpected")
        yield  # pragma: no cover

    with patch("app.routes.query.agent.run_stream_events", return_value=mock_raising_stream()):
        resp = await client.post(
            "/api/query/stream",
            json={"question": "What is revenue?", "conversation_id": conv_id},
            headers=HEADERS,
        )

    events = _parse_sse_events(resp.text)
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    assert done[0]["error_code"] == "internal_error"
    assert "something went wrong" in done[0]["error"].lower()

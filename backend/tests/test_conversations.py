import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app import db

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
    assert resp.json()["title"] is None


async def test_list_conversations(client):
    await client.post("/api/conversations", headers=HEADERS)
    await client.post("/api/conversations", headers=HEADERS)
    resp = await client.get("/api/conversations", headers=HEADERS)
    assert len(resp.json()) == 2


async def test_get_conversation(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    resp = await client.get(f"/api/conversations/{conv_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


async def test_get_conversation_wrong_session(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    resp = await client.get(f"/api/conversations/{conv_id}", headers={"X-Session-ID": str(uuid.uuid4())})
    assert resp.status_code == 404


async def test_delete_conversation(client):
    conv_id = (await client.post("/api/conversations", headers=HEADERS)).json()["id"]
    assert (await client.delete(f"/api/conversations/{conv_id}", headers=HEADERS)).status_code == 204
    assert (await client.get(f"/api/conversations/{conv_id}", headers=HEADERS)).status_code == 404


async def test_missing_session_header(client):
    assert (await client.get("/api/conversations")).status_code == 422

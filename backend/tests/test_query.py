# backend/tests/test_query.py
from fastapi.testclient import TestClient
from app.main import app
from app.routes.query import _parse_artifact

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_empty_question():
    response = client.post("/api/query", json={"question": ""})
    assert response.status_code == 200
    data = response.json()
    assert data["error"] == "Please enter a question."


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
    assert meta.action == "create"  # falls back to create
    assert meta.id != "artifact-unknown"  # gets a new ID
    assert meta.id.startswith("artifact-")
    assert meta.title == "Title"
    assert meta.type == "chart"

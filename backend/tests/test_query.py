# backend/tests/test_query.py
from fastapi.testclient import TestClient
from app.main import app

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

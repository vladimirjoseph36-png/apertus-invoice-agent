"""Unit tests for the FastAPI backend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "ocr" in data


def test_chat_ui_serves_html():
    res = client.get("/chat")
    assert res.status_code == 200
    assert "<!DOCTYPE html>" in res.text


def test_stats_endpoint():
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    for key in ("total_docs", "total_amount", "alerts", "by_level", "top_suppliers", "recent", "scores"):
        assert key in data


def test_chat_endpoint_rejects_empty():
    res = client.post("/chat", json={"message": ""})
    assert res.status_code == 400


def test_upload_rejects_unsupported():
    res = client.post("/upload", files={"file": ("test.exe", b"fake", "application/octet-stream")})
    assert res.status_code == 400


def test_dashboard_ui_serves_html():
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "<!DOCTYPE html>" in res.text


def test_clear_analyses_endpoint():
    res = client.post("/api/clear-analyses")
    assert res.status_code == 200
    assert res.json()["success"] is True
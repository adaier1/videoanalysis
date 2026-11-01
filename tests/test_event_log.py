import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from parse_video_py import event_log
from parse_video_py.web import app

AUTH = ("admin", "admin123")


def test_record_and_list_newest_first():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            event_log.load()
            event_log.record("parse", "ok", "测试成功", "admin")
            event_log.record("parse", "bad", "测试失败", "admin")
            events = event_log.list_events()
            assert [e["message"] for e in events] == ["测试失败", "测试成功"]
            lines = (Path(d) / "events.jsonl").read_text(encoding="utf-8").splitlines()
            assert len(lines) == 2


def test_load_skips_broken_lines():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "events.jsonl"
        path.write_text(
            "not json\n"
            '{"t":"2026-01-01T00:00:00+00:00","type":"parse","status":"ok",'
            '"user":"","message":"ok"}\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            event_log.load()
            events = event_log.list_events()
            assert len(events) == 1
            assert events[0]["message"] == "ok"


def test_list_events_requires_login():
    client = TestClient(app)
    assert client.get("/api/events").status_code == 401
    response = client.get("/api/events", auth=AUTH)
    assert response.status_code == 200
    assert isinstance(response.json()["data"]["events"], list)


def test_parse_error_records_event():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            event_log.load()
            client = TestClient(app)
            client.get("/video/share/url/parse", params={"url": "没有链接"}, auth=AUTH)
            events = event_log.list_events()
            assert events[0]["type"] == "parse"
            assert events[0]["status"] == "bad"
            assert "没有链接" in events[0]["message"]


def test_login_failure_records_event():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            event_log.load()
            client = TestClient(app)
            client.post(
                "/login",
                data={"username": "admin", "password": "wrong"},
                follow_redirects=False,
            )
            events = event_log.list_events()
            assert events[0]["type"] == "auth"
            assert events[0]["status"] == "bad"


def test_post_event_requires_login_and_caps_message():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            event_log.load()
            client = TestClient(app)
            assert client.post("/api/events", json={"message": "x"}).status_code == 401
            assert (
                client.post("/api/events", json={"message": ""}, auth=AUTH).json()[
                    "code"
                ]
                == 400
            )
            response = client.post(
                "/api/events", json={"message": "a" * 600}, auth=AUTH
            )
            assert response.status_code == 200
            events = event_log.list_events()
            assert events[0]["type"] == "parse"
            assert events[0]["status"] == "bad"
            assert events[0]["user"] == "admin"
            assert len(events[0]["message"]) == 500

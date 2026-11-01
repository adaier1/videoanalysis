import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from parse_video_py import cookie_store
from parse_video_py.parser.base import BaseParser, VideoSource
from parse_video_py.parser.bilibili import BiliBili
from parse_video_py.web import app

AUTH = ("admin", "admin123")


def test_set_get_delete_persists():
    cookie_store.set_cookie("bilibili", "SESSDATA=x; bili_jct=y")
    assert cookie_store.get_cookie("bilibili") == "SESSDATA=x; bili_jct=y"
    assert cookie_store.get_cookie("weibo") == ""
    assert cookie_store.list_cookies() == {"bilibili": "SESSDATA=x; bili_jct=y"}

    path = Path(os.environ["PARSE_VIDEO_DATA_DIR"]) / "platform_cookies.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "bilibili": "SESSDATA=x; bili_jct=y"
    }

    assert cookie_store.delete_cookie("bilibili") is True
    assert cookie_store.delete_cookie("bilibili") is False
    assert cookie_store.get_cookie("bilibili") == ""


def test_get_cookies_requires_login():
    client = TestClient(app)
    assert client.get("/api/settings/cookies").status_code == 401
    response = client.get("/api/settings/cookies", auth=AUTH)
    assert response.status_code == 200
    assert response.json()["data"]["cookies"] == {}


def test_post_cookie_saves_and_rejects_invalid():
    client = TestClient(app)
    assert (
        client.post("/api/settings/cookies", json={"source": "bilibili"}).status_code
        == 401
    )

    response = client.post(
        "/api/settings/cookies",
        json={"source": "bilibili", "cookie": "SESSDATA=abc"},
        auth=AUTH,
    )
    assert response.json()["code"] == 200
    assert cookie_store.get_cookie("bilibili") == "SESSDATA=abc"

    response = client.post(
        "/api/settings/cookies", json={"source": "unknown", "cookie": "x"}, auth=AUTH
    )
    assert response.json()["code"] == 400
    response = client.post(
        "/api/settings/cookies",
        json={"source": "douyin", "cookie": "a" * 4200},
        auth=AUTH,
    )
    assert response.json()["code"] == 200
    assert len(cookie_store.get_cookie("douyin")) == 4200

    response = client.post(
        "/api/settings/cookies",
        json={"source": "weibo", "cookie": "a" * 8001},
        auth=AUTH,
    )
    assert response.json()["code"] == 400


def test_post_empty_cookie_deletes():
    client = TestClient(app)
    response = client.post(
        "/api/settings/cookies", json={"source": "weibo", "cookie": ""}, auth=AUTH
    )
    assert response.json()["code"] == 400
    response = client.post(
        "/api/settings/cookies", json={"source": "weibo", "cookie": "SUB=x"}, auth=AUTH
    )
    assert response.json()["code"] == 200
    response = client.post(
        "/api/settings/cookies", json={"source": "weibo", "cookie": ""}, auth=AUTH
    )
    assert response.json()["code"] == 200
    assert cookie_store.get_cookie("weibo") == ""


def test_cookie_saved_event_is_recorded():
    client = TestClient(app)
    client.post(
        "/api/settings/cookies",
        json={"source": "bilibili", "cookie": "SESSDATA=x"},
        auth=AUTH,
    )
    events = client.get("/api/events", auth=AUTH).json()["data"]["events"]
    assert events[0]["type"] == "settings"
    assert events[0]["status"] == "ok"
    assert "bilibili" in events[0]["message"]


def test_parser_headers_include_saved_cookie(monkeypatch):
    monkeypatch.setattr(BaseParser, "random_user_agent", staticmethod(lambda: "UA"))
    cookie_store.set_cookie("bilibili", "SESSDATA=abc")
    headers = BiliBili(VideoSource.BiliBili).get_default_headers()
    assert headers["Cookie"] == "SESSDATA=abc"
    assert "Cookie" not in BiliBili().get_default_headers()


class TestBiliBiliQuality:
    @pytest.fixture
    def captured(self):
        return []

    @pytest.fixture
    def mock_bili_responses(self, monkeypatch, captured):
        async def mock_get(self, url, **kwargs):
            captured.append(url)
            if "playurl" in url:
                data = {"durl": [{"url": "https://x/durl.mp4"}]}
                if "qn=127" in url:
                    data["dash"] = {
                        "video": [
                            {"id": 32, "baseUrl": "https://x/720.mp4"},
                            {"id": 80, "baseUrl": "https://x/1080.mp4"},
                        ]
                    }
                payload = {"code": 0, "data": data}
            else:
                payload = {
                    "code": 0,
                    "data": {"title": "t", "pic": "p", "pages": [{"cid": 1}]},
                }

            class MockResponse:
                status_code = 200

                @property
                def text(self):
                    return json.dumps(payload)

            return MockResponse()

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    @pytest.mark.asyncio
    async def test_cookie_unlocks_dash_quality_and_qn127(
        self, mock_bili_responses, captured
    ):
        cookie_store.set_cookie("bilibili", "SESSDATA=abc")
        parser = BiliBili(VideoSource.BiliBili)
        info = await parser.parse_video_id("BV1xx411c7mD")
        assert "qn=127" in captured[1]
        assert info.video_url == "https://x/1080.mp4"
        assert info.headers.get("Referer") == "https://www.bilibili.com/"

    @pytest.mark.asyncio
    async def test_without_cookie_keeps_durl_path(self, mock_bili_responses, captured):
        parser = BiliBili(VideoSource.BiliBili)
        info = await parser.parse_video_id("BV1xx411c7mD")
        assert "qn=80" in captured[1]
        assert info.video_url == "https://x/durl.mp4"

    @pytest.mark.asyncio
    async def test_play_request_carries_saved_cookie(self, monkeypatch, captured):
        cookie_store.set_cookie("bilibili", "SESSDATA=abc")
        seen = {}

        async def mock_get(self, url, **kwargs):
            captured.append(url)
            seen.update(kwargs.get("headers") or {})

            class MockResponse:
                status_code = 200

                @property
                def text(self):
                    return json.dumps(
                        {
                            "code": 0,
                            "data": {
                                "title": "t",
                                "pic": "p",
                                "pages": [{"cid": 1}],
                                "durl": [{"url": "https://x/durl.mp4"}],
                            },
                        }
                    )

            return MockResponse()

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        parser = BiliBili(VideoSource.BiliBili)
        info = await parser.parse_video_id("BV1xx411c7mD")
        assert seen["Cookie"] == "SESSDATA=abc"
        assert info.video_url == "https://x/durl.mp4"

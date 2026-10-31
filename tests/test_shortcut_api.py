import os
import tempfile
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from parse_video_py import key_store
from parse_video_py.parser.base import VideoInfo
from parse_video_py.web import app

AUTH = ("admin", "admin123")
client = TestClient(app)


def test_video_info_headers_field_is_backward_compatible():
    info = VideoInfo("https://example.com/video.mp4", "https://example.com/cover.jpg")
    assert info.headers == {}


def test_get_or_create_key_persists_and_reuses():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("alice")
            assert key_store.find_owner(key) == "alice"
            assert key_store.get_or_create_key("alice") == key
            assert key_store.get_or_create_key("bob") != key


def test_reset_key_invalidates_old_key():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            old = key_store.get_or_create_key("bob")
            new = key_store.reset_key("bob")
            assert new != old
            assert key_store.find_owner(old) is None
            assert key_store.find_owner(new) == "bob"


def test_shortcut_parse_rejects_invalid_key():
    response = client.post(
        "/api/shortcut/parse",
        json={"key": "not-a-real-key", "url": "https://v.douyin.com/abc"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 401
    assert body["success"] is False
    assert body["error_type"] == "invalid_key"
    assert body["message"] == "API Key 无效，请重新配置"


def test_shortcut_parse_get_rejects_invalid_key():
    response = client.get(
        "/api/shortcut/parse", params={"key": "nope", "url": "https://v.douyin.com/abc"}
    )
    body = response.json()
    assert body["code"] == 401
    assert body["success"] is False
    assert body["error_type"] == "invalid_key"
    assert body["message"] == "API Key 无效，请重新配置"


def test_shortcut_parse_get_with_valid_key_and_invalid_url():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("erin")
            response = client.get(
                "/api/shortcut/parse", params={"key": key, "url": "这不是链接"}
            )
            body = response.json()
            assert body["code"] == 400
            assert body["error_type"] == "invalid_url"
            assert body["message"] == "视频链接无效，请检查分享内容"


def test_shortcut_parse_rejects_invalid_url():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("default")
            response = client.post(
                "/api/shortcut/parse", json={"key": key, "url": "这不是链接"}
            )
            body = response.json()
            assert response.status_code == 200
            assert body["code"] == 400
            assert body["success"] is False
            assert body["error_type"] == "invalid_url"
            assert body["message"] == "视频链接无效，请检查分享内容"


def test_shortcut_parse_failure_returns_standard_alert_message():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("frank")
            with patch(
                "parse_video_py.web.parse_video_share_url",
                AsyncMock(side_effect=RuntimeError("平台反爬拦截")),
            ):
                response = client.post(
                    "/api/shortcut/parse",
                    json={"key": key, "url": "https://v.douyin.com/abc"},
                )
            body = response.json()
            assert body["code"] == 400
            assert body["success"] is False
            assert body["error_type"] == "parse_failed"
            assert body["message"] == "视频解析失败，可能暂不支持该平台"
            assert body["detail"] == "平台反爬拦截"


def test_shortcut_parse_success_without_video_url_returns_parse_failed():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("grace")
            info = VideoInfo("", "https://example.com/cover.jpg")
            with patch(
                "parse_video_py.web.parse_video_share_url",
                AsyncMock(return_value=info),
            ):
                response = client.post(
                    "/api/shortcut/parse",
                    json={"key": key, "url": "https://v.douyin.com/abc"},
                )
            body = response.json()
            assert body["code"] == 400
            assert body["error_type"] == "parse_failed"
            assert body["message"] == "视频解析失败，可能暂不支持该平台"


def test_shortcut_parse_success_returns_download_url_and_headers():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("carol")
            info = VideoInfo(
                video_url="https://example.com/video.mp4",
                cover_url="https://example.com/cover.jpg",
                title="测试视频",
                headers={"Referer": "https://v.douyin.com/"},
            )
            with patch(
                "parse_video_py.web.parse_video_share_url",
                AsyncMock(return_value=info),
            ):
                response = client.post(
                    "/api/shortcut/parse",
                    json={"key": key, "url": "https://v.douyin.com/abc"},
                )
            body = response.json()
            assert response.status_code == 200
            assert body["code"] == 200
            assert body["success"] is True
            assert body["error_type"] == "success"
            assert body["title"] == "测试视频"
            assert body["download_url"] == "https://example.com/video.mp4"
            assert body["message"] == "已获取视频下载地址"
            assert body["headers"]["Referer"] == "https://v.douyin.com/"
            assert body["headers"]["User-Agent"]
            assert body.get("cover_url") == "https://example.com/cover.jpg"


def test_shortcut_parse_success_without_parser_headers_falls_back_to_ua():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            key = key_store.get_or_create_key("dave")
            info = VideoInfo("https://example.com/video.mp4", "")
            with patch(
                "parse_video_py.web.parse_video_share_url",
                AsyncMock(return_value=info),
            ):
                response = client.post(
                    "/api/shortcut/parse",
                    json={"key": key, "url": "https://v.douyin.com/abc"},
                )
            body = response.json()
            assert body["code"] == 200
            assert body["headers"] == {"User-Agent": body["headers"]["User-Agent"]}
            assert "cover_url" not in body


def test_shortcut_key_get_creates_and_reset_rotates():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"PARSE_VIDEO_DATA_DIR": d}):
            data = client.get("/api/shortcut/key", auth=AUTH).json()["data"]
            assert data["owner"] == "admin"
            key1 = data["key"]
            key2 = client.post("/api/shortcut/key/reset", auth=AUTH).json()["data"][
                "key"
            ]
            assert key1 != key2
            assert key_store.find_owner(key1) is None
            assert key_store.find_owner(key2) == "admin"

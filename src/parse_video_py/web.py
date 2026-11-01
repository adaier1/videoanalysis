import base64
import dataclasses
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel

from parse_video_py import VideoSource, parse_video_id, parse_video_share_url
from parse_video_py import auth_store
from parse_video_py import cookie_store
from parse_video_py import event_log
from parse_video_py import key_store
from parse_video_py.parser.base import BaseParser
from parse_video_py.utils import extract_url


def _get_templates_dir() -> str:
    # 模板已移入 src/parse_video_py/templates/，与 web.py 同级
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.is_dir():
        return str(templates_dir)
    raise FileNotFoundError("templates 目录未找到")


app = FastAPI()

mcp = FastApiMCP(app)
mcp.mount_http()

templates = Jinja2Templates(directory=_get_templates_dir())

event_log.load()


SESSION_COOKIE = "pv_session"


def _session_user(request: Request) -> str | None:
    return auth_store.get_session_user(request.cookies.get(SESSION_COOKIE))


def _basic_user(request: Request) -> str | None:
    """兼容 API 客户端的 Basic Auth（凭据来自 auth_store，默认 admin/admin123）"""
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8", errors="replace")
    except Exception:
        return None
    username, _, password = decoded.partition(":")
    if auth_store.verify_credentials(username, password):
        return username
    return None


def current_user(request: Request) -> str | None:
    return _session_user(request) or _basic_user(request)


def require_login(request: Request) -> str:
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


_auth_dependency = [Depends(require_login)]
_key_owner_dependency = Depends(require_login)


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    if current_user(request) is None:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "视频解析控制台 · parse-video-py",
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = current_user(request)
    if user is not None:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"title": "登录 · parse-video-py", "error": ""},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not auth_store.verify_credentials(username, password):
        event_log.record("auth", "bad", "登录失败：用户名或密码不正确", username)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"title": "登录 · parse-video-py", "error": "用户名或密码不正确"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"Cache-Control": "no-store"},
        )
    event_log.record("auth", "ok", "登录成功", username)
    token = auth_store.create_session(username)
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/logout")
async def logout(request: Request):
    user = _session_user(request)
    auth_store.drop_session(request.cookies.get(SESSION_COOKIE, ""))
    if user:
        event_log.record("auth", "ok", "退出登录", user)
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/video/share/url/parse")
async def share_url_parse(url: str, user: str = _key_owner_dependency):
    video_share_url = extract_url(url)
    if video_share_url is None:
        event_log.record("parse", "bad", f"未检测到有效的分享链接：{url}", user)
        return {
            "code": 400,
            "msg": "未检测到有效的分享链接",
        }

    try:
        video_info = await parse_video_share_url(video_share_url)
        event_log.record("parse", "ok", f"分享链接解析成功：{video_share_url}", user)
        return {
            "code": 200,
            "msg": "解析成功",
            "data": dataclasses.asdict(video_info),
        }
    except Exception as err:
        event_log.record("parse", "bad", f"分享链接解析失败：{err}", user)
        return {
            "code": 500,
            "msg": str(err),
        }


@app.get("/video/id/parse")
async def video_id_parse(
    source: VideoSource, video_id: str, user: str = _key_owner_dependency
):
    try:
        video_info = await parse_video_id(source, video_id)
        event_log.record(
            "parse", "ok", f"ID 解析成功：{source.value} / {video_id}", user
        )
        return {
            "code": 200,
            "msg": "解析成功",
            "data": dataclasses.asdict(video_info),
        }
    except Exception as err:
        event_log.record(
            "parse", "bad", f"ID 解析失败：{source.value} / {video_id}：{err}", user
        )
        return {
            "code": 500,
            "msg": str(err),
        }


class ShortcutParseRequest(BaseModel):
    key: str
    url: str


# iOS 快捷指令标准提示文案：快捷指令在 success=false 时直接用 message 弹窗（Alert）。
# 客户端场景（无法连接服务器、下载失败、服务器任务失败）由快捷指令自身的失败分支
# 弹出同类文案，见 docs/knowledge/03_core_flows.md 的映射表。
SHORTCUT_ALERT_MESSAGES = {
    "success": "已获取视频下载地址",
    "invalid_url": "视频链接无效，请检查分享内容",
    "parse_failed": "视频解析失败，可能暂不支持该平台",
    "invalid_key": "API Key 无效，请重新配置",
}


def _shortcut_error(code: int, error_type: str, detail: str = "") -> dict:
    response = {
        "code": code,
        "success": False,
        "error_type": error_type,
        "message": SHORTCUT_ALERT_MESSAGES[error_type],
    }
    if detail:
        response["detail"] = detail
    return response


async def _shortcut_parse(key: str, url: str) -> dict:
    owner = key_store.find_owner(key)
    if owner is None:
        event_log.record("parse", "bad", "快捷指令解析失败：API Key 无效", "")
        return _shortcut_error(401, "invalid_key")

    share_url = extract_url(url)
    if share_url is None:
        event_log.record(
            "parse", "bad", f"快捷指令解析失败：未检测到有效的分享链接：{url}", owner
        )
        return _shortcut_error(400, "invalid_url")

    try:
        video_info = await parse_video_share_url(share_url)
    except Exception as err:
        event_log.record("parse", "bad", f"快捷指令解析失败：{err}", owner)
        return _shortcut_error(400, "parse_failed", str(err))

    if not video_info.video_url:
        event_log.record(
            "parse", "bad", f"快捷指令解析失败：无可用视频地址：{share_url}", owner
        )
        return _shortcut_error(400, "parse_failed", "解析成功但没有可用的视频下载地址")

    event_log.record("parse", "ok", f"快捷指令解析成功：{share_url}", owner)

    headers = dict(video_info.headers or {})
    headers.setdefault("User-Agent", BaseParser.random_user_agent())

    response = {
        "code": 200,
        "success": True,
        "error_type": "success",
        "title": video_info.title,
        "download_url": video_info.video_url,
        "message": SHORTCUT_ALERT_MESSAGES["success"],
        "headers": headers,
    }
    if video_info.cover_url:
        response["cover_url"] = video_info.cover_url
    return response


@app.post("/api/shortcut/parse")
async def shortcut_parse(payload: ShortcutParseRequest):
    return await _shortcut_parse(payload.key, payload.url)


@app.get("/api/shortcut/parse")
async def shortcut_parse_get(key: str, url: str):
    return await _shortcut_parse(key, url)


@app.get("/api/shortcut/key")
async def get_shortcut_key(owner: str = _key_owner_dependency):
    key = key_store.get_or_create_key(owner)
    return {
        "code": 200,
        "msg": "ok",
        "data": {"owner": owner, "key": key},
    }


@app.post("/api/shortcut/key/reset")
async def reset_shortcut_key(owner: str = _key_owner_dependency):
    key = key_store.reset_key(owner)
    return {
        "code": 200,
        "msg": "ok",
        "data": {"owner": owner, "key": key},
    }


class CredentialsRequest(BaseModel):
    username: str
    password: str


@app.get("/api/settings/credentials", dependencies=_auth_dependency)
async def get_credentials():
    username, _ = auth_store.load_credentials()
    return {
        "code": 200,
        "msg": "ok",
        "data": {"username": username},
    }


@app.post("/api/settings/credentials", dependencies=_auth_dependency)
async def set_credentials(payload: CredentialsRequest):
    username = payload.username.strip()
    password = payload.password
    if not username or not password:
        return {
            "code": 400,
            "msg": "账号名称和密码不能为空",
        }

    auth_store.save_credentials(username, password)
    # 凭据变更后所有会话立即失效，需要重新登录
    auth_store.clear_sessions()
    event_log.record("settings", "ok", "账号名称或密码已修改", username)
    return {
        "code": 200,
        "msg": "账号已更新，请重新登录",
        "data": {"username": username, "relogin_required": True},
    }


class CookieRequest(BaseModel):
    source: str
    cookie: str


MAX_COOKIE_LEN = 8000
VALID_COOKIE_SOURCES = {source.value for source in VideoSource}


@app.get("/api/settings/cookies", dependencies=_auth_dependency)
async def get_cookies():
    return {
        "code": 200,
        "msg": "ok",
        "data": {"cookies": cookie_store.list_cookies()},
    }


@app.post("/api/settings/cookies")
async def set_cookie(payload: CookieRequest, user: str = _key_owner_dependency):
    source = payload.source.strip().lower()
    cookie = payload.cookie.strip()
    if source not in VALID_COOKIE_SOURCES:
        return {"code": 400, "msg": "无效的平台来源"}
    if len(cookie) > MAX_COOKIE_LEN:
        return {"code": 400, "msg": f"Cookie 长度不能超过 {MAX_COOKIE_LEN} 个字符"}
    if not cookie:
        if not cookie_store.delete_cookie(source):
            return {"code": 400, "msg": "该平台没有已保存的 Cookie"}
        event_log.record("settings", "ok", f"已清除 {source} 的 Cookie", user)
        return {"code": 200, "msg": "Cookie 已清除", "data": {"source": source}}

    cookie_store.set_cookie(source, cookie)
    event_log.record("settings", "ok", f"已保存 {source} 的 Cookie", user)
    return {"code": 200, "msg": "Cookie 已保存", "data": {"source": source}}


@app.get("/api/events")
async def get_events(limit: int = 200, user: str = _key_owner_dependency):
    limit = max(1, min(limit, event_log.MAX_EVENTS))
    return {
        "code": 200,
        "msg": "ok",
        "data": {"events": event_log.list_events(limit)},
    }


class EventRequest(BaseModel):
    message: str


# 前端本地校验失败（请求未发出）也记入日志；服务端固定 parse/bad 并限长，防止任意写入
MAX_EVENT_MESSAGE_LEN = 500


@app.post("/api/events")
async def post_event(payload: EventRequest, user: str = _key_owner_dependency):
    message = payload.message.strip()[:MAX_EVENT_MESSAGE_LEN]
    if not message:
        return {
            "code": 400,
            "msg": "日志内容不能为空",
        }
    entry = event_log.record("parse", "bad", message, user)
    return {
        "code": 200,
        "msg": "ok",
        "data": {"event": entry},
    }


mcp.setup_server()

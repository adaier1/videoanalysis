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
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"title": "登录 · parse-video-py", "error": "用户名或密码不正确"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"Cache-Control": "no-store"},
        )
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
    auth_store.drop_session(request.cookies.get(SESSION_COOKIE, ""))
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/video/share/url/parse", dependencies=_auth_dependency)
async def share_url_parse(url: str):
    video_share_url = extract_url(url)
    if video_share_url is None:
        return {
            "code": 400,
            "msg": "未检测到有效的分享链接",
        }

    try:
        video_info = await parse_video_share_url(video_share_url)
        return {
            "code": 200,
            "msg": "解析成功",
            "data": dataclasses.asdict(video_info),
        }
    except Exception as err:
        return {
            "code": 500,
            "msg": str(err),
        }


@app.get("/video/id/parse", dependencies=_auth_dependency)
async def video_id_parse(source: VideoSource, video_id: str):
    try:
        video_info = await parse_video_id(source, video_id)
        return {
            "code": 200,
            "msg": "解析成功",
            "data": dataclasses.asdict(video_info),
        }
    except Exception as err:
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
        return _shortcut_error(401, "invalid_key")

    share_url = extract_url(url)
    if share_url is None:
        return _shortcut_error(400, "invalid_url")

    try:
        video_info = await parse_video_share_url(share_url)
    except Exception as err:
        return _shortcut_error(400, "parse_failed", str(err))

    if not video_info.video_url:
        return _shortcut_error(400, "parse_failed", "解析成功但没有可用的视频下载地址")

    headers = dict(video_info.headers or {})
    headers.setdefault("User-Agent", BaseParser.get_default_headers()["User-Agent"])

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
    return {
        "code": 200,
        "msg": "账号已更新，请重新登录",
        "data": {"username": username, "relogin_required": True},
    }


mcp.setup_server()

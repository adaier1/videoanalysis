---
knowledge_version: 1
last_scanned_at: 2026-06-08
source_commit: dd55df3
confidence: high
---

# 项目地图

## 技术栈

| 类型 | 技术/框架 | 版本 | 证据来源 |
|---|---|---|---|
| 语言 | Python | >=3.10 | `pyproject.toml:requires-python` |
| Web 框架 | FastAPI | >=0.110 | `pyproject.toml:web deps` |
| ASGI 服务器 | uvicorn | >=0.29 | `pyproject.toml:web deps` |
| 模板引擎 | Jinja2 | >=3.1 | `pyproject.toml:web deps` |
| MCP 集成 | fastapi-mcp | >=0.4 | `pyproject.toml:web deps` |
| CLI 框架 | Typer | >=0.12 | `pyproject.toml:cli deps` |
| CLI 输出 | Rich | >=13.0 | `pyproject.toml:cli deps` |
| HTTP 客户端 | httpx / aiohttp | >=0.27 / >=3.9 | `pyproject.toml:dependencies` |
| HTML 解析 | parsel + lxml | >=1.9 / >=5.0 | `pyproject.toml:dependencies` |
| JSON 查询 | jmespath | >=1.0 | `pyproject.toml:dependencies` |
| UA 伪装 | fake-useragent | >=1.5 | `pyproject.toml:dependencies` |
| 构建工具 | hatchling | - | `pyproject.toml:build-system` |
| 包管理 | uv | - | `README.md:69-78` |
| 测试 | pytest + pytest-asyncio | >=8.0 / >=0.23 | `pyproject.toml:dev deps` |
| 代码格式 | black + isort + flake8 | line-length: 88 | `pyproject.toml:tool.black/isort` |

## 目录结构

| 路径 | 作用 | 是否核心 | 证据来源 |
|---|---|---|---|
| `main.py` | Web 服务启动入口 | 是 | `main.py:1-6` |
| `src/parse_video_py/` | 主包源码 | 是 | `pyproject.toml:packages` |
| `src/parse_video_py/parser/` | 26 个平台解析器 + BaseParser + 路由映射 | 是 | `src/parse_video_py/parser/__init__.py` |
| `src/parse_video_py/web.py` | FastAPI 应用、路由、登录鉴权（会话 + Basic Auth 兼容） | 是 | `src/parse_video_py/web.py` |
| `src/parse_video_py/cli/` | CLI 命令行工具 | 是 | `src/parse_video_py/cli/__init__.py` |
| `src/parse_video_py/utils.py` | URL 提取、query 参数解析工具 | 是 | `src/parse_video_py/utils.py` |
| `src/parse_video_py/key_store.py` | API Key JSON 持久化存储（按用户隔离） | 是 | `src/parse_video_py/key_store.py` |
| `src/parse_video_py/auth_store.py` | 登录凭据 JSON 持久化（默认 admin/admin123）+ 内存会话管理 | 是 | `src/parse_video_py/auth_store.py` |
| `src/parse_video_py/event_log.py` | 系统事件日志（解析/登录/设置），JSONL 持久化 + 内存最近列表 | 是 | `src/parse_video_py/event_log.py` |
| `src/parse_video_py/cookie_store.py` | 平台 Cookie JSON 持久化（按平台存储，解析时注入请求头） | 是 | `src/parse_video_py/cookie_store.py` |
| `src/parse_video_py/templates/` | Jinja2 HTML 模板 | 否 | `src/parse_video_py/templates/` |
| `tests/` | 测试用例 | 否 | `tests/` |
| `docs/` | 文档（agents 配置等） | 否 | `docs/` |
| `.github/workflows/` | CI/CD 配置 | 否 | `.github/workflows/` |

## 启动入口

| 类型 | 入口位置 | 启动方式 | 证据来源 |
|---|---|---|---|
| Web 服务 | `main.py` | `uvicorn main:app --reload` | `main.py:4-6` |
| Web 服务（生产） | `parse_video_py.web:app` | `uvicorn parse_video_py.web:app --host 0.0.0.0 --port 8000` | `Dockerfile:20` |
| CLI | `parse_video_py.cli:app` | `parse-video-py parse/serve/version` | `pyproject.toml:project.scripts` |
| Python SDK | `parse_video_py.parse_video_share_url` | `asyncio.run(parse_video_share_url(url))` | `src/parse_video_py/__init__.py:1` |

## 核心模块

| 模块 | 路径 | 职责 | 被谁调用 | 修改风险 | 证据来源 |
|---|---|---|---|---|---|
| BaseParser | `parser/base.py` | 定义解析器抽象基类、数据结构、VideoSource 枚举 | 所有解析器 | **高** | `parser/base.py` |
| 解析器路由 | `parser/__init__.py` | VideoSource→域名→解析器映射、`parse_video_share_url()`、`parse_video_id()` | web.py、cli | **高** | `parser/__init__.py:29-193` |
| Web 应用 | `web.py` | FastAPI 路由、登录鉴权（会话 Cookie + Basic Auth 兼容）、MCP 挂载 | uvicorn | **高** | `web.py` |
| CLI 入口 | `cli/__init__.py` | Typer 命令注册（parse/serve/version） | pyproject.toml scripts | 中 | `cli/__init__.py` |
| CLI 解析逻辑 | `cli/_parse.py` | 解析命令核心逻辑、批量解析、并发控制 | cli/__init__.py | 中 | `cli/_parse.py` |
| CLI 输出 | `cli/output.py` | 结果格式化（text/json） | cli/_parse.py | 低 | `cli/output.py` |
| 工具函数 | `utils.py` | URL 提取、query 参数解析、HTTP 客户端工厂 | web.py、cli/_parse.py、所有解析器 | **高** | `utils.py` |
| API Key 存储 | `key_store.py` | JSON 文件读写、Key 生成/重置/校验（`secrets.compare_digest`） | web.py | 中 | `key_store.py` |
| 登录凭据/会话存储 | `auth_store.py` | 凭据 JSON 读写、`secrets.compare_digest` 校验、内存会话创建/失效 | web.py | **高** | `auth_store.py` |
| 系统事件日志 | `event_log.py` | 事件记录（解析/登录/设置）与内存最近列表、JSONL 持久化（上限 1000 条） | web.py | 中 | `event_log.py` |
| 平台 Cookie 存储 | `cookie_store.py` | 按平台读写 Cookie JSON；`BaseParser.get_default_headers()` 经 `get_cookie_header()` 读取并注入 `Cookie` 请求头 | web.py、parser/base.py | 中 | `cookie_store.py` |
| 26 个解析器 | `parser/*.py` | 各平台视频/图集解析 | parser/__init__.py 路由 | 中 | `parser/` |

## 外部依赖

| 依赖 | 用途 | 配置位置 | 调用位置 | 证据来源 |
|---|---|---|---|---|
| httpx | HTTP 请求（异步） | `pyproject.toml` | 各平台解析器（通过 `utils.py:create_async_client()` 工厂创建） | `parser/douyin.py`、`parser/weibo.py` 等 |
| aiohttp | HTTP 请求（异步，部分解析器使用） | `pyproject.toml` | 部分解析器 | `pyproject.toml:dependencies` |
| fake-useragent | 随机 User-Agent 生成 | `pyproject.toml` | `BaseParser.get_default_headers()` | `parser/base.py:99` |
| parsel + lxml | HTML/XPath 解析 | `pyproject.toml` | 部分解析器 | `pyproject.toml:dependencies` |
| jmespath | JSON 数据查询 | `pyproject.toml` | 部分解析器 | `pyproject.toml:dependencies` |
| pyyaml | YAML 解析（小红书解析器用） | `pyproject.toml` | `parser/redbook.py` | `parser/redbook.py:6` |
| fastapi-mcp | MCP 协议集成 | `pyproject.toml` | `web.py` | `web.py:10,26-27` |

## 数据存储

项目无数据库。解析结果仍为无状态即时返回；持久化文件都在 `PARSE_VIDEO_DATA_DIR`（默认 `data/`，容器内由 named volume `parse_video_data` 持久化到 `/app/data`）：

- `key_store.py` → `api_keys.json`：API Key 按用户（owner）隔离，重置后旧 Key 立即失效
- `auth_store.py` → `credentials.json`：登录账号名称与密码（默认 admin/admin123，设置页修改）；会话为进程内存，重启后失效
- `event_log.py` → `events.jsonl`：系统事件（解析/登录/设置）逐行 JSON 追加持久化（上限 1000 条，启动时载入）
- `cookie_store.py` → `platform_cookies.json`：平台 Cookie 按平台（VideoSource 值）持久化，仅登录用户可通过设置页管理

> 注意：`data/platform_cookies.json` 含账号 Cookie（敏感），发布到 GitHub 前必须核查排除（`.gitignore` 已排除 `data/`）。

- 已检查路径：`src/`、`tests/`、`requirements.txt`、`pyproject.toml`
- 证据：无 migration、无 ORM、无数据库连接配置；Key 与凭据存储为 JSON 文件

> 注意：`data/credentials.json` 含凭据，发布到 GitHub 前必须核查排除（`.gitignore` 已排除 `data/`）。

## API 路由

| 方法 | 路径 | 功能 | Handler | 证据来源 |
|---|---|---|---|---|
| GET | `/` | Web 界面（未登录时重定向到 `/login`） | `web.py:read_item` | `web.py` |
| GET | `/login` | 登录页 | `web.py:login_page` | `web.py` |
| POST | `/login` | 登录表单（成功创建会话并写 Cookie） | `web.py:login_submit` | `web.py` |
| POST | `/logout` | 退出登录（清除会话与 Cookie） | `web.py:logout` | `web.py` |
| GET | `/healthz` | 容器健康检查（不受登录影响） | `web.py:healthz` | `web.py` |
| GET | `/video/share/url/parse` | 分享链接解析 | `web.py:share_url_parse` | `web.py:75` |
| GET | `/video/id/parse` | 视频 ID 解析 | `web.py:video_id_parse` | `web.py:98` |
| GET/POST | `/api/shortcut/parse` | iOS 快捷指令解析（GET `?key&url` 或 POST `{key,url}`，返回 download_url+headers，仅 Key 鉴权） | `web.py:_shortcut_parse`（`shortcut_parse`/`shortcut_parse_get`） | `tests/test_shortcut_api.py` |
| GET | `/api/shortcut/key` | 查看/自动生成当前登录用户 API Key（受登录保护） | `web.py:get_shortcut_key` | `web.py` |
| POST | `/api/shortcut/key/reset` | 重置 API Key（旧 Key 立即失效，受登录保护） | `web.py:reset_shortcut_key` | `web.py` |
| GET | `/api/settings/credentials` | 查看当前登录账号名称（受登录保护） | `web.py:get_credentials` | `web.py` |
| POST | `/api/settings/credentials` | 修改账号名称与密码（受登录保护，成功后全部会话失效） | `web.py:set_credentials` |
| GET | `/api/settings/cookies` | 查看已保存的平台 Cookie（受登录保护） | `web.py:get_cookies` |
| POST | `/api/settings/cookies` | 保存/清除平台 Cookie（受登录保护，空 Cookie 即清除；来源必须是有效 VideoSource，长度限 4000） | `web.py:set_cookie` | `web.py` |
| GET | `/api/events` | 系统事件日志（解析/登录/设置，受登录保护，倒序返回） | `web.py:get_events` | `tests/test_event_log.py` |
| POST | `/api/events` | 记录前端本地校验失败（受登录保护，固定 parse/bad，消息限长 500） | `web.py:post_event` | `tests/test_event_log.py` |
| MCP | `/mcp` | AI 工具集成 | FastApiMCP 自动注册 | `web.py:26-27,114` |

## 环境变量

| 变量 | 用途 | 是否敏感 | 默认值 | 使用位置 | 证据来源 |
|---|---|---|---|---|---|
| `PARSE_VIDEO_USERNAME` | 登录账号初始值（仅当 `credentials.json` 不存在时生效） | 是 | 未设置=用默认 `admin` | `auth_store.py:load_credentials()` | `auth_store.py` |
| `PARSE_VIDEO_PASSWORD` | 登录密码初始值（仅当 `credentials.json` 不存在时生效） | 是 | 未设置=用默认 `admin123` | `auth_store.py:load_credentials()` | `auth_store.py` |
| `PARSE_VIDEO_PROXY` | HTTP 代理地址 | 是 | 未设置=不使用代理，格式：`http://[user:pass@]host:port` | `utils.py:create_async_client()` | `utils.py` |
| `PARSE_VIDEO_PORT` | Docker Compose 宿主端口映射 | 否 | 8000 | `docker-compose.yml` | `.env.example` |
| `PARSE_VIDEO_DATA_DIR` | API Key JSON 存储目录 | 否 | `data`（容器内 `/app/data`，named volume 持久化） | `key_store.py` | `key_store.py` |

## 未确认事项

- 无

# Changelog

所有重要变更均会记录在此文件中。

## [Unreleased] - 2026-11-01

### 新增功能

- **WebUI 登录功能**：打开网页需登录，默认账号 `admin` / `admin123`；登录页 `templates/login.html`，会话 HttpOnly Cookie（7 天）
- **设置页修改账号名称与密码**：`GET/POST /api/settings/credentials`，凭据持久化到 `data/credentials.json`，保存后全部会话失效需重新登录；新增退出登录（`POST /logout`）
- **凭据存储模块 `auth_store.py`**：凭据文件优先，环境变量 `PARSE_VIDEO_USERNAME`/`PARSE_VIDEO_PASSWORD` 仅作为文件缺失时的初始值；校验保持 `secrets.compare_digest()`
- **Basic Auth 兼容**：API 客户端仍可用账号名称/密码作为 Basic 凭据；`/healthz` 不受登录影响
- **新增测试** `tests/test_auth.py`（登录/会话/凭据修改/登出），既有测试同步加鉴权；`.gitignore` 排除含凭据的 `data/` 目录
- **Cookie 管理（WebUI 顶部导航新视图）**：平台下拉 + Cookie 文本域，保存/清除经 `GET/POST /api/settings/cookies`（受登录保护，来源限 VideoSource、长度限 4000），持久化到 `data/platform_cookies.json`；解析时经 `BaseParser.get_default_headers()` 自动注入 `Cookie` 请求头（B 站/腾讯视频/微博等），可解锁 1080P/4K 并提升成功率；B 站已配 Cookie 时改走 `qn=127&fourk=1` dash 最高清晰度（回退 durl）；新增 `cookie_store.py` 与 `tests/test_cookie_store.py`

- **Twitter/X GraphQL 登录态兜底（仅在已保存 Cookie 时启用）**：匿名 syndication 读不到媒体时（敏感内容、受保护、已删除），改用 `x.com/i/api/graphql/<queryId>/TweetResultByRestId` 读取 `legacy.entities.media`，Cookie 中的 `ct0` 作 `x-csrf-token`；未保存 Cookie 时仍报明确不可访问错误。queryId 为类常量 `GRAPHQL_QUERY_ID`，X 前端变化时需更新

### Bug 修复

- **Twitter/X 解析器改用 `get_default_headers()`**：此前手工构造请求头，设置页保存的 twitter Cookie 从未被发送；现在按统一规则注入（该 Cookie 对匿名 syndication 接口无解锁作用，受保护推文仍不可读）
- **Twitter/X 媒体提取补强**：顶层 `video` 的 variants 兼容 `type`/`src` 命名（原实现只认 `content_type`/`url`，导致该路径永远取不到 mp4）；无码率时取最后一个 mp4；`photos` 数组与 `media_details` 命名作为兜底；引用推文 `quoted_tweet` 的媒体作为兜底
- **错误信息更明确**：接口返回 JSON 错误或非 JSON（风控、已删除、受保护）时给出对应提示，不再统一报"没有找到视频或图片"；新增 `tests/test_twitter.py` 媒体提取用例

## [v0.0.3] - 2026-04-19

### 新增功能

- **新增 CLI 命令行工具**：支持 `version`/`parse`/`serve` 三个子命令，可通过 `parse-video-py` 入口直接使用
- **新增 CLI `-h` 简写**：所有命令支持 `-h` 作为 `--help` 的简写
- **新增 pyproject.toml**：使用 hatchling 构建，支持 `[web]`/`[cli]`/`[dev]` 可选依赖安装
- **新增包公开 API**：支持 `from parse_video_py import VideoSource, parse_video_share_url` 直接调用

### 架构重构

- **迁移到 src 标准布局**：`parser/`、`utils/`、`templates/` 统一迁移到 `src/parse_video_py/` 下
- **uv 包管理**：从 venv + requirements.txt 迁移到 uv + pyproject.toml，支持 `uv pip install -e ".[all]"`
- **Web 服务拆分**：从 `main.py` 提取到 `src/parse_video_py/web.py`，`main.py` 改为薄入口
- **URL 工具统一**：`URL_REG` 正则和 `extract_url` 提取到 `utils.py`，消除 web/cli 模块间的重复定义

### 优化改进

- **Web 序列化**：使用 `dataclasses.asdict()` 替代 `__dict__`，正确处理嵌套 dataclass 序列化
- **Auth 依赖缓存**：Basic Auth 依赖在模块加载时构建一次，避免每个路由重复调用
- **批量解析并发限制**：CLI 批量解析添加 `Semaphore(10)` 防止无界并发
- **Dockerfile 更新**：使用 uv 安装依赖，适配 src 布局
- **CI 更新**：GitHub Actions 改用 `astral-sh/setup-uv`

---

## [v0.0.2] - 2026-04-18

### 新增功能

- **新增 B站(哔哩哔哩) 视频解析**：支持 bilibili.com、b23.tv、m.bilibili.com 域名
- **新增 Twitter/X 视频解析**：支持 twitter.com、x.com、t.co 域名
- **新增微博图集解析**：支持微博图片帖子的图集批量提取
- **新增抖音 Live Photo 实况照片支持**：通过 slidesinfo API 提取实况照片视频
- **新增图集批量下载功能**：前端支持图集图片批量下载 (#58)
- **新增 MCP 支持**：通过 StreamableHttp 方式接入 MCP 协议，接入 URL: `/mcp`
- **新增主题样式选择**：前端页面支持多种主题风格切换
- **新增 Basic Auth 自定义认证**：支持通过环境变量自定义用户名密码 (#48)
- **新增 Claude Code 集成**：添加 CLAUDE.md 项目指引和 GitHub Actions CI 工作流

### 优化改进

- **小红书图集图片高清化**：图集图片使用高清地址，优化图片域名替换逻辑 (#45)
- **抖音图集解析音频**：支持抖音图集内容的音频提取 (#70)
- **单元测试覆盖**：添加核心模块单元测试，pre-commit 支持提交时自动运行测试
- **分享链接正则优化**：优化 URL 匹配正则表达式，增强无效输入处理鲁棒性 (#74)
- **依赖管理优化**：整理 requirements.txt 依赖项

### Bug 修复

- **修复无效分享链接导致崩溃**：无效 URL 输入不再导致服务异常
- **修复小红书图片域名替换逻辑**：当图片 URL 不包含 notes_pre_post 时使用原域名

---

## [v0.0.1] - 初始版本

### 基础功能

- 支持 20+ 平台视频去水印解析
- 支持 4 平台图集解析（抖音、快手、小红书、皮皮虾）
- 支持 LivePhoto 解析（小红书）
- FastAPI Web 服务 + REST API 接口
- 前端解析页面
- Docker 部署支持

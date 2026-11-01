---
knowledge_version: 1
last_scanned_at: 2026-06-08
source_commit: dd55df3
confidence: high
---

# 核心业务流程

## 流程：分享链接解析

### 是否已确认

- 状态：已确认
- 证据来源：`web.py:75-95`、`parser/__init__.py:148-173`

### 触发入口

| 类型 | 路径/接口/命令 | 入口代码 |
|---|---|---|
| HTTP API | `GET /video/share/url/parse?url=<share_url>` | `web.py:share_url_parse` |
| CLI | `parse-video-py parse "<url>"` | `cli/__init__.py:parse` → `cli/_parse.py:run_parse` |
| SDK | `asyncio.run(parse_video_share_url(url))` | `parser/__init__.py:148` |

### 执行链路

1. 接收分享链接（URL 参数/CLI 参数/SDK 参数）
2. `utils.py:extract_url()` 从文本中提取 URL
3. `parser/__init__.py:parse_video_share_url()` 遍历 `video_source_info_mapping`，用域名匹配确定平台
4. 实例化对应平台的 Parser 类
5. 调用 `parser.parse_share_url(share_url)` 获取 `VideoInfo`
6. 各平台解析器内部流程：
   - 解析 URL 域名和路径，提取视频 ID
   - 构造平台 API 请求（带 UA 伪装；若该平台在设置页保存了 Cookie，`BaseParser.get_default_headers()` 自动注入 `Cookie` 请求头）
   - 解析响应（JSON/HTML），提取视频/图集信息
   - 返回标准 `VideoInfo` 对象

   Cookie 解锁清晰度：B 站在已配置 Cookie 时以 `qn=127&fourk=1&fnval=16` 请求 playurl，优先选择 dash 中最高清晰度（最高 4K，响应需带 Referer），回退 durl；未配置 Cookie 时保持原 `qn=80` durl 行为。

   Twitter/X 登录态兜底：默认走匿名 syndication 接口（`cdn.syndication.twimg.com/tweet-result`，token 由 tweet ID 计算）。该接口读不到敏感内容、受保护或已删除的推文（返回 `TweetTombstone`/`TweetUnavailable`）。仅当设置页保存了 twitter Cookie 时，解析器才走 `x.com/i/api/graphql/<queryId>/TweetResultByRestId` 登录态接口兜底，需要 Cookie 中的 `auth_token` 与 `ct0`（作 `x-csrf-token`）；queryId 会随 X 前端发布变化。未保存 Cookie 时直接给出不可访问的明确错误。
7. Web/API 模式：`dataclasses.asdict(video_info)` 转为 JSON 返回

### 关键代码

| 类/函数/文件 | 职责 | 来源 |
|---|---|---|
| `parse_video_share_url()` | URL→平台路由→调用解析器 | `parser/__init__.py:148` |
| `video_source_info_mapping` | 平台→域名→解析器映射表 | `parser/__init__.py:29-145` |
| `BaseParser.parse_share_url()` | 解析器抽象接口 | `parser/base.py:103` |
| `extract_url()` | 从文本中提取 URL | `utils.py:7` |
| `dataclasses.asdict()` | VideoInfo 序列化 | `web.py:89` |

### 数据流

- 输入：用户分享链接（字符串）
- 处理：域名匹配→平台识别→HTTP 请求→HTML/JSON 解析
- 输出：`VideoInfo`（video_url, cover_url, title, music_url, images, author, headers）
- 存储：无持久化（Key 存储见 iOS 快捷指令 API 流程）

### 配置项

| 配置项 | 用途 | 读取位置 |
|---|---|---|
| `PARSE_VIDEO_USERNAME` | 登录账号初始值（凭据文件缺失时生效） | `auth_store.py:load_credentials()` |
| `PARSE_VIDEO_PASSWORD` | 登录密码初始值（凭据文件缺失时生效） | `auth_store.py:load_credentials()` |
| `fake_useragent` | 随机 UA 伪装 | `parser/base.py:random_user_agent()` |
| `platform_cookies.json`（设置页保存） | 平台 Cookie，解析时注入 `Cookie` 请求头 | `cookie_store.py`、`parser/base.py:get_cookie_header()` |

### 异常处理

- URL 无法识别平台：抛出 `ValueError("share url does not have source config")` → `parser/__init__.py:164`
- 解析器未配置：抛出 `ValueError("source has no video parser")` → `parser/__init__.py:167`
- Web 层捕获所有异常返回 `{"code": 500, "msg": str(err)}` → `web.py:91-95`
- CLI 层区分单条失败和全部失败 → `cli/_parse.py:84-101`

### 修改风险

- 修改 `video_source_info_mapping` 影响所有平台的 URL 路由
- 修改 `BaseParser` 接口影响所有 26 个解析器
- 修改 `VideoInfo` 数据结构影响 Web API 响应格式

### 未确认事项

- 无

---

## 流程：视频 ID 解析

### 是否已确认

- 状态：已确认
- 证据来源：`web.py:98-111`、`parser/__init__.py:176-193`

### 触发入口

| 类型 | 路径/接口/命令 | 入口代码 |
|---|---|---|
| HTTP API | `GET /video/id/parse?source=<VideoSource>&video_id=<id>` | `web.py:video_id_parse` |
| SDK | `asyncio.run(parse_video_id(VideoSource.DouYin, "xxx"))` | `parser/__init__.py:176` |

### 执行链路

1. 接收 VideoSource 枚举和视频 ID
2. 从 `video_source_info_mapping` 查找对应解析器
3. 实例化解析器，调用 `parser.parse_video_id(video_id)`
4. 返回标准 `VideoInfo` 对象

### 关键代码

| 类/函数/文件 | 职责 | 来源 |
|---|---|---|
| `parse_video_id()` | 根据平台枚举和 ID 调用解析器 | `parser/__init__.py:176` |
| `VideoSource` | 平台枚举定义 | `parser/base.py:9-38` |

### 修改风险

- 与分享链接解析共用 `video_source_info_mapping`，修改映射表需同时验证两条链路

### 未确认事项

- 无

---

## 流程：CLI 批量解析

### 是否已确认

- 状态：已确认
- 证据来源：`cli/_parse.py`

### 触发入口

| 类型 | 命令 | 入口代码 |
|---|---|---|
| CLI | `parse-video-py parse "url1" "url2"` | `cli/__init__.py:parse` |
| CLI（文件） | `parse-video-py parse -f urls.txt` | `cli/_parse.py:18-28` |
| CLI（管道） | `echo "url" \| parse-video-py parse -f -` | `cli/_parse.py:20-21` |

### 执行链路

1. 接收 URL 列表（参数/文件/stdin）
2. 单条：`asyncio.run(_parse_single())` → 直接解析
3. 多条：`asyncio.run(_parse_batch())` → `asyncio.Semaphore(10)` 控制并发
4. 格式化输出（text 或 json）

### 关键代码

| 类/函数/文件 | 职责 | 来源 |
|---|---|---|
| `_CONCURRENCY_LIMIT = 10` | 并发限制 | `cli/_parse.py:14` |
| `_limited_parse_single()` | 带信号量的单条解析 | `cli/_parse.py:45-48` |
| `_parse_batch()` | 批量并发解析 | `cli/_parse.py:51-57` |

### 未确认事项

- 无

---

## 流程：登录鉴权（会话 + Basic Auth 兼容）

### 是否已确认

- 状态：已确认
- 证据来源：`web.py`（`require_login`、`/login`、`/logout`）、`auth_store.py`、`tests/test_auth.py`

### 执行链路

1. 所有页面与 API 路由默认必须登录（`/login`、`/healthz` 除外）
2. 凭据来源优先级：`data/credentials.json`（可在设置中修改）→ `PARSE_VIDEO_USERNAME`/`PARSE_VIDEO_PASSWORD` 环境变量（仅当凭据文件不存在时作为初始值）→ 默认 `admin` / `admin123`
3. 未登录访问 `/` 重定向到 `/login` 登录页；表单 POST `/login` 验证凭据后创建会话（内存 session token）并写入 HttpOnly Cookie（`pv_session`，7 天）
4. API 客户端仍可用 Basic Auth（`_basic_user` 解析 Authorization 头），与 Cookie 会话二选一
5. `secrets.compare_digest()` 比较凭据（防时序攻击）
6. 设置页修改账号名称/密码：`POST /api/settings/credentials` 持久化到 `data/credentials.json` 后立即清空全部会话，需重新登录；API Key 按登录用户名（owner）隔离

### 关键代码

| 函数 | 职责 | 来源 |
|---|---|---|
| `require_login()` | 会话 Cookie 或 Basic Auth 二选一鉴权依赖 | `web.py` |
| `current_user()` / `_session_user()` / `_basic_user()` | 解析当前登录用户 | `web.py` |
| `login_page()` / `login_submit()` / `logout()` | 登录页、登录表单、退出 | `web.py` |
| `load_credentials()` / `save_credentials()` / `verify_credentials()` | 凭据 JSON 持久化与校验 | `auth_store.py` |
| `create_session()` / `get_session_user()` / `clear_sessions()` | 内存会话管理 | `auth_store.py` |

### 修改风险

- 使用 `secrets.compare_digest()` 防止时序攻击，不要改为普通字符串比较
- 会话仅存在于进程内存，容器重启后失效（凭据文件持久化）
- 修改凭据后所有会话立即失效；登出/登录流程与 `/` 重定向逻辑需同步测试（`tests/test_auth.py`）

---

## 流程：iOS 快捷指令 API

### 是否已确认

- 状态：已确认
- 证据来源：`web.py:shortcut_parse`、`key_store.py`、`tests/test_shortcut_api.py`

### 触发入口

| 类型 | 路径/接口/命令 | 入口代码 |
|---|---|---|
| HTTP API | `GET/POST /api/shortcut/parse`（GET `?key=<key>&url=` 或 POST JSON `{key, url}`） | `web.py:_shortcut_parse` |
| HTTP API | `GET /api/shortcut/key`（查看/自动生成） | `web.py:get_shortcut_key` |
| HTTP API | `POST /api/shortcut/key/reset`（重置，旧 Key 立即失效） | `web.py:reset_shortcut_key` |

### 执行链路

1. `key_store.find_owner()` 用 `secrets.compare_digest()` 校验 Key，无效返回 401
2. `utils.py:extract_url()` 校验分享链接合法性
3. 复用 `parse_video_share_url()`（不重复实现解析，不执行服务端下载，不写 NAS）
4. 无 `video_url` 时返回 400 明确错误；解析异常（超时、平台变更）返回 400 + 错误信息
5. 响应核心字段：`code/success/error_type/title/download_url/message/headers`；`headers` 取 `VideoInfo.headers`（解析器按需填充防盗链/临时 Token），为空时回退 iOS UA；`cover_url` 有值才返回
6. Key 按 owner（登录账号名称，如默认 `admin`）隔离，首次访问自动生成，持久化到 `api_keys.json`
7. `message` 是快捷指令标准弹窗文案（`web.py:SHORTCUT_ALERT_MESSAGES`），失败时 `detail` 携带原始异常供调试；快捷指令在 `success=false` 时用 Alert 弹 `message`，不得静默结束

### 标准提示文案映射（服务端 + 客户端）

| error_type / 场景 | 来源 | message（iPhone Alert 文案） |
|---|---|---|
| success | 服务端 | 已获取视频下载地址 |
| invalid_url（400） | 服务端 | 视频链接无效，请检查分享内容 |
| parse_failed（400） | 服务端 | 视频解析失败，可能暂不支持该平台 |
| invalid_key（401） | 服务端 | API Key 无效，请重新配置 |
| 无法连接解析服务器 | 快捷指令"获取 URL 内容"失败分支 | 无法连接解析服务器，请检查网络 |
| 下载失败 | 快捷指令存储文件失败分支 | 视频下载失败，请检查网络或稍后重试 |
| 服务器任务失败（远程保存） | 服务器任务接口（如启用） | 服务器下载失败，请查看任务详情 |
| 本地保存成功 | 快捷指令 | 视频已保存到照片相簿 |
| 远程保存提交成功 | 快捷指令 | 视频已提交服务器下载 |

### 修改风险

- Key 校验必须保持 `secrets.compare_digest()`
- `VideoInfo.headers` 为新增可选字段（默认空 dict），影响 API 响应格式
- `/api/shortcut/parse` 仅 Key 鉴权、不走登录鉴权；Key 管理路由受登录保护

### 未确认事项

- 多清晰度选择：现有 `VideoInfo` 仅单条 `video_url`，未实现清晰度参数

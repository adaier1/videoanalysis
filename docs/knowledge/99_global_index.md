---
knowledge_version: 1
last_scanned_at: 2026-06-08
---

# 全局索引

## 按任务读取

| 任务 | 必读文档 | 可选文档 | 注意事项 |
|---|---|---|---|
| 新增平台解析器 | 02_project_map.md、03_core_flows.md、04_code_rules.md | 05_change_safety.md | 参考已有解析器模式 |
| 修改解析逻辑 | 03_core_flows.md、05_change_safety.md | 04_code_rules.md | 先看影响范围 |
| 新增 API 接口 | 02_project_map.md、03_core_flows.md、04_code_rules.md | 06_build_run_deploy.md | 确认路由和响应格式 |
| 修复 Bug | 02_project_map.md、03_core_flows.md、06_build_run_deploy.md | 05_change_safety.md | 先复现问题 |
| 修改鉴权 | 03_core_flows.md、05_change_safety.md | 04_code_rules.md | 注意时序安全 |
| iOS 快捷指令 API / Key 管理 | 02_project_map.md、03_core_flows.md | 05_change_safety.md、06_build_run_deploy.md | Key 校验保持 `secrets.compare_digest()`；不重复实现解析 |
| Cookie 管理（平台 Cookie） | 02_project_map.md、03_core_flows.md | 04_code_rules.md、05_change_safety.md | Cookie 经 `BaseParser.get_default_headers()` 注入，不绕过；B 站已配 Cookie 时走 dash/fourk 高清路径 |
| 修改 CLI | 02_project_map.md、03_core_flows.md、04_code_rules.md | 06_build_run_deploy.md | 注意向后兼容 |
| 代理相关 | 06_build_run_deploy.md（含免费代理获取和测试方法） | 02_project_map.md | 仅测试用免费代理 |
| 部署上线 | 06_build_run_deploy.md | 05_change_safety.md | 不要猜命令 |

## 修改什么，先看哪里

| 想改的内容 | 先看 | 再看 |
|---|---|---|
| 新增解析器 | 03_core_flows.md | 04_code_rules.md |
| API 接口 | 02_project_map.md | 03_core_flows.md |
| 路由映射 | 02_project_map.md | 05_change_safety.md |
| 鉴权逻辑 | 03_core_flows.md | 05_change_safety.md |
| 数据结构 | 02_project_map.md | 05_change_safety.md |
| 部署 | 06_build_run_deploy.md | 05_change_safety.md |
| CLI 命令 | 03_core_flows.md | 04_code_rules.md |

## 按模块读取

| 模块 | 相关文档 | 关键路径 |
|---|---|---|
| 解析器路由 | 02_project_map.md、03_core_flows.md | `parser/__init__.py` |
| BaseParser | 02_project_map.md、04_code_rules.md | `parser/base.py` |
| 各平台解析器 | 03_core_flows.md、04_code_rules.md | `parser/<平台>.py` |
| Web 应用 | 02_project_map.md、03_core_flows.md | `web.py` |
| CLI 工具 | 03_core_flows.md、04_code_rules.md | `cli/` |
| 工具函数 | 02_project_map.md | `utils.py` |
| 平台 Cookie 存储 | 02_project_map.md、03_core_flows.md | `cookie_store.py` |
| Docker 部署 | 06_build_run_deploy.md | `Dockerfile` |

## 核心代码索引

| 文件/类/函数 | 职责 | 相关流程 | 修改风险 |
|---|---|---|---|
| `parser/base.py:VideoSource` | 26 个平台枚举定义 | 路由映射、API 参数 | 高 |
| `parser/base.py:VideoInfo` | 视频信息数据结构 | API 响应格式 | 高 |
| `parser/base.py:BaseParser` | 解析器抽象基类 | 所有解析器继承 | 高 |
| `parser/__init__.py:video_source_info_mapping` | 平台→域名→解析器映射 | URL 路由分发 | 高 |
| `parser/__init__.py:parse_video_share_url()` | 分享链接解析入口 | 核心业务流程 | 高 |
| `parser/__init__.py:parse_video_id()` | 视频 ID 解析入口 | 核心业务流程 | 高 |
| `web.py:app` | FastAPI 应用实例 | Web 服务 | 高 |
| `web.py:require_login()` | 登录鉴权依赖（会话 Cookie 或 Basic Auth） | 登录鉴权 | 高 |
| `auth_store.py` | 登录凭据 JSON 持久化（默认 admin/admin123）+ 内存会话管理 | 登录鉴权 | 高 |
| `utils.py:extract_url()` | URL 提取正则匹配 | 所有解析入口 | 中 |
| `event_log.py:record()` / `event_log.py:list_events()` | 系统事件记录与查询（解析/登录/设置） | 日志页、解析入口 | 中 |
| `utils.py:create_async_client()` | HTTP 客户端工厂（代理注入） | 所有解析器 HTTP 请求 | 高 |
| `cookie_store.py` | 平台 Cookie JSON 持久化（get/set/delete/list） | `web.py` 设置页 API、`parser/base.py` | 中 |
| `parser/base.py:BaseParser.get_default_headers()` | 请求头（UA + 已保存平台 Cookie 注入），实例 `source` 由路由入口传入 | 所有解析器请求 | 高 |
| `cli/_parse.py:run_parse()` | CLI 解析命令入口 | CLI 批量解析 | 中 |

## 配置索引

| 配置项 | 用途 | 使用位置 | 修改风险 |
|---|---|---|---|
| `PARSE_VIDEO_USERNAME` | 登录账号初始值（凭据文件缺失时生效；可运行时在设置页修改） | `auth_store.py` | 低 |
| `PARSE_VIDEO_PASSWORD` | 登录密码初始值（凭据文件缺失时生效；可运行时在设置页修改） | `auth_store.py` | 低 |
| `PARSE_VIDEO_PROXY` | HTTP/HTTPS 代理地址 | `utils.py:create_async_client()` | 中（需重启服务） |
| `pyproject.toml:dependencies` | 核心依赖声明 | 构建安装 | 中 |
| `pyproject.toml:project.scripts` | CLI 入口点 | CLI 安装 | 中 |

## 未确认事项总表

- 无未确认事项

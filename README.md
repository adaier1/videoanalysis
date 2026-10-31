# Video Analysis（视频去水印解析 · WebUI + Docker）

本项目基于 [wujunwei928/parse-video-py](https://github.com/wujunwei928/parse-video-py) 改造，核心解析能力沿用原项目。本地新增：Docker 部署、深色 WebUI 控制面板（分享链接 / 视频 ID 双标签解析、结果卡片、视频/音频/封面下载、图集与 ZIP 打包）、登录鉴权与 API Key、健康检查。**许可证沿用原参考项目（MIT，见 LICENSE）**。

## 快速部署（Docker Compose）

`docker-compose.yml`（不使用 env 变量，直接构建运行）：

```yaml
services:
  parse-video:
    build: .
    image: parse-video-py:local
    container_name: parse-video-py
    restart: unless-stopped
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    volumes:
      - parse_video_data:/app/data

volumes:
  parse_video_data:
```

启动：

```shell
docker compose up -d
```

- 访问 http://127.0.0.1:8000/ ，首次会跳转登录页。
- 默认凭据为 `admin` / `admin123`，登录后请在设置页修改；凭据与 API Key 持久化在 `parse_video_data` 卷（容器内 `/app/data`）。
- 公网部署请务必修改默认凭据。

## API

解析接口（需登录，支持会话或 Basic Auth；`/healthz` 不受鉴权影响）：

```shell
curl -u 'admin:your_password' 'http://127.0.0.1:8000/video/share/url/parse?url=视频分享链接' | jq
```

返回格式：

```json
{
  "author": {
    "uid": "uid",
    "name": "name",
    "avatar": "https://xxx"
  },
  "title": "记录美好生活#峡谷天花板",
  "video_url": "https://xxx",
  "music_url": "https://yyy",
  "cover_url": "https://zzz"
}
```

| 字段名 | 说明 |
| ---- | ---- |
| author.uid | 视频作者 id |
| author.name | 视频作者名称 |
| author.avatar | 视频作者头像 |
| title | 视频标题 |
| video_url | 视频无水印链接 |
| music_url | 视频音乐链接 |
| cover_url | 视频封面 |
| images | 图集图片列表 |
| images.[index].url | 图集图片地址 |
| images.[index].live_photo_url | 图集图片 livephoto 视频地址 |

> 除视频地址外，其他字段可能为空。

另提供 `/api/shortcut/parse`（带 API Key 的快捷解析）与 Key 管理接口。

## MCP 支持

沿用原项目的 MCP 能力，StreamableHttp 接入 URL：`http://localhost:8000/mcp`

## 本地运行

```shell
uv venv && uv pip install -e ".[all]"
uvicorn parse_video_py.web:app --reload
```

CLI：

```shell
parse-video-py parse "https://v.douyin.com/xxx" --format json
parse-video-py serve --port 8000
```

## 支持平台（沿用原项目）

### 图集

| 平台 | 状态 |
|----|----|
| 抖音 | ✔ |
| 快手 | ✔ |
| 小红书 | ✔ |
| 皮皮虾 | ✔ |
| 微博 | ✔ |

LivePhoto：小红书、抖音。

### 视频

小红书、皮皮虾、抖音短视频、火山短视频、皮皮搞笑、快手短视频、微视短视频、西瓜视频、最右、梨视频、度小视(原全民)、逗拍、微博、绿洲、全民K歌、6间房、美拍、新片场、好看视频、虎牙、AcFun、央视网、搜狐视频、哔哩哔哩、腾讯视频、Twitter/X。

> tips：出现解析失败可在 issue 中提问，并提供可复现的平台信息与分享链接；尽量使用 App 分享链接，网页版未做充分测试。

## 许可

MIT，沿用原参考项目 parse-video-py。

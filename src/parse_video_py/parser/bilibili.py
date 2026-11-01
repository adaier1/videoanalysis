import json
from urllib.parse import urlparse

from ..utils import create_async_client
from .base import BaseParser, VideoAuthor, VideoInfo


class BiliBili(BaseParser):
    """
    哔哩哔哩
    """

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )

    REFERER = "https://www.bilibili.com/"

    def get_default_headers(self) -> dict:
        headers = super().get_default_headers()
        headers["User-Agent"] = self.USER_AGENT
        headers["Referer"] = self.REFERER
        return headers

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        bvid = await self._get_bvid_from_url(share_url)
        return await self.parse_video_id(bvid)

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        # 第一步：获取视频信息
        view_api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={video_id}"
        view_resp_data = await self._send_bili_request(view_api_url)

        view_resp = json.loads(view_resp_data)
        if view_resp.get("code") != 0 or not view_resp.get("data", {}).get("pages"):
            raise ValueError(f"无法获取该视频: {view_resp.get('message', '未知错误')}")

        data = view_resp["data"]
        first_page_cid = data["pages"][0]["cid"]

        # 第二步：获取播放链接；已配置 Cookie 时请求更高清晰度（dash 最高可到 4K）
        cookie = self.get_cookie_header()
        if cookie:
            play_api_url = (
                f"https://api.bilibili.com/x/player/playurl?"
                f"otype=json&fnver=0&fnval=16&fourk=1&qn=127&bvid={video_id}"
                f"&cid={first_page_cid}&platform=html5"
            )
        else:
            play_api_url = (
                f"https://api.bilibili.com/x/player/playurl?"
                f"otype=json&fnver=0&fnval=0&qn=80&bvid={video_id}"
                f"&cid={first_page_cid}&platform=html5"
            )
        play_resp_data = await self._send_bili_request(play_api_url)

        play_resp = json.loads(play_resp_data)
        if play_resp.get("code") != 0:
            raise ValueError(
                f"B站API返回错误: {play_resp.get('message', '未知错误')} "
                f"(code: {play_resp.get('code')})"
            )

        # 提取视频URL：优先 dash 最高清晰度（Cookie 解锁），回退 durl
        video_url = ""
        play_data = play_resp.get("data", {})
        dash_videos = play_data.get("dash", {}).get("video", [])
        use_dash = False
        if dash_videos:
            best_video = max(dash_videos, key=lambda v: v.get("id", 0))
            video_url = best_video.get("baseUrl", "")
            use_dash = bool(video_url)
        if not video_url and play_data.get("durl") and len(play_data["durl"]) > 0:
            video_url = play_data["durl"][0].get("url", "")

        if not video_url:
            raise ValueError("无法获取该视频播放链接")

        # 构建视频信息
        video_info = VideoInfo(
            title=data.get("title", ""),
            video_url=video_url,
            cover_url=data.get("pic", ""),
            images=[],  # 空的图片列表
        )
        if use_dash:
            video_info.headers = {"Referer": self.REFERER}

        # 设置作者信息
        owner = data.get("owner", {})
        video_info.author = VideoAuthor(
            uid=str(owner.get("mid", "")),
            name=owner.get("name", ""),
            avatar=owner.get("face", ""),
        )

        return video_info

    async def _get_bvid_from_url(self, raw_url: str) -> str:
        """从URL中提取BVID"""
        try:
            parsed_url = urlparse(raw_url)
        except Exception:
            raise ValueError("URL格式无效")

        if "b23.tv" in parsed_url.netloc:
            # 处理短链接
            async with create_async_client(follow_redirects=False) as client:
                resp = await client.get(raw_url, headers=self.get_default_headers())
                location = resp.headers.get("location")
                if not location:
                    raise ValueError("无法从b23.tv获取重定向链接")
                return await self._get_bvid_from_url(location)

        if "bilibili.com" in parsed_url.netloc:
            path = parsed_url.path.strip("/")
            parts = path.split("/")
            if len(parts) >= 2 and parts[0] == "video":
                if parts[1].startswith("BV"):
                    return parts[1]

        raise ValueError("不是有效的B站视频链接")

    async def _send_bili_request(self, api_url: str) -> str:
        """发送B站API请求"""
        async with create_async_client() as client:
            response = await client.get(api_url, headers=self.get_default_headers())
            if response.status_code != 200:
                raise ValueError(f"HTTP请求失败, 状态码: {response.status_code}")
            return response.text

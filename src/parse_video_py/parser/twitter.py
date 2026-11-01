import json
import math
import re
from typing import Dict, List, Tuple
from urllib.parse import quote

from ..utils import create_async_client
from .base import BaseParser, ImgInfo, VideoAuthor, VideoInfo


class Twitter(BaseParser):
    """
    Twitter/X 解析器
    支持解析 twitter.com 和 x.com 的推文
    支持视频、GIF 和图集
    默认走匿名 syndication 接口；读不到媒体时（敏感内容、受保护推文）若已保存
    twitter Cookie，则用 Cookie 走 GraphQL 登录态接口兜底
    """

    # GraphQL queryId 随 X 前端发布变化，失效时需要更新
    GRAPHQL_QUERY_ID = "2ICDjqPd81tulZcYrtpTuQ"
    GRAPHQL_BEARER = (
        "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
        "=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
    )
    GRAPHQL_FEATURES = {
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }

    async def parse_share_url(self, share_url: str) -> VideoInfo:
        # 处理 t.co 短链: 需要先跟随重定向获取真实 URL
        if "t.co/" in share_url:
            share_url = await self._resolve_tco_url(share_url)

        # 从 URL 中提取 tweet ID
        tweet_id = self._extract_tweet_id(share_url)
        return await self.parse_video_id(tweet_id)

    async def parse_video_id(self, video_id: str) -> VideoInfo:
        token = self._get_token(video_id)
        api_url = (
            f"https://cdn.syndication.twimg.com/tweet-result?"
            f"id={video_id}&token={token}"
        )

        headers = self.get_default_headers()
        headers.update(
            {
                "Accept": "application/json",
                "Referer": "https://platform.twitter.com/",
            }
        )

        async with create_async_client() as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()

        try:
            json_data = response.json()
        except ValueError:
            raise Exception("推文接口返回非 JSON（可能被风控或需要登录）")

        if not isinstance(json_data, dict):
            raise Exception("推文接口返回格式异常")

        error = self._payload_error(json_data)
        if error:
            if self.get_cookie_header():
                return await self._parse_via_graphql(video_id)
            raise Exception(f"{error}（保存该平台的 Cookie 后可尝试登录态接口）")

        # 提取作者信息
        user_data = json_data.get("user", {})
        author_name = user_data.get("name", "")
        author_screen_name = user_data.get("screen_name", "")
        author_avatar = user_data.get("profile_image_url_https", "")
        author_id = user_data.get("id_str", "")

        # 提取推文文本作为标题
        title = json_data.get("text", "")

        # 提取视频、封面和图集
        video_url, cover_url, images = self._collect_media(json_data)

        if not video_url and not images:
            if self.get_cookie_header():
                return await self._parse_via_graphql(video_id)
            raise Exception(
                "该推文中没有找到视频或图片（推文可能无媒体，或媒体被限制/账号受保护）"
            )

        # 使用 screen_name 作为作者名称的补充
        display_name = author_name if author_name else author_screen_name

        video_info = VideoInfo(
            video_url=video_url,
            cover_url=cover_url,
            title=title,
            images=images,
            author=VideoAuthor(
                uid=author_id,
                name=display_name,
                avatar=author_avatar,
            ),
        )
        return video_info

    @staticmethod
    def _payload_error(data: Dict) -> str:
        """接口返回错误或 tombstone 时给出具体原因（匿名接口读不到受保护推文）"""
        errors = data.get("errors")
        if errors:
            first = errors[0] if isinstance(errors, list) and errors else {}
            message = first.get("message", "") if isinstance(first, dict) else ""
            return f"推文无法访问: {message or '未知错误'}"

        typename = data.get("__typename", "")
        if typename and typename != "Tweet":
            tombstone = data.get("tombstone") or {}
            detail = tombstone.get("text") or tombstone.get("description") or ""
            hint = "推文可能已删除、账号受保护或被限制，Cookie 无法解决"
            return f"推文不可匿名访问（{typename}）：{detail or hint}"

        return ""

    @staticmethod
    def _csrf_from_cookie(cookie: str) -> str:
        """从 Cookie 中取 ct0（GraphQL 的 x-csrf-token）"""
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == "ct0":
                return value
        return ""

    @staticmethod
    def _media_entries(data: Dict) -> List[Dict]:
        """兼容 syndication 的 mediaDetails 与 GraphQL legacy 的 entities.media"""
        entries = data.get("mediaDetails") or data.get("media_details") or []
        if not entries:
            entities_media = (data.get("entities") or {}).get("media")
            if isinstance(entities_media, dict):
                entries = entities_media.get("media") or []
            elif isinstance(entities_media, list):
                entries = entities_media
        return entries if isinstance(entries, list) else []

    async def _parse_via_graphql(self, tweet_id: str) -> VideoInfo:
        """用已保存的 Cookie 走 GraphQL 登录态接口读取推文"""
        cookie = self.get_cookie_header()
        if not cookie:
            raise Exception("GraphQL 兜底需要已保存的 twitter Cookie")

        csrf = self._csrf_from_cookie(cookie)
        variables = {
            "tweetId": tweet_id,
            "withCommunity": False,
            "includePromotedContent": False,
            "withVoice": False,
        }
        features = quote(json.dumps(self.GRAPHQL_FEATURES, separators=(",", ":")))
        api_url = (
            f"https://x.com/i/api/graphql/{self.GRAPHQL_QUERY_ID}/TweetResultByRestId?"
            f"variables={quote(json.dumps(variables, separators=(',', ':')))}"
            f"&features={features}"
        )

        headers = self.get_default_headers()
        headers.update(
            {
                "Authorization": f"Bearer {self.GRAPHQL_BEARER}",
                "x-csrf-token": csrf,
                "x-twitter-active-user": "yes",
                "x-twitter-auth-type": "OAuth2Session",
            }
        )

        async with create_async_client() as client:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            raise Exception("GraphQL 接口返回非 JSON（可能被风控或 Cookie 已失效）")

        result = ((payload.get("data") or {}).get("tweetResult") or {}).get(
            "result"
        ) or {}
        typename = result.get("__typename", "")

        if typename == "TweetUnavailable":
            raise Exception(
                f"登录态接口仍无法访问该推文: {result.get('reason') or '未知原因'}"
            )
        if typename == "TweetTombstone":
            tombstone = result.get("tombstone") or {}
            text = tombstone.get("text")
            detail = text.get("text", "") if isinstance(text, dict) else str(text or "")
            raise Exception(f"登录态接口仍无法访问该推文: {detail or '未知原因'}")
        if typename == "TweetWithVisibilityResults":
            result = result.get("tweet") or {}

        legacy = result.get("legacy") or {}
        user = ((result.get("core") or {}).get("user_results") or {}).get(
            "result"
        ) or {}
        user = user.get("legacy") or {}

        video_url, cover_url, images = self._collect_media(legacy)
        if not video_url and not images:
            raise Exception("登录态接口可读，但该推文没有媒体")

        return VideoInfo(
            video_url=video_url,
            cover_url=cover_url,
            title=legacy.get("full_text") or legacy.get("text", ""),
            images=images,
            author=VideoAuthor(
                uid=user.get("id_str", ""),
                name=user.get("name") or user.get("screen_name", ""),
                avatar=user.get("profile_image_url_https", ""),
            ),
        )

    def _collect_media(self, data: Dict) -> Tuple[str, str, List[ImgInfo]]:
        """从推文 JSON 中提取视频、封面和图片，引用推文媒体作为兜底"""
        media_details = self._media_entries(data)
        video_url = ""
        cover_url = ""
        images: List[ImgInfo] = []

        for media in media_details:
            if not isinstance(media, dict):
                continue
            media_type = media.get("type", "")

            if media_type in ("video", "animated_gif"):
                cover_url = cover_url or media.get("media_url_https", "")
                video_info = media.get("video_info") or {}
                video_url = video_url or self._best_mp4(video_info.get("variants", []))
            elif media_type == "photo":
                image_url = media.get("media_url_https", "")
                if image_url:
                    images.append(ImgInfo(url=image_url))

        # 顶层 video 字段兜底（variants 使用 type/src 命名）
        if not video_url:
            top_video = data.get("video") or {}
            video_url = self._best_mp4(top_video.get("variants", []))
            if video_url:
                cover_url = cover_url or top_video.get("poster", "")

        # photos 数组兜底
        if not images:
            for photo in data.get("photos", []):
                if not isinstance(photo, dict):
                    continue
                image_url = photo.get("url") or photo.get("media_url_https", "")
                if image_url:
                    images.append(ImgInfo(url=image_url))

        if images and not cover_url:
            cover_url = images[0].url

        if not video_url and not images:
            quoted = data.get("quoted_tweet")
            if isinstance(quoted, dict):
                return self._collect_media(quoted)

        return video_url, cover_url, images

    @staticmethod
    def _best_mp4(variants: List) -> str:
        """选取最高码率的 mp4，兼容 content_type/url 与 type/src 两种命名；
        无码率信息时取列表最后一个（通常质量最高）"""
        mp4s = []
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            content_type = variant.get("content_type") or variant.get("type") or ""
            url = variant.get("url") or variant.get("src") or ""
            if content_type == "video/mp4" and url:
                mp4s.append((variant.get("bitrate") or 0, url))

        if not mp4s:
            return ""
        if any(bitrate for bitrate, _ in mp4s):
            return max(mp4s, key=lambda item: item[0])[1]
        return mp4s[-1][1]

    async def _resolve_tco_url(self, tco_url: str) -> str:
        """
        解析 t.co 短链接，获取真实 URL
        """
        async with create_async_client(follow_redirects=False) as client:
            response = await client.get(
                tco_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                },
            )
            # t.co 会返回 301 重定向
            if response.status_code in (301, 302):
                location = response.headers.get("location", "")
                if location:
                    return location
        return tco_url

    def _extract_tweet_id(self, share_url: str) -> str:
        """
        从推文 URL 中提取 tweet ID
        支持格式:
        - https://x.com/user/status/1234567890
        - https://twitter.com/user/status/1234567890
        - https://mobile.twitter.com/user/status/1234567890
        """
        pattern = r"(?:twitter\.com|x\.com)/[^/]+/status(?:es)?/(\d+)"
        match = re.search(pattern, share_url)
        if not match:
            raise ValueError(f"无法从 URL 中提取推文 ID: {share_url}")
        return match.group(1)

    def _get_token(self, tweet_id: str) -> str:
        """
        计算 syndication API 所需的 token
        算法: (tweetId / 1e15 * π) 转换为字符串, 去除 "0" 和 "."
        """
        num = float(tweet_id)
        token = (num / 1e15) * math.pi
        token_str = str(token).replace("0", "").replace(".", "")
        return token_str

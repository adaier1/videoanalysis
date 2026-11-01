import pytest

from parse_video_py.parser.base import VideoSource
from parse_video_py.parser.twitter import Twitter


class TestTwitterToken:
    """测试 token 计算逻辑"""

    def test_get_token_normal_id(self):
        """测试普通推文 ID 的 token 生成"""
        tw = Twitter()
        token = tw._get_token("1849000000000000000")
        assert len(token) > 0

    def test_get_token_short_id(self):
        """测试短 ID 的 token 生成"""
        tw = Twitter()
        token = tw._get_token("123456789")
        assert len(token) > 0

    def test_get_token_long_id(self):
        """测试长 ID 的 token 生成"""
        tw = Twitter()
        token = tw._get_token("1879553847283155177")
        assert len(token) > 0


class TestTwitterExtractTweetId:
    """测试推文 ID 提取"""

    def test_x_com_standard_url(self):
        """测试 x.com 标准链接"""
        tw = Twitter()
        tweet_id = tw._extract_tweet_id(
            "https://x.com/elonmusk/status/1849000000000000000"
        )
        assert tweet_id == "1849000000000000000"

    def test_twitter_com_standard_url(self):
        """测试 twitter.com 标准链接"""
        tw = Twitter()
        tweet_id = tw._extract_tweet_id(
            "https://twitter.com/elonmusk/status/1849000000000000000"
        )
        assert tweet_id == "1849000000000000000"

    def test_url_with_query_params(self):
        """测试带查询参数的链接"""
        tw = Twitter()
        tweet_id = tw._extract_tweet_id(
            "https://x.com/user/status/1849000000000000000?s=20"
        )
        assert tweet_id == "1849000000000000000"

    def test_mobile_twitter_com(self):
        """测试 mobile.twitter.com 链接"""
        tw = Twitter()
        tweet_id = tw._extract_tweet_id(
            "https://mobile.twitter.com/user/status/1849000000000000000"
        )
        assert tweet_id == "1849000000000000000"

    def test_invalid_url(self):
        """测试无效链接"""
        tw = Twitter()
        with pytest.raises(ValueError):
            tw._extract_tweet_id("https://x.com/user/likes")

    def test_empty_string(self):
        """测试空字符串"""
        tw = Twitter()
        with pytest.raises(ValueError):
            tw._extract_tweet_id("")


class TestTwitterCollectMedia:
    """测试媒体提取"""

    def test_video_media_details(self):
        """mediaDetails 中的视频"""
        tw = Twitter()
        data = {
            "mediaDetails": [
                {
                    "type": "video",
                    "media_url_https": "https://pbs.twimg.com/thumb.jpg",
                    "video_info": {
                        "variants": [
                            {"content_type": "application/x-mpegURL", "url": "a.m3u8"},
                            {
                                "bitrate": 832000,
                                "content_type": "video/mp4",
                                "url": "b.mp4",
                            },
                            {
                                "bitrate": 2176000,
                                "content_type": "video/mp4",
                                "url": "c.mp4",
                            },
                        ]
                    },
                }
            ]
        }
        video_url, cover_url, images = tw._collect_media(data)
        assert video_url == "c.mp4"
        assert cover_url == "https://pbs.twimg.com/thumb.jpg"
        assert images == []

    def test_top_level_video_fallback(self):
        """顶层 video 使用 type/src 命名时也能取到最高码率 mp4"""
        tw = Twitter()
        data = {
            "video": {
                "poster": "https://pbs.twimg.com/thumb.jpg",
                "variants": [
                    {"type": "application/x-mpegURL", "src": "a.m3u8"},
                    {"type": "video/mp4", "src": "low.mp4"},
                    {"type": "video/mp4", "src": "high.mp4"},
                ],
            }
        }
        video_url, cover_url, images = tw._collect_media(data)
        assert video_url == "high.mp4"
        assert cover_url == "https://pbs.twimg.com/thumb.jpg"
        assert images == []

    def test_photo_media(self):
        """图片推文，第一张作为封面"""
        tw = Twitter()
        data = {
            "mediaDetails": [
                {"type": "photo", "media_url_https": "https://pbs.twimg.com/1.jpg"},
                {"type": "photo", "media_url_https": "https://pbs.twimg.com/2.jpg"},
            ]
        }
        video_url, cover_url, images = tw._collect_media(data)
        assert video_url == ""
        assert [img.url for img in images] == [
            "https://pbs.twimg.com/1.jpg",
            "https://pbs.twimg.com/2.jpg",
        ]
        assert cover_url == "https://pbs.twimg.com/1.jpg"

    def test_photos_array_fallback(self):
        """mediaDetails 为空时用 photos 数组兜底"""
        tw = Twitter()
        data = {"photos": [{"url": "https://pbs.twimg.com/3.jpg"}]}
        video_url, cover_url, images = tw._collect_media(data)
        assert video_url == ""
        assert [img.url for img in images] == ["https://pbs.twimg.com/3.jpg"]
        assert cover_url == "https://pbs.twimg.com/3.jpg"

    def test_quoted_tweet_fallback(self):
        """引用推文的媒体作为兜底"""
        tw = Twitter()
        data = {
            "quoted_tweet": {
                "media_details": [
                    {"type": "photo", "media_url_https": "https://pbs.twimg.com/4.jpg"}
                ]
            }
        }
        video_url, cover_url, images = tw._collect_media(data)
        assert video_url == ""
        assert [img.url for img in images] == ["https://pbs.twimg.com/4.jpg"]
        assert cover_url == "https://pbs.twimg.com/4.jpg"

    def test_graphql_legacy_entities_media(self):
        """GraphQL legacy 的 entities.media（dict 形态）"""
        tw = Twitter()
        legacy = {
            "entities": {
                "media": {
                    "media": [
                        {
                            "type": "video",
                            "media_url_https": "https://pbs.twimg.com/thumb.jpg",
                            "video_info": {
                                "variants": [
                                    {
                                        "bitrate": 832000,
                                        "content_type": "video/mp4",
                                        "url": "low.mp4",
                                    },
                                    {
                                        "bitrate": 2176000,
                                        "content_type": "video/mp4",
                                        "url": "high.mp4",
                                    },
                                ]
                            },
                        }
                    ]
                }
            }
        }
        video_url, cover_url, images = tw._collect_media(legacy)
        assert video_url == "high.mp4"
        assert cover_url == "https://pbs.twimg.com/thumb.jpg"

    def test_entities_media_as_list(self):
        """entities.media 直接是列表时也能取到图片"""
        tw = Twitter()
        legacy = {
            "entities": {"media": [{"type": "photo", "media_url_https": "p.jpg"}]}
        }
        video_url, cover_url, images = tw._collect_media(legacy)
        assert video_url == ""
        assert [img.url for img in images] == ["p.jpg"]
        assert cover_url == "p.jpg"

    def test_no_media(self):
        """无媒体时返回空结果"""
        tw = Twitter()
        video_url, cover_url, images = tw._collect_media({"text": "hello"})
        assert (video_url, cover_url, images) == ("", "", [])


class TestTwitterPayloadError:
    """测试错误响应识别"""

    def test_normal_tweet_no_error(self):
        """正常推文无错误"""
        tw = Twitter()
        assert tw._payload_error({"__typename": "Tweet", "text": "hi"}) == ""

    def test_tombstone(self):
        """tombstone（已删除/受保护）给出原因"""
        tw = Twitter()
        err = tw._payload_error({"__typename": "TweetTombstone", "tombstone": {}})
        assert "TweetTombstone" in err
        assert "Cookie 无法解决" in err

    def test_errors_array(self):
        """errors 数组给出错误消息"""
        tw = Twitter()
        err = tw._payload_error({"errors": [{"message": "Rate limit exceeded"}]})
        assert err == "推文无法访问: Rate limit exceeded"


class TestTwitterCookieHelpers:
    """测试 Cookie 相关辅助"""

    def test_csrf_from_cookie(self):
        """从 Cookie 取 ct0"""
        tw = Twitter()
        assert tw._csrf_from_cookie("auth_token=abc; ct0=def") == "def"
        assert tw._csrf_from_cookie("auth_token=abc") == ""

    def test_graphql_needs_cookie(self):
        """无 Cookie 时 GraphQL 兜底直接报错"""
        import asyncio

        tw = Twitter()
        with pytest.raises(Exception):
            asyncio.run(tw._parse_via_graphql("1234567890123456789"))


class TestTwitterVideoSource:
    """测试 VideoSource 枚举值"""

    def test_twitter_video_source_exists(self):
        """测试 Twitter VideoSource 枚举存在"""
        assert VideoSource.Twitter.value == "twitter"

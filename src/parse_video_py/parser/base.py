import dataclasses
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional

import fake_useragent

from .. import cookie_store


class VideoSource(Enum):
    """
    视频来源：douiyin，kuaishou...
    """

    DouYin = "douyin"  # 抖音 / 抖音火山版（原 火山小视频）
    KuaiShou = "kuaishou"  # 快手
    PiPiXia = "pipixia"  # 皮皮虾
    WeiBo = "weibo"  # 微博
    WeiShi = "weishi"  # 微视
    LvZhou = "lvzhou"  # 绿洲
    ZuiYou = "zuiyou"  # 最右
    QuanMin = "quanmin"  # 度小视(原 全民小视频)
    XiGua = "xigua"  # 西瓜
    LiShiPin = "lishipin"  # 梨视频
    PiPiGaoXiao = "pipigaoxiao"  # 皮皮搞笑
    HuYa = "huya"  # 虎牙
    AcFun = "acfun"  # A站
    DouPai = "doupai"  # 逗拍
    MeiPai = "meipai"  # 美拍
    QuanMinKGe = "quanminkge"  # 全民K歌
    SixRoom = "sixroom"  # 六间房
    XinPianChang = "xinpianchang"  # 新片场
    HaoKan = "haokan"  # 好看视频
    BiliBili = "bilibili"  # 哔哩哔哩
    RedBook = "redbook"  # 小红书
    Twitter = "twitter"  # Twitter/X
    QQVideo = "qqvideo"  # 腾讯视频
    Sohu = "sohu"  # 搜狐视频
    CCTV = "cctv"  # 央视网


@dataclasses.dataclass
class VideoAuthor:
    """
    视频作者信息
    """

    # 作者ID
    uid: str = ""

    # 作者昵称
    name: str = ""

    # 作者头像
    avatar: str = ""


@dataclasses.dataclass
class ImgInfo:
    """
    图集图片信息
    """

    # 图片url
    url: str = ""

    # livephoto 视频地址
    live_photo_url: str = ""


@dataclasses.dataclass
class VideoInfo:
    """
    视频信息
    """

    # 视频播放地址
    video_url: str

    # 视频封面地址
    cover_url: str

    # 视频标题
    title: str = ""

    # 音乐播放地址
    music_url: str = ""

    # 图集图片地址列表
    images: List[ImgInfo] = dataclasses.field(default_factory=list)

    # 视频作者信息
    author: VideoAuthor = dataclasses.field(default_factory=VideoAuthor)

    # 下载所需的额外请求头（防盗链、临时 Token、Referer 等），由解析器按需填充
    headers: Dict[str, str] = dataclasses.field(default_factory=dict)


class BaseParser(ABC):
    def __init__(self, source: Optional[VideoSource] = None) -> None:
        self.source = source

    @staticmethod
    def random_user_agent() -> str:
        return fake_useragent.UserAgent(os="iOS").random

    def get_cookie_header(self) -> str:
        if self.source is None:
            return ""
        return cookie_store.get_cookie(self.source.value)

    def get_default_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": self.random_user_agent()}
        cookie = self.get_cookie_header()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    @abstractmethod
    async def parse_share_url(self, share_url: str) -> VideoInfo:
        """
        解析分享链接, 获取视频信息
        :param share_url: 视频分享链接
        :return: VideoInfo
        """
        pass

    @abstractmethod
    async def parse_video_id(self, video_id: str) -> VideoInfo:
        """
        解析视频ID, 获取视频信息
        :param video_id: 视频ID
        :return:
        """
        pass

from __future__ import annotations

import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field, model_validator


class DouyinSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200, description="本次搜索使用的一个关键词")
    order: Literal["comprehensive", "most_liked", "newest"] = Field(
        default="comprehensive", description="综合、最多点赞或最新发布"
    )
    publish_time: Literal["all", "1d", "7d", "180d"] = Field(
        default="all", description="发布时间范围"
    )
    max_videos: int = Field(default=10, ge=1, le=50, description="精确返回的最大视频数")
    page_budget: int = Field(default=3, ge=1, le=10, description="最多请求多少页搜索结果")


class BilibiliSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200, description="本次搜索使用的一个关键词")
    order: Literal["totalrank", "click", "pubdate"] = Field(
        default="totalrank", description="综合、播放量或最新发布"
    )
    publish_time: Literal["all", "1d", "7d", "30d", "180d"] = Field(
        default="all", description="发布时间范围"
    )
    max_videos: int = Field(default=10, ge=1, le=50, description="精确返回的最大视频数")
    page_budget: int = Field(default=3, ge=1, le=10, description="最多请求多少页搜索结果")


class XiaohongshuSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200, description="本次搜索使用的一个关键词")
    order: Literal["comprehensive", "most_popular", "newest"] = Field(default="comprehensive")
    note_type: Literal["all", "video", "image"] = Field(default="all")
    max_notes: int = Field(default=10, ge=1, le=50, description="精确返回的最大笔记数")
    page_budget: int = Field(default=3, ge=1, le=10)


class XiaohongshuNoteRef(BaseModel):
    note_id: str = Field(min_length=8, max_length=80)
    xsec_token: str = Field(min_length=1, description="搜索结果或完整链接中的访问令牌")
    xsec_source: str = Field(default="pc_search")
    source_url: str | None = None

    @model_validator(mode="after")
    def clean_ref(self):
        self.note_id = self.note_id.strip()
        self.xsec_token = self.xsec_token.strip()
        self.xsec_source = self.xsec_source.strip() or "pc_search"
        if not re.fullmatch(r"[0-9A-Za-z_-]{8,80}", self.note_id):
            raise ValueError("小红书 note_id 格式不正确")
        return self

    @classmethod
    def from_url(cls, value: str) -> "XiaohongshuNoteRef":
        parsed = urlparse(value.strip())
        match = re.search(r"/(?:explore|discovery/item)/([0-9A-Za-z_-]+)", parsed.path)
        params = parse_qs(parsed.query)
        if not match or not params.get("xsec_token"):
            raise ValueError("固定笔记必须提供含 xsec_token 的完整小红书 explore 链接")
        return cls(
            note_id=match.group(1),
            xsec_token=params["xsec_token"][0],
            xsec_source=(params.get("xsec_source") or ["pc_search"])[0],
            source_url=value.strip(),
        )


class _CollectRequest(BaseModel):
    video_ids: list[str] = Field(
        default_factory=list,
        description="统一视频 ID 字段；抖音传 aweme ID，B站传 BV 号",
    )
    default_comments_per_video: int = Field(
        default=100, ge=0, le=1000, description="每个视频默认抓取的一级评论数"
    )
    comments_per_video: dict[str, int] = Field(
        default_factory=dict,
        description="重点视频的评论数覆盖，键必须是本次提交的视频 ID",
    )
    include_replies: Literal[False] = Field(
        default=False, description="第一版固定只抓一级评论"
    )

    @model_validator(mode="after")
    def validate_limits(self):
        self.video_ids = list(dict.fromkeys(value.strip() for value in self.video_ids if value.strip()))
        if len(self.video_ids) > 20:
            raise ValueError("一次最多提交 20 个视频 ID")
        unknown = set(self.comments_per_video) - set(self.video_ids)
        if unknown:
            raise ValueError(f"comments_per_video 包含未提交的视频 ID：{sorted(unknown)}")
        invalid = {key: value for key, value in self.comments_per_video.items() if not 0 <= value <= 1000}
        if invalid:
            raise ValueError("单视频评论数必须在 0 到 1000 之间")
        return self

    def comment_limit_for(self, video_id: str) -> int:
        return self.comments_per_video.get(video_id, self.default_comments_per_video)


class DouyinCollectRequest(_CollectRequest):
    aweme_ids: list[str] = Field(
        default_factory=list, description="抖音专用兼容字段，可与 video_ids 二选一"
    )
    comment_mode: Literal["api_only", "browser_fallback"] = Field(
        default="api_only",
        description="api_only 只使用后台签名请求；browser_fallback 才允许页面响应回退",
    )

    @model_validator(mode="before")
    @classmethod
    def merge_aweme_ids(cls, data):
        if not isinstance(data, dict):
            return data
        merged = [*data.get("video_ids", []), *data.get("aweme_ids", [])]
        data = dict(data)
        data["video_ids"] = list(dict.fromkeys(str(value).strip() for value in merged if str(value).strip()))
        return data

    @model_validator(mode="after")
    def require_aweme_ids(self):
        if not self.video_ids:
            raise ValueError("video_ids 或 aweme_ids 至少提供一个")
        invalid = [value for value in self.video_ids if not re.fullmatch(r"\d{5,30}", value)]
        if invalid:
            raise ValueError(f"抖音视频 ID 必须是数字 aweme ID：{invalid}")
        return self


class BilibiliCollectRequest(_CollectRequest):
    bvids: list[str] = Field(
        default_factory=list, description="B站专用兼容字段，可与 video_ids 二选一"
    )
    default_danmaku_per_video: int = Field(
        default=0, ge=0, le=1000, description="每个视频默认抓取的弹幕数；低层接口默认不抓"
    )
    danmaku_per_video: dict[str, int] = Field(
        default_factory=dict, description="单视频弹幕数覆盖，键必须是本次提交的 BV 号"
    )

    @model_validator(mode="before")
    @classmethod
    def merge_bvids(cls, data):
        if not isinstance(data, dict):
            return data
        merged = [*data.get("video_ids", []), *data.get("bvids", [])]
        data = dict(data)
        data["video_ids"] = list(dict.fromkeys(str(value).strip() for value in merged if str(value).strip()))
        return data

    @model_validator(mode="after")
    def require_bvids(self):
        if not self.video_ids:
            raise ValueError("video_ids 或 bvids 至少提供一个")
        invalid = [value for value in self.video_ids if not re.fullmatch(r"BV[0-9A-Za-z]+", value)]
        if invalid:
            raise ValueError(f"B站视频 ID 必须是 BV 号：{invalid}")
        unknown = set(self.danmaku_per_video) - set(self.video_ids)
        if unknown:
            raise ValueError(f"danmaku_per_video 包含未提交的视频 ID：{sorted(unknown)}")
        invalid_limits = {
            key: value for key, value in self.danmaku_per_video.items() if not 0 <= value <= 1000
        }
        if invalid_limits:
            raise ValueError("单视频弹幕数必须在 0 到 1000 之间")
        return self

    def danmaku_limit_for(self, video_id: str) -> int:
        return self.danmaku_per_video.get(video_id, self.default_danmaku_per_video)


class XiaohongshuCollectRequest(BaseModel):
    notes: list[XiaohongshuNoteRef] = Field(default_factory=list)
    note_urls: list[str] = Field(default_factory=list, description="含 xsec_token 的完整笔记链接")
    default_comments_per_note: int = Field(default=100, ge=0, le=1000)
    comments_per_note: dict[str, int] = Field(default_factory=dict)
    include_replies: Literal[False] = Field(default=False, description="固定只抓一级评论")

    @model_validator(mode="after")
    def validate_notes(self):
        merged = [*self.notes, *(XiaohongshuNoteRef.from_url(url) for url in self.note_urls)]
        unique: dict[str, XiaohongshuNoteRef] = {}
        for ref in merged:
            unique.setdefault(ref.note_id, ref)
        self.notes = list(unique.values())
        if not self.notes:
            raise ValueError("notes 或 note_urls 至少提供一项")
        if len(self.notes) > 20:
            raise ValueError("一次最多提交 20 篇小红书笔记")
        unknown = set(self.comments_per_note) - set(unique)
        if unknown:
            raise ValueError(f"comments_per_note 包含未提交的笔记 ID：{sorted(unknown)}")
        if any(not 0 <= value <= 1000 for value in self.comments_per_note.values()):
            raise ValueError("单篇笔记评论数必须在 0 到 1000 之间")
        return self

    def comment_limit_for(self, note_id: str) -> int:
        return self.comments_per_note.get(note_id, self.default_comments_per_note)


class DouyinCollectionTaskRequest(BaseModel):
    """One complete Douyin search + pinned-ID + comment collection task."""

    searches: list[DouyinSearchRequest] = Field(
        default_factory=list,
        max_length=10,
        description="按数组顺序执行的抖音搜索计划；同一任务最多 10 次搜索",
    )
    pinned_video_ids: list[str] = Field(
        default_factory=list,
        description="必须采集的抖音 aweme ID；搜索未命中也会保留",
    )
    default_comments_per_video: int = Field(
        default=100, ge=0, le=1000, description="每个最终视频默认抓取的一级评论数"
    )
    comments_per_video: dict[str, int] = Field(
        default_factory=dict,
        description="单视频评论数覆盖；键使用数字 aweme ID",
    )
    include_replies: Literal[False] = Field(default=False, description="第一版固定只抓一级评论")
    comment_mode: Literal["api_only"] = Field(
        default="api_only",
        description="Agent 正式任务固定使用后台 API，不启动页面滚动回退",
    )

    @model_validator(mode="after")
    def validate_task(self):
        self.pinned_video_ids = list(
            dict.fromkeys(value.strip() for value in self.pinned_video_ids if value.strip())
        )
        if not self.searches and not self.pinned_video_ids:
            raise ValueError("searches 与 pinned_video_ids 至少提供一项")
        if len(self.pinned_video_ids) > 20:
            raise ValueError("一次最多固定指定 20 个抖音视频")
        invalid_ids = [
            value
            for value in [*self.pinned_video_ids, *self.comments_per_video]
            if not re.fullmatch(r"\d{5,30}", value)
        ]
        if invalid_ids:
            raise ValueError(f"抖音视频 ID 必须是数字 aweme ID：{invalid_ids}")
        invalid_limits = {
            key: value for key, value in self.comments_per_video.items() if not 0 <= value <= 1000
        }
        if invalid_limits:
            raise ValueError("单视频评论数必须在 0 到 1000 之间")
        return self


class BilibiliCollectionTaskRequest(BaseModel):
    """One complete Bilibili search + pinned-ID + comment/danmaku task."""

    searches: list[BilibiliSearchRequest] = Field(
        default_factory=list,
        max_length=10,
        description="按数组顺序执行的B站搜索计划；同一任务最多 10 次搜索",
    )
    pinned_video_ids: list[str] = Field(
        default_factory=list,
        description="必须采集的 BV 号；搜索未命中也会保留",
    )
    default_comments_per_video: int = Field(
        default=100, ge=0, le=1000, description="每个最终视频默认抓取的一级评论数"
    )
    comments_per_video: dict[str, int] = Field(
        default_factory=dict,
        description="单视频评论数覆盖；键使用 BV 号",
    )
    default_danmaku_per_video: int = Field(
        default=100, ge=0, le=1000, description="每个最终视频默认抓取的弹幕数"
    )
    danmaku_per_video: dict[str, int] = Field(
        default_factory=dict,
        description="单视频弹幕数覆盖；键使用 BV 号",
    )
    include_replies: Literal[False] = Field(default=False, description="第一版固定只抓一级评论")

    @model_validator(mode="after")
    def validate_task(self):
        self.pinned_video_ids = list(
            dict.fromkeys(value.strip() for value in self.pinned_video_ids if value.strip())
        )
        if not self.searches and not self.pinned_video_ids:
            raise ValueError("searches 与 pinned_video_ids 至少提供一项")
        if len(self.pinned_video_ids) > 20:
            raise ValueError("一次最多固定指定 20 个B站视频")
        all_ids = [
            *self.pinned_video_ids,
            *self.comments_per_video,
            *self.danmaku_per_video,
        ]
        invalid_ids = [value for value in all_ids if not re.fullmatch(r"BV[0-9A-Za-z]+", value)]
        if invalid_ids:
            raise ValueError(f"B站视频 ID 必须是 BV 号：{invalid_ids}")
        invalid_comments = {
            key: value for key, value in self.comments_per_video.items() if not 0 <= value <= 1000
        }
        invalid_danmaku = {
            key: value for key, value in self.danmaku_per_video.items() if not 0 <= value <= 1000
        }
        if invalid_comments or invalid_danmaku:
            raise ValueError("单视频评论数和弹幕数必须在 0 到 1000 之间")
        return self

    def danmaku_limit_for(self, video_id: str) -> int:
        return self.danmaku_per_video.get(video_id, self.default_danmaku_per_video)


class XiaohongshuCollectionTaskRequest(BaseModel):
    searches: list[XiaohongshuSearchRequest] = Field(default_factory=list, max_length=10)
    pinned_notes: list[XiaohongshuNoteRef] = Field(default_factory=list)
    pinned_note_urls: list[str] = Field(default_factory=list)
    default_comments_per_note: int = Field(default=100, ge=0, le=1000)
    comments_per_note: dict[str, int] = Field(default_factory=dict)
    include_replies: Literal[False] = Field(default=False, description="固定只抓一级评论")

    @model_validator(mode="after")
    def validate_task(self):
        merged = [*self.pinned_notes, *(XiaohongshuNoteRef.from_url(url) for url in self.pinned_note_urls)]
        unique: dict[str, XiaohongshuNoteRef] = {}
        for ref in merged:
            unique.setdefault(ref.note_id, ref)
        self.pinned_notes = list(unique.values())
        if not self.searches and not self.pinned_notes:
            raise ValueError("searches 与 pinned_notes/pinned_note_urls 至少提供一项")
        if len(self.pinned_notes) > 20:
            raise ValueError("一次最多固定指定 20 篇小红书笔记")
        if any(not 0 <= value <= 1000 for value in self.comments_per_note.values()):
            raise ValueError("单篇笔记评论数必须在 0 到 1000 之间")
        return self


class ApiError(BaseModel):
    code: str
    message: str
    detail: str | None = None

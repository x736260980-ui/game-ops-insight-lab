from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any


TAG_RE = re.compile(r"<[^>]+>")


def as_int(value: Any) -> int | None:
    if value is None or value == "" or value == "--":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    multiplier = 1
    if text.endswith("万"):
        multiplier, text = 10_000, text[:-1]
    elif text.endswith("亿"):
        multiplier, text = 100_000_000, text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def iso_time(value: Any) -> str | None:
    timestamp = as_int(value)
    if timestamp is None or timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp //= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def clean_title(value: Any) -> str:
    return html.unescape(TAG_RE.sub("", str(value or ""))).strip()


def normalize_douyin_video(item: dict[str, Any]) -> dict[str, Any]:
    author = item.get("author") or {}
    stats = item.get("statistics") or {}
    video_id = str(item.get("aweme_id") or "")
    description = str(item.get("desc") or "")
    return {
        "platform": "douyin",
        "video_id": video_id,
        "source_url": f"https://www.douyin.com/video/{video_id}" if video_id else None,
        "title": description,
        "description": description,
        "author": str(author.get("nickname") or ""),
        "published_at": iso_time(item.get("create_time")),
        "metrics": {
            "play_count": as_int(stats.get("play_count")),
            "like_count": as_int(stats.get("digg_count")),
            "comment_count": as_int(stats.get("comment_count")),
            "share_count": as_int(stats.get("share_count")),
            "favorite_count": as_int(stats.get("collect_count")),
        },
    }


def normalize_douyin_comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "comment_id": str(item.get("cid") or ""),
        "content": str(item.get("text") or ""),
        "created_at": iso_time(item.get("create_time")),
        "like_count": as_int(item.get("digg_count")) or 0,
        "reply_count": as_int(item.get("reply_comment_total")) or 0,
    }


def normalize_bilibili_search_video(item: dict[str, Any]) -> dict[str, Any]:
    bvid = str(item.get("bvid") or "")
    return {
        "platform": "bilibili",
        "video_id": bvid,
        "bvid": bvid,
        "source_url": f"https://www.bilibili.com/video/{bvid}" if bvid else None,
        "title": clean_title(item.get("title")),
        "description": str(item.get("description") or ""),
        "author": str(item.get("author") or ""),
        "published_at": iso_time(item.get("pubdate") or item.get("senddate")),
        "metrics": {
            "play_count": as_int(item.get("play")),
            "like_count": as_int(item.get("like")),
            "comment_count": as_int(item.get("review")),
            "danmaku_count": as_int(item.get("video_review")),
            "favorite_count": as_int(item.get("favorites")),
        },
    }


def normalize_bilibili_detail(detail: dict[str, Any]) -> dict[str, Any]:
    view = detail.get("View") or detail
    owner = view.get("owner") or {}
    stats = view.get("stat") or {}
    bvid = str(view.get("bvid") or "")
    return {
        "platform": "bilibili",
        "video_id": bvid,
        "bvid": bvid,
        "aid": str(view.get("aid") or ""),
        "source_url": f"https://www.bilibili.com/video/{bvid}" if bvid else None,
        "title": str(view.get("title") or ""),
        "description": str(view.get("desc") or ""),
        "author": str(owner.get("name") or ""),
        "published_at": iso_time(view.get("pubdate")),
        "metrics": {
            "play_count": as_int(stats.get("view")),
            "like_count": as_int(stats.get("like")),
            "comment_count": as_int(stats.get("reply")),
            "share_count": as_int(stats.get("share")),
            "favorite_count": as_int(stats.get("favorite")),
            "coin_count": as_int(stats.get("coin")),
            "danmaku_count": as_int(stats.get("danmaku")),
        },
    }


def normalize_bilibili_comment(item: dict[str, Any]) -> dict[str, Any]:
    content = item.get("content") or {}
    return {
        "comment_id": str(item.get("rpid") or ""),
        "content": str(content.get("message") or ""),
        "created_at": iso_time(item.get("ctime")),
        "like_count": as_int(item.get("like")) or 0,
        "reply_count": as_int(item.get("rcount")) or 0,
    }


def normalize_bilibili_danmaku(content: str, metadata: str) -> dict[str, Any]:
    """Normalize one Bilibili XML danmaku without exposing sender identity hashes."""

    fields = metadata.split(",")

    def field(index: int, default: str = "") -> str:
        return fields[index] if index < len(fields) else default

    try:
        video_offset_seconds = float(field(0, "0"))
    except ValueError:
        video_offset_seconds = 0.0
    return {
        "danmaku_id": field(7),
        "content": str(content or "").strip(),
        "video_offset_seconds": video_offset_seconds,
        "created_at": iso_time(field(4)),
        "mode": as_int(field(1)),
        "font_size": as_int(field(2)),
        "color": as_int(field(3)),
    }


def normalize_xiaohongshu_note(
    item: dict[str, Any], *, xsec_token: str = "", xsec_source: str = "pc_search"
) -> dict[str, Any]:
    card = item.get("note_card") or item
    user = card.get("user") or {}
    interact = card.get("interact_info") or {}
    note_id = str(item.get("id") or card.get("note_id") or card.get("id") or "")
    token = str(item.get("xsec_token") or card.get("xsec_token") or xsec_token or "")
    source = str(item.get("xsec_source") or card.get("xsec_source") or xsec_source or "pc_search")
    source_url = (
        f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={token}&xsec_source={source}"
        if note_id and token
        else None
    )
    return {
        "platform": "xiaohongshu",
        "video_id": note_id,
        "note_id": note_id,
        "xsec_token": token,
        "xsec_source": source,
        "source_url": source_url,
        "title": str(card.get("display_title") or card.get("title") or ""),
        "description": str(card.get("desc") or ""),
        "author": str(user.get("nickname") or ""),
        "published_at": iso_time(card.get("time")),
        "metrics": {
            "like_count": as_int(interact.get("liked_count") or card.get("liked_count")),
            "comment_count": as_int(interact.get("comment_count") or card.get("comment_count")),
            "share_count": as_int(interact.get("share_count") or card.get("share_count")),
            "favorite_count": as_int(interact.get("collected_count") or card.get("collected_count")),
        },
    }


def normalize_xiaohongshu_comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "comment_id": str(item.get("id") or item.get("comment_id") or ""),
        "content": str(item.get("content") or ""),
        "created_at": iso_time(item.get("create_time") or item.get("time")),
        "like_count": as_int(item.get("like_count")) or 0,
        "reply_count": as_int(item.get("sub_comment_count")) or 0,
        "parent_comment_id": None,
    }

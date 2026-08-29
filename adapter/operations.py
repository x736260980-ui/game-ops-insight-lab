from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.field import SearchOrderType
from media_platform.douyin.client import DouYinClient
from media_platform.douyin.field import PublishTimeType, SearchSortType
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.field import SearchNoteType as XhsSearchNoteType
from media_platform.xhs.field import SearchSortType as XhsSearchSortType
from media_platform.xhs.help import get_search_id
from tools.httpx_util import make_async_client
from var import request_keyword_var

from .models import (
    BilibiliCollectRequest,
    BilibiliCollectionTaskRequest,
    BilibiliSearchRequest,
    DouyinCollectRequest,
    DouyinCollectionTaskRequest,
    DouyinSearchRequest,
    XiaohongshuCollectRequest,
    XiaohongshuCollectionTaskRequest,
    XiaohongshuNoteRef,
    XiaohongshuSearchRequest,
)
from .normalize import (
    normalize_bilibili_comment,
    normalize_bilibili_danmaku,
    normalize_bilibili_detail,
    normalize_bilibili_search_video,
    normalize_douyin_comment,
    normalize_douyin_video,
    normalize_xiaohongshu_comment,
    normalize_xiaohongshu_note,
)


PLATFORM_CONCURRENCY = 3
MAX_TASK_VIDEOS = 20
T = TypeVar("T")


def envelope(platform: str, operation: str, request: dict[str, Any], videos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "platform": platform,
        "operation": operation,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "data": {"videos": videos},
        "meta": {"video_count": len(videos)},
        "warnings": [],
    }


async def gather_limited(
    values: list[T],
    worker: Callable[[T], Awaitable[dict[str, Any]]],
    concurrency: int = PLATFORM_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Run independent jobs concurrently while preserving input order."""

    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(value: T) -> dict[str, Any]:
        async with semaphore:
            return await worker(value)

    return list(await asyncio.gather(*(guarded(value) for value in values)))


async def search_douyin(client: DouYinClient, request: DouyinSearchRequest) -> dict[str, Any]:
    sort_map = {
        "comprehensive": SearchSortType.GENERAL,
        "most_liked": SearchSortType.MOST_LIKE,
        "newest": SearchSortType.LATEST,
    }
    time_map = {
        "all": PublishTimeType.UNLIMITED,
        "1d": PublishTimeType.ONE_DAY,
        "7d": PublishTimeType.ONE_WEEK,
        "180d": PublishTimeType.SIX_MONTH,
    }
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    search_id = ""
    for page in range(request.page_budget):
        response = await client.search_info_by_keyword(
            keyword=request.keyword,
            offset=page * 10,
            sort_type=sort_map[request.order],
            publish_time=time_map[request.publish_time],
            search_id=search_id,
        )
        items = response.get("data") or []
        if not items:
            break
        search_id = str((response.get("extra") or {}).get("logid") or search_id)
        for post in items:
            info = post.get("aweme_info")
            if not info:
                mix_items = (post.get("aweme_mix_info") or {}).get("mix_items") or []
                info = mix_items[0] if mix_items else None
            if not info:
                continue
            video_id = str(info.get("aweme_id") or "")
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            found.append(normalize_douyin_video(info))
            if len(found) >= request.max_videos:
                return envelope("douyin", "search", request.model_dump(), found)
        await asyncio.sleep(0.5)
    return envelope("douyin", "search", request.model_dump(), found)


async def collect_douyin(
    client: DouYinClient, request: DouyinCollectRequest, browser_runtime: Any | None = None
) -> dict[str, Any]:
    request_keyword_var.set("fixed-video-collection")

    async def collect_one(video_id: str) -> dict[str, Any]:
        limit = request.comment_limit_for(video_id)
        comments: list[dict[str, Any]] = []
        detail: dict[str, Any] | None = None
        primary_error: str | None = None
        try:
            detail = await client.get_video_by_id(video_id)
            if not detail:
                primary_error = "video_not_found"
            elif limit:
                comments = await client.get_aweme_all_comments(
                    aweme_id=video_id,
                    crawl_interval=0.5,
                    is_fetch_sub_comments=False,
                    max_count=limit,
                )
        except Exception as exc:
            primary_error = str(exc)

        browser_fallback: dict[str, Any] | None = None
        if (
            request.comment_mode == "browser_fallback"
            and (primary_error or (limit and not comments))
            and browser_runtime is not None
        ):
            browser_fallback = await browser_runtime.collect_douyin_comments_from_browser(video_id, limit)
            comments = browser_fallback["comments"]

        if detail:
            item = normalize_douyin_video(detail)
        else:
            item = {
                "platform": "douyin",
                "video_id": video_id,
                "source_url": f"https://www.douyin.com/video/{video_id}",
                "title": (browser_fallback or {}).get("title") or "",
                "description": (browser_fallback or {}).get("description") or "",
                "author": "",
                "published_at": None,
                "metrics": {},
            }
        item["collection_mode"] = "browser_fallback" if browser_fallback else "api_only"
        if primary_error:
            item["error"] = {"code": "douyin_collection_failed", "message": primary_error}
        item["comments"] = {
            "requested_count": limit,
            "returned_count": len(comments[:limit]),
            "items": [normalize_douyin_comment(comment) for comment in comments[:limit]],
        }
        return item

    concurrency = 1 if request.comment_mode == "browser_fallback" else PLATFORM_CONCURRENCY
    videos = await gather_limited(request.video_ids, collect_one, concurrency=concurrency)
    result = envelope("douyin", "collect", request.model_dump(), videos)
    result["meta"]["concurrency"] = concurrency
    return result


def bili_time_range(publish_time: str) -> tuple[int, int]:
    if publish_time == "all":
        return 0, 0
    days = int(publish_time[:-1])
    end = int(time.time())
    return end - days * 86400, end


async def search_bilibili(client: BilibiliClient, request: BilibiliSearchRequest) -> dict[str, Any]:
    order_map = {
        "totalrank": SearchOrderType.DEFAULT,
        "click": SearchOrderType.MOST_CLICK,
        "pubdate": SearchOrderType.LAST_PUBLISH,
    }
    begin, end = bili_time_range(request.publish_time)
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, request.page_budget + 1):
        response = await client.search_video_by_keyword(
            keyword=request.keyword,
            page=page,
            page_size=min(20, request.max_videos),
            order=order_map[request.order],
            pubtime_begin_s=begin,
            pubtime_end_s=end,
        )
        items = response.get("result") or []
        if not items:
            break
        for item in items:
            bvid = str(item.get("bvid") or "")
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            found.append(normalize_bilibili_search_video(item))
            if len(found) >= request.max_videos:
                break
        if len(found) >= request.max_videos:
            break
        await asyncio.sleep(0.5)

    enriched: list[dict[str, Any]] = []
    for fallback in found:
        try:
            detail = await client.get_video_info(bvid=fallback["bvid"])
            enriched.append(normalize_bilibili_detail(detail))
        except Exception:
            enriched.append(fallback)
        await asyncio.sleep(0.2)
    return envelope("bilibili", "search", request.model_dump(), enriched)


async def fetch_bilibili_danmaku(
    client: BilibiliClient, cid: str, limit: int
) -> list[dict[str, Any]]:
    if not cid or limit <= 0:
        return []
    url = f"https://comment.bilibili.com/{cid}.xml"
    async with make_async_client(proxy=client.proxy, follow_redirects=True) as http_client:
        response = await http_client.get(url, headers=client.headers, timeout=client.timeout)
        response.raise_for_status()
    root = ET.fromstring(response.content)
    items: list[dict[str, Any]] = []
    for element in root.findall("d"):
        content = str(element.text or "").strip()
        if not content:
            continue
        items.append(normalize_bilibili_danmaku(content, element.attrib.get("p", "")))
        if len(items) >= limit:
            break
    return items


async def collect_bilibili(client: BilibiliClient, request: BilibiliCollectRequest) -> dict[str, Any]:
    async def collect_one(bvid: str) -> dict[str, Any]:
        comment_limit = request.comment_limit_for(bvid)
        danmaku_limit = request.danmaku_limit_for(bvid)
        try:
            detail = await client.get_video_info(bvid=bvid)
            view = detail.get("View") or {}
            aid = str(view.get("aid") or "")
            cid = str(view.get("cid") or "")
            if not aid:
                raise RuntimeError("video_not_found")
            comments: list[dict[str, Any]] = []
            if comment_limit:
                comments = await client.get_video_all_comments(
                    video_id=aid,
                    crawl_interval=0.5,
                    is_fetch_sub_comments=False,
                    max_count=comment_limit,
                )
            danmaku = await fetch_bilibili_danmaku(client, cid, danmaku_limit)
            item = normalize_bilibili_detail(detail)
            item["cid"] = cid
            item["comments"] = {
                "requested_count": comment_limit,
                "returned_count": len(comments[:comment_limit]),
                "items": [normalize_bilibili_comment(comment) for comment in comments[:comment_limit]],
            }
            item["danmaku"] = {
                "requested_count": danmaku_limit,
                "returned_count": len(danmaku),
                "items": danmaku,
            }
            return item
        except Exception as exc:
            return {
                "platform": "bilibili",
                "video_id": bvid,
                "bvid": bvid,
                "source_url": f"https://www.bilibili.com/video/{bvid}",
                "error": {"code": "bilibili_collection_failed", "message": str(exc)},
                "comments": {"requested_count": comment_limit, "returned_count": 0, "items": []},
                "danmaku": {"requested_count": danmaku_limit, "returned_count": 0, "items": []},
            }

    videos = await gather_limited(request.video_ids, collect_one)
    result = envelope("bilibili", "collect", request.model_dump(), videos)
    result["meta"]["concurrency"] = PLATFORM_CONCURRENCY
    return result


async def search_xiaohongshu(
    client: XiaoHongShuClient, request: XiaohongshuSearchRequest
) -> dict[str, Any]:
    sort_map = {
        "comprehensive": XhsSearchSortType.GENERAL,
        "most_popular": XhsSearchSortType.MOST_POPULAR,
        "newest": XhsSearchSortType.LATEST,
    }
    type_map = {
        "all": XhsSearchNoteType.ALL,
        "video": XhsSearchNoteType.VIDEO,
        "image": XhsSearchNoteType.IMAGE,
    }
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    search_id = get_search_id()
    for page in range(1, request.page_budget + 1):
        response = await client.get_note_by_keyword(
            keyword=request.keyword,
            search_id=search_id,
            page=page,
            page_size=20,
            sort=sort_map[request.order],
            note_type=type_map[request.note_type],
        )
        items = response.get("items") or []
        for raw in items:
            if raw.get("model_type") in {"rec_query", "hot_query"}:
                continue
            note = normalize_xiaohongshu_note(raw)
            note_id = str(note.get("note_id") or "")
            if not note_id or not note.get("xsec_token") or note_id in seen:
                continue
            seen.add(note_id)
            found.append(note)
            if len(found) >= request.max_notes:
                return envelope("xiaohongshu", "search", request.model_dump(), found)
        if not response.get("has_more"):
            break
        await asyncio.sleep(0.5)
    return envelope("xiaohongshu", "search", request.model_dump(), found)


async def _get_xiaohongshu_first_level_comments(
    client: XiaoHongShuClient, note_id: str, xsec_token: str, max_count: int
) -> list[dict[str, Any]]:
    """Page through the first-level endpoint directly; never request sub-comments."""
    result: list[dict[str, Any]] = []
    cursor = ""
    has_more = True
    while has_more and len(result) < max_count:
        response = await client.get_note_comments(note_id=note_id, xsec_token=xsec_token, cursor=cursor)
        comments = response.get("comments") or []
        result.extend(comments[: max_count - len(result)])
        has_more = bool(response.get("has_more"))
        cursor = str(response.get("cursor") or "")
        if has_more and len(result) < max_count:
            await asyncio.sleep(1.0)
    return result


async def collect_xiaohongshu(
    client: XiaoHongShuClient, request: XiaohongshuCollectRequest
) -> dict[str, Any]:
    async def collect_one(ref: XiaohongshuNoteRef) -> dict[str, Any]:
        limit = request.comment_limit_for(ref.note_id)
        try:
            detail = await client.get_note_by_id(ref.note_id, ref.xsec_source, ref.xsec_token)
            comments = await _get_xiaohongshu_first_level_comments(
                client, ref.note_id, ref.xsec_token, limit
            ) if limit else []
            item = normalize_xiaohongshu_note(
                detail, xsec_token=ref.xsec_token, xsec_source=ref.xsec_source
            )
            item["video_id"] = item["note_id"] = ref.note_id
            item["source_url"] = ref.source_url or item.get("source_url")
            item["comments"] = {
                "requested_count": limit,
                "returned_count": len(comments),
                "include_replies": False,
                "items": [normalize_xiaohongshu_comment(comment) for comment in comments],
            }
            return item
        except Exception as exc:
            return {
                "platform": "xiaohongshu",
                "video_id": ref.note_id,
                "note_id": ref.note_id,
                "source_url": ref.source_url,
                "comments": {"requested_count": limit, "returned_count": 0, "include_replies": False, "items": []},
                "error": {"code": "xiaohongshu_collection_failed", "message": str(exc)},
            }

    notes = await gather_limited(request.notes, collect_one)
    result = envelope("xiaohongshu", "collect", request.model_dump(), notes)
    result["meta"]["concurrency"] = PLATFORM_CONCURRENCY
    return result


async def _run_searches(
    searches: list[Any],
    search_worker: Callable[[Any], Awaitable[dict[str, Any]]],
) -> list[dict[str, Any] | Exception]:
    semaphore = asyncio.Semaphore(PLATFORM_CONCURRENCY)

    async def guarded(search: Any) -> dict[str, Any]:
        async with semaphore:
            return await search_worker(search)

    return list(await asyncio.gather(*(guarded(search) for search in searches), return_exceptions=True))


def _add_selection_reason(
    selected: dict[str, list[dict[str, Any]]], video_id: str, reason: dict[str, Any]
) -> None:
    if not video_id:
        return
    reasons = selected.setdefault(video_id, [])
    if reason not in reasons:
        reasons.append(reason)


def _task_status(videos: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if not videos or all(video.get("error") for video in videos):
        return "failed"
    if warnings or any(video.get("error") for video in videos):
        return "partial_success"
    return "success"


async def collect_douyin_task(
    client: DouYinClient,
    request: DouyinCollectionTaskRequest,
) -> dict[str, Any]:
    selected: dict[str, list[dict[str, Any]]] = {}
    warnings: list[dict[str, Any]] = []
    for video_id in request.pinned_video_ids:
        _add_selection_reason(selected, video_id, {"type": "pinned"})

    search_results = await _run_searches(request.searches, lambda search: search_douyin(client, search))
    for index, (search, result) in enumerate(zip(request.searches, search_results)):
        if isinstance(result, Exception):
            warnings.append(
                {"code": "search_failed", "search_index": index, "keyword": search.keyword, "message": str(result)}
            )
            continue
        for video in result["data"]["videos"]:
            video_id = str(video.get("video_id") or "")
            if video_id not in selected and len(selected) >= MAX_TASK_VIDEOS:
                continue
            _add_selection_reason(
                selected,
                video_id,
                {"type": "search", "search_index": index, "keyword": search.keyword, "order": search.order},
            )

    video_ids = list(selected)[:MAX_TASK_VIDEOS]
    unknown_overrides = set(request.comments_per_video) - set(video_ids)
    if unknown_overrides:
        warnings.append({"code": "unused_comment_overrides", "video_ids": sorted(unknown_overrides)})
    if video_ids:
        collect_request = DouyinCollectRequest(
            video_ids=video_ids,
            default_comments_per_video=request.default_comments_per_video,
            comments_per_video={key: value for key, value in request.comments_per_video.items() if key in selected},
            include_replies=False,
            comment_mode="api_only",
        )
        collected = await collect_douyin(client, collect_request)
        videos = collected["data"]["videos"]
    else:
        videos = []
    for video in videos:
        video["selection_reasons"] = selected.get(str(video.get("video_id") or ""), [])

    return {
        "schema_version": "1.1",
        "platform": "douyin",
        "operation": "collect_task",
        "status": _task_status(videos, warnings),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(),
        "data": {"videos": videos},
        "meta": {
            "search_count": len(request.searches),
            "pinned_count": len(request.pinned_video_ids),
            "video_count": len(videos),
            "concurrency": PLATFORM_CONCURRENCY,
        },
        "warnings": warnings,
    }


async def collect_bilibili_task(
    client: BilibiliClient,
    request: BilibiliCollectionTaskRequest,
) -> dict[str, Any]:
    selected: dict[str, list[dict[str, Any]]] = {}
    warnings: list[dict[str, Any]] = []
    for video_id in request.pinned_video_ids:
        _add_selection_reason(selected, video_id, {"type": "pinned"})

    search_results = await _run_searches(request.searches, lambda search: search_bilibili(client, search))
    for index, (search, result) in enumerate(zip(request.searches, search_results)):
        if isinstance(result, Exception):
            warnings.append(
                {"code": "search_failed", "search_index": index, "keyword": search.keyword, "message": str(result)}
            )
            continue
        for video in result["data"]["videos"]:
            video_id = str(video.get("video_id") or video.get("bvid") or "")
            if video_id not in selected and len(selected) >= MAX_TASK_VIDEOS:
                continue
            _add_selection_reason(
                selected,
                video_id,
                {"type": "search", "search_index": index, "keyword": search.keyword, "order": search.order},
            )

    video_ids = list(selected)[:MAX_TASK_VIDEOS]
    unknown_comment_overrides = set(request.comments_per_video) - set(video_ids)
    unknown_danmaku_overrides = set(request.danmaku_per_video) - set(video_ids)
    if unknown_comment_overrides:
        warnings.append({"code": "unused_comment_overrides", "video_ids": sorted(unknown_comment_overrides)})
    if unknown_danmaku_overrides:
        warnings.append({"code": "unused_danmaku_overrides", "video_ids": sorted(unknown_danmaku_overrides)})
    if video_ids:
        collect_request = BilibiliCollectRequest(
            video_ids=video_ids,
            default_comments_per_video=request.default_comments_per_video,
            comments_per_video={key: value for key, value in request.comments_per_video.items() if key in selected},
            default_danmaku_per_video=request.default_danmaku_per_video,
            danmaku_per_video={key: value for key, value in request.danmaku_per_video.items() if key in selected},
            include_replies=False,
        )
        collected = await collect_bilibili(client, collect_request)
        videos = collected["data"]["videos"]
    else:
        videos = []
    for video in videos:
        video["selection_reasons"] = selected.get(str(video.get("video_id") or ""), [])

    return {
        "schema_version": "1.1",
        "platform": "bilibili",
        "operation": "collect_task",
        "status": _task_status(videos, warnings),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(),
        "data": {"videos": videos},
        "meta": {
            "search_count": len(request.searches),
            "pinned_count": len(request.pinned_video_ids),
            "video_count": len(videos),
            "concurrency": PLATFORM_CONCURRENCY,
        },
        "warnings": warnings,
    }


async def collect_xiaohongshu_task(
    client: XiaoHongShuClient,
    request: XiaohongshuCollectionTaskRequest,
) -> dict[str, Any]:
    selected: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, Any]] = []

    def add_ref(ref: XiaohongshuNoteRef, reason: dict[str, Any]) -> None:
        if not ref.note_id:
            return
        entry = selected.setdefault(ref.note_id, {"ref": ref, "reasons": []})
        if not entry["ref"].xsec_token and ref.xsec_token:
            entry["ref"] = ref
        if reason not in entry["reasons"]:
            entry["reasons"].append(reason)

    for ref in request.pinned_notes:
        add_ref(ref, {"type": "pinned"})

    search_results = await _run_searches(
        request.searches, lambda search: search_xiaohongshu(client, search)
    )
    for index, (search, result) in enumerate(zip(request.searches, search_results)):
        if isinstance(result, Exception):
            warnings.append({
                "code": "search_failed", "search_index": index,
                "keyword": search.keyword, "message": str(result),
            })
            continue
        for note in result["data"]["videos"]:
            note_id = str(note.get("note_id") or note.get("video_id") or "")
            if note_id not in selected and len(selected) >= MAX_TASK_VIDEOS:
                continue
            add_ref(
                XiaohongshuNoteRef(
                    note_id=note_id,
                    xsec_token=str(note.get("xsec_token") or ""),
                    xsec_source=str(note.get("xsec_source") or "pc_search"),
                    source_url=note.get("source_url"),
                ),
                {"type": "search", "search_index": index, "keyword": search.keyword, "order": search.order},
            )

    selected = dict(list(selected.items())[:MAX_TASK_VIDEOS])
    unknown = set(request.comments_per_note) - set(selected)
    if unknown:
        warnings.append({"code": "unused_comment_overrides", "note_ids": sorted(unknown)})
    if selected:
        collected = await collect_xiaohongshu(
            client,
            XiaohongshuCollectRequest(
                notes=[entry["ref"] for entry in selected.values()],
                default_comments_per_note=request.default_comments_per_note,
                comments_per_note={key: value for key, value in request.comments_per_note.items() if key in selected},
                include_replies=False,
            ),
        )
        notes = collected["data"]["videos"]
    else:
        notes = []
    for note in notes:
        note["selection_reasons"] = selected.get(str(note.get("note_id") or ""), {}).get("reasons", [])

    return {
        "schema_version": "1.1",
        "platform": "xiaohongshu",
        "operation": "collect_task",
        "status": _task_status(notes, warnings),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "request": request.model_dump(),
        "data": {"videos": notes},
        "meta": {
            "search_count": len(request.searches),
            "pinned_count": len(request.pinned_notes),
            "video_count": len(notes),
            "concurrency": PLATFORM_CONCURRENCY,
        },
        "warnings": warnings,
    }

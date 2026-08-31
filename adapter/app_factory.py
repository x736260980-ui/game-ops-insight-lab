from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from .models import (
    BilibiliCollectRequest,
    BilibiliCollectionTaskRequest,
    BilibiliDynamicCollectRequest,
    BilibiliSearchRequest,
    DouyinCollectRequest,
    DouyinCollectionTaskRequest,
    DouyinSearchRequest,
    XiaohongshuCollectRequest,
    XiaohongshuCollectionTaskRequest,
    XiaohongshuSearchRequest,
)
from .operations import (
    collect_bilibili,
    collect_bilibili_dynamics,
    collect_bilibili_task,
    collect_douyin,
    collect_douyin_task,
    search_bilibili,
    search_douyin,
    collect_xiaohongshu,
    collect_xiaohongshu_task,
    search_xiaohongshu,
)
from .runtime import NativeBrowserRuntime


def create_app(platform: str, chrome_port: int) -> FastAPI:
    runtime = NativeBrowserRuntime(platform=platform, debug_port=chrome_port)  # type: ignore[arg-type]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await runtime.start()
        yield
        await runtime.stop()

    labels = {"douyin": "抖音", "bilibili": "B站", "xiaohongshu": "小红书"}
    if platform not in labels:
        raise ValueError(f"不支持的平台：{platform}")
    label = labels[platform]
    app = FastAPI(
        title=f"{label} MediaCrawler Adapter API",
        version="1.1.0",
        description=(
            f"{label}采集服务。服务启动时由 MediaCrawler 原生 CDP 管理器启动可见 Chrome；"
            "首次使用请在窗口内登录。/collect-task 一次完成搜索、固定 ID 合并去重和采集；"
            "/search 与 /collect 保留供调试。"
        ),
        lifespan=lifespan,
    )
    app.state.runtime = runtime

    @app.get("/health", summary="检查服务和浏览器状态")
    async def health(check_login: bool = Query(default=False, description="是否同时请求平台检查登录态")):
        return await runtime.status(check_login=check_login)

    if platform == "douyin":
        @app.post("/search", summary="按一个关键词搜索抖音视频，不抓评论")
        async def search(request: DouyinSearchRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await search_douyin(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "douyin_search_failed", "message": "抖音搜索失败", "detail": str(exc)}) from exc

        @app.post("/collect", summary="按固定 aweme ID 批量获取详情和一级评论")
        async def collect(request: DouyinCollectRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_douyin(client, request, browser_runtime=runtime)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "douyin_collect_failed", "message": "抖音评论采集失败", "detail": str(exc)}) from exc

        @app.post("/collect-task", summary="一次完成抖音搜索、固定 ID 合并和评论采集")
        async def collect_task(request: DouyinCollectionTaskRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_douyin_task(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "douyin_task_failed", "message": "抖音完整采集任务失败", "detail": str(exc)}) from exc
    elif platform == "bilibili":
        @app.post("/search", summary="按一个关键词搜索B站视频，不抓评论")
        async def search(request: BilibiliSearchRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await search_bilibili(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "bilibili_search_failed", "message": "B站搜索失败", "detail": str(exc)}) from exc

        @app.post("/collect", summary="按固定 BV 号批量获取详情和一级评论")
        async def collect(request: BilibiliCollectRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_bilibili(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "bilibili_collect_failed", "message": "B站评论采集失败", "detail": str(exc)}) from exc

        @app.post("/collect-dynamic", summary="按固定图文/动态链接或 ID 批量获取正文和一级评论")
        async def collect_dynamic(request: BilibiliDynamicCollectRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_bilibili_dynamics(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "bilibili_dynamic_collect_failed", "message": "B站图文评论采集失败", "detail": str(exc)}) from exc

        @app.post("/collect-task", summary="自动识别视频与图文动态，一次完成搜索和评论采集")
        async def collect_task(request: BilibiliCollectionTaskRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_bilibili_task(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "bilibili_task_failed", "message": "B站完整采集任务失败", "detail": str(exc)}) from exc

    else:
        @app.post("/search", summary="按一个关键词搜索小红书笔记，不抓评论")
        async def search(request: XiaohongshuSearchRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await search_xiaohongshu(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "xiaohongshu_search_failed", "message": "小红书搜索失败", "detail": str(exc)}) from exc

        @app.post("/collect", summary="按固定完整笔记链接批量获取详情和一级评论")
        async def collect(request: XiaohongshuCollectRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_xiaohongshu(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "xiaohongshu_collect_failed", "message": "小红书评论采集失败", "detail": str(exc)}) from exc

        @app.post("/collect-task", summary="一次完成小红书搜索、固定笔记合并和一级评论采集")
        async def collect_task(request: XiaohongshuCollectionTaskRequest):
            async with runtime.lock:
                try:
                    client = await runtime.refresh_client()
                    return await collect_xiaohongshu_task(client, request)  # type: ignore[arg-type]
                except Exception as exc:
                    raise HTTPException(status_code=502, detail={"code": "xiaohongshu_task_failed", "message": "小红书完整采集任务失败", "detail": str(exc)}) from exc

    return app

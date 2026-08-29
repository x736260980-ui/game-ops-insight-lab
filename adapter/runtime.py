from __future__ import annotations

import asyncio
import os
import socket
import sys
from pathlib import Path
from typing import Any, Literal


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import config  # noqa: E402
from media_platform.bilibili.client import BilibiliClient  # noqa: E402
from media_platform.douyin.client import DouYinClient  # noqa: E402
from media_platform.xhs.client import XiaoHongShuClient  # noqa: E402
from playwright.async_api import Page, Playwright, async_playwright  # noqa: E402
from tools import utils  # noqa: E402
from tools.cdp_browser import CDPBrowserManager  # noqa: E402


Platform = Literal["douyin", "bilibili", "xiaohongshu"]


class NativeBrowserRuntime:
    """Own one browser launched by MediaCrawler's native CDP manager."""

    def __init__(self, platform: Platform, debug_port: int):
        self.platform = platform
        self.debug_port = debug_port
        self.manager: CDPBrowserManager | None = None
        self.playwright: Playwright | None = None
        self.page: Page | None = None
        self.client: DouYinClient | BilibiliClient | XiaoHongShuClient | None = None
        self.lock = asyncio.Lock()
        self.start_error: str | None = None
        self.browser_mode: str | None = None

    @property
    def homepage(self) -> str:
        return {
            "douyin": "https://www.douyin.com/",
            "bilibili": "https://www.bilibili.com/",
            "xiaohongshu": "https://www.xiaohongshu.com/",
        }[self.platform]

    async def start(self) -> None:
        os.chdir(SOURCE_ROOT)
        attach_existing = self._port_is_open(self.debug_port)
        config.PLATFORM = {"douyin": "dy", "bilibili": "bili", "xiaohongshu": "xhs"}[self.platform]
        config.ENABLE_GET_SUB_COMMENTS = False
        config.ENABLE_CDP_MODE = True
        # Use MediaCrawler's own CDP manager in both cases. If the fixed port is
        # already a Chrome session, attach and reuse its login state. Otherwise
        # let MediaCrawler launch Chrome itself on that exact fixed port.
        config.CDP_CONNECT_EXISTING = attach_existing
        config.CDP_DEBUG_PORT = self.debug_port
        config.CDP_HEADLESS = False
        config.SAVE_LOGIN_STATE = True
        config.AUTO_CLOSE_BROWSER = True
        config.ENABLE_IP_PROXY = False

        self.playwright = await async_playwright().start()
        self.manager = CDPBrowserManager()
        try:
            context = await self.manager.launch_and_connect(
                playwright=self.playwright,
                user_agent=None,
                headless=False,
            )
            if self.manager.debug_port != self.debug_port:
                raise RuntimeError(
                    f"固定浏览器端口 {self.debug_port} 被占用，MediaCrawler 尝试改用 "
                    f"{self.manager.debug_port}；服务已拒绝端口漂移，请关闭冲突程序后重试"
                )
            self.browser_mode = "attached_existing" if attach_existing else "native_launched"
            await self.manager.add_stealth_script(str(SOURCE_ROOT / "libs" / "stealth.min.js"))
            self.page = await context.new_page()
            await self.page.goto(self.homepage, wait_until="domcontentloaded", timeout=60_000)
            await self.refresh_client()
            self.start_error = None
        except Exception as exc:
            self.start_error = str(exc)
            await self.stop()
            raise

    async def stop(self) -> None:
        if self.manager:
            await self.manager.cleanup(force=True)
        self.manager = None
        self.page = None
        self.client = None
        self.browser_mode = None
        if self.playwright:
            await self.playwright.stop()
        self.playwright = None

    async def refresh_client(self) -> DouYinClient | BilibiliClient | XiaoHongShuClient:
        if not self.manager or not self.manager.browser_context or not self.page:
            raise RuntimeError("MediaCrawler 原生浏览器尚未启动")
        cookie_urls = [self.homepage]
        if self.platform == "douyin":
            cookie_urls = [
                "https://douyin.com",
                "https://www.douyin.com",
                "https://creator.douyin.com",
                "https://douhot.douyin.com",
                "https://live.douyin.com",
            ]
        cookie_str, cookie_dict = await utils.convert_browser_context_cookies(
            self.manager.browser_context,
            urls=cookie_urls,
        )
        user_agent = await self.page.evaluate("() => navigator.userAgent")
        if self.platform == "douyin":
            self.client = DouYinClient(
                headers={
                    "User-Agent": user_agent,
                    "Cookie": cookie_str,
                    "Host": "www.douyin.com",
                    "Origin": "https://www.douyin.com/",
                    "Referer": "https://www.douyin.com/",
                    "Content-Type": "application/json;charset=UTF-8",
                },
                playwright_page=self.page,
                cookie_dict=cookie_dict,
            )
        elif self.platform == "bilibili":
            self.client = BilibiliClient(
                headers={
                    "User-Agent": user_agent,
                    "Cookie": cookie_str,
                    "Origin": "https://www.bilibili.com",
                    "Referer": "https://www.bilibili.com",
                    "Content-Type": "application/json;charset=UTF-8",
                },
                playwright_page=self.page,
                cookie_dict=cookie_dict,
            )
        else:
            self.client = XiaoHongShuClient(
                headers={
                    "accept": "application/json, text/plain, */*",
                    "accept-language": "zh-CN,zh;q=0.9",
                    "cache-control": "no-cache",
                    "content-type": "application/json;charset=UTF-8",
                    "origin": "https://www.xiaohongshu.com",
                    "pragma": "no-cache",
                    "referer": "https://www.xiaohongshu.com/",
                    "user-agent": user_agent,
                    "Cookie": cookie_str,
                },
                playwright_page=self.page,
                cookie_dict=cookie_dict,
            )
        return self.client

    async def collect_douyin_comments_from_browser(
        self, video_id: str, max_count: int
    ) -> dict[str, Any]:
        """Collect first-level comments from Douyin's own logged-in web page.

        This is deliberately a narrow fallback. The primary collection route is
        MediaCrawler's HTTP client. If Douyin rejects its current static signing
        algorithm, the visible browser can still load its own real comment pages.
        """
        if self.platform != "douyin":
            raise RuntimeError("网页评论回退仅适用于抖音")
        if not self.manager or not self.manager.browser_context:
            raise RuntimeError("MediaCrawler 原生浏览器尚未启动")
        if max_count <= 0:
            return {"comments": [], "title": None, "description": None}

        page = await self.manager.browser_context.new_page()
        comments: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        response_errors: list[str] = []

        async def capture(response):
            if "/aweme/v1/web/comment/list/" not in response.url:
                return
            try:
                payload = await response.json()
                for item in payload.get("comments") or []:
                    comment_id = str(item.get("cid") or "")
                    if not comment_id or comment_id in seen_ids:
                        continue
                    seen_ids.add(comment_id)
                    comments.append(item)
                    if len(comments) >= max_count:
                        break
            except Exception as exc:  # Browser response can be cancelled while navigating.
                response_errors.append(type(exc).__name__)

        page.on("response", capture)
        try:
            await page.goto(
                f"https://www.douyin.com/video/{video_id}",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            # First page normally arrives after the player page becomes interactive.
            await page.wait_for_timeout(2_500)
            idle_rounds = 0
            # The page first returns 5 comments and then usually 10 per scroll.
            # A hard cap prevents a malformed page from producing unlimited UI work.
            max_scrolls = min(140, max(6, (max_count + 4) // 5 + 8))
            previous_count = len(comments)
            for _ in range(max_scrolls):
                if len(comments) >= max_count:
                    break
                await page.mouse.wheel(0, 5_000)
                await page.wait_for_timeout(900)
                if len(comments) == previous_count:
                    idle_rounds += 1
                else:
                    idle_rounds = 0
                    previous_count = len(comments)
                if idle_rounds >= 3:
                    break

            description = await page.evaluate(
                "() => document.querySelector('meta[name=description]')?.content || ''"
            )
            return {
                "comments": comments[:max_count],
                "title": await page.title(),
                "description": description or None,
                "response_errors": response_errors,
            }
        finally:
            page.remove_listener("response", capture)
            await page.close()

    @staticmethod
    def _port_is_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    async def status(self, check_login: bool = False) -> dict[str, Any]:
        browser = await self.manager.get_browser_info() if self.manager else {}
        profile_platform = {"douyin": "dy", "bilibili": "bili", "xiaohongshu": "xhs"}[self.platform]
        result: dict[str, Any] = {
            "platform": self.platform,
            "service_ready": bool(self.client and browser.get("is_connected")),
            "browser": browser,
            "browser_mode": self.browser_mode,
            "fixed_debug_port": self.debug_port,
            "profile_directory": str(SOURCE_ROOT / "browser_data" / f"cdp_{profile_platform}_user_data_dir"),
            "login_checked": check_login,
            "logged_in": None,
            "start_error": self.start_error,
        }
        if check_login and self.client and self.manager and self.manager.browser_context:
            try:
                await self.refresh_client()
                if self.platform == "douyin":
                    result["logged_in"] = await self.client.pong(self.manager.browser_context)  # type: ignore[arg-type]
                else:
                    result["logged_in"] = await self.client.pong()  # type: ignore[union-attr]
            except Exception as exc:
                result["login_error"] = str(exc)
                result["logged_in"] = False
        return result

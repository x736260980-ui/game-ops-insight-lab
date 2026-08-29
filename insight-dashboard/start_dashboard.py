"""Launch the locally built Game Insight Dashboard without a Vite dev server."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Sequence


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_STATIC_DIR = PROJECT_DIR / "dist"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the small set of options needed to host the dashboard locally."""
    parser = argparse.ArgumentParser(description="启动游戏调研看板（FastAPI/Uvicorn）。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认：127.0.0.1")
    parser.add_argument("--port", default=8090, type=int, help="监听端口，默认：8090")
    parser.add_argument(
        "--no-browser",
        action="store_false",
        dest="open_browser",
        help="启动后不自动打开浏览器。",
    )
    parser.set_defaults(open_browser=True)
    return parser.parse_args(argv)


def ensure_dashboard_build(static_dir: Path = DEFAULT_STATIC_DIR) -> None:
    """Raise an actionable error unless the Vite production page is available."""
    if not (static_dir / "index.html").is_file():
        raise RuntimeError(
            "未找到前端构建产物 dist/index.html。请在 insight-dashboard 目录依次运行："
            "npm install 和 npm run build，然后重新启动看板。"
        )


def _connectable_host(host: str) -> str:
    """Map wildcard listener addresses to the loopback address a browser can reach."""
    if host == "0.0.0.0":
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host


def _browser_url(host: str, port: int) -> str:
    browser_host = _connectable_host(host)
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    return f"http://{browser_host}:{port}/"


def wait_for_server(
    host: str,
    port: int,
    *,
    timeout: float = 10.0,
    interval: float = 0.1,
    connect: Callable[..., object] = socket.create_connection,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    """Wait briefly for Uvicorn to accept TCP connections at its configured address."""
    deadline = monotonic() + timeout
    while True:
        try:
            with connect((_connectable_host(host), port), timeout=1.0):
                return True
        except OSError:
            if monotonic() >= deadline:
                return False
            sleep(interval)


def open_browser_when_ready(
    host: str,
    port: int,
    *,
    wait_for_ready: Callable[[str, int], bool] = wait_for_server,
    opener: Callable[[str], object] = webbrowser.open,
) -> bool:
    """Open the local URL only after the requested listener can accept connections."""
    if not wait_for_ready(host, port):
        return False
    opener(_browser_url(host, port))
    return True


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_args(argv)
    try:
        ensure_dashboard_build()
    except RuntimeError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1

    if options.open_browser:
        threading.Thread(
            target=open_browser_when_ready,
            args=(options.host, options.port),
            daemon=True,
        ).start()

    import uvicorn

    uvicorn.run("app:app", host=options.host, port=options.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

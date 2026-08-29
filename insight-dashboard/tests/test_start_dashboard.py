from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


def _launcher_module():
    try:
        return importlib.import_module("start_dashboard")
    except ModuleNotFoundError:
        pytest.fail("start_dashboard 模块尚未实现")


def test_parse_args_uses_local_defaults_and_opens_browser() -> None:
    options = _launcher_module().parse_args([])

    assert options.host == "127.0.0.1"
    assert options.port == 8090
    assert options.open_browser is True


def test_parse_args_accepts_host_port_and_no_browser() -> None:
    options = _launcher_module().parse_args(["--host", "0.0.0.0", "--port", "9010", "--no-browser"])

    assert options.host == "0.0.0.0"
    assert options.port == 9010
    assert options.open_browser is False


def test_ensure_dashboard_build_accepts_dist_index(tmp_path: Path) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>dashboard</main>", encoding="utf-8")

    _launcher_module().ensure_dashboard_build(static_dir)


def test_ensure_dashboard_build_explains_how_to_build_when_index_is_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"npm install.*npm run build"):
        _launcher_module().ensure_dashboard_build(tmp_path / "dist")


def test_windows_launcher_forwards_command_line_arguments() -> None:
    launcher = Path(__file__).resolve().parents[1] / "start-dashboard.cmd"

    assert "python start_dashboard.py %*" in launcher.read_text(encoding="utf-8")


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_wait_for_server_retries_until_the_configured_address_accepts_connections() -> None:
    launcher = _launcher_module()
    outcomes = iter([OSError("not ready"), _Connection()])
    attempts: list[tuple[tuple[str, int], float]] = []
    pauses: list[float] = []

    def connect(address: tuple[str, int], timeout: float):
        attempts.append((address, timeout))
        outcome = next(outcomes)
        if isinstance(outcome, OSError):
            raise outcome
        return outcome

    assert launcher.wait_for_server(
        "127.0.0.1", 9010, timeout=5, interval=0.25, connect=connect, sleep=pauses.append
    )
    assert attempts == [(("127.0.0.1", 9010), 1.0), (("127.0.0.1", 9010), 1.0)]
    assert pauses == [0.25]


def test_wait_for_server_stops_after_its_timeout() -> None:
    launcher = _launcher_module()
    now = [0.0]
    attempts = 0

    def connect(address: tuple[str, int], timeout: float):
        nonlocal attempts
        attempts += 1
        raise OSError("not ready")

    def sleep(interval: float) -> None:
        now[0] += interval

    assert not launcher.wait_for_server(
        "127.0.0.1", 9010, timeout=0.5, interval=0.25, connect=connect, sleep=sleep, monotonic=lambda: now[0]
    )
    assert attempts == 3


@pytest.mark.parametrize(
    ("listen_host", "connect_host", "browser_url"),
    [
        ("0.0.0.0", "127.0.0.1", "http://127.0.0.1:9010/"),
        ("::", "::1", "http://[::1]:9010/"),
    ],
)
def test_wait_for_server_and_browser_url_use_the_same_loopback_for_wildcard_hosts(
    listen_host: str, connect_host: str, browser_url: str
) -> None:
    launcher = _launcher_module()
    attempts: list[tuple[str, int]] = []

    def connect(address: tuple[str, int], timeout: float) -> _Connection:
        attempts.append(address)
        return _Connection()

    assert launcher.wait_for_server(listen_host, 9010, connect=connect)
    assert attempts == [(connect_host, 9010)]
    assert launcher._browser_url(listen_host, 9010) == browser_url


def test_open_browser_when_ready_uses_reachable_url_only() -> None:
    launcher = _launcher_module()
    opened: list[str] = []

    assert launcher.open_browser_when_ready(
        "0.0.0.0", 9010, wait_for_ready=lambda host, port: host == "0.0.0.0" and port == 9010, opener=opened.append
    )
    assert opened == ["http://127.0.0.1:9010/"]


def test_main_passes_host_and_port_to_uvicorn_and_starts_browser_readiness_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _launcher_module()
    calls: list[object] = []

    class FakeThread:
        def __init__(self, *, target, args, daemon) -> None:
            calls.append((target, args, daemon))

        def start(self) -> None:
            calls.append("thread-started")

    def run(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(launcher, "ensure_dashboard_build", lambda: None)
    monkeypatch.setattr(launcher.threading, "Thread", FakeThread)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=run))

    assert launcher.main(["--host", "127.0.0.1", "--port", "9010"]) == 0
    assert calls[0] == (launcher.open_browser_when_ready, ("127.0.0.1", 9010), True)
    assert calls[1] == "thread-started"
    assert calls[2] == (("app:app",), {"host": "127.0.0.1", "port": 9010, "reload": False})


def test_main_does_not_start_browser_thread_when_no_browser_is_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _launcher_module()
    started = False
    uvicorn_calls: list[object] = []

    class UnexpectedThread:
        def __init__(self, **kwargs) -> None:
            nonlocal started
            started = True
            raise AssertionError("--no-browser 不应创建浏览器线程")

    monkeypatch.setattr(launcher, "ensure_dashboard_build", lambda: None)
    monkeypatch.setattr(launcher.threading, "Thread", UnexpectedThread)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *args, **kwargs: uvicorn_calls.append((args, kwargs))))

    assert launcher.main(["--no-browser"]) == 0
    assert not started
    assert uvicorn_calls == [(("app:app",), {"host": "127.0.0.1", "port": 8090, "reload": False})]

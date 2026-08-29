from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "run_dual_agent.py"


def resolve_run_dir(value: str) -> Path:
    raw = value.strip().strip('"').strip("'")
    if not raw:
        raise ValueError("请输入 incoming 文件夹或事件目录。")
    selected = Path(raw).expanduser().resolve()
    run_dir = selected.parent if selected.name.lower() == "incoming" else selected
    if not run_dir.is_dir():
        raise ValueError(f"目录不存在：{run_dir}")
    required = run_dir / "analysis-input.json"
    if not required.is_file():
        raise ValueError(f"缺少 analysis-input.json：{required}")
    return run_dir


def build_command(run_dir: Path, topic: str, *, force: bool = False) -> list[str]:
    command = [
        sys.executable, "-X", "utf8", str(RUNNER),
        "--run-dir", str(run_dir), "--topic", topic,
    ]
    if force:
        command.append("--force")
    return command


def read_state(run_dir: Path) -> dict[str, object]:
    path = run_dir / "dual-agent" / ".runtime" / "state.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_utf8()
    print("Codex × Claude 双 Agent 游戏运营分析")
    try:
        run_dir = resolve_run_dir(input("请粘贴 incoming 文件夹或事件目录：\n> "))
        topic = input("请输入研究议题：\n> ").strip()
        if not topic:
            raise ValueError("研究议题不能为空。")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。")
        return 130
    except ValueError as exc:
        print(f"输入错误：{exc}")
        return 2

    state = read_state(run_dir)
    force = False
    existing_topic = str(state.get("topic") or "")
    stages = state.get("stages") if isinstance(state.get("stages"), dict) else {}
    complete = bool(stages) and stages.get("final_report") == "completed" and stages.get("final_summary") == "completed"
    if existing_topic and existing_topic != topic:
        answer = input("当前目录已有不同议题的分析。输入 R 归档旧结果并重新分析，其他键取消：\n> ").strip().lower()
        if answer != "r":
            print("已取消。")
            return 0
        force = True
    elif complete:
        print(f"该议题已经完成：{run_dir / 'dual-agent' / '05-final-analysis.md'}")
        answer = input("输入 R 归档旧结果并重新分析，直接回车退出：\n> ").strip().lower()
        if answer != "r":
            return 0
        force = True

    print("\n正在启动双 Agent……\n")
    return subprocess.call(build_command(run_dir, topic, force=force), cwd=str(APP_DIR))


if __name__ == "__main__":
    raise SystemExit(main())

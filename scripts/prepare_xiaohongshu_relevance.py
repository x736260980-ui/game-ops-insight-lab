#!/usr/bin/env python3
"""把小红书多笔记采集结果或原始分片转换为 relevance-input-1.0。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from scripts import prepare_relevance_common as common
except ModuleNotFoundError:
    import prepare_relevance_common as common


PLATFORM = "xiaohongshu"
PREFIX = "XHS-"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path.home() / "Desktop" / "xiaohongshu.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "collection-data" / "numbered-comments" / "xiaohongshu-relevance-input.json"
load_json = common.load_json


def extract_video(path: Path, source: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    return common.extract_video(path, source, PLATFORM)


def build_output(
    sources: list[tuple[str, list[dict[str, Any]]]], target: str | None
) -> dict[str, Any]:
    return common.build_output(sources, target, PLATFORM, PREFIX)


def main() -> None:
    common.run_cli(PLATFORM, PREFIX, DEFAULT_INPUT, DEFAULT_OUTPUT)


if __name__ == "__main__":
    main()

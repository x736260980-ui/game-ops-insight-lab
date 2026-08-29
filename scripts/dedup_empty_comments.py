"""删除空白评论，兼容 Dify Code 节点和本地文件调用。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main(input_data: dict[str, Any]) -> dict[str, Any]:
    platform = input_data["platform"]
    comments = input_data["comments"]
    if not isinstance(comments, dict):
        raise ValueError("comments 必须是编号映射对象")
    kept: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    for record_id, value in comments.items():
        if isinstance(value, str):
            text = value
        elif isinstance(value, dict):
            text = value.get("text")
        else:
            raise ValueError(f"{record_id} 的格式错误")
        if not isinstance(text, str):
            raise ValueError(f"{record_id}.text 必须是字符串")
        if not text.strip():
            excluded.append({"record_id": record_id, "reason": "empty_text"})
        else:
            kept.append({"record_id": record_id, "text": text})
    return {
        "platform": platform,
        "comments": kept,
        "hard_excluded": excluded,
        "stats": {
            "input_count": len(comments),
            "kept_count": len(kept),
            "empty_excluded_count": len(excluded),
        },
    }


def cli() -> None:
    parser = argparse.ArgumentParser(description="删除编号评论中的空白文本。")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.input.open("r", encoding="utf-8-sig") as handle:
        input_data = json.load(handle)
    result = main(input_data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    stats = result["stats"]
    print(
        f"输入 {stats['input_count']} 条 → 保留 {stats['kept_count']} 条，"
        f"剔除空白 {stats['empty_excluded_count']} 条"
    )


if __name__ == "__main__":
    cli()

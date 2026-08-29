#!/usr/bin/env python3
"""按模型判断的排除清单，从 base-cleaned 生成 relevance.json。

模型负责逐条语义判断，本脚本只做确定性组装：读取 base-cleaned，
剔除模型排除清单中的 record_id，保留其余原样输出并统计数量。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="按模型排除清单生成 relevance.json")
    parser.add_argument("--base-cleaned", required=True, help="base-cleaned.json")
    parser.add_argument("--exclusions", required=True, help="{record_id: reason} 排除清单 json")
    parser.add_argument("--output", required=True, help="relevance.json 输出路径")
    args = parser.parse_args()

    data = json.loads(Path(args.base_cleaned).read_text(encoding="utf-8"))
    exclusions = json.loads(Path(args.exclusions).read_text(encoding="utf-8"))

    comments = data.get("comments") or []
    excluded = [rid for c in comments if (rid := c.get("record_id")) in exclusions]
    kept = [c for c in comments if c.get("record_id") not in exclusions]

    stats = {
        "input_count": data.get("stats", {}).get("kept_count", len(comments)),
        "kept_count": len(comments),
        "empty_excluded_count": data.get("stats", {}).get("empty_excluded_count", 0),
        "relevance_input_count": len(comments),
        "relevance_excluded_count": len(excluded),
        "final_kept_count": len(kept),
    }
    result = {
        "platform": data.get("platform"),
        "comments": kept,
        "hard_excluded": data.get("hard_excluded", []),
        "stats": stats,
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"input={len(comments)} excluded={len(excluded)} kept={len(kept)}")


if __name__ == "__main__":
    main()

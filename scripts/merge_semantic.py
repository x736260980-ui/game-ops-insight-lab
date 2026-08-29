#!/usr/bin/env python3
"""合并旧 semantic-analysis（抖音+B站）与新小红书 results，产出完整 semantic-analysis。

旧 results 原样保留；新 results 追加；category_outputs 用传入的新版覆盖
（由模型重新写 summary 和 representative_ids）。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="旧 semantic-analysis.json")
    ap.add_argument("--xhs-results", required=True, help="新小红书 results json")
    ap.add_argument("--category-outputs", required=True, help="新版 category_outputs json")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    old = json.loads(Path(args.old).read_text(encoding="utf-8"))
    xhs = json.loads(Path(args.xhs_results).read_text(encoding="utf-8"))
    cats = json.loads(Path(args.category_outputs).read_text(encoding="utf-8"))

    merged = old["results"] + xhs
    result = {
        "schema_version": old.get("schema_version", "game-comment-semantic-analysis-1.0"),
        "research_target": old.get("research_target"),
        "results": merged,
        "category_outputs": cats,
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    inc = sum(1 for r in merged if r.get("include_in_dashboard"))
    print(f"total={len(merged)} included={inc}")


if __name__ == "__main__":
    main()

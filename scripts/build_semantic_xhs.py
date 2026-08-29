#!/usr/bin/env python3
"""为小红书折叠评论生成 semantic-analysis 结果（模型逐条判断）。

输入：analysis-input.json（含小红书评论）
输出：semantic-analysis 的 results 部分（只含 XHS- 前缀的评论）。
模型判断结果硬编码在 JUDGMENTS 里（由模型逐条语义判断产出）。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

# 类别 id 由各主题分类方案决定；这里只提供组装逻辑，判断由调用方传入。
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis-input", required=True)
    ap.add_argument("--judgments", required=True, help="record_id -> {sent, aspects} 的 json")
    ap.add_argument("--output", required=True, help="XHS results json 输出")
    args = ap.parse_args()

    data = json.loads(Path(args.analysis_input).read_text(encoding="utf-8"))
    j = json.loads(Path(args.judgments).read_text(encoding="utf-8"))

    results = []
    for c in data["comments"]:
        rid = c["record_id"]
        if not rid.startswith("XHS-"):
            continue
        if rid not in j:
            raise SystemExit(f"缺少判断：{rid}")
        spec = j[rid]
        if spec.get("include_in_dashboard") is False:
            results.append({
                "record_id": rid,
                "include_in_dashboard": False,
                "overall_sentiment": None,
                "aspects": [],
                "exclusion_reason": spec["exclusion_reason"],
            })
        else:
            results.append({
                "record_id": rid,
                "include_in_dashboard": True,
                "overall_sentiment": spec["overall_sentiment"],
                "aspects": [
                    {"category_id": cat, "sentiment": sent}
                    for cat, sent in spec["aspects"].items()
                ],
            })
    Path(args.output).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    inc = sum(1 for r in results if r["include_in_dashboard"])
    print(f"XHS results={len(results)} included={inc}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""按模型判断的折叠组，从 relevance.json 生成 folded.json。

模型决定哪些组可以安全折叠，本脚本只做确定性组装：验证成员存在、
按顺序输出、复制代表原文、计算 stats。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="按模型折叠组生成 folded.json")
    parser.add_argument("--relevance", required=True, help="relevance.json")
    parser.add_argument("--folds", required=True, help="折叠组定义 json")
    parser.add_argument("--output", required=True, help="folded.json 输出路径")
    args = parser.parse_args()

    data = json.loads(Path(args.relevance).read_text(encoding="utf-8"))
    comments = data.get("comments") or []
    by_id = {c.get("record_id"): c for c in comments}
    folds = json.loads(Path(args.folds).read_text(encoding="utf-8")).get("folds", [])

    in_group: set[str] = set()
    # 记录每组首次出现位置用于排序
    first_pos: list[tuple[int, dict]] = []
    for group in folds:
        members = group["members"]
        rep_id = group["representative"]
        assert rep_id in members, f"代表 {rep_id} 不属于成员 {members}"
        for mid in members:
            assert mid in by_id, f"成员 {mid} 不存在"
            assert mid not in in_group, f"成员 {mid} 重复出现在多个折叠组"
            in_group.add(mid)
        text = by_id[rep_id]["text"]
        idx = min(comments.index(by_id[m]) for m in members)
        first_pos.append(
            (
                idx,
                {
                    "record_id": rep_id,
                    "text": text,
                    "support_count": len(members),
                    "merged_record_ids": list(members),
                },
            )
        )

    standalone = [
        {"record_id": c["record_id"], "text": c["text"]}
        for c in comments
        if c["record_id"] not in in_group
    ]

    first_pos.sort(key=lambda x: x[0])
    ordered: list[dict] = [item for _, item in first_pos] + standalone

    folded_count = sum(len(g["members"]) - 1 for g in folds)
    result = {
        "platform": data.get("platform"),
        "comments": ordered,
        "stats": {
            "input_count": len(comments),
            "output_count": len(ordered),
            "folded_count": folded_count,
        },
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"input={len(comments)} output={len(ordered)} "
        f"groups={len(folds)} folded={folded_count}"
    )


if __name__ == "__main__":
    main()

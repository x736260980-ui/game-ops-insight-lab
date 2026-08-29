#!/usr/bin/env python3
"""折叠第一遍粗筛（脚本预筛，非最终判断）。

找出字面重复/高度雷同的候选组，供模型逐条语义判断是否可安全折叠。
脚本只负责找候选，合并与否最终由模型决定。
"""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\s　\U0001F000-\U0001FAFF☀-➿️]+", "", text)
    text = re.sub(r"[，。！？、；：,.!?;:\"'（）()【】\[\]]", "", text)
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def build_candidates(comments: list[dict], threshold: float = 0.86) -> list[dict]:
    norms = [
        (c.get("record_id", ""), c.get("text", ""), normalize(c.get("text", "")))
        for c in comments
    ]
    # 第一类：归一化后完全相同
    exact: dict[str, list[dict]] = {}
    for rid, text, norm in norms:
        if norm:
            exact.setdefault(norm, []).append({"record_id": rid, "text": text})
    groups: list[dict] = []
    for norm, members in exact.items():
        if len(members) >= 2:
            groups.append({"type": "exact", "members": members})

    used_ids = {m["record_id"] for g in groups for m in g["members"]}
    remaining = [
        (rid, text, norm) for rid, text, norm in norms if rid not in used_ids
    ]
    # 第二类：高度相似（相似度阈值内，只找长度>=8 的文本，避免短句误判）
    for i, (rid_i, text_i, norm_i) in enumerate(remaining):
        if len(norm_i) < 8:
            continue
        for rid_j, text_j, norm_j in remaining[i + 1 :]:
            if len(norm_j) < 8:
                continue
            if similarity(norm_i, norm_j) >= threshold:
                groups.append(
                    {
                        "type": "similar",
                        "similarity": round(similarity(norm_i, norm_j), 3),
                        "members": [
                            {"record_id": rid_i, "text": text_i},
                            {"record_id": rid_j, "text": text_j},
                        ],
                    }
                )
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="折叠脚本预筛（非最终判断）")
    parser.add_argument("--input", required=True, help="relevance.json")
    parser.add_argument("--output", required=True, help="候选组 json")
    parser.add_argument("--threshold", type=float, default=0.86)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    comments = data.get("comments") or []
    groups = build_candidates(comments, args.threshold)

    # 去重：similar 组如果与别的组完全包含同一对
    seen_pairs: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for g in groups:
        ids = sorted(m["record_id"] for m in g["members"])
        key = tuple(ids)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique.append(g)

    Path(args.output).write_text(
        json.dumps(
            {"note": "折叠候选（脚本预筛），是否合并由模型决定", "candidate_groups": unique},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"candidate_groups={len(unique)}")


if __name__ == "__main__":
    main()

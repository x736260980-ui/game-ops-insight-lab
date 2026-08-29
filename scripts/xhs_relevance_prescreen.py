#!/usr/bin/env python3
"""小红书相关性第一遍粗筛（脚本预筛，非最终判断）。

只负责按词表为每条评论标注候选保留/候选排除/待定，输出 record_id 清单，
供模型逐条语义复核。脚本结果不得直接作为最终结论。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# 每个主题一组词表。include 命中→候选保留；exclude 命中→候选排除。
TOPIC_LEXICON: dict[str, dict[str, list[str]]] = {
    "ubw": {
        "include": [
            "联动", "fate", "fgo", "红a", "卫宫", "凛", "士郎", "二世",
            "二期", "第二期", "2期", "二期", "绝版", "复刻", "卡池", "抽卡",
            "抽", "石头", "立绘", "强度", "技能", "特效", "大招", "archer",
            "caster", "同款", "op", "ed", "正版",
        ],
        "exclude": [
            "原神", "鸣潮", "明日方舟", "p5", "女神异闻录", "塞尔达",
        ],
    },
    "zhenzhu": {
        "include": [
            "真珠", "强度", "输出", "伤害", "主c", "c位", "辅助", "配队",
            "遗器", "光锥", "命座", "机制", "好用", "废", "刮痧", "手感",
            "拐", "buff", "提升", "就业", "t0", "t1", "毕业", "武器",
            "双爆", "面板", "倍率",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
    "silverwolf": {
        "include": [
            "银狼", "强度", "弱", "退环境", "增幅", "量子", "配队", "拐",
            "上弱点", "弱点", "伤害", "淘汰", "退坑", "gif", "数值",
            "机制", "辅助", "减抗", "增伤", "就业", "仓管", "练吗", "值得",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
    "feiying": {
        "include": [
            "绯英", "pv", "敷衍", "特效", "画面", "质量", "制作", "诚意",
            "粗糙", "立绘", "动画", "演示", "cg", "预告", "宣发", "mv",
            "唱歌", "曲", "演出", "敷衍", "敷衍了事",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
    "liandong": {
        "include": [
            "联动", "绝区零", "zzz", "崩坏", "抽卡", "角色", "期待", "复刻",
            "新角色", "剧情", "卡池", "进", "跳", "必抽", "愿望单",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
    "jingliu": {
        "include": [
            "镜流", "加强", "增强", "强度", "数值", "复刻", "抽", "遗器",
            "专武", "命座", "光锥", "提升", "buff", "配队", "伤害", "主c",
            "值", "0命", "2命", "特效", "风堇", "售后", "返场",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
    "xilian": {
        "include": [
            "昔涟", "皮肤", "氪金", "累充", "价格", "2000", "特效", "建模",
            "立绘", "免费", "送", "争议", "值", "买", "外观", "服装",
            "爱莉", "同位体", "回忆", "黑图", "胸",
        ],
        "exclude": [
            "原神", "鸣潮",
        ],
    },
}


def prescreen(comments: list[dict], include: list[str], exclude: list[str]) -> dict:
    result: dict[str, dict] = {}
    for item in comments:
        rid = item.get("record_id", "")
        text = item.get("text", "")
        low = text.lower()
        hit_inc = next((w for w in include if w.lower() in low), None)
        hit_exc = next((w for w in exclude if w.lower() in low), None)
        if hit_inc:
            label, reason = "keep", f"命中关键词:{hit_inc}"
        elif hit_exc:
            label, reason = "exclude", f"命中排除词:{hit_exc}"
        else:
            label, reason = "unknown", "无关键词命中"
        result[rid] = {"text": text, "label": label, "reason": reason}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="小红书相关性脚本预筛（非最终判断）")
    parser.add_argument("--input", required=True, help="base-cleaned.json")
    parser.add_argument("--output", required=True, help="候选标注 json")
    parser.add_argument("--topic", required=True, choices=sorted(TOPIC_LEXICON))
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    comments = data.get("comments") or []
    lex = TOPIC_LEXICON[args.topic]
    marked = prescreen(comments, lex["include"], lex["exclude"])

    counts: dict[str, int] = {}
    for v in marked.values():
        counts[v["label"]] = counts.get(v["label"], 0) + 1

    out = {
        "topic": args.topic,
        "note": "脚本预筛仅作参考，最终以模型逐条语义判断为准",
        "lexicon_include": lex["include"],
        "lexicon_exclude": lex["exclude"],
        "stats": {"total": len(marked), **counts},
        "candidates": marked,
    }
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"预筛完成: total={len(marked)} keep={counts.get('keep',0)} "
        f"exclude={counts.get('exclude',0)} unknown={counts.get('unknown',0)}"
    )


if __name__ == "__main__":
    main()

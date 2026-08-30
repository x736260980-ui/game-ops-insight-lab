"""在当前事件初判之后，构建不含当前事件的历史证据包。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH
from .repository import Repository


class ContextPackError(RuntimeError):
    """历史复核前置条件或查询参数不满足时抛出。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_context_pack(
    run_path: str | Path,
    queries: list[str],
    db_path: str | Path = DEFAULT_DB_PATH,
    sentiment: str | None = None,
    limit: int = 30,
    initial_analysis_path: str | Path | None = None,
) -> dict[str, Any]:
    """先验证盲审初判存在，再检索历史评论、动态类别和最终摘要。"""

    run_dir = Path(run_path).expanduser().resolve()
    if not run_dir.is_dir():
        raise ContextPackError(f"run directory not found: {run_dir}")
    event_id = run_dir.name
    normalized_queries = list(
        dict.fromkeys(query.strip() for query in queries if query.strip())
    )
    if not normalized_queries:
        raise ContextPackError("at least one non-empty query is required")
    if not 1 <= limit <= 200:
        raise ContextPackError("limit must be between 1 and 200")
    initial_path = (
        Path(initial_analysis_path).expanduser().resolve()
        if initial_analysis_path
        else run_dir / "analysis" / "initial-analysis.md"
    )
    if not initial_path.is_file() or not initial_path.read_text(
        encoding="utf-8"
    ).strip():
        raise ContextPackError(
            "initial analysis is required before historical retrieval: "
            f"{initial_path}"
        )

    repository = Repository(db_path)
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    hits_by_query: dict[str, int] = {}
    for query in normalized_queries:
        hits = repository.search_comments(
            query=query,
            exclude_event_id=event_id,
            sentiment=sentiment,
            limit=limit,
        )
        hits_by_query[query] = len(hits)
        for item in hits:
            key = (item["event_id"], item["record_id"])
            current = merged.setdefault(key, {**item, "matched_queries": []})
            current["matched_queries"].append(query)

    comments = list(merged.values())[:limit]
    categories = repository.get_categories_for_comments(
        (item["event_id"], item["record_id"]) for item in comments
    )
    for item in comments:
        item["dynamic_categories"] = categories.get(
            (item["event_id"], item["record_id"]), []
        )
    event_ids = list(dict.fromkeys(item["event_id"] for item in comments))
    analyses = repository.get_analyses_for_events(event_ids)
    events = {
        event_id: repository.get_event(event_id) for event_id in event_ids
    }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in comments:
        grouped[item["event_id"]].append(item)
    historical_events = []
    for historical_event_id, event_comments in grouped.items():
        historical_events.append(
            {
                "event": events.get(historical_event_id),
                "comments": event_comments,
                "analyses": analyses.get(historical_event_id, []),
            }
        )

    result = {
        "schema_version": "historical-context-pack-1.0",
        "current_event_id": event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retrieval_phase": "after_initial_analysis",
        "initial_analysis": {
            "path": str(initial_path),
            "sha256": _sha256(initial_path),
        },
        "request": {
            "queries": normalized_queries,
            "sentiment": sentiment,
            "exclude_event_id": event_id,
            "limit": limit,
        },
        "summary": {
            "query_hit_counts": hits_by_query,
            "unique_comment_count": len(comments),
            "historical_event_count": len(historical_events),
        },
        "historical_events": historical_events,
        "limitations": [
            "这是第二遍历史复核材料，不得覆盖当前事件初判中的直接证据。",
            "动态类别只在各自事件内成立，不把不同事件的 category_id 当作统一口径。",
            "FTS5/关键词命中表示文本相关，不等于事实相同或商业影响相同。",
        ],
    }

    retrieval_dir = run_dir / "retrieval"
    json_path = retrieval_dir / "historical-context.json"
    md_path = retrieval_dir / "historical-context.md"
    _write_json(json_path, result)
    lines = [
        "# 历史复核证据包",
        "",
        f"- 当前事件：`{event_id}`",
        f"- 查询：{'；'.join(normalized_queries)}",
        f"- 历史事件：{len(historical_events)}",
        f"- 唯一命中评论：{len(comments)}",
        "- 使用阶段：当前事件初判之后",
        "",
    ]
    for item in historical_events:
        event = item["event"] or {}
        lines.extend(
            [
                f"## {event.get('title') or event.get('event_id') or '未知事件'}",
                "",
            ]
        )
        for comment in item["comments"]:
            category_names = [
                category.get("category_name") or category.get("category_id")
                for category in comment["dynamic_categories"]
            ]
            lines.extend(
                [
                    f"- `{comment['record_id']}` [{comment['platform']}] {comment['text']}",
                    f"  - 情绪：{comment.get('sentiment') or '未标注'}；动态类别：{'、'.join(category_names) or '无'}；support_count={comment.get('support_count', 1)}",
                ]
            )
        lines.append("")
    lines.extend(["## 使用边界", "", *[f"- {item}" for item in result["limitations"]], ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        **result["summary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="在盲审初判之后构建 SQLite 历史复核证据包。"
    )
    parser.add_argument("run_path", type=Path)
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--sentiment")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--initial-analysis", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    try:
        summary = build_context_pack(
            args.run_path,
            args.query,
            args.db,
            sentiment=args.sentiment,
            limit=args.limit,
            initial_analysis_path=args.initial_analysis,
        )
    except ContextPackError as exc:
        parser.error(str(exc))
        return
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

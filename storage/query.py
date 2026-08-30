"""面向人工和 Agent 的单一只读查询入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH
from .repository import Repository


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="查询本地游戏运营 SQLite 数据库。")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("events", help="列出全部研究事件。")

    search_parser = subparsers.add_parser("search", help="按关键词搜索评论。")
    search_parser.add_argument("query")
    search_parser.add_argument("--event")
    search_parser.add_argument("--exclude-event")
    search_parser.add_argument("--platform")
    search_parser.add_argument("--sentiment")
    search_parser.add_argument("--category")
    search_parser.add_argument("--limit", type=int, default=50)

    comments_parser = subparsers.add_parser("comments", help="读取一个事件的评论。")
    comments_parser.add_argument("event_id")
    comments_parser.add_argument("--platform")
    comments_parser.add_argument("--sentiment")
    comments_parser.add_argument("--limit", type=int, default=50)

    category_parser = subparsers.add_parser("category", help="读取一个事件类别的评论。")
    category_parser.add_argument("event_id")
    category_parser.add_argument("category_id")
    category_parser.add_argument("--limit", type=int, default=50)

    persona_parser = subparsers.add_parser("persona", help="读取 Persona 和证据。")
    persona_parser.add_argument("persona_id")

    simulations_parser = subparsers.add_parser("simulations", help="读取 Persona 模拟记录。")
    simulations_parser.add_argument("--persona")
    simulations_parser.add_argument("--event")

    args = parser.parse_args()
    repository = Repository(args.db)

    if args.command == "events":
        _print({"events": repository.list_events()})
    elif args.command == "search":
        results = repository.search_comments(
            query=args.query,
            event_id=args.event,
            exclude_event_id=args.exclude_event,
            platform=args.platform,
            sentiment=args.sentiment,
            category_id=args.category,
            limit=args.limit,
        )
        _print({"query": args.query, "count": len(results), "results": results})
    elif args.command == "comments":
        if not 1 <= args.limit <= 500:
            parser.error("--limit must be between 1 and 500")
        results = repository.get_comments(
            args.event_id, platform=args.platform, sentiment=args.sentiment
        )[: args.limit]
        _print({"event_id": args.event_id, "count": len(results), "results": results})
    elif args.command == "category":
        if not 1 <= args.limit <= 500:
            parser.error("--limit must be between 1 and 500")
        results = repository.get_comments_by_category(
            args.event_id, args.category_id
        )[: args.limit]
        _print(
            {
                "event_id": args.event_id,
                "category_id": args.category_id,
                "count": len(results),
                "results": results,
            }
        )
    elif args.command == "persona":
        _print(
            {
                "persona": repository.get_persona(args.persona_id),
                "evidence": repository.get_persona_evidence(args.persona_id),
            }
        )
    elif args.command == "simulations":
        results = repository.get_simulations(
            persona_id=args.persona, event_id=args.event
        )
        _print({"count": len(results), "results": results})


if __name__ == "__main__":
    main()

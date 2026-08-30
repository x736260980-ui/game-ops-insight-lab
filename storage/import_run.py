"""把一个现有 runs/<run_id> 旁路导入 SQLite，不改写任何源文件。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH, PROJECT_ROOT, db_session, init_db


EXPECTED_FILES = (
    "analysis-input.json",
    "classification-plan.json",
    "semantic-analysis.json",
    "dashboard.json",
)


class ImportRunError(RuntimeError):
    """run 存在但无法被安全映射时抛出。"""


def _load_optional(run_dir: Path, name: str, warnings: list[str]) -> dict[str, Any] | None:
    path = run_dir / name
    if not path.is_file():
        warnings.append(f"optional file missing: {name}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportRunError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ImportRunError(f"{path} must contain a JSON object")
    return value


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _boolean(value: Any) -> int | None:
    return int(value) if isinstance(value, bool) else None


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImportRunError(f"{label} must be a positive integer")
    converted = int(value)
    if converted < 1 or converted != value:
        raise ImportRunError(f"{label} must be a positive integer")
    return converted


def _merge_category_definitions(
    classification: dict[str, Any],
    semantic: dict[str, Any],
    dashboard: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    collections = (
        classification.get("categories", []),
        semantic.get("category_outputs", []),
        dashboard.get("categories", []),
    )
    for collection in collections:
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict) or not isinstance(item.get("category_id"), str):
                continue
            category_id = item["category_id"]
            current = definitions.setdefault(category_id, {"category_id": category_id})
            current.update({key: value for key, value in item.items() if value is not None})

    results = semantic.get("results", [])
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("aspects"), list):
                continue
            for aspect in result["aspects"]:
                if isinstance(aspect, dict) and isinstance(aspect.get("category_id"), str):
                    category_id = aspect["category_id"]
                    definitions.setdefault(category_id, {"category_id": category_id})
    return definitions


def import_run(
    run_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """幂等导入一个研究目录中能够可靠映射的数据。"""

    run_dir = Path(run_path).expanduser().resolve()
    if not run_dir.is_dir():
        raise ImportRunError(f"run directory not found: {run_dir}")
    event_id = run_dir.name.strip()
    if not event_id:
        raise ImportRunError("run directory name cannot be used as event_id")

    warnings: list[str] = []
    documents = {name: _load_optional(run_dir, name, warnings) for name in EXPECTED_FILES}
    if not any(documents.values()):
        raise ImportRunError(f"no supported run artifacts found in {run_dir}")

    analysis_input = documents["analysis-input.json"] or {}
    classification = documents["classification-plan.json"] or {}
    semantic = documents["semantic-analysis.json"] or {}
    dashboard = documents["dashboard.json"] or {}

    comments = analysis_input.get("comments", [])
    if not isinstance(comments, list):
        raise ImportRunError("analysis-input.json comments must be an array")
    semantic_results = semantic.get("results", [])
    if not isinstance(semantic_results, list):
        raise ImportRunError("semantic-analysis.json results must be an array")

    semantic_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(semantic_results):
        if not isinstance(item, dict) or not isinstance(item.get("record_id"), str):
            raise ImportRunError(f"semantic result {index} has no valid record_id")
        record_id = item["record_id"]
        if record_id in semantic_by_id:
            raise ImportRunError(f"duplicate semantic record_id: {record_id}")
        semantic_by_id[record_id] = item

    category_definitions = _merge_category_definitions(classification, semantic, dashboard)
    research_target = (
        analysis_input.get("research_target")
        or classification.get("research_target")
        or semantic.get("research_target")
        or dashboard.get("research_target")
    )
    title = dashboard.get("title") or research_target or event_id
    present_files = [name for name, value in documents.items() if value is not None]
    required_complete = {"analysis-input.json", "semantic-analysis.json", "dashboard.json"}
    status = "complete" if required_complete.issubset(present_files) else "partial"
    metadata = {
        "present_files": present_files,
        "schema_versions": {
            name: value.get("schema_version")
            for name, value in documents.items()
            if value and value.get("schema_version")
        },
    }
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = init_db(db_path)

    imported_ids: set[str] = set()
    represented_count = 0
    included_represented_count = 0
    included_record_count = 0
    category_link_count = 0

    with db_session(db) as connection:
        connection.execute(
            """
            INSERT INTO events(
                event_id, title, research_target, imported_at,
                run_path, status, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                title = excluded.title,
                research_target = excluded.research_target,
                imported_at = excluded.imported_at,
                run_path = excluded.run_path,
                status = excluded.status,
                metadata_json = excluded.metadata_json
            """,
            (
                event_id,
                str(title),
                str(research_target) if research_target is not None else None,
                now,
                _relative_or_absolute(run_dir),
                status,
                _dump(metadata),
            ),
        )

        for index, item in enumerate(comments):
            if not isinstance(item, dict):
                raise ImportRunError(f"analysis comment {index} must be an object")
            record_id = item.get("record_id")
            platform = item.get("platform")
            text = item.get("text")
            if not isinstance(record_id, str) or not record_id:
                raise ImportRunError(f"analysis comment {index} has invalid record_id")
            if not isinstance(platform, str) or not platform:
                raise ImportRunError(f"comment {record_id} has invalid platform")
            if not isinstance(text, str):
                raise ImportRunError(f"comment {record_id} text must be a string")
            if record_id in imported_ids:
                raise ImportRunError(f"duplicate comment record_id in event: {record_id}")
            imported_ids.add(record_id)

            support_count = _positive_int(item.get("support_count", 1), f"{record_id}.support_count")
            represented_count += support_count
            semantic_item = semantic_by_id.get(record_id, {})
            included = _boolean(semantic_item.get("include_in_dashboard"))
            if included != 0:
                included_record_count += 1
                included_represented_count += support_count
            merged_ids = item.get("merged_record_ids", [record_id])
            if (
                not isinstance(merged_ids, list)
                or not merged_ids
                or not all(isinstance(value, str) for value in merged_ids)
            ):
                raise ImportRunError(f"{record_id}.merged_record_ids must be a non-empty string array")
            if support_count != len(merged_ids):
                raise ImportRunError(
                    f"{record_id}.support_count differs from merged_record_ids length"
                )

            raw = {"analysis_input": item}
            if semantic_item:
                raw["semantic_analysis"] = semantic_item
            connection.execute(
                """
                INSERT INTO comments(
                    event_id, record_id, platform, text, support_count,
                    sentiment, information_level, source_url,
                    include_in_dashboard, merged_record_ids_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, record_id) DO UPDATE SET
                    platform = excluded.platform,
                    text = excluded.text,
                    support_count = excluded.support_count,
                    sentiment = excluded.sentiment,
                    information_level = excluded.information_level,
                    source_url = excluded.source_url,
                    include_in_dashboard = excluded.include_in_dashboard,
                    merged_record_ids_json = excluded.merged_record_ids_json,
                    raw_json = excluded.raw_json
                """,
                (
                    event_id,
                    record_id,
                    platform,
                    text,
                    support_count,
                    semantic_item.get("overall_sentiment"),
                    semantic_item.get("information_level") or item.get("information_level"),
                    item.get("source_url"),
                    included,
                    _dump(merged_ids),
                    _dump(raw),
                ),
            )

        connection.execute("DELETE FROM comment_categories WHERE event_id = ?", (event_id,))
        connection.execute("DELETE FROM categories WHERE event_id = ?", (event_id,))
        for category_id, item in category_definitions.items():
            connection.execute(
                """
                INSERT INTO categories(
                    event_id, category_id, category_name,
                    definition, summary, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    category_id,
                    item.get("name"),
                    item.get("definition"),
                    item.get("summary"),
                    _dump(item),
                ),
            )

        for result in semantic_results:
            record_id = result["record_id"]
            if record_id not in imported_ids:
                warnings.append(f"semantic result has no imported comment: {record_id}")
                continue
            aspects = result.get("aspects", [])
            if not isinstance(aspects, list):
                raise ImportRunError(f"{record_id}.aspects must be an array")
            seen_categories: set[str] = set()
            for aspect in aspects:
                if not isinstance(aspect, dict) or not isinstance(aspect.get("category_id"), str):
                    raise ImportRunError(f"{record_id} has an invalid aspect")
                category_id = aspect["category_id"]
                if category_id in seen_categories:
                    raise ImportRunError(f"{record_id} repeats category {category_id}")
                seen_categories.add(category_id)
                connection.execute(
                    """
                    INSERT INTO comment_categories(
                        event_id, record_id, category_id, sentiment, raw_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        record_id,
                        category_id,
                        aspect.get("sentiment"),
                        _dump(aspect),
                    ),
                )
                category_link_count += 1

    dashboard_final_count = None
    counts = dashboard.get("counts")
    if isinstance(counts, dict):
        dashboard_final_count = counts.get("final_analyzed_count")
        if (
            isinstance(dashboard_final_count, int)
            and dashboard_final_count != included_represented_count
        ):
            warnings.append(
                "included support_count differs from dashboard final_analyzed_count: "
                f"{included_represented_count} != {dashboard_final_count}"
            )

    metadata["import_warnings"] = list(warnings)
    with db_session(db) as connection:
        connection.execute(
            "UPDATE events SET metadata_json = ? WHERE event_id = ?",
            (_dump(metadata), event_id),
        )

    return {
        "event_id": event_id,
        "status": status,
        "db_path": str(db),
        "comment_count": len(imported_ids),
        "represented_count": represented_count,
        "included_record_count": included_record_count,
        "included_represented_count": included_represented_count,
        "dashboard_final_analyzed_count": dashboard_final_count,
        "category_count": len(category_definitions),
        "comment_category_count": category_link_count,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="把 runs/<run_id> 的事件、评论、动态类别与情绪证据导入 SQLite。"
    )
    parser.add_argument("run_path", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    try:
        summary = import_run(args.run_path, args.db)
    except ImportRunError as exc:
        parser.error(str(exc))
        return
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

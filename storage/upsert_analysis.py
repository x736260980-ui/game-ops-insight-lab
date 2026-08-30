"""在最终分析完成后，单独把分析结果幂等写入 SQLite。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB_PATH, PROJECT_ROOT, db_session, init_db


class AnalysisUpsertError(RuntimeError):
    """最终分析文件不完整或无法安全映射时抛出。"""


SUMMARY_REQUIRED = {
    "schema_version",
    "research_title",
    "core_judgment",
    "risk",
    "confidence",
    "key_findings",
    "operation_directions",
    "evidence_refs",
    "evidence_gaps",
}


def _load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AnalysisUpsertError(f"required file missing: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisUpsertError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnalysisUpsertError(f"{path} must contain a JSON object")
    return value


def _relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _analysis_mode(run_dir: Path, explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    manifest_path = run_dir / "run-manifest.json"
    if manifest_path.is_file():
        manifest = _load_object(manifest_path)
        mode = manifest.get("analysis_mode")
        if mode in {"single", "dual"}:
            return str(mode)
    raise AnalysisUpsertError(
        "analysis mode is unknown; pass --mode single|dual or provide run-manifest.json"
    )


def upsert_analysis(
    run_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    mode: str | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_path).expanduser().resolve()
    if not run_dir.is_dir():
        raise AnalysisUpsertError(f"run directory not found: {run_dir}")
    event_id = run_dir.name
    final_analysis = run_dir / "final-analysis.md"
    final_summary_path = run_dir / "final-summary.json"
    if not final_analysis.is_file():
        raise AnalysisUpsertError("required file missing: final-analysis.md")
    final_summary = _load_object(final_summary_path)
    if final_summary.get("schema_version") != "game-ops-final-summary-1.0":
        raise AnalysisUpsertError("final-summary.json has unsupported schema_version")
    missing = sorted(SUMMARY_REQUIRED - set(final_summary))
    if missing:
        raise AnalysisUpsertError(
            "final-summary.json is missing required fields: " + ", ".join(missing)
        )
    analysis_mode = _analysis_mode(run_dir, mode)
    if analysis_mode not in {"single", "dual"}:
        raise AnalysisUpsertError("analysis mode must be single or dual")

    db = init_db(db_path)
    with db_session(db) as connection:
        exists = connection.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if not exists:
            raise AnalysisUpsertError(
                "event evidence has not been imported; run storage.import_run first"
            )

        def artifact(name: str) -> str | None:
            path = run_dir / name
            return _relative_or_absolute(path) if path.is_file() else None

        analysis_id = f"{event_id}:{analysis_mode}"
        connection.execute(
            """
            INSERT INTO analyses(
                analysis_id, event_id, analysis_mode, final_summary_json,
                final_analysis_path, final_summary_path, semantic_analysis_path,
                classification_plan_path, dashboard_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(analysis_id) DO UPDATE SET
                final_summary_json = excluded.final_summary_json,
                final_analysis_path = excluded.final_analysis_path,
                final_summary_path = excluded.final_summary_path,
                semantic_analysis_path = excluded.semantic_analysis_path,
                classification_plan_path = excluded.classification_plan_path,
                dashboard_path = excluded.dashboard_path,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                analysis_id,
                event_id,
                analysis_mode,
                json.dumps(final_summary, ensure_ascii=False, separators=(",", ":")),
                artifact("final-analysis.md"),
                artifact("final-summary.json"),
                artifact("semantic-analysis.json"),
                artifact("classification-plan.json"),
                artifact("dashboard.json"),
            ),
        )
    return {
        "analysis_id": analysis_id,
        "event_id": event_id,
        "analysis_mode": analysis_mode,
        "db_path": str(db),
        "status": "upserted",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="把最终分析结果单独写入 SQLite。")
    parser.add_argument("run_path", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--mode", choices=("single", "dual"))
    args = parser.parse_args()
    try:
        result = upsert_analysis(args.run_path, args.db, args.mode)
    except AnalysisUpsertError as exc:
        parser.error(str(exc))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

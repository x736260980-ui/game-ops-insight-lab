from __future__ import annotations

import argparse
import json
from pathlib import Path

from _manifest import STAGE_ORDER, now, recompute, write_manifest


def init_manifest(
    run_dir: Path,
    research_title: str,
    analysis_mode: str,
    historical_review: bool,
    persona_simulation: bool,
) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run-manifest.json"
    if path.exists():
        raise ValueError(f"manifest already exists: {path}")
    enabled = {
        "historical_review": historical_review,
        "persona_simulation": persona_simulation,
    }
    created = now()
    stages = {}
    for name in STAGE_ORDER:
        optional = name in enabled and not enabled[name]
        stages[name] = {
            "status": "skipped" if optional else "pending",
            "executor": None,
            "executor_detail": None,
            "validation": "not_run",
            "outputs": [],
            "reason": "disabled for this run" if optional else None,
            "updated_at": created,
        }
    manifest = {
        "schema_version": "game-player-research-run-1.0",
        "run_id": run_dir.name,
        "research_title": research_title.strip(),
        "analysis_mode": analysis_mode,
        "run_status": "pending",
        "current_stage": "research_brief",
        "options": enabled,
        "stages": stages,
    }
    recompute(manifest)
    write_manifest(run_dir, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化可恢复的研究运行清单。")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--analysis-mode", choices=("single", "dual"), default="single")
    parser.add_argument("--historical-review", action="store_true")
    parser.add_argument("--persona-simulation", action="store_true")
    args = parser.parse_args()
    try:
        manifest = init_manifest(
            args.run_dir.resolve(),
            args.title,
            args.analysis_mode,
            args.historical_review,
            args.persona_simulation,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

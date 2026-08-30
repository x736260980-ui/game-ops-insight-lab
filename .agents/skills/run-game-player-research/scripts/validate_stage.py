from __future__ import annotations

import argparse
import json
from pathlib import Path

from _manifest import STAGE_ORDER, read_manifest, validate_shape


REQUIRED_FILES = {
    "research_brief": ("research-brief.md",),
    "collection": (),
    "cleaning": ("analysis-input.json",),
    "classification_sentiment": (
        "classification-plan.json",
        "semantic-analysis.json",
    ),
    "dashboard_freeze": ("dashboard.json",),
    "sqlite_evidence_import": (
        "analysis-input.json",
        "classification-plan.json",
        "semantic-analysis.json",
        "dashboard.json",
    ),
    "current_event_analysis": ("analysis/initial-analysis.md",),
    "historical_review": (
        "retrieval/historical-context.json",
        "retrieval/historical-context.md",
        "analysis/historical-review.md",
    ),
    "final_analysis": ("final-analysis.md", "final-summary.json"),
    "sqlite_analysis_upsert": ("final-analysis.md", "final-summary.json"),
    "dashboard_result_injection": ("dashboard.json", "final-summary.json"),
    "persona_simulation": (),
}

INPUT_FILES = {
    "research_brief": (),
    "collection": ("research-brief.md",),
    "cleaning": (),
    "classification_sentiment": ("analysis-input.json",),
    "dashboard_freeze": (
        "analysis-input.json",
        "classification-plan.json",
        "semantic-analysis.json",
    ),
    "sqlite_evidence_import": REQUIRED_FILES["sqlite_evidence_import"],
    "current_event_analysis": (
        "analysis-input.json",
        "semantic-analysis.json",
        "dashboard.json",
    ),
    "historical_review": ("analysis/initial-analysis.md",),
    "final_analysis": ("analysis/initial-analysis.md",),
    "sqlite_analysis_upsert": REQUIRED_FILES["sqlite_analysis_upsert"],
    "dashboard_result_injection": REQUIRED_FILES["dashboard_result_injection"],
    "persona_simulation": ("final-summary.json",),
}


def _is_nonempty(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if path.suffix.lower() == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return isinstance(value, (dict, list))
    return bool(path.read_text(encoding="utf-8").strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="校验研究阶段的文件和前置状态。")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("stage", nargs="?", choices=STAGE_ORDER)
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--phase", choices=("before", "after"), default="before")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    try:
        manifest = read_manifest(run_dir)
        errors = validate_shape(manifest)
        if errors:
            raise ValueError("; ".join(errors))
        stage_name = manifest.get("current_stage") if args.next else args.stage
        if not stage_name:
            raise ValueError("no stage selected or core run is already complete")
        stage_index = STAGE_ORDER.index(stage_name)
        predecessor_errors = []
        for prior in STAGE_ORDER[:stage_index]:
            if prior in {"historical_review", "persona_simulation"}:
                continue
            if manifest["stages"][prior]["status"] not in {"completed", "skipped"}:
                predecessor_errors.append(prior)
        if stage_name == "historical_review" and manifest["stages"]["current_event_analysis"]["status"] != "completed":
            predecessor_errors.append("current_event_analysis")
        expected = INPUT_FILES[stage_name] if args.phase == "before" else REQUIRED_FILES[stage_name]
        missing = [
            relative
            for relative in expected
            if not _is_nonempty(run_dir / relative)
        ]
        if stage_name == "cleaning" and args.phase == "before":
            incoming = run_dir / "incoming"
            if not incoming.is_dir() or not any(path.is_file() for path in incoming.iterdir()):
                missing.append("incoming/<at least one file>")
        if stage_name == "collection" and args.phase == "after":
            incoming = run_dir / "incoming"
            if not incoming.is_dir() or not any(path.is_file() for path in incoming.iterdir()):
                missing.append("incoming/<at least one file>")
        if (
            stage_name == "final_analysis"
            and args.phase == "before"
            and manifest.get("options", {}).get("historical_review")
            and not _is_nonempty(run_dir / "analysis" / "historical-review.md")
        ):
            missing.append("analysis/historical-review.md")
        result = {
            "stage": stage_name,
            "phase": args.phase,
            "ready": not predecessor_errors and not missing,
            "analysis_mode": manifest["analysis_mode"],
            "predecessors_not_completed": list(dict.fromkeys(predecessor_errors)),
            "missing_or_invalid_outputs": missing,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_ORDER = (
    "research_brief",
    "collection",
    "cleaning",
    "classification_sentiment",
    "dashboard_freeze",
    "sqlite_evidence_import",
    "current_event_analysis",
    "historical_review",
    "final_analysis",
    "sqlite_analysis_upsert",
    "dashboard_result_injection",
    "persona_simulation",
)
CORE_FINAL_STAGE = "dashboard_result_injection"
STATUSES = {"pending", "waiting", "completed", "needs_review", "skipped", "failed"}
EXECUTORS = {"codex", "local_codex", "cloud", "dify", "external", "automation", "manual"}
VALIDATIONS = {"not_run", "passed", "failed", "needs_review"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run-manifest.json"
    if not path.is_file():
        raise ValueError(f"manifest not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("run-manifest.json must contain an object")
    return value


def write_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    path = run_dir / "run-manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def file_descriptor(run_dir: Path, relative: str) -> dict[str, Any]:
    candidate = (run_dir / relative).resolve()
    try:
        normalized = candidate.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"output must stay inside run directory: {relative}") from exc
    if not candidate.is_file():
        raise ValueError(f"output file does not exist: {relative}")
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": normalized.as_posix(),
        "size": candidate.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def recompute(manifest: dict[str, Any]) -> None:
    stages = manifest["stages"]
    core_status = stages[CORE_FINAL_STAGE]["status"]
    if core_status == "completed":
        manifest["run_status"] = "completed"
        manifest["current_stage"] = None
        return
    statuses = [stages[name]["status"] for name in STAGE_ORDER]
    if "failed" in statuses:
        manifest["run_status"] = "failed"
    elif "needs_review" in statuses:
        manifest["run_status"] = "needs_review"
    elif "waiting" in statuses:
        manifest["run_status"] = "waiting"
    elif any(status == "completed" for status in statuses):
        manifest["run_status"] = "in_progress"
    else:
        manifest["run_status"] = "pending"
    manifest["current_stage"] = next(
        (
            name
            for name in STAGE_ORDER
            if stages[name]["status"] not in {"completed", "skipped"}
        ),
        None,
    )


def validate_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "game-player-research-run-1.0":
        errors.append("unsupported schema_version")
    if manifest.get("analysis_mode") not in {"single", "dual"}:
        errors.append("analysis_mode must be single or dual")
    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        return [*errors, "stages must be an object"]
    if list(stages) != list(STAGE_ORDER):
        errors.append("stages must use the exact V1 order")
    for name in STAGE_ORDER:
        stage = stages.get(name)
        if not isinstance(stage, dict):
            errors.append(f"missing stage: {name}")
            continue
        if stage.get("status") not in STATUSES:
            errors.append(f"{name}.status is invalid")
        if stage.get("executor") is not None and stage.get("executor") not in EXECUTORS:
            errors.append(f"{name}.executor is invalid")
        if stage.get("validation") not in VALIDATIONS:
            errors.append(f"{name}.validation is invalid")
    return errors

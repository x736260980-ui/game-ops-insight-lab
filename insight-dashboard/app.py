"""Local API for browsing MediaCrawler game-insight run artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles


DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "dist"
SENTIMENT_KEYS = {"positive", "negative", "neutral", "mixed"}


def _mtime_as_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")


def _sort_timestamp(value: str, fallback_path: Path) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return fallback_path.stat().st_mtime
        except OSError:
            return 0


def _safe_run_name(run_id: str) -> str:
    if (
        not run_id
        or run_id in {".", ".."}
        or ":" in run_id
        or "/" in run_id
        or "\\" in run_id
        or Path(run_id).is_absolute()
    ):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    return run_id


def _load_dashboard(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"invalid JSON in dashboard.json: {exc.msg}") from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="dashboard.json is not valid UTF-8") from exc
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"dashboard.json cannot be read: {exc.strerror or exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="dashboard.json must contain a JSON object")
    return payload


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"{path.name} cannot be read as UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail=f"{path.name} must contain a JSON object")
    return value


def _summary_for_run(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "dual-agent" / "05-final-summary.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, JSONDecodeError):
        return None
    required = {
        "schema_version", "research_title", "core_judgment", "risk", "confidence",
        "key_findings", "operation_directions", "evidence_refs", "evidence_gaps",
    }
    if not isinstance(value, dict) or set(value) != required:
        return None
    if value.get("schema_version") != "game-ops-final-summary-1.0":
        return None
    return value


def _classification_path(run_dir: Path) -> Path | None:
    semantic = run_dir / "semantic-analysis.json"
    fallback = run_dir / "incoming" / "dify-classification.json"
    if semantic.is_file():
        return semantic
    if fallback.is_file():
        return fallback
    return None


def _comment_drilldown_available(run_dir: Path) -> bool:
    return (run_dir / "analysis-input.json").is_file() and _classification_path(run_dir) is not None


def _category_comments(run_dir: Path, category_id: str, sentiment: str) -> dict[str, Any]:
    analysis_path = run_dir / "analysis-input.json"
    classification_path = _classification_path(run_dir)
    if not analysis_path.is_file() or classification_path is None:
        raise HTTPException(status_code=404, detail="Comment drill-down sources are unavailable")
    analysis = _load_json_object(analysis_path)
    classification = _load_json_object(classification_path)
    comments = analysis.get("comments")
    results = classification.get("results")
    if not isinstance(comments, list) or not isinstance(results, list):
        raise HTTPException(status_code=422, detail="Comment drill-down source schema is invalid")
    selected_ids: set[str] = set()
    for result in results:
        if not isinstance(result, dict) or result.get("include_in_dashboard") is False:
            continue
        record_id = result.get("record_id")
        aspects = result.get("aspects")
        if not isinstance(record_id, str) or not isinstance(aspects, list):
            continue
        if any(
            isinstance(aspect, dict)
            and aspect.get("category_id") == category_id
            and aspect.get("sentiment") == sentiment
            for aspect in aspects
        ):
            selected_ids.add(record_id)
    records: list[dict[str, Any]] = []
    for comment in comments:
        if not isinstance(comment, dict) or comment.get("record_id") not in selected_ids:
            continue
        support = comment.get("support_count", 1)
        support_count = int(support) if isinstance(support, (int, float)) and not isinstance(support, bool) else 1
        records.append({
            "record_id": str(comment.get("record_id")),
            "platform": str(comment.get("platform") or "unknown"),
            "text": str(comment.get("text") or ""),
            "support_count": max(1, support_count),
        })
    return {
        "category_id": category_id,
        "sentiment": sentiment,
        "weighted_expression_count": sum(item["support_count"] for item in records),
        "representative_record_count": len(records),
        "records": records,
    }


def _is_within_runs(runs_dir: Path, candidate: Path) -> bool:
    """Return whether a resolved artifact path stays below the resolved runs root."""
    try:
        candidate.resolve().relative_to(runs_dir.resolve())
    except (OSError, ValueError):
        return False
    return True


def _dashboard_path_for_id(runs_dir: Path, run_id: str) -> Path:
    run_id = _safe_run_name(run_id)
    direct_path = runs_dir / run_id / "dashboard.json"
    if not _is_within_runs(runs_dir, direct_path):
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        if direct_path.is_file():
            return direct_path
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"dashboard.json cannot be accessed: {exc.strerror or exc}") from exc
    raise HTTPException(status_code=404, detail="Run not found")


def _error_summary(directory: Path, error: str) -> dict[str, Any]:
    return {
        "run_id": directory.name,
        "research_target": None,
        "generated_at": "",
        "platforms": [],
        "final_analyzed_count": 0,
        "category_count": 0,
        "status": "error",
        "error": error,
        "_sort_timestamp": 0,
    }


def _summary(directory: Path) -> dict[str, Any]:
    dashboard_path = directory / "dashboard.json"
    try:
        fallback_generated_at = _mtime_as_timestamp(dashboard_path)
        data = _load_dashboard(dashboard_path)
    except HTTPException as exc:
        return _error_summary(directory, str(exc.detail))
    except OSError as exc:
        return _error_summary(directory, f"dashboard.json cannot be accessed: {exc.strerror or exc}")

    generated_at = data.get("generated_at") or fallback_generated_at
    categories = data.get("categories")
    counts = data.get("counts")
    final_analyzed_count = counts.get("final_analyzed_count") if isinstance(counts, dict) else None
    if final_analyzed_count is None:
        final_analyzed_count = data.get("final_analyzed_count", 0)
    source_run_id = data.get("run_id")
    summary = _summary_for_run(directory)
    return {
        "run_id": directory.name,
        **({"source_run_id": source_run_id} if source_run_id and source_run_id != directory.name else {}),
        "research_target": data.get("research_target"),
        "generated_at": generated_at,
        "platforms": data.get("platforms", []),
        "final_analyzed_count": final_analyzed_count,
        "category_count": len(categories) if isinstance(categories, list) else 0,
        "status": "ready",
        **({"research_title": summary["research_title"]} if summary else {}),
        "_sort_timestamp": _sort_timestamp(str(generated_at), dashboard_path),
    }


def create_app(
    runs_dir: Path | str | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Build the API, allowing tests and local hosts to select artifact folders."""
    configured_runs_dir = Path(runs_dir) if runs_dir is not None else DEFAULT_RUNS_DIR
    configured_static_dir = Path(static_dir) if static_dir is not None else DEFAULT_STATIC_DIR
    app = FastAPI(title="Game Insight Dashboard API")

    @app.get("/api/dashboard/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dashboard/runs")
    def list_runs() -> dict[str, list[dict[str, Any]]]:
        try:
            directories = list(configured_runs_dir.iterdir()) if configured_runs_dir.is_dir() else []
        except OSError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Runs directory cannot be scanned: {exc.strerror or exc}",
            ) from exc
        items = []
        for directory in directories:
            dashboard_path = directory / "dashboard.json"
            try:
                if not directory.is_dir() or not _is_within_runs(configured_runs_dir, dashboard_path):
                    continue
                if not dashboard_path.is_file():
                    continue
            except OSError as exc:
                items.append(_error_summary(directory, f"dashboard.json cannot be accessed: {exc.strerror or exc}"))
                continue
            items.append(_summary(directory))
        items.sort(key=lambda item: item.pop("_sort_timestamp"), reverse=True)
        return {"runs": items}

    @app.get("/api/dashboard/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        dashboard_path = _dashboard_path_for_id(configured_runs_dir, run_id)
        data = _load_dashboard(dashboard_path)
        source_run_id = data.get("run_id")
        data["run_id"] = dashboard_path.parent.name
        summary = _summary_for_run(dashboard_path.parent)
        if summary:
            data["analysis_summary"] = summary
        data["comment_drilldown_available"] = _comment_drilldown_available(dashboard_path.parent)
        if source_run_id and source_run_id != data["run_id"]:
            data["source_run_id"] = source_run_id
        if not data.get("generated_at"):
            try:
                data["generated_at"] = _mtime_as_timestamp(dashboard_path)
            except OSError as exc:
                raise HTTPException(status_code=422, detail=f"dashboard.json cannot be accessed: {exc.strerror or exc}") from exc
        return data

    @app.get("/api/dashboard/runs/{run_id}/categories/{category_id}/comments")
    def get_category_comments(run_id: str, category_id: str, sentiment: str) -> dict[str, Any]:
        if sentiment not in SENTIMENT_KEYS:
            raise HTTPException(status_code=400, detail="Invalid sentiment")
        dashboard_path = _dashboard_path_for_id(configured_runs_dir, run_id)
        payload = _category_comments(dashboard_path.parent, category_id, sentiment)
        return {"run_id": run_id, **payload}

    @app.get("/api/dashboard/runs/{run_id}/report")
    def get_report(run_id: str) -> dict[str, str]:
        run_dir = _dashboard_path_for_id(configured_runs_dir, run_id).parent
        authoritative = run_dir / "dual-agent" / "05-final-analysis.md"
        report_path = authoritative if authoritative.is_file() else run_dir / "report.md"
        if not _is_within_runs(configured_runs_dir, report_path):
            raise HTTPException(status_code=404, detail="Report not found")
        try:
            if not report_path.is_file():
                raise HTTPException(status_code=404, detail="Report not found")
            content = report_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="report.md is not valid UTF-8") from exc
        except OSError as exc:
            raise HTTPException(status_code=422, detail=f"report.md cannot be read: {exc.strerror or exc}") from exc
        return {"run_id": run_id, "content": content}

    if configured_static_dir.is_dir():
        app.mount("/", StaticFiles(directory=configured_static_dir, html=True), name="static")
    else:
        @app.get("/")
        def service_info() -> dict[str, str]:
            return {
                "service": "Game Insight Dashboard API",
                "message": "Static dashboard build is not available yet.",
            }

    return app


app = create_app()

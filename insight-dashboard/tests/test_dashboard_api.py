import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as dashboard_app

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app import _is_within_runs, create_app


def write_dashboard(runs_dir: Path, run_id: str, payload: object, *, mtime: float | None = None) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    dashboard_path = run_dir / "dashboard.json"
    if isinstance(payload, str):
        dashboard_path.write_text(payload, encoding="utf-8")
    else:
        dashboard_path.write_text(json.dumps(payload), encoding="utf-8")
    if mtime is not None:
        os.utime(dashboard_path, (mtime, mtime))
    return run_dir


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs"


def client_for(runs_dir: Path) -> TestClient:
    return TestClient(create_app(runs_dir=runs_dir))


def test_health_and_empty_runs_directory(runs_dir: Path) -> None:
    client = client_for(runs_dir)

    health = client.get("/api/dashboard/health")
    listing = client.get("/api/dashboard/runs")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert listing.status_code == 200
    assert listing.json() == {"runs": []}


def test_runs_returns_normal_and_legacy_summary_with_fallback_metadata(runs_dir: Path) -> None:
    write_dashboard(
        runs_dir,
        "new-run",
        {
            "run_id": "stored-id",
            "generated_at": "2026-08-23T12:00:00Z",
            "research_target": "新分析",
            "platforms": [{"platform": "bilibili"}],
            "counts": {"final_analyzed_count": 12},
            "categories": [{"name": "角色强度"}],
        },
    )
    legacy_dir = write_dashboard(
        runs_dir,
        "legacy-run",
        {
            "research_target": "旧分析",
            "platforms": ["douyin"],
            "final_analyzed_count": 4,
            "categories": [],
        },
        mtime=1_700_000_000,
    )

    response = client_for(runs_dir).get("/api/dashboard/runs")

    assert response.status_code == 200
    items = response.json()["runs"]
    assert [item["run_id"] for item in items] == ["new-run", "legacy-run"]
    assert items[0] == {
        "run_id": "new-run",
        "source_run_id": "stored-id",
        "research_target": "新分析",
        "generated_at": "2026-08-23T12:00:00Z",
        "platforms": [{"platform": "bilibili"}],
        "final_analyzed_count": 12,
        "category_count": 1,
        "status": "ready",
    }
    assert items[1]["generated_at"]
    assert items[1]["final_analyzed_count"] == 4
    assert legacy_dir.name == items[1]["run_id"]


def test_routes_use_unique_directory_names_not_duplicated_or_unsafe_embedded_ids(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "first-safe", {"run_id": "batch:2026", "research_target": "第一份"})
    write_dashboard(runs_dir, "second-safe", {"run_id": "batch:2026", "research_target": "第二份"})
    client = client_for(runs_dir)

    listing = client.get("/api/dashboard/runs")

    assert listing.status_code == 200
    items = {item["run_id"]: item for item in listing.json()["runs"]}
    assert set(items) == {"first-safe", "second-safe"}
    assert {item["source_run_id"] for item in items.values()} == {"batch:2026"}
    detail = client.get("/api/dashboard/runs/first-safe")
    assert detail.status_code == 200
    assert detail.json()["run_id"] == "first-safe"
    assert detail.json()["source_run_id"] == "batch:2026"


def test_summary_uses_top_level_final_count_when_counts_is_empty_missing_or_null_but_preserves_zero(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "empty-counts", {"counts": {}, "final_analyzed_count": 7})
    write_dashboard(runs_dir, "missing-count", {"counts": {"input_relevance_count": 10}, "final_analyzed_count": 9})
    write_dashboard(runs_dir, "null-count", {"counts": {"final_analyzed_count": None}, "final_analyzed_count": 11})
    write_dashboard(runs_dir, "zero-count", {"counts": {"final_analyzed_count": 0}, "final_analyzed_count": 13})

    response = client_for(runs_dir).get("/api/dashboard/runs")

    assert response.status_code == 200
    counts = {item["run_id"]: item["final_analyzed_count"] for item in response.json()["runs"]}
    assert counts == {"empty-counts": 7, "missing-count": 9, "null-count": 11, "zero-count": 0}


def test_runs_root_scan_oserror_returns_service_error(runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir.mkdir()
    original_iterdir = Path.iterdir

    def fail_runs_scan(self: Path):
        if self == runs_dir:
            raise PermissionError("denied scan")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", fail_runs_scan)

    response = client_for(runs_dir).get("/api/dashboard/runs")

    assert response.status_code == 503
    assert "cannot be scanned" in response.json()["detail"]


def test_list_isolates_stat_and_read_oserrors_and_detail_is_a_clear_4xx(
    runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_dashboard(runs_dir, "stat-fails", {"research_target": "不可访问"})
    write_dashboard(runs_dir, "read-fails", {"research_target": "不可读取"})
    original_stat = Path.stat
    original_read_text = Path.read_text

    def fail_stat(self: Path, *args: object, **kwargs: object):
        if self.name == "dashboard.json" and self.parent.name == "stat-fails":
            raise PermissionError("denied stat")
        return original_stat(self, *args, **kwargs)

    def fail_read_text(self: Path, *args: object, **kwargs: object):
        if self.name == "dashboard.json" and self.parent.name == "read-fails":
            raise PermissionError("denied read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fail_stat)
    monkeypatch.setattr(Path, "read_text", fail_read_text)
    client = client_for(runs_dir)

    listing = client.get("/api/dashboard/runs")
    detail = client.get("/api/dashboard/runs/read-fails")

    assert listing.status_code == 200
    entries = {item["run_id"]: item for item in listing.json()["runs"]}
    assert entries["stat-fails"]["status"] == "error"
    assert entries["read-fails"]["status"] == "error"
    assert detail.status_code == 422
    assert "cannot be read" in detail.json()["detail"]


def test_runs_are_sorted_by_generated_at_descending(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "old", {"generated_at": "2026-01-01T00:00:00Z"})
    write_dashboard(runs_dir, "new", {"generated_at": "2026-02-01T00:00:00Z"})

    response = client_for(runs_dir).get("/api/dashboard/runs")

    assert response.status_code == 200
    assert [item["run_id"] for item in response.json()["runs"]] == ["new", "old"]


def test_bad_dashboard_is_isolated_in_run_list(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "broken", "{ not JSON")
    write_dashboard(runs_dir, "valid", {"research_target": "仍可读取"})

    response = client_for(runs_dir).get("/api/dashboard/runs")

    assert response.status_code == 200
    entries = {item["run_id"]: item for item in response.json()["runs"]}
    assert entries["valid"]["status"] == "ready"
    assert entries["broken"]["status"] == "error"
    assert "invalid JSON" in entries["broken"]["error"]


def test_run_detail_returns_full_dashboard_and_backfills_metadata(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "legacy", {"research_target": "完整旧文件", "categories": []})

    response = client_for(runs_dir).get("/api/dashboard/runs/legacy")

    assert response.status_code == 200
    assert response.json()["research_target"] == "完整旧文件"
    assert response.json()["run_id"] == "legacy"
    assert response.json()["generated_at"]


def test_detail_merges_authoritative_summary_and_list_uses_short_title(runs_dir: Path) -> None:
    run_dir = write_dashboard(runs_dir, "with-summary", {"research_target": "完整而很长的研究问题", "categories": []})
    final_dir = run_dir / "dual-agent"
    final_dir.mkdir()
    summary = {
        "schema_version": "game-ops-final-summary-1.0",
        "research_title": "绯英 PV 争议",
        "core_judgment": "质量不足被规格差异升级为待遇不公叙事。",
        "risk": {"score": 0.6, "level": "middle", "rationale": "风险集中但暂无规模证据。"},
        "confidence": {"level": "middle", "rationale": "评论充分，官方信息不足。"},
        "key_findings": ["基础体验伤口明确"],
        "operation_directions": ["补足角色表达"],
        "evidence_refs": ["XHS-0001"],
        "evidence_gaps": ["缺少官方说明"],
    }
    (final_dir / "05-final-summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    client = client_for(runs_dir)

    detail = client.get("/api/dashboard/runs/with-summary")
    listing = client.get("/api/dashboard/runs")

    assert detail.status_code == 200
    assert detail.json()["analysis_summary"] == summary
    assert detail.json()["research_target"] == "完整而很长的研究问题"
    assert listing.json()["runs"][0]["research_title"] == "绯英 PV 争议"


def test_root_summary_takes_priority_over_legacy_dual_agent_summary(runs_dir: Path) -> None:
    run_dir = write_dashboard(runs_dir, "unified-summary", {"research_target": "统一协议", "categories": []})
    legacy_dir = run_dir / "dual-agent"
    legacy_dir.mkdir()
    base = {
        "schema_version": "game-ops-final-summary-1.0",
        "research_title": "旧标题",
        "core_judgment": "旧判断",
        "risk": {"score": 0.2, "level": "low", "rationale": "旧风险"},
        "confidence": {"level": "low", "rationale": "旧置信度"},
        "key_findings": ["旧发现"],
        "operation_directions": ["旧方向"],
        "evidence_refs": [],
        "evidence_gaps": [],
    }
    (legacy_dir / "05-final-summary.json").write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    unified = {**base, "research_title": "统一标题", "core_judgment": "统一判断"}
    (run_dir / "final-summary.json").write_text(json.dumps(unified, ensure_ascii=False), encoding="utf-8")

    response = client_for(runs_dir).get("/api/dashboard/runs/unified-summary")

    assert response.status_code == 200
    assert response.json()["analysis_summary"] == unified


def test_category_sentiment_drilldown_distinguishes_weighted_expressions_and_records(runs_dir: Path) -> None:
    run_dir = write_dashboard(runs_dir, "drill", {"research_target": "测试", "categories": []})
    (run_dir / "analysis-input.json").write_text(json.dumps({
        "comments": [
            {"record_id": "XHS-1", "platform": "xiaohongshu", "text": "太短了", "support_count": 3, "merged_record_ids": ["XHS-1", "XHS-2", "XHS-3"]},
            {"record_id": "BILI-1", "platform": "bilibili", "text": "没有记忆点", "support_count": 1, "merged_record_ids": ["BILI-1"]},
            {"record_id": "DY-1", "platform": "douyin", "text": "我觉得不错", "support_count": 2, "merged_record_ids": ["DY-1", "DY-2"]},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    (run_dir / "semantic-analysis.json").write_text(json.dumps({
        "results": [
            {"record_id": "XHS-1", "include_in_dashboard": True, "aspects": [{"category_id": "pv_quality", "sentiment": "negative"}]},
            {"record_id": "BILI-1", "include_in_dashboard": True, "aspects": [{"category_id": "pv_quality", "sentiment": "negative"}]},
            {"record_id": "DY-1", "include_in_dashboard": True, "aspects": [{"category_id": "pv_quality", "sentiment": "positive"}]},
        ]
    }, ensure_ascii=False), encoding="utf-8")
    client = client_for(runs_dir)

    detail = client.get("/api/dashboard/runs/drill")
    response = client.get("/api/dashboard/runs/drill/categories/pv_quality/comments?sentiment=negative")

    assert detail.json()["comment_drilldown_available"] is True
    assert response.status_code == 200
    assert response.json() == {
        "run_id": "drill",
        "category_id": "pv_quality",
        "sentiment": "negative",
        "weighted_expression_count": 4,
        "representative_record_count": 2,
        "records": [
            {"record_id": "XHS-1", "platform": "xiaohongshu", "text": "太短了", "support_count": 3},
            {"record_id": "BILI-1", "platform": "bilibili", "text": "没有记忆点", "support_count": 1},
        ],
    }


def test_category_drilldown_rejects_bad_sentiment_and_reports_missing_sources(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "missing", {"categories": []})
    client = client_for(runs_dir)

    detail = client.get("/api/dashboard/runs/missing")
    invalid = client.get("/api/dashboard/runs/missing/categories/pv/comments?sentiment=angry")
    missing = client.get("/api/dashboard/runs/missing/categories/pv/comments?sentiment=negative")

    assert detail.json()["comment_drilldown_available"] is False
    assert invalid.status_code == 400
    assert missing.status_code == 404


def test_run_detail_rejects_traversal_and_invalid_json(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "bad", "not-json")
    client = client_for(runs_dir)

    traversal = client.get("/api/dashboard/runs/%2E%2E")
    invalid = client.get("/api/dashboard/runs/bad")

    assert traversal.status_code == 400
    assert invalid.status_code == 422
    assert "invalid JSON" in invalid.json()["detail"]


def test_report_returns_utf8_text_and_missing_report_is_404(runs_dir: Path) -> None:
    report_dir = write_dashboard(runs_dir, "with-report", {})
    (report_dir / "report.md").write_text("# 游戏洞察\n\n结论：值得关注。", encoding="utf-8")
    write_dashboard(runs_dir, "without-report", {})
    client = client_for(runs_dir)

    found = client.get("/api/dashboard/runs/with-report/report")
    missing = client.get("/api/dashboard/runs/without-report/report")

    assert found.status_code == 200
    assert found.json() == {
        "run_id": "with-report",
        "content": "# 游戏洞察\n\n结论：值得关注。",
    }
    assert missing.status_code == 404


def test_root_final_analysis_takes_priority_over_legacy_reports(runs_dir: Path) -> None:
    report_dir = write_dashboard(runs_dir, "unified-report", {})
    legacy_dir = report_dir / "dual-agent"
    legacy_dir.mkdir()
    (report_dir / "report.md").write_text("旧单 Agent 报告", encoding="utf-8")
    (legacy_dir / "05-final-analysis.md").write_text("旧双 Agent 报告", encoding="utf-8")
    (report_dir / "final-analysis.md").write_text("统一权威报告", encoding="utf-8")

    response = client_for(runs_dir).get("/api/dashboard/runs/unified-report/report")

    assert response.status_code == 200
    assert response.json()["content"] == "统一权威报告"


def test_report_read_oserror_returns_clear_4xx(runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report_dir = write_dashboard(runs_dir, "report-unreadable", {})
    (report_dir / "report.md").write_text("private", encoding="utf-8")
    original_read_text = Path.read_text

    def fail_report_read(self: Path, *args: object, **kwargs: object):
        if self.name == "report.md":
            raise PermissionError("denied report")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_report_read)

    response = client_for(runs_dir).get("/api/dashboard/runs/report-unreadable/report")

    assert response.status_code == 422
    assert "report.md cannot be read" in response.json()["detail"]


@pytest.mark.parametrize("unsafe_id", ["C:", "C:foo"])
def test_detail_and_report_reject_windows_drive_relative_ids(runs_dir: Path, unsafe_id: str) -> None:
    client = client_for(runs_dir)

    assert client.get(f"/api/dashboard/runs/{unsafe_id}").status_code == 400
    assert client.get(f"/api/dashboard/runs/{unsafe_id}/report").status_code == 400


@pytest.mark.parametrize("unsafe_id", ["nested/id", r"nested\id", "/absolute/path", r"C:\absolute"])
def test_detail_and_report_reject_separator_and_absolute_ids(runs_dir: Path, unsafe_id: str) -> None:
    client = client_for(runs_dir)

    detail = client.get(f"/api/dashboard/runs/{unsafe_id}")
    report = client.get(f"/api/dashboard/runs/{unsafe_id}/report")

    assert 400 <= detail.status_code < 500
    assert 400 <= report.status_code < 500


def test_resolved_path_must_remain_inside_runs_directory(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    outside_dashboard = tmp_path / "outside" / "dashboard.json"
    root.mkdir()
    outside_dashboard.parent.mkdir()
    outside_dashboard.write_text("{}", encoding="utf-8")

    assert _is_within_runs(root, root / "legitimate" / "dashboard.json")
    assert not _is_within_runs(root, outside_dashboard)


def test_path_resolution_oserror_keeps_run_boundary_closed(
    runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_dashboard(runs_dir, "safe-run", {})
    original_resolve = Path.resolve

    def fail_candidate_resolution(self: Path, *args: object, **kwargs: object) -> Path:
        if self.name == "dashboard.json":
            raise PermissionError("denied resolve")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_candidate_resolution)

    response = client_for(runs_dir).get("/api/dashboard/runs/safe-run")

    assert response.status_code == 404


def test_directory_symlink_cannot_expose_dashboard_or_report(runs_dir: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside-run"
    outside.mkdir()
    (outside / "dashboard.json").write_text('{"research_target": "outside"}', encoding="utf-8")
    (outside / "report.md").write_text("outside", encoding="utf-8")
    link = runs_dir / "escaped-run"
    runs_dir.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Creating directory symlinks is unavailable: {exc}")

    client = client_for(runs_dir)
    assert client.get("/api/dashboard/runs/escaped-run").status_code == 404
    assert client.get("/api/dashboard/runs/escaped-run/report").status_code == 404


def test_run_detail_backfills_null_and_empty_metadata(runs_dir: Path) -> None:
    write_dashboard(runs_dir, "legacy-null", {"run_id": None, "generated_at": ""})

    response = client_for(runs_dir).get("/api/dashboard/runs/legacy-null")

    assert response.status_code == 200
    assert response.json()["run_id"] == "legacy-null"
    assert response.json()["generated_at"]


def test_existing_static_homepage_is_served_without_shadowing_api(runs_dir: Path, tmp_path: Path) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>Dashboard</h1>", encoding="utf-8")
    client = TestClient(create_app(runs_dir=runs_dir, static_dir=static_dir))

    homepage = client.get("/")
    health = client.get("/api/dashboard/health")

    assert homepage.status_code == 200
    assert "Dashboard" in homepage.text
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_report_endpoint_refuses_a_report_path_outside_runs(
    runs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_dir = write_dashboard(runs_dir, "safe-run", {})
    (report_dir / "report.md").write_text("must not be returned", encoding="utf-8")
    original_is_within_runs = dashboard_app._is_within_runs

    def report_path_is_outside(root: Path, candidate: Path) -> bool:
        if candidate.name == "report.md":
            return False
        return original_is_within_runs(root, candidate)

    monkeypatch.setattr(dashboard_app, "_is_within_runs", report_path_is_outside)
    response = client_for(runs_dir).get("/api/dashboard/runs/safe-run/report")

    assert response.status_code == 404
    assert "must not be returned" not in response.text


def test_report_file_symlink_resolves_outside_runs_when_supported(runs_dir: Path, tmp_path: Path) -> None:
    report_dir = write_dashboard(runs_dir, "report-link", {})
    outside_report = tmp_path / "outside.md"
    outside_report.write_text("outside report", encoding="utf-8")
    report_link = report_dir / "report.md"
    try:
        report_link.symlink_to(outside_report)
    except OSError as exc:
        pytest.skip(f"Creating file symlinks is unavailable: {exc}")

    assert not _is_within_runs(runs_dir, report_link)
    response = client_for(runs_dir).get("/api/dashboard/runs/report-link/report")
    assert response.status_code in {400, 404}
    assert "outside report" not in response.text

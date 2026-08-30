"""把最终分析摘要持久注入 dashboard.json，同时证明评论统计未被修改。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def inject(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    dashboard_path = run_dir / "dashboard.json"
    summary_path = run_dir / "final-summary.json"
    dashboard = _load(dashboard_path)
    summary = _load(summary_path)
    if summary.get("schema_version") != "game-ops-final-summary-1.0":
        raise ValueError("final-summary.json has unsupported schema_version")
    protected = {
        key: dashboard.get(key)
        for key in (
            "counts",
            "platforms",
            "overall_sentiment",
            "categories",
            "final_analyzed_count",
        )
    }
    before = _fingerprint(protected)
    dashboard["analysis_summary"] = summary
    after = _fingerprint(
        {
            key: dashboard.get(key)
            for key in (
                "counts",
                "platforms",
                "overall_sentiment",
                "categories",
                "final_analyzed_count",
            )
        }
    )
    if before != after:
        raise RuntimeError("protected dashboard statistics changed during injection")
    temporary = dashboard_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(dashboard_path)
    return {
        "dashboard": str(dashboard_path),
        "analysis_summary": "injected",
        "protected_statistics_sha256": before,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="把 final-summary 注入 dashboard。")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        result = inject(args.run_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

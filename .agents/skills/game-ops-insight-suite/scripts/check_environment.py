from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SKILL_DIR.parents[2]


def main() -> int:
    commands = {
        name: shutil.which(name)
        for name in ("git", "node", "npm", "codex", "claude")
    }
    paths = {
        "project_root": PROJECT_ROOT,
        "mediacrawler_source": PROJECT_ROOT / "source" / "main.py",
        "dashboard": PROJECT_ROOT / "insight-dashboard" / "app.py",
        "dual_agent": PROJECT_ROOT / "dual-agent" / "run_dual_agent.py",
        "runs": PROJECT_ROOT / "runs",
    }
    payload = {
        "python": sys.version.split()[0],
        "commands": commands,
        "paths": {key: str(value) for key, value in paths.items()},
        "path_status": {key: value.exists() for key, value in paths.items()},
        "ready_for_collection": bool(paths["mediacrawler_source"].is_file()),
        "ready_for_dashboard": bool(paths["dashboard"].is_file()),
        "ready_for_dual_agent": bool(
            paths["dual_agent"].is_file()
            and commands["codex"]
            and commands["claude"]
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


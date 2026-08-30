from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from storage.context_pack import build_context_pack
from storage.db import db_session, init_db
from storage.import_run import import_run
from storage.repository import Repository
from storage.upsert_analysis import upsert_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_ROOT / "examples" / "hsr-fate-second-collab"


class StorageV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        artifacts = PROJECT_ROOT / "test-artifacts"
        artifacts.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="storage-", dir=artifacts)
        self.root = Path(self.temporary.name)
        self.db = self.root / "game_ops.db"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _count(self, table: str) -> int:
        with db_session(self.db) as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def _copy_example(self, name: str) -> Path:
        run = self.root / name
        shutil.copytree(EXAMPLE, run)
        return run

    def test_database_is_local_and_evidence_and_analysis_are_two_phases(self) -> None:
        path = init_db(self.db)
        self.assertTrue(path.is_relative_to(self.root))
        run = self._copy_example("history-event")
        evidence = import_run(run, self.db)
        self.assertGreater(evidence["comment_count"], 0)
        self.assertEqual(self._count("analyses"), 0)
        upsert_analysis(run, self.db, mode="single")
        self.assertEqual(self._count("analyses"), 1)

    def test_fts_search_can_exclude_current_event(self) -> None:
        run = self._copy_example("history-event")
        import_run(run, self.db)
        repository = Repository(self.db)
        self.assertTrue(repository.search_comments("联动", limit=10))
        self.assertEqual(
            repository.search_comments(
                "联动", exclude_event_id="history-event", limit=10
            ),
            [],
        )

    def test_historical_context_requires_initial_analysis(self) -> None:
        history = self._copy_example("history-event")
        import_run(history, self.db)
        upsert_analysis(history, self.db, mode="single")
        current = self.root / "current-event"
        (current / "analysis").mkdir(parents=True)
        (current / "analysis" / "initial-analysis.md").write_text(
            "# Blind initial analysis\n", encoding="utf-8"
        )
        summary = build_context_pack(current, ["联动"], self.db, limit=5)
        payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["retrieval_phase"], "after_initial_analysis")
        self.assertTrue(payload["historical_events"])
        categories = payload["historical_events"][0]["comments"][0][
            "dynamic_categories"
        ]
        self.assertTrue(categories)


if __name__ == "__main__":
    unittest.main()

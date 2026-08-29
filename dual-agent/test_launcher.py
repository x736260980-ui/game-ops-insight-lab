import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("launch_dual_agent.py")
SPEC = importlib.util.spec_from_file_location("launch_dual_agent", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LauncherTest(unittest.TestCase):
    def test_accepts_incoming_or_run_directory_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "事件 A"
            incoming = run_dir / "incoming"
            incoming.mkdir(parents=True)
            (run_dir / "analysis-input.json").write_text("{}", encoding="utf-8")

            self.assertEqual(MODULE.resolve_run_dir(f'"{incoming}"'), run_dir.resolve())
            self.assertEqual(MODULE.resolve_run_dir(str(run_dir)), run_dir.resolve())

    def test_rejects_directory_without_analysis_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "analysis-input.json"):
                MODULE.resolve_run_dir(temporary)

    def test_build_command_uses_utf8_and_passes_topic_as_one_argument(self):
        command = MODULE.build_command(Path("E:/事件 A"), "PV质量还是待遇不公")
        self.assertEqual(command[:3], [MODULE.sys.executable, "-X", "utf8"])
        self.assertEqual(command[-4:], ["--run-dir", str(Path("E:/事件 A")), "--topic", "PV质量还是待遇不公"])


if __name__ == "__main__":
    unittest.main()

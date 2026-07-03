from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class DistributionDocsTests(TestCase):
    def test_readme_describes_gui_startup_and_model_workflow(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("双击 `启动.bat`", readme)
        self.assertIn("模型配置", readme)
        self.assertIn("设为 writer", readme)
        self.assertIn("设为 reviewer", readme)
        self.assertIn("dry-run", readme)
        self.assertIn("projects/", readme)

    def test_startup_batch_bootstraps_environment_and_runs_gui(self):
        script = (ROOT / "启动.bat").read_text(encoding="utf-8")

        script.encode("ascii")
        self.assertIn("python -m venv .venv", script)
        self.assertIn(".venv\\Scripts\\python.exe", script)
        self.assertIn("-m pip install -r requirements.txt", script)
        self.assertIn("run_gui.py", script)
        self.assertIn("pause", script.lower())

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramScaffoldTest(unittest.TestCase):
    def test_app_config_points_to_home_first(self):
        app_config = json.loads((MINIPROGRAM_ROOT / "app.json").read_text())

        self.assertEqual(app_config["pages"][0], "pages/home/index")
        self.assertIn("pages/ashare/index", app_config["pages"])
        self.assertIn("pages/beijing/index", app_config["pages"])

    def test_project_config_does_not_contain_real_sensitive_values(self):
        project_config = json.loads((MINIPROGRAM_ROOT / "project.config.json").read_text())

        self.assertEqual(project_config["appid"], "touristappid")
        self.assertEqual(project_config["cloudfunctionRoot"], "../api/cloudfunctions/")
        serialized = json.dumps(project_config, ensure_ascii=False).lower()
        self.assertNotIn("env-id", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("token", serialized)

    def test_private_project_config_is_ignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text()

        self.assertIn("miniprogram/project.private.config.json", gitignore)

    def test_ec_canvas_source_files_are_present(self):
        required_files = [
            "ec-canvas.js",
            "ec-canvas.json",
            "ec-canvas.wxml",
            "ec-canvas.wxss",
            "wx-canvas.js",
            "echarts.js",
        ]

        for file_name in required_files:
            path = MINIPROGRAM_ROOT / "components" / "ec-canvas" / file_name
            self.assertTrue(path.exists(), file_name)
            self.assertGreater(path.stat().st_size, 20, file_name)

        echarts_source = (MINIPROGRAM_ROOT / "components" / "ec-canvas" / "echarts.js").read_text()
        self.assertIn("Apache Software Foundation", echarts_source)


if __name__ == "__main__":
    unittest.main()

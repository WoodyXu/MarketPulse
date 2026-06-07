import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_GUIDE = PROJECT_ROOT / "docs" / "delivery-guide.md"


class DeliveryDocumentationTest(unittest.TestCase):
    def test_delivery_guide_covers_required_step_25_topics(self):
        content = DELIVERY_GUIDE.read_text(encoding="utf-8")

        required_phrases = (
            "生成 payload",
            "上传到云存储",
            "部署云函数",
            "小程序本地调试与预览",
            "测试云环境",
            "已知限制",
            "python3 -m pytest",
            "getDashboardSection",
            "marketpulse-payload/manifest.json",
            "project.private.config.json",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, content)

    def test_delivery_guide_preserves_product_boundaries(self):
        content = DELIVERY_GUIDE.read_text(encoding="utf-8")

        self.assertIn("不修改 `src/security_market_pulse.py`", content)
        self.assertIn("不新增指标", content)
        self.assertIn("不得提交或公开", content)
        self.assertIn("不允许小程序端或公网直接读取", content)

    def test_readmes_link_to_delivery_guide(self):
        readme_paths = (
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "api" / "README.md",
            PROJECT_ROOT / "api" / "cloudfunctions" / "getDashboardSection" / "README.md",
        )

        for readme_path in readme_paths:
            with self.subTest(readme_path=readme_path):
                content = readme_path.read_text(encoding="utf-8")
                self.assertIn("delivery-guide.md", content)


if __name__ == "__main__":
    unittest.main()

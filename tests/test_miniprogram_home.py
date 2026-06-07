import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOME_PAGE = REPO_ROOT / "miniprogram" / "pages" / "home" / "index.js"


class MiniProgramHomeTest(unittest.TestCase):
    def test_home_page_exposes_only_two_board_entries(self):
        script = textwrap.dedent(
            f"""
            let pageConfig = null;
            global.Page = (config) => {{ pageConfig = config; }};

            require({json.dumps(str(HOME_PAGE))});

            const boards = pageConfig.data.boards;
            if (boards.length !== 2) {{
              throw new Error(`expected 2 boards, got ${{boards.length}}`);
            }}

            const titles = boards.map((board) => board.title);
            const paths = boards.map((board) => board.path);
            if (JSON.stringify(titles) !== JSON.stringify(["资本市场", "北京楼市"])) {{
              throw new Error(`unexpected board titles: ${{JSON.stringify(titles)}}`);
            }}
            if (JSON.stringify(paths) !== JSON.stringify(["/pages/ashare/index", "/pages/beijing/index"])) {{
              throw new Error(`unexpected board paths: ${{JSON.stringify(paths)}}`);
            }}
            """
        )

        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_home_share_routes_to_home_page(self):
        script = textwrap.dedent(
            f"""
            let pageConfig = null;
            global.Page = (config) => {{ pageConfig = config; }};

            require({json.dumps(str(HOME_PAGE))});

            const message = pageConfig.onShareAppMessage();
            const timeline = pageConfig.onShareTimeline();
            if (message.title !== "MarketPulse 市场脉搏" || message.path !== "/pages/home/index") {{
              throw new Error(`unexpected share message: ${{JSON.stringify(message)}}`);
            }}
            if (timeline.title !== "MarketPulse 市场脉搏") {{
              throw new Error(`unexpected timeline share: ${{JSON.stringify(timeline)}}`);
            }}
            """
        )

        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_home_page_does_not_request_dashboard_sections(self):
        home_js = HOME_PAGE.read_text(encoding="utf-8")

        self.assertNotIn("utils/request", home_js)
        self.assertNotIn("requestDashboardSection", home_js)
        self.assertNotIn("wx.cloud.callFunction", home_js)
        self.assertNotIn("getDashboardSection", home_js)


if __name__ == "__main__":
    unittest.main()

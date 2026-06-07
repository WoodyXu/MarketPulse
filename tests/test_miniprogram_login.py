import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramLoginTest(unittest.TestCase):
    def test_auth_utility_completes_profile_and_wx_login(self):
        script = textwrap.dedent(
            f"""
            const auth = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))});
            const storage = {{}};
            const wxApi = {{
              getStorageSync(key) {{ return storage[key]; }},
              setStorageSync(key, value) {{ storage[key] = value; }},
              removeStorageSync(key) {{ delete storage[key]; }},
              login(options) {{ options.success({{ code: "login-code" }}); }}
            }};

            auth.loginWithUserInfo({{ avatarUrl: "avatar.png", nickName: "测试用户" }}, wxApi)
              .then((result) => {{
                const state = auth.getLoginState(wxApi);
                if (!result.loggedIn || result.loginCode !== "login-code") {{
                  throw new Error("login result mismatch");
                }}
                if (!state.loggedIn || state.userInfo.nickName !== "测试用户") {{
                  throw new Error("stored login state mismatch");
                }}
              }})
              .catch((error) => {{
                console.error(error.message);
                process.exit(1);
              }});
            """
        )

        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_auth_utility_rejects_incomplete_profile(self):
        script = textwrap.dedent(
            f"""
            const auth = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))});
            const wxApi = {{
              login() {{ throw new Error("wx.login should not run"); }}
            }};

            auth.loginWithUserInfo({{ avatarUrl: "", nickName: "测试用户" }}, wxApi)
              .then(() => {{
                console.error("expected rejection");
                process.exit(1);
              }})
              .catch((error) => {{
                if (!error.message.includes("请先选择头像并填写昵称")) {{
                  console.error(error.message);
                  process.exit(1);
                }}
              }});
            """
        )

        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_all_entry_pages_render_login_panel(self):
        page_dirs = [
            MINIPROGRAM_ROOT / "pages" / "home",
            MINIPROGRAM_ROOT / "pages" / "ashare",
            MINIPROGRAM_ROOT / "pages" / "beijing",
        ]

        for page_dir in page_dirs:
            page_js = (page_dir / "index.js").read_text(encoding="utf-8")
            page_wxml = (page_dir / "index.wxml").read_text(encoding="utf-8")

            self.assertIn("require('../../utils/auth')", page_js)
            self.assertIn("refreshLoginState", page_js)
            self.assertIn("submitLogin", page_js)
            self.assertIn('open-type="chooseAvatar"', page_wxml)
            self.assertIn('type="nickname"', page_wxml)
            self.assertIn('wx:if="{{!loginState.loggedIn}}"', page_wxml)
            self.assertIn("登录失败，请重试", page_js)

    def test_home_does_not_navigate_to_board_before_login(self):
        home_js = (MINIPROGRAM_ROOT / "pages" / "home" / "index.js").read_text(encoding="utf-8")

        self.assertIn("if (!this.data.loginState.loggedIn)", home_js)
        self.assertIn("请先登录后查看看板", home_js)
        self.assertIn("wx.navigateTo", home_js)


if __name__ == "__main__":
    unittest.main()

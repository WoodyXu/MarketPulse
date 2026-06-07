import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramBeijingPageTest(unittest.TestCase):
    def run_node_script(self, script):
        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_beijing_share_routes_to_board_and_login_resumes_target_page(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js"))};
            const authPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))};
            const requestPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))};
            const pageResolved = require.resolve(pagePath);
            const authResolved = require.resolve(authPath);
            const requestResolved = require.resolve(requestPath);

            delete require.cache[pageResolved];
            let loggedIn = false;
            require.cache[authResolved] = {{
              id: authResolved,
              filename: authResolved,
              loaded: true,
              exports: {{
                getLoginState() {{ return {{ loggedIn }}; }},
                loginWithUserInfo() {{
                  loggedIn = true;
                  return Promise.resolve({{ loggedIn: true }});
                }}
              }}
            }};

            const calls = [];
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section) {{
                  calls.push({{ type, section }});
                  return Promise.resolve({{ type, section, data: [] }});
                }}
              }}
            }};

            function applySetData(target, updates) {{
              Object.keys(updates).forEach((key) => {{
                const parts = key.split(".");
                let cursor = target.data;
                for (let index = 0; index < parts.length - 1; index += 1) {{
                  cursor = cursor[parts[index]];
                }}
                cursor[parts[parts.length - 1]] = updates[key];
              }});
            }}

            let page = null;
            global.Page = (config) => {{
              page = config;
              page.data = JSON.parse(JSON.stringify(config.data));
              page.setData = (updates) => applySetData(page, updates);
            }};

            require(pageResolved);

            (async () => {{
              const share = page.onShareAppMessage();
              if (share.title !== "MarketPulse 北京楼市看板" || share.path !== "/pages/beijing/index") {{
                throw new Error(`unexpected Beijing real estate share: ${{JSON.stringify(share)}}`);
              }}

              await page.onLoad();
              if (page.data.loginState.loggedIn || calls.length !== 0) {{
                throw new Error("unauthenticated share receiver should stay on the target page login gate");
              }}

              page.setData({{
                authForm: {{
                  avatarUrl: "avatar.png",
                  nickName: "测试用户"
                }}
              }});
              page.submitLogin();
              await new Promise((resolve) => setImmediate(resolve));
              await new Promise((resolve) => setImmediate(resolve));

              if (!page.data.loginState.loggedIn) {{
                throw new Error("share receiver should complete login on the Beijing real estate page");
              }}
              if (calls.length !== 1 || calls[0].type !== "beijing" || calls[0].section !== "houseViewPeople") {{
                throw new Error("login should resume the Beijing real estate target page");
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_beijing_page_requests_main_tabs_and_credit_sub_tabs_do_not_refetch(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js"))};
            const authPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))};
            const requestPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))};
            const pageResolved = require.resolve(pagePath);
            const authResolved = require.resolve(authPath);
            const requestResolved = require.resolve(requestPath);

            delete require.cache[pageResolved];
            require.cache[authResolved] = {{
              id: authResolved,
              filename: authResolved,
              loaded: true,
              exports: {{
                getLoginState() {{ return {{ loggedIn: true }}; }},
                loginWithUserInfo() {{ return Promise.resolve({{ loggedIn: true }}); }}
              }}
            }};

            const calls = [];
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section) {{
                  calls.push({{ type, section }});
                  const payloads = {{
                    houseViewPeople: [
                      {{ x: "2026-06-01", label: "2026-06-01", value: 1250, weekday: "周一" }},
                      {{ x: "2026-06-07", label: "2026-06-07", value: 1680, weekday: "周末" }}
                    ],
                    decreaseRatio: [
                      {{ x: "2026-06-01", label: "2026-06-01", value: 8.5 }}
                    ],
                    lianjiaDeals: [
                      {{ x: "2026-06-01", label: "2026-06-01", value: 420, weekday: "周一" }},
                      {{ x: "2026-06-07", label: "2026-06-07", value: 1350, weekday: "周末" }}
                    ],
                    onlineSignings: {{
                      dailyOnlineSignings: [{{ x: "2026-06-01", label: "2026-06-01", value: 420 }}],
                      monthlyOnlineSignings: [{{ x: "2026-06-01", label: "2026-06", value: 11800 }}]
                    }},
                    credit: {{
                      creditYoy: [{{ x: "2026-05-01", label: "2026-05", value: 0.0325 }}],
                      loanNetIncreaseByMonth: [
                        {{ x: 2026, label: "2026", year: 2026, month: 1, value: 21.5 }},
                        {{ x: 2026, label: "2026", year: 2026, month: 12, value: -12.25 }}
                      ],
                      totalLoanNetIncreaseByMonth: [
                        {{ x: 2026, label: "2026", year: 2026, month: 1, value: 21.5 }},
                        {{ x: 2026, label: "2026", year: 2026, month: 12, value: 210.75 }}
                      ]
                    }}
                  }};
                  return Promise.resolve({{
                    type,
                    section,
                    data: payloads[section]
                  }});
                }}
              }}
            }};

            function applySetData(target, updates) {{
              Object.keys(updates).forEach((key) => {{
                const parts = key.split(".");
                let cursor = target.data;
                for (let index = 0; index < parts.length - 1; index += 1) {{
                  cursor = cursor[parts[index]];
                }}
                cursor[parts[parts.length - 1]] = updates[key];
              }});
            }}

            let page = null;
            global.Page = (config) => {{
              page = config;
              page.data = JSON.parse(JSON.stringify(config.data));
              page.setData = (updates) => applySetData(page, updates);
            }};

            require(pageResolved);

            (async () => {{
              await page.onLoad();
              if (calls.length !== 1 || calls[0].type !== "beijing" || calls[0].section !== "houseViewPeople") {{
                throw new Error("default tab should be the only first-load request");
              }}
              if (!page.data.sectionStates.houseViewPeople.loaded) {{
                throw new Error("default tab should be marked loaded");
              }}
              if (page.data.activeSectionState.chartCards.length !== 6) {{
                throw new Error("house view section should render one chart per weekday group");
              }}
              const firstHousePoint = page.data.activeSectionState.chartCards[0].ec.option.series[0].data[0];
              if (page.data.activeSectionState.chartCards[0].title !== "周一看房人数" || firstHousePoint[1] !== 1250) {{
                throw new Error("house view chart should preserve weekday order and payload values");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "decreaseRatio" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 1 || page.data.activeSectionState.chartCards[0].ec.option.series[0].markLine.data[0].yAxis !== 10) {{
                throw new Error("decrease ratio chart should keep the reference line");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "lianjiaDeals" }} }} }});
              const weekendDealCard = page.data.activeSectionState.chartCards.find((chart) => chart.title === "周末大中介成交量");
              if (!weekendDealCard || weekendDealCard.ec.option.series[0].markLine.data[0].yAxis !== 1200) {{
                throw new Error("weekend large-agency deal chart should keep the 1200 reference line");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "onlineSignings" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 2) {{
                throw new Error("online signing section should render daily and monthly charts only");
              }}
              const monthlySigningCard = page.data.activeSectionState.chartCards.find((chart) => chart.title === "每月二手房网签量");
              if (!monthlySigningCard || monthlySigningCard.ec.option.series[0].markLine.data[0].yAxis !== 12000) {{
                throw new Error("monthly online signing chart should keep the 12000 reference line");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "credit" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 1 || page.data.activeSectionState.chartCards[0].title !== "居民贷款余额增速") {{
                throw new Error("credit default sub tab should render only the YoY chart");
              }}
              if (page.data.activeSectionState.chartCards[0].ec.option.series[0].markLine.data[0].yAxis !== 0) {{
                throw new Error("credit YoY chart should keep the zero reference line");
              }}

              const requestedSections = calls.map((call) => call.section).join(",");
              if (requestedSections !== "houseViewPeople,decreaseRatio,lianjiaDeals,onlineSignings,credit") {{
                throw new Error(`unexpected request order: ${{requestedSections}}`);
              }}

              page.onTapCreditTab({{ currentTarget: {{ dataset: {{ key: "loanNetIncreaseByMonth" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 12 || page.data.activeSectionState.chartCards[0].title !== "1月当月居民贷款增量") {{
                throw new Error("credit monthly increase sub tab should render 12 month-specific charts");
              }}
              page.onTapCreditTab({{ currentTarget: {{ dataset: {{ key: "totalLoanNetIncreaseByMonth" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 12 || page.data.activeSectionState.chartCards[11].title !== "1-12月居民贷款增量") {{
                throw new Error("credit YTD increase sub tab should render 12 month-specific charts");
              }}
              page.onTapCreditTab({{ currentTarget: {{ dataset: {{ key: "creditYoy" }} }} }});
              if (page.data.activeSectionState.chartCards.length !== 1 || page.data.activeSectionState.chartCards[0].title !== "居民贷款余额增速") {{
                throw new Error("credit YoY sub tab should not stack monthly chart groups");
              }}
              if (calls.length !== 5) {{
                throw new Error("credit sub tabs should not request extra dashboard sections");
              }}
              if (page.data.activeCreditTab !== "creditYoy" || page.data.activeCreditTabTitle !== "同比") {{
                throw new Error("active credit sub tab state mismatch");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "houseViewPeople" }} }} }});
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "credit" }} }} }});
              if (calls.length !== 5) {{
                throw new Error("loaded main sections should not be requested again");
              }}
              if (page.data.activeTab !== "credit" || page.data.activeTabTitle !== "居民贷款") {{
                throw new Error("active main tab state mismatch after switching back");
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_beijing_page_structure_stays_with_real_estate_sections(self):
        page_js = (MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js").read_text(encoding="utf-8")
        page_wxml = (MINIPROGRAM_ROOT / "pages" / "beijing" / "index.wxml").read_text(encoding="utf-8")
        page_json = (MINIPROGRAM_ROOT / "pages" / "beijing" / "index.json").read_text(encoding="utf-8")

        self.assertIn("require('../../utils/request')", page_js)
        self.assertIn("require('../../utils/echarts-option')", page_js)
        self.assertIn("const DASHBOARD_TYPE = 'beijing'", page_js)
        self.assertIn("const DEFAULT_TAB = 'houseViewPeople'", page_js)
        self.assertIn("requestDashboardSection(DASHBOARD_TYPE, section, {", page_js)
        self.assertIn("onPullDownRefresh()", page_js)
        self.assertIn("stopPullDownRefresh", page_js)
        self.assertIn('"enablePullDownRefresh": true', page_json)
        self.assertIn('bindtap="onTapTab"', page_wxml)
        self.assertIn('bindtap="onTapCreditTab"', page_wxml)
        self.assertIn('bindtap="retryActiveSection"', page_wxml)
        self.assertIn("重试", page_wxml)
        self.assertIn("<ec-canvas", page_wxml)
        self.assertIn("activeTab === 'credit'", page_wxml)

        for section in ["houseViewPeople", "decreaseRatio", "lianjiaDeals", "onlineSignings", "credit"]:
            self.assertIn(section, page_js)

        for credit_section in ["creditYoy", "loanNetIncreaseByMonth", "totalLoanNetIncreaseByMonth"]:
            self.assertIn(credit_section, page_js)

        self.assertNotIn("indexDeviation", page_js)
        self.assertNotIn("topConcentration", page_js)

    def test_beijing_pull_down_refresh_forces_only_active_main_tab_and_stops_refresh(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js"))};
            const authPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))};
            const requestPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))};
            const pageResolved = require.resolve(pagePath);
            const authResolved = require.resolve(authPath);
            const requestResolved = require.resolve(requestPath);

            delete require.cache[pageResolved];
            require.cache[authResolved] = {{
              id: authResolved,
              filename: authResolved,
              loaded: true,
              exports: {{
                getLoginState() {{ return {{ loggedIn: true }}; }},
                loginWithUserInfo() {{ return Promise.resolve({{ loggedIn: true }}); }}
              }}
            }};

            const calls = [];
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section, options) {{
                  calls.push({{ type, section, forceRefresh: Boolean(options && options.forceRefresh) }});
                  const payloads = {{
                    houseViewPeople: [],
                    credit: {{
                      creditYoy: [{{ x: "2026-05-01", label: "2026-05", value: 0.0325 }}],
                      loanNetIncreaseByMonth: [],
                      totalLoanNetIncreaseByMonth: []
                    }}
                  }};
                  return Promise.resolve({{
                    type,
                    section,
                    data: payloads[section] || []
                  }});
                }}
              }}
            }};

            let stopPullDownRefreshCount = 0;
            global.wx = {{
              stopPullDownRefresh() {{
                stopPullDownRefreshCount += 1;
              }}
            }};

            function applySetData(target, updates) {{
              Object.keys(updates).forEach((key) => {{
                const parts = key.split(".");
                let cursor = target.data;
                for (let index = 0; index < parts.length - 1; index += 1) {{
                  cursor = cursor[parts[index]];
                }}
                cursor[parts[parts.length - 1]] = updates[key];
              }});
            }}

            let page = null;
            global.Page = (config) => {{
              page = config;
              page.data = JSON.parse(JSON.stringify(config.data));
              page.setData = (updates) => applySetData(page, updates);
            }};

            require(pageResolved);

            (async () => {{
              await page.onLoad();
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "credit" }} }} }});
              page.onTapCreditTab({{ currentTarget: {{ dataset: {{ key: "loanNetIncreaseByMonth" }} }} }});
              await page.onPullDownRefresh();

              const requestSummary = calls.map((call) => `${{call.section}}:${{call.forceRefresh}}`).join(",");
              if (requestSummary !== "houseViewPeople:false,credit:false,credit:true") {{
                throw new Error(`pull refresh should force only the active main tab: ${{requestSummary}}`);
              }}
              if (stopPullDownRefreshCount !== 1) {{
                throw new Error("pull refresh should stop after refresh completes");
              }}
              if (page.data.activeTab !== "credit" || page.data.activeCreditTab !== "loanNetIncreaseByMonth") {{
                throw new Error("pull refresh should not change the active tab state");
              }}
              if (page.data.sectionStates.houseViewPeople.loading || page.data.sectionStates.houseViewPeople.error) {{
                throw new Error("pull refresh should not touch inactive main section state");
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_beijing_error_state_stays_stable_and_retry_reloads_active_main_section(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js"))};
            const authPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "auth.js"))};
            const requestPath = {json.dumps(str(MINIPROGRAM_ROOT / "utils" / "request.js"))};
            const pageResolved = require.resolve(pagePath);
            const authResolved = require.resolve(authPath);
            const requestResolved = require.resolve(requestPath);

            delete require.cache[pageResolved];
            require.cache[authResolved] = {{
              id: authResolved,
              filename: authResolved,
              loaded: true,
              exports: {{
                getLoginState() {{ return {{ loggedIn: true }}; }},
                loginWithUserInfo() {{ return Promise.resolve({{ loggedIn: true }}); }}
              }}
            }};

            const calls = [];
            const responses = [
              Promise.resolve({{ type: "beijing", section: "houseViewPeople", data: [] }}),
              Promise.reject(new Error("暂无可用数据，请稍后重试")),
              Promise.resolve({{ type: "beijing", section: "credit", data: {{ creditYoy: [] }} }}),
              Promise.resolve({{
                type: "beijing",
                section: "credit",
                data: {{
                  creditYoy: [],
                  loanNetIncreaseByMonth: [],
                  totalLoanNetIncreaseByMonth: []
                }}
              }})
            ];
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section, options) {{
                  calls.push({{ type, section, forceRefresh: Boolean(options && options.forceRefresh) }});
                  return responses.shift();
                }}
              }}
            }};

            function applySetData(target, updates) {{
              Object.keys(updates).forEach((key) => {{
                const parts = key.split(".");
                let cursor = target.data;
                for (let index = 0; index < parts.length - 1; index += 1) {{
                  cursor = cursor[parts[index]];
                }}
                cursor[parts[parts.length - 1]] = updates[key];
              }});
            }}

            let page = null;
            global.Page = (config) => {{
              page = config;
              page.data = JSON.parse(JSON.stringify(config.data));
              page.setData = (updates) => applySetData(page, updates);
            }};

            require(pageResolved);

            (async () => {{
              await page.onLoad();
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "credit" }} }} }}).catch(() => null);
              if (page.data.activeTab !== "credit" || page.data.sectionStates.houseViewPeople.error) {{
                throw new Error("credit load failure should not disturb inactive loaded section");
              }}
              if (page.data.activeSectionState.error !== "暂无可用数据，请稍后重试") {{
                throw new Error(`unexpected missing payload text: ${{page.data.activeSectionState.error}}`);
              }}

              await page.retryActiveSection();
              if (page.data.activeSectionState.error !== "数据结构异常，请稍后重试") {{
                throw new Error(`malformed credit payload should be rejected: ${{page.data.activeSectionState.error}}`);
              }}

              await page.retryActiveSection();
              if (!page.data.activeSectionState.loaded || page.data.activeSectionState.error) {{
                throw new Error("retry should reload the active credit section and clear error");
              }}

              const requestSummary = calls.map((call) => `${{call.section}}:${{call.forceRefresh}}`).join(",");
              if (requestSummary !== "houseViewPeople:false,credit:false,credit:true,credit:true") {{
                throw new Error(`retry should only refetch the active main section: ${{requestSummary}}`);
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)


if __name__ == "__main__":
    unittest.main()

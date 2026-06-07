import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramAsharePageTest(unittest.TestCase):
    def run_node_script(self, script):
        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_ashare_share_routes_to_board_and_login_resumes_target_page(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js"))};
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
              if (share.title !== "MarketPulse 资本市场看板" || share.path !== "/pages/ashare/index") {{
                throw new Error(`unexpected capital market share: ${{JSON.stringify(share)}}`);
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
                throw new Error("share receiver should complete login on the capital market page");
              }}
              if (calls.length !== 1 || calls[0].type !== "ashare" || calls[0].section !== "indexDeviation") {{
                throw new Error("login should resume the capital market target page");
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_ashare_page_requests_default_tab_and_reuses_loaded_sections(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js"))};
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
            const payloadBySection = {{
              indexDeviation: [],
              margin: [],
              turnover: [],
              topConcentration: {{
                chart: [],
                recentTables: []
              }}
            }};
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section) {{
                  calls.push({{ type, section }});
                  return Promise.resolve({{
                    type,
                    section,
                    data: payloadBySection[section]
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
              if (calls.length !== 1 || calls[0].type !== "ashare" || calls[0].section !== "indexDeviation") {{
                throw new Error("default tab should be the only first-load request");
              }}
              if (!page.data.sectionStates.indexDeviation.loaded) {{
                throw new Error("default tab should be marked loaded");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "margin" }} }} }});
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "turnover" }} }} }});
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "topConcentration" }} }} }});

              const requestedSections = calls.map((call) => call.section).join(",");
              if (requestedSections !== "indexDeviation,margin,turnover,topConcentration") {{
                throw new Error(`unexpected request order: ${{requestedSections}}`);
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "margin" }} }} }});
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "indexDeviation" }} }} }});
              if (calls.length !== 4) {{
                throw new Error("loaded sections should not be requested again");
              }}
              if (page.data.activeTab !== "indexDeviation" || page.data.activeTabTitle !== "指数MA60偏离") {{
                throw new Error("active tab state mismatch after switching back");
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_ashare_page_structure_stays_with_capital_market_sections(self):
        page_js = (MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js").read_text(encoding="utf-8")
        page_wxml = (MINIPROGRAM_ROOT / "pages" / "ashare" / "index.wxml").read_text(encoding="utf-8")
        page_json = (MINIPROGRAM_ROOT / "pages" / "ashare" / "index.json").read_text(encoding="utf-8")

        self.assertIn("require('../../utils/request')", page_js)
        self.assertIn("require('../../utils/echarts-option')", page_js)
        self.assertIn("const DASHBOARD_TYPE = 'ashare'", page_js)
        self.assertIn("const DEFAULT_TAB = 'indexDeviation'", page_js)
        self.assertIn("requestDashboardSection(DASHBOARD_TYPE, section, {", page_js)
        self.assertIn("onPullDownRefresh()", page_js)
        self.assertIn("stopPullDownRefresh", page_js)
        self.assertIn('"enablePullDownRefresh": true', page_json)
        self.assertIn('bindtap="onTapTab"', page_wxml)
        self.assertIn("<ec-canvas", page_wxml)
        self.assertIn('scroll-x="true"', page_wxml)
        self.assertIn("最近 5 个交易日 Top5 股票", page_wxml)
        self.assertIn('bindtap="retryActiveSection"', page_wxml)
        self.assertIn("重试", page_wxml)

        for section in ["indexDeviation", "margin", "turnover", "topConcentration"]:
            self.assertIn(section, page_js)

        self.assertNotIn("houseViewPeople", page_js)
        self.assertNotIn("credit", page_js)

    def test_ashare_page_builds_chart_cards_and_top_stock_tables_from_payload(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js"))};
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

            const payloadBySection = {{
              indexDeviation: [
                {{ date: "2026-06-01", series: "A股-沪深300", close: 3600, ma60: 3500, deviation: 0.028571 }},
                {{ date: "2026-06-02", series: "A股-沪深300", close: 3550, ma60: 3500, deviation: 0.014286 }},
                {{ date: "2026-06-01", series: "A股-创业板指", close: 1900, ma60: 2000, deviation: -0.05 }}
              ],
              margin: [
                {{ date: "2026-06-01", marginBalance100m: 18500.25, marginToMarketCap: 0.0215 }},
                {{ date: "2026-06-02", marginBalance100m: 18610.5, marginToMarketCap: 0.022 }}
              ],
              turnover: [
                {{ date: "2026-06-01", totalAmount100m: 9800.5, hs300Close: 3650.25 }},
                {{ date: "2026-06-02", totalAmount100m: 10010.75, hs300Close: 3666.5 }}
              ],
              topConcentration: {{
                chart: [
                  {{ date: "2026-06-01", value: 0.1825 }},
                  {{ date: "2026-06-02", value: 0.19 }}
                ],
                recentTables: [
                  {{
                    date: "2026-06-02",
                    stocks: [
                      {{ tsCode: "000001.SZ", name: "平安银行", amountYuan: 1234567890, pctChg: 1.234 }},
                      {{ tsCode: "600000.SH", name: "", amountYuan: 987654321, pctChg: -0.5 }}
                    ]
                  }}
                ]
              }}
            }};

            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section) {{
                  return Promise.resolve({{
                    type,
                    section,
                    data: payloadBySection[section]
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
              const indexState = page.data.sectionStates.indexDeviation;
              if (indexState.chartCards.length !== 2) {{
                throw new Error("index deviation should render one chart card per index series");
              }}
              if (indexState.chartCards[0].ec.option.series[0].data[1][1] !== 0.014286) {{
                throw new Error("index deviation latest point should come from payload");
              }}
              if (typeof indexState.chartCards[0].ec.onInit !== "function") {{
                throw new Error("chart card should provide ec-canvas onInit");
              }}
              if (indexState.chartCards[0].ec.option.series[0].markLine.data[0].yAxis !== 0) {{
                throw new Error("index deviation zero reference line missing");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "margin" }} }} }});
              const marginState = page.data.sectionStates.margin;
              if (marginState.chartCards.length !== 2) {{
                throw new Error("margin should render balance and ratio charts");
              }}
              if (marginState.chartCards[1].ec.option.yAxis.axisLabel.formatter(0.022) !== "2.20%") {{
                throw new Error("margin ratio formatter mismatch");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "turnover" }} }} }});
              const turnoverState = page.data.sectionStates.turnover;
              if (turnoverState.chartCards.length !== 1 || turnoverState.chartCards[0].ec.option.series.length !== 2) {{
                throw new Error("turnover should render one dual-axis chart");
              }}
              if (turnoverState.chartCards[0].ec.option.series[1].data[1][1] !== 3666.5) {{
                throw new Error("turnover HS300 latest point mismatch");
              }}

              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "topConcentration" }} }} }});
              const concentrationState = page.data.sectionStates.topConcentration;
              if (concentrationState.chartCards.length !== 1) {{
                throw new Error("top concentration should render one chart");
              }}
              if (concentrationState.chartCards[0].ec.option.series[0].data[1][1] !== 0.19) {{
                throw new Error("top concentration latest point mismatch");
              }}
              if (concentrationState.topStockTables.length !== 1 || concentrationState.topStockTables[0].stocks.length !== 2) {{
                throw new Error("top stock tables should render recent table rows");
              }}
              const firstStock = concentrationState.topStockTables[0].stocks[0];
              if (firstStock.displayName !== "平安银行" || firstStock.amountText !== "12.35亿" || firstStock.pctChgText !== "+1.23%") {{
                throw new Error(`formatted first stock mismatch: ${{JSON.stringify(firstStock)}}`);
              }}
              const secondStock = concentrationState.topStockTables[0].stocks[1];
              if (secondStock.displayName !== "600000.SH" || secondStock.pctChgClass !== "stock-down") {{
                throw new Error(`fallback stock name/change class mismatch: ${{JSON.stringify(secondStock)}}`);
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_ashare_error_state_stays_stable_and_retry_reloads_active_section(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js"))};
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
              Promise.reject(new Error("云函数请求失败，请稍后重试")),
              Promise.resolve({{ type: "ashare", section: "indexDeviation", data: {{ malformed: true }} }}),
              Promise.resolve({{ type: "ashare", section: "indexDeviation", data: [] }})
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
              await page.onLoad().catch(() => null);
              if (page.data.activeTab !== "indexDeviation" || page.data.activeSectionState.loaded) {{
                throw new Error("failed first load should keep current tab structure without marking loaded");
              }}
              if (page.data.activeSectionState.error !== "云函数请求失败，请稍后重试") {{
                throw new Error(`unexpected cloud failure text: ${{page.data.activeSectionState.error}}`);
              }}

              await page.retryActiveSection();
              if (page.data.activeSectionState.error !== "数据结构异常，请稍后重试") {{
                throw new Error(`malformed section should use stable structure error: ${{page.data.activeSectionState.error}}`);
              }}

              await page.retryActiveSection();
              if (!page.data.activeSectionState.loaded || page.data.activeSectionState.error) {{
                throw new Error("retry should reload the current section and clear error");
              }}

              const requestSummary = calls.map((call) => `${{call.section}}:${{call.forceRefresh}}`).join(",");
              if (requestSummary !== "indexDeviation:false,indexDeviation:true,indexDeviation:true") {{
                throw new Error(`retry should only refetch the active section: ${{requestSummary}}`);
              }}
            }})().catch((error) => {{
              console.error(error.message);
              process.exit(1);
            }});
            """
        )

        self.run_node_script(script)

    def test_ashare_pull_down_refresh_forces_only_active_section_and_stops_refresh(self):
        script = textwrap.dedent(
            f"""
            const pagePath = {json.dumps(str(MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js"))};
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
            let failNextRequest = false;
            function buildPayload(section, callNumber) {{
              if (section === "topConcentration") {{
                return {{
                  chart: [{{ callNumber }}],
                  recentTables: []
                }};
              }}
              return [{{ callNumber }}];
            }}
            require.cache[requestResolved] = {{
              id: requestResolved,
              filename: requestResolved,
              loaded: true,
              exports: {{
                requestDashboardSection(type, section, options) {{
                  calls.push({{ type, section, forceRefresh: Boolean(options && options.forceRefresh) }});
                  if (failNextRequest) {{
                    failNextRequest = false;
                    return Promise.reject(new Error("cloud failed"));
                  }}
                  return Promise.resolve({{
                    type,
                    section,
                    data: buildPayload(section, calls.length)
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
              await page.onTapTab({{ currentTarget: {{ dataset: {{ key: "margin" }} }} }});
              await page.onPullDownRefresh();

              const requestSummary = calls.map((call) => `${{call.section}}:${{call.forceRefresh}}`).join(",");
              if (requestSummary !== "indexDeviation:false,margin:false,margin:true") {{
                throw new Error(`pull refresh should force only the active tab: ${{requestSummary}}`);
              }}
              if (stopPullDownRefreshCount !== 1) {{
                throw new Error("pull refresh should stop after successful refresh");
              }}
              if (page.data.activeTab !== "margin" || page.data.activeSectionState.data[0].callNumber !== 3) {{
                throw new Error("pull refresh should update the active section state");
              }}

              failNextRequest = true;
              await page.onPullDownRefresh();
              if (calls.length !== 4 || calls[3].section !== "margin" || !calls[3].forceRefresh) {{
                throw new Error("failed pull refresh should still target only the active tab");
              }}
              if (stopPullDownRefreshCount !== 2) {{
                throw new Error("pull refresh should stop even when refresh fails");
              }}
              if (!page.data.activeSectionState.loaded || page.data.activeSectionState.error !== "cloud failed") {{
                throw new Error("failed pull refresh should keep page state recoverable");
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

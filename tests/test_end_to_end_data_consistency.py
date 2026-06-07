import json
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime
from pathlib import Path

from api import upload_payload
from src import beijing_real_estate_market_pulse, security_market_pulse
from tests.test_get_dashboard_section_cloudfunction import call_handle_request
from tests.test_upload_payload import (
    fixed_builder_time,
    patch_stock_names,
    seed_full_market_database,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = PROJECT_ROOT / "miniprogram"
SECTION_FIELDS = {
    "ashare": {
        "indexDeviation": ("indexDeviation",),
        "margin": ("margin",),
        "turnover": ("turnover",),
        "topConcentration": ("topConcentration",),
    },
    "beijing": {
        "houseViewPeople": ("houseViewPeopleByWeekday",),
        "decreaseRatio": ("decreaseRatio",),
        "lianjiaDeals": ("lianjiaDealsByWeekday",),
        "onlineSignings": ("dailyOnlineSignings", "monthlyOnlineSignings"),
        "credit": (
            "creditYoy",
            "loanNetIncreaseByMonth",
            "totalLoanNetIncreaseByMonth",
        ),
    },
}


class EndToEndDataConsistencyTest(unittest.TestCase):
    def test_generated_html_staged_json_cloud_sections_and_pages_stay_consistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            db_path = seed_full_market_database(temp_root)
            output_dir = temp_root / "payload"
            html_dir = temp_root / "html"
            fixed_now = datetime(2026, 6, 6, 9, 30, 0)

            with fixed_builder_time(fixed_now), patch_stock_names():
                expected_payloads = self.build_payloads(db_path)
                html_paths = self.generate_html(expected_payloads, html_dir)
                payload_paths = upload_payload.generate_payload_files(
                    db_path=str(db_path),
                    start_date="2024-01-01",
                    output_dir=str(output_dir),
                )

            self.assert_html_payloads(html_paths, expected_payloads)
            staged_payloads = {
                dashboard_type: json.loads(path.read_text(encoding="utf-8"))
                for dashboard_type, path in payload_paths.items()
            }
            self.assertEqual(staged_payloads, expected_payloads)

            storage = self.load_staged_storage(output_dir)
            section_responses = self.read_all_cloud_sections(storage)
            self.assert_cloud_sections_match_payloads(section_responses, expected_payloads)

            ashare_page = render_page_with_sections(
                MINIPROGRAM_ROOT / "pages" / "ashare" / "index.js",
                section_responses["ashare"],
            )
            beijing_page = render_page_with_sections(
                MINIPROGRAM_ROOT / "pages" / "beijing" / "index.js",
                section_responses["beijing"],
            )

            self.assert_page_sections_match_cloud(ashare_page, section_responses["ashare"])
            self.assert_page_sections_match_cloud(beijing_page, section_responses["beijing"])
            self.assert_ashare_rendered_values(ashare_page, expected_payloads["ashare"])
            self.assert_beijing_rendered_values(beijing_page, expected_payloads["beijing"])

    def build_payloads(self, db_path):
        conn = upload_payload.open_connection(str(db_path))
        try:
            return {
                "ashare": security_market_pulse.build_dashboard_payload(conn, "2024-01-01"),
                "beijing": beijing_real_estate_market_pulse.build_dashboard_payload(
                    conn,
                    "2024-01-01",
                ),
            }
        finally:
            conn.close()

    def generate_html(self, payloads, output_dir):
        return {
            "ashare": security_market_pulse.generate_html(
                payloads["ashare"],
                str(output_dir),
                "ashare.html",
            ),
            "beijing": beijing_real_estate_market_pulse.generate_html(
                payloads["beijing"],
                str(output_dir),
                "beijing.html",
            ),
        }

    def assert_html_payloads(self, html_paths, payloads):
        for dashboard_type, html_path in html_paths.items():
            payload_json = json.dumps(
                payloads[dashboard_type],
                ensure_ascii=False,
                allow_nan=False,
            )
            html_text = html_path.read_text(encoding="utf-8")
            self.assertIn(f"const payload = {payload_json};", html_text)

    def load_staged_storage(self, output_dir):
        staged_dir = output_dir / upload_payload.PAYLOAD_PREFIX
        return {
            f"{upload_payload.PAYLOAD_PREFIX}/{path.name}": json.loads(
                path.read_text(encoding="utf-8")
            )
            for path in staged_dir.glob("*.json")
        }

    def read_all_cloud_sections(self, storage):
        responses = {}
        for dashboard_type, section_fields in SECTION_FIELDS.items():
            responses[dashboard_type] = {}
            for section in section_fields:
                response = call_handle_request(
                    event={"type": dashboard_type, "section": section},
                    wx_context={"OPENID": "step-22-test-openid"},
                    storage=storage,
                )
                self.assertEqual(set(response), {"type", "section", "data"})
                responses[dashboard_type][section] = response
        return responses

    def assert_cloud_sections_match_payloads(self, responses, payloads):
        for dashboard_type, section_fields in SECTION_FIELDS.items():
            payload = payloads[dashboard_type]
            for section, fields in section_fields.items():
                expected_data = (
                    payload[fields[0]]
                    if len(fields) == 1
                    else {field: payload[field] for field in fields}
                )
                response = responses[dashboard_type][section]
                self.assertEqual(response["type"], dashboard_type)
                self.assertEqual(response["section"], section)
                self.assertEqual(response["data"], expected_data)

    def assert_page_sections_match_cloud(self, page_data, responses):
        self.assertEqual(set(page_data["sectionStates"]), set(responses))
        for section, response in responses.items():
            state = page_data["sectionStates"][section]
            self.assertTrue(state["loaded"])
            self.assertEqual(state["error"], "")
            self.assertEqual(state["data"], response["data"])

    def assert_ashare_rendered_values(self, page_data, payload):
        states = page_data["sectionStates"]

        index_points = chart_points(states["indexDeviation"]["chartCards"])
        expected_index_points = sorted(
            (row["date"], row["deviation"]) for row in payload["indexDeviation"]
        )
        self.assertEqual(sorted(index_points), expected_index_points)

        margin_cards = states["margin"]["chartCards"]
        self.assertEqual(
            margin_cards[0]["ec"]["option"]["series"][0]["data"],
            [[row["date"], row["marginBalance100m"]] for row in payload["margin"]],
        )
        self.assertEqual(
            margin_cards[1]["ec"]["option"]["series"][0]["data"],
            [[row["date"], row["marginToMarketCap"]] for row in payload["margin"]],
        )

        turnover_series = states["turnover"]["chartCards"][0]["ec"]["option"]["series"]
        self.assertEqual(
            turnover_series[0]["data"],
            [[row["date"], row["totalAmount100m"]] for row in payload["turnover"]],
        )
        self.assertEqual(
            turnover_series[1]["data"],
            [[row["date"], row["hs300Close"]] for row in payload["turnover"]],
        )

        concentration_state = states["topConcentration"]
        self.assertEqual(
            concentration_state["chartCards"][0]["ec"]["option"]["series"][0]["data"],
            [[row["date"], row["value"]] for row in payload["topConcentration"]["chart"]],
        )
        self.assertEqual(
            [table["date"] for table in concentration_state["topStockTables"]],
            [table["date"] for table in payload["topConcentration"]["recentTables"]],
        )

    def assert_beijing_rendered_values(self, page_data, payload):
        states = page_data["sectionStates"]

        self.assertEqual(
            sorted(chart_points(states["houseViewPeople"]["chartCards"])),
            sorted((row["label"], row["value"]) for row in payload["houseViewPeopleByWeekday"]),
        )
        self.assertEqual(
            states["decreaseRatio"]["chartCards"][0]["ec"]["option"]["series"][0]["data"],
            [[row["label"], row["value"]] for row in payload["decreaseRatio"]],
        )
        self.assertEqual(
            sorted(chart_points(states["lianjiaDeals"]["chartCards"])),
            sorted((row["label"], row["value"]) for row in payload["lianjiaDealsByWeekday"]),
        )

        signing_cards = states["onlineSignings"]["chartCards"]
        self.assertEqual(
            signing_cards[0]["ec"]["option"]["series"][0]["data"],
            [[row["label"], row["value"]] for row in payload["dailyOnlineSignings"]],
        )
        self.assertEqual(
            signing_cards[1]["ec"]["option"]["series"][0]["data"],
            [[row["label"], row["value"]] for row in payload["monthlyOnlineSignings"]],
        )

        credit_groups = states["credit"]["creditChartGroups"]
        self.assertEqual(
            credit_groups["creditYoy"][0]["ec"]["option"]["series"][0]["data"],
            [[row["label"], row["value"]] for row in payload["creditYoy"]],
        )
        self.assertEqual(
            sorted(chart_points(credit_groups["loanNetIncreaseByMonth"])),
            sorted(
                (row["label"], row["value"])
                for row in payload["loanNetIncreaseByMonth"]
            ),
        )
        self.assertEqual(
            sorted(chart_points(credit_groups["totalLoanNetIncreaseByMonth"])),
            sorted(
                (row["label"], row["value"])
                for row in payload["totalLoanNetIncreaseByMonth"]
            ),
        )


def chart_points(chart_cards):
    points = []
    for chart_card in chart_cards:
        for series in chart_card["ec"]["option"]["series"]:
            points.extend(tuple(point) for point in series["data"])
    return points


def render_page_with_sections(page_path, responses):
    auth_path = MINIPROGRAM_ROOT / "utils" / "auth.js"
    request_path = MINIPROGRAM_ROOT / "utils" / "request.js"
    script = textwrap.dedent(
        """
        const pagePath = process.argv[1];
        const responses = JSON.parse(process.argv[2]);
        const authPath = require.resolve(process.argv[3]);
        const requestPath = require.resolve(process.argv[4]);
        const pageResolved = require.resolve(pagePath);

        delete require.cache[pageResolved];
        require.cache[authPath] = {
          id: authPath,
          filename: authPath,
          loaded: true,
          exports: {
            getLoginState() { return { loggedIn: true }; },
            loginWithUserInfo() { return Promise.resolve({ loggedIn: true }); }
          }
        };
        require.cache[requestPath] = {
          id: requestPath,
          filename: requestPath,
          loaded: true,
          exports: {
            requestDashboardSection(type, section) {
              const response = responses[section];
              if (!response || response.type !== type) {
                return Promise.reject(new Error(`missing response for ${type}.${section}`));
              }
              return Promise.resolve(response);
            }
          }
        };

        function applySetData(target, updates) {
          Object.keys(updates).forEach((key) => {
            const parts = key.split('.');
            let cursor = target.data;
            for (let index = 0; index < parts.length - 1; index += 1) {
              cursor = cursor[parts[index]];
            }
            cursor[parts[parts.length - 1]] = updates[key];
          });
        }

        let page = null;
        global.Page = (config) => {
          page = config;
          page.data = JSON.parse(JSON.stringify(config.data));
          page.setData = (updates) => applySetData(page, updates);
        };
        require(pageResolved);

        (async () => {
          await page.onLoad();
          for (const section of Object.keys(responses)) {
            if (section !== page.data.activeTab) {
              await page.onTapTab({ currentTarget: { dataset: { key: section } } });
            }
          }
          process.stdout.write(JSON.stringify(page.data));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )
    result = subprocess.run(
        [
            "node",
            "-e",
            script,
            str(page_path),
            json.dumps(responses, ensure_ascii=False),
            str(auth_path),
            str(request_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()

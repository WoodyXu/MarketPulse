import json
import subprocess
import textwrap
import unittest
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_FUNCTION_PATH = PROJECT_ROOT / "api" / "cloudfunctions" / "getDashboardSection" / "index.js"


class GetDashboardSectionCloudFunctionTest(unittest.TestCase):
    def test_missing_openid_returns_handled_auth_error(self):
        response = call_handle_request(
            event={"type": "ashare", "section": "turnover"},
            wx_context={},
        )

        self.assertEqual(set(response), {"type", "section", "error"})
        self.assertEqual(response["type"], "ashare")
        self.assertEqual(response["section"], "turnover")
        self.assertEqual(response["error"]["code"], "UNAUTHENTICATED")
        self.assertIn("请先登录", response["error"]["message"])

    def test_existing_openid_reads_latest_payload_from_manifest_when_date_is_omitted(self):
        storage = build_storage_payloads()
        response = call_handle_request(
            event={"type": "ashare", "section": "turnover"},
            wx_context={"OPENID": "test-openid"},
            storage=storage,
        )

        self.assertEqual(set(response), {"type", "section", "data"})
        self.assertEqual(response["type"], "ashare")
        self.assertEqual(response["section"], "turnover")
        self.assertEqual(response["data"], SAMPLE_PAYLOADS["ashare"]["turnover"])

    def test_existing_openid_reads_exact_requested_payload_date(self):
        storage = build_storage_payloads()
        response = call_handle_request(
            event={"type": "ashare", "section": "turnover", "date": "2024-03-01"},
            wx_context={"OPENID": "test-openid"},
            storage=storage,
        )

        self.assertEqual(set(response), {"type", "section", "data"})
        self.assertEqual(response["data"], [{"date": "2024-03-01", "totalAmount100m": 100}])

    def test_missing_requested_date_falls_back_to_nearest_manifest_date(self):
        storage = build_storage_payloads()
        response = call_handle_request(
            event={"type": "ashare", "section": "turnover", "date": "2024-03-05"},
            wx_context={"OPENID": "test-openid"},
            storage=storage,
        )

        self.assertEqual(set(response), {"type", "section", "data"})
        self.assertEqual(response["data"], [{"date": "2024-03-01", "totalAmount100m": 100}])

    def test_all_whitelisted_sections_return_cropped_data(self):
        cases = [
            ("ashare", "indexDeviation", [{"date": "2024-03-01", "deviation": 0.01}]),
            ("ashare", "margin", [{"date": "2024-03-01", "marginBalance100m": 100}]),
            ("ashare", "turnover", [{"date": "2024-03-01", "totalAmount100m": 200}]),
            (
                "ashare",
                "topConcentration",
                {"chart": [{"date": "2024-03-01", "value": 0.2}], "recentTables": []},
            ),
            ("beijing", "houseViewPeople", [{"x": "2024-03-01", "value": 300}]),
            ("beijing", "decreaseRatio", [{"x": "2024-03-01", "value": 2}]),
            ("beijing", "lianjiaDeals", [{"x": "2024-03-01", "value": 100}]),
            (
                "beijing",
                "onlineSignings",
                {
                    "dailyOnlineSignings": [{"x": "2024-03-01", "value": 10}],
                    "monthlyOnlineSignings": [{"x": "2024-03-01", "value": 300}],
                },
            ),
            (
                "beijing",
                "credit",
                {
                    "creditYoy": [{"x": "2024-03-01", "value": 0.1}],
                    "loanNetIncreaseByMonth": [{"x": 2024, "month": 3, "value": 20}],
                    "totalLoanNetIncreaseByMonth": [{"x": 2024, "month": 3, "value": 60}],
                },
            ),
        ]

        for dashboard_type, section, expected_data in cases:
            with self.subTest(dashboard_type=dashboard_type, section=section):
                response = call_handle_request(
                    event={"type": dashboard_type, "section": section, "date": "2024-03-10"},
                    wx_context={"OPENID": "test-openid"},
                    payload=SAMPLE_PAYLOADS[dashboard_type],
                )

                self.assertEqual(set(response), {"type", "section", "data"})
                self.assertEqual(response["type"], dashboard_type)
                self.assertEqual(response["section"], section)
                self.assertEqual(response["data"], expected_data)

    def test_invalid_type_or_section_returns_error_without_payload_data(self):
        for event in [
            {"type": "unknown", "section": "turnover"},
            {"type": "ashare", "section": "dailyOnlineSignings"},
            {"type": "beijing", "section": "topConcentration"},
        ]:
            with self.subTest(event=event):
                response = call_handle_request(
                    event=event,
                    wx_context={"OPENID": "test-openid"},
                    payload=SAMPLE_PAYLOADS["ashare"],
                )

                self.assertEqual(set(response), {"type", "section", "error"})
                self.assertEqual(response["error"]["code"], "INVALID_SECTION")
                self.assertNotIn("data", response)

    def test_missing_required_payload_field_returns_handled_error(self):
        response = call_handle_request(
            event={"type": "beijing", "section": "onlineSignings"},
            wx_context={"OPENID": "test-openid"},
            payload={"dailyOnlineSignings": []},
        )

        self.assertEqual(set(response), {"type", "section", "error"})
        self.assertEqual(response["type"], "beijing")
        self.assertEqual(response["section"], "onlineSignings")
        self.assertEqual(response["error"]["code"], "SECTION_DATA_MISSING")

    def test_success_response_excludes_storage_metadata_and_full_payload_fields(self):
        storage = build_storage_payloads()
        storage["marketpulse-payload/manifest.json"]["dashboards"]["ashare"][
            "fileID"
        ] = "cloud://secret-env.marketpulse-payload/ashare_2024-03-10.json"
        storage["marketpulse-payload/manifest.json"]["dashboards"]["ashare"][
            "downloadCredential"
        ] = "secret-download-token"
        response = call_handle_request(
            event={"type": "ashare", "section": "turnover"},
            wx_context={"OPENID": "test-openid"},
            storage=storage,
        )

        self.assertEqual(set(response), {"type", "section", "data"})
        response_text = json.dumps(response, ensure_ascii=False)
        self.assertNotIn("marketpulse-payload", response_text)
        self.assertNotIn("fileID", response_text)
        self.assertNotIn("downloadCredential", response_text)
        self.assertNotIn("generatedAt", response_text)
        self.assertNotIn("startDate", response_text)
        self.assertNotIn("indexDeviation", response_text)
        self.assertNotIn("margin", response_text)
        self.assertNotIn("topConcentration", response_text)

    def test_request_parameters_cannot_bypass_section_cropping(self):
        response = call_handle_request(
            event={
                "type": "ashare",
                "section": "turnover",
                "fields": ["generatedAt", "margin", "topConcentration"],
                "includeFullPayload": True,
                "fileID": "marketpulse-payload/ashare_2024-03-10.json",
            },
            wx_context={"OPENID": "test-openid"},
            payload=SAMPLE_PAYLOADS["ashare"],
        )

        self.assertEqual(set(response), {"type", "section", "data"})
        self.assertEqual(response["data"], SAMPLE_PAYLOADS["ashare"]["turnover"])
        response_text = json.dumps(response, ensure_ascii=False)
        self.assertNotIn("generatedAt", response_text)
        self.assertNotIn("marginBalance100m", response_text)
        self.assertNotIn("topConcentration", response_text)


SAMPLE_PAYLOADS = {
    "ashare": {
        "generatedAt": "2024-03-10 12:00:00",
        "startDate": "2024-01-01",
        "indexDeviation": [{"date": "2024-03-01", "deviation": 0.01}],
        "margin": [{"date": "2024-03-01", "marginBalance100m": 100}],
        "turnover": [{"date": "2024-03-01", "totalAmount100m": 200}],
        "topConcentration": {
            "chart": [{"date": "2024-03-01", "value": 0.2}],
            "recentTables": [],
        },
    },
    "beijing": {
        "generatedAt": "2024-03-10 12:00:00",
        "startDate": "2024-01-01",
        "startMonth": "2024-01",
        "houseViewPeopleByWeekday": [{"x": "2024-03-01", "value": 300}],
        "lianjiaDealsByWeekday": [{"x": "2024-03-01", "value": 100}],
        "decreaseRatio": [{"x": "2024-03-01", "value": 2}],
        "dailyOnlineSignings": [{"x": "2024-03-01", "value": 10}],
        "monthlyOnlineSignings": [{"x": "2024-03-01", "value": 300}],
        "creditYoy": [{"x": "2024-03-01", "value": 0.1}],
        "loanNetIncreaseByMonth": [{"x": 2024, "month": 3, "value": 20}],
        "totalLoanNetIncreaseByMonth": [{"x": 2024, "month": 3, "value": 60}],
        "weekdayOrder": ["周一", "周二", "周三", "周四", "周五", "周末"],
    },
}


def build_storage_payloads() -> dict:
    ashare_older = dict(SAMPLE_PAYLOADS["ashare"])
    ashare_older["turnover"] = [{"date": "2024-03-01", "totalAmount100m": 100}]

    return {
        "marketpulse-payload/manifest.json": {
            "payloadPrefix": "marketpulse-payload",
            "dashboards": {
                "ashare": {
                    "latestDate": "2024-03-10",
                    "latestFile": "marketpulse-payload/ashare_2024-03-10.json",
                    "availableDates": ["2024-03-01", "2024-03-10"],
                    "files": {
                        "2024-03-01": "marketpulse-payload/ashare_2024-03-01.json",
                        "2024-03-10": "marketpulse-payload/ashare_2024-03-10.json",
                    },
                },
                "beijing": {
                    "latestDate": "2024-02-01",
                    "latestFile": "marketpulse-payload/beijing_2024-02-01.json",
                    "availableDates": ["2024-02-01"],
                    "files": {
                        "2024-02-01": "marketpulse-payload/beijing_2024-02-01.json",
                    },
                },
            },
        },
        "marketpulse-payload/ashare_2024-03-01.json": ashare_older,
        "marketpulse-payload/ashare_2024-03-10.json": SAMPLE_PAYLOADS["ashare"],
        "marketpulse-payload/beijing_2024-02-01.json": SAMPLE_PAYLOADS["beijing"],
    }


def call_handle_request(
    event: dict,
    wx_context: dict,
    payload: Optional[dict] = None,
    storage: Optional[dict] = None,
) -> dict:
    script = textwrap.dedent(
        """
        const cloudFunction = require(process.argv[1]);
        const event = JSON.parse(process.argv[2]);
        const wxContext = JSON.parse(process.argv[3]);
        const payload = JSON.parse(process.argv[4]);
        const storage = JSON.parse(process.argv[5]);
        const cloudRuntime = {
          getWXContext: () => wxContext
        };
        const options = {};
        if (payload !== null) {
          options.payloadReader = async () => payload;
        }
        if (storage !== null) {
          options.storageReader = async (cloudPath) => {
            if (!Object.prototype.hasOwnProperty.call(storage, cloudPath)) {
              throw new Error(`missing storage object: ${cloudPath}`);
            }
            return storage[cloudPath];
          };
        }

        cloudFunction.handleRequest(event, {}, cloudRuntime, options)
          .then((result) => {
            process.stdout.write(JSON.stringify(result));
          })
          .catch((error) => {
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
            str(CLOUD_FUNCTION_PATH),
            json.dumps(event),
            json.dumps(wx_context),
            json.dumps(payload),
            json.dumps(storage),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()

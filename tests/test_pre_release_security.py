import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLOUD_FUNCTION_PATH = REPO_ROOT / "api" / "cloudfunctions" / "getDashboardSection" / "index.js"


class PreReleaseSecurityTest(unittest.TestCase):
    def test_private_inputs_and_generated_payloads_are_ignored(self):
        sensitive_paths = [
            ".env",
            "data/market_data.sqlite",
            "data/market_data.sqlite-wal",
            "project.private.config.json",
            "api/payload/marketpulse-payload/manifest.json",
            "api/payload/marketpulse-payload/ashare_2026-06-07.json",
        ]

        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=REPO_ROOT,
            input="\n".join(sensitive_paths),
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(set(result.stdout.splitlines()), set(sensitive_paths))

    def test_tracked_files_exclude_private_data_and_credentials(self):
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        tracked_files = set(result.stdout.splitlines())
        forbidden_suffixes = (
            ".sqlite",
            ".sqlite-wal",
            ".sqlite-shm",
            ".db",
            ".db-wal",
            ".db-shm",
            ".pem",
            ".key",
        )

        self.assertNotIn(".env", tracked_files)
        self.assertNotIn("project.private.config.json", tracked_files)
        self.assertFalse(
            any(path.startswith("api/payload/") for path in tracked_files),
            tracked_files,
        )
        self.assertFalse(
            any(path.lower().endswith(forbidden_suffixes) for path in tracked_files),
            tracked_files,
        )

        env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertEqual(env_example.strip(), "TUSHARE_TOKEN=")

    def test_miniprogram_package_has_no_storage_or_backend_credentials(self):
        forbidden_text = [
            "marketpulse-payload",
            "downloadfile",
            "fileid",
            "tushare_token",
            ".sqlite",
            "cloud://",
            "downloadcredential",
        ]

        for path in (REPO_ROOT / "miniprogram").rglob("*"):
            if not path.is_file() or path.name == "echarts.js":
                continue
            content = path.read_text(encoding="utf-8").lower()
            for marker in forbidden_text:
                self.assertNotIn(marker, content, f"{marker} found in {path}")

        project_config = json.loads(
            (REPO_ROOT / "project.config.json").read_text(encoding="utf-8")
        )
        serialized_config = json.dumps(project_config, ensure_ascii=False).lower()
        for marker in ["env-id", "secret", "token", "credential", "cloud://"]:
            self.assertNotIn(marker, serialized_config)

    def test_all_cloud_function_response_samples_exclude_sensitive_metadata(self):
        responses = call_all_section_samples()
        self.assertEqual(len(responses), 10)

        for response in responses[:9]:
            self.assertEqual(set(response), {"type", "section", "data"})

        error_response = responses[9]
        self.assertEqual(set(error_response), {"type", "section", "error"})
        self.assertEqual(error_response["error"]["code"], "INVALID_SECTION")

        response_text = json.dumps(responses, ensure_ascii=False).lower()
        for marker in [
            "marketpulse-payload",
            "fileid",
            "downloadcredential",
            "secret-download-token",
            "cloud://",
            "generatedat",
            "startdate",
            "tushare_token",
        ]:
            self.assertNotIn(marker, response_text)


def call_all_section_samples() -> list[dict]:
    script = textwrap.dedent(
        """
        const cloudFunction = require(process.argv[1]);
        const payloads = {
          ashare: {
            generatedAt: "2026-06-07 12:00:00",
            startDate: "2024-01-01",
            fileID: "cloud://secret-env/marketpulse-payload/ashare.json",
            downloadCredential: "secret-download-token",
            indexDeviation: [{ date: "2026-06-06", deviation: 0.01 }],
            margin: [{ date: "2026-06-06", marginBalance100m: 100 }],
            turnover: [{ date: "2026-06-06", totalAmount100m: 200 }],
            topConcentration: {
              chart: [{ date: "2026-06-06", value: 0.2 }],
              recentTables: []
            }
          },
          beijing: {
            generatedAt: "2026-06-07 12:00:00",
            startDate: "2024-01-01",
            fileID: "cloud://secret-env/marketpulse-payload/beijing.json",
            downloadCredential: "secret-download-token",
            houseViewPeopleByWeekday: [{ x: "2026-06-06", value: 300 }],
            decreaseRatio: [{ x: "2026-06-06", value: 2 }],
            lianjiaDealsByWeekday: [{ x: "2026-06-06", value: 100 }],
            dailyOnlineSignings: [{ x: "2026-06-06", value: 10 }],
            monthlyOnlineSignings: [{ x: "2026-06-01", value: 300 }],
            creditYoy: [{ x: "2026-06-01", value: 0.1 }],
            loanNetIncreaseByMonth: [{ x: 2026, month: 6, value: 20 }],
            totalLoanNetIncreaseByMonth: [{ x: 2026, month: 6, value: 60 }]
          }
        };
        const cases = [
          ["ashare", "indexDeviation"],
          ["ashare", "margin"],
          ["ashare", "turnover"],
          ["ashare", "topConcentration"],
          ["beijing", "houseViewPeople"],
          ["beijing", "decreaseRatio"],
          ["beijing", "lianjiaDeals"],
          ["beijing", "onlineSignings"],
          ["beijing", "credit"]
        ];
        const cloudRuntime = {
          getWXContext: () => ({ OPENID: "security-test-openid" })
        };

        Promise.all(cases.map(([type, section]) => (
          cloudFunction.handleRequest(
            { type, section },
            {},
            cloudRuntime,
            { payloadReader: async () => payloads[type] }
          )
        ))).then(async (responses) => {
          responses.push(await cloudFunction.handleRequest(
            {
              type: "ashare",
              section: "unknown",
              fileID: "cloud://secret-env/marketpulse-payload/ashare.json",
              downloadCredential: "secret-download-token",
              includeFullPayload: true
            },
            {},
            cloudRuntime,
            { payloadReader: async () => payloads.ashare }
          ));
          process.stdout.write(JSON.stringify(responses));
        }).catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )
    result = subprocess.run(
        ["node", "-e", script, str(CLOUD_FUNCTION_PATH)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()

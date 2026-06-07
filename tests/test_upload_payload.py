import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from api import upload_payload
from src import beijing_real_estate_market_pulse, security_market_pulse
from src.beijing_real_estate_market_pulse import build_dashboard_payload as build_beijing_payload
from src.security_market_pulse import build_dashboard_payload as build_ashare_payload
from src.security_market_pulse import init_db as init_ashare_db
from tests.test_payload_contract import (
    create_beijing_schema,
    seed_ashare_rows,
    seed_beijing_rows,
    seed_index_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UploadPayloadTest(unittest.TestCase):
    def test_cli_prefers_this_repository_when_pythonpath_contains_conflicting_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            conflicting_root = tmp_path / "conflicting-project"
            conflicting_config = conflicting_root / "config"
            conflicting_config.mkdir(parents=True)
            (conflicting_config / "__init__.py").write_text("", encoding="utf-8")
            (conflicting_config / "consts.py").write_text(
                'raise RuntimeError("loaded conflicting config")\n',
                encoding="utf-8",
            )

            db_path = seed_full_market_database(tmp_path)
            output_dir = tmp_path / "payload"
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [str(conflicting_root), str(PROJECT_ROOT)]
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "api" / "upload_payload.py"),
                    "--db-path",
                    str(db_path),
                    "--start-date",
                    "2024-01-01",
                    "--output-dir",
                    str(output_dir),
                    "--type",
                    "beijing",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (output_dir / "marketpulse-payload" / "beijing_2024-02-01.json").exists()
            )

    def test_generates_payload_json_matching_existing_builders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = seed_full_market_database(Path(tmpdir))
            output_dir = Path(tmpdir) / "payload"
            fixed_now = datetime(2026, 6, 5, 9, 30, 0)

            with fixed_builder_time(fixed_now), patch_stock_names():
                conn = upload_payload.open_connection(str(db_path))
                try:
                    expected_ashare = build_ashare_payload(conn, "2024-01-01")
                    expected_beijing = build_beijing_payload(conn, "2024-01-01")
                finally:
                    conn.close()

                output_paths = upload_payload.generate_payload_files(
                    db_path=str(db_path),
                    start_date="2024-01-01",
                    output_dir=str(output_dir),
                )

            self.assertEqual(set(output_paths), {"ashare", "beijing"})
            self.assertEqual(output_paths["ashare"].name, "ashare_2024-03-10.json")
            self.assertEqual(output_paths["beijing"].name, "beijing_2024-02-01.json")
            self.assertEqual(output_paths["ashare"].parent.name, "marketpulse-payload")
            self.assertEqual(output_paths["beijing"].parent.name, "marketpulse-payload")

            ashare_payload = json.loads(output_paths["ashare"].read_text(encoding="utf-8"))
            beijing_payload = json.loads(output_paths["beijing"].read_text(encoding="utf-8"))
            self.assertEqual(ashare_payload, expected_ashare)
            self.assertEqual(beijing_payload, expected_beijing)

            json.dumps(ashare_payload, ensure_ascii=False, allow_nan=False)
            json.dumps(beijing_payload, ensure_ascii=False, allow_nan=False)

            manifest_path = output_dir / "marketpulse-payload" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["payloadPrefix"], "marketpulse-payload")
            self.assertEqual(
                manifest["dashboards"]["ashare"]["latestFile"],
                "marketpulse-payload/ashare_2024-03-10.json",
            )
            self.assertEqual(manifest["dashboards"]["ashare"]["latestDate"], "2024-03-10")
            self.assertEqual(manifest["dashboards"]["ashare"]["availableDates"], ["2024-03-10"])
            self.assertEqual(
                manifest["dashboards"]["beijing"]["latestFile"],
                "marketpulse-payload/beijing_2024-02-01.json",
            )
            self.assertEqual(manifest["dashboards"]["beijing"]["latestDate"], "2024-02-01")
            self.assertEqual(manifest["dashboards"]["beijing"]["availableDates"], ["2024-02-01"])

    def test_target_date_must_match_latest_business_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = seed_full_market_database(Path(tmpdir))
            with fixed_builder_time(datetime(2026, 6, 5, 9, 30, 0)), patch_stock_names():
                with self.assertRaisesRegex(ValueError, "与 --date 2024-01-01 不一致"):
                    upload_payload.generate_payload_files(
                        db_path=str(db_path),
                        start_date="2024-01-01",
                        output_dir=str(Path(tmpdir) / "payload"),
                        payload_types=["ashare"],
                        target_date="2024-01-01",
                    )

    def test_manifest_preserves_existing_dates_and_updates_latest_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "payload"
            staged_dir = output_dir / "marketpulse-payload"
            staged_dir.mkdir(parents=True)
            manifest_path = staged_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "generatedAt": "2026-06-01 00:00:00",
                        "payloadPrefix": "marketpulse-payload",
                        "dashboards": {
                            "ashare": {
                                "latestDate": "2024-03-01",
                                "latestFile": "marketpulse-payload/ashare_2024-03-01.json",
                                "availableDates": ["2024-03-01"],
                                "files": {
                                    "2024-03-01": "marketpulse-payload/ashare_2024-03-01.json"
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            new_payload_path = staged_dir / "ashare_2024-03-10.json"
            new_payload_path.write_text("{}", encoding="utf-8")

            upload_payload.write_manifest(str(output_dir), {"ashare": new_payload_path})

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            ashare_manifest = manifest["dashboards"]["ashare"]
            self.assertEqual(ashare_manifest["latestDate"], "2024-03-10")
            self.assertEqual(
                ashare_manifest["latestFile"],
                "marketpulse-payload/ashare_2024-03-10.json",
            )
            self.assertEqual(ashare_manifest["availableDates"], ["2024-03-01", "2024-03-10"])
            self.assertEqual(
                ashare_manifest["files"]["2024-03-01"],
                "marketpulse-payload/ashare_2024-03-01.json",
            )
            self.assertEqual(
                ashare_manifest["files"]["2024-03-10"],
                "marketpulse-payload/ashare_2024-03-10.json",
            )

    def test_upload_command_uploads_payloads_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload_dir = Path(tmpdir)
            ashare_path = payload_dir / "ashare_2024-03-10.json"
            beijing_path = payload_dir / "beijing_2024-02-01.json"
            manifest_path = payload_dir / "manifest.json"
            ashare_path.write_text("{}", encoding="utf-8")
            beijing_path.write_text("{}", encoding="utf-8")
            manifest_path.write_text("{}", encoding="utf-8")

            with patch.object(upload_payload.subprocess, "run") as run_mock:
                upload_payload.upload_staged_files(
                    payload_paths={"ashare": ashare_path, "beijing": beijing_path},
                    manifest_path=manifest_path,
                    upload_command="wx-cloud-upload --env {env_id} {local_path} {cloud_path}",
                    env_id="test-env",
                )

            commands = [call.args[0] for call in run_mock.call_args_list]
            self.assertEqual(
                commands,
                [
                    [
                        "wx-cloud-upload",
                        "--env",
                        "test-env",
                        str(ashare_path),
                        "marketpulse-payload/ashare_2024-03-10.json",
                    ],
                    [
                        "wx-cloud-upload",
                        "--env",
                        "test-env",
                        str(beijing_path),
                        "marketpulse-payload/beijing_2024-02-01.json",
                    ],
                    [
                        "wx-cloud-upload",
                        "--env",
                        "test-env",
                        str(manifest_path),
                        "marketpulse-payload/manifest.json",
                    ],
                ],
            )
            for call in run_mock.call_args_list:
                self.assertTrue(call.kwargs["check"])


def seed_full_market_database(tmpdir: Path) -> Path:
    db_path = tmpdir / "market_data.sqlite"
    conn = init_ashare_db(str(db_path))
    try:
        seed_index_rows(conn)
        seed_ashare_rows(conn)
    finally:
        conn.close()

    create_beijing_schema(db_path)
    conn = beijing_real_estate_market_pulse.init_db(str(db_path))
    try:
        seed_beijing_rows(conn)
    finally:
        conn.close()
    return db_path


@contextmanager
def fixed_builder_time(fixed_now: datetime):
    with patch.object(security_market_pulse, "datetime", FixedDateTime(fixed_now)):
        with patch.object(beijing_real_estate_market_pulse, "datetime", FixedDateTime(fixed_now)):
            yield


class FixedDateTime:
    def __init__(self, fixed_now: datetime) -> None:
        self._fixed_now = fixed_now

    def now(self) -> datetime:
        return self._fixed_now


def patch_stock_names():
    return patch.object(
        security_market_pulse,
        "fetch_ashare_stock_code_name_from_akshare",
        return_value="测试股票",
    )


if __name__ == "__main__":
    unittest.main()

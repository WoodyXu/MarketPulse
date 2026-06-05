"""Generate and stage dashboard JSON payloads for the WeChat mini program."""

import argparse
import json
import logging
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.consts import DB_PATH, START_DATE  # noqa: E402
from src import beijing_real_estate_market_pulse, security_market_pulse  # noqa: E402


LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT_DIR = "api/payload"
PAYLOAD_PREFIX = "marketpulse-payload"
MANIFEST_NAME = "manifest.json"
PAYLOAD_TYPES = ("ashare", "beijing")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 MarketPulse 小程序 payload JSON")
    parser.add_argument("--start-date", default=START_DATE, help="图表起始日期，格式 YYYY-MM-DD")
    parser.add_argument("--date", help="目标业务日期，格式 YYYY-MM-DD；不传则使用 payload 最新业务日期")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="本地 JSON 输出目录")
    parser.add_argument(
        "--type",
        choices=PAYLOAD_TYPES,
        action="append",
        dest="payload_types",
        help="只生成指定 payload 类型；可重复传入。默认生成全部类型",
    )
    parser.add_argument("--env-id", help="云环境 ID；传给可选上传命令")
    parser.add_argument(
        "--upload-command",
        help=(
            "可选上传命令模板。支持 {local_path}、{cloud_path}、{env_id} 占位符；"
            "未提供时仅生成本地云存储目录和 manifest"
        ),
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def validate_date(date_text: str) -> None:
    datetime.strptime(date_text, "%Y-%m-%d")


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def open_connection(db_path: str) -> sqlite3.Connection:
    db_file = resolve_project_path(db_path)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    return conn


def build_payload(payload_type: str, conn: sqlite3.Connection, start_date: str) -> dict:
    if payload_type == "ashare":
        return security_market_pulse.build_dashboard_payload(conn, start_date)
    if payload_type == "beijing":
        return beijing_real_estate_market_pulse.build_dashboard_payload(conn, start_date)
    raise ValueError(f"不支持的 payload 类型：{payload_type}")


def iter_payload_date_values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"date", "x"} and isinstance(item, str):
                date_text = normalize_business_date(item)
                if date_text:
                    yield date_text
            else:
                yield from iter_payload_date_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_payload_date_values(item)


def normalize_business_date(value: str) -> Optional[str]:
    if not DATE_PATTERN.match(value):
        return None
    validate_date(value)
    return value


def latest_business_date(payload: dict) -> str:
    dates = [date_text for date_text in iter_payload_date_values(payload) if date_text]
    if not dates:
        raise ValueError("payload 中没有可用于文件命名的业务日期字段")
    return max(dates)


def cloud_payload_path(payload_type: str, business_date: str) -> str:
    return f"{PAYLOAD_PREFIX}/{payload_type}_{business_date}.json"


def cloud_manifest_path() -> str:
    return f"{PAYLOAD_PREFIX}/{MANIFEST_NAME}"


def local_cloud_path(output_dir: str, cloud_path: str) -> Path:
    return resolve_project_path(output_dir) / cloud_path


def write_payload_json(
    payload_type: str,
    payload: dict,
    output_dir: str,
    target_date: Optional[str] = None,
) -> Path:
    business_date = latest_business_date(payload)
    if target_date is not None and business_date != target_date:
        raise ValueError(
            f"{payload_type} payload 最新业务日期为 {business_date}，与 --date {target_date} 不一致"
        )

    output_path = local_cloud_path(output_dir, cloud_payload_path(payload_type, business_date))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True)
    output_path.write_text(payload_json + "\n", encoding="utf-8")
    return output_path


def read_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(output_dir: str, payload_paths: dict[str, Path]) -> Path:
    manifest_path = local_cloud_path(output_dir, cloud_manifest_path())
    manifest = read_manifest(manifest_path)
    dashboards = manifest.get("dashboards")
    if not isinstance(dashboards, dict):
        dashboards = {}

    for payload_type, payload_path in payload_paths.items():
        business_date = business_date_from_payload_path(payload_type, payload_path)
        cloud_path = cloud_payload_path(payload_type, business_date)
        entry = dashboards.get(payload_type)
        if not isinstance(entry, dict):
            entry = {}

        existing_dates = entry.get("availableDates")
        if not isinstance(existing_dates, list):
            existing_dates = []
        available_dates = sorted({*existing_dates, business_date})

        files = entry.get("files")
        if not isinstance(files, dict):
            files = {}
        files[business_date] = cloud_path

        latest_date = max(available_dates)
        dashboards[payload_type] = {
            "latestDate": latest_date,
            "latestFile": files[latest_date],
            "availableDates": available_dates,
            "files": {date_text: files[date_text] for date_text in available_dates},
        }

    manifest = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "payloadPrefix": PAYLOAD_PREFIX,
        "dashboards": dashboards,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_json = json.dumps(manifest, ensure_ascii=False, allow_nan=False, sort_keys=True)
    manifest_path.write_text(manifest_json + "\n", encoding="utf-8")
    return manifest_path


def business_date_from_payload_path(payload_type: str, payload_path: Path) -> str:
    match = re.match(rf"^{re.escape(payload_type)}_(\d{{4}}-\d{{2}}-\d{{2}})\.json$", payload_path.name)
    if not match:
        raise ValueError(f"无法从 payload 文件名解析业务日期：{payload_path.name}")
    business_date = match.group(1)
    validate_date(business_date)
    return business_date


def run_upload_command(
    *,
    upload_command: str,
    local_path: Path,
    cloud_path: str,
    env_id: Optional[str],
) -> None:
    command_text = upload_command.format(
        local_path=str(local_path),
        cloud_path=cloud_path,
        env_id=env_id or "",
    )
    command = shlex.split(command_text)
    if not command:
        raise ValueError("--upload-command 不能为空")
    LOGGER.info("上传 %s -> %s", local_path, cloud_path)
    subprocess.run(command, check=True)


def upload_staged_files(
    *,
    payload_paths: dict[str, Path],
    manifest_path: Path,
    upload_command: Optional[str],
    env_id: Optional[str],
) -> None:
    if not upload_command:
        LOGGER.info("未提供 --upload-command，仅生成本地云存储目录；不会输出公开下载地址")
        return

    for payload_type, payload_path in payload_paths.items():
        business_date = business_date_from_payload_path(payload_type, payload_path)
        run_upload_command(
            upload_command=upload_command,
            local_path=payload_path,
            cloud_path=cloud_payload_path(payload_type, business_date),
            env_id=env_id,
        )
    run_upload_command(
        upload_command=upload_command,
        local_path=manifest_path,
        cloud_path=cloud_manifest_path(),
        env_id=env_id,
    )


def generate_payload_files(
    *,
    db_path: str,
    start_date: str,
    output_dir: str,
    payload_types: Iterable[str] = PAYLOAD_TYPES,
    target_date: Optional[str] = None,
    upload_command: Optional[str] = None,
    env_id: Optional[str] = None,
) -> dict[str, Path]:
    output_paths: dict[str, Path] = {}
    conn = open_connection(db_path)
    try:
        for payload_type in payload_types:
            payload = build_payload(payload_type, conn, start_date)
            output_paths[payload_type] = write_payload_json(
                payload_type,
                payload,
                output_dir,
                target_date=target_date,
            )
    finally:
        conn.close()
    manifest_path = write_manifest(output_dir, output_paths)
    upload_staged_files(
        payload_paths=output_paths,
        manifest_path=manifest_path,
        upload_command=upload_command,
        env_id=env_id,
    )
    return output_paths


def main() -> int:
    args = parse_args()
    setup_logging()
    validate_date(args.start_date)
    if args.date:
        validate_date(args.date)
    if args.env_id and not args.upload_command:
        LOGGER.info("已接收云环境参数 --env-id=%s；未提供上传命令，本次仅本地生成", args.env_id)

    payload_types = args.payload_types or list(PAYLOAD_TYPES)
    output_paths = generate_payload_files(
        db_path=args.db_path,
        start_date=args.start_date,
        output_dir=args.output_dir,
        payload_types=payload_types,
        target_date=args.date,
        upload_command=args.upload_command,
        env_id=args.env_id,
    )
    for payload_type, output_path in output_paths.items():
        LOGGER.info("%s payload JSON 已生成：%s", payload_type, output_path)
        print(output_path)
    LOGGER.info("manifest 已生成：%s", local_cloud_path(args.output_dir, cloud_manifest_path()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

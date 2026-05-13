import argparse
import html
import json
import logging
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.consts import START_DATE  # noqa: E402
from config.index_code import index_dict  # noqa: E402
from src.market_daily_info import (  # noqa: E402
    REQUEST_SLEEP_SECONDS,
    fetch_index_full_from_akshare,
    fetch_sh_daily_float_mv_amount_from_sse_official,
    fetch_sh_sz_daily_float_mv_amount_from_tushare,
    fetch_sh_sz_full_margin_balance_from_akshare,
    fetch_sz_daily_float_mv_amount_from_szse_official,
    get_tushare_pro,
)

try:
    from config.consts import DB_PATH
except ImportError:
    DB_PATH = "data/market_data.sqlite"

try:
    from config.consts import DEFAULT_OUTPUT_DIR
except ImportError:
    DEFAULT_OUTPUT_DIR = "security_market_pulse"


LOGGER = logging.getLogger(__name__)
YUAN_PER_100M = 100_000_000
HS300_NAME = "A股-沪深300"


def parse_args():
    parser = argparse.ArgumentParser(description="更新市场脉搏数据并生成交互式网页")
    parser.add_argument("--start-date", default=START_DATE, help="图表起始日期，格式 YYYY-MM-DD")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="网页输出目录")
    parser.add_argument("--output-name", default="index.html", help="网页文件名")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过网络抓取，只用本地缓存生成网页")
    return parser.parse_args()


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def validate_date(date_text: str) -> None:
    datetime.strptime(date_text, "%Y-%m-%d")


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def normalize_date_text(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def today_text() -> str:
    return date.today().strftime("%Y-%m-%d")


def iter_date_texts(start_text: str, end_text: str):
    current = datetime.strptime(start_text, "%Y-%m-%d").date()
    end = datetime.strptime(end_text, "%Y-%m-%d").date()
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def init_db(db_path: str) -> sqlite3.Connection:
    db_file = resolve_project_path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ashare_daily_market_data (
            trade_date TEXT PRIMARY KEY,
            total_margin_balance_yuan REAL,
            sse_amount_yuan REAL,
            szse_amount_yuan REAL,
            sse_circulating_market_cap_yuan REAL,
            szse_circulating_market_cap_yuan REAL,
            margin_updated_at TEXT,
            sse_updated_at TEXT,
            szse_updated_at TEXT,
            sse_market_cap_updated_at TEXT,
            szse_market_cap_updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS index_daily_data (
            index_name TEXT NOT NULL,
            index_code TEXT NOT NULL,
            market_type TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            close REAL,
            high REAL,
            low REAL,
            volume REAL,
            amount REAL,
            data_source TEXT,
            data_status TEXT NOT NULL DEFAULT 'complete',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (index_code, trade_date)
        )
        """
    )
    conn.commit()
    return conn


def get_pending_ashare_market_dates(conn: sqlite3.Connection, fallback_start_date: str) -> list[str]:
    null_rows = conn.execute(
        """
        SELECT trade_date
        FROM ashare_daily_market_data
        WHERE sse_amount_yuan IS NULL
           OR szse_amount_yuan IS NULL
           OR sse_circulating_market_cap_yuan IS NULL
           OR szse_circulating_market_cap_yuan IS NULL
        """
    ).fetchall()
    pending = {row["trade_date"] for row in null_rows}

    max_row = conn.execute("SELECT MAX(trade_date) AS max_trade_date FROM ashare_daily_market_data").fetchone()
    max_trade_date = max_row["max_trade_date"] if max_row else None
    if max_trade_date:
        next_day = (datetime.strptime(max_trade_date, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        next_day = fallback_start_date

    today = today_text()
    if next_day <= today:
        pending.update(iter_date_texts(next_day, today))

    return sorted(pending)


def get_existing_ashare_record(conn: sqlite3.Connection, trade_date: str):
    row = conn.execute(
        "SELECT * FROM ashare_daily_market_data WHERE trade_date = ?",
        (trade_date,),
    ).fetchone()
    return dict(row) if row else None


def coalesce_with_existing(record: dict, existing: Optional[dict], fields: list) -> dict:
    if not existing:
        return record
    merged = dict(record)
    for field in fields:
        if merged.get(field) is None:
            merged[field] = existing.get(field)
    return merged


def fetch_ashare_market_record(trade_date: str, tushare_pro) -> dict:
    tushare_market_info = fetch_sh_sz_daily_float_mv_amount_from_tushare(trade_date, tushare_pro)
    sh_info = (tushare_market_info or {}).get("SH")
    sz_info = (tushare_market_info or {}).get("SZ")

    if sh_info is None or sh_info.get("amount_yuan") is None or sh_info.get("float_mv_yuan") is None:
        fallback = fetch_sh_daily_float_mv_amount_from_sse_official(trade_date)
        sh_info = merge_market_info(sh_info, fallback)

    if sz_info is None or sz_info.get("amount_yuan") is None or sz_info.get("float_mv_yuan") is None:
        fallback = fetch_sz_daily_float_mv_amount_from_szse_official(trade_date)
        sz_info = merge_market_info(sz_info, fallback)

    return {
        "trade_date": trade_date,
        "sse_amount_yuan": sh_info.get("amount_yuan") if sh_info else None,
        "szse_amount_yuan": sz_info.get("amount_yuan") if sz_info else None,
        "sse_circulating_market_cap_yuan": sh_info.get("float_mv_yuan") if sh_info else None,
        "szse_circulating_market_cap_yuan": sz_info.get("float_mv_yuan") if sz_info else None,
    }


def merge_market_info(primary, fallback):
    if primary is None:
        return fallback
    if fallback is None:
        return primary
    merged = dict(primary)
    for key in ["amount_yuan", "float_mv_yuan"]:
        if merged.get(key) is None:
            merged[key] = fallback.get(key)
    return merged


def upsert_ashare_market_record(conn: sqlite3.Connection, record: dict) -> bool:
    fields = [
        "sse_amount_yuan",
        "szse_amount_yuan",
        "sse_circulating_market_cap_yuan",
        "szse_circulating_market_cap_yuan",
    ]
    if all(record.get(field) is None for field in fields):
        return False

    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO ashare_daily_market_data (
            trade_date, sse_amount_yuan, szse_amount_yuan,
            sse_circulating_market_cap_yuan, szse_circulating_market_cap_yuan,
            sse_updated_at, szse_updated_at,
            sse_market_cap_updated_at, szse_market_cap_updated_at
        )
        VALUES (
            :trade_date, :sse_amount_yuan, :szse_amount_yuan,
            :sse_circulating_market_cap_yuan, :szse_circulating_market_cap_yuan,
            :sse_updated_at, :szse_updated_at,
            :sse_market_cap_updated_at, :szse_market_cap_updated_at
        )
        ON CONFLICT(trade_date) DO UPDATE SET
            sse_amount_yuan = COALESCE(excluded.sse_amount_yuan, ashare_daily_market_data.sse_amount_yuan),
            szse_amount_yuan = COALESCE(excluded.szse_amount_yuan, ashare_daily_market_data.szse_amount_yuan),
            sse_circulating_market_cap_yuan = COALESCE(excluded.sse_circulating_market_cap_yuan, ashare_daily_market_data.sse_circulating_market_cap_yuan),
            szse_circulating_market_cap_yuan = COALESCE(excluded.szse_circulating_market_cap_yuan, ashare_daily_market_data.szse_circulating_market_cap_yuan),
            sse_updated_at = COALESCE(excluded.sse_updated_at, ashare_daily_market_data.sse_updated_at),
            szse_updated_at = COALESCE(excluded.szse_updated_at, ashare_daily_market_data.szse_updated_at),
            sse_market_cap_updated_at = COALESCE(excluded.sse_market_cap_updated_at, ashare_daily_market_data.sse_market_cap_updated_at),
            szse_market_cap_updated_at = COALESCE(excluded.szse_market_cap_updated_at, ashare_daily_market_data.szse_market_cap_updated_at)
        """,
        {
            **record,
            "sse_updated_at": now if record.get("sse_amount_yuan") is not None else None,
            "szse_updated_at": now if record.get("szse_amount_yuan") is not None else None,
            "sse_market_cap_updated_at": now if record.get("sse_circulating_market_cap_yuan") is not None else None,
            "szse_market_cap_updated_at": now if record.get("szse_circulating_market_cap_yuan") is not None else None,
        },
    )
    return True


def update_ashare_daily_market_data(conn: sqlite3.Connection, start_date: str) -> tuple[int, int]:
    pending_dates = get_pending_ashare_market_dates(conn, start_date)
    if not pending_dates:
        LOGGER.info("沪深成交额和流通市值无待更新日期")
        return 0, 0

    LOGGER.info("待更新沪深成交额和流通市值日期数：%s", len(pending_dates))
    tushare_pro = get_tushare_pro()
    updated_count = 0
    skipped_count = 0
    for trade_date in pending_dates:
        existing = get_existing_ashare_record(conn, trade_date)
        fetched = fetch_ashare_market_record(trade_date, tushare_pro)
        merged = coalesce_with_existing(
            fetched,
            existing,
            [
                "sse_amount_yuan",
                "szse_amount_yuan",
                "sse_circulating_market_cap_yuan",
                "szse_circulating_market_cap_yuan",
            ],
        )
        if upsert_ashare_market_record(conn, merged):
            updated_count += 1
            conn.commit()
        else:
            skipped_count += 1
        time.sleep(REQUEST_SLEEP_SECONDS)

    LOGGER.info("沪深成交额和流通市值更新完成：写入 %s 条，跳过 %s 条", updated_count, skipped_count)
    return updated_count, skipped_count


def update_margin_balance(conn: sqlite3.Connection) -> int:
    margin_rows = fetch_sh_sz_full_margin_balance_from_akshare()
    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for row in margin_rows:
        if row.get("total_margin_balance_yuan") is None:
            continue
        conn.execute(
            """
            INSERT INTO ashare_daily_market_data (
                trade_date, total_margin_balance_yuan, margin_updated_at
            )
            VALUES (
                :trade_date, :total_margin_balance_yuan, :margin_updated_at
            )
            ON CONFLICT(trade_date) DO UPDATE SET
                total_margin_balance_yuan = excluded.total_margin_balance_yuan,
                margin_updated_at = excluded.margin_updated_at
            """,
            {
                "trade_date": row["trade_date"],
                "total_margin_balance_yuan": row["total_margin_balance_yuan"],
                "margin_updated_at": now,
            },
        )
        count += 1
    conn.commit()
    LOGGER.info("融资余额更新完成：写入 %s 条", count)
    return count


def upsert_index_daily_records(conn: sqlite3.Connection, records: list[dict]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for record in records:
        values = dict(record)
        values["created_at"] = now
        values["updated_at"] = now
        conn.execute(
            """
            INSERT INTO index_daily_data (
                index_name, index_code, market_type, trade_date,
                open, close, high, low, volume, amount,
                data_source, data_status, created_at, updated_at
            )
            VALUES (
                :index_name, :index_code, :market_type, :trade_date,
                :open, :close, :high, :low, :volume, :amount,
                :data_source, :data_status, :created_at, :updated_at
            )
            ON CONFLICT(index_code, trade_date) DO UPDATE SET
                index_name = excluded.index_name,
                market_type = excluded.market_type,
                open = excluded.open,
                close = excluded.close,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                amount = excluded.amount,
                data_source = excluded.data_source,
                data_status = excluded.data_status,
                updated_at = excluded.updated_at
            """,
            values,
        )
        count += 1
    return count


def update_index_daily_data(conn: sqlite3.Connection) -> int:
    total_count = 0
    for index_name, index_code in index_dict.items():
        try:
            records = fetch_index_full_from_akshare(index_name, index_code)
        except Exception as exc:
            LOGGER.warning("%s (%s) 获取失败，保留本地缓存：%s", index_name, index_code, exc)
            continue
        count = upsert_index_daily_records(conn, records)
        conn.commit()
        total_count += count
        LOGGER.info("%s (%s) 指数数据写入 %s 条", index_name, index_code, count)
    return total_count


def load_index_chart_data(conn: sqlite3.Connection, start_date: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT index_name, index_code, trade_date, close
        FROM index_daily_data
        WHERE trade_date >= ?
          AND close IS NOT NULL
          AND data_status = 'complete'
        ORDER BY index_name, trade_date
        """,
        (start_date,),
    ).fetchall()
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return []

    output = []
    for index_name, group in df.groupby("index_name", sort=False):
        work = group.sort_values("trade_date").copy()
        work["ma60"] = work["close"].rolling(window=60, min_periods=60).mean()
        work["deviation"] = (work["close"] - work["ma60"]) / work["ma60"]
        for _, row in work.dropna(subset=["deviation"]).iterrows():
            output.append(
                {
                    "date": row["trade_date"],
                    "series": index_name,
                    "close": round(float(row["close"]), 4),
                    "ma60": round(float(row["ma60"]), 4),
                    "deviation": round(float(row["deviation"]), 6),
                }
            )
    return output


def load_turnover_chart_data(conn: sqlite3.Connection, start_date: str) -> list[dict]:
    hs300_code = index_dict.get(HS300_NAME)
    if not hs300_code:
        raise RuntimeError(f"未在 config/index_code.py 中找到 {HS300_NAME}")

    rows = conn.execute(
        """
        SELECT
            a.trade_date,
            a.sse_amount_yuan,
            a.szse_amount_yuan,
            i.close AS hs300_close
        FROM ashare_daily_market_data a
        LEFT JOIN index_daily_data i
          ON i.index_code = ?
         AND i.trade_date = a.trade_date
        WHERE a.trade_date >= ?
          AND a.sse_amount_yuan IS NOT NULL
          AND a.szse_amount_yuan IS NOT NULL
          AND i.close IS NOT NULL
        ORDER BY a.trade_date
        """,
        (hs300_code, start_date),
    ).fetchall()
    data = []
    for row in rows:
        total_amount = float(row["sse_amount_yuan"]) + float(row["szse_amount_yuan"])
        data.append(
            {
                "date": row["trade_date"],
                "totalAmount100m": round(total_amount / YUAN_PER_100M, 4),
                "hs300Close": round(float(row["hs300_close"]), 4),
            }
        )
    return data


def load_margin_chart_data(conn: sqlite3.Connection, start_date: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            trade_date,
            total_margin_balance_yuan,
            sse_circulating_market_cap_yuan,
            szse_circulating_market_cap_yuan
        FROM ashare_daily_market_data
        WHERE trade_date >= ?
          AND total_margin_balance_yuan IS NOT NULL
          AND sse_circulating_market_cap_yuan IS NOT NULL
          AND szse_circulating_market_cap_yuan IS NOT NULL
        ORDER BY trade_date
        """,
        (start_date,),
    ).fetchall()
    data = []
    for row in rows:
        total_market_cap = float(row["sse_circulating_market_cap_yuan"]) + float(
            row["szse_circulating_market_cap_yuan"]
        )
        if total_market_cap == 0:
            continue
        margin_balance = float(row["total_margin_balance_yuan"])
        data.append(
            {
                "date": row["trade_date"],
                "marginBalance100m": round(margin_balance / YUAN_PER_100M, 4),
                "marginToMarketCap": round(margin_balance / total_market_cap, 6),
            }
        )
    return data


def build_dashboard_payload(conn: sqlite3.Connection, start_date: str) -> dict:
    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "startDate": start_date,
        "indexDeviation": load_index_chart_data(conn, start_date),
        "turnover": load_turnover_chart_data(conn, start_date),
        "margin": load_margin_chart_data(conn, start_date),
    }


def generate_html(payload: dict, output_dir: str, output_name: str) -> Path:
    out_dir = resolve_project_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / output_name
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    safe_title = html.escape("资本市场脉搏")
    output_path.write_text(
        HTML_TEMPLATE.replace("__PAYLOAD__", payload_json).replace("__TITLE__", safe_title),
        encoding="utf-8",
    )
    LOGGER.info("交互网页已生成：%s", output_path)
    return output_path


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      color-scheme: light;
      --bg: #f2f0eb;
      --panel: #ffffff;
      --text: rgba(0, 0, 0, 0.87);
      --text-soft: rgba(0, 0, 0, 0.58);
      --accent: #00754A;
      --accent-2: #006241;
      --accent-3: #cba258;
      --accent-4: #2b5148;
      --line: #d6dbde;
      --grid: #edebe9;
      --shadow-sm: 0 0 0.5px rgba(0, 0, 0, 0.14), 0 1px 1px rgba(0, 0, 0, 0.24);
      --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.06);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.5;
      letter-spacing: -0.01em;
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }
    header {
      max-width: 2400px;
      margin: 0 auto;
      padding: 48px 40px 32px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 32px;
      font-weight: 600;
      line-height: 1.2;
      letter-spacing: -0.02em;
      color: var(--accent-2);
    }
    .meta {
      display: none;
    }
    main {
      max-width: 2400px;
      margin: 0 auto;
      padding: 0 40px 48px;
    }
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }
    .tab-button {
      appearance: none;
      border: none;
      background: transparent;
      color: var(--text-soft);
      font-family: inherit;
      font-size: 14px;
      font-weight: 500;
      letter-spacing: -0.01em;
      padding: 10px 20px;
      border-radius: 50px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .tab-button:hover {
      background: rgba(0, 117, 74, 0.08);
      color: var(--accent);
    }
    .tab-button[aria-selected="true"] {
      background: var(--accent);
      color: #ffffff;
      font-weight: 600;
    }
    .tab-button[aria-selected="true"]:hover {
      background: var(--accent-2);
    }
    .tab-panel {
      display: none;
    }
    .tab-panel.active {
      display: block;
    }
    .chart-card {
      background: var(--panel);
      border-radius: 12px;
      box-shadow: var(--shadow-sm);
      padding: 24px;
      margin-bottom: 20px;
    }
    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--grid);
    }
    .chart-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--accent-2);
      margin: 0;
    }
    .chart-latest {
      color: #bd3c2f;
      font-size: 13px;
      font-weight: 600;
      text-align: right;
    }
    .chart {
      position: relative;
      width: 100%;
      height: 380px;
    }
    svg {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .axis text {
      fill: var(--text-soft);
      font-size: 12px;
      font-weight: 400;
    }
    .axis line, .axis path {
      stroke: var(--line);
    }
    .grid line {
      stroke: var(--grid);
      stroke-width: 1;
    }
    .reference-line {
      stroke: rgba(0, 117, 74, 0.15);
      stroke-width: 1;
      stroke-dasharray: 4 4;
    }
    .zero-line {
      stroke: rgba(203, 162, 88, 0.4);
      stroke-width: 1.2;
    }
    .latest-guide {
      stroke: rgba(0, 117, 74, 0.35);
      stroke-width: 1.5;
      stroke-dasharray: 4 4;
    }
    .latest-marker {
      fill: var(--accent);
      stroke: #ffffff;
      stroke-width: 2.5;
    }
    .latest-label {
      fill: #bd3c2f;
      font-size: 12px;
      font-weight: 600;
    }
    .area-fill {
      fill: url(#areaGradient);
      opacity: 0.15;
    }
    .tooltip {
      position: absolute;
      z-index: 10;
      pointer-events: none;
      min-width: 240px;
      max-width: 360px;
      padding: 14px 16px;
      background: rgba(255, 255, 255, 0.98);
      border: 1px solid var(--line);
      border-radius: 12px;
      box-shadow: var(--shadow-md);
      font-size: 13px;
      line-height: 1.5;
      display: none;
      backdrop-filter: blur(8px);
    }
    .tooltip strong {
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      color: var(--accent-2);
      font-size: 14px;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--grid);
    }
    .legend span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--text-soft);
      font-size: 13px;
    }
    .swatch {
      width: 20px;
      height: 4px;
      border-radius: 999px;
    }
    .empty {
      height: 200px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: var(--text-soft);
      background: var(--bg);
      border: 1px dashed var(--line);
      border-radius: 12px;
      gap: 8px;
    }
    .empty-icon {
      width: 48px;
      height: 48px;
      opacity: 0.4;
    }
    .index-panel .chart-card {
      margin-bottom: 20px;
    }
    .index-panel .chart {
      height: 360px;
    }
    @media (max-width: 768px) {
      header { padding: 32px 20px 24px; }
      h1 { font-size: 26px; }
      main { padding: 0 20px 32px; }
      .tabs { overflow-x: auto; padding-bottom: 12px; }
      .tab-button { padding: 8px 16px; font-size: 13px; white-space: nowrap; }
      .chart-card { padding: 16px; }
      .chart { height: 320px; }
      .index-panel .chart { height: 280px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>资本市场脉搏</h1>
    <div class="meta" id="meta"></div>
  </header>
  <main>
    <nav class="tabs" aria-label="图表分类">
      <button class="tab-button" type="button" data-tab="indexPanel" aria-selected="true">指数 MA60 偏离度</button>
      <button class="tab-button" type="button" data-tab="marginPanel" aria-selected="false">融资余额与流通市值占比</button>
      <button class="tab-button" type="button" data-tab="turnoverPanel" aria-selected="false">沪深成交金额</button>
    </nav>

    <div class="tab-panel active index-panel" id="indexPanel"></div>

    <div class="tab-panel" id="marginPanel">
      <div class="chart-card">
        <div class="chart-header">
          <h2 class="chart-title">沪深市场融资余额</h2>
          <div class="chart-latest" id="marginBalanceLatest"></div>
        </div>
        <div class="chart" id="marginBalanceChart"></div>
        <div class="legend" id="marginBalanceLegend"></div>
      </div>
      <div class="chart-card">
        <div class="chart-header">
          <h2 class="chart-title">沪深市场融资余额/流通市值</h2>
          <div class="chart-latest" id="marginRatioLatest"></div>
        </div>
        <div class="chart" id="marginRatioChart"></div>
        <div class="legend" id="marginRatioLegend"></div>
      </div>
    </div>

    <div class="tab-panel" id="turnoverPanel">
      <div class="chart-card">
        <div class="chart-header">
          <h2 class="chart-title">沪深成交金额</h2>
          <div class="chart-latest" id="turnoverLatest"></div>
        </div>
        <div class="chart" id="turnoverChart"></div>
        <div class="legend" id="turnoverLegend"></div>
      </div>
    </div>
  </main>
  <script>
    const payload = __PAYLOAD__;
    const colors = ["#00754A", "#006241", "#cba258", "#2b5148", "#4a7c6f", "#8b6f4e", "#3d7a6a", "#a08040"];
    const parseDate = value => new Date(value + "T00:00:00");
    const fmtNumber = (value, digits = 2) => Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
    const fmtPercent = value => (Number(value) * 100).toFixed(2) + "%";
    const renderedTabs = new Set();

    document.getElementById("meta").textContent = ``;

    document.querySelectorAll(".tab-button").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab-button").forEach(item => item.setAttribute("aria-selected", String(item === button)));
        document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.toggle("active", panel.id === button.dataset.tab));
        renderTab(button.dataset.tab);
      });
    });

    function extent(values) {
      const nums = values.filter(value => Number.isFinite(value));
      return nums.length ? [Math.min(...nums), Math.max(...nums)] : [0, 1];
    }

    function quantile(sorted, q) {
      if (!sorted.length) return 0;
      const pos = (sorted.length - 1) * q;
      const base = Math.floor(pos);
      const rest = pos - base;
      if (sorted[base + 1] === undefined) return sorted[base];
      return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
    }

    function niceDomain(min, max) {
      if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
      if (min === max) {
        const pad = Math.abs(min || 1) * 0.1;
        return [min - pad, max + pad];
      }
      const pad = (max - min) * 0.08;
      return [min - pad, max + pad];
    }

    function domainFor(values, mode) {
      const nums = values.filter(value => Number.isFinite(value)).sort((a, b) => a - b);
      if (!nums.length) return [0, 1];
      if (mode === "zeroMin") {
        return [0, niceDomain(nums[0], nums[nums.length - 1])[1]];
      }
      if (mode === "nice") {
        return niceDomain(nums[0], nums[nums.length - 1]);
      }
      if (mode === "focused" && nums.length >= 20) {
        return niceDomain(quantile(nums, 0.03), quantile(nums, 0.97));
      }
      return niceDomain(nums[0], nums[nums.length - 1]);
    }

    function percentDomain(values, paddingRatio = 0.15, clampToZero = false) {
  const nums = values
    .map(value => Number(value))
    .filter(value => Number.isFinite(value))
    .sort((a, b) => a - b);

  if (!nums.length) return [0.02, 0.03];

  const min = nums[0];
  const max = nums[nums.length - 1];

  if (min === max) {
    const pad = Math.max(Math.abs(min) * paddingRatio, 0.001);
    const lower = clampToZero ? Math.max(0, min - pad) : min - pad;
    return [lower, max + pad];
  }

  const span = max - min;
  const padding = Math.max(span * paddingRatio, 0.001);

  const lower = clampToZero ? Math.max(0, min - padding) : min - padding;
  const upper = max + padding;

  return [
    Number(lower.toFixed(6)),
    Number(upper.toFixed(6))
  ];
}

    function percentStepTicks(values, step = 0.05) {
      const [min, max] = extent(values);
      const lower = Math.min(-step, Math.floor(min / step) * step);
      const upper = Math.max(step, Math.ceil(max / step) * step);
      const result = [];
      for (let value = lower; value <= upper + step / 2; value += step) {
        result.push(Number(value.toFixed(4)));
      }
      if (!result.some(value => Math.abs(value) < 0.000001)) result.push(0);
      return result.sort((a, b) => a - b);
    }

    function makeSvg(container) {
      container.innerHTML = "";
      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
      gradient.setAttribute("id", "areaGradient");
      gradient.setAttribute("x1", "0%");
      gradient.setAttribute("y1", "0%");
      gradient.setAttribute("x2", "0%");
      gradient.setAttribute("y2", "100%");
      const stop1 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
      stop1.setAttribute("offset", "0%");
      stop1.setAttribute("stop-color", "#00754A");
      stop1.setAttribute("stop-opacity", "0.4");
      const stop2 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
      stop2.setAttribute("offset", "100%");
      stop2.setAttribute("stop-color", "#00754A");
      stop2.setAttribute("stop-opacity", "0.02");
      gradient.appendChild(stop1);
      gradient.appendChild(stop2);
      defs.appendChild(gradient);
      const tooltip = document.createElement("div");
      tooltip.className = "tooltip";
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.appendChild(defs);
      container.appendChild(tooltip);
      container.appendChild(svg);
      return { svg, tooltip };
    }

    function setAttrs(node, attrs) {
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    }

    function make(tag, attrs = {}, text = "") {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      setAttrs(node, attrs);
      if (text) node.textContent = text;
      return node;
    }

    function ticks(min, max, count) {
      if (count <= 1) return [min];
      return Array.from({ length: count }, (_, index) => min + (max - min) * index / (count - 1));
    }

    function buildAreaPath(points, xScale, yScale, height) {
      if (!points.length) return "";
      const sorted = [...points].sort((a, b) => a.date.localeCompare(b.date));
      const first = sorted[0];
      const last = sorted[sorted.length - 1];
      const x1 = xScale(parseDate(first.date).getTime());
      const x2 = xScale(parseDate(last.date).getTime());
      const yBottom = height - 42;
      let d = `M${x1.toFixed(2)},${yBottom}`;
      sorted.forEach(p => {
        d += ` L${xScale(parseDate(p.date).getTime()).toFixed(2)},${yScale(Number(p.value)).toFixed(2)}`;
      });
      d += ` L${x2.toFixed(2)},${yBottom} Z`;
      return d;
    }

    function renderLineChart(options) {
      const container = document.getElementById(options.containerId);
      const legend = document.getElementById(options.legendId);
      const latest = document.getElementById(options.latestId);
      const rawSeries = options.series.filter(item => item.points.length);
      if (!rawSeries.length) {
        container.innerHTML = '<div class="empty"><svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>暂无可绘制数据</div>';
        legend.innerHTML = "";
        latest.textContent = "";
        return;
      }

      const { svg, tooltip } = makeSvg(container);
      const width = container.clientWidth || 900;
      const height = container.clientHeight || 420;
      setAttrs(svg, { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": options.title });

      const margin = { top: 20, right: options.rightAxis ? 72 : 24, bottom: 48, left: 72 };
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const allPoints = rawSeries.flatMap(series => series.points);
      const dateValues = allPoints.map(point => parseDate(point.date).getTime());
      const [xMin, xMax] = extent(dateValues);
      const leftValues = rawSeries.filter(series => series.axis !== "right").flatMap(series => series.points.map(point => Number(point.value)));
      const rightValues = rawSeries.filter(series => series.axis === "right").flatMap(series => series.points.map(point => Number(point.value)));
      const [leftMin, leftMax] = options.leftDomain || domainFor(leftValues, options.leftDomainMode);
      const [rightMin, rightMax] = options.rightAxis ? (options.rightDomain || domainFor(rightValues, options.rightDomainMode)) : [leftMin, leftMax];
      function safeSpan(min, max) {
          const span = max - min;
          return Number.isFinite(span) && Math.abs(span) > 1e-12 ? span : 1;
      }

      const xSpan = safeSpan(xMin, xMax);
      const leftSpan = safeSpan(leftMin, leftMax);
      const rightSpan = safeSpan(rightMin, rightMax);

      const xScale = time =>
        margin.left + ((time - xMin) / xSpan) * plotW;

      const yLeft = value =>
        margin.top + (1 - (value - leftMin) / leftSpan) * plotH;

      const yRight = value =>
        margin.top + (1 - (value - rightMin) / rightSpan) * plotH;
      const clampY = value => Math.min(height - margin.bottom, Math.max(margin.top, value));

      const grid = make("g", { class: "grid" });
      const leftTicks = options.leftTicks || ticks(leftMin, leftMax, 5);
      const rightTicks = options.rightTicks || ticks(rightMin, rightMax, 5);
      leftTicks.forEach(value => {
        const y = yLeft(value);
        grid.appendChild(make("line", { x1: margin.left, x2: width - margin.right, y1: y, y2: y }));
      });
      svg.appendChild(grid);

      if (options.referenceLines) {
        const references = make("g", { class: "references" });
        options.referenceLines.forEach(value => {
          if (value < leftMin || value > leftMax) return;
          const y = yLeft(value);
          references.appendChild(make("line", { class: value === 0 ? "zero-line" : "reference-line", x1: margin.left, x2: width - margin.right, y1: y, y2: y }));
        });
        svg.appendChild(references);
      }

      const axis = make("g", { class: "axis" });
      leftTicks.forEach(value => {
        const y = yLeft(value);
        axis.appendChild(make("text", { x: margin.left - 12, y: y + 4, "text-anchor": "end" }, options.leftFormat(value)));
      });
      if (options.rightAxis) {
        rightTicks.forEach(value => {
          const y = yRight(value);
          axis.appendChild(make("text", { x: width - margin.right + 12, y: y + 4 }, options.rightFormat(value)));
        });
      }
      const dateTicks = ticks(xMin, xMax, Math.min(7, Math.max(2, Math.floor(plotW / 130))));
      dateTicks.forEach(value => {
        const d = new Date(value);
        axis.appendChild(make("text", { x: xScale(value), y: height - 16, "text-anchor": "middle" }, `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`));
      });
      axis.appendChild(make("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom }));
      axis.appendChild(make("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom }));
      if (options.rightAxis) axis.appendChild(make("line", { x1: width - margin.right, x2: width - margin.right, y1: margin.top, y2: height - margin.bottom }));
      svg.appendChild(axis);

      if (options.areaSeries !== undefined) {
        const areaSeries = rawSeries.find(s => s.name === options.areaSeries);
        if (areaSeries) {
          const areaPath = make("path", { class: "area-fill", d: buildAreaPath(areaSeries.points, xScale, yLeft, height) });
          svg.insertBefore(areaPath, svg.querySelector(".grid")?.nextSibling || svg.firstChild.nextSibling);
        }
      }

        rawSeries.forEach((series, index) => {
        const scaleY = series.axis === "right" ? yRight : yLeft;
        const d = series.points.map((point, pointIndex) => {
          const command = pointIndex === 0 ? "M" : "L";
          return `${command}${xScale(parseDate(point.date).getTime()).toFixed(2)},${clampY(scaleY(Number(point.value))).toFixed(2)}`;
        }).join(" ");
        svg.appendChild(make("path", {
          d,
          fill: "none",
          stroke: series.color || colors[index % colors.length],
          "stroke-width": options.lineWidth || 2,
          "stroke-linejoin": "round",
          "stroke-linecap": "round"
        }));
      });

      if (options.latestAnnotation && rawSeries[0]?.points.length) {
        const series = rawSeries[0];
        const point = series.points[series.points.length - 1];
        const x = xScale(parseDate(point.date).getTime());
        const y = clampY(yLeft(Number(point.value)));
        const labelX = x;
        const labelY = margin.top + 22;
        svg.appendChild(make("line", { class: "latest-guide", x1: x, x2: x, y1: labelY + 24, y2: y }));
        svg.appendChild(make("circle", { class: "latest-marker", cx: x, cy: y, r: 5 }));
        const label = make("text", { class: "latest-label", x: labelX, y: labelY, "text-anchor": "middle" });
        label.appendChild(make("tspan", { x: labelX, dy: 0 }, point.date));
        label.appendChild(make("tspan", { x: labelX, dy: 16 }, options.latestAnnotationFormat(point)));
        svg.appendChild(label);
      }

      const hoverLine = make("line", {
        y1: margin.top,
        y2: height - margin.bottom,
        stroke: "rgba(0,0,0,0.2)",
        "stroke-width": 1,
        "stroke-dasharray": "4 4",
        opacity: 0
      });
      svg.appendChild(hoverLine);
      const overlay = make("rect", {
        x: margin.left,
        y: margin.top,
        width: plotW,
        height: plotH,
        fill: "transparent"
      });
      svg.appendChild(overlay);

      const byDate = new Map();
      allPoints.forEach(point => {
        if (!byDate.has(point.date)) byDate.set(point.date, []);
        byDate.get(point.date).push(point);
      });
      const dates = Array.from(byDate.keys()).sort();
      const dateTimes = dates.map(date => parseDate(date).getTime());

      overlay.addEventListener("mousemove", event => {
        const rect = svg.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const time = xMin + (Math.min(Math.max(mouseX, margin.left), width - margin.right) - margin.left) / plotW * (xMax - xMin);
        let nearestIndex = 0;
        let nearestDistance = Infinity;
        dateTimes.forEach((item, index) => {
          const distance = Math.abs(item - time);
          if (distance < nearestDistance) {
            nearestDistance = distance;
            nearestIndex = index;
          }
        });
        const date = dates[nearestIndex];
        const x = xScale(dateTimes[nearestIndex]);
        setAttrs(hoverLine, { x1: x, x2: x, opacity: 1 });
        tooltip.innerHTML = options.tooltip(date, byDate.get(date));
        tooltip.style.display = "block";
        const left = Math.min(Math.max(x + 16, 12), width - 300);
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${Math.max(12, event.clientY - rect.top - 24)}px`;
      });
      overlay.addEventListener("mouseleave", () => {
        tooltip.style.display = "none";
        setAttrs(hoverLine, { opacity: 0 });
      });

      legend.innerHTML = rawSeries.map((series, index) => {
        const color = series.color || colors[index % colors.length];
        const axisLabel = options.rightAxis ? (series.axis === "right" ? "右轴" : "左轴") : "";
        const name = axisLabel ? `${series.name}（${axisLabel}）` : series.name;
        return `<span><i class="swatch" style="background:${color}"></i>${name}</span>`;
      }).join("");

      const latestDate = dates[dates.length - 1];
      latest.textContent = options.latestText(latestDate, byDate.get(latestDate));
    }

    function groupIndexRows(rows) {
      const grouped = new Map();
      rows.forEach(row => {
        if (!grouped.has(row.series)) grouped.set(row.series, []);
        grouped.get(row.series).push({ date: row.date, value: row.deviation, close: row.close, ma60: row.ma60, series: row.series });
      });
      return Array.from(grouped, ([name, points]) => ({
        name,
        color: colors[grouped.size % colors.length],
        points: points.sort((a, b) => a.date.localeCompare(b.date))
      }));
    }

    function renderIndexCharts() {
      if (renderedTabs.has("index")) return;
      renderedTabs.add("index");
      const panel = document.getElementById("indexPanel");
      const groups = groupIndexRows(payload.indexDeviation);
      if (!groups.length) {
        panel.innerHTML = '<div class="empty"><svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>暂无可绘制数据</div>';
        return;
      }
      panel.innerHTML = groups.map((group, index) => `
        <div class="chart-card">
          <div class="chart-header">
            <h2 class="chart-title">${group.name}</h2>
            <div class="chart-latest" id="indexLatest${index}"></div>
          </div>
          <div class="chart" id="indexChart${index}"></div>
          <div class="legend" id="indexLegend${index}"></div>
        </div>
      `).join("");
      groups.forEach((group, index) => {
        const deviationTicks = percentStepTicks(group.points.map(point => Number(point.value)), 0.05);
        renderLineChart({
          containerId: `indexChart${index}`,
          legendId: `indexLegend${index}`,
          latestId: `indexLatest${index}`,
          title: `${group.name} MA60 偏离度`,
          series: [{ name: "MA60 偏离度", color: "#00754A", points: group.points }],
          leftDomain: [deviationTicks[0], deviationTicks[deviationTicks.length - 1]],
          leftTicks: deviationTicks,
          referenceLines: deviationTicks,
          leftFormat: fmtPercent,
          latestAnnotation: true,
          latestAnnotationFormat: point => fmtPercent(point.value),
          tooltip: (date, points) => `<strong>${date}</strong>偏离度：${fmtPercent(points[0]?.value || 0)}<br>收盘：${fmtNumber(points[0]?.close || 0, 2)}<br>MA60：${fmtNumber(points[0]?.ma60 || 0, 2)}`,
          latestText: () => ``
        });
      });
    }

    function renderMarginChart() {
      if (renderedTabs.has("margin")) return;
      renderedTabs.add("margin");

      // Chart 1: 沪深市场融资余额
      renderLineChart({
        containerId: "marginBalanceChart",
        legendId: "marginBalanceLegend",
        latestId: "marginBalanceLatest",
        title: "沪深市场融资余额",
        rightAxis: false,
        leftDomainMode: "zeroMin",
        areaSeries: "沪深合计融资余额（亿元）",
        series: [
          { name: "沪深合计融资余额（亿元）", color: "#00754A", points: payload.margin.map(row => ({ date: row.date, value: row.marginBalance100m })) }
        ],
        leftFormat: value => fmtNumber(value, 0),
        tooltip: (date, points) => `<strong>${date}</strong>融资余额：${fmtNumber(points[0]?.value || 0, 2)} 亿元`,
        latestText: (date, points) => `${date}　融资余额 ${fmtNumber(points[0]?.value || 0, 2)} 亿元`
      });

      // Chart 2: 融资余额 / 流通市值
    const ratioPoints = payload.margin
        .map(row => ({
             date: row.date,
             value: Number(row.marginToMarketCap)
      })).filter(point => Number.isFinite(point.value));

    const ratioValues = ratioPoints.map(point => point.value);

    const ratioDomain = percentDomain(ratioValues, 0.15, true);

    // 不要用 percentStepTicks 生成过多刻度，直接用 5 个刻度
    const ratioTicks = ticks(ratioDomain[0], ratioDomain[1], 5);

    renderLineChart({
  containerId: "marginRatioChart",
  legendId: "marginRatioLegend",
  latestId: "marginRatioLatest",
  title: "融资余额 / 流通市值",
  rightAxis: false,
  leftDomain: ratioDomain,
  leftTicks: ratioTicks,
  referenceLines: ratioTicks,
  series: [
    {
      name: "融资余额/流通市值",
      color: "#cba258",
      points: ratioPoints
    }
  ],
  lineWidth: 3,
  leftFormat: fmtPercent,
  tooltip: (date, points) =>
    `<strong>${date}</strong>占流通市值：${fmtPercent(points[0]?.value || 0)}`,
  latestText: (date, points) =>
    `${date} 占比 ${fmtPercent(points[0]?.value || 0)}`
        });
    }

    function renderTurnoverChart() {
      if (renderedTabs.has("turnover")) return;
      renderedTabs.add("turnover");
      renderLineChart({
        containerId: "turnoverChart",
        legendId: "turnoverLegend",
        latestId: "turnoverLatest",
        title: "沪深成交金额与沪深300点位",
        rightAxis: true,
        leftDomainMode: "zeroMin",
        rightDomainMode: "zeroMin",
        areaSeries: "沪深合计成交金额（亿元）",
        series: [
          { name: "沪深合计成交金额（亿元）", color: "#00754A", points: payload.turnover.map(row => ({ date: row.date, value: row.totalAmount100m })) },
          { name: "沪深300点位", color: "#8b5cf6", axis: "right", points: payload.turnover.map(row => ({ date: row.date, value: row.hs300Close })) }
        ],
        leftFormat: value => fmtNumber(value, 0),
        rightFormat: value => fmtNumber(value, 0),
        tooltip: (date, points) => `<strong>${date}</strong>成交金额：${fmtNumber(points[0]?.value || 0, 2)} 亿元<br>沪深300：${fmtNumber(points[1]?.value || 0, 2)}`,
        latestText: (date, points) => `${date}　成交金额 ${fmtNumber(points[0]?.value || 0, 2)} 亿元　沪深300 ${fmtNumber(points[1]?.value || 0, 2)}`
      });
    }

    function renderTab(tabId) {
      if (tabId === "indexPanel") {
        renderIndexCharts();
      } else if (tabId === "marginPanel") {
        renderMarginChart();
      } else if (tabId === "turnoverPanel") {
        renderTurnoverChart();
      }
    }

    window.addEventListener("resize", () => {
      clearTimeout(window.__resizeTimer);
      window.__resizeTimer = setTimeout(() => location.reload(), 200);
    });

    requestAnimationFrame(() => renderTab("indexPanel"));
  </script>
</body>
</html>
"""


def main():
    args = parse_args()
    setup_logging()
    validate_date(args.start_date)
    conn = init_db(args.db_path)
    try:
        if not args.skip_fetch:
            update_ashare_daily_market_data(conn, args.start_date)
            update_margin_balance(conn)
            update_index_daily_data(conn)
        payload = build_dashboard_payload(conn, args.start_date)
        output_path = generate_html(payload, args.output_dir, args.output_name)
        print(output_path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

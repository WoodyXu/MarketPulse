import argparse
import html
import json
import logging
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text in sys.path:
    sys.path.remove(project_root_text)
sys.path.insert(0, project_root_text)

try:
    from config.consts import START_DATE  # noqa: E402
except ImportError:
    START_DATE = "2020-01-01"

def detect_default_db_path() -> str:
    for candidate in (
        "data/market_data.sqlite",
        "data/market_data.db",
        "data/market_data",
    ):
        if (PROJECT_ROOT / candidate).exists():
            return candidate
    return "data/market_data.sqlite"


try:
    from config.consts import DB_PATH  # noqa: E402
except ImportError:
    DB_PATH = detect_default_db_path()


LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT_DIR = "beijing_real_estate_market_pulse"
PAGE_TITLE = "北京房产市场脉搏"
WEEKDAY_LABELS = {
    0: "周一",
    1: "周二",
    2: "周三",
    3: "周四",
    4: "周五",
    5: "周六",
    6: "周日",
}
CHART_WEEKDAY_ORDER = ["周一", "周二", "周三", "周四", "周五", "周末"]


def parse_args():
    parser = argparse.ArgumentParser(description="生成北京房产市场脉搏交互式网页")
    parser.add_argument("--start-date", default=START_DATE, help="图表起始日期，格式 YYYY-MM-DD")
    parser.add_argument("--db-path", default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="网页输出目录")
    parser.add_argument("--output-name", default="index.html", help="网页文件名")
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


def init_db(db_path: str) -> sqlite3.Connection:
    db_file = resolve_project_path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"数据库不存在：{db_file}")
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    validate_required_tables(conn)
    return conn


def validate_required_tables(conn: sqlite3.Connection) -> None:
    required_tables = {
        "beijing_real_estate_daily_info",
        "beijing_residents_credit_monthly_info",
    }
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name IN (?, ?)
        """,
        tuple(required_tables),
    ).fetchall()
    existing_tables = {row["name"] for row in rows}
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        raise RuntimeError(f"数据库缺少必要数据表：{', '.join(missing_tables)}")


def safe_float(value: Any):
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def safe_round(value: Any, digits: int = 4):
    num = safe_float(value)
    if num is None:
        return None
    return round(num, digits)


def int_or_none(value: Any):
    num = safe_float(value)
    if num is None:
        return None
    return int(round(num))


def sum_non_null(series: pd.Series):
    values = series.dropna()
    if values.empty:
        return None
    return values.sum()


def append_point(output: list[dict], *, x: Any, label: str, value: Any, **extra: Any) -> None:
    num = safe_float(value)
    if num is None:
        return
    point = {
        "x": str(x),
        "label": label,
        "value": round(num, 6),
    }
    point.update(extra)
    output.append(point)


def load_daily_market_df(conn: sqlite3.Connection, start_date: str) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT
            trade_date,
            lianjia_deals,
            second_hand_online_signings,
            house_view_people,
            price_increase_houses,
            price_decrease_houses
        FROM beijing_real_estate_daily_info
        WHERE trade_date >= ?
        ORDER BY trade_date
        """,
        (start_date,),
    ).fetchall()
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    numeric_columns = [
        "lianjia_deals",
        "second_hand_online_signings",
        "house_view_people",
        "price_increase_houses",
        "price_decrease_houses",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["weekday"] = df["date"].dt.weekday
    df["weekday_label"] = df["weekday"].map(WEEKDAY_LABELS)
    return df.sort_values("trade_date").reset_index(drop=True)


def build_weekday_points(df: pd.DataFrame, value_column: str) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output

    weekday_df = df[df["weekday"].between(0, 4)].copy()
    for _, row in weekday_df.iterrows():
        append_point(
            output,
            x=row["trade_date"],
            label=row["trade_date"],
            value=row[value_column],
            weekday=row["weekday_label"],
        )

    weekend_df = df[df["weekday"].isin([5, 6])].copy()
    if not weekend_df.empty:
        weekend_df["week_start"] = weekend_df["date"] - pd.to_timedelta(weekend_df["weekday"], unit="D")
        grouped = (
            weekend_df.groupby("week_start", as_index=False)
            .agg(value=(value_column, sum_non_null))
            .sort_values("week_start")
        )
        for _, row in grouped.iterrows():
            if row["value"] is None or pd.isna(row["value"]):
                continue
            weekend_date = row["week_start"] + pd.Timedelta(days=6)
            label = weekend_date.strftime("%Y-%m-%d")
            append_point(
                output,
                x=label,
                label=label,
                value=row["value"],
                weekday="周末",
            )
    return output


def build_decrease_ratio_points(df: pd.DataFrame) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output
    work = df.dropna(subset=["price_increase_houses", "price_decrease_houses"]).copy()
    work = work[work["price_increase_houses"] > 0]
    work["decrease_ratio"] = work["price_decrease_houses"] / work["price_increase_houses"]
    for _, row in work.iterrows():
        append_point(
            output,
            x=row["trade_date"],
            label=row["trade_date"],
            value=row["decrease_ratio"],
        )
    return output


def build_daily_online_signing_points(df: pd.DataFrame) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output
    for _, row in df.iterrows():
        append_point(
            output,
            x=row["trade_date"],
            label=row["trade_date"],
            value=row["second_hand_online_signings"],
        )
    return output


def load_monthly_online_signing_df(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT
            trade_month,
            second_hand_online_signings
        FROM beijing_real_estate_monthly_info
        ORDER BY trade_month
        """
    ).fetchall()
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return df
    df["month_date"] = pd.to_datetime(df["trade_month"] + "-01", errors="coerce")
    df["second_hand_online_signings"] = pd.to_numeric(df["second_hand_online_signings"], errors="coerce")
    return df.dropna(subset=["month_date"]).sort_values("trade_month").reset_index(drop=True)


def build_monthly_online_signing_points(df: pd.DataFrame) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output
    for _, row in df.iterrows():
        append_point(
            output,
            x=f"{row['trade_month']}-01",
            label=row["trade_month"],
            value=row["second_hand_online_signings"],
        )
    return output


def load_credit_monthly_df(conn: sqlite3.Connection) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT
            trade_month,
            residents_loan_balance,
            residents_demand_deposits
        FROM beijing_residents_credit_monthly_info
        ORDER BY trade_month
        """
    ).fetchall()
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return df

    df["month_date"] = pd.to_datetime(df["trade_month"] + "-01", errors="coerce")
    df = df.dropna(subset=["month_date"]).copy()
    df["residents_loan_balance"] = pd.to_numeric(df["residents_loan_balance"], errors="coerce")
    df["residents_demand_deposits"] = pd.to_numeric(df["residents_demand_deposits"], errors="coerce")
    df["year"] = df["month_date"].dt.year
    df["month"] = df["month_date"].dt.month
    return df.sort_values("trade_month").reset_index(drop=True)


def enrich_credit_monthly_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    work = df.copy()
    balance_by_month = dict(zip(work["trade_month"], work["residents_loan_balance"]))
    loan_balance_yoy = []
    loan_net_increase = []

    for _, row in work.iterrows():
        current_balance = safe_float(row["residents_loan_balance"])
        prev_year_key = f"{int(row['year']) - 1}-{int(row['month']):02d}"
        prev_month_date = row["month_date"] - pd.DateOffset(months=1)
        prev_month_key = prev_month_date.strftime("%Y-%m")
        prev_year_balance = safe_float(balance_by_month.get(prev_year_key))
        prev_month_balance = safe_float(balance_by_month.get(prev_month_key))

        if current_balance is not None and prev_year_balance not in (None, 0):
            loan_balance_yoy.append((current_balance - prev_year_balance) / prev_year_balance)
        else:
            loan_balance_yoy.append(None)

        if current_balance is not None and prev_month_balance is not None:
            loan_net_increase.append(current_balance - prev_month_balance)
        else:
            loan_net_increase.append(None)

    work["loan_balance_yoy"] = pd.to_numeric(loan_balance_yoy, errors="coerce")
    work["loan_net_increase"] = pd.to_numeric(loan_net_increase, errors="coerce")
    work["total_loan_net_increase"] = (
        work.sort_values("trade_month")
        .groupby("year")["loan_net_increase"]
        .cumsum()
    )
    return work


def build_credit_yoy_points(df: pd.DataFrame, start_month: str) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output
    work = df[df["trade_month"] >= start_month].copy()
    for _, row in work.iterrows():
        append_point(
            output,
            x=f"{row['trade_month']}-01",
            label=row["trade_month"],
            value=row["loan_balance_yoy"],
        )
    return output


def build_credit_month_group_points(
    df: pd.DataFrame,
    start_month: str,
    value_column: str,
) -> list[dict]:
    output: list[dict] = []
    if df.empty:
        return output
    work = df[df["trade_month"] >= start_month].copy()
    for _, row in work.iterrows():
        append_point(
            output,
            x=int(row["year"]),
            label=str(int(row["year"])),
            value=row[value_column],
            month=int(row["month"]),
            year=int(row["year"]),
        )
    return output


def build_dashboard_payload(conn: sqlite3.Connection, start_date: str) -> dict:
    daily_df = load_daily_market_df(conn, start_date)
    credit_df = enrich_credit_monthly_df(load_credit_monthly_df(conn))
    monthly_df = load_monthly_online_signing_df(conn)
    start_month = start_date[:7]

    payload = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "startDate": start_date,
        "startMonth": start_month,
        "houseViewPeopleByWeekday": build_weekday_points(daily_df, "house_view_people"),
        "lianjiaDealsByWeekday": build_weekday_points(daily_df, "lianjia_deals"),
        "decreaseRatio": build_decrease_ratio_points(daily_df),
        "dailyOnlineSignings": build_daily_online_signing_points(daily_df),
        "monthlyOnlineSignings": build_monthly_online_signing_points(monthly_df),
        "creditYoy": build_credit_yoy_points(credit_df, start_month),
        "loanNetIncreaseByMonth": build_credit_month_group_points(
            credit_df,
            start_month,
            "loan_net_increase",
        ),
        "totalLoanNetIncreaseByMonth": build_credit_month_group_points(
            credit_df,
            start_month,
            "total_loan_net_increase",
        ),
        "weekdayOrder": CHART_WEEKDAY_ORDER,
    }
    return payload


def generate_html(payload: dict, output_dir: str, output_name: str) -> Path:
    out_dir = resolve_project_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / output_name
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    safe_title = html.escape(PAGE_TITLE)
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
      --danger: #bd3c2f;
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
      color: var(--text-soft);
      font-size: 13px;
    }
    main {
      max-width: 2400px;
      margin: 0 auto;
      padding: 0 40px 48px;
    }
    .tabs, .subtabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }
    .subtabs {
      margin-top: 4px;
      margin-bottom: 20px;
      border-bottom-color: var(--grid);
    }
    .tab-button, .subtab-button {
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
      white-space: nowrap;
    }
    .subtab-button {
      font-size: 13px;
      padding: 8px 16px;
    }
    .tab-button:hover, .subtab-button:hover {
      background: rgba(0, 117, 74, 0.08);
      color: var(--accent);
    }
    .tab-button[aria-selected="true"], .subtab-button[aria-selected="true"] {
      background: var(--accent);
      color: #ffffff;
      font-weight: 600;
    }
    .tab-button[aria-selected="true"]:hover, .subtab-button[aria-selected="true"]:hover {
      background: var(--accent-2);
    }
    .tab-panel, .subtab-panel {
      display: none;
    }
    .tab-panel.active, .subtab-panel.active {
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
      gap: 16px;
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
      color: var(--danger);
      font-size: 13px;
      font-weight: 600;
      text-align: right;
      white-space: nowrap;
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
    .threshold-line {
      stroke: var(--danger);
      stroke-width: 1.2;
      stroke-dasharray: 4 4;
      opacity: 0.75;
    }
    .threshold-dot {
      fill: var(--danger);
      opacity: 0.8;
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
    .swatch-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--danger);
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
    @media (max-width: 768px) {
      header { padding: 32px 20px 24px; }
      h1 { font-size: 26px; }
      main { padding: 0 20px 32px; }
      .tabs, .subtabs { overflow-x: auto; flex-wrap: nowrap; padding-bottom: 12px; }
      .tab-button { padding: 8px 16px; font-size: 13px; }
      .subtab-button { padding: 7px 14px; font-size: 12px; }
      .chart-card { padding: 16px; }
      .chart { height: 320px; }
      .chart-header { align-items: flex-start; flex-direction: column; }
      .chart-latest { white-space: normal; text-align: left; }
    }
  </style>
</head>
<body>
  <header>
    <h1>北京房产市场脉搏</h1>
  </header>
  <main>
    <nav class="tabs" aria-label="图表分类">
      <button class="tab-button" type="button" data-tab="houseViewPanel" aria-selected="true">看房人数趋势</button>
      <button class="tab-button" type="button" data-tab="decreaseRatioPanel" aria-selected="false">房东调价跌涨比趋势</button>
      <button class="tab-button" type="button" data-tab="lianjiaDealsPanel" aria-selected="false">大中介成交量趋势</button>
      <button class="tab-button" type="button" data-tab="onlineSigningsPanel" aria-selected="false">二手房网签量趋势</button>
      <button class="tab-button" type="button" data-tab="creditPanel" aria-selected="false">北京居民贷款趋势</button>
    </nav>

    <div class="tab-panel active" id="houseViewPanel"></div>
    <div class="tab-panel" id="decreaseRatioPanel"></div>
    <div class="tab-panel" id="lianjiaDealsPanel"></div>
    <div class="tab-panel" id="onlineSigningsPanel"></div>
    <div class="tab-panel" id="creditPanel">
      <nav class="subtabs" aria-label="北京居民贷款趋势子分类">
        <button class="subtab-button" type="button" data-subtab="creditYoyPanel" aria-selected="true">居民贷款余额增速</button>
        <button class="subtab-button" type="button" data-subtab="creditMonthlyIncreasePanel" aria-selected="false">月度居民贷款增量</button>
        <button class="subtab-button" type="button" data-subtab="creditYtdIncreasePanel" aria-selected="false">年度累计居民贷款增量</button>
      </nav>
      <div class="subtab-panel active" id="creditYoyPanel"></div>
      <div class="subtab-panel" id="creditMonthlyIncreasePanel"></div>
      <div class="subtab-panel" id="creditYtdIncreasePanel"></div>
    </div>
  </main>
  <script>
    const payload = __PAYLOAD__;
    const colors = ["#00754A", "#006241", "#cba258", "#2b5148", "#4a7c6f", "#8b6f4e", "#3d7a6a", "#a08040"];
    const monthNames = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
    const renderedTabs = new Set();

    document.querySelectorAll(".tab-button").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab-button").forEach(item => item.setAttribute("aria-selected", String(item === button)));
        document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.toggle("active", panel.id === button.dataset.tab));
        renderTab(button.dataset.tab);
      });
    });

    document.querySelectorAll(".subtab-button").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".subtab-button").forEach(item => item.setAttribute("aria-selected", String(item === button)));
        document.querySelectorAll(".subtab-panel").forEach(panel => panel.classList.toggle("active", panel.id === button.dataset.subtab));
        renderCreditSubTab(button.dataset.subtab);
      });
    });

    function fmtNumber(value, digits = 0) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "-";
      return num.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
    }

    function fmtRatio(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "-";
      return num.toFixed(2);
    }

    function fmtPercent(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "-";
      return (num * 100).toFixed(2) + "%";
    }

    function fmtSignedNumber(value, digits = 2) {
      const num = Number(value);
      if (!Number.isFinite(num)) return "-";
      const sign = num > 0 ? "+" : "";
      return sign + fmtNumber(num, digits);
    }

    function parseXValue(value, kind) {
      if (kind === "year") return Number(value);
      return new Date(String(value) + "T00:00:00").getTime();
    }

    function formatXTick(value, kind) {
      if (kind === "year") return String(Math.round(value));
      const date = new Date(value);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      if (kind === "month") return `${year}-${month}`;
      return `${year}-${month}`;
    }

    function extent(values) {
      const nums = values.map(Number).filter(Number.isFinite);
      return nums.length ? [Math.min(...nums), Math.max(...nums)] : [0, 1];
    }

    function niceDomain(min, max, forceZeroMin = false) {
      if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
      if (forceZeroMin) min = Math.min(0, min);
      if (min === max) {
        const pad = Math.max(Math.abs(min || 1) * 0.12, 1);
        return [forceZeroMin ? 0 : min - pad, max + pad];
      }
      const span = max - min;
      const pad = Math.max(span * 0.08, Math.abs(max || 1) * 0.01, 0.0001);
      return [forceZeroMin ? 0 : min - pad, max + pad];
    }

    function ticks(min, max, count) {
      if (count <= 1) return [min];
      if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
      if (min === max) return [min];
      return Array.from({ length: count }, (_, index) => min + (max - min) * index / (count - 1));
    }

    function buildXTicks(xValues, kind, plotW) {
      const values = [...new Set(xValues.map(Number).filter(Number.isFinite))].sort((a, b) => a - b);
      if (!values.length) return [0, 1];
      if (kind === "year") {
        const step = Math.max(1, Math.ceil(values.length / Math.max(2, Math.floor(plotW / 120))));
        return values.filter((_, index) => index % step === 0 || index === values.length - 1);
      }
      const [min, max] = extent(values);
      return ticks(min, max, Math.min(7, Math.max(2, Math.floor(plotW / 140))));
    }

    function makeSvg(container) {
      container.innerHTML = "";
      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
      gradient.setAttribute("id", `areaGradient-${container.id}`);
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
      return { svg, tooltip, gradientId: `areaGradient-${container.id}` };
    }

    function setAttrs(node, attrs) {
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    }

    function make(tag, attrs = {}, text = "") {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      setAttrs(node, attrs);
      if (text !== "") node.textContent = text;
      return node;
    }

    function buildAreaPath(points, xScale, yScale, yBottom, xKind) {
      if (!points.length) return "";
      const sorted = [...points].sort((a, b) => parseXValue(a.x, xKind) - parseXValue(b.x, xKind));
      const first = sorted[0];
      const last = sorted[sorted.length - 1];
      let d = `M${xScale(parseXValue(first.x, xKind)).toFixed(2)},${yBottom}`;
      sorted.forEach(point => {
        d += ` L${xScale(parseXValue(point.x, xKind)).toFixed(2)},${yScale(Number(point.value)).toFixed(2)}`;
      });
      d += ` L${xScale(parseXValue(last.x, xKind)).toFixed(2)},${yBottom} Z`;
      return d;
    }

    function renderLineChart(options) {
      const container = document.getElementById(options.containerId);
      const legend = document.getElementById(options.legendId);
      const latest = document.getElementById(options.latestId);
      const xKind = options.xKind || "date";
      const rawSeries = options.series
        .map(series => ({
          ...series,
          points: series.points
            .filter(point => Number.isFinite(Number(point.value)) && Number.isFinite(parseXValue(point.x, xKind)))
            .sort((a, b) => parseXValue(a.x, xKind) - parseXValue(b.x, xKind))
        }))
        .filter(series => series.points.length);

      if (!rawSeries.length) {
        container.innerHTML = '<div class="empty"><svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>暂无可绘制数据</div>';
        legend.innerHTML = "";
        latest.textContent = "";
        return;
      }

      const { svg, tooltip, gradientId } = makeSvg(container);
      const width = container.clientWidth || 900;
      const height = container.clientHeight || 380;
      setAttrs(svg, { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": options.title });

      const margin = { top: 20, right: 28, bottom: 48, left: options.leftMargin || 82 };
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const allPoints = rawSeries.flatMap(series => series.points.map(point => ({ ...point, series: series.name })));
      const xValues = allPoints.map(point => parseXValue(point.x, xKind));
      let [xMin, xMax] = extent(xValues);
      if (xMin === xMax) {
        const pad = xKind === "year" ? 1 : 24 * 60 * 60 * 1000;
        xMin -= pad;
        xMax += pad;
      }

      const yValues = rawSeries.flatMap(series => series.points.map(point => Number(point.value)));
      if (options.scatterReferenceValue !== undefined) yValues.push(Number(options.scatterReferenceValue));
      if (Array.isArray(options.referenceLines)) options.referenceLines.forEach(value => yValues.push(Number(value)));
      const [actualYMin, actualYMax] = extent(yValues);
      const [yMin, yMax] = options.yDomain || niceDomain(actualYMin, actualYMax, options.yDomainMode === "zeroMin");
      const ySpan = Math.abs(yMax - yMin) > 1e-12 ? yMax - yMin : 1;
      const xSpan = Math.abs(xMax - xMin) > 1e-12 ? xMax - xMin : 1;
      const xScale = value => margin.left + ((value - xMin) / xSpan) * plotW;
      const yScale = value => margin.top + (1 - (value - yMin) / ySpan) * plotH;
      const clampY = value => Math.min(height - margin.bottom, Math.max(margin.top, value));
      const yTicks = options.yTicks || ticks(yMin, yMax, 5);
      const xTicks = buildXTicks(xValues, xKind, plotW);

      const grid = make("g", { class: "grid" });
      yTicks.forEach(value => {
        const y = yScale(value);
        grid.appendChild(make("line", { x1: margin.left, x2: width - margin.right, y1: y, y2: y }));
      });
      svg.appendChild(grid);

      const references = make("g", { class: "references" });
      (options.referenceLines || []).forEach(value => {
        if (!Number.isFinite(Number(value))) return;
        const y = yScale(Number(value));
        references.appendChild(make("line", { class: "reference-line", x1: margin.left, x2: width - margin.right, y1: y, y2: y }));
      });
      if (options.scatterReferenceValue !== undefined && Number.isFinite(Number(options.scatterReferenceValue))) {
        const y = yScale(Number(options.scatterReferenceValue));
        references.appendChild(make("line", { class: "threshold-line", x1: margin.left, x2: width - margin.right, y1: y, y2: y }));
        const uniqueX = [...new Set(xValues.map(value => Number(value)))].sort((a, b) => a - b);
        const maxDots = 160;
        const step = Math.max(1, Math.ceil(uniqueX.length / maxDots));
        uniqueX.forEach((value, index) => {
          if (index % step !== 0 && index !== uniqueX.length - 1) return;
          references.appendChild(make("circle", { class: "threshold-dot", cx: xScale(value), cy: y, r: 2.5 }));
        });
      }
      svg.appendChild(references);

      const axis = make("g", { class: "axis" });
      yTicks.forEach(value => {
        const y = yScale(value);
        axis.appendChild(make("text", { x: margin.left - 12, y: y + 4, "text-anchor": "end" }, options.yFormat(value)));
      });
      xTicks.forEach(value => {
        const x = xScale(value);
        axis.appendChild(make("text", { x, y: height - 16, "text-anchor": "middle" }, formatXTick(value, xKind)));
      });
      axis.appendChild(make("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom }));
      axis.appendChild(make("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom }));
      svg.appendChild(axis);

      if (options.areaSeries) {
        const areaSeries = rawSeries.find(series => series.name === options.areaSeries);
        if (areaSeries) {
          svg.appendChild(make("path", {
            class: "area-fill",
            d: buildAreaPath(areaSeries.points, xScale, value => clampY(yScale(value)), height - margin.bottom, xKind),
            fill: `url(#${gradientId})`
          }));
        }
      }

      rawSeries.forEach((series, index) => {
        const d = series.points.map((point, pointIndex) => {
          const command = pointIndex === 0 ? "M" : "L";
          return `${command}${xScale(parseXValue(point.x, xKind)).toFixed(2)},${clampY(yScale(Number(point.value))).toFixed(2)}`;
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

      const byX = new Map();
      allPoints.forEach(point => {
        const key = String(point.x);
        if (!byX.has(key)) byX.set(key, []);
        byX.get(key).push(point);
      });
      const xKeys = Array.from(byX.keys()).sort((a, b) => parseXValue(a, xKind) - parseXValue(b, xKind));
      const xTimes = xKeys.map(key => parseXValue(key, xKind));

      overlay.addEventListener("mousemove", event => {
        const rect = svg.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const xValue = xMin + (Math.min(Math.max(mouseX, margin.left), width - margin.right) - margin.left) / plotW * (xMax - xMin);
        let nearestIndex = 0;
        let nearestDistance = Infinity;
        xTimes.forEach((item, index) => {
          const distance = Math.abs(item - xValue);
          if (distance < nearestDistance) {
            nearestDistance = distance;
            nearestIndex = index;
          }
        });
        const key = xKeys[nearestIndex];
        const points = byX.get(key) || [];
        const x = xScale(xTimes[nearestIndex]);
        setAttrs(hoverLine, { x1: x, x2: x, opacity: 1 });
        tooltip.innerHTML = options.tooltip(points[0]?.label || key, points);
        tooltip.style.display = "block";
        const left = Math.min(Math.max(x + 16, 12), width - 300);
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${Math.max(12, event.clientY - rect.top - 24)}px`;
      });
      overlay.addEventListener("mouseleave", () => {
        tooltip.style.display = "none";
        setAttrs(hoverLine, { opacity: 0 });
      });

      const legendItems = rawSeries.map((series, index) => {
        const color = series.color || colors[index % colors.length];
        return `<span><i class="swatch" style="background:${color}"></i>${series.name}</span>`;
      });
      if (options.scatterReferenceValue !== undefined) {
        legendItems.push(`<span><i class="swatch-dot"></i>${options.referenceLabel || "参考线"}：${options.yFormat(Number(options.scatterReferenceValue))}</span>`);
      }
      legend.innerHTML = legendItems.join("");

      const lastKey = xKeys[xKeys.length - 1];
      latest.textContent = options.latestText(pointsLabel(lastKey, byX.get(lastKey)), byX.get(lastKey));
    }

    function pointsLabel(key, points) {
      return points && points[0] ? points[0].label : key;
    }

    function emptyPanel(panelId) {
      const panel = document.getElementById(panelId);
      panel.innerHTML = '<div class="empty"><svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>暂无可绘制数据</div>';
    }

    function cardHtml(id, title) {
      return `
        <div class="chart-card">
          <div class="chart-header">
            <h2 class="chart-title">${title}</h2>
            <div class="chart-latest" id="${id}Latest"></div>
          </div>
          <div class="chart" id="${id}Chart"></div>
          <div class="legend" id="${id}Legend"></div>
        </div>
      `;
    }

    function groupBy(rows, key) {
      const result = new Map();
      rows.forEach(row => {
        const groupKey = row[key];
        if (!result.has(groupKey)) result.set(groupKey, []);
        result.get(groupKey).push(row);
      });
      return result;
    }

    function renderWeekdayCharts({ panelId, rows, titleSuffix, valueName, yFormat, tooltipUnit }) {
      if (!rows.length) {
        emptyPanel(panelId);
        return;
      }
      const panel = document.getElementById(panelId);
      const grouped = groupBy(rows, "weekday");
      const labels = payload.weekdayOrder || ["周一", "周二", "周三", "周四", "周五", "周末"];
      panel.innerHTML = labels.map((label, index) => cardHtml(`${panelId}Chart${index}`, `${label}${titleSuffix}`)).join("");
      labels.forEach((label, index) => {
        const points = (grouped.get(label) || []).sort((a, b) => String(a.x).localeCompare(String(b.x)));
        renderLineChart({
          containerId: `${panelId}Chart${index}Chart`,
          legendId: `${panelId}Chart${index}Legend`,
          latestId: `${panelId}Chart${index}Latest`,
          title: `${label}${titleSuffix}`,
          xKind: "date",
          yDomainMode: "zeroMin",
          areaSeries: valueName,
          series: [{ name: valueName, color: "#00754A", points }],
          yFormat,
          tooltip: (labelText, items) => `<strong>${labelText}</strong>${valueName}：${yFormat(items[0]?.value || 0)}${tooltipUnit}`,
          latestText: (labelText, items) => `${labelText}　${valueName} ${yFormat(items[0]?.value || 0)}${tooltipUnit}`,
          ...(label === "周末" && panelId === "lianjiaDealsPanel" ? { scatterReferenceValue: 1200, referenceLabel: "周末荣枯线" } : {})
        });
      });
    }

    function renderHouseViewCharts() {
      if (renderedTabs.has("houseViewPanel")) return;
      renderedTabs.add("houseViewPanel");
      renderWeekdayCharts({
        panelId: "houseViewPanel",
        rows: payload.houseViewPeopleByWeekday || [],
        titleSuffix: "看房人数",
        valueName: "看房人数",
        yFormat: value => fmtNumber(value, 0),
        tooltipUnit: "人"
      });
    }

    function renderDecreaseRatioChart() {
      if (renderedTabs.has("decreaseRatioPanel")) return;
      renderedTabs.add("decreaseRatioPanel");
      const panel = document.getElementById("decreaseRatioPanel");
      panel.innerHTML = cardHtml("decreaseRatio", "房东调价跌涨比");
      renderLineChart({
        containerId: "decreaseRatioChart",
        legendId: "decreaseRatioLegend",
        latestId: "decreaseRatioLatest",
        title: "房东调价跌涨比",
        xKind: "date",
        yDomainMode: "zeroMin",
        lineWidth: 2.5,
        series: [{ name: "跌涨比", color: "#00754A", points: payload.decreaseRatio || [] }],
        scatterReferenceValue: 10,
        referenceLabel: "参考线",
        yFormat: fmtRatio,
        tooltip: (labelText, items) => `<strong>${labelText}</strong>跌涨比：${fmtRatio(items[0]?.value || 0)}`,
        latestText: (labelText, items) => `${labelText}　跌涨比 ${fmtRatio(items[0]?.value || 0)}`
      });
    }

    function renderLianjiaDealCharts() {
      if (renderedTabs.has("lianjiaDealsPanel")) return;
      renderedTabs.add("lianjiaDealsPanel");
      renderWeekdayCharts({
        panelId: "lianjiaDealsPanel",
        rows: payload.lianjiaDealsByWeekday || [],
        titleSuffix: "大中介成交量",
        valueName: "大中介成交量",
        yFormat: value => fmtNumber(value, 0),
        tooltipUnit: "套"
      });
    }

    function renderOnlineSigningCharts() {
      if (renderedTabs.has("onlineSigningsPanel")) return;
      renderedTabs.add("onlineSigningsPanel");
      const panel = document.getElementById("onlineSigningsPanel");
      panel.innerHTML = cardHtml("dailyOnlineSignings", "每日二手房网签量") + cardHtml("monthlyOnlineSignings", "每月二手房网签量");
      renderLineChart({
        containerId: "dailyOnlineSigningsChart",
        legendId: "dailyOnlineSigningsLegend",
        latestId: "dailyOnlineSigningsLatest",
        title: "每日二手房网签量",
        xKind: "date",
        yDomainMode: "zeroMin",
        areaSeries: "每日二手房网签量",
        series: [{ name: "每日二手房网签量", color: "#00754A", points: payload.dailyOnlineSignings || [] }],
        yFormat: value => fmtNumber(value, 0),
        tooltip: (labelText, items) => `<strong>${labelText}</strong>网签量：${fmtNumber(items[0]?.value || 0, 0)}套`,
        latestText: (labelText, items) => `${labelText}　网签量 ${fmtNumber(items[0]?.value || 0, 0)}套`
      });
      renderLineChart({
        containerId: "monthlyOnlineSigningsChart",
        legendId: "monthlyOnlineSigningsLegend",
        latestId: "monthlyOnlineSigningsLatest",
        title: "每月二手房网签量",
        xKind: "month",
        yDomainMode: "zeroMin",
        areaSeries: "每月二手房网签量",
        series: [{ name: "每月二手房网签量", color: "#00754A", points: payload.monthlyOnlineSignings || [] }],
        scatterReferenceValue: 12000,
        referenceLabel: "荣枯线",
        yFormat: value => fmtNumber(value, 0),
        tooltip: (labelText, items) => `<strong>${labelText}</strong>月度网签量：${fmtNumber(items[0]?.value || 0, 0)}套`,
        latestText: (labelText, items) => `${labelText}　月度网签量 ${fmtNumber(items[0]?.value || 0, 0)}套`
      });
    }

    function renderCreditYoyChart() {
      if (renderedTabs.has("creditYoyPanel")) return;
      renderedTabs.add("creditYoyPanel");
      const panel = document.getElementById("creditYoyPanel");
      panel.innerHTML = cardHtml("creditYoy", "居民贷款余额增速");
      renderLineChart({
        containerId: "creditYoyChart",
        legendId: "creditYoyLegend",
        latestId: "creditYoyLatest",
        title: "居民贷款余额增速",
        xKind: "month",
        lineWidth: 2.5,
        series: [{ name: "居民贷款余额同比增速", color: "#00754A", points: payload.creditYoy || [] }],
        scatterReferenceValue: 0,
        referenceLabel: "荣枯线",
        yFormat: fmtPercent,
        tooltip: (labelText, items) => `<strong>${labelText}</strong>同比增速：${fmtPercent(items[0]?.value || 0)}`,
        latestText: (labelText, items) => `${labelText}　同比增速 ${fmtPercent(items[0]?.value || 0)}`
      });
    }

    function renderMonthGroupCharts({ panelId, rows, valueName, titleBuilder, valueFormatter }) {
      if (!rows.length) {
        emptyPanel(panelId);
        return;
      }
      const panel = document.getElementById(panelId);
      panel.innerHTML = monthNames.map((name, index) => cardHtml(`${panelId}Month${index + 1}`, titleBuilder(index + 1))).join("");
      const grouped = groupBy(rows, "month");
      for (let month = 1; month <= 12; month += 1) {
        const points = (grouped.get(month) || []).sort((a, b) => Number(a.x) - Number(b.x));
        renderLineChart({
          containerId: `${panelId}Month${month}Chart`,
          legendId: `${panelId}Month${month}Legend`,
          latestId: `${panelId}Month${month}Latest`,
          title: titleBuilder(month),
          xKind: "year",
          lineWidth: 2.5,
          series: [{ name: valueName, color: "#00754A", points }],
          scatterReferenceValue: 0,
          referenceLabel: "荣枯线",
          yFormat: value => valueFormatter(value),
          tooltip: (labelText, items) => `<strong>${labelText}</strong>${valueName}：${valueFormatter(items[0]?.value || 0)}亿元`,
          latestText: (labelText, items) => `${labelText}　${valueName} ${valueFormatter(items[0]?.value || 0)}亿元`
        });
      }
    }

    function renderCreditMonthlyIncreaseCharts() {
      if (renderedTabs.has("creditMonthlyIncreasePanel")) return;
      renderedTabs.add("creditMonthlyIncreasePanel");
      renderMonthGroupCharts({
        panelId: "creditMonthlyIncreasePanel",
        rows: payload.loanNetIncreaseByMonth || [],
        valueName: "当月居民贷款增量",
        titleBuilder: month => `${month}月当月居民贷款增量`,
        valueFormatter: value => fmtSignedNumber(value, 2)
      });
    }

    function renderCreditYtdIncreaseCharts() {
      if (renderedTabs.has("creditYtdIncreasePanel")) return;
      renderedTabs.add("creditYtdIncreasePanel");
      renderMonthGroupCharts({
        panelId: "creditYtdIncreasePanel",
        rows: payload.totalLoanNetIncreaseByMonth || [],
        valueName: "当年累计居民贷款增量",
        titleBuilder: month => `1-${month}月居民贷款增量`,
        valueFormatter: value => fmtSignedNumber(value, 2)
      });
    }

    function renderCreditSubTab(subtabId) {
      if (subtabId === "creditYoyPanel") {
        renderCreditYoyChart();
      } else if (subtabId === "creditMonthlyIncreasePanel") {
        renderCreditMonthlyIncreaseCharts();
      } else if (subtabId === "creditYtdIncreasePanel") {
        renderCreditYtdIncreaseCharts();
      }
    }

    function renderTab(tabId) {
      if (tabId === "houseViewPanel") {
        renderHouseViewCharts();
      } else if (tabId === "decreaseRatioPanel") {
        renderDecreaseRatioChart();
      } else if (tabId === "lianjiaDealsPanel") {
        renderLianjiaDealCharts();
      } else if (tabId === "onlineSigningsPanel") {
        renderOnlineSigningCharts();
      } else if (tabId === "creditPanel") {
        const activeSubtab = document.querySelector(".subtab-button[aria-selected='true']")?.dataset.subtab || "creditYoyPanel";
        renderCreditSubTab(activeSubtab);
      }
    }

    window.addEventListener("resize", () => {
      clearTimeout(window.__resizeTimer);
      window.__resizeTimer = setTimeout(() => location.reload(), 200);
    });

    requestAnimationFrame(() => renderTab("houseViewPanel"));
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    setup_logging()
    validate_date(args.start_date)
    conn = init_db(args.db_path)
    try:
        payload = build_dashboard_payload(conn, args.start_date)
        output_path = generate_html(payload, args.output_dir, args.output_name)
        print(output_path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

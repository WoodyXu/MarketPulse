import logging
import os
import warnings
from datetime import datetime
from io import BytesIO
from pathlib import Path

import akshare as ak
import pandas as pd
import requests

try:
    import tushare as ts
except ImportError:
    ts = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)

YUAN_PER_100M = 100_000_000
MAX_STALE_CALENDAR_DAYS = 14
REQUEST_SLEEP_SECONDS = 1.0
TUSHARE_TOKEN_ENV = "TUSHARE_TOKEN"
TUSHARE_DAILY_INFO_FIELDS = "ts_code,ts_name,float_mv,amount"
SSE_STOCK_BOARD_COLUMNS = ["主板A", "主板B", "科创板"]


def load_env_file(env_path: Path = PROJECT_ROOT / ".env") -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_tushare_pro():
    load_env_file()
    token = os.environ.get(TUSHARE_TOKEN_ENV, "").strip()
    if not token:
        return None
    if ts is None:
        LOGGER.warning("已配置 TUSHARE_TOKEN，但本地未安装 tushare，将使用备选数据源")
        return None
    return ts.pro_api(token)


def to_float(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value or value == "-":
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_date(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def make_market_info(float_mv_yuan, amount_yuan):
    if float_mv_yuan is None and amount_yuan is None:
        return None
    return {
        "float_mv_yuan": float(float_mv_yuan) if float_mv_yuan is not None else None,
        "amount_yuan": float(amount_yuan) if amount_yuan is not None else None,
    }


def fetch_sh_sz_daily_float_mv_amount_from_tushare(trade_date: str, tushare_pro):
    if tushare_pro is None:
        return {}
    try:
        df = tushare_pro.daily_info(
            trade_date=trade_date.replace("-", ""),
            exchange="SH,SZ",
            fields=TUSHARE_DAILY_INFO_FIELDS,
        )
        if df is None or df.empty:
            LOGGER.warning("%s Tushare SH,SZ daily_info 返回空数据", trade_date)
            return {}
        return {
            "SH": extract_sh_tushare_market_info(df, trade_date),
            "SZ": extract_sz_tushare_market_info(df, trade_date),
        }
    except Exception as exc:
        LOGGER.warning("%s Tushare SH,SZ daily_info 获取失败：%s", trade_date, exc)
        return {}


def extract_sh_tushare_market_info(df: pd.DataFrame, trade_date: str):
    required_columns = {"ts_code", "float_mv", "amount"}
    if not required_columns.issubset(df.columns):
        LOGGER.warning("%s Tushare SH daily_info 缺少必要字段：%s", trade_date, list(df.columns))
        return None

    rows = df.copy()
    rows["ts_code"] = rows["ts_code"].astype(str).str.upper()
    board_rows = rows[rows["ts_code"].isin(["SH_A", "SH_B", "SH_STAR"])]
    if board_rows.empty:
        LOGGER.warning("%s Tushare SH daily_info 缺少 SH_A/SH_B/SH_STAR 行", trade_date)
        return None

    float_values = [to_float(value) for value in board_rows["float_mv"]]
    amount_values = [to_float(value) for value in board_rows["amount"]]
    float_mv = sum(value for value in float_values if value is not None)
    amount = sum(value for value in amount_values if value is not None)
    return make_market_info(float_mv * YUAN_PER_100M, amount * YUAN_PER_100M)


def extract_sz_tushare_market_info(df: pd.DataFrame, trade_date: str):
    required_columns = {"ts_code", "float_mv", "amount"}
    if not required_columns.issubset(df.columns):
        LOGGER.warning("%s Tushare SZ daily_info 缺少必要字段：%s", trade_date, list(df.columns))
        return None

    rows = df[df["ts_code"].astype(str).str.upper() == "SZ_MARKET"]
    if rows.empty:
        LOGGER.warning("%s Tushare SZ daily_info 缺少 SZ_MARKET 行", trade_date)
        return None
    row = rows.iloc[0]
    float_mv = to_float(row["float_mv"])
    amount = to_float(row["amount"])
    if float_mv is None and amount is None:
        LOGGER.warning("%s Tushare SZ_MARKET float_mv/amount 均为空", trade_date)
        return None
    return make_market_info(
        None if float_mv is None else float_mv * YUAN_PER_100M,
        None if amount is None else amount * YUAN_PER_100M,
    )


def extract_sse_deal_daily_metric(df: pd.DataFrame, metric_name: str):
    metric_row = df[df["单日情况"].astype(str).str.strip() == metric_name]
    if metric_row.empty:
        return None

    row = metric_row.iloc[0]
    metric_value = to_float(row.get("股票"))
    if metric_value is None:
        board_values = [to_float(row.get(column)) for column in SSE_STOCK_BOARD_COLUMNS]
        usable_values = [value for value in board_values if value is not None]
        metric_value = sum(usable_values) if usable_values else None
    return metric_value


def fetch_sh_daily_float_mv_amount_from_sse_official(trade_date: str):
    float_mv_yuan = None
    amount_yuan = None

    try:
        df = ak.stock_sse_deal_daily(date=trade_date.replace("-", ""))
        if df is None or df.empty:
            LOGGER.warning("%s 沪市每日股票情况接口返回空数据", trade_date)
        elif "单日情况" not in df.columns:
            LOGGER.warning("%s 沪市每日股票情况缺少 单日情况 字段：%s", trade_date, list(df.columns))
        else:
            market_cap = extract_sse_deal_daily_metric(df, "流通市值")
            if market_cap is not None:
                float_mv_yuan = market_cap * YUAN_PER_100M

            amount = extract_sse_deal_daily_metric(df, "成交金额")
            if amount is not None:
                amount_yuan = amount * YUAN_PER_100M
    except Exception as exc:
        LOGGER.warning("%s 沪市每日股票情况获取失败：%s", trade_date, exc)

    return make_market_info(float_mv_yuan, amount_yuan)


def fetch_sz_daily_float_mv_amount_from_szse_official(trade_date: str):
    try:
        response = requests.get(
            "https://www.szse.cn/api/report/ShowReport",
            params={
                "SHOWTYPE": "xlsx",
                "CATALOGID": "1803_sczm",
                "TABKEY": "tab1",
                "txtQueryDate": trade_date,
                "random": "0.39339437497296137",
            },
            headers={
                "Referer": "https://www.szse.cn/market/overview/index.html",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=20,
        )
        response.raise_for_status()
        if not response.content:
            LOGGER.warning("%s 深市总貌接口返回空内容", trade_date)
            return None
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Workbook contains no default style.*",
                category=UserWarning,
            )
            df = pd.read_excel(BytesIO(response.content), engine="openpyxl")
        return extract_szse_market_info(df, trade_date)
    except Exception as exc:
        LOGGER.warning("%s 深市总貌获取失败：%s", trade_date, exc)
        return None


def extract_szse_market_info(df: pd.DataFrame, trade_date: str):
    if df is None or df.empty:
        LOGGER.warning("%s 深市总貌接口返回空数据", trade_date)
        return None
    if len(df.columns) >= 5:
        df = df.iloc[:, :5].copy()
        df.columns = ["证券类别", "数量", "成交金额", "总市值", "流通市值"]
    required_columns = {"证券类别", "成交金额", "流通市值"}
    if not required_columns.issubset(df.columns):
        LOGGER.warning("%s 深市总貌缺少必要字段：%s", trade_date, list(df.columns))
        return None

    category = df["证券类别"].astype(str).str.strip()
    rows = df[category == "股票"]
    if rows.empty:
        rows = df[category.str.contains("股票|A股", regex=True, na=False)]
    if rows.empty:
        LOGGER.warning("%s 深市总貌缺少股票类别", trade_date)
        return None

    if len(rows) == 1:
        amount_yuan = to_float(rows.iloc[0]["成交金额"])
        float_mv_yuan = to_float(rows.iloc[0]["流通市值"])
    else:
        amount_values = [to_float(value) for value in rows["成交金额"]]
        float_mv_values = [to_float(value) for value in rows["流通市值"]]
        amount_usable = [value for value in amount_values if value is not None]
        float_mv_usable = [value for value in float_mv_values if value is not None]
        amount_yuan = sum(amount_usable) if amount_usable else None
        float_mv_yuan = sum(float_mv_usable) if float_mv_usable else None

    return make_market_info(float_mv_yuan, amount_yuan)


def fetch_sh_sz_full_margin_balance_from_akshare() -> list:
    LOGGER.info("获取融资余额历史数据")
    df = ak.stock_margin_account_info()
    if df is None or df.empty:
        raise ValueError("融资余额接口返回空数据")
    if "日期" not in df.columns or "融资余额" not in df.columns:
        raise ValueError(f"融资余额接口缺少 日期/融资余额 字段：{list(df.columns)}")

    records = []
    for _, row in df[["日期", "融资余额"]].dropna(subset=["日期", "融资余额"]).iterrows():
        margin_balance = to_float(row["融资余额"])
        if margin_balance is None:
            continue
        records.append(
            {
                "trade_date": normalize_date(row["日期"]),
                "total_margin_balance_yuan": margin_balance * YUAN_PER_100M,
            }
        )
    records.sort(key=lambda item: item["trade_date"])
    if not records:
        raise ValueError("融资余额接口标准化后无有效数据")
    return records


def fetch_index_full_from_akshare(index_name, index_code):
    market_type = index_name.split("-")[0]

    if market_type == "港股":
        data_sources = [
            (
                lambda symbol: ak.stock_hk_index_daily_sina(symbol=symbol),
                "stock_hk_index_daily_sina",
            )
        ]
    elif market_type == "A股":
        data_sources = [
            (lambda symbol: ak.stock_zh_index_daily(symbol=symbol), "stock_zh_index_daily"),
            (lambda symbol: ak.stock_zh_index_daily_tx(symbol=symbol), "stock_zh_index_daily_tx"),
        ]
    else:
        raise ValueError(f"不支持的指数类型：{index_name}")

    last_error = None
    for fetch_func, source_name in data_sources:
        try:
            LOGGER.info("尝试使用 %s 获取 %s (%s) 数据", source_name, index_name, index_code)
            df = fetch_func(index_code)
            records = normalize_index_daily_df(df, index_name, index_code, market_type, source_name)
            if records:
                latest_date = pd.Timestamp(records[-1]["trade_date"])
                stale_cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=MAX_STALE_CALENDAR_DAYS)
                if market_type == "A股" and latest_date < stale_cutoff:
                    LOGGER.warning(
                        "%s 获取 %s 数据成功但最新日期 %s 明显过期，继续尝试备选数据源",
                        source_name,
                        index_name,
                        records[-1]["trade_date"],
                    )
                    last_error = ValueError(f"{source_name} 最新日期明显过期：{records[-1]['trade_date']}")
                    continue
                LOGGER.info("成功使用 %s 获取 %s 数据：%s 条", source_name, index_name, len(records))
                return records
            raise ValueError("返回空数据")
        except Exception as exc:
            last_error = exc
            LOGGER.warning("%s 获取 %s (%s) 数据失败：%s", source_name, index_name, index_code, exc)
    raise RuntimeError(f"所有数据源都失败，放弃获取 {index_name} ({index_code}) 数据：{last_error}")


def normalize_index_daily_df(df, index_name, index_code, market_type, data_source):
    if df is None or df.empty:
        return []

    work_df = df.copy()
    if "date" not in work_df.columns or "close" not in work_df.columns:
        raise ValueError(f"{index_name} 缺少 date/close 字段：{list(work_df.columns)}")

    for column in ["open", "close", "high", "low", "volume", "amount"]:
        if column not in work_df.columns:
            work_df[column] = None
        work_df[column] = pd.to_numeric(work_df[column], errors="coerce")

    records = []
    for _, row in work_df.iterrows():
        if pd.isna(row["date"]) or pd.isna(row["close"]):
            continue
        close_value = None if pd.isna(row["close"]) else float(row["close"])
        records.append(
            {
                "index_name": index_name,
                "index_code": index_code,
                "market_type": market_type,
                "trade_date": normalize_date(row["date"]),
                "open": None if pd.isna(row["open"]) else float(row["open"]),
                "close": close_value,
                "high": None if pd.isna(row["high"]) else float(row["high"]),
                "low": None if pd.isna(row["low"]) else float(row["low"]),
                "volume": None if pd.isna(row["volume"]) else float(row["volume"]),
                "amount": None if pd.isna(row["amount"]) else float(row["amount"]),
                "data_source": data_source,
                "data_status": "complete" if close_value is not None else "partial",
            }
        )
    records.sort(key=lambda item: item["trade_date"])
    return records

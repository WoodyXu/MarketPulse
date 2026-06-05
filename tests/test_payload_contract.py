import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src import security_market_pulse
from src.beijing_real_estate_market_pulse import build_dashboard_payload as build_beijing_payload
from src.beijing_real_estate_market_pulse import init_db as init_beijing_db
from src.security_market_pulse import build_dashboard_payload as build_ashare_payload
from src.security_market_pulse import init_db as init_ashare_db


ASHARE_TOP_LEVEL_FIELDS = {
    "generatedAt",
    "startDate",
    "indexDeviation",
    "turnover",
    "margin",
    "topConcentration",
}
BEIJING_TOP_LEVEL_FIELDS = {
    "generatedAt",
    "startDate",
    "startMonth",
    "houseViewPeopleByWeekday",
    "lianjiaDealsByWeekday",
    "decreaseRatio",
    "dailyOnlineSignings",
    "monthlyOnlineSignings",
    "creditYoy",
    "loanNetIncreaseByMonth",
    "totalLoanNetIncreaseByMonth",
    "weekdayOrder",
}


class PayloadContractTest(unittest.TestCase):
    def test_ashare_payload_matches_field_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "market_data.sqlite"
            conn = init_ashare_db(str(db_path))
            try:
                seed_index_rows(conn)
                seed_ashare_rows(conn)
                with patch.object(
                    security_market_pulse,
                    "fetch_ashare_stock_code_name_from_akshare",
                    return_value="测试股票",
                ):
                    payload = build_ashare_payload(conn, "2024-01-01")
            finally:
                conn.close()

        self.assertEqual(set(payload), ASHARE_TOP_LEVEL_FIELDS)
        self.assertEqual(payload["startDate"], "2024-01-01")

        self.assertGreater(len(payload["indexDeviation"]), 0)
        self.assertEqual(
            set(payload["indexDeviation"][0]),
            {"date", "series", "close", "ma60", "deviation"},
        )

        self.assertGreater(len(payload["margin"]), 0)
        self.assertEqual(
            set(payload["margin"][0]),
            {"date", "marginBalance100m", "marginToMarketCap"},
        )

        self.assertGreater(len(payload["turnover"]), 0)
        self.assertEqual(
            set(payload["turnover"][0]),
            {"date", "totalAmount100m", "hs300Close"},
        )

        top_concentration = payload["topConcentration"]
        self.assertEqual(set(top_concentration), {"chart", "recentTables"})
        self.assertGreater(len(top_concentration["chart"]), 0)
        self.assertEqual(set(top_concentration["chart"][0]), {"date", "value"})
        self.assertGreater(len(top_concentration["recentTables"]), 0)
        recent_table = top_concentration["recentTables"][0]
        self.assertEqual(set(recent_table), {"date", "stocks"})
        self.assertEqual(
            set(recent_table["stocks"][0]),
            {"tsCode", "name", "amountYuan", "pctChg"},
        )

    def test_beijing_payload_matches_field_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "market_data.sqlite"
            create_beijing_schema(db_path)
            conn = init_beijing_db(str(db_path))
            try:
                seed_beijing_rows(conn)
                payload = build_beijing_payload(conn, "2024-01-01")
            finally:
                conn.close()

        self.assertEqual(set(payload), BEIJING_TOP_LEVEL_FIELDS)
        self.assertEqual(payload["startDate"], "2024-01-01")
        self.assertEqual(payload["startMonth"], "2024-01")

        for section_name in ["houseViewPeopleByWeekday", "lianjiaDealsByWeekday"]:
            self.assertGreater(len(payload[section_name]), 0)
            self.assertEqual(
                set(payload[section_name][0]),
                {"x", "label", "value", "weekday"},
            )

        for section_name in [
            "decreaseRatio",
            "dailyOnlineSignings",
            "monthlyOnlineSignings",
            "creditYoy",
        ]:
            self.assertGreater(len(payload[section_name]), 0)
            self.assertEqual(set(payload[section_name][0]), {"x", "label", "value"})

        for section_name in ["loanNetIncreaseByMonth", "totalLoanNetIncreaseByMonth"]:
            self.assertGreater(len(payload[section_name]), 0)
            self.assertEqual(
                set(payload[section_name][0]),
                {"x", "label", "value", "month", "year"},
            )

        self.assertEqual(payload["weekdayOrder"], ["周一", "周二", "周三", "周四", "周五", "周末"])


def seed_index_rows(conn: sqlite3.Connection) -> None:
    for index_name, index_code in [("A股-沪深300", "sh000300"), ("A股-测试指数", "sh000000")]:
        for day in range(70):
            trade_date = (date(2024, 1, 1) + timedelta(days=day)).strftime("%Y-%m-%d")
            close = 3000 + day
            conn.execute(
                """
                INSERT INTO index_daily_data (
                    index_name, index_code, market_type, trade_date,
                    open, close, high, low, volume, amount,
                    data_source, data_status, created_at, updated_at
                )
                VALUES (?, ?, 'A股', ?, ?, ?, ?, ?, ?, ?, 'test', 'complete', 'now', 'now')
                """,
                (index_name, index_code, trade_date, close, close, close, close, close, close),
            )
    conn.commit()


def seed_ashare_rows(conn: sqlite3.Connection) -> None:
    for day in range(65, 70):
        trade_date = (date(2024, 1, 1) + timedelta(days=day)).strftime("%Y-%m-%d")
        stock_json = json.dumps({"000001.SZ": [100000000.0 + day, 1.25]}, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO ashare_daily_market_data (
                trade_date,
                total_margin_balance_yuan,
                sse_amount_yuan,
                szse_amount_yuan,
                sse_circulating_market_cap_yuan,
                szse_circulating_market_cap_yuan,
                top5pct_concentration,
                top5_stocks
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_date,
                300000000000.0 + day,
                100000000000.0 + day,
                200000000000.0 + day,
                10000000000000.0,
                20000000000000.0,
                0.25,
                stock_json,
            ),
        )
    conn.commit()


def create_beijing_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE beijing_real_estate_daily_info (
                trade_date TEXT PRIMARY KEY,
                lianjia_deals REAL,
                second_hand_online_signings REAL,
                house_view_people REAL,
                price_increase_houses REAL,
                price_decrease_houses REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE beijing_real_estate_monthly_info (
                trade_month TEXT PRIMARY KEY,
                second_hand_online_signings REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE beijing_residents_credit_monthly_info (
                trade_month TEXT PRIMARY KEY,
                residents_loan_balance REAL,
                residents_demand_deposits REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_beijing_rows(conn: sqlite3.Connection) -> None:
    for day in range(10):
        trade_date = (date(2024, 1, 1) + timedelta(days=day)).strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO beijing_real_estate_daily_info (
                trade_date,
                lianjia_deals,
                second_hand_online_signings,
                house_view_people,
                price_increase_houses,
                price_decrease_houses
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (trade_date, 100 + day, 200 + day, 300 + day, 10 + day, 20 + day),
        )

    for trade_month, signings in [("2024-01", 1000), ("2024-02", 1200)]:
        conn.execute(
            """
            INSERT INTO beijing_real_estate_monthly_info (
                trade_month,
                second_hand_online_signings
            )
            VALUES (?, ?)
            """,
            (trade_month, signings),
        )

    credit_rows = [
        ("2023-01", 1000.0),
        ("2023-12", 1100.0),
        ("2024-01", 1250.0),
        ("2024-02", 1300.0),
    ]
    for trade_month, loan_balance in credit_rows:
        conn.execute(
            """
            INSERT INTO beijing_residents_credit_monthly_info (
                trade_month,
                residents_loan_balance,
                residents_demand_deposits
            )
            VALUES (?, ?, ?)
            """,
            (trade_month, loan_balance, 500.0),
        )
    conn.commit()


if __name__ == "__main__":
    unittest.main()

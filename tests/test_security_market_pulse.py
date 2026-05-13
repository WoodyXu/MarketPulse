import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.security_market_pulse import (
    build_dashboard_payload,
    generate_html,
    get_pending_ashare_market_dates,
    init_db,
    upsert_ashare_market_record,
)


class SecurityMarketPulseTest(unittest.TestCase):
    def test_pending_dates_merge_null_rows_and_dates_after_latest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(str(Path(tmpdir) / "market_data.sqlite"))
            try:
                conn.execute(
                    """
                    INSERT INTO ashare_daily_market_data (
                        trade_date, sse_amount_yuan, szse_amount_yuan,
                        sse_circulating_market_cap_yuan, szse_circulating_market_cap_yuan
                    )
                    VALUES
                        ('2024-01-02', 1, 2, NULL, 4),
                        ('2024-01-04', 1, 2, 3, 4)
                    """
                )
                conn.commit()

                pending = get_pending_ashare_market_dates(conn, "2024-01-01")

                self.assertIn("2024-01-02", pending)
                self.assertIn("2024-01-05", pending)
                self.assertEqual(pending, sorted(set(pending)))
            finally:
                conn.close()

    def test_upsert_ashare_market_record_keeps_existing_when_new_value_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(str(Path(tmpdir) / "market_data.sqlite"))
            try:
                upsert_ashare_market_record(
                    conn,
                    {
                        "trade_date": "2024-01-02",
                        "sse_amount_yuan": 100.0,
                        "szse_amount_yuan": 200.0,
                        "sse_circulating_market_cap_yuan": 300.0,
                        "szse_circulating_market_cap_yuan": 400.0,
                    },
                )
                conn.commit()

                upsert_ashare_market_record(
                    conn,
                    {
                        "trade_date": "2024-01-02",
                        "sse_amount_yuan": None,
                        "szse_amount_yuan": 250.0,
                        "sse_circulating_market_cap_yuan": None,
                        "szse_circulating_market_cap_yuan": 450.0,
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM ashare_daily_market_data WHERE trade_date = '2024-01-02'"
                ).fetchone()
                self.assertEqual(row["sse_amount_yuan"], 100.0)
                self.assertEqual(row["szse_amount_yuan"], 250.0)
                self.assertEqual(row["sse_circulating_market_cap_yuan"], 300.0)
                self.assertEqual(row["szse_circulating_market_cap_yuan"], 450.0)
            finally:
                conn.close()

    def test_dashboard_payload_and_html_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "market_data.sqlite"
            conn = init_db(str(db_path))
            try:
                seed_index_rows(conn)
                conn.execute(
                    """
                    INSERT INTO ashare_daily_market_data (
                        trade_date, total_margin_balance_yuan,
                        sse_amount_yuan, szse_amount_yuan,
                        sse_circulating_market_cap_yuan, szse_circulating_market_cap_yuan
                    )
                    VALUES
                        ('2024-03-01', 300000000000, 100000000000, 200000000000, 10000000000000, 20000000000000),
                        ('2024-03-04', 330000000000, 110000000000, 220000000000, 11000000000000, 22000000000000)
                    """
                )
                conn.commit()

                payload = build_dashboard_payload(conn, "2024-01-01")
                self.assertGreater(len(payload["indexDeviation"]), 0)
                self.assertEqual(len(payload["turnover"]), 2)
                self.assertEqual(payload["margin"][0]["marginToMarketCap"], 0.01)

                output_path = generate_html(payload, tmpdir, "dashboard.html")
                self.assertTrue(output_path.exists())
                self.assertIn("市场脉搏", output_path.read_text(encoding="utf-8"))
            finally:
                conn.close()


def seed_index_rows(conn: sqlite3.Connection):
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


if __name__ == "__main__":
    unittest.main()

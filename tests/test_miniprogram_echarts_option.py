import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM_ROOT = REPO_ROOT / "miniprogram"


class MiniProgramEchartsOptionTest(unittest.TestCase):
    def run_node_script(self, script):
        subprocess.run(["node", "-e", script], check=True, cwd=REPO_ROOT)

    def test_ashare_chart_options_keep_web_dashboard_semantics(self):
        script = textwrap.dedent(
            f"""
            const option = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "echarts-option.js"))});

            const indexOptions = option.buildIndexDeviationOptions([
              {{ date: "2026-06-01", series: "A股-沪深300", close: 3600, ma60: 3500, deviation: 0.028571 }},
              {{ date: "2026-06-02", series: "A股-沪深300", close: 3550, ma60: 3500, deviation: 0.014286 }},
              {{ date: "2026-06-01", series: "A股-创业板指", close: 1900, ma60: 2000, deviation: -0.05 }}
            ]);
            if (indexOptions.length !== 2 || indexOptions[0].title.text !== "A股-沪深300 MA60 偏离度") {{
              throw new Error("index deviation groups or title mismatch");
            }}
            if (indexOptions[0].series[0].name !== "MA60 偏离度" || indexOptions[0].series[0].markLine.data[0].yAxis !== 0) {{
              throw new Error("index deviation series/reference line mismatch");
            }}
            const indexTooltip = indexOptions[0].tooltip.formatter([{{ dataIndex: 0 }}]);
            if (!indexTooltip.includes("偏离度：2.86%") || !indexTooltip.includes("MA60：3,500.00")) {{
              throw new Error(`index tooltip mismatch: ${{indexTooltip}}`);
            }}

            const marginRows = [
              {{ date: "2026-06-01", marginBalance100m: 18500.25, marginToMarketCap: 0.0215 }},
              {{ date: "2026-06-02", marginBalance100m: 18610.5, marginToMarketCap: 0.022 }}
            ];
            const balanceOption = option.buildMarginBalanceOption(marginRows);
            if (balanceOption.title.text !== "沪深市场融资余额" || balanceOption.yAxis.name !== "亿元") {{
              throw new Error("margin balance axis/title mismatch");
            }}
            if (balanceOption.series[0].name !== "沪深合计融资余额（亿元）" || balanceOption.series[0].data[1][1] !== 18610.5) {{
              throw new Error("margin balance series mismatch");
            }}

            const ratioOption = option.buildMarginRatioOption(marginRows);
            if (ratioOption.title.text !== "融资余额 / 流通市值" || ratioOption.yAxis.axisLabel.formatter(0.022) !== "2.20%") {{
              throw new Error("margin ratio formatter mismatch");
            }}

            const turnoverOption = option.buildTurnoverOption([
              {{ date: "2026-06-01", totalAmount100m: 9800.5, hs300Close: 3650.25 }}
            ]);
            if (!Array.isArray(turnoverOption.yAxis) || turnoverOption.yAxis.length !== 2) {{
              throw new Error("turnover should use dual y axes");
            }}
            if (turnoverOption.series.length !== 2 || turnoverOption.series[1].name !== "沪深300点位" || turnoverOption.series[1].yAxisIndex !== 1) {{
              throw new Error("turnover dual series mismatch");
            }}

            const concentrationOption = option.buildTopConcentrationOption({{
              chart: [{{ date: "2026-06-01", value: 0.1825 }}],
              recentTables: []
            }});
            if (concentrationOption.title.text !== "Top5%成交集中度" || concentrationOption.yAxis.axisLabel.formatter(0.1825) !== "18.25%") {{
              throw new Error("top concentration formatter mismatch");
            }}
            """
        )

        self.run_node_script(script)

    def test_beijing_chart_options_keep_web_dashboard_semantics(self):
        script = textwrap.dedent(
            f"""
            const option = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "echarts-option.js"))});
            const weekdayRows = [
              {{ x: "2026-06-01", label: "2026-06-01", value: 1250, weekday: "周一" }},
              {{ x: "2026-06-07", label: "2026-06-07", value: 1300, weekday: "周末" }}
            ];

            const houseOptions = option.buildHouseViewPeopleOptions(weekdayRows, ["周一", "周末"]);
            if (houseOptions.length !== 2 || houseOptions[0].title.text !== "周一看房人数") {{
              throw new Error("house view weekday option mismatch");
            }}
            if (houseOptions[0].series[0].name !== "看房人数" || houseOptions[0].yAxis.name !== "人") {{
              throw new Error("house view series/unit mismatch");
            }}

            const lianjiaOptions = option.buildLianjiaDealsOptions(weekdayRows, ["周一", "周末"]);
            const weekendOption = lianjiaOptions[1];
            if (weekendOption.series[0].markLine.data[0].yAxis !== 1200 || weekendOption.series[0].markLine.data[0].name !== "周末荣枯线") {{
              throw new Error("weekend lianjia reference line mismatch");
            }}

            const decreaseRatioOption = option.buildDecreaseRatioOption([
              {{ x: "2026-06-01", label: "2026-06-01", value: 8.5 }}
            ]);
            if (decreaseRatioOption.title.text !== "房东调价跌涨比" || decreaseRatioOption.series[0].markLine.data[0].yAxis !== 10) {{
              throw new Error("decrease ratio reference line mismatch");
            }}

            const onlineOptions = option.buildOnlineSigningOptions({{
              dailyOnlineSignings: [{{ x: "2026-06-01", label: "2026-06-01", value: 420 }}],
              monthlyOnlineSignings: [{{ x: "2026-06-01", label: "2026-06", value: 11800 }}]
            }});
            if (onlineOptions.dailyOnlineSignings.title.text !== "每日二手房网签量") {{
              throw new Error("daily online signing title mismatch");
            }}
            if (onlineOptions.monthlyOnlineSignings.series[0].markLine.data[0].yAxis !== 12000) {{
              throw new Error("monthly online signing reference line mismatch");
            }}

            const creditYoyOption = option.buildCreditYoyOption([
              {{ x: "2026-05-01", label: "2026-05", value: 0.0325 }}
            ]);
            if (creditYoyOption.yAxis.axisLabel.formatter(0.0325) !== "3.25%" || creditYoyOption.series[0].markLine.data[0].name !== "荣枯线") {{
              throw new Error("credit yoy formatter/reference line mismatch");
            }}

            const monthIncreaseOptions = option.buildCreditMonthIncreaseOptions([
              {{ x: 2025, label: "2025", year: 2025, month: 5, value: -12.345 }},
              {{ x: 2026, label: "2026", year: 2026, month: 5, value: 21.5 }}
            ]);
            if (monthIncreaseOptions[5].title.text !== "5月当月居民贷款增量") {{
              throw new Error("credit month increase title mismatch");
            }}
            const monthTooltip = monthIncreaseOptions[5].tooltip.formatter([{{ axisValue: "2026", data: ["2026", 21.5] }}]);
            if (!monthTooltip.includes("当月居民贷款增量：+21.50亿元")) {{
              throw new Error(`credit month tooltip mismatch: ${{monthTooltip}}`);
            }}

            const ytdOptions = option.buildCreditYtdIncreaseOptions([
              {{ x: 2026, label: "2026", year: 2026, month: 12, value: 210.75 }}
            ]);
            if (ytdOptions[12].title.text !== "1-12月居民贷款增量") {{
              throw new Error("credit ytd title mismatch");
            }}
            """
        )

        self.run_node_script(script)

    def test_formatters_are_shared_by_chart_options(self):
        script = textwrap.dedent(
            f"""
            const option = require({json.dumps(str(MINIPROGRAM_ROOT / "utils" / "echarts-option.js"))});

            if (option.formatNumber(12345.678, 2) !== "12,345.68") {{
              throw new Error("number formatter mismatch");
            }}
            if (option.formatPercent(0.1234, 2) !== "12.34%") {{
              throw new Error("percent formatter mismatch");
            }}
            if (option.formatSignedNumber(8.5, 1) !== "+8.5") {{
              throw new Error("signed number formatter mismatch");
            }}
            if (option.formatPctChg(-1.234) !== "-1.23%") {{
              throw new Error("pct change formatter mismatch");
            }}
            if (option.buildEmptyOption("占位").title.text !== "占位") {{
              throw new Error("buildEmptyOption compatibility mismatch");
            }}
            """
        )

        self.run_node_script(script)


if __name__ == "__main__":
    unittest.main()

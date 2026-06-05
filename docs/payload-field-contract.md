# Payload Field Contract

This document records the existing dashboard payload fields that the WeChat mini program may consume. It is a contract for the current HTML dashboard payloads, not a place to add new indicators.

## Common Top-Level Fields

| Field | Type | Source | Notes |
|---|---|---|---|
| `generatedAt` | string | `build_dashboard_payload()` runtime | Format: `YYYY-MM-DD HH:MM:SS`. Metadata only. |
| `startDate` | string | CLI or caller argument | Format: `YYYY-MM-DD`. Controls historical query start. |

## `ashare` Payload

Source: `src/security_market_pulse.py::build_dashboard_payload()`.

Top-level fields:

| Field | Type | Source function | Mini program section |
|---|---|---|---|
| `generatedAt` | string | `build_dashboard_payload()` | Metadata only |
| `startDate` | string | Caller argument | Metadata only |
| `indexDeviation` | array | `load_index_chart_data()` | `ashare.indexDeviation` |
| `turnover` | array | `load_turnover_chart_data()` | `ashare.turnover` |
| `margin` | array | `load_margin_chart_data()` | `ashare.margin` |
| `topConcentration` | object | `load_top_concentration_data()` | `ashare.topConcentration` |

### `indexDeviation`

Used by the capital market "指数MA60偏离" tab.

Array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | string | `index_daily_data.trade_date` | Format: `YYYY-MM-DD`. |
| `series` | string | `index_daily_data.index_name` | Index display name. Existing order follows grouped query output. |
| `close` | number | `index_daily_data.close` | Rounded to 4 decimals. |
| `ma60` | number | 60-day rolling average of `close` | Rounded to 4 decimals. Rows exist only after enough MA60 data. |
| `deviation` | number | `(close - ma60) / ma60` | Rounded to 6 decimals. |

### `margin`

Used by the capital market "A股融资余额" tab.

Array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | string | `ashare_daily_market_data.trade_date` | Format: `YYYY-MM-DD`. |
| `marginBalance100m` | number | `total_margin_balance_yuan / 100000000` | Rounded to 4 decimals; unit is 100 million yuan. |
| `marginToMarketCap` | number | `total_margin_balance_yuan / (sse_circulating_market_cap_yuan + szse_circulating_market_cap_yuan)` | Rounded to 6 decimals. |

### `turnover`

Used by the capital market "A股成交金额" tab.

Array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | string | `ashare_daily_market_data.trade_date` | Format: `YYYY-MM-DD`. |
| `totalAmount100m` | number | `(sse_amount_yuan + szse_amount_yuan) / 100000000` | Rounded to 4 decimals; unit is 100 million yuan. |
| `hs300Close` | number | `index_daily_data.close` for `A股-沪深300` | Rounded to 4 decimals. |

### `topConcentration`

Used by the capital market "A股成交集中度" tab.

Object fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `chart` | array | `ashare_daily_market_data.top5pct_concentration` | Line chart data. |
| `recentTables` | array | `ashare_daily_market_data.top5_stocks` | Latest 5 trading days with stock table data, newest first. |

`chart` array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | string | `ashare_daily_market_data.trade_date` | Format: `YYYY-MM-DD`. |
| `value` | number | `top5pct_concentration` | Rounded to 6 decimals. |

`recentTables` array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | string | `ashare_daily_market_data.trade_date` | Format: `YYYY-MM-DD`. |
| `stocks` | array | Parsed `top5_stocks` JSON | Per-day Top5 stock rows. |

`stocks` array element fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `tsCode` | string | `top5_stocks` JSON key | Tushare-style stock code. |
| `name` | string | `fetch_ashare_stock_code_name_from_akshare()` fallback to `tsCode` | Display name. |
| `amountYuan` | number or null | `top5_stocks[tsCode][0]` | Trading amount in yuan. |
| `pctChg` | number or null | `top5_stocks[tsCode][1]` | Daily percentage change value from source data. |

## `beijing` Payload

Source: `src/beijing_real_estate_market_pulse.py::build_dashboard_payload()`.

Top-level fields:

| Field | Type | Source function | Mini program section |
|---|---|---|---|
| `generatedAt` | string | `build_dashboard_payload()` | Metadata only |
| `startDate` | string | Caller argument | Metadata only |
| `startMonth` | string | First 7 chars of `startDate` | Metadata for monthly charts |
| `houseViewPeopleByWeekday` | array | `build_weekday_points()` | `beijing.houseViewPeople` |
| `lianjiaDealsByWeekday` | array | `build_weekday_points()` | `beijing.lianjiaDeals` |
| `decreaseRatio` | array | `build_decrease_ratio_points()` | `beijing.decreaseRatio` |
| `dailyOnlineSignings` | array | `build_daily_online_signing_points()` | `beijing.onlineSignings` |
| `monthlyOnlineSignings` | array | `build_monthly_online_signing_points()` | `beijing.onlineSignings` |
| `creditYoy` | array | `build_credit_yoy_points()` | `beijing.credit` |
| `loanNetIncreaseByMonth` | array | `build_credit_month_group_points()` | `beijing.credit` |
| `totalLoanNetIncreaseByMonth` | array | `build_credit_month_group_points()` | `beijing.credit` |
| `weekdayOrder` | array | `CHART_WEEKDAY_ORDER` | Weekday chart ordering metadata |

### Weekday Series

Used by the "看房人数" and "大中介成交" tabs.

Fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `x` | string | Daily `trade_date`, or weekend week-ending date | Format: `YYYY-MM-DD`. |
| `label` | string | Same as `x` | Axis/display label. |
| `value` | number | `house_view_people` or `lianjia_deals` | Rounded to 6 decimals. |
| `weekday` | string | Calculated weekday label | One of `周一` to `周五`, or `周末`. |

### Daily Point Series

Used by `decreaseRatio`, `dailyOnlineSignings`, `monthlyOnlineSignings`, and `creditYoy`.

Fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `x` | string | Date or month start date | Daily fields use `YYYY-MM-DD`; monthly fields use first day of the month. |
| `label` | string | Date or month label | Monthly labels use `YYYY-MM`. |
| `value` | number | Calculated or source metric | Rounded to 6 decimals. |

Section-specific value sources:

| Field | Value source |
|---|---|
| `decreaseRatio.value` | `price_decrease_houses / price_increase_houses` |
| `dailyOnlineSignings.value` | `beijing_real_estate_daily_info.second_hand_online_signings` |
| `monthlyOnlineSignings.value` | `beijing_real_estate_monthly_info.second_hand_online_signings` |
| `creditYoy.value` | Year-over-year change of `residents_loan_balance` |

### Credit Month Group Series

Used by `loanNetIncreaseByMonth` and `totalLoanNetIncreaseByMonth`.

Fields:

| Field | Type | Source | Notes |
|---|---|---|---|
| `x` | integer | Year | Current implementation serializes this as the year value. |
| `label` | string | Year | Display label. |
| `value` | number | Monthly net increase or year-to-date cumulative net increase | Rounded to 6 decimals. |
| `month` | integer | Month number | `1` through `12`. |
| `year` | integer | Year | Same year represented by `x`. |

### `weekdayOrder`

Array of strings:

```json
["周一", "周二", "周三", "周四", "周五", "周末"]
```

This field controls weekday chart grouping order and is not a separate indicator.

## Section Whitelist For Future Cloud Function

These section names are the only first-version mini program sections implied by the current web dashboards:

| Type | Section | Payload field or fields |
|---|---|---|
| `ashare` | `indexDeviation` | `indexDeviation` |
| `ashare` | `margin` | `margin` |
| `ashare` | `turnover` | `turnover` |
| `ashare` | `topConcentration` | `topConcentration` |
| `beijing` | `houseViewPeople` | `houseViewPeopleByWeekday` |
| `beijing` | `decreaseRatio` | `decreaseRatio` |
| `beijing` | `lianjiaDeals` | `lianjiaDealsByWeekday` |
| `beijing` | `onlineSignings` | `dailyOnlineSignings`, `monthlyOnlineSignings` |
| `beijing` | `credit` | `creditYoy`, `loanNetIncreaseByMonth`, `totalLoanNetIncreaseByMonth` |


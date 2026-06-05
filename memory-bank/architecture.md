# Architecture

## Current system

MarketPulse is currently a local Python data and static HTML dashboard project. The existing system reads from a local SQLite database, optionally fetches missing A-share data from external sources, builds dashboard payload dictionaries, and injects those payloads into static HTML templates embedded in the Python scripts.

The planned WeChat mini program should reuse the existing payload generation functions rather than rewriting data collection or dashboard calculation logic. Existing HTML output paths and template behavior are part of the current product surface and should remain unchanged.

## File roles

### `src/security_market_pulse.py`

Capital market dashboard script. It owns the A-share SQLite schema initialization, optional market data updates, dashboard payload generation, and static HTML rendering.

Key responsibilities:

- Parses CLI arguments including `--start-date`, `--db-path`, `--output-dir`, `--output-name`, and `--skip-fetch`.
- Creates or migrates `ashare_daily_market_data` and `index_daily_data` through `init_db()`.
- Uses external fetch helpers from `src/market_daily_info.py` when `--skip-fetch` is not set.
- Builds the capital market payload through `build_dashboard_payload()`.
- Writes the existing capital market HTML dashboard through `generate_html()`.

Current payload fields:

- `generatedAt`
- `startDate`
- `indexDeviation`
- `turnover`
- `margin`
- `topConcentration`

Default HTML output:

- `security_market_pulse/index.html`

### `src/beijing_real_estate_market_pulse.py`

Beijing real estate dashboard script. It reads existing real estate and credit data from SQLite, builds the Beijing dashboard payload, and renders the static HTML dashboard.

Key responsibilities:

- Parses CLI arguments including `--start-date`, `--db-path`, `--output-dir`, and `--output-name`.
- Validates required SQLite tables through `init_db()` and `validate_required_tables()`.
- Builds weekday, daily, monthly, and credit chart payload data from existing database rows.
- Builds the Beijing real estate payload through `build_dashboard_payload()`.
- Writes the existing Beijing real estate HTML dashboard through `generate_html()`.

Current payload fields:

- `generatedAt`
- `startDate`
- `startMonth`
- `houseViewPeopleByWeekday`
- `lianjiaDealsByWeekday`
- `decreaseRatio`
- `dailyOnlineSignings`
- `monthlyOnlineSignings`
- `creditYoy`
- `loanNetIncreaseByMonth`
- `totalLoanNetIncreaseByMonth`
- `weekdayOrder`

Default HTML output:

- `beijing_real_estate_market_pulse/index.html`

### `src/market_daily_info.py`

A-share external data helper module used by `src/security_market_pulse.py`.

Key responsibilities:

- Loads `.env` values when needed, especially `TUSHARE_TOKEN`.
- Creates a Tushare client when available.
- Fetches and normalizes A-share stock, turnover, market cap, margin balance, and index data from Tushare, AkShare, SSE, and SZSE sources.
- Provides fallback behavior when Tushare is unavailable or incomplete.

### `config/consts.py`

Global project constants.

Current values:

- `START_DATE = "2010-01-01"`
- `DB_PATH = "data/market_data.sqlite"`
- `RECENT_REFRESH_DAYS = 3`

### `config/index_code.py`

Index name to provider code mapping used by the capital market script.

Important detail:

- `A股-沪深300` maps to `sh000300`; `src/security_market_pulse.py` depends on this entry for the turnover chart's HS300 close series.

### `tests/test_security_market_pulse.py`

Current pytest/unittest coverage for the capital market script.

Covered behavior:

- Pending A-share market date calculation with missing fields and dates after the latest record.
- A-share market record upsert preserving existing values when new values are missing.
- Capital market payload generation and HTML writing with a temporary SQLite database.

Current gap:

- There is not yet broad behavioral test coverage for `src/beijing_real_estate_market_pulse.py` beyond the payload contract shape checks in `tests/test_payload_contract.py`.
- There is not yet test coverage for future mini program payload export, cloud function section slicing, or mini program rendering.

### `tests/test_payload_contract.py`

Payload contract regression tests for the future mini program data boundary.

Key responsibilities:

- Builds a capital market payload from a temporary SQLite database using `src/security_market_pulse.py::build_dashboard_payload()`.
- Builds a Beijing real estate payload from a temporary SQLite database using `src/beijing_real_estate_market_pulse.py::build_dashboard_payload()`.
- Verifies the current top-level payload fields for `ashare` and `beijing` so future changes do not silently add or remove mini program section inputs.
- Verifies nested section fields for chart arrays and `topConcentration.recentTables[].stocks[]`.
- Patches A-share stock name lookup during the test to keep the contract check independent from external network access.

### `docs/payload-field-contract.md`

Human-readable field contract for the two existing dashboard payloads.

Key responsibilities:

- Documents the existing `ashare` payload fields from `src/security_market_pulse.py`.
- Documents the existing `beijing` payload fields from `src/beijing_real_estate_market_pulse.py`.
- Records each first-version mini program section's source fields, date fields, numeric fields, object nesting, and Top5 stock table fields.
- Defines the future cloud function section whitelist at a contract level without creating cloud function code.
- Explicitly treats the contract as a description of existing HTML dashboard payloads, not a source for new indicators.

### `data/market_data.sqlite`

Local SQLite database used by the existing scripts.

Confirmed relevant tables:

- `ashare_daily_market_data`
- `index_daily_data`
- `beijing_real_estate_daily_info`
- `beijing_real_estate_monthly_info`
- `beijing_residents_credit_monthly_info`

Additional tables currently present:

- `daily_margin_data`
- `daily_market_data`

### `memory-bank/design-document.md`

Product design document for the WeChat mini program. It defines scope, page structure, data access constraints, section-level payload access, caching, error states, login, sharing, and acceptance criteria.

### `memory-bank/tech-stack.md`

Technical stack recommendation for the mini program implementation. It recommends WeChat native mini program, WeChat cloud functions, WeChat cloud storage, ECharts for WeChat, and reuse of the existing Python payload pipeline.

### `memory-bank/implementation-plan.md`

Step-by-step implementation plan. Step 1 and Step 2 are complete as of 2026-06-05. Step 3, adding the payload upload directory and explanation, has not been started.

### `memory-bank/progress.md`

Chronological progress log for completed implementation milestones and handoff notes for future developers.

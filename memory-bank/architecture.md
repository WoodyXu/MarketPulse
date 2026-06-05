# Architecture

## Current system

MarketPulse is currently a local Python data and static HTML dashboard project. The existing system reads from a local SQLite database, optionally fetches missing A-share data from external sources, builds dashboard payload dictionaries, and injects those payloads into static HTML templates embedded in the Python scripts.

The WeChat mini program work now has an initial native mini program scaffold under `miniprogram/`. It should reuse the existing payload generation functions and `getDashboardSection` cloud function rather than rewriting data collection or dashboard calculation logic. Existing HTML output paths and template behavior are part of the current product surface and should remain unchanged.

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

### `api/README.md`

Documentation for the mini program API boundary and payload staging flow.

Key responsibilities:

- Documents that local Python remains responsible for SQLite reads and full dashboard payload generation.
- Documents that cloud functions should only check login context, read stored JSON, crop whitelisted sections, and return current tab data.
- States that cloud functions must not recalculate market or real estate indicators.
- States that the mini program must not read SQLite, call external data providers, or directly download full cloud storage payloads.
- Records the `api/` layout for local payload generation, cloud-storage-ready staging, and future cloud function code.
- Documents that payloads are staged locally under `api/payload/marketpulse-payload/` using the same object keys planned for non-public cloud storage.
- Documents the optional `--upload-command` template boundary for integrating WeChat cloud development CLI, Tencent Cloud COS CLI, or WeChat developer tool CLI without hard-coding one provider in the repository.
- Documents that `getDashboardSection` checks login context, validates fixed first-version section whitelist entries, reads the manifest-selected dashboard payload, and crops it to the requested section.
- Documents that `getDashboardSection` now reads `marketpulse-payload/manifest.json`, uses the latest manifest date when `date` is omitted, reads exact requested dates when available, and falls back to the nearest manifest date when requested dates are missing.
- Documents that successful cloud function responses contain only `type`, `section`, and current section `data`.
- Documents that handled error responses contain only normalized `type`/`section` when available plus the error object.
- Documents that `getDashboardSection` must not expose cloud storage paths, file IDs, download credentials, selected payload dates, or complete dashboard payloads.

### `api/upload_payload.py`

Local payload JSON generation, cloud-storage staging, manifest handling, and optional upload entry point for the future mini program payload flow.

Key responsibilities:

- Parses CLI arguments including `--db-path`, `--start-date`, `--date`, `--output-dir`, repeated `--type`, `--env-id`, and `--upload-command`.
- Opens the configured SQLite database with `sqlite3.Row` row factory.
- Reuses `src/security_market_pulse.py::build_dashboard_payload()` to generate the `ashare` payload.
- Reuses `src/beijing_real_estate_market_pulse.py::build_dashboard_payload()` to generate the `beijing` payload.
- Writes strict local JSON with `ensure_ascii=False`, `sort_keys=True`, and `allow_nan=False`.
- Names output files with the latest business date discovered inside the payload date fields: `ashare_YYYY-MM-DD.json` and `beijing_YYYY-MM-DD.json`.
- Stages payload files under the planned non-public cloud object prefix: `marketpulse-payload/{type}_{date}.json`.
- Treats `--date` as an optional guard that must match the payload's latest business date.
- Writes and updates `marketpulse-payload/manifest.json` after payload generation.
- Preserves prior manifest dates when adding a new payload date.
- Tracks each dashboard's `latestDate`, `latestFile`, `availableDates`, and `files` date-to-cloud-path mapping.
- Accepts `--env-id` as a placeholder value for optional upload command templates.
- Accepts `--upload-command` for provider-specific upload integration. The command template supports `{local_path}`, `{cloud_path}`, and `{env_id}` placeholders.
- Runs the optional upload command for each generated payload file and then for `marketpulse-payload/manifest.json`.
- Logs clearly when no upload command is provided and only local staging is performed.

Current boundary:

- Does not hard-code a specific WeChat cloud storage, COS, or developer-tool CLI implementation.
- Does not emit public download URLs, cloud storage file IDs, or download credentials.
- Does not implement cloud function runtime behavior.

Default local JSON output directory:

- `api/payload/`

Default staged object layout:

- `api/payload/marketpulse-payload/ashare_YYYY-MM-DD.json`
- `api/payload/marketpulse-payload/beijing_YYYY-MM-DD.json`
- `api/payload/marketpulse-payload/manifest.json`

### `api/cloudfunctions/getDashboardSection/README.md`

README for the `getDashboardSection` WeChat cloud function directory.

Key responsibilities:

- Documents that the current implementation covers the step 6 login-context check, step 7 section whitelist mapping, step 8 manifest-based latest-file fallback, and step 9 response constraints.
- Documents that missing `OPENID` returns a handled auth error.
- Documents accepted input shape: dashboard type, whitelisted section, and optional date.
- Lists the first-version section whitelist:
  - `ashare.indexDeviation`
  - `ashare.margin`
  - `ashare.turnover`
  - `ashare.topConcentration`
  - `beijing.houseViewPeople`
  - `beijing.decreaseRatio`
  - `beijing.lianjiaDeals`
  - `beijing.onlineSignings`
  - `beijing.credit`
- Documents that the function reads `marketpulse-payload/manifest.json`, selects latest/exact/fallback payload dates from manifest metadata, and reads the selected dashboard JSON without cloud storage prefix enumeration.
- Documents that the function crops the selected payload to the requested section without returning unrelated dashboard fields.
- Documents response safety boundaries: successful responses only expose `type`, `section`, and `data`; handled error responses expose only normalized `type`/`section` when available and the error object; no cloud storage paths, file IDs, download credentials, selected payload dates, or complete dashboard payloads are returned.

### `api/cloudfunctions/getDashboardSection/index.js`

Node.js WeChat cloud function for serving mini program dashboard sections.

Key responsibilities:

- Loads `wx-server-sdk` at runtime and initializes it with `DYNAMIC_CURRENT_ENV` when deployed in WeChat cloud functions.
- Reads WeChat login context through `cloud.getWXContext()`.
- Treats missing or empty `OPENID` as unauthenticated and returns a handled `UNAUTHENTICATED` error instead of throwing.
- Normalizes incoming `type`, `section`, and optional `date` values.
- Maintains `SECTION_WHITELIST`, the fixed first-version mapping from dashboard sections to payload fields.
- Rejects invalid dashboard types or invalid/cross-dashboard sections with `INVALID_SECTION` before any payload data is returned.
- Reads `marketpulse-payload/manifest.json` through `readPayloadFromManifest()` when no test `payloadReader` is injected.
- Selects the dashboard payload file through `selectPayloadFile()`:
  - omitted `date` resolves to the latest available manifest date;
  - available requested `date` resolves to the matching manifest file;
  - missing requested `date` resolves to the nearest available manifest date from `availableDates`.
- Reads selected JSON objects through `readJsonFromCloudPath()`, using injected `storageReader` in tests or `cloudRuntime.downloadFile({ fileID: cloudPath })` in the WeChat cloud runtime.
- Crops the selected payload through `selectSectionData()`.
- Returns single-field sections directly as `data` and composite sections as an object containing only the required fields.
- Builds all success responses through `buildSuccessResponse()`, which only returns `type`, `section`, and current section `data`.
- Builds handled errors through `buildErrorResponse()`, which only returns normalized `type`/`section` when available and the error object.
- Returns `SECTION_DATA_MISSING` when a requested section is whitelisted but the loaded payload lacks one of the required fields.
- Returns `PAYLOAD_NOT_FOUND` when the manifest lacks a usable file for the requested dashboard/date.
- Returns `PAYLOAD_READ_FAILED` when manifest or payload JSON cannot be read or parsed.
- Exports `handleRequest()`, `getLoginContext()`, `normalizeRequest()`, `getSectionFields()`, `selectSectionData()`, `selectAvailableDate()`, `selectPayloadFile()`, `readPayloadFromManifest()`, `buildSuccessResponse()`, `buildErrorResponse()`, `SECTION_WHITELIST`, and `MANIFEST_PATH` so local tests and future maintenance can reuse the same section, date-selection, and response-shape boundaries.
- Supports optional `payloadReader` injection in `handleRequest()` for section-cropping tests and optional `storageReader` injection for manifest/cloud storage tests.

Current boundary:

- Uses manifest metadata rather than cloud storage prefix enumeration for first-version fallback.
- Does not expose cloud storage paths, file IDs, download credentials, selected payload dates, or complete dashboard payloads in mini program-facing responses.
- Ignores extra client request parameters such as arbitrary field lists, full-payload flags, or client-supplied file paths because data selection is driven only by normalized `type`, `section`, optional `date`, and the fixed section whitelist.
- Does not implement mini program login, frontend cloud function requests, cache handling, pull-to-refresh, or chart rendering. Those remain later implementation-plan steps.

### `api/cloudfunctions/getDashboardSection/package.json`

Node package manifest for the WeChat cloud function.

Key responsibilities:

- Declares the cloud function package name and `index.js` entry point.
- Marks the package as private so it is not published accidentally.
- Declares the `wx-server-sdk` dependency expected by the WeChat cloud runtime.

### `miniprogram/app.js`

Native WeChat mini program app entry file.

Key responsibilities:

- Defines the global app object.
- Stores minimal global metadata for the first scaffold.
- Does not initialize login, cloud environment, or shared request state yet.

### `miniprogram/app.json`

Native WeChat mini program global configuration.

Key responsibilities:

- Registers the first-version page routes:
  - `pages/home/index`
  - `pages/ashare/index`
  - `pages/beijing/index`
- Keeps `pages/home/index` first so the overview page is the startup page.
- Defines the global window colors, navigation title, and sitemap location.

### `miniprogram/app.wxss`

Global mini program styles.

Key responsibilities:

- Provides the shared light background, typography, page spacing, panel, title, subtitle, and placeholder styles used by the scaffold pages.
- Keeps the current visual baseline close to the existing light dashboard style with green emphasis.

### `miniprogram/sitemap.json`

WeChat mini program sitemap configuration.

Key responsibilities:

- Allows indexing for all pages in the first scaffold.

### `miniprogram/project.config.json`

WeChat Developer Tools project configuration.

Key responsibilities:

- Points the mini program root at `miniprogram/`.
- Points the cloud function root at `api/cloudfunctions/`.
- Uses `touristappid` as a non-sensitive placeholder.
- Does not contain a real `appid`, `env-id`, token, secret, cloud storage credential, or private environment configuration.

### `miniprogram/pages/home/index.*`

Overview home page scaffold.

Key responsibilities:

- Provides the first screen for the mini program.
- Shows two board entries:
  - `资本市场`
  - `北京楼市`
- Navigates to `/pages/ashare/index` and `/pages/beijing/index`.
- Defines the first-version home share title and path.
- Does not request all dashboard data on page load.
- Does not implement login gating yet.

### `miniprogram/pages/ashare/index.*`

Capital market page scaffold.

Key responsibilities:

- Registers the page title `资本市场`.
- Imports the local `ec-canvas` component for future chart rendering.
- Defines the first-version tab list:
  - `indexDeviation`
  - `margin`
  - `turnover`
  - `topConcentration`
- Shows static scaffold placeholder content only.
- Defines the first-version capital market share title and path.
- Does not call `getDashboardSection`, cache data, render charts, or implement pull-to-refresh yet.

### `miniprogram/pages/beijing/index.*`

Beijing real estate page scaffold.

Key responsibilities:

- Registers the page title `北京楼市`.
- Imports the local `ec-canvas` component for future chart rendering.
- Defines the first-version tab list:
  - `houseViewPeople`
  - `decreaseRatio`
  - `lianjiaDeals`
  - `onlineSignings`
  - `credit`
- Shows static scaffold placeholder content only.
- Defines the first-version Beijing real estate share title and path.
- Does not call `getDashboardSection`, cache data, render charts, implement the credit secondary tab, or implement pull-to-refresh yet.

### `miniprogram/components/ec-canvas/`

Local ECharts for WeChat component source directory.

Key responsibilities:

- Contains the ECharts for WeChat `ec-canvas` component files copied into the repository:
  - `ec-canvas.js`
  - `ec-canvas.json`
  - `ec-canvas.wxml`
  - `ec-canvas.wxss`
  - `wx-canvas.js`
  - `echarts.js`
- Provides the chart component dependency expected by future mini program rendering steps without introducing a cross-platform frontend framework or large UI library.

### `miniprogram/utils/auth.js`

Placeholder authentication utility module.

Key responsibilities:

- Exposes a minimal `getLoginState()` scaffold for later login work.
- Does not call WeChat login APIs yet.

### `miniprogram/utils/cache.js`

Placeholder section cache utility module.

Key responsibilities:

- Defines the cache key prefix `marketpulse`.
- Exposes `buildCacheKey(type, section)` for future section-level cache work.
- Does not read or write WeChat storage yet.

### `miniprogram/utils/request.js`

Placeholder cloud function request utility module.

Key responsibilities:

- Exposes `requestDashboardSection()` as a future request boundary.
- Currently rejects with an explicit error so later steps can replace it with `wx.cloud.callFunction()`.
- Does not call cloud functions yet.

### `miniprogram/utils/format.js`

Placeholder formatting utility module.

Key responsibilities:

- Provides a minimal `formatText()` helper for future display formatting.
- Does not yet implement the money, percentage, or chart tooltip formatting required by later chart steps.

### `miniprogram/utils/echarts-option.js`

Placeholder chart option module.

Key responsibilities:

- Provides a minimal `buildEmptyOption()` helper.
- Reserves the centralized chart option construction boundary required by later implementation steps.
- Does not yet implement production chart options for any dashboard section.

### `tests/test_upload_payload.py`

Regression tests for the mini program payload generation, cloud-path staging, manifest, and upload command boundary.

Key responsibilities:

- Seeds a temporary SQLite database with both A-share and Beijing real estate test data.
- Freezes builder timestamps and patches A-share stock name lookup so generated payloads can be compared exactly without network access.
- Verifies `api/upload_payload.py` JSON output matches the existing dashboard payload builders exactly.
- Verifies generated JSON can be serialized with `allow_nan=False`.
- Verifies output file dates come from the latest business data date in the payload rather than `--start-date` or script runtime date.
- Verifies `--date` fails when it does not match the generated payload's latest business date.
- Verifies staged payload files are written under `marketpulse-payload/`.
- Verifies `manifest.json` contains latest file pointers, latest dates, available dates, and per-date file mappings.
- Verifies manifest updates preserve existing dates and select the max business date as the latest.
- Verifies `--upload-command` integration invokes uploads for generated payloads and then the manifest without executing real network calls.

### `tests/test_get_dashboard_section_cloudfunction.py`

Regression tests for the step 6, step 7, step 8, and step 9 `getDashboardSection` cloud function behavior.

Key responsibilities:

- Uses local Node.js from a Python unittest to load `api/cloudfunctions/getDashboardSection/index.js`.
- Injects a mocked cloud runtime object with `getWXContext()` so tests do not require WeChat cloud deployment.
- Verifies missing `OPENID` returns a handled `UNAUTHENTICATED` response.
- Simulates cloud storage with injected `storageReader` objects keyed by `marketpulse-payload/...` cloud paths.
- Verifies omitted `date` reads the dashboard's latest manifest file.
- Verifies exact requested `date` reads the matching manifest file.
- Verifies missing requested `date` falls back to the nearest available manifest date.
- Verifies all 9 legal first-version sections return cropped section data when a payload reader is injected.
- Verifies invalid dashboard type and cross-dashboard section requests return `INVALID_SECTION` without payload data.
- Verifies missing fields in a whitelisted composite section return `SECTION_DATA_MISSING`.
- Verifies section responses do not leak full-payload metadata such as `generatedAt` and `startDate`.
- Verifies exact top-level response field sets for successful and handled error responses.
- Verifies successful responses do not leak `marketpulse-payload` paths, `fileID`, download credentials, manifest-selected dates, or unrelated dashboard fields.
- Verifies extra request parameters cannot bypass fixed whitelist cropping.

### `tests/test_miniprogram_scaffold.py`

Regression tests for the step 10 native mini program scaffold.

Key responsibilities:

- Verifies `miniprogram/app.json` keeps `pages/home/index` as the first startup page.
- Verifies the capital market and Beijing real estate pages are registered.
- Verifies `miniprogram/project.config.json` uses the placeholder `touristappid`.
- Verifies the mini program project config does not contain real sensitive values such as `env-id`, secrets, or tokens.
- Verifies the local `ec-canvas` component source files exist, including `echarts.js`.

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

Step-by-step implementation plan. Step 1 through Step 10 are complete as of 2026-06-05. Step 11, mini program login flow, has not been started.

### `memory-bank/progress.md`

Chronological progress log for completed implementation milestones and handoff notes for future developers.

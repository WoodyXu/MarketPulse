# Architecture

## Current system

MarketPulse is currently a local Python data and static HTML dashboard project. The existing system reads from a local SQLite database, optionally fetches missing A-share data from external sources, builds dashboard payload dictionaries, and injects those payloads into static HTML templates embedded in the Python scripts.

The WeChat mini program work now has a native mini program implementation under `miniprogram/`, with first-version login gating implemented on the home, capital market, and Beijing real estate pages. The shared request/cache utility layer is implemented, and both board pages use it for section-level tab loading. A centralized ECharts option construction layer under `miniprogram/utils/echarts-option.js` owns chart semantics and formatting. The capital market page renders the first-version capital market charts and recent Top5 stock tables; the Beijing real estate page renders real estate and resident-credit charts. Both board pages support section-scoped pull-to-refresh, explicit error states, and retry. All three pages expose fixed page-level share entries. End-to-end acceptance coverage verifies that one SQLite source produces identical HTML payloads and staged JSON, that the cloud function crops those payloads without changing business meaning, and that page render state preserves returned values. Mobile compatibility acceptance covers 320 px and 390 px equivalent widths, horizontal tab/table reachability, bounded chart containers, loading/error states, and real-device debugging. Pre-release security acceptance protects private configuration, databases, generated full payloads, the mini program package boundary, and cloud function response fields through explicit ignore rules and regression tests. Delivery documentation now defines the empty-environment payload generation, upload, cloud deployment, authenticated invocation, local debugging, preview, acceptance, and known-limitations workflow. WeChat Developer Tools opens from the repository root through `project.config.json`; local AppID/tool settings live in ignored `project.private.config.json`. The mini program continues to reuse the existing payload builders and `getDashboardSection` rather than rewriting data collection or calculation logic. Existing HTML output paths and template behavior remain unchanged.

## File roles

### `src/security_market_pulse.py`

Capital market dashboard script. It owns the A-share SQLite schema initialization, optional market data updates, dashboard payload generation, and static HTML rendering.

Key responsibilities:

- Parses CLI arguments including `--start-date`, `--db-path`, `--output-dir`, `--output-name`, and `--skip-fetch`.
- Creates or migrates `ashare_daily_market_data` and `index_daily_data` through `init_db()`.
- Uses external fetch helpers from `src/market_daily_info.py` when `--skip-fetch` is not set.
- Builds the capital market payload through `build_dashboard_payload()`.
- Writes the existing capital market HTML dashboard through `generate_html()`.
- Promotes the repository root to the front of `sys.path` when run as a script so external `PYTHONPATH` entries cannot redirect `config` or `src` imports to another project.

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
- Promotes the repository root to the front of `sys.path` when run as a script so external `PYTHONPATH` entries cannot redirect `config` or `src` imports to another project.

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
- Links to the complete delivery guide and records the required payload-first, manifest-last deployment order.
- States that cloud environment IDs, shared test accounts, storage credentials, and provider-specific upload tools remain deployment-local concerns.

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
- Promotes the repository root to the front of `sys.path` before importing project modules, preventing an external `PYTHONPATH` entry from loading another project's `config` package.

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
- Documents deployment through WeChat Developer Tools with cloud-side dependency installation.
- Requires deployment into the same non-production cloud environment that contains the manifest and payload objects.
- Directs real invocation checks through an authenticated mini program session so the runtime supplies `OPENID`.
- Links to the complete delivery guide.

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
- Does not implement mini program frontend page behavior itself; login gating, section requests, cache handling, chart rendering, and pull-to-refresh are owned by the mini program files under `miniprogram/`.

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
- Provides shared login panel styles for avatar selection, nickname input, primary login action, loading/error layout, and the same restrained green visual baseline.
- Owns global narrow-screen overflow protection and full-width border-box sizing for pages and panels.
- Keeps the login input/action controls within the available panel width.
- Keeps the current visual baseline close to the existing light dashboard style with green emphasis.

### `miniprogram/sitemap.json`

WeChat mini program sitemap configuration.

Key responsibilities:

- Allows indexing for all pages in the first scaffold.

### `project.config.json`

WeChat Developer Tools project configuration.

Key responsibilities:

- Allows WeChat Developer Tools to open the repository root directly.
- Points `miniprogramRoot` at `miniprogram/`.
- Points `cloudfunctionRoot` at `api/cloudfunctions/`.
- Keeps the compilation settings used for simulator and real-device compatibility, including disabled enhanced compilation, minification, WXML/WXSS minification, and source-map upload.
- May be rewritten by WeChat Developer Tools with the selected AppID and concrete base-library version.
- Must not contain tokens, secrets, cloud storage credentials, or private environment identifiers.

### `project.private.config.json`

Ignored local WeChat Developer Tools configuration.

Key responsibilities:

- Stores the developer's actual AppID and machine-specific tool preferences.
- Keeps machine/user-specific Developer Tools settings outside version control.
- May be rewritten by WeChat Developer Tools during preview or real-device debugging.
- Is the only remaining private project configuration; duplicate configuration files under `miniprogram/` were removed.

### `.gitignore`

Repository boundary for local configuration, generated output, and private data.

Key responsibilities:

- Excludes `.env` and root `project.private.config.json`.
- Excludes `data/` and generic SQLite/DB snapshots, including `-wal` and `-shm` sidecar files.
- Excludes generated full dashboard payloads under `api/payload/`.
- Excludes generated HTML dashboards, pictures, Python caches, virtual environments, and local tool state.

Architecture insight:

- `api/payload/` contains full dashboard payloads before cloud-function section cropping, so it is a private staging area rather than a source artifact.
- Database ignore rules must cover both the configured `data/` directory and accidentally created snapshots elsewhere in the repository.
- The public WeChat AppID may remain in `project.config.json`; environment IDs, tokens, secrets, credentials, and machine-specific settings belong outside tracked files.

### `miniprogram/pages/home/index.*`

Overview home page and login gate.

Key responsibilities:

- Provides the first screen for the mini program.
- Reads login state from `miniprogram/utils/auth.js` on load and show.
- Shows the shared avatar/nickname login panel when the user is not logged in.
- Calls `loginWithUserInfo()` after the user selects an avatar and enters a nickname.
- Shows retryable login error text when the login flow fails.
- Shows two board entries:
  - `资本市场`
  - `北京楼市`
- Navigates to `/pages/ashare/index` and `/pages/beijing/index` only after login has completed.
- Defines the first-version home share entry through `onShareAppMessage()`, with title `MarketPulse 市场脉搏` and path `/pages/home/index`.
- Defines the first-version home timeline share entry through `onShareTimeline()`, with title `MarketPulse 市场脉搏`.
- Keeps home sharing page-scoped and independent from dashboard section state.
- Does not request all dashboard data on page load.
- Does not request dashboard sections, cache data, call cloud functions, or render charts.
- Reserves right-side space in board entry cards so the navigation arrow does not overlap text on narrow phones.

### `miniprogram/pages/ashare/index.*`

Capital market page structure, login gate, first-version section request wiring, and capital market chart/table rendering.

Key responsibilities:

- Registers the page title `资本市场`.
- Imports the local `ec-canvas` component for chart rendering.
- Imports `miniprogram/utils/request.js` as the page-level boundary for cloud function section reads and section cache reuse.
- Imports `miniprogram/utils/echarts-option.js` for all capital market chart option construction.
- Reads login state from `miniprogram/utils/auth.js` on load and show.
- Shows the shared avatar/nickname login panel when the user is not logged in.
- Calls `loginWithUserInfo()` after the user selects an avatar and enters a nickname.
- Shows retryable login error text when the login flow fails.
- Defines the first-version capital market tab list:
  - `indexDeviation`
  - `margin`
  - `turnover`
  - `topConcentration`
- Uses `indexDeviation` as the default active section.
- Initializes per-section page state for all four capital market sections with `loading`, `loaded`, `error`, and `data`.
- Loads only the active/default section after login and on page entry.
- Requests section data through `requestDashboardSection("ashare", section)`.
- Switches tabs through `onTapTab()` and requests newly opened sections on demand.
- Skips duplicate requests when a section has already loaded or is currently loading.
- Enables WeChat page-level pull-down refresh in `index.json`.
- Implements `onPullDownRefresh()` to force-refresh only the current active section through `requestDashboardSection("ashare", activeTab, { forceRefresh: true })`.
- Calls `wx.stopPullDownRefresh()` after forced refresh completion or failure.
- Maintains `activeTab`, `activeTabTitle`, and `activeSectionState` so the WXML renders only the current tab's section state.
- Shows loading, error, and loaded placeholder states for the active section.
- Validates section data shape before rendering:
  - `indexDeviation`, `margin`, and `turnover` must be arrays;
  - `topConcentration` must be an object containing `chart[]` and `recentTables[]`.
- Converts invalid section data shape into the stable page error text `数据结构异常，请稍后重试`.
- Shows an explicit error block with a short message and retry button when the active section has an error.
- Implements `retryActiveSection()` to force-refresh only the current active capital market section.
- Keeps loaded section render state in `chartCards` and `topStockTables`.
- Creates ECharts for WeChat `ec` objects with page-local `onInit()` handlers that initialize `miniprogram/components/ec-canvas/echarts`, bind the canvas to the chart, and set the generated option.
- Renders capital market charts from section payloads:
  - `indexDeviation` as one MA60 deviation chart card per index series;
  - `margin` as financing-balance and financing-to-circulating-market-cap ratio chart cards;
  - `turnover` as one turnover and HS300 dual-axis chart card;
  - `topConcentration` as one Top5% concentration chart card.
- Renders `topConcentration.recentTables` as recent Top5 stock tables.
- Formats Top5 stock table rows with stock-name fallback to `tsCode`, amount in `亿`, signed percentage change text, and up/down styling.
- Uses horizontal table scrolling for Top5 stock tables so phone-width layouts can reveal all columns without shrinking text.
- Uses a horizontally scrollable main-tab strip with retained page-edge padding.
- Bounds chart containers to the available panel width and clips canvas overflow.
- Keeps loading and error states in normal layout flow to avoid overlap or blank-screen transitions on narrow phones.
- Defines the first-version capital market share entry through `onShareAppMessage()`, with title `MarketPulse 资本市场看板` and path `/pages/ashare/index`.
- Keeps sharing independent from `activeTab`; receivers enter the capital market page and use `indexDeviation` as the default section.
- Keeps the target-page login gate active for unauthenticated share receivers and loads the default section after login succeeds.

Current boundary:

- Chart option semantics remain centralized in `miniprogram/utils/echarts-option.js`; the page owns only section-to-chart-card wiring, ec-canvas initialization objects, and Top5 table view formatting.
- Pull-to-refresh is page-level and section-scoped; it does not refresh inactive tabs or request a full dashboard payload.
- Retry is page-level and section-scoped; it uses the same forced refresh path as pull-to-refresh and does not refresh inactive tabs.
- Does not render Beijing real estate charts.
- Does not own cloud error-code semantics; `miniprogram/utils/request.js` normalizes cloud and cache failures before the page displays them.
- Does not request optional payload `date` values.

### `miniprogram/pages/beijing/index.*`

Beijing real estate page structure, login gate, first-version section request wiring, and Beijing real estate chart rendering.

Key responsibilities:

- Registers the page title `北京楼市`.
- Imports the local `ec-canvas` component for chart rendering.
- Imports `miniprogram/utils/request.js` as the page-level boundary for cloud function section reads and section cache reuse.
- Imports `miniprogram/utils/echarts-option.js` for all Beijing real estate chart option construction.
- Reads login state from `miniprogram/utils/auth.js` on load and show.
- Shows the shared avatar/nickname login panel when the user is not logged in.
- Calls `loginWithUserInfo()` after the user selects an avatar and enters a nickname.
- Shows retryable login error text when the login flow fails.
- Defines the first-version tab list:
  - `houseViewPeople`
  - `decreaseRatio`
  - `lianjiaDeals`
  - `onlineSignings`
  - `credit`
- Uses `houseViewPeople` as the default active section.
- Initializes per-section page state for all five Beijing real estate sections with `loading`, `loaded`, `error`, and `data`.
- Loads only the active/default section after login and on page entry.
- Requests section data through `requestDashboardSection("beijing", section)`.
- Switches main tabs through `onTapTab()` and requests newly opened sections on demand.
- Skips duplicate requests when a section has already loaded or is currently loading.
- Enables WeChat page-level pull-down refresh in `index.json`.
- Implements `onPullDownRefresh()` to force-refresh only the current active main section through `requestDashboardSection("beijing", activeTab, { forceRefresh: true })`.
- Calls `wx.stopPullDownRefresh()` after forced refresh completion or failure.
- Maintains `activeTab`, `activeTabTitle`, and `activeSectionState` so the WXML renders only the current main tab's section state.
- Defines the resident credit secondary tab list:
  - `creditYoy`
  - `loanNetIncreaseByMonth`
  - `totalLoanNetIncreaseByMonth`
- Uses `creditYoy` as the default resident credit secondary tab.
- Switches resident credit secondary tabs through `onTapCreditTab()` without issuing additional cloud function requests, because all resident credit subviews belong to the same `beijing.credit` section payload.
- Shows the resident credit secondary tab control only while the active main tab is `credit`.
- Shows loading, error, and loaded placeholder states for the active section.
- Validates section data shape before rendering:
  - `houseViewPeople`, `decreaseRatio`, and `lianjiaDeals` must be arrays;
  - `onlineSignings` must be an object containing `dailyOnlineSignings[]` and `monthlyOnlineSignings[]`;
  - `credit` must be an object containing `creditYoy[]`, `loanNetIncreaseByMonth[]`, and `totalLoanNetIncreaseByMonth[]`.
- Converts invalid section data shape into the stable page error text `数据结构异常，请稍后重试`.
- Shows an explicit error block with a short message and retry button when the active section has an error.
- Implements `retryActiveSection()` to force-refresh only the active Beijing real estate main section.
- Keeps loaded section render state in `chartCards` and keeps resident-credit prebuilt render groups in `creditChartGroups`.
- Creates ECharts for WeChat `ec` objects with page-local `onInit()` handlers that initialize `miniprogram/components/ec-canvas/echarts`, bind the canvas to the chart, and set the generated option.
- Renders Beijing real estate charts from section payloads:
  - `houseViewPeople` as one weekday-grouped chart card per first-version weekday bucket;
  - `decreaseRatio` as one跌涨比 chart card;
  - `lianjiaDeals` as one weekday-grouped large-agency deal chart card per first-version weekday bucket;
  - `onlineSignings` as daily and monthly online-signing chart cards;
  - `credit` as resident-loan YoY, monthly net increase, and year-to-date net increase chart groups.
- Shows only the active resident-credit secondary tab's chart cards, so YoY, monthly net increase, and year-to-date net increase are not all stacked at once.
- Uses horizontally scrollable main and resident-credit secondary tab strips.
- Bounds chart containers to the available panel width and clips canvas overflow.
- Keeps loading and error states in normal layout flow to avoid overlap or blank-screen transitions on narrow phones.
- Defines the first-version Beijing real estate share entry through `onShareAppMessage()`, with title `MarketPulse 北京楼市看板` and path `/pages/beijing/index`.
- Keeps sharing independent from the active main tab and resident-credit secondary tab; receivers enter the Beijing real estate page and use `houseViewPeople` as the default section.
- Keeps the target-page login gate active for unauthenticated share receivers and loads the default section after login succeeds.

Current boundary:

- Chart option semantics remain centralized in `miniprogram/utils/echarts-option.js`; the page owns only section-to-chart-card wiring, ec-canvas initialization objects, and resident-credit secondary-tab chart group selection.
- Pull-to-refresh is scoped to the active main tab; resident-credit secondary tabs remain local views over the already loaded `beijing.credit` section and do not issue separate refresh requests.
- Retry is scoped to the active main tab; resident-credit secondary tabs remain local views over the already loaded `beijing.credit` section and do not issue separate retry requests.
- Does not own cloud error-code semantics; `miniprogram/utils/request.js` normalizes cloud and cache failures before the page displays them.
- Does not request optional payload `date` values.

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

Mini program authentication utility module.

Key responsibilities:

- Stores first-version login state under the `marketpulse:auth` storage key.
- Exposes `getLoginState()` for pages to determine whether to show the login panel or page content.
- Exposes `loginWithUserInfo()` to validate avatar/nickname profile fields, call `wx.login()`, and persist successful login state.
- Exposes `clearLoginState()` for future logout/test reset needs.
- Normalizes stored user profile data to `avatarUrl` and `nickName`.
- Supports injecting a mocked `wxApi` in tests so login behavior can be verified without WeChat Developer Tools.

Current boundary:

- Performs first-version identity recognition only.
- Does not exchange the `wx.login()` code with a backend.
- Does not implement roles, permission tiers, private allowlists, subscriptions, or user preferences.
- Does not call cloud functions or request dashboard data.

### `miniprogram/utils/cache.js`

Mini program section cache utility module.

Key responsibilities:

- Defines the cache key prefix `marketpulse`.
- Builds section cache keys as `marketpulse:{type}:{section}`.
- Defines the first-version cache TTL as 24 hours through `CACHE_TTL_MS`.
- Stores section data entries with `cachedAt`, `type`, `section`, and `data`.
- Reads valid cache entries from memory first and then from WeChat local storage.
- Writes successful section responses into both memory and WeChat local storage.
- Rejects malformed or expired entries instead of returning stale data.
- Exposes `getCachedSection()`, `setCachedSection()`, `clearCachedSection()`, `clearMemoryCache()`, `isCacheEntryValid()`, `buildCacheKey()`, `CACHE_PREFIX`, and `CACHE_TTL_MS`.
- Supports injecting a mocked `wxApi` in tests so cache behavior can be verified without WeChat Developer Tools.

### `miniprogram/utils/request.js`

Mini program cloud function request utility module.

Key responsibilities:

- Exposes `requestDashboardSection(type, section, options)` as the shared section request boundary for future board pages.
- Calls the `getDashboardSection` cloud function through `wx.cloud.callFunction()`.
- Sends the first-version request payload containing only `type` and `section`.
- Validates that returned data contains matching `type`, `section`, and `data`.
- Recognizes handled cloud function error responses and converts `error.code` values into stable user-facing messages.
- Maps payload-not-found and payload-read failures to `暂无可用数据，请稍后重试`.
- Maps missing section data, invalid sections, and malformed response shapes to `数据结构异常，请稍后重试`.
- Maps unauthenticated and cloud-unavailable cases to concise retry/login-oriented page messages.
- Writes successful responses through `miniprogram/utils/cache.js`.
- Returns valid cached data before cloud calls unless `forceRefresh` is requested.
- Falls back to valid cache when a cloud request fails.
- Rejects when the cloud request fails and no valid cache exists, including when the only cache entry is expired.
- Exports `CLOUD_FUNCTION_NAME`, `callDashboardSection()`, `normalizeResponse()`, and `requestDashboardSection()` for tests and future page integration.
- Exports `buildRequestError()` so request error mapping can be tested without page lifecycle code.

Current boundary:

- Does not request optional payload `date` values yet.
- Is now imported by the capital market and Beijing real estate pages for page-level section loading.
- Does not own page lifecycle behavior or render charts; board pages decide when to pass `forceRefresh` during pull-to-refresh and retry.

### `miniprogram/utils/format.js`

Placeholder formatting utility module.

Key responsibilities:

- Provides a minimal `formatText()` helper for future display formatting.
- Does not yet implement the money, percentage, or chart tooltip formatting required by later chart steps.

### `miniprogram/utils/echarts-option.js`

Centralized mini program ECharts option construction module.

Key responsibilities:

- Defines shared chart constants including the restrained green/gold/purple palette and first-version weekday order.
- Exposes shared formatters for chart labels and tooltip text:
  - `formatNumber()`
  - `formatSignedNumber()`
  - `formatPercent()`
  - `formatPctChg()`
  - `formatRatio()`
- Keeps reusable line-chart option helpers for titles, legends, axes, grid, split lines, tooltip confinement, line series, latest-point marks, and reference lines.
- Builds capital market chart options:
  - `buildIndexDeviationOptions()` groups `indexDeviation` rows by index series and creates one MA60 deviation option per index, with percentage axis, zero reference line, latest point, and tooltip values for deviation, close, and MA60.
  - `buildMarginBalanceOption()` creates the financing-balance option with unit `亿元`.
  - `buildMarginRatioOption()` creates the financing-balance-to-circulating-market-cap ratio option with percentage axis and latest point.
  - `buildTurnoverOption()` creates the turnover and HS300 close dual-axis option.
  - `buildTopConcentrationOption()` creates the Top5% concentration option with percentage axis and latest point.
- Builds Beijing real estate chart options:
  - `buildHouseViewPeopleOptions()` creates weekday-grouped house-view people options.
  - `buildLianjiaDealsOptions()` creates weekday-grouped large-agency deal options and preserves the weekend 1200 reference line.
  - `buildDecreaseRatioOption()` creates the decrease-ratio option and preserves the reference line at 10.
  - `buildOnlineSigningOptions()` creates daily and monthly online-signing options and preserves the monthly 12000 reference line.
  - `buildCreditYoyOption()` creates the resident-loan YoY option and preserves the zero reference line.
  - `buildCreditMonthIncreaseOptions()` and `buildCreditYtdIncreaseOptions()` create 12 month-specific options for resident-loan monthly and year-to-date increase charts.
- Keeps `buildEmptyOption()` exported for compatibility with the initial scaffold.

Current boundary:

- Does not initialize `ec-canvas` instances.
- Does not mutate page state or request dashboard data.
- Does not render the Top5 stock table; only chart option construction belongs in this module.

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
- Launches `api/upload_payload.py` as a subprocess with a conflicting external `config` package on `PYTHONPATH` and verifies the CLI still imports this repository's modules.

### `docs/delivery-guide.md`

Operational handoff guide for the first-version mini program.

Key responsibilities:

- Defines local Python, Node.js, SQLite, WeChat Developer Tools, developer-account, and non-production cloud-environment prerequisites.
- Documents local HTML validation while preserving the existing HTML templates, output paths, and behavior.
- Documents payload and manifest generation through `api/upload_payload.py`.
- Documents manual cloud-storage upload and provider-neutral `--upload-command` integration.
- Requires payload files to be uploaded before `manifest.json`, so the manifest never points to missing objects.
- Documents `getDashboardSection` deployment with cloud-side dependency installation and authenticated invocation checks.
- Documents repository-root mini program debugging, cache fallback, retry, pull-to-refresh, preview, and real-device acceptance.
- Records the release commands, security checklist, test-environment ownership, and first-version known limitations.
- Explicitly preserves the no-new-indicators boundary and keeps full staged payloads private.

Architecture insight:

- Delivery configuration is intentionally split: tracked documentation and public project structure live in the repository, while environment IDs, developer membership, storage ACLs, and credentials remain in the deployment environment.
- Manifest upload is the publication boundary. Uploading it last makes a payload release visible only after all referenced objects exist.
- A documented command is part of the supported interface; CLI entry points must resolve repository-local imports deterministically even when the caller has an unrelated `PYTHONPATH`.

### `tests/test_delivery_documentation.py`

Regression tests for implementation plan step 25 delivery documentation.

Key responsibilities:

- Verifies the delivery guide covers payload generation, cloud upload, cloud function deployment, mini program debugging/preview, test cloud environment setup, known limitations, and release testing.
- Verifies the guide preserves existing HTML behavior, adds no indicators, protects complete payloads, and requires non-public cloud storage.
- Verifies the root, API, and cloud-function README files link to the delivery guide.

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
- Verifies the repository-root `project.config.json` points to `miniprogram/` and `api/cloudfunctions/`.
- Verifies the root project configuration keeps the expected compatibility-oriented compilation settings.
- Verifies the project configuration does not contain sensitive values such as `env-id`, secrets, or tokens.
- Verifies root `project.private.config.json` is ignored.
- Verifies the local `ec-canvas` component source files exist, including `echarts.js`.

### `tests/test_miniprogram_mobile_compatibility.py`

Regression tests for implementation plan step 23 mobile compatibility acceptance.

Key responsibilities:

- Models 320 px and 390 px common phone widths from the current `rpx` layout values.
- Verifies page/panel padding leaves readable chart content width and height.
- Verifies capital market and Beijing main tabs remain horizontally scrollable.
- Verifies Beijing resident-credit secondary tabs remain horizontally scrollable.
- Verifies the capital market Top5 table is intentionally wider than the viewport and every column remains reachable through horizontal scrolling.
- Verifies loading, error, retry, and empty states remain in normal document flow.
- Verifies home entry cards reserve space for the navigation arrow.
- Verifies `ec-canvas` fills a bounded chart container without forcing page-level horizontal overflow.

Architecture insight:

- Mobile compatibility is enforced at three layers: shared page/panel sizing in `app.wxss`, page-specific horizontal overflow controls in board WXML/WXSS, and static regression checks over the layout contract.
- Wide business content such as tabs and Top5 tables should scroll inside a bounded component; the whole page must not become horizontally scrollable.
- ECharts canvas sizing belongs to the page chart container, while the `ec-canvas` component remains a 100%-width/height rendering surface.
- WeChat Developer Tools project configuration belongs at the repository root because both mini program and cloud function roots are repository-relative siblings.
- Local AppID and tool preferences belong in ignored `project.private.config.json`; duplicate project configs create ambiguous behavior depending on which directory is opened.
- Real-device failures in `WAServiceMainContext.js` before project code evaluation should first be treated as Developer Tools/base-library/debug-package issues, not as page business-logic failures.

### `tests/test_pre_release_security.py`

Regression tests for implementation plan step 24 pre-release security acceptance.

Key responsibilities:

- Uses `git check-ignore` to verify private inputs, local databases, database sidecars, private project configuration, and generated staged payloads remain ignored.
- Uses `git ls-files` to verify tracked files exclude `.env`, private project configuration, database snapshots, private key files, and `api/payload/`.
- Verifies `.env.example` exposes only an empty `TUSHARE_TOKEN=` placeholder.
- Scans mini program source files to ensure the package does not contain cloud storage paths, direct download APIs, `fileID`, backend tokens, SQLite references, or download credentials.
- Verifies root `project.config.json` excludes environment IDs, tokens, secrets, credentials, and cloud URLs while allowing the public AppID.
- Invokes the real `getDashboardSection` handler for all nine legal sections plus an invalid request.
- Injects sensitive full-payload metadata into test payloads and verifies success/error responses cannot expose storage paths, file IDs, download credentials, builder metadata, or complete dashboard payloads.

Architecture insight:

- Security is enforced at three repository layers: ignore rules prevent private artifacts from entering version control, package scanning prevents backend details from entering the mini program bundle, and response-shape tests prevent cloud-function data overexposure.
- Cloud storage ACLs cannot be proven by repository-only tests. Deployment must keep `marketpulse-payload/` non-public and inaccessible to direct mini program reads.
- The cloud function may read complete stored payloads internally, but its public boundary remains the fixed section whitelist and centralized response builders.

### `tests/test_miniprogram_login.py`

Regression tests for the step 11 mini program login flow.

Key responsibilities:

- Uses local Node.js from Python unittest to load `miniprogram/utils/auth.js`.
- Injects a mocked `wxApi` object so login utility behavior can be tested without WeChat Developer Tools.
- Verifies avatar/nickname plus `wx.login()` produces a stored logged-in state.
- Verifies incomplete profile input is rejected before `wx.login()` runs.
- Verifies home, capital market, and Beijing real estate pages all import the auth utility and render the avatar/nickname login panel.
- Verifies the home page has a pre-login navigation guard before board navigation.

### `tests/test_miniprogram_home.py`

Regression tests for the step 12 overview homepage and sharing entry behavior.

Key responsibilities:

- Loads `miniprogram/pages/home/index.js` through local Node.js with a mocked `Page()` registration function.
- Verifies the homepage exposes exactly two board entries:
  - `资本市场` -> `/pages/ashare/index`
  - `北京楼市` -> `/pages/beijing/index`
- Verifies homepage sharing returns the first-version title `MarketPulse 市场脉搏` and routes share receivers to `/pages/home/index`.
- Verifies timeline sharing uses the same first-version homepage title.
- Verifies the homepage does not import the request utility, call `requestDashboardSection()`, call `wx.cloud.callFunction()`, or reference `getDashboardSection`.
- Locks the step 12 boundary so future request/cache implementation remains in step 13 and board-page steps rather than moving full dashboard loading into the overview page.

### `tests/test_miniprogram_request_cache.py`

Regression tests for the step 13 mini program request/cache utility layer.

Key responsibilities:

- Uses local Node.js from Python unittest to load `miniprogram/utils/cache.js` and `miniprogram/utils/request.js`.
- Injects mocked `wxApi` objects so storage and cloud function behavior can be tested without WeChat Developer Tools.
- Verifies section cache keys use `marketpulse:{type}:{section}` and the cache TTL is 24 hours.
- Verifies first section requests call `getDashboardSection`, pass only `type` and `section`, and write successful responses into cache.
- Verifies repeated section requests use valid memory or local-storage cache without unnecessary cloud calls.
- Verifies forced/cloud request failures fall back to valid cache.
- Verifies expired cache entries do not mask cloud request failures.
- Verifies malformed cloud function response shapes are rejected before data is cached.
- Verifies handled cloud function error codes map to stable page messages for missing payload files, payload read failures, and missing section data.
- Verifies expired-cache failures surface normalized retryable messages instead of raw cloud/network errors.

### `tests/test_miniprogram_ashare_page.py`

Regression tests for the capital market mini program page structure, request sequencing, chart-card generation, and Top5 stock table rendering.

Key responsibilities:

- Loads `miniprogram/pages/ashare/index.js` through local Node.js with a mocked `Page()` registration function.
- Injects mocked `auth` and `request` modules so the test can verify page-level request sequencing without WeChat Developer Tools or real cloud calls.
- Verifies first page entry requests only the default `ashare.indexDeviation` section.
- Verifies switching through the capital market tabs requests `indexDeviation`, `margin`, `turnover`, and `topConcentration`.
- Verifies switching back to already loaded tabs does not trigger unnecessary repeat requests.
- Verifies the page imports the request utility, uses dashboard type `ashare`, uses `indexDeviation` as the default tab, and stays limited to the four capital market sections.
- Verifies the page imports the ECharts option utility and renders `ec-canvas` chart cards.
- Verifies section payloads produce the expected number of chart cards:
  - one card per index series for `indexDeviation`;
  - two cards for `margin`;
  - one dual-axis card for `turnover`;
  - one concentration card for `topConcentration`.
- Verifies sampled chart card options preserve payload latest values, reference lines, percentage formatting, and dual-axis HS300 setup.
- Verifies Top5 stock table rows format amount, signed percentage change, stock-name fallback, and up/down classes.
- Verifies the WXML uses horizontal scrolling for the Top5 stock table.
- Verifies the capital market share title and fixed `/pages/ashare/index` path.
- Verifies unauthenticated share receivers stay on the capital market login gate and request only `ashare.indexDeviation` after login.
- Verifies pull-to-refresh is enabled, targets only the active capital market section, passes `forceRefresh: true`, stops WeChat pull-down state after success/failure, and keeps failed-refresh page state recoverable.
- Verifies the explicit capital market error block and retry entry exist.
- Verifies cloud request failure, invalid section shape, and retry behavior keep the active tab structure stable.
- Verifies retry force-refreshes only the active capital market section and clears the section error after success.

### `tests/test_miniprogram_beijing_page.py`

Regression tests for the Beijing real estate mini program page structure, request sequencing, chart-card generation, and resident-credit secondary tab rendering.

Key responsibilities:

- Loads `miniprogram/pages/beijing/index.js` through local Node.js with a mocked `Page()` registration function.
- Injects mocked `auth` and `request` modules so the test can verify page-level request sequencing without WeChat Developer Tools or real cloud calls.
- Verifies first page entry requests only the default `beijing.houseViewPeople` section.
- Verifies switching through the Beijing real estate main tabs requests `houseViewPeople`, `decreaseRatio`, `lianjiaDeals`, `onlineSignings`, and `credit`.
- Verifies resident credit secondary tab switching does not trigger extra dashboard section requests.
- Verifies switching back to already loaded main tabs does not trigger unnecessary repeat requests.
- Verifies the page imports the request utility, uses dashboard type `beijing`, uses `houseViewPeople` as the default tab, includes the resident credit secondary tabs, and stays limited to the five Beijing real estate sections.
- Verifies the page imports the ECharts option utility and renders `ec-canvas` chart cards.
- Verifies section payloads produce the expected number of chart cards:
  - one card per weekday bucket for `houseViewPeople`;
  - one card for `decreaseRatio`;
  - one card per weekday bucket for `lianjiaDeals`;
  - two cards for `onlineSignings`;
  - one YoY card or 12 month-specific cards for the active resident-credit secondary tab.
- Verifies sampled chart card options preserve payload values, weekday ordering, and key reference lines.
- Verifies resident-credit secondary tabs do not stack all resident-loan chart groups at once.
- Verifies the Beijing real estate share title and fixed `/pages/beijing/index` path.
- Verifies unauthenticated share receivers stay on the Beijing real estate login gate and request only `beijing.houseViewPeople` after login.
- Verifies pull-to-refresh is enabled, targets only the active Beijing real estate main section, passes `forceRefresh: true`, stops WeChat pull-down state after completion, and does not request extra resident-credit secondary-tab sections.
- Verifies the explicit Beijing real estate error block and retry entry exist.
- Verifies missing payload data, invalid resident-credit section shape, and retry behavior keep page state stable.
- Verifies retry force-refreshes only the active Beijing real estate main section and clears the section error after success.

### `tests/test_miniprogram_echarts_option.py`

Regression tests for the step 16 mini program ECharts option construction layer.

Key responsibilities:

- Uses local Node.js from Python unittest to load `miniprogram/utils/echarts-option.js`.
- Verifies capital market option construction for:
  - index MA60 deviation grouping, title, series name, zero reference line, and tooltip values;
  - financing-balance title, unit, and series data;
  - financing-to-market-cap ratio percentage formatting;
  - turnover and HS300 dual-axis series setup;
  - Top5% concentration title and percentage formatting.
- Verifies Beijing real estate option construction for:
  - weekday grouped house-view people titles, units, and series names;
  - weekday grouped large-agency deal weekend reference line;
  - decrease-ratio reference line at 10;
  - daily and monthly online-signing titles and monthly reference line at 12000;
  - resident-loan YoY percentage formatting and zero reference line;
  - resident-loan monthly and year-to-date increase month-specific option titles and signed tooltip formatting.
- Verifies shared formatter behavior and keeps `buildEmptyOption()` compatibility locked.

### `tests/test_end_to_end_data_consistency.py`

End-to-end data consistency acceptance coverage for implementation plan step 22.

Key responsibilities:

- Creates one temporary SQLite database with the A-share and Beijing real estate schemas and sample rows used by the existing payload builders.
- Builds both dashboard payloads directly from the existing Python source-of-truth functions.
- Generates both existing HTML dashboards and verifies that each HTML file embeds the exact builder payload.
- Runs the production payload staging flow and verifies the staged `ashare` and `beijing` JSON files are exactly equal to the corresponding builder payloads.
- Loads the generated manifest and payload JSON files as mock cloud storage, then invokes the real `getDashboardSection` handler for all nine first-version sections.
- Verifies single-field and composite cloud sections exactly match their source payload fields, with no business-field additions, removals, or reinterpretation.
- Loads the real capital market and Beijing real estate page modules through Node.js with authenticated request stubs backed by the cloud function responses.
- Verifies each page stores the exact section response data before rendering.
- Verifies ECharts series values remain aligned with the source payload for every capital market and Beijing real estate chart group.
- Verifies the recent Top5 stock table dates remain aligned with `topConcentration.recentTables`.

Architecture insight:

- The dashboard builders are the canonical business-data boundary shared by HTML and mini program delivery.
- `api/upload_payload.py` is a serialization and staging adapter; it must preserve builder payloads exactly.
- `getDashboardSection` is a manifest-backed projection layer; it selects and crops data but must not calculate or transform indicators.
- Mini program page modules are presentation adapters; their raw section state should remain equal to cloud section data, while chart options and table rows are derived display structures.
- The end-to-end test deliberately crosses Python and Node.js boundaries so regressions between payload generation, cloud projection, and page rendering cannot be hidden by isolated unit tests.

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

Step-by-step implementation plan. Steps 1 through 25 are complete as of 2026-06-07.

### `memory-bank/progress.md`

Chronological progress log for completed implementation milestones and handoff notes for future developers.

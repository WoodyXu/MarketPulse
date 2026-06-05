# Progress

## 2026-06-05 - Step 10 WeChat native mini program scaffold

- Completed implementation plan step 10 by creating the native WeChat mini program scaffold under `miniprogram/`.
- Added global mini program files:
  - `miniprogram/app.js`
  - `miniprogram/app.json`
  - `miniprogram/app.wxss`
  - `miniprogram/sitemap.json`
  - `miniprogram/project.config.json`
- Set `pages/home/index` as the first app page so the overview home page is the startup page.
- Added the first-version page directories:
  - `miniprogram/pages/home/`
  - `miniprogram/pages/ashare/`
  - `miniprogram/pages/beijing/`
- The home page currently shows the two planned board entries, "资本市场" and "北京楼市", and navigates to their page skeletons.
- The capital market and Beijing real estate pages currently contain only tab/page skeletons and explicit placeholder text. Login, cloud function requests, cache handling, pull-to-refresh, and chart rendering were intentionally not implemented because those belong to later steps.
- Added `miniprogram/utils/` placeholder modules for later steps:
  - `auth.js`
  - `cache.js`
  - `request.js`
  - `format.js`
  - `echarts-option.js`
- Added ECharts for WeChat source files directly under `miniprogram/components/ec-canvas/`:
  - `ec-canvas.js`
  - `ec-canvas.json`
  - `ec-canvas.wxml`
  - `ec-canvas.wxss`
  - `wx-canvas.js`
  - `echarts.js`
- `miniprogram/project.config.json` uses the non-sensitive placeholder `touristappid` and does not contain a real `appid`, `env-id`, token, secret, or cloud storage credential.
- Added `tests/test_miniprogram_scaffold.py` to verify:
  - the home page is the first configured page;
  - the two board pages are registered;
  - the ECharts component source files exist;
  - `project.config.json` does not contain real sensitive configuration values.
- Ran `python3 -m pytest tests/test_miniprogram_scaffold.py`; all 3 tests passed.
- Ran `node -c api/cloudfunctions/getDashboardSection/index.js`; syntax check passed.
- Ran `python3 -m pytest`; all 21 tests passed.
- The user reported validation complete.
- Step 11 has not been started. Next developer should implement the login flow only after explicit instruction.

## 2026-06-05 - Step 9 cloud function response constraints

- Completed implementation plan step 9 by hardening the `getDashboardSection` cloud function response shape in `api/cloudfunctions/getDashboardSection/index.js`.
- Added centralized response builders:
  - `buildSuccessResponse()` returns only `type`, `section`, and current section `data`;
  - `buildErrorResponse()` returns only normalized `type`/`section` when available plus the handled `error` object.
- Removed nonessential response metadata from mini program-facing responses, including `ok` and selected payload `date`.
- Successful section responses no longer expose cloud storage paths, file IDs, download credentials, selected manifest dates, or complete dashboard payload fields.
- Error responses still preserve necessary user/actionable error codes:
  - `UNAUTHENTICATED`
  - `INVALID_SECTION`
  - `SECTION_DATA_MISSING`
  - `PAYLOAD_NOT_FOUND`
  - `PAYLOAD_READ_FAILED`
  - `CLOUD_NOT_CONFIGURED`
- Extra request parameters such as arbitrary `fields`, `includeFullPayload`, or client-supplied `fileID` are ignored by the whitelist and section-cropping flow.
- Updated `api/README.md` and `api/cloudfunctions/getDashboardSection/README.md` to document the completed response constraints.
- Expanded `tests/test_get_dashboard_section_cloudfunction.py` to cover:
  - exact top-level response field sets for successful and error responses;
  - no leakage of `marketpulse-payload`, `fileID`, download credentials, manifest-selected dates, or full-payload metadata;
  - inability to bypass section cropping through extra request parameters;
  - existing auth, whitelist, manifest fallback, and missing-field behavior under the new response shape.
- Ran `node -c api/cloudfunctions/getDashboardSection/index.js`; syntax check passed.
- Ran `python3 -m pytest tests/test_get_dashboard_section_cloudfunction.py`; all 9 tests passed.
- Ran `python3 -m pytest`; all 18 tests passed.
- The user reported validation complete.
- Step 10 has not been started. Next developer should initialize the WeChat native mini program project only after explicit instruction.

## 2026-06-05 - Step 8 latest-file fallback through manifest

- Completed implementation plan step 8 by adding manifest-driven payload lookup inside `api/cloudfunctions/getDashboardSection/index.js`.
- The cloud function now reads `marketpulse-payload/manifest.json` before loading dashboard JSON when no test `payloadReader` is injected.
- Date selection behavior now follows the first-version manifest fallback contract:
  - omitted `date` selects the latest available manifest date for the requested dashboard type;
  - requested date that exists in the manifest selects that exact JSON file;
  - requested date that is missing falls back to the nearest available manifest date recorded in `availableDates`;
  - fallback uses manifest metadata and does not rely on cloud storage prefix enumeration.
- Added payload read helpers and exports for local tests and future maintenance:
  - `selectAvailableDate()`
  - `selectPayloadFile()`
  - `readPayloadFromManifest()`
  - `MANIFEST_PATH`
- The runtime storage reader uses `cloudRuntime.downloadFile({ fileID: cloudPath })` for the selected manifest and payload objects. Local tests can inject `storageReader` to simulate cloud storage without WeChat deployment.
- Added handled read errors:
  - `PAYLOAD_NOT_FOUND` when the manifest has no usable file for the requested dashboard/date;
  - `PAYLOAD_READ_FAILED` when manifest or payload JSON cannot be read or parsed.
- The cloud function still checks login context first, validates the fixed section whitelist before reading payload data, and crops the selected dashboard payload through the existing `selectSectionData()` helper.
- Updated `api/README.md` and `api/cloudfunctions/getDashboardSection/README.md` to document manifest reads, latest-date selection, requested-date selection, and missing-date fallback.
- Expanded `tests/test_get_dashboard_section_cloudfunction.py` to cover:
  - no `date` reading the latest manifest file;
  - exact requested date reading the matching manifest file;
  - missing requested date falling back to the nearest manifest date;
  - existing step 6 and step 7 auth, whitelist, cropping, and missing-field behavior.
- Ran `node -c api/cloudfunctions/getDashboardSection/index.js`; syntax check passed.
- Ran `python3 -m pytest tests/test_get_dashboard_section_cloudfunction.py`; all 7 tests passed.
- Ran `python3 -m pytest`; all 16 tests passed.
- The user reported validation complete.
- Step 9 was subsequently completed on 2026-06-05.

## 2026-06-05 - Step 7 section whitelist mapping and payload cropping

- Completed implementation plan step 7 by adding fixed section whitelist mapping inside `api/cloudfunctions/getDashboardSection/index.js`.
- Whitelisted first-version sections now match the documented payload contract:
  - `ashare.indexDeviation`
  - `ashare.margin`
  - `ashare.turnover`
  - `ashare.topConcentration`
  - `beijing.houseViewPeople`
  - `beijing.decreaseRatio`
  - `beijing.lianjiaDeals`
  - `beijing.onlineSignings`
  - `beijing.credit`
- The cloud function still checks login context first. Missing `OPENID` returns `UNAUTHENTICATED`.
- After login succeeds, invalid `type` or `section` now returns a handled `INVALID_SECTION` error and does not return payload data.
- Added section cropping helper behavior:
  - Single-field sections return the payload field value directly as `data`.
  - Composite sections return only the required field combination under `data`.
  - Missing required payload fields return `SECTION_DATA_MISSING`.
- Added exported helpers for future step 8 integration and local tests:
  - `getSectionFields()`
  - `selectSectionData()`
  - `SECTION_WHITELIST`
- Added optional `payloadReader` injection to `handleRequest()` for tests and future cloud storage integration. The real cloud storage reader, manifest lookup, latest-file fallback, and date fallback were not implemented.
- Updated `api/README.md` and `api/cloudfunctions/getDashboardSection/README.md` to document that section whitelist mapping and cropping are implemented while cloud storage reads and date fallback remain deferred.
- Expanded `tests/test_get_dashboard_section_cloudfunction.py` to cover:
  - all 9 legal sections returning cropped data;
  - illegal dashboard type and cross-dashboard sections returning `INVALID_SECTION`;
  - missing composite-section fields returning `SECTION_DATA_MISSING`;
  - no response leakage of full-payload metadata such as `generatedAt` and `startDate`.
- Ran `node -c api/cloudfunctions/getDashboardSection/index.js`; syntax check passed.
- Ran `python3 -m pytest tests/test_get_dashboard_section_cloudfunction.py`; all 5 tests passed.
- Ran `python3 -m pytest`; all 14 tests passed.
- The user reported validation complete.
- Step 8 has not been started. Next developer should implement manifest/cloud storage latest-file fallback only after explicit instruction.

## 2026-06-05 - Step 6 cloud function skeleton and login context check

- Completed implementation plan step 6 by creating the Node.js cloud function skeleton under `api/cloudfunctions/getDashboardSection/`.
- Added `api/cloudfunctions/getDashboardSection/index.js`.
- The cloud function now attempts to load `wx-server-sdk`, initializes the cloud runtime with `DYNAMIC_CURRENT_ENV`, and reads the WeChat login context through `getWXContext()`.
- Missing `OPENID` returns a handled `UNAUTHENTICATED` error with a Chinese user-facing message.
- Existing `OPENID` is treated as sufficient access for the first version and returns a `READ_PAYLOAD_DEFERRED` status, confirming the request can enter the later payload read flow.
- The skeleton echoes normalized `type`, `section`, and optional `date` values only after login context is present.
- Added exported helper functions for local tests:
  - `handleRequest()`
  - `getLoginContext()`
  - `normalizeRequest()`
- Added `api/cloudfunctions/getDashboardSection/package.json` with the `wx-server-sdk` dependency and private package metadata.
- Updated `api/README.md` and `api/cloudfunctions/getDashboardSection/README.md` to state that step 6 is implemented and that section whitelist mapping, cloud storage reads, date fallback, and response cropping remain deferred.
- Added `tests/test_get_dashboard_section_cloudfunction.py` to run the cloud function handler through local Node.js with a mocked cloud runtime.
- The new test covers:
  - missing `OPENID` returning `UNAUTHENTICATED`;
  - present `OPENID` entering the deferred read flow while preserving `type`, `section`, and `date`.
- Ran `python3 -m pytest tests/test_get_dashboard_section_cloudfunction.py`; all 2 tests passed.
- Ran `python3 -m pytest`; all 11 tests passed.
- The user reported validation complete.
- Step 7 has not been started. Next developer should implement section whitelist mapping only after explicit instruction.

## 2026-06-05 - Step 5 cloud storage staging and manifest handling

- Completed implementation plan step 5 by extending `api/upload_payload.py` from local JSON generation into cloud-storage-ready staging and manifest handling.
- Payload JSON files are now written under the planned non-public cloud object prefix in the local output directory:
  - `marketpulse-payload/ashare_YYYY-MM-DD.json`
  - `marketpulse-payload/beijing_YYYY-MM-DD.json`
- The default local output root remains `api/payload/`, so generated files stage to `api/payload/marketpulse-payload/`.
- Added `marketpulse-payload/manifest.json` generation and update logic.
- The manifest records:
  - `payloadPrefix`
  - per-dashboard `latestDate`
  - per-dashboard `latestFile`
  - per-dashboard `availableDates`
  - per-dashboard date-to-file `files` mapping
- Manifest updates preserve existing available dates and update each dashboard's latest file to the max available business date.
- Added `--upload-command` as a CLI template hook for future WeChat cloud development CLI, Tencent Cloud COS CLI, or WeChat developer tool CLI integration.
- `--upload-command` supports `{local_path}`, `{cloud_path}`, and `{env_id}` placeholders and uploads generated payload files plus `marketpulse-payload/manifest.json`.
- When `--upload-command` is omitted, the script only stages local files and logs that no public download URL is emitted.
- Updated `api/README.md` to document the staged object layout, manifest, and upload command boundary.
- Expanded `tests/test_upload_payload.py` to cover staged cloud-path output, manifest content, preservation of historical manifest dates, latest-file updates, and upload command invocation for payloads and manifest.
- Ran `python3 -m pytest tests/test_upload_payload.py`; all 4 tests passed.
- Ran `python3 -m pytest`; all 9 tests passed.
- The user reported validation complete.
- Step 6 has not been started. Next developer should create the cloud function skeleton only after explicit instruction.

## 2026-06-05 - Step 4 local payload generation and serialization

- Completed implementation plan step 4 by implementing local JSON generation in `api/upload_payload.py`.
- `api/upload_payload.py` now reuses the existing payload builders:
  - `src/security_market_pulse.py::build_dashboard_payload()` for `ashare`.
  - `src/beijing_real_estate_market_pulse.py::build_dashboard_payload()` for `beijing`.
- The script supports `--db-path`, `--start-date`, `--date`, `--output-dir`, repeated `--type`, and `--env-id`.
- `--start-date` is passed through to the existing builders and does not drive output file naming.
- Output filenames use the latest business date discovered in the generated payload date fields, for example `ashare_YYYY-MM-DD.json` and `beijing_YYYY-MM-DD.json`.
- `--date` is treated as an optional target business date guard; generation fails if it does not match the payload's latest business date.
- JSON is written with `ensure_ascii=False`, `sort_keys=True`, and `allow_nan=False`, so NaN and Infinity are rejected before upload is ever introduced.
- `--env-id` is accepted only as a placeholder parameter and logs that step 4 does not upload. No cloud storage upload, manifest generation, or cloud function runtime behavior was implemented.
- Added `tests/test_upload_payload.py` to verify generated JSON exactly matches the existing builders, strict serialization works, filenames come from business data dates, and mismatched `--date` fails.
- Ran `python3 -m pytest`; all 7 tests passed. The user reported validation complete.
- Step 5 has not been started. Next developer should implement cloud storage upload and manifest handling only after explicit instruction.

## 2026-06-05 - Step 3 payload upload directory planning

- Completed implementation plan step 3 by adding the planned `api/` boundary directory for the future mini program backend integration.
- Added `api/README.md` to document the split between local Python payload generation and future WeChat cloud function section serving.
- Added `api/upload_payload.py` as a placeholder entry point only. It intentionally raises a message explaining that local JSON generation belongs to implementation plan step 4.
- Added `api/cloudfunctions/getDashboardSection/README.md` to reserve the future cloud function directory and document its read/crop/return responsibilities.
- No payload serialization, cloud upload, or cloud function runtime code was implemented in this step.
- Ran `python3 -m pytest`; all 5 tests passed. The user reported validation complete.
- Step 4 has not been started. Next developer should implement `api/upload_payload.py` local JSON generation only after explicit instruction.

## 2026-06-05 - Step 2 payload field contract

- Completed implementation plan step 2 by documenting the existing `ashare` and `beijing` dashboard payload contracts in `docs/payload-field-contract.md`.
- The field contract covers all first-version mini program sections from the product design:
  - `ashare.indexDeviation`, `ashare.margin`, `ashare.turnover`, and `ashare.topConcentration`.
  - `beijing.houseViewPeople`, `beijing.decreaseRatio`, `beijing.lianjiaDeals`, `beijing.onlineSignings`, and `beijing.credit`.
- Documented each section's source function, array/object nesting, date fields, numeric fields, and Top5 stock table fields without adding indicators beyond the existing HTML dashboard payloads.
- Added `tests/test_payload_contract.py` to generate both payload types from temporary SQLite databases and verify top-level fields, section presence, nested array/object fields, and weekday order metadata.
- Stubbed A-share stock name lookup in the contract test so the Top5 table field check does not depend on external network access.
- Ran `python3 -m pytest`; all 5 tests passed. The user reported validation complete.
- Step 3 was subsequently completed on 2026-06-05.

## 2026-06-05 - Step 1 implementation baseline

- Completed implementation plan step 1 by reading `memory-bank/design-document.md`, `memory-bank/tech-stack.md`, `memory-bank/implementation-plan.md`, and the existing `src/` scripts.
- Confirmed existing HTML dashboard behavior is contained in the two current script entry points and should remain unchanged:
  - `src/security_market_pulse.py` generates the capital market dashboard.
  - `src/beijing_real_estate_market_pulse.py` generates the Beijing real estate dashboard.
- Confirmed both dashboard scripts expose `build_dashboard_payload()` functions that can be reused by future mini program payload export work.
- Confirmed current SQLite database path is `data/market_data.sqlite` and includes the tables required by the existing dashboards.
- Confirmed current test entry is `python3 -m pytest`; the user ran validation and reported it passed.
- No code changes were made during step 1. The next implementation step must not start until explicitly requested.

# MarketPulse API

This directory contains the implemented boundary between the existing local
Python payload pipeline and the WeChat cloud function layer.

## Responsibility split

- Local Python remains responsible for reading SQLite data and generating full
  dashboard JSON payloads by reusing the existing `build_dashboard_payload()`
  functions.
- Cloud functions remain responsible only for authentication context checks,
  reading stored JSON payloads, selecting the requested dashboard section, and
  returning that section to the mini program.
- Cloud functions must not recalculate market or real estate indicators.
- The mini program must not read SQLite, call external data providers, or
  download full payload JSON files directly from cloud storage.

## Layout

```text
api/
├── README.md
├── upload_payload.py
└── cloudfunctions/
    └── getDashboardSection/
        ├── README.md
        ├── index.js
        └── package.json
```

`upload_payload.py` generates strict local JSON files from the existing payload
builders, stages them under the same object keys planned for cloud storage, and
maintains a manifest for latest-version lookup:

```text
api/payload/
└── marketpulse-payload/
    ├── ashare_YYYY-MM-DD.json
    ├── beijing_YYYY-MM-DD.json
    └── manifest.json
```

The default behavior is local staging only, which is useful before the WeChat
cloud environment is configured. For cloud upload integration, pass
`--upload-command` with a CLI command template. The script substitutes
`{local_path}`, `{cloud_path}`, and `{env_id}`, then uploads each generated
payload and `marketpulse-payload/manifest.json`. The upload command must point
to a non-public cloud storage location; the script never emits public download
URLs.

`cloudfunctions/getDashboardSection/` contains the Node.js cloud function. It
checks the WeChat login context and returns a handled auth error when `OPENID`
is missing. When `OPENID` is present, it validates `type` and `section` against
the fixed first-version whitelist, reads `marketpulse-payload/manifest.json`,
selects either the requested payload date or the latest/nearest available
manifest date, reads that dashboard JSON, and crops it to the requested section.
Successful responses contain only `type`, `section`, and `data`. Error
responses contain only the normalized `type`/`section` when available plus the
handled error object. The function must not expose cloud storage paths, file
IDs, download credentials, selected payload dates, or complete dashboard
payloads.

## Delivery

The complete empty-environment staging, upload, deployment, cloud invocation,
mini program preview, test-environment, and known-limitations instructions are
in [`docs/delivery-guide.md`](../docs/delivery-guide.md).

The required production order is:

1. Generate payload files and `manifest.json`.
2. Upload payload JSON files to non-public cloud storage.
3. Upload `manifest.json` last.
4. Deploy `getDashboardSection` with cloud-side dependency installation.
5. Verify section calls through an authenticated mini program session.

The repository intentionally does not commit a cloud environment ID, shared
test account, storage credential, or provider-specific uploader.

# getDashboardSection Cloud Function

This directory contains the WeChat cloud function that serves mini program
dashboard sections.

The current implementation:

- Checks the WeChat cloud function login context.
- Returns a handled `UNAUTHENTICATED` error when `OPENID` is missing.
- Allows requests with `OPENID` to enter the payload section flow.
- Maintains a fixed whitelist for first-version dashboard sections.
- Crops an already loaded payload to the requested section without returning
  unrelated dashboard fields.
- Reads `marketpulse-payload/manifest.json` for available payload dates.
- Uses the latest manifest date when the request omits `date`.
- Uses the requested manifest date when available.
- Falls back to the nearest available manifest date when the requested date is
  missing.
- Reads the selected dashboard JSON from cloud storage without relying on
  prefix enumeration.
- Returns successful section responses with only `type`, `section`, and `data`.
- Returns handled errors with only normalized `type`/`section` when available
  and the error object.
- Avoids returning storage paths, file IDs, download credentials, selected
  payload dates, or complete dashboard payloads.

Whitelisted sections:

- `ashare.indexDeviation`
- `ashare.margin`
- `ashare.turnover`
- `ashare.topConcentration`
- `beijing.houseViewPeople`
- `beijing.decreaseRatio`
- `beijing.lianjiaDeals`
- `beijing.onlineSignings`
- `beijing.credit`

## Deployment

Open the repository root in WeChat Developer Tools, select the non-production
cloud environment containing the staged payloads, then deploy this directory
with the option equivalent to "upload and deploy: install dependencies in the
cloud".

The function must be deployed in an environment that can read:

- `marketpulse-payload/manifest.json`
- every payload object referenced by the manifest

Use an authenticated mini program session for the real invocation check so the
WeChat runtime supplies `OPENID`. Do not make the payload directory public to
work around missing storage permissions.

See [`docs/delivery-guide.md`](../../../docs/delivery-guide.md) for the complete
upload, deployment, preview, acceptance, and rollback-safe ordering.

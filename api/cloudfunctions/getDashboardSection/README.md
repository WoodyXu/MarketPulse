# getDashboardSection Cloud Function

This directory reserves the planned WeChat cloud function that will serve mini
program dashboard sections.

The current implementation covers step 6, step 7, step 8, and step 9. It:

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

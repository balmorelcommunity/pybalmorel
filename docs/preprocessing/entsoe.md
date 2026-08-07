# ENTSO-E Data Fetching

`pybalmorel.entsoe` is a thin, Balmorel-independent client for the ENTSO-E
Transparency Platform. It fetches raw load, day-ahead price, generation, and
cross-border flow data, and it owns the zone-code vocabulary that bridges
Balmorel region names and ENTSO-E bidding zones (see `CONTEXT.md`). It has no
dependency on Balmorel results — `pybalmorel.backcasting` builds on top of it
for validating Balmorel against these observations (see
[backcasting](backcasting.md)).

## Zone vocabulary

- `bidding_zone_codes` — dict, canonical region name → ENTSO-E query code
  (`IT-NORD`, `NO1`–`NO5`, `SE1`–`SE4`, `BA`, etc.)
- `bidding_zones` — list of every ENTSO-E bidding zone identifier this package
  knows about.
- `bidding_zone_translation` — dict, Balmorel region name → canonical name
  shared with ENTSO-E (e.g. `DE4-E`/`DE4-N`/`DE4-S`/`DE4-W` → `DE`,
  `IT-NORD`/... → `IT`, `FIN` → `FI`). See `CONTEXT.md`'s "Canonical Region
  Name".
- `region_to_entsoe_code(canonical_region)` — canonical name → the code
  `entsoe-py` expects for querying it, including the handful of codes (`DE`,
  `IE`, `UK`, `DK1`, `DK2`) that aren't equal to their canonical name.
- `entsoe_subzones(canonical_region)` — the ENTSO-E bidding zones that
  collapse to a canonical region (e.g. `'IT'` → the 7 Italian bidding zones).
- `entsoe_code_to_region(code)` — inverse of `region_to_entsoe_code`.

## Fetching data

- `get_api_key()` — reads `ENTSOE_API_KEY` from `.env`, or prompts for it.
- `fetch_annual_data(entsoe_query, year, bidding_zones, path, api_key)` —
  fetch a full calendar year of a single-zone query (e.g. `'load'`,
  `'day_ahead_prices'`, `'generation'`) for each zone, skipping any already
  downloaded.
- `fetch_annual_transmission_data(entsoe_query, from_to_list, year, path, api_key)`
  — same, but for a border-pair query (e.g. `'crossborder_flows'`).

## Example

```python
from pybalmorel.entsoe import get_api_key, fetch_annual_data, bidding_zones

api_key = get_api_key()
fetch_annual_data("load", 2024, bidding_zones, "entsoe_data", api_key)
```

## TODO

A standalone CLI (`python -m pybalmorel.entsoe`) for downloading raw ENTSO-E
data scoped to Balmorel bidding zones, independent of the backcasting
validation workflow, is planned but not yet built.

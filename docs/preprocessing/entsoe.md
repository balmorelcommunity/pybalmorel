# ENTSO-E Data Fetching

`pybalmorel.entsoe` is a thin, Balmorel-independent client for the ENTSO-E
Transparency Platform. It fetches raw load, day-ahead price, generation, and
cross-border flow data, and it owns the zone-code vocabulary that bridges
Balmorel region names and ENTSO-E bidding zones (see [`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md)). It has no
dependency on Balmorel results — `pybalmorel.backcasting` builds on top of it
for [preparing](preparing_backcast.md) and
[validating](../postprocessing/validating_backcast.md) a Backcast.

## Installation

`pybalmorel.entsoe` needs the `entso-e` extra, which installs `entsoe-py`,
`python-decouple` and `click`:

```bash
pip install pybalmorel[entso-e]
```

You also need an API key for the ENTSO-E Transparency Platform: register
at [transparency.entsoe.eu](https://transparency.entsoe.eu/) and request
Restful API access. Then put the key in a `.env` file in your working
directory, so you are not prompted for it every time:

```
ENTSOE_API_KEY=your-key-here
```

## Zone vocabulary

- `bidding_zone_codes` — dict, canonical region name → ENTSO-E query code
  (`IT-NORD`, `NO1`–`NO5`, `SE1`–`SE4`, `BA`, etc.)
- `bidding_zones` — list of every ENTSO-E bidding zone identifier this package
  knows about.
- `bidding_zone_translation` — dict, Balmorel region name → canonical name
  shared with ENTSO-E (e.g. `DE4-E`/`DE4-N`/`DE4-S`/`DE4-W` → `DE`,
  `IT-NORD`/... → `IT`, `FIN` → `FI`). See [`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md)'s "Canonical Region
  Name".
- `region_to_entsoe_code(canonical_region)` — canonical name → the code
  `entsoe-py` expects for querying it, including the handful of codes (`DE`,
  `IE`, `UK`, `DK1`, `DK2`) that aren't equal to their canonical name.
- `entsoe_subzones(canonical_region)` — the ENTSO-E bidding zones that
  collapse to a canonical region (e.g. `'IT'` → the 7 Italian bidding zones).
- `entsoe_code_to_region(code)` — inverse of `region_to_entsoe_code`.
- `zone_eic_code(zone)` / `zone_to_region(zone)` — the EIC code / region
  name of a zone in any spelling: a region name (`DK1`, `UK`), an
  `entsoe-py` area name (`DK_1`, `GB`) or an EIC code (`10YDK-1--------W`).

## Fetching data

- `get_api_key()` — reads `ENTSOE_API_KEY` from `.env`, or prompts for it.
- `fetch_annual_data(entsoe_query, year, bidding_zones, path, api_key)` —
  fetch a full calendar year of a single-zone query (e.g. `'load'`,
  `'day_ahead_prices'`, `'generation'`) for each zone, skipping any already
  downloaded and any ENTSO-E had no data for on an earlier run (listed in
  `<year>_<query>_nodata.txt`).
- `fetch_annual_transmission_data(entsoe_query, from_to_list, year, path, api_key)`
  — same, but for a border-pair query (e.g. `'crossborder_flows'`). A pair
  counts as downloaded if a file exists for it under any spelling of its
  zones, so `2023_DK_1-DE_LU_crossborder_flows.csv` also covers a request
  for `10YDK-1--------W` → `DE_LU`.
- `transmission_files(path, year)` / `find_transmission_file(path, year, from, to)`
  — the downloaded border files, one per directed pair of EIC codes, so a
  border saved under two spellings is never read twice.

Data is saved as one CSV per zone (or border) and query, named
`<year>_<zone>_<query>.csv` (or `<year>_<from>-<to>_<query>.csv`), in the
`path` folder, which must already exist. Zones with no data are reported and
skipped.

## Example

```python
from pathlib import Path
from pybalmorel.entsoe import get_api_key, fetch_annual_data, bidding_zones

Path("entsoe_data").mkdir(exist_ok=True)
api_key = get_api_key()
fetch_annual_data("load", 2024, bidding_zones, "entsoe_data", api_key)
```

## Command line

To download every zone in `bidding_zones`, and the flows between
neighbouring zones, without writing Python, use the backcasting
[`download` command](preparing_backcast.md#downloading-entso-e-data):

```bash
python -m pybalmorel.backcasting download <entsoe-data-path> <year>
```

`neighbour_pairs(zones)` gives the directed border pairs it queries.

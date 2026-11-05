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
- `fetch_annual_data(entsoe_query, year, bidding_zones, path, api_key, timeout=120)` —
  fetch a full calendar year of a single-zone query (e.g. `'load'`,
  `'day_ahead_prices'`, `'generation'`) for each zone, skipping any already
  downloaded and any ENTSO-E had no data for on an earlier run.
- `fetch_annual_transmission_data(entsoe_query, from_to_list, year, path, api_key, timeout=120)`
  — same, but for a border-pair query (e.g. `'crossborder_flows'`). A pair
  counts as downloaded if a file exists for it under any spelling of its
  zones, so `2023_DK_1-DE_LU_crossborder_flows.csv` also covers a request
  for `10YDK-1--------W` → `DE_LU`.
- `transmission_files(path, year)` / `find_transmission_file(path, year, from, to)`
  — the downloaded border files, one per directed pair of EIC codes, so a
  border saved under two spellings is never read twice.

Data is saved as one CSV per zone (or border) and query, named
`<year>_<zone>_<query>.csv` (or `<year>_<from>-<to>_<query>.csv`), in the
`path` folder, which must already exist.

Zones and pairs ENTSO-E answers "no matching data" for are written to
`<year>_<query>_nodata.txt` in `path` (one zone, or two tab-separated EIC
codes, per line) and skipped on later calls; delete a line or the file to
query them again. Timeouts, dropped connections and server errors are
reported but not remembered, so the next call retries them. `timeout` is in
seconds; without one, a connection lost mid-request would hang forever.

## Transmission map

`plot_transmission_map(path, year)` maps the downloaded `crossborder_flows`
between ENTSO-E's own bidding zones, as `entsoe-py` names them (`DE_LU`,
`DK_1`, `IT_NORD`, `IE_SEM`, ...). Nothing is translated to Balmorel regions
or Canonical Region Names. Each border with a downloaded file is drawn as a
line between its two zones. The line's width is proportional to the energy
that flowed over the border.

```python
from pybalmorel.entsoe import plot_transmission_map

# Net flows over 2024, arrows pointing at the net importer
fig, ax = plot_transmission_map("entsoe_data", 2024)

# Both directions added, for January, in GWh, zoomed in on the Nordics
fig, ax = plot_transmission_map(
    "entsoe_data", 2024, value="gross", start="2024-01-01", end="2024-02-01",
    unit="GWh", extent=(3, 53.5, 32, 71.5), line_label_show=True,
)
```

- `value` — `'net'` (flow one way minus the other, with an arrow towards the
  net importer) or `'gross'` (both ways added).
- `start` / `end` — limit the map to part of the year. Both are read as
  Brussels time; `end` itself is excluded.
- `extent` — `(lon min, lat min, lon max, lat max)` to show. Zones partly
  outside are clipped, and their lines meet in the part shown.
- `line_value_max` — the flow drawn at the widest line. Set it to compare
  several maps on one scale.
- `zone_coordinates` — `{zone: (lon, lat)}` where a zone's lines meet,
  instead of the centroid of its largest part.

See the docstring for the remaining styling options. Flows are physical, so
they include loop flows. A direction without a downloaded file counts as no
flow.

The data and outlines behind the map are available separately:

- `sum_crossborder_flows(path, year, start=None, end=None)` — the energy (MWh)
  over each directed border, with columns `From`, `To` and `Value`.
- `load_zone_geometries(zones, year=None)` — zone outlines in lon/lat. They come
  from `entsoe-py`, and from pybalmorel's geofiles for the zones `entsoe-py`
  has no outline for. GB is drawn with the UK's outline and `IE_SEM` with
  Ireland's, so Northern Ireland shows as part of GB. Before 2021, the
  Italian zones get their pre-2021 outlines.

## Production profile

`plot_profile(path, year, zones)` plots one or more zones' hourly production
from the downloaded files. The production is stacked by type, with net import
on top and the load drawn as a line. If day-ahead prices were downloaded,
they go in a panel below.

```python
from pybalmorel.entsoe import plot_profile

# DK1 in the last week of June
fig, axes = plot_profile("entsoe_data", 2023, "DK1", start="2023-06-26", end="2023-07-03")

# All 7 Italian zones summed, over the whole year
fig, axes = plot_profile("entsoe_data", 2023, "IT")

# Several zones, with your own title
fig, axes = plot_profile("entsoe_data", 2023, ["DK1", "DK2"], title="Denmark")

# Every zone with generation and load in the folder
fig, axes = plot_profile("entsoe_data", 2023, "all", start="2023-01-09", end="2023-01-16")
```

- `zones` — one zone or a list, in any spelling `zone_eic_code` accepts. A
  region made of several bidding zones (e.g. `'IT'`, `'NO'`) means all of
  them. The zones are summed, and their prices are weighted by their load.
  An hour missing for any of the zones is a gap in the sum, so a total that
  is missing a zone is never drawn.
- `zones='all'` — every zone with both generation and load in the folder.
  Zones with only one of them, or listed in a `_nodata.txt` file, are left
  out, as are zones without data in the period. The printout lists them
  under `Left out:`, e.g. `AL (no generation from ENTSO-E)`.
- `start` / `end` — limit the plot to part of the year. Both are read as
  Brussels time; `end` itself is excluded. The time axis is in Brussels time.
- The production types are grouped as Nuclear, Coal & lignite, Gas, Hydro,
  Biomass & waste, Wind, Solar and Oil & other (everything else). The groups
  are listed in `pybalmorel.entsoe.profile.production_groups`. Pumping
  consumption ('Actual Consumption') is left out.
- Net import is the flow into the zones from all their other neighbours,
  minus the flow out to them. Flows between the selected zones cancel out,
  including flows to LU when DE_LU is selected.
  Exports are drawn below 0. A direction without a downloaded file counts as
  no flow. Without any flow files, net import is left out.

Generation and load are required. If either is missing for any zone, the
function raises an error. The error lists each missing file, and whether
ENTSO-E has no data for the zone (it is in `<year>_<query>_nodata.txt`) or
the file was not downloaded. For files that were not downloaded, it also
prints the `download` command that fetches them. It also raises an error if
the files have no data in the period. Hours without data are left as gaps.
With several zones, the printout lists the zones with missing hours, the
most missing first. The energy totals then cover only the hours that every
zone has data for.

Every call prints the scope of the plot:

```text
ENTSO-E profile scope
  Zones:       DK_1 (10YDK-1--------W)
  Period:      2023-06-26 00:00 to 2023-07-03 00:00 Europe/Brussels (168 hours)
               = 2023-06-25 22:00 to 2023-07-02 22:00 UTC
  Generation:  2023_10YDK-1--------W_generation.csv - 10 production types, all 168 hours
  Load:        2023_10YDK-1--------W_load.csv - all 168 hours
  Price:       2023_10YDK-1--------W_day_ahead_prices.csv - all 168 hours
  Net import:  borders with DE_LU, DK_2, GB, NL, NO_2, SE_3
  Energy:      generation 428 GWh, net import -55 GWh, load 360 GWh
```

The data behind the plot is returned by `read_profile`, with the same
arguments. It returns an `EntsoeProfile` with `generation` (MW per
production type), `load`, `price` and `net_import`, indexed by hour in
Brussels time. `price` and `net_import` are None when there is no data for
them. Pass `verbose=False` to skip the printout.

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

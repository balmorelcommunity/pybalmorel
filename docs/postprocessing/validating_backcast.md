# Validating a Backcast

`pybalmorel.backcasting` compares a Backcast's simulated load, electricity
prices, generation and cross-border flows with ENTSO-E observations for the
Backcast Year. This is the last step of the workflow described in
[Preparing a Backcast](../preprocessing/preparing_backcast.md), which also
covers installation and configuration. Validation needs a GAMS
installation, since it reads the Backcast's `MainResults`.

It needs the Backcast Year's ENTSO-E `load`, `day_ahead_prices`,
`generation` and `crossborder_flows` files, downloaded with
[`download`](../preprocessing/preparing_backcast.md#downloading-entso-e-data).
If one of the first three is missing for that year, `format` warns and its
comparison comes out empty.

## CLI

```bash
# Fetch and format data for validation
python -m pybalmorel.backcasting format \
    <balmorel-scenario> \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year> \
    [--elpriceaggfunc mean] \
    [--overwrite] \
    [--allow-unmapped]

# Generate statistics
python -m pybalmorel.backcasting statistics <balmorel-scenario-path>

# Generate plots
python -m pybalmorel.backcasting generation <balmorel-scenario-path>
python -m pybalmorel.backcasting prices <balmorel-scenario-path>
python -m pybalmorel.backcasting price-duration <balmorel-scenario-path> [--ylim -60 320]
python -m pybalmorel.backcasting flows <balmorel-scenario-path>
```

`format` options:

- `--elpriceaggfunc` — how electricity prices are aggregated across the
  sub-regions of a canonical zone (any pandas aggregation, e.g. `mean`,
  `max`). Defaults to `mean`.
- `--overwrite` — regenerate the cached `.csv` files in
  `<scenario-path>/backcastoutput/` instead of reusing them.
- `--allow-unmapped` — compare technologies without a category as
  `Unmapped` instead of stopping (see
  [Technology categories](#technology-categories)).

:::{important}
Caches in `backcastoutput/` made before the switch to the UTC Backcast
Calendar ([ADR 0008](../adr/0008-backcast-calendar-utc.md)) are one hour
off after the March DST change. Rerun `format` with `--overwrite` once.
:::

Run `python -m pybalmorel.backcasting <command> --help` for details on each
command.

## Key features

- **Technology Categorisation**: `balmorel_to_category`/`entsoe_to_category`
  standardise generation technologies between Balmorel and ENTSO-E so they can
  be compared (see [Technology categories](#technology-categories)).
- **Spatial Aggregation**: sums sub-regions to their canonical zone
  (`DE4-*` → `DE`, `IT-*` → `IT`) before comparing.
- **Full hourly grid**: generation is outer-joined per (region, category,
  hour) over the regions both sides have. A missing Balmorel value is 0,
  since `MainResults` leaves out zeros; a missing ENTSO-E value is 0 only in
  hours in which ENTSO-E reports some generation for the region, and a
  region's hour without any ENTSO-E data is dropped from both sides. Load
  and prices keep the inner join, and `format` warns about a region with
  fewer hours than the Backcast Calendar on either side.
- **Prices in the Backcast Year's euros**: Balmorel's prices (€2016, the
  [Price Year](../preprocessing/preparing_backcast.md#price-year)) are
  converted to nominal euros of the Backcast Year, so `prices.csv` holds
  both sides in the euros the market reported. The cached
  `balmorel_prices.csv` stays in €2016.
- **Load without storage charging**: ENTSO-E's actual total load excludes
  storage charging, so Balmorel's `ENDO_INTRASTO` load is left out of the
  comparison (see [Load components](#load-components)).
- **Label matching**: Balmorel results are mapped onto the
  [Backcast Calendar](../preprocessing/preparing_backcast.md#key-features)
  by their (Season, Term) labels, never by position.
- **Flow validation**: compares Balmorel's hourly flows with ENTSO-E's per
  directed border, using the same ENTSO-E flow files as the transmission
  overrides (see [Flow validation](#flow-validation)).

## Technology categories

Every Balmorel technology (`COMMODITY - FUEL`, e.g. `CONDENSING - SHALE`)
and every ENTSO-E production type must have a category in
`balmorel_to_category`/`entsoe_to_category` in
`pybalmorel/backcasting/__main__.py`. If one doesn't, `format` stops with a
`ValueError` that names it with its annual energy in TWh. Add it to the
mapping, or rerun with `--allow-unmapped` to compare it as `Unmapped`, which
then shows up in the `generation` table and plots. Earlier versions dropped
such technologies with a warning; in the 2023 backcast this left out all
observed run-of-river hydro (a misspelt key), about 170 TWh, and Estonia's
oil-shale condensing fleet. Rerun `format` with `--overwrite` on caches made
before the fix.

Oil shale is `Fossil Solid` on both sides, since it is burned as a solid
fuel.

ENTSO-E's former "Storage & Flexibility" is split in four:

| Category | ENTSO-E | Balmorel |
|---|---|---|
| Storage | Hydro Pumped Storage, Energy storage | `INTRASEASONAL-ELECT-STORAGE - ELECTRIC` |
| Other renewable | Geothermal, Marine, Other renewable | – |
| Other | Other | `CHP-BACK-PRESSURE - HEAT`, the heat storages, `ELECT-TO-HEAT - ELECTRIC` |
| Backup | – | `CONDENSING - DUMMY` |

ENTSO-E's "Other" is mostly gas CHP of unreported fuel (NL, IT), so it
shows where Balmorel's gas has to go. "Storage" checks the price spread,
since pumped storage only cycles when prices vary. "Backup" should be
close to 0.

## Price duration curves

`price-duration` reads `backcastoutput/prices.csv` and saves
`price_duration_curves.png`: Balmorel's and ENTSO-E's price duration curves
with all region-hours pooled in one large panel, then one small panel per
region. Every panel has the same y-range (`--ylim`, -60 to 320 €/MWh by
default); prices outside it are clipped and counted in the subtitle. Both
sides are in nominal euros of the Backcast Year.

## Load components

`format` also writes `backcastoutput/load_components.csv`: Balmorel's
annual load (TWh) per region and `EL_DEMAND_YCRST` category, with
storage charging (`ENDO_INTRASTO`) listed but marked as excluded. A
`Total compared` row per region sums the other categories next to
ENTSO-E's annual load over the Backcast Calendar. It shows which part of
Balmorel's load misses ENTSO-E's.

## Calibration Inputs

A result that is a Calibration Input of the Backcast is no longer
independent evidence, since it was derived from the data it is compared
with. Depending on which preparation commands were run:

- **Demand profiles**
  ([`demand-profile`](../preprocessing/preparing_backcast.md#demand-profiles)):
  the load-shape correlation that `statistics` prints compares observed
  load with itself, up to Balmorel's endogenous demand.
- **Demand level**
  ([`demand-level`](../preprocessing/preparing_backcast.md#demand-level)):
  with the `entsoe` basis, a country's annual load matches ENTSO-E's up to
  Balmorel's electric heating. Only the endogenous demand (heat pumps,
  electric boilers, EVs, electrolysis) remains to be validated;
  `load_components.csv` shows it per category.
- **VRE level** ([`vre-flh`](../preprocessing/preparing_backcast.md#vre-level)):
  a country's annual wind and solar output matches ENTSO-E's up to
  curtailment. Their hourly timing, which comes from the weather year,
  is still a check.
- **Nuclear and thermal availability, and the must-run floor**
  ([`nuclear-availability`](../preprocessing/preparing_backcast.md#nuclear-availability),
  [`thermal-availability`](../preprocessing/preparing_backcast.md#thermal-availability),
  [`must-run-floor`](../preprocessing/preparing_backcast.md#must-run-floor)):
  annual nuclear output and the bottom of the fossil mix are set. Prices,
  flows, the fossil mix above the floor, and the timing of nuclear and
  hydro output within the year stay Validation Metrics.

## Flow validation

`format` also writes `backcastoutput/flows.csv`: Balmorel's `X_FLOW_YCRST`
next to the ENTSO-E physical flows, per directed border and hour. Both sides
are summed up to Canonical Region Names (`DE4-*` → `DE`, the Italian
sub-zones → `IT`), and internal links are dropped. Hours Balmorel leaves out
of its results count as zero flow. Each border's Observed Flow Limit (the
same total written to `XKFX_ENTSOE.inc`, see
[ADR 0010](../adr/0010-observed-flow-limit-percentile.md)) is stored as
`Limit`. Pass `format` the same `--percentile` as `transmission-flow-limit`
(default 99 for both) so the two agree.

`statistics` then prints, per border, the annual energy of both datasets,
their correlation, the RMSE, and the share of hours each spends within 1%
of the limit. ENTSO-E exceeds the limit in about 1% of its flowing hours by
construction, while Balmorel cannot. If Balmorel sits at the limit far more
often than ENTSO-E does, the Observed Flow Limit is binding more than it did
in reality. The
`flows` command plots duration curves per border.

ENTSO-E flows are physical, including loop flows, while Balmorel's are
commercial. Some borders will therefore mismatch for reasons the model
cannot reproduce.

## Output

`format` caches the Balmorel results and writes the joined comparison data
to `<scenario-path>/backcastoutput/` (`loads.csv`, `prices.csv`,
`generation.csv`, `flows.csv`, `load_components.csv`). The plot commands save their figures to the
current folder.

## Data flow

1. Balmorel results extracted from GDX files via `MainResults`.
2. ENTSO-E data for the Backcast Year read from `<entsoe-data-path>`.
3. Both datasets mapped onto the UTC Backcast Calendar and canonical regions.
4. Datasets aligned and joined for comparison (`format`).
5. Statistics calculated and visualisations generated.

## Limitations

- No data available for Cyprus (CY) or Turkey (TR) in ENTSO-E.
- Some bidding zones may lack complete data coverage.
- Cross-border flow data requires explicit region pairs.
- ENTSO-E data is fetched for the Brussels calendar year, so the last UTC
  hour of a Backcast Calendar that ends on 31 December may be missing; it is
  left out of the comparison.

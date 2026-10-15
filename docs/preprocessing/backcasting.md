# Backcasting: Validating Balmorel Against ENTSO-E

`pybalmorel.backcasting` compares simulated Balmorel behaviour for a
historical year against ENTSO-E observations, and derives the `XKFX`
(exogenous transmission capacity) backcast override from ENTSO-E's Observed
Max Flow (see [`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md) and ADRs
[0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md),
[0006](../adr/0006-xkfx-override-file-not-regeneration.md) and
[0007](../adr/0007-split-entsoe-and-backcasting-packages.md)). It also
writes season- and hour-resolved historical [fuel prices](#fuel-prices) and
a [CO2 tax](#co2-tax) for the Backcast Year.
It depends on [`pybalmorel.entsoe`](entsoe.md) for raw data access and on
`pybalmorel.MainResults` for Balmorel results — never the other way round.

## Installation

Backcasting needs the `entso-e` extra and a GAMS installation (for reading
Balmorel results):

```bash
pip install pybalmorel[entso-e]
```

## CLI

```bash
# Fetch and format data for validation
python -m pybalmorel.backcasting format \
    <balmorel-scenario> \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year> \
    [--elpriceaggfunc mean] \
    [--overwrite]

# Generate statistics
python -m pybalmorel.backcasting statistics <balmorel-scenario-path>

# Generate plots
python -m pybalmorel.backcasting generation <balmorel-scenario-path>
python -m pybalmorel.backcasting prices <balmorel-scenario-path>
python -m pybalmorel.backcasting flows <balmorel-scenario-path>

# Write XKFX_ENTSOE.inc: transmission overrides from ENTSO-E Observed Max Flow
python -m pybalmorel.backcasting transmission-max-flow \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year>

# Write FUELPRICE.inc + FUELPRICE_CONSTANT.inc: historical NATGAS/COAL prices
python -m pybalmorel.backcasting fuelprices \
    <balmorel-scenario-path> \
    <historicalprices-path> \
    <year>

# Write TAX_CO2_ST.inc: historical EUA price as CO2 tax
python -m pybalmorel.backcasting co2-tax \
    <balmorel-scenario-path> \
    <historicalprices-path> \
    <year> \
    [--co2-override UNITED_KINGDOM=85 --co2-override SERBIA=0]
```

`format` options:

- `--elpriceaggfunc` — how electricity prices are aggregated across the
  sub-regions of a canonical zone (any pandas aggregation, e.g. `mean`,
  `max`). Defaults to `mean`.
- `--overwrite` — regenerate the cached `.csv` files in
  `<scenario-path>/backcastoutput/` instead of reusing them.

:::{important}
Caches in `backcastoutput/` made before the switch to the UTC Backcast
Calendar ([ADR 0008](../adr/0008-backcast-calendar-utc.md)) are one hour
off after the March DST change. Rerun `format` with `--overwrite` once.
:::

Run `python -m pybalmorel.backcasting <command> --help` for details on each
command.

## Key features

- **Backcast Calendar**: every timestamp ↔ (Season, Term) conversion goes
  through `pybalmorel.backcasting.calendar`. S01 T001 is 00:00 UTC on the
  first Monday of the year, and every day has 24 terms (see
  [ADR 0008](../adr/0008-backcast-calendar-utc.md)). Balmorel results are
  matched by label, never by position. Inputs not in UTC, such as a demand
  series in local time, must be converted before they are mapped onto it.
- **Bidding Zone Mapping**: uses `bidding_zone_codes`/`bidding_zone_translation`
  from `pybalmorel.entsoe` to bridge ENTSO-E bidding zones and Balmorel regions.
- **Technology Categorisation**: `balmorel_to_category`/`entsoe_to_category`
  standardise generation technologies between Balmorel and ENTSO-E so they can
  be compared.
- **Spatial Aggregation**: sums sub-regions to their canonical zone
  (`DE4-*` → `DE`, `IT-*` → `IT`) before comparing.
- **Transmission overrides**: `flows.py` computes the Observed Max Flow per
  border and writes it to `XKFX_ENTSOE.inc` (see ADRs
  [0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md) and
  [0006](../adr/0006-xkfx-override-file-not-regeneration.md)) — a
  non-destructive override file, never a rewrite of the base `XKFX.inc`.
- **Flow validation**: compares Balmorel's hourly flows with ENTSO-E's per
  directed border, using the same ENTSO-E flow files as the transmission
  overrides (see [Flow validation](#flow-validation)).

## Price Year

All generated prices are in €2016. Nominal prices are converted from USD
at the Eurostat annual-average EUR/USD rate of the Backcast Year and
deflated with the annual euro-area HICP. Both tables are bundled in
`pybalmorel.backcasting.pricelevel` (see
[ADR 0009](../adr/0009-price-year-bundled-deflator-table.md)), with the
Eurostat dataset codes next to them; extend them when a new year is needed.

## Fuel prices

The `fuelprices` command converts historical daily fuel prices into Balmorel's
season- and hour-resolved `FUELPRICE(YYY,AAA,FFF,SSS,TTT)` input, so a
backcast sees the fuel prices of the actual year. It reads two CSV files
from `<historicalprices-path>`:

| Fuel | File | Unit |
|---|---|---|
| `NATGAS` | `natural_gas_TTF_<year>.csv` (TTF futures) | €/MWh, converted to €/GJ |
| `COAL` | `Rotterdam Coal Futures Historical Data.csv` (must cover the year) | USD/t, converted to €/GJ with 30.2 GJ/t |

Daily prices apply to the UTC calendar day on the Backcast Calendar,
carrying the last price forward over weekends and holidays. Two files are
written to `<scenario-path>/data/`:

- `FUELPRICE.inc` — the (S,T)-resolved NATGAS and COAL prices.
- `FUELPRICE_CONSTANT.inc` — flags every other fuel as constant over the year.

Only natural gas and coal are covered; oil is not covered yet. For annual
averages instead, see the
[average fuel prices CLI](economics.md#average-fuel-prices-cli).

## CO2 tax

The `co2-tax` command converts the EEX EUA primary-auction results into
Balmorel's `TAX_CO2_ST(YYY,CCC,SSS,TTT)` input (see ADR 0002 in the
Balmorel repo) and writes `<scenario-path>/data/TAX_CO2_ST.inc`. It reads
`emission-spot-primary-market-auction-report-<year>-data.xlsx`, found
anywhere under `<historicalprices-path>`, downloaded from
[EEX](https://www.eex.com/en/market-data/market-data-hub/environmentals/eex-eua-primary-auction-spot-download).

Only successful auctions are used. Days with several auctions (EU, DE, PL)
get the mean clearing price, and days without one carry the last price
forward.

Every country gets the EUA price. Use `--co2-override COUNTRY=VALUE`
(repeatable, Balmorel `CCC` names, nominal €/tCO2 of the Backcast Year) for
countries with a different carbon price, such as the UK, or `0` for
countries without one.

:::{note}
`fuelprices` and `co2-tax` never edit the scenario's options, but they warn
when Balmorel would ignore what they wrote:

- `balopt.opt` (the scenario's own, else `base/model/balopt.opt`) must set
  `FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT` and `TAX_CO2_DOL=YYY_CCC_SSS_TTT`.
- `HYDROGEN_FUELPRICE.inc` must not assign COAL or NATGAS prices, since
  `FUELPRICE_HYDROGEN` overrides `IFUELPRICE` wherever it is nonzero.
:::

## Flow validation

`format` also writes `backcastoutput/flows.csv`: Balmorel's `X_FLOW_YCRST`
next to the ENTSO-E physical flows, per directed border and hour. Both sides
are summed up to Canonical Region Names (`DE4-*` → `DE`, the Italian
sub-zones → `IT`), and internal links are dropped. Hours Balmorel leaves out
of its results count as zero flow. Each border's Observed Max Flow (the
same total written to `XKFX_ENTSOE.inc`) is stored as `Limit`.

`statistics` then prints, per border, the annual energy of both datasets,
their correlation, the RMSE, and the share of hours each spends within 1%
of the limit. If Balmorel sits at the limit far more often than ENTSO-E
does, the Observed Max Flow is binding more than it did in reality. The
`flows` command plots duration curves per border.

ENTSO-E flows are physical, including loop flows, while Balmorel's are
commercial. Some borders will therefore mismatch for reasons the model
cannot reproduce.

## Configuration

- **API Key**: set `ENTSOE_API_KEY` in `.env`, or provide it when prompted.
- **GAMS Path**: set `GAMS_SYSTEM_DIR` in `.env` for Balmorel result processing.
- **Output**: processed comparison data cached in
  `<scenario-path>/backcastoutput/`; XKFX, fuel price and CO2 tax overrides
  written to `<scenario-path>/data/`.

## Data flow

1. Raw ENTSO-E data fetched via `pybalmorel.entsoe` and saved as CSV.
2. Balmorel model results extracted from GDX files via `MainResults`.
3. Both datasets mapped onto the UTC Backcast Calendar and canonical regions.
4. Datasets aligned and joined for comparison (`format`), or the XKFX
   override is computed directly from ENTSO-E flows
   (`transmission-max-flow`), or historical prices are written
   (`fuelprices`, `co2-tax`).
5. Statistics calculated and visualisations generated.

## Limitations

- No data available for Cyprus (CY) or Turkey (TR) in ENTSO-E.
- Some bidding zones may lack complete data coverage.
- Cross-border flow data requires explicit region pairs.
- ENTSO-E data is fetched for the Brussels calendar year, so the last UTC
  hour of a Backcast Calendar that ends on 31 December may be missing; it is
  left out of the comparison.

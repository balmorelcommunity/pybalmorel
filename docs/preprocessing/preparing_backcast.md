# Preparing a Backcast

A Backcast is a Balmorel scenario run for one historical Backcast Year,
so its results can be compared with what actually happened (see
[`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md)).
`pybalmorel.backcasting` covers the whole workflow:

1. **Prepare** the Backcast's inputs: download ENTSO-E data, derive the
   `XKFX` transmission override from ENTSO-E's Observed Max Flow, and write
   season- and hour-resolved historical [fuel prices](#fuel-prices) and a
   [CO2 tax](#co2-tax) for the Backcast Year. This page.
2. **Run** the Balmorel scenario as usual.
3. **Validate** the Backcast's results against ENTSO-E observations. See
   [Validating a Backcast](../postprocessing/validating_backcast.md).

The transmission override follows ADRs
[0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md),
[0006](../adr/0006-xkfx-override-file-not-regeneration.md) and
[0007](../adr/0007-split-entsoe-and-backcasting-packages.md).
`pybalmorel.backcasting` depends on [`pybalmorel.entsoe`](entsoe.md) for raw
data access and on `pybalmorel.MainResults` for Balmorel results — never the
other way round.

## Installation

Backcasting needs the `entso-e` extra:

```bash
pip install pybalmorel[entso-e]
```

A GAMS installation is also needed for reading Balmorel results, i.e. for
`transmission-max-flow` (which reads the scenario's `XKFX` borders) and for
[validating a Backcast](../postprocessing/validating_backcast.md).

## CLI

```bash
# Download ENTSO-E load, prices, generation and cross-border flows
python -m pybalmorel.backcasting download \
    <entsoe-data-path> \
    <year> \
    [--query load --query crossborder_flows]

# Write XKFX_ENTSOE.inc: transmission overrides from ENTSO-E Observed Max Flow
python -m pybalmorel.backcasting transmission-max-flow \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year>

# Split a saved Yahoo Finance TTF=F page into natural_gas_TTF_<year>.csv
python -m pybalmorel.backcasting ttf-csv <html-path> <historicalprices-path>

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

Run `python -m pybalmorel.backcasting <command> --help` for details on each
command.

## Downloading ENTSO-E data

`download` fetches the Backcast Year's ENTSO-E data into `<entsoe-data-path>`,
for every zone in `pybalmorel.entsoe.bidding_zones`:

| `--query` | Files | Used by |
|---|---|---|
| `load` | `<year>_<zone>_load.csv` | `format` |
| `day_ahead_prices` | `<year>_<zone>_day_ahead_prices.csv` | `format` |
| `generation` | `<year>_<zone>_generation.csv` | `format` |
| `crossborder_flows` | `<year>_<from>-<to>_crossborder_flows.csv` | `transmission-max-flow`, `format` |

Without `--query`, all four are downloaded. `--query` is repeatable.

Flows are fetched for every directed pair of neighbouring zones. Files that
already exist are skipped, and so are pairs ENTSO-E had no data for on an
earlier run (listed in `<year>_crossborder_flows_nodata.txt`; delete it to
query them again). Failed requests don't stop the download, so rerun the
command to retry them.

## Key features

- **Backcast Calendar**: every timestamp ↔ (Season, Term) conversion goes
  through `pybalmorel.backcasting.calendar`. S01 T001 is 00:00 UTC on the
  first Monday of the year, and every day has 24 terms (see
  [ADR 0008](../adr/0008-backcast-calendar-utc.md)). Balmorel results are
  matched by label, never by position. Inputs not in UTC, such as a demand
  series in local time, must be converted before they are mapped onto it.
- **Bidding Zone Mapping**: uses `bidding_zone_codes`/`bidding_zone_translation`
  from `pybalmorel.entsoe` to bridge ENTSO-E bidding zones and Balmorel regions.
- **Transmission overrides**: `flows.py` computes the Observed Max Flow per
  border and writes it to `XKFX_ENTSOE.inc` (see ADRs
  [0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md) and
  [0006](../adr/0006-xkfx-override-file-not-regeneration.md)) — a
  non-destructive override file, never a rewrite of the base `XKFX.inc`.

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
Backcast sees the fuel prices of the actual year. It reads two CSV files
from `<historicalprices-path>`:

| Fuel | File | Unit |
|---|---|---|
| `NATGAS` | `natural_gas_TTF_<year>.csv` (TTF futures, see [below](#getting-the-ttf-price-files)) | €/MWh, converted to €/GJ |
| `COAL` | `Rotterdam Coal Futures Historical Data.csv` (must cover the year) | USD/t, converted to €/GJ with 30.2 GJ/t |

### Getting the TTF price files

Yahoo Finance only lets paying users download its history as CSV. Instead,
open <https://finance.yahoo.com/quote/TTF%3DF/history/>, choose a date range
(it can span several years), and save the page from the browser as HTML.
Then run `ttf-csv` on it:

```bash
python -m pybalmorel.backcasting ttf-csv \
    "2020-2025 Dutch TTF Natural Gas Calendar (TTF=F) Stock Historical Prices & Data - Yahoo Finance.html" \
    <historicalprices-path>
```

This writes one `natural_gas_TTF_<year>.csv` per calendar year on the page,
overwriting any that already exist. Each file has the columns
`Date,Open,High,Low,Close,Adj Close,Volume`. `Date` has no year (`Dec 30`),
and `Volume` has no thousands separators, so the file is valid CSV. The
`fuelprices` command uses `Adj Close`.

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

## Configuration

- **API Key**: set `ENTSOE_API_KEY` in `.env`, or provide it when prompted.
- **GAMS Path**: set `GAMS_SYSTEM_DIR` in `.env` for Balmorel result processing.
- **Output**: raw ENTSO-E data in `<entsoe-data-path>`; XKFX, fuel price
  and CO2 tax overrides written to `<scenario-path>/data/`; validation
  data cached in `<scenario-path>/backcastoutput/`.

## Data flow

1. Raw ENTSO-E data fetched via `pybalmorel.entsoe` (`download`) and saved
   as CSV.
2. The XKFX override is computed from the ENTSO-E flows
   (`transmission-max-flow`).
3. Historical prices are mapped onto the UTC Backcast Calendar and written
   (`fuelprices`, `co2-tax`).

The Backcast is then run in Balmorel and
[validated](../postprocessing/validating_backcast.md).

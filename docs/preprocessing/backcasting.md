# Backcasting: Validating Balmorel Against ENTSO-E

`pybalmorel.backcasting` compares simulated Balmorel behaviour for a
historical year against ENTSO-E observations, and derives the `XKFX`
(exogenous transmission capacity) backcast override from ENTSO-E's Observed
Max Flow (see [`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md) and ADRs
[0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md),
[0006](../adr/0006-xkfx-override-file-not-regeneration.md) and
[0007](../adr/0007-split-entsoe-and-backcasting-packages.md)). It can also
write season- and hour-resolved historical fuel prices (see [Fuel prices](#fuel-prices)).
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

# Write XKFX_ENTSOE.inc: transmission overrides from ENTSO-E Observed Max Flow
python -m pybalmorel.backcasting transmission-max-flow \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year>

# Write FUELPRICE.inc + FUELPRICE_CONSTANT.inc: historical NATGAS/COAL prices
python -m pybalmorel.backcasting fuelprices \
    <balmorel-scenario-path> \
    <historicalprices-path> \
    <year> \
    --eur-per-usd <rate>
```

`format` options:

- `--elpriceaggfunc` — how electricity prices are aggregated across the
  sub-regions of a canonical zone (any pandas aggregation, e.g. `mean`,
  `max`). Defaults to `mean`.
- `--overwrite` — regenerate the cached `.csv` files in
  `<scenario-path>/backcastoutput/` instead of reusing them.

Run `python -m pybalmorel.backcasting <command> --help` for details on each
command.

## Key features

- **Bidding Zone Mapping**: uses `bidding_zone_codes`/`bidding_zone_translation`
  from `pybalmorel.entsoe` to bridge ENTSO-E bidding zones and Balmorel regions.
- **Technology Categorisation**: `balmorel_to_category`/`entsoe_to_category`
  standardise generation technologies between Balmorel and ENTSO-E so they can
  be compared.
- **Temporal Alignment**: converts Balmorel's seasonal time slices to
  ENTSO-E's hourly timestamps.
- **Spatial Aggregation**: sums sub-regions to their canonical zone
  (`DE4-*` → `DE`, `IT-*` → `IT`) before comparing.
- **Transmission overrides**: `flows.py` computes the Observed Max Flow per
  border and writes it to `XKFX_ENTSOE.inc` (see ADRs
  [0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md) and
  [0006](../adr/0006-xkfx-override-file-not-regeneration.md)) — a
  non-destructive override file, never a rewrite of the base `XKFX.inc`.

## Fuel prices

The `fuelprices` command converts historical daily fuel prices into Balmorel's
season- and hour-resolved `FUELPRICE(YYY,AAA,FFF,SSS,TTT)` input, so a
backcast sees the fuel prices of the actual year. It reads two CSV files
from `<historicalprices-path>`:

| Fuel | File | Unit |
|---|---|---|
| `NATGAS` | `natural_gas_TTF_<year>.csv` (TTF futures) | €/MWh, converted to €/GJ |
| `COAL` | `Rotterdam Coal Futures Historical Data.csv` | USD/t, converted to €/GJ with `--eur-per-usd` and 30.2 GJ/t |

Daily prices are mapped onto the S01–S52 × T001–T168 backcast grid (the
same first-Monday-to-last-Sunday window as the ENTSO-E comparison), carrying
the last price forward over weekends and holidays. Two files are written to
`<scenario-path>/data/`:

- `FUELPRICE.inc` — the (S,T)-resolved NATGAS and COAL prices.
- `FUELPRICE_CONSTANT.inc` — flags every other fuel as constant over the year.

Only natural gas and coal are covered: CO2 belongs to `EMI_POL`, not
`FUELPRICE`, and oil is not covered yet. For annual averages instead, see the
[average fuel prices CLI](economics.md#average-fuel-prices-cli).

:::{note}
The scenario's `balopt.opt` must set `FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT`
for Balmorel to read the (S,T)-resolved prices; the command does not set
this. Also check that no other input (e.g. `HYDROGEN_FUELPRICE.inc`) hardcodes
COAL or NATGAS prices, or the override is silently ignored for those fuels.
:::

## Configuration

- **API Key**: set `ENTSOE_API_KEY` in `.env`, or provide it when prompted.
- **GAMS Path**: set `GAMS_SYSTEM_DIR` in `.env` for Balmorel result processing.
- **Output**: processed comparison data cached in
  `<scenario-path>/backcastoutput/`; XKFX overrides written to
  `<scenario-path>/data/XKFX_ENTSOE.inc`.

## Data flow

1. Raw ENTSO-E data fetched via `pybalmorel.entsoe` and saved as CSV.
2. Balmorel model results extracted from GDX files via `MainResults`.
3. Both datasets formatted to a common temporal and regional structure.
4. Datasets aligned and joined for comparison (`format`), or the XKFX
   override is computed directly from ENTSO-E flows
   (`transmission-max-flow`), or historical fuel prices are written
   (`fuelprices`).
5. Statistics calculated and visualisations generated.

## Limitations

- No data available for Cyprus (CY) or Turkey (TR) in ENTSO-E.
- Some bidding zones may lack complete data coverage.
- Cross-border flow data requires explicit region pairs.

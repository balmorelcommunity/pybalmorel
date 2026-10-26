# Preparing a Backcast

A Backcast is a Balmorel scenario run for one historical Backcast Year,
so its results can be compared with what actually happened (see
[`CONTEXT.md`](https://github.com/Mathias157/pybalmorel/blob/master/CONTEXT.md)).
`pybalmorel.backcasting` covers the whole workflow:

1. **Prepare** the Backcast's inputs: download ENTSO-E data, derive the
   `XKFX` transmission override from ENTSO-E's Observed Flow Limit, the
   weekly [nuclear availability](#nuclear-availability), the
   [electricity demand profiles](#demand-profiles), and write
   season- and hour-resolved historical [fuel prices](#fuel-prices) and a
   [CO2 tax](#co2-tax) for the Backcast Year. This page.
2. **Run** the Balmorel scenario as usual.
3. **Validate** the Backcast's results against ENTSO-E observations. See
   [Validating a Backcast](../postprocessing/validating_backcast.md).

The transmission override follows ADRs
[0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md),
[0006](../adr/0006-xkfx-override-file-not-regeneration.md),
[0007](../adr/0007-split-entsoe-and-backcasting-packages.md) and
[0010](../adr/0010-observed-flow-limit-percentile.md).
`pybalmorel.backcasting` depends on [`pybalmorel.entsoe`](entsoe.md) for raw
data access and on `pybalmorel.MainResults` for Balmorel results — never the
other way round.

## Installation

Backcasting needs the `entso-e` extra:

```bash
pip install pybalmorel[entso-e]
```

A GAMS installation is also needed for reading Balmorel results, i.e. for
`transmission-flow-limit` (which reads the scenario's `XKFX` borders) and for
[validating a Backcast](../postprocessing/validating_backcast.md).

## CLI

```bash
# Download ENTSO-E load, prices, generation and cross-border flows
python -m pybalmorel.backcasting download \
    <entsoe-data-path> \
    <year> \
    [--query load --query crossborder_flows]

# Write XKFX_ENTSOE.inc: transmission overrides from the ENTSO-E Observed Flow Limit
python -m pybalmorel.backcasting transmission-flow-limit \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year> \
    [--percentile 99]

# Write GKRATE_ENTSOE.inc: weekly nuclear availability from ENTSO-E nuclear output
python -m pybalmorel.backcasting nuclear-availability \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year> \
    [--reload-input]

# Write DE_VAR_T_ENTSOE.inc: electricity demand profiles from ENTSO-E actual load
python -m pybalmorel.backcasting demand-profile \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year> \
    [--reload-input]

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
| `load` | `<year>_<zone>_load.csv` | `format`, `demand-profile` |
| `day_ahead_prices` | `<year>_<zone>_day_ahead_prices.csv` | `format` |
| `generation` | `<year>_<zone>_generation.csv` | `format`, `nuclear-availability` |
| `crossborder_flows` | `<year>_<from>-<to>_crossborder_flows.csv` | `transmission-flow-limit`, `format` |

Without `--query`, all four are downloaded. `--query` is repeatable.

Flows are fetched for every directed pair of neighbouring zones.

The download can be stopped and rerun at any time. On a rerun:

- Files that already exist are skipped.
- Zones and pairs ENTSO-E answered "no matching data" for on an earlier
  run are skipped. They are listed in `<year>_<query>_nodata.txt` in
  `<entsoe-data-path>`, one zone per line (or, for flows, two EIC codes
  separated by a tab). Delete a line to query that zone or pair again, or
  the whole file to query them all again, e.g. if ENTSO-E has since
  published the data.
- Failed requests are retried. Timeouts, dropped connections and server
  errors are never written to the `_nodata.txt` files, and don't stop the
  download. Requests time out after 120 seconds, so a connection lost
  mid-request, e.g. when switching networks, doesn't hang the download.

## Key features

- **Backcast Calendar**: every timestamp ↔ (Season, Term) conversion goes
  through `pybalmorel.backcasting.calendar`. S01 T001 is 00:00 UTC on the
  first Monday of the year, and every day has 24 terms (see
  [ADR 0008](../adr/0008-backcast-calendar-utc.md)). Balmorel results are
  matched by label, never by position. Inputs not in UTC, such as a demand
  series in local time, must be converted before they are mapped onto it.
- **Bidding Zone Mapping**: uses `bidding_zone_codes`/`bidding_zone_translation`
  from `pybalmorel.entsoe` to bridge ENTSO-E bidding zones and Balmorel regions.
- **Transmission overrides**: `flows.py` computes the Observed Flow Limit
  per border and writes it to `XKFX_ENTSOE.inc` (see ADRs
  [0005](../adr/0005-observed-max-flow-not-ntc-for-backcasting.md),
  [0006](../adr/0006-xkfx-override-file-not-regeneration.md) and
  [0010](../adr/0010-observed-flow-limit-percentile.md)) — a
  non-destructive override file, never a rewrite of the base `XKFX.inc`.
  The limit is a percentile (`--percentile`, default 99) of the hourly flow
  in one direction, over the hours with flow in that direction, after
  summing every ENTSO-E zone pair of the border hour by hour. A direction
  without flow gets 0, and `--percentile 100` gives the maximum. The
  `transmission-flow-limit` command replaces `transmission-max-flow`, which
  took the yearly maximum; there is no alias for the old name.

## Nuclear availability

The `nuclear-availability` command writes `<scenario-path>/data/GKRATE_ENTSOE.inc`:
one `GKRATE` per nuclear (area, technology) and Backcast Calendar week. The
rating is the country's Nuclear Availability: the highest hourly nuclear
output ENTSO-E reports for that week, divided by the country's nuclear
`GKFX` in the Backcast Year, clipped at 1. It reads the generation files
`download --query generation` fetched; it does not fetch.

- Nuclear technologies are those whose `GDATA(G,'GDFUEL')` is
  `FDATA('NUCLEAR','FDACRONYM')`. `GKFX` is read through GAMS from the
  scenario's cached `<scenario>_input_data.gdx`, or by running ReadData if
  it isn't cached. The command warns if a file in `<scenario>/data` is newer
  than the cache, which then misses it; `--reload-input` runs ReadData again
  (more than 20 minutes on the backcast).
- Every nuclear technology in a country gets the same rating, since ENTSO-E
  only reports nuclear output per bidding zone. Areas are grouped by
  Canonical Region Name (`FIN` → `FI`, `DE4-*` → `DE`).
- A rating of 0 is written as `eps`, since Balmorel reads a literal 0 as
  "no rating" and uses full capacity.
- Weeks without data after a country's last week with data are a closure:
  ENTSO-E stops reporting a closed fleet instead of reporting zeros (Germany
  in 2023 after 15 April). They are written as `eps`, with a loud warning,
  since a feed that simply stops looks the same.
- Any other week without data gets no line and keeps the base rating. Countries with
  nuclear `GKFX` but no ENTSO-E nuclear output, or the other way round, are
  reported and left out.

The scenario's `data/GKRATE.inc` must include the file after the base
ratings (the command warns if it doesn't):

```gams
$if EXIST '../data/GKRATE_ENTSOE.inc' $INCLUDE '../data/GKRATE_ENTSOE.inc';
```

The nuclear availability is a Calibration Input: nuclear output that it
fixes by construction is not evidence in Backcast validation.

## Demand profiles

The `demand-profile` command writes `<scenario-path>/data/DE_VAR_T_ENTSOE.inc`:
the hourly ENTSO-E actual load of the Backcast Year on the Backcast
Calendar, as `DE_VAR_T` of the electricity users `OTHER` and `RESE` (set
equal to `OTHER`) in every region with electricity demand. `PII` keeps its
profile. Balmorel scales `DE_VAR_T` to the annual `DE`, which still comes
from the scenario's input data, so only the shape is replaced. It reads the
load files `download --query load` fetched; it does not fetch.

It exists because the weather-year electricity demand profiles
(`classic_demand.csv`) are corrupt from 2022 onwards: negative hours down to
-1e13 in LV and LT, spikes of 20-60 times the median in NL and EE, and
copies of one profile in sub-areas. In the 2023 backcast, NL's demand
peaked at 136 GW (observed: about 19 GW). The weather-year demand step now
[checks the profiles](multi_weather_year_input.md#demand-plausibility-check),
but the backcast should use the observed load anyway.

- Regions and the current profiles are read through GAMS from the
  scenario's cached `<scenario>_input_data.gdx`, as for
  [nuclear availability](#nuclear-availability), with the same staleness
  warning and `--reload-input`.
- Bidding zones are summed to their Canonical Region Name (`IT-*` → `IT`);
  an hour missing in one zone is missing for the region. Balmorel regions
  take the load of their Canonical Region Name, so all `DE4-*` take `DE`'s
  and `FIN` takes `FI`'s.
- Hours outside 0.2-3 times the profile's median, or missing, are
  interpolated. A region with more than 2% such hours takes its current
  profile from the input data instead, with the same cleaning, and if that
  fails too it keeps its current profile unchanged, with a warning. Regions
  without ENTSO-E load (the UK, and CY, LU, MT, TR in 2023) also take the
  input data. The file's header lists the source and number of
  interpolated hours of every region; check it.
- The command appends this line to the scenario's `data/DE_VAR_T.inc` if it
  isn't there, creating the file to include base's first if needed:

  ```gams
  $if EXIST '../data/DE_VAR_T_ENTSOE.inc' $INCLUDE '../data/DE_VAR_T_ENTSOE.inc';
  ```

  Writing new weather-year data (`run_weatheryear`, `write_scenario_data`)
  overwrites `DE_VAR_T.inc`, so run `demand-profile` again afterwards.

Caveats:

- ENTSO-E actual load is total load. It includes demand that Balmorel
  models endogenously: heat pumps, electric boilers, EV charging and
  electrolysis. Using its shape for the exogenous users counts part of
  their temperature and time-of-day variation twice. For a backcast this is
  a much smaller error than the corrupt profiles. A cleaner option is to
  subtract an estimate of those loads first.
- The demand profile is a Calibration Input: the load-shape correlation in
  [Backcast validation](../postprocessing/validating_backcast.md) is no
  longer independent evidence. Only the annual level and the endogenous
  demand remain to be validated.

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
- **Output**: raw ENTSO-E data in `<entsoe-data-path>`; XKFX, GKRATE, fuel price,
  CO2 tax and demand profile overrides written to `<scenario-path>/data/`; validation
  data cached in `<scenario-path>/backcastoutput/`.

## Data flow

1. Raw ENTSO-E data fetched via `pybalmorel.entsoe` (`download`) and saved
   as CSV.
2. The XKFX override is computed from the ENTSO-E flows
   (`transmission-flow-limit`), and the GKRATE override from the ENTSO-E
   nuclear output (`nuclear-availability`), and the DE_VAR_T override from
   the ENTSO-E load (`demand-profile`).
3. Historical prices are mapped onto the UTC Backcast Calendar and written
   (`fuelprices`, `co2-tax`).

The Backcast is then run in Balmorel and
[validated](../postprocessing/validating_backcast.md).

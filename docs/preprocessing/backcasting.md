# Backcasting: Validating Balmorel Against ENTSO-E

`pybalmorel.backcasting` compares simulated Balmorel behaviour for a
historical year against ENTSO-E observations, and derives the `XKFX`
(exogenous transmission capacity) backcast override from ENTSO-E's Observed
Max Flow (see `CONTEXT.md` and `docs/adr/0001`, `0002`, `0003`). It depends on
[`pybalmorel.entsoe`](entsoe.md) for raw data access and on `pybalmorel.MainResults`
for Balmorel results — never the other way round.

## CLI

```bash
# Fetch and format data for validation
python -m pybalmorel.backcasting format \
    <balmorel-scenario> \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year>

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
```

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
  border and writes it to `XKFX_ENTSOE.inc` (see `docs/adr/0001`, `0002`) — a
  non-destructive override file, never a rewrite of the base `XKFX.inc`.

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
   (`transmission-max-flow`).
5. Statistics calculated and visualisations generated.

## Limitations

- No data available for Cyprus (CY) or Turkey (TR) in ENTSO-E.
- Some bidding zones may lack complete data coverage.
- Cross-border flow data requires explicit region pairs.

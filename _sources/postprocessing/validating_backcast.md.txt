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
    [--overwrite]

# Generate statistics
python -m pybalmorel.backcasting statistics <balmorel-scenario-path>

# Generate plots
python -m pybalmorel.backcasting generation <balmorel-scenario-path>
python -m pybalmorel.backcasting prices <balmorel-scenario-path>
python -m pybalmorel.backcasting flows <balmorel-scenario-path>
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

- **Technology Categorisation**: `balmorel_to_category`/`entsoe_to_category`
  standardise generation technologies between Balmorel and ENTSO-E so they can
  be compared.
- **Spatial Aggregation**: sums sub-regions to their canonical zone
  (`DE4-*` → `DE`, `IT-*` → `IT`) before comparing.
- **Label matching**: Balmorel results are mapped onto the
  [Backcast Calendar](../preprocessing/preparing_backcast.md#key-features)
  by their (Season, Term) labels, never by position.
- **Flow validation**: compares Balmorel's hourly flows with ENTSO-E's per
  directed border, using the same ENTSO-E flow files as the transmission
  overrides (see [Flow validation](#flow-validation)).

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

## Output

`format` caches the Balmorel results and writes the joined comparison data
to `<scenario-path>/backcastoutput/` (`loads.csv`, `prices.csv`,
`generation.csv`, `flows.csv`). The plot commands save their figures to the
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

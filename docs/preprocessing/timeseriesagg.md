# Time Series Aggregation

:::{warning} 
This functionality is currently under development and being tested! 
Do not trust it blindly.
:::

The time series aggregation function uses dependencies that are not automatically installed with pybalmorel: riprepy (a Python wrapper for [ripgrep](https://github.com/BurntSushi/ripgrep)) and the time series aggregation package [tsam](https://tsam.readthedocs.io/en/latest/). Install them into your virtual environment with pip:

```bash
pip install tsam
pip install riprepy
```

## Overview

`Balmorel.temporal_aggregation` aggregates the time series input data of a Balmorel scenario from a full hourly resolution down to a user-defined number of representative seasons (periods) and terms (hours per period). It uses [tsam](https://tsam.readthedocs.io/en/latest/) under the hood to cluster the time series data, and then writes new `.inc` files for the aggregated scenario into a new scenario folder named `{scenario}_S{seasons}T{terms}`.

The method works in three steps:

1. **Collect and standardise** — loads all `.inc` files (manually or
   automatically) and extracts every time-indexed GAMS symbol (those with
`SSS`/`TTT` domains). Each symbol's data is placed on a common `(SSS, TTT)`
index and joined into a single DataFrame.
2. **Cluster** — runs tsam to find representative periods for the collected data.
3. **Save** — writes new `.inc` files containing the aggregated data, plus updated `S.inc` and `T.inc` set definitions, 
into a new scenario folder.

:::{warning} 
- Any .inc files that define both SSS/TTT-related symbols AND symbols without any SSS/TTT 
dependency will result in new .inc files that does NOT include the non-SSS/TTT dependant
symbols. Hence, remember to copy paste those parts into the newly
generated .inc files after aggregation, or re-organise before.
- If you have several .inc files in the scenario/data folder that define the same symbol 
through some option in balopt.opt (like EV_profile, selecting only one of the profiles), 
only one of these files will contain data after aggregation. Remember to rename the one 
containing the data to match the selection in balopt.opt or just delete the .inc files that 
are not selected before aggregation.
:::

## Basic Usage

```python
from pybalmorel import Balmorel

model = Balmorel('path/to/Balmorel')

model.temporal_aggregation(
    scenario='base',
    seasons=8,
    terms=24,
)
```

This produces a new scenario folder `path/to/Balmorel/base_S8T24/` containing the aggregated `.inc` files
with 8 seasons and 24 terms.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scenario` | `str` | — | The scenario folder to aggregate. |
| `seasons` | `int` | — | Number of representative seasons (periods) to cluster to. |
| `terms` | `int` | — | Number of hours per period. |
| `method` | `str` | `'contiguous'` | Clustering method. See [Clustering methods](#clustering-methods). |
| `representation` | `str` | `'distribution_minmax'` | How cluster centres are represented. See [Representation options](#representation-options). |
| `symbols_to_aggregate` | `dict \| str` | `'auto'` | `'auto'` to detect time series symbols automatically, or a dict for manual selection. See [Manual symbol selection](#manual-symbol-selection). |
| `incfile_symbol_relation` | `dict` | `{}` | Required when `symbols_to_aggregate` is a dict. Maps each symbol to the `.inc` file(s) it should be written to. |
| `overwrite` | `bool` | `False` | Re-collect and re-standardise input data even if cached `.pkl` files already exist. |

## Clustering Methods

The `method` parameter is passed directly to tsam. Available options:

| Method | Description |
|---|---|
| `'contiguous'` | *(default)* Clusters consecutive time steps together, preserving temporal order. |
| `'averaging'` | Simple averaging within clusters. |
| `'kmeans'` | k-means clustering. |
| `'kmedoids'` | k-medoids clustering. |
| `'kmaxoids'` | k-maxoids clustering. |
| `'hierarchical'` | Agglomerative hierarchical clustering. |

## Representation Options

The `representation` parameter controls how the representative value for each cluster is chosen:

| Option | Description |
|---|---|
| `'distribution_minmax'` | *(default)* Preserves the distribution of each time series and matches the min/max values. |
| `'mean'` | Uses the mean of the cluster. |
| `'medoid'` | Uses the medoid (the actual time step closest to the centroid). |
| `'maxoid'` | Uses the time step with the highest overall load. |
| `'distribution'` | Preserves the distribution of each time series. |
| `'minmax_mean'` | Matches the min and max values and uses the mean otherwise. |

## Automatic Symbol Detection

By default (`symbols_to_aggregate='auto'`), the method scans all loaded `.inc` files and GAMS symbols to find every parameter that has `SSS` or `TTT` in its domain. It categorises them into three groups:

- `'SSS,TTT'` — symbols indexed over both seasons and terms (e.g. `DE_VAR_T`, `WND_VAR_T`).
- `'SSS'` — symbols indexed over seasons only.
- `'TTT'` — symbols indexed over terms only.

Certain meta-data symbols are excluded automatically (e.g. `WEIGHT_S`, `CHRONOHOUR`, `S`, `T`). Symbols with all-constant time series are also skipped.

Intermediate results are cached as `.pkl` files in the scenario folder (`std_ts_data.pkl`, `symbols_to_agg.pkl`, `incfile_symbol_relation.pkl`). On subsequent runs, these are loaded directly unless `overwrite=True` is passed, to reduce computational time when doing several clusterings of the same data.

## Manual Symbol Selection

If you want precise control over which symbols are aggregated, pass a dict to `symbols_to_aggregate` and a companion dict to `incfile_symbol_relation`:

```python
model.temporal_aggregation(
    scenario='base',
    seasons=8,
    terms=24,
    symbols_to_aggregate={
        'SSS,TTT': ['DE_VAR_T', 'WND_VAR_T'],
        'SSS':     [],
        'TTT':     [],
    },
    incfile_symbol_relation={
        'DE_VAR_T':  ['base/data/DE_VAR_T.inc',
                      'base/data/INDIVUSERS_DE_VAR_T.inc'
                      'base/data/TRANSPORT_DE_VAR_T.inc'],
        'WND_VAR_T': ['base/data/WND_VAR_T.inc'],
    },
)
```

Each key in `incfile_symbol_relation` is a symbol name, and the value is a list of `.inc` file paths. The first path 
will receive the aggregated data; the remaining files are written as empty stubs (since all appending to the symbol 
from addons will be contained in the first file, and the others therefore need
to be empty to avoid reading of its '../../base/data' counterpart).

## Output

After a successful run, a new scenario folder is created:

```
Balmorel/
└── base_S8T24/
    └── data/
        ├── S.inc                  ← updated season set (S01 … S08)
        ├── T.inc                  ← updated term set (T001 … T024)
        ├── DE_VAR_T.inc           ← aggregated demand profiles
        ├── WND_VAR_T.inc          ← aggregated wind profiles
        └── ...
    └── temporal_aggregation.md    ← log of aggregation settings
```

The `temporal_aggregation.md` log records the timestamp, method, representation, and the aggregated resolution.

## Important Notes

- If an `.inc` file contains **both** time-dependent symbols and symbols without `S`/`T` sets, the newly generated file will **only** contain the time-dependent data. You must manually copy the non-time-dependent parts back into the new file or re-organise into several files before aggregation.
- The `overwrite=False` default means repeated calls are fast — the standardisation step is skipped if cached data is found. Pass `overwrite=True` if your input data has changed since the last run.
- GAMS-dependent input loading (via `load_incfiles`) is performed internally; make sure a GAMS installation is available and `gams_system_directory` is set on the `Balmorel` object if GAMS cannot be found automatically.


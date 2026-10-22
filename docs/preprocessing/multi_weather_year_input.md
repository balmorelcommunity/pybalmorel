# Multi-Weather-Year Input Generation

The `weatheryear` module converts outputs from external models (CorRES, demand, hydro, and COP models) into Balmorel-compatible `.inc` files for a chosen historical weather year. The year must be covered by every input time series. This allows you to run Balmorel with multiple weather-year scenarios to capture annual variability of renewable energy sources and demand.

## Installation

`pyyaml`, `xlsxwriter` and `openpyxl` are required by this module but are **not installed by default** with `pybalmorel`. Install them via the `weatheryear` extra:

```bash
pip install pybalmorel[weatheryear]
```

## Overview

The module produces Balmorel `.inc` files for the following data types:

| Data type | Method | Key outputs |
|---|---|---|
| VRE time series (wind & solar) | `get_vre_data()` | Excel review files + `*_VAR_T_*.inc` files |
| VRE-related investment data | `get_vre_related_files()` | `AAA`, `GGG`, `GDATA`, `GKFX`, `ANNUITYCG`, `INVDATA` `.inc` files |
| Electricity & heat demand | `get_demand_data()` | `DE_VAR_T_*.inc`, `DH_VAR_T_*.inc` |
| Hydro inflow | `get_hydro_data()` | `HYDRO_ROR_VAR_T_*.inc`, `HYDRO_RES_VAR_T_*.inc`, `FLHO_*.inc` |
| Heat-pump COP factors | `get_cop_data()` | `SEASONALCOP_COP_VAR_T_*.inc` |

Each method generates both Day-Ahead and CapDev time series.

## Configuration File

All methods are driven by a single YAML configuration file. Below is an annotated template:

```yaml
# Optional convenience key: weather-year input root folder.
# If provided, defaults are inferred for:
# corres_results, VRE_tech_costs, Existing_wind_cap, Existing_solar_cap,
# VRE_potentials, demand_model_results, hydro_model_results, cop_model_results.
weatheryear_inputs_folder: path/to/weatheryear_inputs

# Backward-compatible alternative key:
# multiweather_other_inputs_folder: path/to/weatheryear_inputs/multiweather_other_inputs

# Technology-run folders to process (required). This is the only switch for
# including or excluding a technology.
tech_to_keep:
  - Future_Onshore
  - Future_Offshore_bottom_fixed
  - PV_Rooftop

# Wind turbine models (future installations only) 
# Onshore Future available turbines: SP199-HH100, SP199-HH150,SP199-HH200, SP277-HH100, SP277-HH150,SP277-HH200 , SP335-HH100, SP335-HH150,SP335-HH200
# Offshore Future available turbines:  SP316-HH155 , SP370-HH155
turbine_to_keep:
  - SP335-HH100
  - SP277-HH150
  - SP199-HH150

# Resource grades to include per technology (RGA/B/C → RG1/2/3 in Balmorel)
RGs_to_keep:
  Future_Onshore: [RGA, RGB, RGC]
  Future_Offshore_bottom_fixed: [RGB]
  PV_Rooftop: [RGA, RGB, RGC]
  # Every technology in tech_to_keep needs an entry here, or loading fails.

# Geographic regions to include
Regions_to_keep:
  onshore: [DK1, DK2, FIN, DE4-E, DE4-N, ...]
  offshore: [DK1_OFF, DK2_OFF, FIN_OFF, DE4-N_OFF, ...]

# --- VRE investment 
ANNUITYCG_calculation:
  DEBT_SHARE: 0
  INTEREST_RATE: 0.04
  DISCOUNTRATE: 0.04

# --- Demand data ---
spaceHeat_to_hotWater_ratio: 0.7   # fraction of heat demand attributed to space heating
ann_corr_fac_ref_year: 2012        # reference year for annual correction factors

# --- Hydro full-load hours (optional) ---
# relative (default): a factor on Balmorel's base FLH, the year's inflow over its long-term mean.
# absolute: CorRES inflow energy / the GKFX that receives it, read from a Balmorel scenario.
hydro_flh:
  mode: absolute
  balmorel_path: ../..      # Balmorel root, relative to this config file
  scenario: backcast        # whose GKFX receives the inflow
  capacity_year: 2023       # the Y of GKFX

# --- CapDev time-series aggregation ---
# Representative seasons (S) and hours (T) used for the aggregated resolution
CapDev_timesteps_to_keep:
  S: [S02, S08, S15, S21, S28, S34, S41, S47]
  T: [T073, T076, T079, T082, T085, T088, T091, T094,
      T097, T100, T103, T106, T109, T112, T115, T118,
      T121, T124, T127, T130, T133, T136, T139, T142]
```

When `weatheryear_inputs_folder` is set, the module assumes this structure:

```text
weatheryear_inputs/
├── Corres_runs/
├── demand_data/
├── hydro_data/
├── cop_data/
└── multiweather_other_inputs/
```

Defaults are resolved as follows:

- `corres_results` from `Corres_runs` (or `CorRES_runs` if present)
- `VRE_tech_costs`, `VRE_potentials`, `Existing_wind_cap`, `Existing_solar_cap` from `multiweather_other_inputs`
- `demand_model_results` from `demand_data` (falls back to `multiweather_other_inputs/Demand_model_Bal_ready_csv*`)
- `hydro_model_results` from `hydro_data`
- `cop_model_results` from `cop_data`

## Basic Usage

```python
from pybalmorel import WEATHERYEAR

# Instantiate for a specific weather year
mly = WEATHERYEAR(
    year=2013,
    config_fn="config.yml",
    output_folder="results/",
)

# 1. Export VRE time series from CorRES to Excel and .inc files
mly.get_vre_data()

# 2. Generate VRE-related investment .inc files
mly.get_vre_related_files()

# 3. Generate electricity and heat demand .inc files
mly.get_demand_data()

# 4. Generate hydro inflow .inc files
mly.get_hydro_data()

# 5. Generate heat-pump COP .inc files
mly.get_cop_data()
```

After running, the output folder will have the structure:

```
results/
└── 2013/
    ├── Future_Onshore/               ← Excel stats files for review
    ├── Future_Offshore_bottom_fixed/
    ├── Existing_ERA5_GWA2/
    ├── PV_Rooftop/
    ├── ...
    └── to_balmorel/                  ← .inc files ready for Balmorel
        ├── AAA_renewable.inc         ← investment data (get_vre_related_files)
        ├── GDATA_renewable.inc
        ├── ...
        ├── HourlyDispatch/           ← Day-Ahead (full hourly) time series
        │   ├── raw/
        │   └── scaled_long_term/
        └── CapDev/                   ← time series at the CapDev timesteps
            ├── raw/                  ← the actual weather of the year
            ├── scaled_long_term/
            └── scaled_full_year/
```

Each time series folder holds the wind, solar, demand, hydro and COP files, e.g. `WND_VAR_T.inc`, `SOLE_VAR_T.inc`, `WNDFLH.inc`, `DE_VAR_T_RESE.inc` and `WTRRRVAR_T_WY.inc`.

## Absolute Hydro FLH

By default the hydro full-load-hour files (`WTRRSFLH_WY.inc`, `WTRRRFLH_WY.inc`) scale Balmorel's base FLH by the year's inflow over its long-term mean, so the level comes from Balmorel's base data. With `hydro_flh: mode: absolute`, the level comes from CorRES instead (see [ADR 0011](../adr/0011-absolute-hydro-flh-with-observed-fallback.md)):

1. The reservoir and run-of-river `GKFX` of `capacity_year` per area is read from `scenario` with `Balmorel.load_incfiles`. The scenario's `<scenario>_input_data.gdx` is reused if it exists, and it must hold the `IGHYRS` and `IGHYRR` sets, which pybalmorel's `Balmorelbb4_ReadData.inc` assigns since this mode was added. If you get an error that they are empty, delete `<scenario>/model/<scenario>_input_data.gdx` and the copied `<scenario>/model/Balmorelbb4_ReadData.inc`, and run again (this can take more than 20 minutes).
2. Each year's inflow energy is the sum of the hourly `res_inflow.csv` and `ror_inflow.csv` values. Run-of-river inflow above an area's run-of-river capacity in an hour would be spilled by Balmorel, so it moves to the same area's reservoir if it has one.
3. The FLH is the energy divided by the capacity: the year's value in `raw` and `scaled_full_year`, the long-term mean in the `scaled_long_term` folders. Areas with inflow but no capacity get no line, which is reported.
4. **Plausibility check per country.** A country fails if a reservoir series equals the area's run-of-river series, if a series equals another area's series, if its long-term CorRES energy is more than ±20% from the bundled observed long-term Natural-Inflow Hydro (`pybalmorel.weatheryear.hydro_reference`, Eurostat 2013–2022 and the Swiss Federal Office of Energy), or if CorRES covers its hydro capacity only partly (an area and hydro type with `GKFX` but no column) or not at all. A failing country gets the **Hydro Inflow Fallback**: the observed long-term energy, times the year's relative factor, split over its areas and hydro types by Balmorel's base FLH × `GKFX`. An area and type without a CorRES column takes its country's factor, and a country without any column gets a factor of 1, so no variation between years. A missing base FLH counts as 0, and a failing country without a reference value keeps its base FLH times the factor. The base FLH is read from the `base` scenario.

The run stops if any FLH is above 8,760 h or if every country fails the check, since both point to wrong units.

## Writing a Balmorel Scenario

Some of the WEATHERYEAR output can't be dropped straight into a Balmorel scenario: Balmorel only reads a scenario's own `data/<NAME>.inc` when the filename matches exactly, and some output is split across several files or holds scaling factors rather than values. `write_scenario_data` turns one year's CapDev output into the files a scenario's `data/` folder needs:

```python
from pybalmorel.weatheryear.scenario_data import write_scenario_data

written = write_scenario_data(
    capdev_dir="results/2013/to_balmorel/CapDev/raw",
    to_balmorel_dir="results/2013/to_balmorel",
    dest_dir="path/to/Balmorel/WY2013/data",
)
print(f"Wrote {len(written)} files")
```

What it does:

- **Wind and solar** profiles and full-load hours keep their names. Wind gets a fallback profile for existing areas CorRES has no profile for.
- **Hydro** files lose the `_WY` suffix. The full-load-hour files are scaling factors, so the base values are loaded first and multiplied. Absolute Hydro FLH files set the value and are left as they are.
- **Demand** is split by user in the WEATHERYEAR output, but Balmorel reads one `DE_VAR_T.inc` and one `DH_VAR_T.inc`. The files are concatenated on top of the base defaults, since the weather year only sets its own users' values.
- **Individual-user heat** is loaded inside `DH.inc` and `DH_VAR_T.inc`, and empty `INDIVUSERS_DH*.inc` overrides are written so it isn't applied twice.
- **Investment files** at the top of `to_balmorel/` are copied, except `GKFX_renewable.inc` (the existing fleet comes from base) and `SUBTECHGROUPKPOT.inc`.
- **Heat-pump COP** files are not written; models that use them need their own wrapper.

Optional arguments:

- `base_data_dir` — GAMS path, relative to the scenario's `model/` folder, of the base data the weather year is applied on top of. Defaults to `'../../base/data'`.
- `drop_areas` — areas your model doesn't have, removed wherever they appear (matched as substrings), e.g. `drop_areas=('AL_', 'IT_OFF1')`.

Existing files in `dest_dir` with the same names are overwritten.

## Processing Multiple Years

Loop over years to build a full multi-weather-year dataset:

```python
from pybalmorel import WEATHERYEAR

for year in range(1980, 2026):  # the years your inputs cover
    mly = WEATHERYEAR(year=year, config_fn="config.yml", output_folder="results/")
    mly.get_vre_data()
    mly.get_vre_related_files()
    mly.get_demand_data()
    mly.get_hydro_data()
    mly.get_cop_data()
```

## API Reference

See the auto-generated API docs under **Reference → pybalmorel.weatheryear** for the full list of classes and functions exposed by this module.

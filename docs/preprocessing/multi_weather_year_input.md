# Multi-Weather-Year Input Generation

The `weatheryear` module converts outputs from external models (CorRES, demand, hydro, and COP models) into Balmorel-compatible `.inc` files for a chosen historical weather year (1980–2021). This allows you to run Balmorel with multiple weather-year scenarios to capture annual variability of renewable energy sources and demand.

## Installation

`pyyaml` and `xlsxwriter` are required by this module but are **not installed by default** with `pybalmorel`. Install them via the `weatheryear` extra:

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
# --- VRE data ---
corres_results:
  wind:
    - path/to/Future_Onshore
    - path/to/Future_Offshore_bottom_fixed
    - path/to/Existing_ERA5_GWA2
  solar:
    - path/to/PV_Rooftop
    - path/to/PV_Utility_scale_no_tracking
    - path/to/PV_Utility_scale_tracking

# VRE technology subsets to process
tech_to_keep:
  - Future_Onshore
  - Future_Offshore_bottom_fixed
  - Existing_ERA5_GWA2
  - PV_Rooftop
  - PV_Utility_scale_no_tracking
  - PV_Utility_scale_tracking

# Wind turbine models (future installations only)
turbine_to_keep:
  - SP335-HH100
  - SP277-HH150
  - SP199-HH150

# Resource grades to include per technology (RGA/B/C → RG1/2/3 in Balmorel)
RGs_to_keep:
  Future_Onshore: [RGA, RGB, RGC]
  Future_Offshore_bottom_fixed: [RGB]
  PV_Rooftop: [RGA, RGB, RGC]

# Geographic regions to include
Regions_to_keep:
  onshore: [DK1, DK2, FIN, DE4-E, DE4-N, ...]
  offshore: [DK1_OFF, DK2_OFF, FIN_OFF, DE4-N_OFF, ...]

# --- VRE investment / cost data ---
VRE_tech_costs: path/to/VRE_Tech_Costs_EUR2015.xlsx
VRE_potentials: path/to/VRE_Potentials.xlsx
Existing_wind_cap: path/to/Existing_wind_capacities.xlsx
Existing_solar_cap: path/to/Existing_solar_capacities.xlsx

ANNUITYCG_calculation:
  DEBT_SHARE: 0
  INTEREST_RATE: 0.04
  DISCOUNTRATE: 0.04

# --- Demand data ---
demand_model_results: path/to/demand_model_csv_folder
spaceHeat_to_hotWater_ratio: 0.7   # fraction of heat demand attributed to space heating
ann_corr_fac_ref_year: 2012        # reference year for annual correction factors

# --- Hydro data ---
hydro_model_results: path/to/hydro_model_csv_folder

# --- COP data ---
cop_model_results: path/to/cop_model_csv_folder

# --- CapDev time-series aggregation ---
# Representative seasons (S) and hours (T) used for the aggregated resolution
CapDev_timesteps_to_keep:
  S: [S02, S08, S15, S21, S28, S34, S41, S47]
  T: [T073, T076, T079, T082, T085, T088, T091, T094,
      T097, T100, T103, T106, T109, T112, T115, T118,
      T121, T124, T127, T130, T133, T136, T139, T142]
```

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
        ├── WND_VAR_T_Future_Onshore_2013.inc
        ├── SOL_VAR_T_PV_Rooftop_2013.inc
        ├── AAA_renewable.inc
        ├── GDATA_renewable.inc
        ├── DE_VAR_T_DK1_2013.inc
        ├── DH_VAR_T_DK1_2013.inc
        ├── HYDRO_ROR_VAR_T_2013.inc
        ├── SEASONALCOP_COP_VAR_T_2013.inc
        └── ...
```

## Processing Multiple Years

Loop over years to build a full multi-weather-year dataset:

```python
from pybalmorel import WEATHERYEAR

for year in range(1980, 2022):
    mly = WEATHERYEAR(year=year, config_fn="config.yml", output_folder="results/")
    mly.get_vre_data()
    mly.get_vre_related_files()
    mly.get_demand_data()
    mly.get_hydro_data()
    mly.get_cop_data()
```

## API Reference

See the auto-generated API docs under **Reference → pybalmorel.weatheryear** for the full list of classes and functions exposed by this module.

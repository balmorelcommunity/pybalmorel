# Installation

Install into your virtual python environment with [conda](https://www.anaconda.com/) or [pixi](https://pixi.prefix.dev/latest/).
For more information on how to manage and install virtual environments check out [this resource](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html) if you are a conda user.

## Quick install

```bash
pip install pybalmorel
```

## Requirements

pybalmorel has the following requirements - here illustrated in an environment.yml file that can be used to create the necessary conda environment (note that it will also install pybalmorel itself, including the dependencies of all optional features listed below):

```yaml
name: pybalmorel
channels:
  - conda-forge
dependencies:
  - python >= 3.10
  - numpy>=2.1.2
  - pandas>=2.1.4
  - matplotlib>=3.9.0
  - geopandas>=1.0.1
  - cartopy>=0.24.1
  - ipywidgets>=8.1.3
  - ipykernel>=6.29.5
  - requests
  - xlsxwriter
  - pyyaml
  - openpyxl>=3.1.5
  - entsoe-py>=0.8.0,<0.9
  - python-decouple>=3.8,<4
  - click>=8
  - pip
  - pip:
    - pybalmorel==1.3.5
```

## GAMS

Loading `.gdx` files, reading .inc files and running Balmorel requires a [GAMS](https://www.gams.com/) installation with a valid licence. The GAMS Python API (`gamsapi`) is installed with pybalmorel, but it needs to find your GAMS installation. If it does not find it automatically, pass the GAMS system directory explicitly, e.g. `Balmorel('path/to/Balmorel', gams_system_directory='/opt/gams/53')` or `MainResults(..., system_directory='/opt/gams/53')`.

## Optional features

Some features need additional packages that are not installed by default:

| Feature | Install |
| --- | --- |
| [Multi-weather-year input](../preprocessing/multi_weather_year_input.md) | `pip install pybalmorel[weatheryear]` |
| [ENTSO-E data fetching](../preprocessing/entsoe.md), [backcasting](../preprocessing/preparing_backcast.md) and the [average fuel price CLI](../preprocessing/economics.md#average-fuel-prices-cli) | `pip install pybalmorel[entso-e]` |
| [Time series aggregation](../preprocessing/timeseriesagg.md) | `pip install tsam ripgrepy` |
| [Geography GUI](../preprocessing/overview.md#defining-geography) | `pip install eel` |
| Reading the [technology catalogues](../preprocessing/overview.md#downloading-technology-catalogues) | `pip install openpyxl` (included in the `weatheryear` extra) |

Several extras can be combined, e.g. `pip install "pybalmorel[weatheryear,entso-e]"` (the quotes are needed in some shells, like zsh).

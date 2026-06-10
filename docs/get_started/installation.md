# Installation
Install into your virtual python environment with [conda](https://www.anaconda.com/) or [pixi](https://pixi.prefix.dev/latest/).
For more information on how to manage and install virtual environments check out [this resource](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html) if you are a conda user.

## Requirements
pybalmorel has the following requirements - here illustrated in an environment.yml file that can be used to create the necessary conda environment (note that it will also install pybalmorel itself):
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
  - pip
  - pip:
    - pybalmorel==1.1.13
```

Note: If you want to use the [time series aggregation tools](../preprocessing/timeseriesagg.md), you will also need to pip install the python packages tsam and ripgrepy.

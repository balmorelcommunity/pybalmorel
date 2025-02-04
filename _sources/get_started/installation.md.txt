# Installation
Install into your virtual python environment with:

`pip install pybalmorel`

For more information on how to manage and install virtual environments check out [this resource](https://docs.python.org/3/library/venv.html), or if you are a conda user, [this resource](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html).

## Requirements
pybalmorel has the following requirements - here illustrated in a environment.yml file that can be used to create the necessary conda environment (note that it will also install pybalmorel itself):
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
  - ipywidgets>=8.1.3
  - ipykernel>=6.29.5
  - cartopy>=0.24.1
  - pip
  - pip:
    - pybalmorel==0.5.3
    - cartopy>=0.24.1
```


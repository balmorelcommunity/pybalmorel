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
  - python >= 3.9
  - pandas>=2.1.4 
  - matplotlib>=3.9.0 
  - geopandas>=1.0.1
  - ipywidgets>=8.1.3
  - pip
  - pip:
    - gamsapi[transfer]>=45.7.0 
    - eel>=0.17.0
    - pybalmorel==0.3.12
```

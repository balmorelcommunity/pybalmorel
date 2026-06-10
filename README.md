# pybalmorel
Convenient python framework for pre-, post-processing or executing the GAMS framework Balmorel. Install into your virtual python environment with:

`pip install pybalmorel`

For more information on how to manage and install virtual environments check out [this resource](https://docs.python.org/3/library/venv.html), or if you are a conda user, [this resource](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html).

## Get Started

Check out the [documentation](https://balmorelcommunity.github.io/pybalmorel) for examples on how to use pybalmorel. The following notebooks can also be downloaded:
- [Pre-Processing](https://github.com/Mathias157/pybalmorel/blob/master/examples/PreProcessing.ipynb)
- [Execution](https://github.com/Mathias157/pybalmorel/blob/master/examples/Execution.ipynb)
- [Post-Processing](https://github.com/Mathias157/pybalmorel/blob/master/examples/PostProcessing.ipynb)

## Developer Notes

This package is distributed to [PyPI](https://pypi.org). See the [Developing pybalmorel](https://balmorelcommunity.github.io/pybalmorel/developing.html) section of the documentation for full details. The short version:

Install [pixi](https://pixi.prefix.dev/latest/#installation) and use one of the following environments:

| Command | Purpose |
|---|---|
| `pixi shell` | Develop pybalmorel and build documentation (editable install + all tools) |
| `pixi shell -e user` | Test pybalmorel as an end-user (PyPI install only) |

### Publishing a new version

1. Update the pybalmorel version in `pyproject.toml`, `docs/conf.py` and `docs/get_started/installation.md` (a find and replace in VS Code will do)
2. Build the distribution: `python -m build`
3. Upload to PyPI with your PyPI token: `python -m twine upload dist/pybalmorel-X.Y.Z.tar.gz`

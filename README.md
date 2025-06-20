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

This package is distributed to [PyPI](https://pypi.org), and the distribution of a new version requires the following steps:
1. Update the pybalmorel version in pyproject.toml, environment.yaml, docs/conf.py and docs/get_started/installation.md (a find and replace in VS code will do)
2. Make sure that you have the most recent `build` and `setuptools` packages in your virtual environment and build the new distribution with `python -m build`
3. Make a user at PyPI.org and obtain a PyPI token.
4. Make sure that you have the most recent `twine` and `packaging` packages in your virtual envrionment and upload the newly created package in the dist folder with `python -m twine upload dist/pybalmorel-X.Y.Z.tar.gz`
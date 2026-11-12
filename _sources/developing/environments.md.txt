# Environments

pybalmorel uses [pixi](https://pixi.prefix.dev/latest/#installation) to manage its development environments. All environments are defined in `pyproject.toml`.

## Available Environments

### `default` (dev)

The default environment is intended for developing pybalmorel and building its documentation. It includes:

- All runtime dependencies (`pandas`, `matplotlib`, `geopandas`, etc.)
- Testing tools (`pytest`)
- Publishing tools (`build`, `setuptools`, `twine`, `packaging`)
- Documentation tools (`sphinx`, `sphinx-rtd-theme`, `sphinx-autoapi`, `sphinx-copybutton`, `myst-parser`)
- pybalmorel itself, installed as an **editable** local package so that code changes are picked up immediately

Activate it with:

```bash
pixi shell
```

or, if you are in the user environment below and need to go back to development mode:

```bash
pixi shell -e default
```

### `user`

The `user` environment simulates a clean end-user installation. It installs only the latest released version of pybalmorel from [PyPI](https://pypi.org/project/pybalmorel/), with no extra packages. Use this to verify that the package works correctly as distributed.

Activate it with:

```bash
pixi shell -e user
```


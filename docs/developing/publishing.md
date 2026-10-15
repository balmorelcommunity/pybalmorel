# Publishing to PyPI

New versions of pybalmorel are distributed to [PyPI](https://pypi.org/project/pybalmorel/). The steps below assume you are in the `dev` environment (`pixi shell`).

## Steps

1. **Check that all tests pass**, including the GAMS-dependent ones that CI skips (see [testing](testing.md)):

   ```bash
   pixi run test
   ```

2. **Bump the version** in the following files:
   - `pyproject.toml`
   - `docs/conf.py`
   - `docs/get_started/installation.md`
   - `environment.yaml`

   Avoid a blind project-wide find & replace, as the old version number can also appear in unrelated dependency pins in `pyproject.toml`. The `release-update` pixi task does the replacement in these four files, but the old and new versions are written into the task itself, so edit it before running it.

3. **Build and upload**:

   ```bash
   pixi run publish
   ```

   This builds a source archive and a wheel into `dist/` and uploads them with twine. Use `pixi run publish-test` to upload to [TestPyPI](https://test.pypi.org/) first. You will need a [PyPI account](https://pypi.org/account/register/) and an [API token](https://pypi.org/help/#apitoken) configured in `~/.pypirc` or passed interactively.

   Note that `publish` uploads everything in `dist/`, so remove files from earlier builds first. To do the steps by hand:

   ```bash
   python -m build
   python -m twine upload dist/pybalmorel-X.Y.Z.tar.gz dist/pybalmorel-X.Y.Z-py3-none-any.whl
   ```

4. **Check the release** in the `user` environment, which installs the latest version from PyPI (see [environments](environments.md)).

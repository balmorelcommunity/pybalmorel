# Publishing to PyPI

New versions of pybalmorel are distributed to [PyPI](https://pypi.org/project/pybalmorel/). The steps below assume you are in the `dev` environment (`pixi shell`).

## Steps

1. **Bump the version** in the following files (a project-wide find & replace works well):
   - `pyproject.toml`
   - `docs/conf.py`
   - `docs/get_started/installation.md`

2. **Build the distribution**:

   ```bash
   python -m build
   ```

   This creates a source archive and a wheel in the `dist/` folder.

3. **Upload to PyPI** using your PyPI token:

   ```bash
   python -m twine upload dist/pybalmorel-X.Y.Z.tar.gz
   ```

   You will need a [PyPI account](https://pypi.org/account/register/) and an [API token](https://pypi.org/help/#apitoken) configured in `~/.pypirc` or passed interactively.

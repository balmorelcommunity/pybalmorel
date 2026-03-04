# AGENTS.md — pybalmorel

Guidance for agentic coding assistants working in this repository.

---

## Repository layout

```
pybalmorel/
├── src/pybalmorel/          ← package source (src layout)
│   ├── __init__.py          ← public API: IncFile, MainResults, Balmorel, GUI, TechData
│   ├── classes.py           ← the five main public classes
│   ├── formatting.py        ← colour dicts, GAMS symbol → column name mappings
│   ├── utils.py             ← symbol_to_df and DataFrame helpers
│   ├── GeneralHelperFunctions.py  ← internal helpers (not public API)
│   ├── plotting/            ← plot_bar_chart, plot_profile, plot_map
│   └── interactive/         ← ipywidgets GUI, Eel.js dashboard
├── tests/                   ← pytest test suite (flat, at repo root)
├── docs/                    ← Sphinx documentation source (MyST Markdown)
├── examples/                ← example .gdx files and minimal Balmorel model
└── pyproject.toml           ← build metadata + pixi workspace config
```

---

## Environment setup

This project uses [pixi](https://pixi.prefix.dev) to manage environments.

```bash
pixi install       # resolve and install the default (dev) environment
pixi shell         # activate it
```

Two environments are available:

| Command | Purpose |
|---|---|
| `pixi shell` | Develop pybalmorel — editable install + all tools |
| `pixi shell -e user` | End-user simulation — PyPI install only, no dev tools |

---

## GAMS path configuration

GAMS-dependent tests (`test_utils.py`, `test_postprocessing.py`) need to locate
the GAMS shared libraries at runtime. The mechanism works as follows:

1. The user sets `GAMS_SYSTEM_DIR` in a local `.env` file (gitignored):

   ```
   GAMS_SYSTEM_DIR=/opt/gams/53
   ```

2. `pyproject.toml` maps this into `GAMS_SYSTEM_DIR` via pixi's
   `[tool.pixi.feature.dev.activation.env]`:

   ```toml
   [tool.pixi.feature.dev.activation.env]
   GAMS_SYSTEM_DIR = "/opt/gams/53"
   ```

   Pixi expands `$GAMS_SYSTEM_DIR` at activation time, **after** reading `.env`
   but **before** conda dependency activation scripts run — so the value is not
   overwritten by conda.

3. Test files read `GAMS_SYSTEM_DIR` and pass it to GAMS as the system directory:

   ```python
   gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
   assert gams_system_directory is not None, (
       "GAMS system directory not found. "
       "Set GAMS_SYSTEM_DIR in your .env file to point at your GAMS installation, e.g.:\n"
       "  GAMS_SYSTEM_DIR=/opt/gams/53"
   )
   ```

**Important:** Do not set `GAMS_SYSTEM_DIR` directly in `.env` — pixi treats `.env`
values as the lowest-priority outside environment variables, and conda activation
scripts overwrite them. Always set `GAMS_SYSTEM_DIR` in `.env` and let
`activation.env` in `pyproject.toml` propagate it into `GAMS_SYSTEM_DIR`.

**Important:** Do not use quotes or inline comments around values in `.env` — pixi
does not strip them and the value will be corrupted.

---

## Build / test / lint commands

### Running tests

```bash
# Full suite (via pixi task)
pixi run test

# Full suite (raw, inside pixi shell)
pytest tests

# Single test file
pytest tests/test_preprocessing.py
pytest tests/test_postprocessing.py
pytest tests/test_utils.py
pytest tests/test_execution.py

# Single test function
pytest tests/test_preprocessing.py::test_IncFile
pytest tests/test_utils.py::test_symbol_to_df_mainresults
pytest tests/test_postprocessing.py::test_MainResults
```

**Important:** `test_utils.py` and `test_postprocessing.py` require a working GAMS
installation and are excluded from CI. The CI pipeline (`.github/workflows/tests.yml`)
only runs the GAMS-free tests via `tests/online_tests.sh`:

```bash
python -m pytest tests/test_preprocessing.py
python -m pytest tests/test_execution.py
```

When writing new tests, keep GAMS-dependent tests in separate files so CI can
skip them without configuration.

### Building documentation

```bash
pixi run docs          # build Sphinx docs then serve at http://127.0.0.1:8000
pixi run _docs-build   # build only
pixi run _docs-serve   # serve only (requires prior build)
```

### Building the package for release

```bash
python -m build
python -m twine upload dist/pybalmorel-X.Y.Z.tar.gz
```

### Linting / formatting

**No formatter or linter is configured** (no ruff, black, flake8, isort, or
pre-commit). Follow the style conventions below manually.

---

## Code style guidelines

### Imports

Group imports in this order, with a blank line only before local (relative) imports:

```python
# 1. stdlib
import os
import sys
from typing import Union

# 2. third-party (no blank line from stdlib)
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 3. local — always last, blank line before this group
from .utils import symbol_to_df
from .formatting import tech_colours
from ..plotting.plot_functions import plot_bar_chart
```

Use `import pandas as pd`, `import numpy as np`, `import matplotlib.pyplot as plt`
— these abbreviations are universal in the codebase. Never use star imports.

### Type annotations

Add type hints to all function signatures. Use the Python 3.10+ union syntax for
new code:

```python
# preferred (new code)
def get_result(self, symbol: str, cols: list[str] | None = None) -> pd.DataFrame:

# acceptable (existing style)
def get_result(self, symbol: str, cols: Union[str, list, None] = None) -> pd.DataFrame:
```

Do not annotate local variables. Return types should always be annotated.

### Docstrings

Use **Google style** with `Args:` and `Returns:` sections:

```python
def symbol_to_df(db: GamsDatabase, symbol: str, cols: list[str] | None = None) -> pd.DataFrame:
    """Convert a GAMS symbol to a pandas DataFrame.

    Args:
        db (GamsDatabase): The GAMS database to read from.
        symbol (str): Name of the GAMS symbol, e.g. 'PRO_YCRAGF'.
        cols (list[str] | None, optional): Override column names. Defaults to None.

    Returns:
        pd.DataFrame: The symbol contents as a DataFrame.
    """
```

Class-level docstrings go on the class itself (not `__init__`), and list
constructor arguments under `Args:`. New source files should begin with a module
docstring noting creation date and author.

### Naming conventions

| Entity | Convention | Examples |
|---|---|---|
| Classes | `PascalCase` | `MainResults`, `IncFile`, `Balmorel`, `TechData` |
| Functions / methods | `snake_case` | `get_result`, `symbol_to_df`, `body_prepare` |
| Variables / parameters | `snake_case` | `scenario_names`, `result_type`, `system_directory` |
| Module-level constants / dicts | `snake_case` | `tech_colours`, `balmorel_symbol_columns` |
| GAMS symbol names (strings) | `ALL_CAPS` | `'PRO_YCRAGF'`, `'EL_PRICE_YCRST'` |

Avoid single-letter variables outside of short loop indices. Avoid the legacy
`fProd` / `fFlI` abbreviation style in new code.

### Section headers

Use the cell-separator comment style throughout new modules — it keeps files
navigable in VSCode/Spyder interactive mode and matches the existing codebase:

```python
#%% ------------------------------- ###
###        1. Data Loading          ###
### ------------------------------- ###
```

### Error handling

- Use specific `except` clauses — never bare `except:`.
- Raise `Exception` with a descriptive f-string message. No custom exception
  classes are defined; keep this consistent unless a meaningful hierarchy is needed.
- Use `print()` for user-facing warnings (consistent with the rest of the package —
  no `logging` module).

```python
# good
try:
    db = ws.add_database_from_gdx(path)
except gams.control.workspace.GamsException as e:
    raise Exception(f"Could not load GDX file at '{path}': {e}")

# avoid
try:
    ...
except:
    pass
```

### Classes

- Use plain classes with `__init__` for domain objects (`MainResults`, `Balmorel`,
  `IncFile`). Use `@dataclass` only for simple data holders (`TechData`).
- Do not add `__slots__`, `__repr__`, or `__eq__` unless there is a clear need.
- Methods that delegate to standalone functions (e.g. plotting) should be thin
  wrappers that pass `self`'s data and forward `**kwargs`:

```python
def plot_profile(self, **kwargs) -> tuple[Figure, Axes]:
    return plot_profile(self._df, **kwargs)
```

### Plotting functions

Plotting functions live in `src/pybalmorel/plotting/` and should always return
`(Figure, Axes)` or `(Figure, np.ndarray[Axes])`. Expose new plot types via a
delegating method on `MainResults`.

---

## Public API

The package's public interface is declared in `src/pybalmorel/__init__.py`:

```python
from . import formatting, utils
from .classes import IncFile, MainResults, Balmorel, GUI, TechData
```

Only add to this list intentionally. Internal helpers (e.g. everything in
`GeneralHelperFunctions.py`) are not part of the public API and should not be
imported in user-facing documentation examples.

---

## Tests

- Tests live in `tests/` at the repo root, not inside the package.
- Run tests from the repo root — test files use relative paths like
  `examples/files/MainResults_Example1.gdx` and `tests/output/`.
- There is no `conftest.py`. Add shared fixtures there if needed rather than
  duplicating setup code.
- Do not use `@pytest.mark.parametrize` sparingly — it is fine to use it for new
  tests.
- Separate GAMS-dependent tests (require a GAMS licence) from GAMS-free tests by
  filename so CI can skip the former.

---

## CI

`.github/workflows/tests.yml` runs on every push/PR using micromamba and
`environment.yaml`. It installs `pybalmorel` from PyPI (not an editable install)
and runs only `tests/online_tests.sh` (GAMS-free tests). Ensure
`test_preprocessing.py` and `test_execution.py` remain GAMS-free.

`.github/workflows/sphinx.yml` builds and deploys documentation to GitHub Pages.

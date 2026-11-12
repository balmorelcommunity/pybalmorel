# Testing

The test suite uses [pytest](https://docs.pytest.org/) and lives in the `tests/` directory. The `dev` environment (`pixi shell`) includes pytest so no extra installation is needed. Run tests from the repository root, as the tests use paths relative to it.

## With pixi (recommended)

```bash
pixi run test
```

This runs `pytest tests -s` from the repository root.

## Raw commands

Inside an active `pixi shell`:

```bash
pytest tests                                         # full suite
pytest tests/test_preprocessing.py                   # single file
pytest tests/test_preprocessing.py::test_IncFile     # single test
```

## Tests that need GAMS

Some tests need a GAMS installation with a valid licence, and `test_temporal_aggregation` also needs a local Balmorel model. They find these through two environment variables, which the `dev` environment sets in `pyproject.toml`:

```toml
[tool.pixi.feature.dev.activation.env]
GAMS_SYSTEM_DIR = "/opt/gams/53"
LOCAL_BALMOREL_DIR = "../Balmorel"
```

Change these to match your machine if needed. The GAMS-dependent tests are:

- `tests/test_utils.py`
- `tests/test_postprocessing.py`
- `tests/test_preprocessing.py::test_temporal_aggregation`

## Continuous integration

GitHub Actions (`.github/workflows/tests.yml`) runs on every push and pull request to `master`. It builds a conda environment from `environment.yaml`, installs the checked-out pybalmorel over it with `pip install -e .`, and runs `tests/online_tests.sh`.

As GAMS is not available on GitHub's runners, `online_tests.sh` only runs the GAMS-free tests. When adding tests:

- Put tests that need GAMS in separate files from GAMS-free ones, and only add GAMS-free files to `online_tests.sh`.
- Don't check for GAMS at module level in a file that CI runs, as that fails the whole file. Check inside the test that needs it.
- If a new feature needs extra packages, add them to `environment.yaml` too, or CI will fail with a `ModuleNotFoundError`.

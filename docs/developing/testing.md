# Testing

The test suite uses [pytest](https://docs.pytest.org/) and lives in the `tests/` directory. The `dev` environment (`pixi shell`) includes pytest so no extra installation is needed.

## With pixi (recommended)

```bash
pixi run test
```

This runs `pytest tests` from the repository root.

## Raw command

Inside an active `pixi shell`:

```bash
pytest tests
```

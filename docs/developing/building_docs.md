# Building Documentation Locally

The documentation is built with [Sphinx](https://www.sphinx-doc.org/) and hosted on GitHub Pages. The `dev` environment (`pixi shell`) includes all necessary tools so no extra installation is needed.

## With pixi (recommended)

The easiest way to build and preview the documentation is with the `docs` pixi task. It builds the documentation and immediately starts a local HTTP server so you can view the result in your browser:

```bash
pixi run docs
```

Then open `http://127.0.0.1:8000` in your browser. The task runs two steps in sequence:

1. `sphinx-build docs docs/_build/html` — compiles the documentation
2. `python -m http.server 8000` (from `docs/_build/html`) — serves it locally

Press `Ctrl+C` to stop the server.

If you want to run the two steps individually you can also use the underlying tasks directly:

```bash
pixi run _docs-build   # build only
pixi run _docs-serve   # serve only (requires a prior build)
```

## Raw commands

If you prefer running the commands directly without pixi tasks (e.g. inside an active `pixi shell`), the equivalent steps are:

```bash
sphinx-build docs docs/_build/html
cd docs/_build/html
python -m http.server 8000
```

Then open `http://127.0.0.1:8000` in your browser. Use a different port number if 8000 is already in use on your machine.

## Live Preview

For a live-reloading preview while editing, use `sphinx-autobuild` (install it separately if needed):

```bash
pip install sphinx-autobuild
sphinx-autobuild docs docs/_build/html
```

## Structure

The documentation source lives in the `docs/` directory:

| File / folder | Purpose |
|---|---|
| `conf.py` | Sphinx configuration |
| `index.md` | Landing page and top-level toctree |
| `get_started/` | Installation instructions |
| `preprocessing.md` | Pre-processing examples |
| `execution.md` | Execution examples |
| `postprocessing/` | Post-processing and map plotting |
| `developing/` | Developer documentation (this section) |
| `about.md` | About page |

Pages are written in [MyST Markdown](https://myst-parser.readthedocs.io/), which extends standard Markdown with Sphinx directives.

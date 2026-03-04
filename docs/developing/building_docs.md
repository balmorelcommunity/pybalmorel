# Building Documentation Locally

The documentation is built with [Sphinx](https://www.sphinx-doc.org/) and hosted on GitHub Pages. The `dev` environment (`pixi shell`) includes all necessary tools so no extra installation is needed.

## Build

From the repository root, run:

```bash
sphinx-build docs docs/_build/html
```

Then, change directory into docs/_build_html and open the documentation files by running `python -m http.server 8000` (or another port than 8000 if your computer already uses this). You can then view the documentation from your browser by opening `http://127.0.0.1:8000`.

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

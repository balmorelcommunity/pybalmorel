project = "pybalmorel"
copyright = "2024, Mathias Berg Rosendal, Théodore Le Nalinec, Polyneikis Kanellas"
author = "Mathias Berg Rosendal, Théodore Le Nalinec, Polyneikis Kanellas"
release = "1.4.2"


exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", ".testenv", ".testenv/**"]

conf_py_path = "/docs/"  # with leading and trailing slash

html_static_path = ["css"]

# General configurations
extensions = [
    "myst_parser",  # in order to use markdown
    "autoapi.extension",  # in order to use markdown
    "sphinx_copybutton",
    "sphinx.ext.napoleon",  # in order to read Google-style docstrings (Args:, Returns:)
]

# the package uses Google-style docstrings only
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# The classes pybalmorel re-exports are documented twice (pybalmorel.IncFile and
# pybalmorel.classes.IncFile), so a docstring type naming one has two targets. Both are the
# same class, so the 'more than one target' warnings are silenced
suppress_warnings = ["ref.python"]

# search this directory for Python files
autoapi_dirs = ["../src/pybalmorel"]

# ignore this file when generating API documentation
autoapi_ignore = ["*/conf.py"]

# generate anchors for headings down to ###, so links like page.md#heading work
myst_heading_anchors = 3

myst_enable_extensions = [
    "colon_fence",  # ::: can be used instead of ``` for better rendering
]

html_theme = "sphinx_rtd_theme"


def setup(app):
    app.add_css_file("css_options.css")  # may also be an URL

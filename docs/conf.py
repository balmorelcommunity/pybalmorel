project = "pybalmorel"
copyright = "2024, Mathias Berg Rosendal, Théodore Le Nalinec"
author = "Mathias Berg Rosendal, Théodore Le Nalinec"
release = "0.3.11"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", ".testenv", ".testenv/**"]

conf_py_path = "/docs/"  # with leading and trailing slash

html_static_path = ["css"]

# General configurations
extensions = [
    "myst_parser",  # in order to use markdown
    "autoapi.extension",  # in order to use markdown
    "sphinx_copybutton",
]

# search this directory for Python files
autoapi_dirs = ["../src/pybalmorel"]

# ignore this file when generating API documentation
autoapi_ignore = ["*/conf.py"]

myst_enable_extensions = [
    "colon_fence",  # ::: can be used instead of ``` for better rendering    
]

html_theme = "sphinx_rtd_theme"

def setup(app):
    app.add_css_file('css_options.css')  # may also be an URL
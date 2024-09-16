project = "pybalmorel"
copyright = "2024, Authors"
author = "Mathias Berg Rosendal, Théodore Le Nalinec"
release = "0.3.4"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

extensions = [
    "myst_parser",  # in order to use markdown
]

myst_enable_extensions = [
    "colon_fence",  # ::: can be used instead of ``` for better rendering
]

html_theme = "sphinx_rtd_theme"
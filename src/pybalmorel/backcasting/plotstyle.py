"""
Plot Style

Colours and themes of the backcast validation plots: the ENTSO-E and
Balmorel line colours, the technology category colours, and a light and a
dark theme. The dark theme uses Catppuccin Mocha colours on a transparent
background, so the plots sit on the background of a dark slide.

Created on 09.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from collections.abc import Generator
from contextlib import contextmanager
import matplotlib.pyplot as plt

# Line colours of ENTSO-E and Balmorel, checked for colour-blind separation
# and for at least 3:1 contrast on the dark theme's surface
ENTSOE_COLOUR = "#2a78d6"
BALMOREL_COLOUR = "#eb6834"

# Category of technologies missing from the mappings, with format --allow-unmapped
UNMAPPED_CATEGORY = "Unmapped"

# Colours of the technology categories
colors = {
    "Wind": "#4ECDC4",
    "Solar": "#FFE66D",
    "Hydro": "#0077B6",
    "Nuclear": "#FF6B6B",
    "Biomass & Bioenergy": "#6B8E23",
    "Fossil Gas": "#8B4513",
    "Fossil Solid": "#555555",
    "Fossil Liquid & Other Fossil": "#333333",
    "Waste & Heat Recovery": "#9B59B6",
    "Storage": "#F39C12",
    "Other renewable": "#A3D977",
    "Other": "#CCCCCC",
    "Backup": "#C0392B",
    UNMAPPED_CATEGORY: "#FF00FF",
}

# Category colours with less than 3:1 contrast on the dark surface (#1e1e2e),
# lightened to at least 3.2:1
DARK_COLOR_OVERRIDES = {
    "Fossil Liquid & Other Fossil": "#6e6e6e",
    "Fossil Solid": "#8a8a8a",
    "Fossil Gas": "#c8733a",
    "Backup": "#e0544a",
}

# Colour tokens: ink for titles, ink2 for labels and annotations, muted for
# tick labels, grid for grid lines, axis for the zero line and spines,
# surface for the background
THEMES = {
    # The colours price-duration had before the themes
    "light": dict(
        ink="#0b0b0b", ink2="#52514e", muted="#898781",
        grid="#e1e0d9", axis="#c3c2b7", surface="#fcfcfb",
    ),
    # Catppuccin Mocha: Text, Subtext1, Subtext0, Surface1, Overlay1, Base
    "dark": dict(
        ink="#cdd6f4", ink2="#bac2de", muted="#a6adc8",
        grid="#45475a", axis="#7f849c", surface="#1e1e2e",
    ),
}

#%% ------------------------------- ###
###          1. Functions           ###
### ------------------------------- ###


@contextmanager
def plot_style(style: str = "light") -> Generator[tuple[dict[str, str], dict[str, str]], None, None]:
    """Theme the plots drawn inside the context.

    'light' keeps matplotlib's defaults, so the plots look as they did
    before the themes. 'dark' starts from matplotlib's dark_background,
    colours text, ticks, spines, grid and legends with the dark tokens, and
    makes the figure and axes backgrounds transparent. Save a dark figure
    with transparent=True.

    Args:
        style (str, optional): 'light' or 'dark'. Defaults to 'light'.

    Raises:
        ValueError: If style is neither 'light' nor 'dark'.

    Yields:
        tuple[dict[str, str], dict[str, str]]: The theme's colour tokens, and
            the category colours with DARK_COLOR_OVERRIDES applied in 'dark'.
    """
    if style not in THEMES:
        raise ValueError(f"style must be 'light' or 'dark', not '{style}'")
    tokens = dict(THEMES[style])

    if style == "light":
        with plt.rc_context():
            yield tokens, dict(colors)
        return

    rc = {
        "text.color": tokens["ink"],
        "axes.labelcolor": tokens["ink2"],
        "xtick.color": tokens["muted"],
        "ytick.color": tokens["muted"],
        "axes.edgecolor": tokens["axis"],
        "grid.color": tokens["grid"],
        "legend.labelcolor": tokens["ink"],
        "legend.facecolor": tokens["surface"],
        "legend.edgecolor": tokens["grid"],
        "figure.facecolor": "none",
        "axes.facecolor": "none",
        "savefig.facecolor": "none",
    }
    with plt.style.context("dark_background"), plt.rc_context(rc):
        yield tokens, {**colors, **DARK_COLOR_OVERRIDES}

"""
Tests for the stacking order of the Balmorel production profile, on made-up data

GAMS-free: these tests call the plotting functions directly, without MainResults.

Created on 05.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.colors import to_hex

matplotlib.use("Agg")

from pybalmorel.formatting import balmorel_colours  # noqa: E402
from pybalmorel.plotting.production_profile import (  # noqa: E402
    _stack_order,
    single_profile_plot,
)

# %% ------------------------------- ###
###          1. Stack order         ###
### ------------------------------- ###


def test_fuels_stacked_in_entsoe_group_order():
    fuels = ["WIND", "COAL", "NUCLEAR", "ZZZ", "SUN", "NATGAS", "WATER", "WOODCHIPS", "AAA"]

    assert _stack_order(fuels, "Fuel") == [
        "NUCLEAR",
        "COAL",
        "NATGAS",
        "WOODCHIPS",
        "WATER",
        "WIND",
        "SUN",
        "AAA",
        "ZZZ",
    ]


def test_technologies_stacked_thermal_hydro_wind_solar():
    technologies = ["SOLAR-PV", "WIND-ON", "NEW-TECH", "HYDRO-RESERVOIRS", "CONDENSING"]

    assert _stack_order(technologies, "Technology") == [
        "CONDENSING",
        "HYDRO-RESERVOIRS",
        "WIND-ON",
        "SOLAR-PV",
        "NEW-TECH",
    ]


# %% ------------------------------- ###
###             2. Plot             ###
### ------------------------------- ###


def test_import_on_top_and_export_below_zero():
    index = pd.MultiIndex.from_tuples([("S01", "T001"), ("S01", "T002")], names=["SSS", "TTT"])
    demand = pd.DataFrame({"Val": [3500.0, 800.0]}, index=index)
    price = pd.DataFrame({"Val": [10.0, 20.0]}, index=index)
    production = pd.DataFrame(
        {
            "IMPORT": [2000.0, -1000.0],
            "NUCLEAR": [1000.0, 1000.0],
            "NATGAS": [500.0, 500.0],
            "WIND": [300.0, 300.0],
        },
        index=index,
    )

    fig, ax = single_profile_plot(
        "scenario", "ELECTRICITY", "DK1", "2023", "R", demand, price,
        fc="white", f=production, c=balmorel_colours, demcolor="k",
    )

    handles, labels = ax.get_legend_handles_labels()
    assert labels == ["Demand", "IMPORT", "WIND", "NATGAS", "NUCLEAR"]
    assert [text.get_text() for text in ax.get_legend().get_texts()] == [
        "Demand",
        "Import (export below 0)",
        "Wind",
        "Natgas",
        "Nuclear",
        "Price",
    ]
    areas = dict(zip(labels[1:], handles[1:]))
    assert np.isclose(areas["IMPORT"].get_paths()[0].vertices[:, 1].max(), 1.8 + 2.0)
    assert np.isclose(areas["NUCLEAR"].get_paths()[0].vertices[:, 1].min(), 0)
    export_area = ax.collections[-1]
    assert np.isclose(export_area.get_paths()[0].vertices[:, 1].min(), -1.0)
    assert to_hex(areas["NUCLEAR"].get_facecolor()[0]) == balmorel_colours["NUCLEAR"].lower()

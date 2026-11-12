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
    _aggregate_price,
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
###       2. Price aggregation      ###
### ------------------------------- ###


def _price_and_demand() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two regions over three timeslices, T003 without any demand."""
    prices = pd.DataFrame(
        {
            "RRR": ["DK1", "DK2"] * 3,
            "SSS": ["S01"] * 6,
            "TTT": ["T001", "T001", "T002", "T002", "T003", "T003"],
            "Val": [10.0, 40.0, 20.0, 20.0, 30.0, 50.0],
        }
    )
    demand = pd.DataFrame(
        {
            "RRR": ["DK1", "DK1", "DK2", "DK1", "DK2"],
            "SSS": ["S01"] * 5,
            "TTT": ["T001", "T001", "T001", "T002", "T002"],
            "VARIABLE_CATEGORY": ["EXOGENOUS", "DIST_LOSSES", "EXOGENOUS", "EXOGENOUS", "EXOGENOUS"],
            "Val": [200.0, 100.0, 100.0, 50.0, 150.0],
        }
    )
    return prices, demand


def test_load_weighted_price_weights_regions_by_demand():
    prices, demand = _price_and_demand()

    price = _aggregate_price(prices, demand, "RRR", "load-weighted")

    # T001: DK1 has 300 (two demand categories), DK2 100. T003 has no demand, so gets the average
    assert price.loc[("S01", "T001"), "Val"] == (10 * 300 + 40 * 100) / 400
    assert price.loc[("S01", "T002"), "Val"] == 20
    assert price.loc[("S01", "T003"), "Val"] == 40


def test_average_price_is_simple_mean_over_regions():
    prices, demand = _price_and_demand()

    price = _aggregate_price(prices, demand, "RRR", "average")

    assert list(price["Val"]) == [25, 20, 40]


def test_load_weighted_price_counts_demand_without_price_record_as_zero_price():
    prices, demand = _price_and_demand()
    # GDX files do not store zeros, so DK2 had a price of 0 in T001
    prices = prices[~((prices.RRR == "DK2") & (prices.TTT == "T001"))]

    price = _aggregate_price(prices, demand, "RRR", "load-weighted")

    assert price.loc[("S01", "T001"), "Val"] == (10 * 300 + 0 * 100) / 400


# %% ------------------------------- ###
###             3. Plot             ###
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
        "scenario", "ELECTRICITY", "DK1", "2023", "Price", demand, price,
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
    assert fig.axes[1].get_ylabel() == "Price [€ / MWh]"

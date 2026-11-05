# -*- coding: utf-8 -*-
"""
Created on 28.05.2022

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ----------------------------- ###
###       0. Script Settings      ###
### ----------------------------- ###

import pandas as pd
import numpy as np
from gams import GamsException
from typing import Tuple, List
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.collections import PolyCollection
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt

from ..utils import symbol_to_df
from ..formatting import balmorel_colours, fuel_groups, technology_order


# %% ----------------------------- ###
###       1. Public Functions     ###
### ----------------------------- ###


def plot_profile(
    MainResults,
    commodity: str,
    year: int,
    scenario: str | int = 0,
    columns: str = "Technology",
    region: str = "ALL",
    style: str = "light",
    seasons: str | list[str] | None = None,
    terms: str | list[str] | None = None,
) -> Tuple[Figure, Axes]:
    """Plots the production profile of a commodity, in a year, for a certain scenario

    By default the whole year is plotted. Use `seasons` and/or `terms` to plot
    only part of it, e.g. `seasons='S02'` plots the second week in a model
    with weekly seasons.

    Args:
        MainResults (_type_): The MainResults class containing results
        commodity (str): The commodity (Electricity, Heat or Hydrogen)
        year (int): The model year to plot
        scenario (str, optional): Defaults to the first scenario in MainResults.
        columns (str, optional): Technology or Fuel as . Defaults to 'Technology'.
        region (str, optional): Which country, region or area to plot. Defaults to 'ALL'.
        style (str, optional): Plot style, light or dark. Defaults to 'light'.
        seasons (str | list[str] | None, optional): Season(s) to plot, e.g. 'S02' or ['S02', 'S03']. Defaults to None, which plots all seasons.
        terms (str | list[str] | None, optional): Term(s) to plot within the chosen seasons, e.g. ['T001', 'T002']. Defaults to None, which plots all terms.

    Returns:
        Figure, Axes: The figure and axes objects for further manipulations
    """

    fc, demcolor = _set_plot_style(style)
    scenario, commodity, region, year, CorRorA, fD, fP, f = _prepare_profile_data(
        MainResults, commodity, year, scenario, columns, region
    )
    fD, fP, f = _select_timeslices(fD, fP, f, seasons, terms)

    ### Plot a profile for all selected timeslices
    fig, ax = single_profile_plot(
        scenario,
        commodity,
        region,
        year,
        CorRorA,
        fD,
        fP,
        fc=fc,
        f=f,
        c=balmorel_colours,
        demcolor=demcolor,
    )

    return fig, ax


def plot_profiles(
    MainResults,
    commodity: str,
    year: int,
    scenario: str | int = 0,
    chunk_size: int = 168,
    columns: str = "Technology",
    region: str = "ALL",
    style: str = "light",
    seasons: str | list[str] | None = None,
    terms: str | list[str] | None = None,
) -> Tuple[List, List]:
    """Plots the production profile of a commodity, in a year, for a certain scenario,
    split into one figure per `chunk_size` timeslices

    Use `seasons` and/or `terms` to only plot part of the year, e.g.
    `seasons=['S02', 'S03']` with `chunk_size=168` gives one figure for each
    of those two weeks in a model with weekly seasons of 168 terms.

    Args:
        MainResults (_type_): The MainResults class containing results
        commodity (str): The commodity (Electricity, Heat or Hydrogen)
        year (int): The model year to plot
        scenario (str, optional): Defaults to the first scenario in MainResults.
        chunk_size (int, optional): How many timeslices per profile, defaults to 168
        columns (str, optional): Technology or Fuel as . Defaults to 'Technology'.
        region (str, optional): Which country, region or area to plot. Defaults to 'ALL'.
        style (str, optional): Plot style, light or dark. Defaults to 'light'.
        seasons (str | list[str] | None, optional): Season(s) to plot, e.g. 'S02' or ['S02', 'S03']. Defaults to None, which plots all seasons.
        terms (str | list[str] | None, optional): Term(s) to plot within the chosen seasons, e.g. ['T001', 'T002']. Defaults to None, which plots all terms.

    Returns:
        list[Figure], list[Axes]: The figure and axes objects for further manipulations
    """

    fc, demcolor = _set_plot_style(style)
    scenario, commodity, region, year, CorRorA, fD, fP, f = _prepare_profile_data(
        MainResults, commodity, year, scenario, columns, region
    )
    fD, fP, f = _select_timeslices(fD, fP, f, seasons, terms)

    ### Plot a profile per chunk of timeslices - if fewer than chunk_size timeslices, will only plot one
    figs, axes = [], []
    for i in range(0, len(fD), chunk_size):
        fig, ax = single_profile_plot(
            scenario,
            commodity,
            region,
            year,
            CorRorA,
            fD.iloc[i : i + chunk_size, :],
            fP.iloc[i : i + chunk_size, :],
            fc=fc,
            f=f,
            c=balmorel_colours,
            demcolor=demcolor,
        )
        figs.append(fig)
        axes.append(ax)

    return figs, axes


# %% ----------------------------- ###
###        2. Data Handling       ###
### ----------------------------- ###


def _set_plot_style(style: str) -> tuple[str, str]:
    """Set the matplotlib style and return the matching face and demand line colours.

    Args:
        style (str): Plot style, 'light' or 'dark'.

    Returns:
        tuple[str, str]: Face colour and demand line colour.
    """
    if style == "light":
        plt.style.use("default")
        return "white", "k"
    elif style == "dark":
        plt.style.use("dark_background")
        return "none", "w"
    raise Exception(f"style must be 'light' or 'dark', not '{style}'")


def _stack_order(production_columns: list[str], columns: str) -> list[str]:
    """Order production columns from the bottom of the stack up, as the ENTSO-E profile stacks them.

    Args:
        production_columns (list[str]): The fuels or technologies to order.
        columns (str): 'Fuel', which orders by `fuel_groups`, or 'Technology',
            which orders by `technology_order`.

    Returns:
        list[str]: The columns in stacking order. Columns not listed in
            `fuel_groups` or `technology_order` come last, in alphabetical order.
    """
    if columns == "Fuel":
        order = [fuel for fuels in fuel_groups.values() for fuel in fuels]
    else:
        order = technology_order
    listed = [column for column in order if column in production_columns]
    return listed + sorted(column for column in production_columns if column not in order)


def _select_timeslices(
    fD: pd.DataFrame,
    fP: pd.DataFrame,
    f: pd.DataFrame,
    seasons: str | list[str] | None = None,
    terms: str | list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Keep only the chosen seasons and terms of the demand, price and production data.

    Args:
        fD (pd.DataFrame): Demand, indexed by (season, term).
        fP (pd.DataFrame): Price, with the same index as fD.
        f (pd.DataFrame): Production and import per column, with the same index as fD.
        seasons (str | list[str] | None, optional): Season(s) to keep. Defaults to None, which keeps all.
        terms (str | list[str] | None, optional): Term(s) to keep. Defaults to None, which keeps all.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: The filtered fD, fP and f.
    """
    mask = np.ones(len(fD), dtype=bool)
    for level, selection, set_name in ((0, seasons, "season"), (1, terms, "term")):
        if selection is None:
            continue
        if isinstance(selection, str):
            selection = [selection]

        available = fD.index.get_level_values(level)
        missing = [element for element in selection if element not in available]
        if len(missing) > 0:
            raise Exception(
                f"{set_name.capitalize()}(s) {missing} not found in the results. "
                f"Available {set_name}s: {list(available.unique())}"
            )
        mask &= available.isin(selection)

    if not mask.any():
        raise Exception(
            f"No timeslices found for seasons={seasons} and terms={terms}"
        )

    return fD[mask], fP[mask], f[mask]


def _prepare_profile_data(
    MainResults,
    commodity: str,
    year: int,
    scenario: str | int,
    columns: str,
    region: str,
) -> tuple[str, str, str, str, str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and aggregate demand, price, production and import data for a profile plot.

    Args:
        MainResults (_type_): The MainResults class containing results
        commodity (str): The commodity (Electricity, Heat or Hydrogen)
        year (int): The model year to plot
        scenario (str | int): Scenario name or index in MainResults.sc.
        columns (str): Technology or Fuel.
        region (str): Which country, region or area to plot, or 'ALL'.

    Returns:
        tuple: scenario, commodity, region, year and region level (C, R, A or All),
            followed by demand, price and production DataFrames sharing the same
            sorted (season, term) index.
    """

    if type(scenario) == int:
        scenario = MainResults.sc[scenario]

    commodity = commodity.upper()
    year = str(year)

    ### ----------------------------- ###
    ###        1. Read Files          ###
    ### ----------------------------- ###

    ### Try to load the non-iteration scenario suffix first
    db = MainResults.db[scenario]

    fProd = symbol_to_df(
        db,
        "PRO_YCRAGFST",
        cols=[
            "Y",
            "C",
            "RRR",
            "AAA",
            "G",
            "Fuel",
            "SSS",
            "TTT",
            "COMMODITY",
            "Technology",
            "UNITS",
            "Val",
        ],
    )

    if commodity == "ELECTRICITY":
        fPrice = symbol_to_df(
            db, "EL_PRICE_YCRST", cols=["Y", "C", "RRR", "SSS", "TTT", "UNITS", "Val"]
        )
        fDem = symbol_to_df(
            db,
            "EL_DEMAND_YCRST",
            cols=["Y", "C", "RRR", "SSS", "TTT", "VARIABLE_CATEGORY", "UNIT", "Val"],
        )
        fBal = symbol_to_df(
            db,
            "EL_BALANCE_YCRST",
            cols=["Y", "C", "RRR", "Technology", "SSS", "TTT", "UNIT", "Val"],
        )
        fBal = fBal[fBal.Technology == "EXPORT3RD"]
    elif commodity == "HYDROGEN":
        fPrice = symbol_to_df(
            db, "H2_PRICE_YCRST", cols=["Y", "C", "RRR", "SSS", "TTT", "UNITS", "Val"]
        )
        fDem = symbol_to_df(
            db,
            "H2_DEMAND_YCRST",
            cols=["Y", "C", "RRR", "SSS", "TTT", "VARIABLE_CATEGORY", "UNIT", "Val"],
        )
    elif commodity == "HEAT":
        fPrice = symbol_to_df(
            db,
            "H_PRICE_YCRAST",
            cols=["Y", "C", "RRR", "AAA", "SSS", "TTT", "UNITS", "Val"],
        )
        fDem = symbol_to_df(
            db,
            "H_DEMAND_YCRAST",
            cols=[
                "Y",
                "C",
                "RRR",
                "AAA",
                "SSS",
                "TTT",
                "VARIABLE_CATEGORY",
                "UNIT",
                "Val",
            ],
        )

    ### ----------------------------- ###
    ###           Parameters          ###
    ### ----------------------------- ###

    # Choices
    try:
        if region.upper() in fProd.C.unique():
            CorRorA = "C"  # Region or country level?
            country = region.upper()
            # Load transmission
            if commodity == "ELECTRICITY":
                fFlow = symbol_to_df(
                    db,
                    "X_FLOW_YCRST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            elif commodity == "HYDROGEN":
                fFlow = symbol_to_df(
                    db,
                    "XH2_FLOW_YCRST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            elif commodity == "HEAT":
                fFlow = symbol_to_df(
                    db,
                    "XH_FLOW_YCAST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            else:
                pass
        elif region in fProd.RRR.unique():
            CorRorA = "R"
            # Load transmission
            if commodity == "ELECTRICITY":
                fFlow = symbol_to_df(
                    db,
                    "X_FLOW_YCRST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            elif commodity == "HYDROGEN":
                fFlow = symbol_to_df(
                    db,
                    "XH2_FLOW_YCRST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            elif commodity == "HEAT":
                fFlow = symbol_to_df(
                    db,
                    "XH_FLOW_YCAST",
                    cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
                )
            else:
                pass
        elif region in fProd.AAA.unique():
            CorRorA = "A"
            fFlow = symbol_to_df(
                db,
                "XH_FLOW_YCAST",
                cols=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"],
            )
        elif region.upper() == "ALL":
            region = "All"
            CorRorA = "All"
    except GamsException:
        fFlow = pd.DataFrame(
            columns=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"]
        )

    # Check if flow is empty
    if region != "All":
        if len(fFlow) == 0:
            fFlow = pd.DataFrame(
                columns=["Y", "C", "IRRRE", "IRRRI", "SSS", "TTT", "UNITS", "Val"]
            )

    resfactor = 1  # Factor on flows, to get yearly results
    price_agg_func = (
        np.average
    )  # function for aggregation of regions - average or max ?
    bypass_eps = "Y"  # Bypass EPS values in electricity prices? This could be fair, if you have regions with very small electricity demand, making EPS electricity prices (not wrong)

    ### ----------------------------- ###
    ###              Sort             ###
    ### ----------------------------- ###

    # Production
    if CorRorA == "R":
        idx = fProd["RRR"] == region
    elif CorRorA == "C":
        idx = fProd["C"] == country
    elif CorRorA == "A":
        idx = fProd["AAA"] == region
    elif CorRorA == "All":
        idx = fProd["C"] == fProd["C"]
    idx = idx & (fProd["COMMODITY"] == commodity)
    idx = idx & (fProd["Y"] == year)

    # Make temporal index
    t_index = pd.MultiIndex.from_product(
        (fProd.SSS.unique(), fProd.TTT.unique()), names=["SSS", "TTT"]
    )
    df_placeholder = pd.DataFrame(index=t_index)

    # Create production dataframe
    fPr = fProd[idx].pivot_table(
        values="Val", index=["SSS", "TTT"], columns=[columns], aggfunc="sum"
    )
    fPr = df_placeholder.join(fPr, how="left")
    fPr.fillna(0, inplace=True)
    fPr = fPr[_stack_order(list(fPr.columns), columns)]

    ### Import / Export
    # First aggregate regions in country, if country
    if CorRorA == "C":
        for reg0 in [reg0 for reg0 in fFlow.loc[fFlow.C == region, "IRRRE"].unique()]:
            fFlow["IRRRE"] = fFlow["IRRRE"].str.replace(reg0, country)
            fFlow["IRRRI"] = fFlow["IRRRI"].str.replace(reg0, country)
        # Delete internal flows
        fFlow = fFlow[~((fFlow.IRRRE == region) & (fFlow.IRRRI == region))]

    # Get year
    # print('Note that the following flows have not been scaled to fit annual flows\n')
    try:
        idx = fFlow["Y"] == year

        idx1 = fFlow["IRRRE"] == region
        idx2 = fFlow["IRRRI"] == region

        fFlE = fFlow[idx & idx1].pivot_table(
            values="Val", index=["SSS", "TTT"], aggfunc="sum"
        )
        fFlI = fFlow[idx & idx2].pivot_table(
            values="Val", index=["SSS", "TTT"], aggfunc="sum"
        )

        # Make sure no values are missing
        fFlE = df_placeholder.join(fFlE, how="left")
        fFlE.fillna(0, inplace=True)

        fFlI = df_placeholder.join(fFlI, how="left")
        fFlI.fillna(0, inplace=True)

        # print('\n' + region + ' Main Export-To Regions: [TWh]')
        # print(fFlow[idx & idx1].pivot_table(values='Val', index=['IRRRI'], aggfunc='sum')/1e6*resfactor  )
        # print('\n')

        # print(region + ' Main Import-From Regions: [TWh]')
        # print(fFlow[idx & idx2].pivot_table(values='Val', index=['IRRRE'], aggfunc='sum')/1e6*resfactor  )
        # print('\n')
        no_trans_data = False
    except (KeyError, NameError):
        no_trans_data = True
        # print('No transmission data')

    ### Electricity Demand and price
    if CorRorA == "C":
        fP = fPrice.groupby(["Y", "C", "SSS", "TTT"], as_index=False)
        fP = fP.aggregate(
            {"Val": price_agg_func}
        )  # For aggregation of electricity price, max or average? (maybe max if nodal representation of a market?)
        fP = fP[fP.C == country]

        if commodity == "ELECTRICITY":
            fBal = (
                fBal[(fBal.C == country) & (fBal.Y == year)]
                .pivot_table(values="Val", index=["SSS", "TTT"], aggfunc="sum")
                .fillna(0)
            )
        fD = fDem.groupby(["Y", "C", "VARIABLE_CATEGORY", "SSS", "TTT"], as_index=False)
        fD = fD.aggregate({"Val": np.sum})
        dems = fD[(fD["Y"] == year) & (fD["C"] == country)]
        fD = fDem[fDem.C == country]
    elif CorRorA == "R":
        dems = fDem[(fDem["Y"] == year) & (fDem["RRR"] == region)]
        fP = fPrice[fPrice["RRR"] == region]
        if commodity == "ELECTRICITY":
            fBal = (
                fBal[(fBal.RRR == region) & (fBal.Y == year)]
                .pivot_table(values="Val", index=["SSS", "TTT"], aggfunc="sum")
                .fillna(0)
            )
        fD = fDem[fDem["RRR"] == region]
    elif CorRorA == "A":
        dems = fDem[(fDem["Y"] == year) & (fDem["AAA"] == region)]
        fP = fPrice[fPrice["AAA"] == region]
        fD = fDem[fDem["AAA"] == region]
    elif CorRorA == "All":
        fP = fPrice.groupby(["Y", "C", "SSS", "TTT"], as_index=False)
        fP = fP.aggregate(
            {"Val": price_agg_func}
        )  # For aggregation of electricity price, max or average? (maybe max if nodal representation of a market?)
        if commodity == "ELECTRICITY":
            fBal = (
                fBal[(fBal.Y == year)]
                .pivot_table(values="Val", index=["SSS", "TTT"], aggfunc="sum")
                .fillna(0)
            )
        fD = fDem.groupby(["Y", "C", "VARIABLE_CATEGORY", "SSS", "TTT"], as_index=False)
        fD = fD.aggregate({"Val": "sum"})
        dems = fD[(fD["Y"] == year)]

    # print('Electricity Demand: [TWh]')
    # for cat in np.unique(dems['VARIABLE_CATEGORY']):
    #     print(cat, ' = ', round(dems[dems['VARIABLE_CATEGORY'] == cat]['Val'].sum()/1e6*resfactor,2))

    # Subtract import from export
    f = pd.DataFrame({"IMPORT": np.zeros(len(fPr))}, index=fPr.index)
    if not (no_trans_data):
        # f = f + fFlI - fFlE
        f_temp = pd.DataFrame([], index=fPr.index)
        try:
            f_temp["IMPORT"] = fFlI
            f_temp["EXPORT"] = -fFlE
            f_temp[np.isnan(f_temp)] = 0
        except ValueError:
            # If no connections to this region
            pass

        # f[np.isnan(f)] = 0
        # f.columns = ['IMPORT']
        f = pd.DataFrame([], index=fPr.index)
        f["IMPORT"] = f_temp.sum(axis=1)

        f[fPr.columns] = fPr

    else:
        f = pd.DataFrame([], index=fPr.index)
        f[fPr.columns] = fPr

    # Price
    if bypass_eps.lower() == "y":
        idx = fP.Val == "Eps"
        fP.loc[idx, "Val"] = (
            0  # If you chose to bypass eps values in el-price, it's probably because the actual prices are very small
        )
        fP.loc[:, "Val"] = fP.Val.astype(float).values

    idx = fP["Y"] == year
    fP = fP[idx].pivot_table(values="Val", index=["SSS", "TTT"], aggfunc=price_agg_func)

    # Make sure no values are missing
    fP = df_placeholder.join(fP, how="left")
    fP.fillna(0, inplace=True)

    # Demand
    idx = fD["Y"] == year
    fD = fD[idx].pivot_table(values="Val", index=["SSS", "TTT"], aggfunc="sum")

    # Make sure no values are missing
    fD = df_placeholder.join(fD, how="left")
    fD = fD.fillna(0)

    # Add import/export from 3rd countries
    if commodity == "ELECTRICITY":
        try:
            fD = fD.add(fBal, fill_value=0)
        except ValueError:
            # In case no 3RD country export/import
            pass

    # x-axis
    xticks = fD.sort_index().index
    fD = fD.loc[xticks]

    # Align price and production to the sorted demand index
    fP = fP.reindex(xticks, fill_value=0)
    f = f.reindex(xticks, fill_value=0)

    return scenario, commodity, region, year, CorRorA, fD, fP, f


# %% ----------------------------- ###
###           3. Plotting         ###
### ----------------------------- ###


def _fill_area(
    ax: Axes,
    x: range,
    lower: np.ndarray,
    upper: np.ndarray,
    column: str,
    colours: dict[str, str],
) -> PolyCollection:
    """Fill between lower and upper in the colour of a fuel or technology.

    Args:
        ax (Axes): The axes to draw on.
        x (range): Timeslice positions.
        lower (np.ndarray): Lower edge of the area, GW.
        upper (np.ndarray): Upper edge of the area, GW.
        column (str): The fuel or technology, used as label and colour key.
        colours (dict[str, str]): Colour per fuel or technology. Columns without
            one get matplotlib's next colour.

    Returns:
        PolyCollection: The filled area.
    """
    if column not in colours:
        print("No defined colour for %s" % column)
        return ax.fill_between(x, lower, upper, label=column)
    return ax.fill_between(x, lower, upper, label=column, facecolor=colours[column])


def single_profile_plot(
    scenario, commodity, region, year, CorRorA, fD, fP, fc, f, c, demcolor
):
    fig, ax = plt.subplots(figsize=(9, 3), facecolor=fc)
    x = range(len(fD))
    values = {col: f.loc[fD.index, col].values / 1e3 for col in f}

    # Production is stacked from 0 in the order of the columns, net import goes
    # on top and net export below 0, as in the ENTSO-E profile
    production = [col for col in f if col != "IMPORT"]
    bottoms = {}
    top = np.zeros(len(fD))
    for col in production:
        bottoms[col] = top
        top = top + values[col]

    # Artists are added in legend order: demand, import, then production from the top down
    (demand_line,) = ax.plot(x, fD.values[:, 0] / 1e3, color=demcolor, label="Demand")
    handles, names = [demand_line], ["Demand"]
    if "IMPORT" in values:
        net_import = values["IMPORT"]
        import_area = _fill_area(ax, x, top, top + np.clip(net_import, 0, None), "IMPORT", c)
        handles.append(import_area)
        names.append("Import (export below 0)")
    for col in reversed(production):
        handles.append(_fill_area(ax, x, bottoms[col], bottoms[col] + values[col], col, c))
        names.append(col.lower().capitalize())
    if "IMPORT" in values:
        ax.fill_between(
            x, 0, np.clip(net_import, None, 0), facecolor=import_area.get_facecolor()
        )

    ax2 = ax.twinx()
    try:
        (price_line,) = ax2.plot(
            x, fP.loc[fD.index].values, "r--", linewidth=1, label="Price"
        )
        handles.append(price_line)
        names.append("Price")
    except TypeError:
        print('\nThere could be "EPS" values in electricity prices - cannot plot')

    ax.set_facecolor(fc)
    ax.legend(
        handles,
        names,
        loc="center",
        bbox_to_anchor=(0.5, 1.28),
        ncol=5,
    )
    ax.set_title(scenario + " - " + commodity + " - " + region + " - " + str(year))
    ax.set_ylabel("Power [GW]")

    if (CorRorA == "R") | (CorRorA == "A"):
        ax2.set_ylabel("Price [€ / MWh]")
    else:
        ax2.set_ylabel("Average Price [€ / MWh]")

    ax.set_xlim([min(x), max(x)])

    # Label ticks with season and term, only on whole timeslices within the plotted range
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    xticks = [int(tick) for tick in ax.get_xticks() if min(x) <= tick <= max(x)]
    seasons = list(fD.index.get_level_values(0))
    terms = list(fD.index.get_level_values(1))
    xticklabels = [f"{seasons[i]} {terms[i]}" for i in xticks]
    ax.set_xticks(xticks, xticklabels, rotation=90)

    return fig, ax

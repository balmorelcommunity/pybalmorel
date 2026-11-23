"""
IAMC Reader

The only part of the IAMC conversion that knows Balmorel symbol and column
names. It reads MainResults into one long table of what each unit does, which
the GAMS-free conversion in convert.py turns into IAMC Variables.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from ..classes import MainResults

# Columns of the long table, by the column names MainResults.get_result gives
long_columns = {
    "Scenario": "scenario",
    "Year": "year",
    "Country": "country",
    "Area": "area",
    "Generation": "unit_name",
    "Technology": "tech_type",
    "Fuel": "fuel",
    "Commodity": "commodity",
    "Category": "demand_category",
    "To": "to_area",
    "Unit": "value_unit",
    "Value": "value",
}

# The symbols each quantity is read from, the commodity they are of if they don't say, whether
# every scenario must have them, and column renames before long_columns applies. Hydrogen
# demand and transmission are per region, so their rows have no area.
quantity_symbols = [
    {"quantity": "capacity", "symbol": "G_CAP_YCRAF", "commodity": None, "required": True, "renames": {}},
    {"quantity": "output", "symbol": "PRO_YCRAGF", "commodity": None, "required": True, "renames": {}},
    {"quantity": "demand", "symbol": "H_DEMAND_YCRA", "commodity": "HEAT", "required": False, "renames": {}},
    {"quantity": "demand", "symbol": "H2_DEMAND_YCR", "commodity": "HYDROGEN", "required": False, "renames": {}},
    {"quantity": "exchange", "symbol": "XH_FLOW_YCA", "commodity": "HEAT", "required": False,
     "renames": {"From": "Area"}},
    {"quantity": "exchange", "symbol": "XH2_FLOW_YCR", "commodity": "HYDROGEN", "required": False,
     "renames": {"To": "To region"}},
]
# Columns naming where something is, whose country the Country column gives
place_columns = ["Region", "Area", "From"]


#%% ------------------------------- ###
###          1. Long Table          ###
### ------------------------------- ###

def read_mainresults(results: "MainResults") -> pd.DataFrame:
    """Read the long table of what each unit and area does from MainResults.

    Capacity is net: the sum of G_CAP_YCRAF's exogenous, endogenous and (negative)
    decommissioning categories. Demand (H_DEMAND_YCRA per area, H2_DEMAND_YCR per region) and
    exchange (XH_FLOW_YCA, heat transmission from 'area' to 'to_area'; XH2_FLOW_YCR, hydrogen
    transmission between regions) are read where the results have them. Exchange rows say which
    country they go to.

    Args:
        results (MainResults): The loaded result files.

    Returns:
        pd.DataFrame: One row per scenario, year, country, area, unit, fuel, commodity, demand
            category, receiving area and country, and quantity, with the columns of long_columns,
            'to_country' and 'quantity' ('capacity', 'output', 'demand' or 'exchange'). Columns a
            quantity doesn't have are ''.
    """
    tables = []
    # Country of each region and area, for where exchange goes
    countries = {}
    for spec in quantity_symbols:
        symbol = spec["symbol"]
        if not spec["required"] and not any(has_symbol(results, scenario, symbol) for scenario in results.sc):
            continue
        table = results.get_result(symbol)
        if table.empty:
            if spec["required"]:
                raise Exception(f"No scenario has '{symbol}', which IAMC {spec['quantity']} is read from.")
            continue

        for column in place_columns:
            if column in table.columns:
                pairs = table[[column, "Country"]].drop_duplicates().astype(str)
                countries.update(zip(pairs[column], pairs["Country"]))
        to_country = table["To"].astype(str).map(countries).fillna("") if "To" in table.columns else ""

        table = table.rename(columns=spec["renames"]).rename(columns=long_columns)
        if spec["commodity"] is not None:
            table["commodity"] = spec["commodity"]
        for column in long_columns.values():
            if column not in table.columns:
                table[column] = ""
        table = table[list(long_columns.values())].assign(to_country=to_country)
        keys = [column for column in table.columns if column != "value"]
        # Sums capacity categories and transmission between regions of the same two countries
        table = table.groupby(keys, as_index=False, observed=True)["value"].sum()
        table["quantity"] = spec["quantity"]
        tables.append(table)

    long = pd.concat(tables, ignore_index=True)
    long["year"] = long["year"].astype(int)
    return long


def has_symbol(results: "MainResults", scenario: str, symbol: str) -> bool:
    """Whether one scenario's result file has a symbol.

    Args:
        results (MainResults): The loaded result files.
        scenario (str): The scenario.
        symbol (str): The GAMS symbol, e.g. 'XH_FLOW_YCA'.

    Returns:
        bool: True if the file has the symbol, even if it is empty.
    """
    return any(item.name == symbol for item in results.db[scenario])

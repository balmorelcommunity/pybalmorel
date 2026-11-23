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

# The symbol each quantity is read from, the commodity it is of if the symbol doesn't say,
# whether every scenario must have it, and column renames before long_columns applies
quantity_symbols = {
    "capacity": {"symbol": "G_CAP_YCRAF", "commodity": None, "required": True, "renames": {}},
    "output": {"symbol": "PRO_YCRAGF", "commodity": None, "required": True, "renames": {}},
    "demand": {"symbol": "H_DEMAND_YCRA", "commodity": "HEAT", "required": False, "renames": {}},
    "exchange": {"symbol": "XH_FLOW_YCA", "commodity": "HEAT", "required": False, "renames": {"From": "Area"}},
}


#%% ------------------------------- ###
###          1. Long Table          ###
### ------------------------------- ###

def read_mainresults(results: "MainResults") -> pd.DataFrame:
    """Read the long table of what each unit and area does from MainResults.

    Capacity is net: the sum of G_CAP_YCRAF's exogenous, endogenous and (negative)
    decommissioning categories. Demand (H_DEMAND_YCRA) and exchange (XH_FLOW_YCA, heat
    transmission from 'area' to 'to_area') are read where the results have them.

    Args:
        results (MainResults): The loaded result files.

    Returns:
        pd.DataFrame: One row per scenario, year, country, area, unit, fuel, commodity, demand
            category, receiving area and quantity, with the columns of long_columns and
            'quantity' ('capacity', 'output', 'demand' or 'exchange'). Columns a quantity
            doesn't have are ''.
    """
    tables = []
    for quantity, spec in quantity_symbols.items():
        symbol = spec["symbol"]
        if not spec["required"] and not any(has_symbol(results, scenario, symbol) for scenario in results.sc):
            continue
        table = results.get_result(symbol)
        if table.empty:
            if spec["required"]:
                raise Exception(f"No scenario has '{symbol}', which IAMC {quantity} is read from.")
            continue

        table = table.rename(columns=spec["renames"]).rename(columns=long_columns)
        if spec["commodity"] is not None:
            table["commodity"] = spec["commodity"]
        for column in long_columns.values():
            if column not in table.columns:
                table[column] = ""
        table = table[list(long_columns.values())]
        keys = [column for column in table.columns if column != "value"]
        # Sums capacity categories; other quantities have one row per key already
        table = table.groupby(keys, as_index=False, observed=True)["value"].sum()
        table["quantity"] = quantity
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

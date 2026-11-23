"""
IAMC Reader

The only part of the IAMC conversion that knows Balmorel symbol and column
names. It reads MainResults into one long table of what each unit does, which
the GAMS-free conversion in convert.py turns into IAMC Variables.

Created on 23.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
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
    "Unit": "value_unit",
    "Value": "value",
}

# The symbol each quantity is read from
quantity_symbols = {
    "capacity": "G_CAP_YCRAF",
    "output": "PRO_YCRAGF",
}


#%% ------------------------------- ###
###          1. Long Table          ###
### ------------------------------- ###

def read_mainresults(results: "MainResults") -> pd.DataFrame:
    """Read the long table of what each unit does from MainResults.

    Capacity is net: the sum of G_CAP_YCRAF's exogenous, endogenous and (negative)
    decommissioning categories.

    Args:
        results (MainResults): The loaded result files.

    Returns:
        pd.DataFrame: One row per scenario, year, country, area, unit, fuel, commodity and
            quantity, with the columns scenario, year, country, area, unit_name, tech_type, fuel,
            commodity, quantity ('capacity' or 'output'), value_unit and value.
    """
    tables = []
    for quantity, symbol in quantity_symbols.items():
        table = results.get_result(symbol)
        if table.empty:
            raise Exception(f"No scenario has '{symbol}', which IAMC {quantity} is read from.")

        table = table.rename(columns=long_columns)[list(long_columns.values())]
        keys = [column for column in table.columns if column != "value"]
        # Sums capacity categories; output has one row per key already
        table = table.groupby(keys, as_index=False, observed=True)["value"].sum()
        table["quantity"] = quantity
        tables.append(table)

    long = pd.concat(tables, ignore_index=True)
    long["year"] = long["year"].astype(int)
    return long

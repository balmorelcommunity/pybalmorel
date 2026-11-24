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

from pathlib import Path
from typing import TYPE_CHECKING
import gams.transfer as gt
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
# Columns only some quantities have, '' for the others
extra_columns = ["to_country", "stated_unit", "from_process", "to_process", "flow"]

# The symbols each quantity is read from, the commodity they are of if they don't say, whether
# every scenario must have them, and column renames before long_columns applies. Electricity
# and hydrogen demand and transmission are per region, so their rows have no area. Emissions and
# captured CO2 are per unit but not per commodity; their unit is fixed, as results don't always
# state it right, and the units they may state for it are listed. Fuel input is per unit too; it
# is not reported, but gives the electricity that heat units outside district heating use, and
# derives captured CO2 where the results don't give it.
quantity_symbols = [
    {"quantity": "capacity", "symbol": "G_CAP_YCRAF", "commodity": None, "required": True, "renames": {}},
    {"quantity": "output", "symbol": "PRO_YCRAGF", "commodity": None, "required": True, "renames": {}},
    {"quantity": "demand", "symbol": "EL_DEMAND_YCR", "commodity": "ELECTRICITY", "required": False, "renames": {}},
    {"quantity": "demand", "symbol": "H_DEMAND_YCRA", "commodity": "HEAT", "required": False, "renames": {}},
    {"quantity": "demand", "symbol": "H2_DEMAND_YCR", "commodity": "HYDROGEN", "required": False, "renames": {}},
    {"quantity": "exchange", "symbol": "X_FLOW_YCR", "commodity": "ELECTRICITY", "required": False,
     "renames": {"To": "To region"}},
    {"quantity": "exchange", "symbol": "XH_FLOW_YCA", "commodity": "HEAT", "required": False,
     "renames": {"From": "Area"}},
    {"quantity": "exchange", "symbol": "XH2_FLOW_YCR", "commodity": "HYDROGEN", "required": False,
     "renames": {"To": "To region"}},
    {"quantity": "emissions", "symbol": "EMI_YCRAG", "commodity": None, "required": False, "renames": {},
     "unit": "kt CO2", "unit_aliases": {"kton", "kt"}},
    {"quantity": "captured", "symbol": "CC_YCRAG", "commodity": None, "required": False, "renames": {},
     "unit": "kt CO2", "unit_aliases": {"kton", "kt"}},
    {"quantity": "input", "symbol": "F_CONS_YCRA", "commodity": None, "required": False, "renames": {},
     "unit": "TWh", "unit_aliases": {"TWh"}},
]
# OptiFlow's flows between processes, and the result file names next to a MainResults file
optiflow_symbol = "VFLOW_Opti_C"
optiflow_columns = {"Y": "year", "CCC": "country", "IPROCFROM": "from_process", "IPROCTO": "to_process",
                    "FLOW": "flow", "value": "value"}
optiflow_prefix = "Optiflow_"
# Columns naming where something is, whose country the Country column gives
place_columns = ["Region", "Area", "From"]


#%% ------------------------------- ###
###          1. Long Table          ###
### ------------------------------- ###

def read_mainresults(results: "MainResults",
                     optiflow: dict[str, str | Path | None] | None = None) -> pd.DataFrame:
    """Read the long table of what each unit and area does from MainResults.

    Capacity is net: the sum of G_CAP_YCRAF's exogenous, endogenous and (negative)
    decommissioning categories. Demand (EL_DEMAND_YCR and H2_DEMAND_YCR per region, H_DEMAND_YCRA
    per area) and exchange (X_FLOW_YCR and XH2_FLOW_YCR, electricity and hydrogen transmission
    between regions; XH_FLOW_YCA, heat transmission from 'area' to 'to_area') are read where the
    results have them. Exchange rows say which country they go to. Emissions (EMI_YCRAG),
    captured CO2 (CC_YCRAG) and fuel input (F_CONS_YCRA) are per unit, with no commodity. Where a
    scenario was linked to OptiFlow, OptiFlow's flows between processes (VFLOW_Opti_C) are read
    too.

    Args:
        results (MainResults): The loaded result files.
        optiflow (dict[str, str | Path | None] | None, optional): OptiFlow result file per
            scenario; None for a scenario without OptiFlow. Scenarios not listed use
            'Optiflow_<MainResults file>' next to their MainResults file, if it exists.
            Defaults to None.

    Returns:
        pd.DataFrame: One row per scenario, year, country, area, unit, fuel, commodity, demand
            category, receiving area and country, and quantity, with the columns of long_columns,
            extra_columns and 'quantity' ('capacity', 'output', 'demand', 'exchange',
            'emissions', 'captured', 'input' or 'flow'). Columns a quantity doesn't have are ''.
            'stated_unit' is the unit the results state where it isn't one the Reader expects.
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
        table = table[list(long_columns.values())].assign(to_country=to_country, stated_unit="")
        if "unit" in spec:
            stated = table["value_unit"].astype(str)
            table["stated_unit"] = stated.where(~stated.isin(spec["unit_aliases"]), "")
            table["value_unit"] = spec["unit"]
        keys = [column for column in table.columns if column != "value"]
        # Sums capacity categories and transmission between regions of the same two countries
        table = table.groupby(keys, as_index=False, observed=True)["value"].sum()
        table["quantity"] = spec["quantity"]
        tables.append(table)

    flows = read_optiflow(results, optiflow or {})
    if not flows.empty:
        tables.append(flows)
    long = pd.concat(tables, ignore_index=True)
    for column in list(long_columns.values()) + extra_columns:
        if column not in long.columns:
            long[column] = ""
        if column != "value":
            long[column] = long[column].fillna("")
    long["year"] = long["year"].astype(int)
    return long


def read_optiflow(results: "MainResults", optiflow: dict[str, str | Path | None]) -> pd.DataFrame:
    """Read OptiFlow's flows between processes for the scenarios linked to it.

    Args:
        results (MainResults): The loaded result files.
        optiflow (dict[str, str | Path | None]): OptiFlow result file per scenario, as in
            read_mainresults.

    Returns:
        pd.DataFrame: Rows of quantity 'flow' with scenario, year, country, from_process,
            to_process, flow and value, without zero flows; no rows if no scenario has OptiFlow
            results.
    """
    unknown = [scenario for scenario in optiflow if scenario not in results.sc]
    if unknown:
        raise Exception(f"OptiFlow results are given for scenarios {unknown}, which the results don't have "
                        f"({results.sc}).")

    tables = []
    for scenario, path, file in zip(results.sc, results.paths, results.files):
        if scenario in optiflow:
            source = optiflow[scenario]
            if source is None:
                continue
            source = Path(source)
            if not source.exists():
                raise Exception(f"No OptiFlow results at '{source}' for scenario {scenario}.")
        else:
            source = Path(path) / f"{optiflow_prefix}{file}"
            if not source.exists():
                continue

        container = gt.Container(system_directory=getattr(results, "_gams_system_directory", None))
        try:
            container.read(str(source.absolute()), symbols=[optiflow_symbol])
        except Exception as error:
            raise Exception(f"Could not read {optiflow_symbol} from the OptiFlow results '{source}': {error}")
        flows = container[optiflow_symbol].records
        if flows is None or flows.empty:
            continue
        flows = flows.set_axis(list(optiflow_columns), axis=1).rename(columns=optiflow_columns)
        flows = flows.astype({column: str for column in flows.columns if column != "value"})
        flows = flows[flows["value"] != 0].assign(scenario=scenario, quantity="flow", value_unit="")
        tables.append(flows)
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


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

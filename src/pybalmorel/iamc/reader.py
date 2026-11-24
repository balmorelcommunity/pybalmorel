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
# derives captured CO2 where the results don't give it. The CO2 tax units pay (ECO_G_YCRAG's
# GENERATION_CO2_TAX) is per unit too; with their emissions it gives the carbon price. 'columns'
# names a symbol's columns where pybalmorel has no format for it, and 'keep' the rows read.
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
    {"quantity": "tax", "symbol": "ECO_G_YCRAG", "commodity": None, "required": False, "renames": {},
     "columns": ["Year", "Country", "Region", "Area", "Generation", "Fuel", "Technology", "Cost category", "Cost",
                 "Unit", "Value"],
     "keep": {"Cost": "GENERATION_CO2_TAX"}, "unit": "Mmoney", "unit_aliases": {"Mmoney"}},
]
# The symbols prices are read from, the commodity they are the price of, the column that says
# where in a country each price holds, and the symbol of the demand there, whose annual sum
# weighs the price when a country has several. Balmorel's AVERAGE price is the mean of the
# hourly marginal prices over the year, not weighted by consumption.
price_symbols = [
    {"symbol": "EL_PRICE_YCR", "commodity": "ELECTRICITY", "place": "Region", "demand": "EL_DEMAND_YCR"},
    {"symbol": "H2_PRICE_YCR", "commodity": "HYDROGEN", "place": "Region", "demand": "H2_DEMAND_YCR"},
    {"symbol": "H_PRICE_YCRA", "commodity": "HEAT", "place": "Area", "demand": "H_DEMAND_YCRA"},
]
price_category = "AVERAGE"
price_unit = "money/MWh"
price_unit_aliases = {"Money_per_MWh"}
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
    captured CO2 (CC_YCRAG), fuel input (F_CONS_YCRA) and CO2 tax (ECO_G_YCRAG) are per unit, with
    no commodity. Prices (EL_PRICE_YCR, H2_PRICE_YCR, H_PRICE_YCRA) are per region or area, with
    the commodity's annual demand there as weight. Where a scenario was linked to OptiFlow,
    OptiFlow's flows between processes (VFLOW_Opti_C) are read too.

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
            'emissions', 'captured', 'input', 'tax', 'price' or 'flow'). Columns a quantity
            doesn't have are ''. 'stated_unit' is the unit the results state where it isn't one
            the Reader expects. Price rows are one per region or area, so a country can have
            several with the same columns; their 'weight' is the demand they hold for, NaN for
            the other quantities.
    """
    tables = []
    # Country of each region and area, for where exchange goes
    countries = {}
    for spec in quantity_symbols:
        symbol = spec["symbol"]
        if not spec["required"] and not any(has_symbol(results, scenario, symbol) for scenario in results.sc):
            continue
        table = results.get_result(symbol, cols=spec.get("columns"))
        if table.empty:
            if spec["required"]:
                raise Exception(f"No scenario has '{symbol}', which IAMC {spec['quantity']} is read from.")
            continue
        for column, kept in spec.get("keep", {}).items():
            table = table[table[column].astype(str) == kept]

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

    prices = read_prices(results)
    if not prices.empty:
        tables.append(prices)
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


def read_prices(results: "MainResults") -> pd.DataFrame:
    """Read Balmorel's average prices per region or area, with the demand they hold for.

    Args:
        results (MainResults): The loaded result files.

    Returns:
        pd.DataFrame: Rows of quantity 'price' with scenario, year, country, area ('' for prices
            per region), commodity, value_unit, stated_unit, value and weight (the commodity's
            annual demand at the same place, summed over demand categories, 0 if negative or
            none); no rows if no scenario has prices.
    """
    tables = []
    for spec in price_symbols:
        if not any(has_symbol(results, scenario, spec["symbol"]) for scenario in results.sc):
            continue
        prices = results.get_result(spec["symbol"])
        if prices.empty:
            continue
        place = ["Scenario", "Year", "Country", spec["place"]]
        prices = prices[prices["Category"].astype(str) == price_category].astype({column: str for column in place})

        weights = pd.DataFrame({column: pd.Series(dtype=str) for column in place})
        if any(has_symbol(results, scenario, spec["demand"]) for scenario in results.sc):
            demand = results.get_result(spec["demand"])
            if not demand.empty:
                weights = demand.astype({column: str for column in place}).groupby(place, as_index=False)["Value"].sum()
        weights = weights.rename(columns={"Value": "weight"})
        prices = prices.merge(weights, on=place, how="left")

        stated = prices["Unit"].astype(str)
        tables.append(pd.DataFrame({
            "scenario": prices["Scenario"],
            "year": prices["Year"],
            "country": prices["Country"],
            "area": prices[spec["place"]] if spec["place"] == "Area" else "",
            "commodity": spec["commodity"],
            "value_unit": price_unit,
            "stated_unit": stated.where(~stated.isin(price_unit_aliases), ""),
            "value": prices["Value"],
            "weight": prices.get("weight", pd.Series(0.0, index=prices.index)).fillna(0.0).clip(lower=0.0),
            "quantity": "price",
        }))
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


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

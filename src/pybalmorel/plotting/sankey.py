"""
Sankey Diagrams

Draws where energy comes from, what it is turned into and where it goes, from MainResults or
from the IAMC data that MainResults.to_iamc makes of them, and both side by side to see where
the IAMC data counts differently. Both sides are classified with the IAMC Mapping Rules, so
their nodes share names (docs/adr/0018).

    flows = sankey_flows(results, 2050, countries='DENMARK')
    fig, ax = plot_sankey(flows)

Created on 26.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pathlib import Path
from typing import TYPE_CHECKING
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch, Polygon, Rectangle
from matplotlib.path import Path as DrawPath

from ..formatting import fuel_colours
from ..iamc.reader import read_mainresults
from ..iamc.rules import (import_unit, load_definitions, load_rules, match_area_kinds, match_mapping_rules,
                          match_optiflow_rules, not_reported, optiflow_unit)

if TYPE_CHECKING:
    from ..classes import MainResults

# Columns of a flow table, and the kinds of flow: what a conversion makes ('flow') or loses
# ('loss'), heat that heat pumps take from their surroundings ('ambient'), and what makes a
# commodity's inflow and outflow add up where the data doesn't say ('unaccounted')
flow_columns = ["From", "To", "Kind", "Value"]
flow_kinds = ("flow", "loss", "ambient", "unaccounted")
# How many of each energy unit make one TWh
units_per_twh = {
    "TWh": 1.0, "TWh/yr": 1.0, "GWh": 1e3, "GWh/yr": 1e3, "MWh": 1e6, "MWh/yr": 1e6,
    "PJ": 3.6, "PJ/yr": 3.6, "TJ": 3.6e3, "TJ/yr": 3.6e3, "GJ": 3.6e6, "GJ/yr": 3.6e6,
    "EJ": 3.6e-3, "EJ/yr": 3.6e-3, "Mtoe": 0.0859845, "Mtoe/yr": 0.0859845, "ktoe": 85.9845, "ktoe/yr": 85.9845,
}
# Node of each Balmorel commodity, and the commodity each carrier fuel is: units burning a
# carrier fuel take it from the commodity's node
commodity_nodes = {"ELECTRICITY": "Electricity", "HEAT": "Heat", "HYDROGEN": "Hydrogen", "BIOMETHANE": "Gases"}
carrier_fuels = {"ELECTRIC": "ELECTRICITY", "HEAT": "HEAT", "HYDROGEN": "HYDROGEN", "BIOMETHANE": "BIOMETHANE"}
# A commodity made in an Area Kind where it isn't reported as output (stems.csv) is On-site Use
on_site_prefix = "On-site "
# Demand categories that are losses, and the OptiFlow add-on's demand
loss_categories = ("DIST_LOSSES", "TRANS_LOSSES")
optiflow_category = "ENDO_OPTIFLOW"
# Units that make more heat than the electricity they take in take the rest from the surroundings
ambient_fuel = "ELECTRIC"
ambient_commodity = "HEAT"
# Node names
imports = "Imports"
exports = "Exports"
losses = "Losses"
unaccounted = "Unaccounted"
ambient_heat = "Ambient Heat"
grid = "Grid"
optiflow_node = "OptiFlow"
final_energy = "Final Energy"
other = "Other"
# Nodes drawn twice: what flows out of them with the sources, what flows into them with the uses
two_sided = (unaccounted, grid)
# Commodities whose residual goes to and from the Grid when areas are chosen, as their demand
# and transmission are per region
grid_commodities = ("Electricity", "Hydrogen")
# IAMC Variables the IAMC side reads, and the first segments of IAMC carriers under Final Energy;
# other segments there are Final Energy Sectors
secondary_energy = "Secondary Energy"
primary_energy = "Primary Energy"
trade_variable = "Trade|Secondary Energy|{} [Volume]"
iamc_carriers = ("Electricity", "Heat", "Hydrogen", "Gases", "Liquids", "Solids", "Solar", "Geothermal", "Waste",
                 other)
iamc_columns = ["Model", "Scenario", "Region", "Variable", "Unit"]
# Smallest value counted, and the share of a node's flow below which its inflow and outflow
# count as equal
noise = 1e-9
relative_tolerance = 1e-6


#%% ------------------------------- ###
###          1. Flow Tables         ###
### ------------------------------- ###

def sankey_flows(data: "MainResults | pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]",
                 year: int,
                 scenario: str | int = 0,
                 countries: str | list[str] | None = None,
                 regions: str | list[str] | None = None,
                 areas: str | list[str] | None = None,
                 unit: str = "TWh",
                 filter: str | None = None,
                 iamc: pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame] | None = None,
                 iamc_scenario: str | int | None = None,
                 rules: dict[str, str | Path | pd.DataFrame] | None = None,
                 optiflow: dict[str, str | Path | None] | None = None,
                 definitions: str | Path | None = None) -> pd.DataFrame:
    """Make the flow table a Sankey diagram draws, from MainResults or from IAMC data.

    From MainResults, sources are units' fuel input by Fuel Category (the Source the Mapping
    Rules give), imports, and the heat heat pumps take from their surroundings. A unit's input
    is split over what it makes in proportion to its output: what it makes flows from the
    Source to the commodity ('flow'), what it loses flows from the Source to the commodity and
    on to Losses ('loss'). Heat made in areas where it isn't centralized heat goes to On-site
    Heat. Final demand goes to its Final Energy Sector, or to Final Energy where it has none;
    transmission to and from places outside the selection to Exports and from Imports, per
    direction. The OptiFlow add-on's demand goes to OptiFlow, and what the OptiFlow Mapping
    reports it giving back flows from OptiFlow. Where a commodity's inflow and outflow don't
    add up, the rest goes to or comes from Unaccounted.

    From IAMC data, Secondary Energy flows from its Source (or the commodity it was made of) to
    its commodity; where Primary Energy by Source and use is reported too, the difference is
    'loss'. Final Energy flows from its carrier's node to its sector, or to Final Energy for
    what no sector holds, and Trade to Exports or from Imports, net. Commodities' residuals go
    to Unaccounted, which shows what the IAMC data leaves out, such as what electrolysers take
    in.

    Args:
        data (MainResults | pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]): Loaded results,
            or IAMC data as MainResults.to_iamc returns it (wide, one column per year, or with
            Year and Value columns).
        year (int): The year.
        scenario (str | int, optional): The scenario, or its position. For IAMC data, the IAMC
            Scenario, or its position in order of appearance. Defaults to 0.
        countries (str | list[str] | None, optional): Countries to cover; Balmorel countries,
            or for IAMC data IAMC Regions too. Defaults to None, all of them.
        regions (str | list[str] | None, optional): Balmorel regions to cover, instead of
            countries. MainResults only. Defaults to None.
        areas (str | list[str] | None, optional): Balmorel areas to cover, instead of countries.
            Electricity and hydrogen demand and transmission are per region, so where these
            areas' electricity and hydrogen come from and go to shows as the Grid. MainResults
            only. Defaults to None.
        unit (str, optional): Energy unit of the values, e.g. 'TWh', 'PJ' or 'EJ/yr'. Defaults
            to 'TWh'.
        filter (str | None, optional): A pandas query on the columns From, To, Kind and Value
            that the flows must meet, e.g. "Kind != 'loss'" to show only what conversions make.
            Losses and Unaccounted are worked out before it applies. Defaults to None.
        iamc (pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame] | None, optional): IAMC data of
            the same results to compare with, as MainResults.to_iamc returns it. With it, the
            table compares the two (see compare_sankey_flows). Countries only. Defaults to None.
        iamc_scenario (str | int | None, optional): The IAMC Scenario to compare with. Defaults
            to None, the Balmorel scenario's name.
        rules (dict[str, str | Path | pd.DataFrame] | None, optional): Rule rows that take
            precedence over the shipped ones, as in to_iamc. Defaults to None.
        optiflow (dict[str, str | Path | None] | None, optional): OptiFlow result file per
            Balmorel scenario, as in to_iamc. Defaults to None.
        definitions (str | Path | None, optional): Folder with your own Definitions Snapshot,
            whose regions name the IAMC Regions of Balmorel countries. Defaults to None.

    Returns:
        pd.DataFrame: Columns From, To, Kind and Value; with `iamc`, From, To, Kind,
            MainResults, IAMC and Difference (IAMC less MainResults).
    """
    if is_iamc(data):
        if iamc is not None:
            raise Exception("Compare with IAMC data by passing MainResults as the data, not IAMC data.")
        if regions is not None or areas is not None:
            raise Exception("IAMC data is per IAMC Region; choose what to cover with countries, not regions or areas.")
        flows = iamc_flows(data, year, scenario, countries, rules, definitions)
        return finish_flows(flows, unit, filter)

    scenario = pick(scenario, list(data.sc), "scenario")
    long = read_mainresults(data, optiflow, by_region=True)
    flows = finish_flows(mainresults_flows(long, year, scenario, countries, regions, areas, rules), unit, filter)
    if iamc is None:
        return flows
    if regions is not None or areas is not None:
        raise Exception("IAMC data is per IAMC Region, so it can only be compared for countries, not regions or areas.")
    compared = sankey_flows(iamc, year, scenario if iamc_scenario is None else iamc_scenario, countries, unit=unit,
                            filter=filter, rules=rules, definitions=definitions)
    return compare_sankey_flows(flows, compared)


def compare_sankey_flows(left: pd.DataFrame, right: pd.DataFrame,
                         names: tuple[str, str] = ("MainResults", "IAMC")) -> pd.DataFrame:
    """Put two flow tables side by side.

    Args:
        left (pd.DataFrame): A flow table (From, To, Kind, Value), e.g. from MainResults.
        right (pd.DataFrame): Another, e.g. from the IAMC data of the same results.
        names (tuple[str, str], optional): Column names of the two tables' values. Defaults to
            ('MainResults', 'IAMC').

    Returns:
        pd.DataFrame: Columns From, To, Kind, the two names and Difference (right less left),
            0 where a table has no such flow.
    """
    keys = ["From", "To", "Kind"]
    both = (left.groupby(keys)["Value"].sum().rename(names[0]).to_frame()
            .join(right.groupby(keys)["Value"].sum().rename(names[1]), how="outer")
            .fillna(0.0).reset_index())
    both["Difference"] = both[names[1]] - both[names[0]]
    return both.sort_values(keys, ignore_index=True)


def finish_flows(flows: pd.DataFrame, unit: str, filter: str | None) -> pd.DataFrame:
    """Convert a flow table from TWh, and keep the flows that meet a filter.

    Args:
        flows (pd.DataFrame): Flow table in TWh.
        unit (str): The energy unit to convert to.
        filter (str | None): A pandas query on From, To, Kind and Value, or None.

    Returns:
        pd.DataFrame: The flow table.
    """
    flows = flows.assign(Value=flows["Value"] * to_twh(unit) ** -1)
    if filter:
        try:
            flows = flows.query(filter)
        except Exception as error:
            raise Exception(f"Could not filter the flows with '{filter}' (a pandas query on From, To, Kind and "
                            f"Value): {error}")
    return flows.reset_index(drop=True)


def to_twh(unit: str) -> float:
    """Factor that converts an energy unit to TWh.

    Args:
        unit (str): The unit, e.g. 'EJ/yr'.

    Returns:
        float: The factor.
    """
    if unit not in units_per_twh:
        raise Exception(f"Unknown energy unit '{unit}'; known ones are {list(units_per_twh)}.")
    return 1 / units_per_twh[unit]


def is_iamc(data: object) -> bool:
    """Whether data is IAMC data rather than loaded results.

    Args:
        data (object): What was passed.

    Returns:
        bool: True for a DataFrame, or the (data, notes) tuple to_iamc returns.
    """
    return isinstance(data, (pd.DataFrame, tuple))


def pick(chosen: str | int, names: list[str], what: str) -> str:
    """Pick a name by itself or by its position.

    Args:
        chosen (str | int): The name, or its position in `names`.
        names (list[str]): The names there are.
        what (str): What the names are, for errors, e.g. 'scenario'.

    Returns:
        str: The name.
    """
    if isinstance(chosen, (int, np.integer)):
        if not -len(names) <= chosen < len(names):
            raise Exception(f"There is no {what} number {chosen}; there are {len(names)}: {names}.")
        return names[chosen]
    if chosen not in names:
        raise Exception(f"There is no {what} '{chosen}'; there are {names}.")
    return chosen


def as_list(names: str | list[str] | None) -> list[str] | None:
    """A name or list of names as a list.

    Args:
        names (str | list[str] | None): One name, several, or None.

    Returns:
        list[str] | None: The names, or None.
    """
    return [names] if isinstance(names, str) else (list(names) if names is not None else None)


def tidy(links: list[tuple[str, str, str, float]] | pd.DataFrame) -> pd.DataFrame:
    """Sum links with the same ends and kind, and turn negative ones around.

    Args:
        links (list[tuple[str, str, str, float]] | pd.DataFrame): Links (From, To, Kind, Value)
            in TWh.

    Returns:
        pd.DataFrame: The flow table, without links below noise.
    """
    links = pd.DataFrame(links, columns=flow_columns) if isinstance(links, list) else links[flow_columns]
    links = links.groupby(["From", "To", "Kind"], as_index=False)["Value"].sum()
    turned = links["Value"] < 0
    links.loc[turned, ["From", "To"]] = links.loc[turned, ["To", "From"]].to_numpy()
    links["Value"] = links["Value"].abs()
    links = links.groupby(["From", "To", "Kind"], as_index=False)["Value"].sum()
    return links[links["Value"] >= noise].sort_values(["From", "To", "Kind"], ignore_index=True)


def balance(links: list[tuple[str, str, str, float]], nodes: set[str],
            other_end: dict[str, str] | None = None) -> None:
    """Send what each node's inflow and outflow don't account for to or from Unaccounted.

    Args:
        links (list[tuple[str, str, str, float]]): Links (From, To, Kind, Value), appended to.
        nodes (set[str]): The nodes to balance.
        other_end (dict[str, str] | None, optional): Nodes whose rest goes to or comes from
            another node than Unaccounted, as a 'flow'. Defaults to None.
    """
    table = pd.DataFrame(links, columns=flow_columns)
    inflow = table.groupby("To")["Value"].sum()
    outflow = table.groupby("From")["Value"].sum()
    for node in sorted(nodes):
        into, out_of = inflow.get(node, 0.0), outflow.get(node, 0.0)
        rest = into - out_of
        if abs(rest) < max(noise, relative_tolerance * max(abs(into), abs(out_of))):
            continue
        end = (other_end or {}).get(node, unaccounted)
        kind = "unaccounted" if end == unaccounted else "flow"
        links.append((node, end, kind, rest) if rest > 0 else (end, node, kind, -rest))


#%% ------------------------------- ###
###          2. MainResults         ###
### ------------------------------- ###

def mainresults_flows(long: pd.DataFrame,
                      year: int,
                      scenario: str,
                      countries: str | list[str] | None = None,
                      regions: str | list[str] | None = None,
                      areas: str | list[str] | None = None,
                      rules: dict[str, str | Path | pd.DataFrame] | None = None) -> pd.DataFrame:
    """Make the flow table of one scenario and year from the Reader's long table.

    Args:
        long (pd.DataFrame): The long table of read_mainresults with by_region=True.
        year (int): The year.
        scenario (str): The scenario.
        countries (str | list[str] | None, optional): Balmorel countries to cover. Defaults to
            None, all of them.
        regions (str | list[str] | None, optional): Balmorel regions to cover. Defaults to None.
        areas (str | list[str] | None, optional): Balmorel areas to cover. Defaults to None.
        rules (dict[str, str | Path | pd.DataFrame] | None, optional): Rule rows that take
            precedence over the shipped ones. Defaults to None.

    Returns:
        pd.DataFrame: The flow table (From, To, Kind, Value) in TWh.
    """
    chosen = {"country": as_list(countries), "region": as_list(regions), "area": as_list(areas)}
    chosen = {level: names for level, names in chosen.items() if names is not None}
    if len(chosen) > 1:
        raise Exception(f"Choose countries, regions or areas, not {' and '.join(chosen)}.")
    level, names = next(iter(chosen.items())) if chosen else ("country", None)

    tables = load_rules(rules)
    rows = long[(long["scenario"] == scenario) & (long["year"].astype(str) == str(year))]
    if rows.empty:
        years = sorted(long.loc[long["scenario"] == scenario, "year"].unique())
        raise Exception(f"Scenario {scenario} has no results for {year}; it has {years}.")
    rows = rows.assign(**{column: rows[column].fillna("").astype(str) for column in rows.columns
                          if column not in ("value", "weight")})
    for column in ("balmorel_region", "to_balmorel_region"):
        if column not in rows.columns:
            raise Exception("The long table has no regions; read it with read_mainresults(..., by_region=True).")
    rows = rows[rows["quantity"] != "flow"].assign(value=rows["value"] * rows["value_unit"].map(
        lambda unit: to_twh(unit) if unit in units_per_twh else np.nan)).pipe(
        lambda table: pd.concat([table, long_flows(long, scenario, year)], ignore_index=True))

    area_rows = rows[(rows["area"] != "") & (rows["balmorel_region"] != "")].drop_duplicates("area")
    area_places = {"region": area_rows.set_index("area")["balmorel_region"],
                   "country": rows[rows["area"] != ""].drop_duplicates("area").set_index("area")["country"]}
    if names is not None:
        known = set(place_of(rows, level, area_places)) | set(place_of(rows, level, area_places, to=True))
        unknown = [name for name in names if name not in known]
        if unknown:
            raise Exception(f"Scenario {scenario} has no {level} {unknown} in {year}.")
    inside = pd.Series(True, index=rows.index) if names is None else place_of(rows, level, area_places).isin(names)
    rows = rows.assign(inside=inside, area_kind="")
    with_area = rows["area"] != ""
    rows.loc[with_area, "area_kind"] = match_area_kinds(rows.loc[with_area, "area"], tables["areas"])

    stems = tables["stems"]
    output_kinds = stems[stems["quantity"] == "output"].groupby("commodity")["area_kind"].agg(set).to_dict()
    final_sectors = stems[(stems["quantity"] == "final") & (stems["sector"] != "")].set_index(
        ["commodity", "area_kind"])["sector"].map(lambda sector: sector.split("|")[0]).to_dict()

    def node_of(commodity: str, area_kind: str) -> str:
        name = commodity_nodes.get(commodity, commodity.capitalize())
        kinds = output_kinds.get(commodity)
        if kinds is None or area_kind == "" or "" in kinds or area_kind in kinds:
            return name
        return on_site_prefix + name

    links = []
    nodes = set()
    unit_links(rows[rows["inside"]], tables, node_of, links, nodes)
    demand_links(rows[rows["inside"]], tables, node_of, final_sectors, level == "area", links, nodes)
    if level != "area":
        transmission_links(rows, level, names, area_places, node_of, links, nodes)
    heat_exchange_links(rows, level, names, area_places, tables, node_of, links, nodes)
    if level == "country":
        optiflow_links(rows[rows["inside"]], tables, links)
    other_end = {node: grid for node in grid_commodities} if level == "area" else None
    balance(links, nodes, other_end)
    return tidy(links)


def long_flows(long: pd.DataFrame, scenario: str, year: int) -> pd.DataFrame:
    """OptiFlow's flows of one scenario and year, as they are in the long table.

    Args:
        long (pd.DataFrame): The long table.
        scenario (str): The scenario.
        year (int): The year.

    Returns:
        pd.DataFrame: The rows of quantity 'flow'.
    """
    flows = long[(long["quantity"] == "flow") & (long["scenario"] == scenario) & (long["year"].astype(str) == str(year))]
    return flows.assign(**{column: flows[column].fillna("").astype(str) for column in flows.columns
                           if column not in ("value", "weight")})


def place_of(rows: pd.DataFrame, level: str, area_places: dict[str, pd.Series], to: bool = False) -> pd.Series:
    """Where each row is, or where its exchange goes, at a level.

    Args:
        rows (pd.DataFrame): Rows of the long table.
        level (str): 'country', 'region' or 'area'.
        area_places (dict[str, pd.Series]): Region and country of each area.
        to (bool, optional): Where exchange goes, instead of where the row is. Defaults to False.

    Returns:
        pd.Series: The country, region or area per row; '' where unknown.
    """
    area = rows["to_area" if to else "area"]
    if level == "area":
        return area
    column = {"country": "to_country" if to else "country", "region": "to_balmorel_region" if to else "balmorel_region"}
    place = rows[column[level]].replace("", np.nan).fillna(area.map(area_places[level]))
    if to and level == "country":
        place = place.fillna(rows["country"])
    return place.fillna("")


def unit_links(rows: pd.DataFrame, tables: dict[str, pd.DataFrame], node_of, links: list, nodes: set) -> None:
    """Links of what units take in and make.

    A unit's input is split over the commodities it makes in proportion to its output. For each
    commodity, what it makes flows from its Source; what its share of the input exceeds that by
    is lost, and what it falls short of comes from the surroundings (heat pumps) or Unaccounted.
    Units that make what they take in (storage) only lose. Import units' output comes from
    Imports; units whose Mapping Rule says 'optiflow' are left out.

    Args:
        rows (pd.DataFrame): Rows of the long table in the selection, with 'area_kind'.
        tables (dict[str, pd.DataFrame]): The rule tables.
        node_of (Callable[[str, str], str]): Node of a commodity in an Area Kind.
        links (list): Links (From, To, Kind, Value), appended to.
        nodes (set): Commodity nodes to balance, added to.
    """
    keys = ["country", "balmorel_region", "area", "area_kind", "unit_name", "tech_type", "fuel"]
    made = rows[rows["quantity"] == "output"].groupby(keys + ["commodity"], as_index=False)["value"].sum()
    taken = rows[rows["quantity"] == "input"].groupby(keys, as_index=False)["value"].sum()
    if made.empty:
        return
    made["template"] = match_mapping_rules(made, tables["mapping"])
    categories = tables["fuels"].set_index("fuel")["category"].to_dict()

    # Input of units without output, other than import and OptiFlow units, is lost
    orphans = taken.merge(made[keys].drop_duplicates(), on=keys, how="left", indicator=True)
    orphans = orphans[orphans["_merge"] == "left_only"].assign(commodity="")
    if not orphans.empty:
        orphans["template"] = match_mapping_rules(orphans, tables["mapping"])
        for row in orphans[~orphans["template"].isin([import_unit, optiflow_unit])].itertuples():
            links.append((source_of(row.fuel, row.template, row.area_kind, categories, node_of), losses, "loss",
                          row.value))

    for row in made[made["template"] == import_unit].itertuples():
        node = node_of(row.commodity, row.area_kind)
        links.append((imports, node, "flow", row.value))
        nodes.add(node)
    made = made[~made["template"].isin([import_unit, optiflow_unit])]
    if taken.empty:
        print("Warning: the results have no fuel input (F_CONS_YCRA); the Sankey counts units' input as equal "
              "to their output, so it shows no conversion losses.")
        made = made.assign(input=made["value"])
    else:
        made = made.merge(taken.rename(columns={"value": "unit_input"}), on=keys, how="left")
        share = made["value"] / made.groupby(keys)["value"].transform("sum").where(lambda total: total != 0)
        made["input"] = made["unit_input"].fillna(0.0) * share.fillna(0.0)

    # Losses are netted per link, as the IAMC data nets them per Source and commodity
    made["node"] = [node_of(commodity, kind) for commodity, kind in zip(made["commodity"], made["area_kind"])]
    made["source"] = [source_of(fuel, template, kind, categories, node_of)
                      for fuel, template, kind in zip(made["fuel"], made["template"], made["area_kind"])]
    made["ambient"] = (made["fuel"] == ambient_fuel) & (made["commodity"] == ambient_commodity)
    nodes.update(made["node"])
    nodes.update(made.loc[made["fuel"].isin(list(carrier_fuels)), "source"])
    pairs = made.groupby(["source", "node", "ambient"], as_index=False)[["value", "input"]].sum()
    for row in pairs.itertuples():
        if row.source == row.node:
            # Storage: only what it loses, or makes beyond what it took in
            rest = row.input - row.value
            links.append((row.node, losses, "loss", rest) if rest > 0
                         else (unaccounted, row.node, "unaccounted", -rest))
            continue
        links.append((row.source, row.node, "flow", min(row.input, row.value)))
        if row.input > row.value:
            links.append((row.source, row.node, "loss", row.input - row.value))
            links.append((row.node, losses, "loss", row.input - row.value))
        elif row.value > row.input:
            links.append((ambient_heat, row.node, "ambient", row.value - row.input) if row.ambient
                         else (unaccounted, row.node, "unaccounted", row.value - row.input))


def source_of(fuel: str, template: str, area_kind: str, categories: dict[str, str], node_of) -> str:
    """The node a unit's fuel comes from.

    Args:
        fuel (str): The Balmorel fuel.
        template (str): The segments template of the unit's Mapping Rule, '' if none matches.
        area_kind (str): The Area Kind of the unit's area.
        categories (dict[str, str]): Fuel Category per fuel.
        node_of (Callable[[str, str], str]): Node of a commodity in an Area Kind.

    Returns:
        str: The commodity node of a carrier fuel, else the Source: the first segment of the
            template, with the Fuel Category filled in, or the Fuel Category itself where the
            rule reports nothing.
    """
    if fuel in carrier_fuels:
        return node_of(carrier_fuels[fuel], area_kind)
    category = categories.get(fuel) or other
    if template and template not in (not_reported, import_unit, optiflow_unit):
        return template.split("|")[0].replace("{category}", category)
    return category


def demand_links(rows: pd.DataFrame, tables: dict[str, pd.DataFrame], node_of, final_sectors: dict,
                 areas_only: bool, links: list, nodes: set) -> None:
    """Links of demand: final demand to its sector, losses to Losses, OptiFlow's to OptiFlow.

    Other categories, such as what storage, electrolysers or heat units take, are left out, as
    units' input gives them.

    Args:
        rows (pd.DataFrame): Rows of the long table in the selection, with 'area_kind'.
        tables (dict[str, pd.DataFrame]): The rule tables.
        node_of (Callable[[str, str], str]): Node of a commodity in an Area Kind.
        final_sectors (dict): Final Energy Sector of on-site use per (commodity, Area Kind).
        areas_only (bool): Leave out demand per region, as areas are chosen.
        links (list): Links (From, To, Kind, Value), appended to.
        nodes (set): Commodity nodes to balance, added to.
    """
    demand = rows[rows["quantity"] == "demand"]
    if areas_only:
        demand = demand[demand["area"] != ""]
    categories = tables["demand_categories"].set_index(["commodity", "demand_category"])
    demand = demand.groupby(["commodity", "demand_category", "area_kind"], as_index=False)["value"].sum()
    for row in demand.itertuples():
        node = node_of(row.commodity, row.area_kind)
        nodes.add(node)
        if row.demand_category in loss_categories:
            links.append((node, losses, "loss", row.value))
        elif row.demand_category == optiflow_category:
            links.append((node, optiflow_node, "flow", row.value))
        elif (row.commodity, row.demand_category) in categories.index:
            rule = categories.loc[(row.commodity, row.demand_category)]
            if rule["final"] != "yes":
                continue
            sector = rule["sector"].split("|")[0] if rule["sector"] else ""
            if not sector and node.startswith(on_site_prefix):
                sector = final_sectors.get((row.commodity, row.area_kind), "")
            links.append((node, sector or final_energy, "flow", row.value))


def transmission_links(rows: pd.DataFrame, level: str, names: list[str] | None, area_places: dict[str, pd.Series],
                       node_of, links: list, nodes: set) -> None:
    """Links of electricity and hydrogen transmission into and out of the selection, per direction.

    Args:
        rows (pd.DataFrame): Rows of the long table, with 'inside'.
        level (str): 'country' or 'region'.
        names (list[str] | None): The countries or regions chosen; None for all.
        area_places (dict[str, pd.Series]): Region and country of each area.
        node_of (Callable[[str, str], str]): Node of a commodity in an Area Kind.
        links (list): Links (From, To, Kind, Value), appended to.
        nodes (set): Commodity nodes to balance, added to.
    """
    if names is None:
        return
    sent = rows[(rows["quantity"] == "exchange") & (rows["commodity"] != ambient_commodity)]
    goes_inside = place_of(sent, level, area_places, to=True).isin(names)
    for row, inside, to_inside in zip(sent.itertuples(), sent["inside"], goes_inside):
        node = node_of(row.commodity, "")
        if inside and not to_inside:
            links.append((node, exports, "flow", row.value))
            nodes.add(node)
        elif to_inside and not inside:
            links.append((imports, node, "flow", row.value))
            nodes.add(node)


def heat_exchange_links(rows: pd.DataFrame, level: str, names: list[str] | None, area_places: dict[str, pd.Series],
                        tables: dict[str, pd.DataFrame], node_of, links: list, nodes: set) -> None:
    """Links of heat exchange between areas: between On-site Heat and Heat within the selection,
    else into and out of it.

    Args:
        rows (pd.DataFrame): Rows of the long table, with 'inside' and 'area_kind'.
        level (str): 'country', 'region' or 'area'.
        names (list[str] | None): The places chosen; None for all.
        area_places (dict[str, pd.Series]): Region and country of each area.
        tables (dict[str, pd.DataFrame]): The rule tables.
        node_of (Callable[[str, str], str]): Node of a commodity in an Area Kind.
        links (list): Links (From, To, Kind, Value), appended to.
        nodes (set): Commodity nodes to balance, added to.
    """
    sent = rows[(rows["quantity"] == "exchange") & (rows["commodity"] == ambient_commodity)]
    if sent.empty:
        return
    goes_inside = (pd.Series(True, index=sent.index) if names is None
                   else place_of(sent, level, area_places, to=True).isin(names))
    to_kinds = match_area_kinds(sent["to_area"], tables["areas"])
    for row, inside, to_inside, to_kind in zip(sent.itertuples(), sent["inside"], goes_inside, to_kinds):
        sender, receiver = node_of(row.commodity, row.area_kind), node_of(row.commodity, to_kind)
        if inside and to_inside:
            if sender != receiver:
                links.append((sender, receiver, "flow", row.value))
                nodes.update((sender, receiver))
        elif inside:
            links.append((sender, exports, "flow", row.value))
            nodes.add(sender)
        elif to_inside:
            links.append((imports, receiver, "flow", row.value))
            nodes.add(receiver)


def optiflow_links(rows: pd.DataFrame, tables: dict[str, pd.DataFrame], links: list) -> None:
    """Links of what the OptiFlow Mapping's 'report' rules say OptiFlow takes from Sources
    (Primary Energy) and gives to Balmorel's commodities (Secondary Energy) or to final use
    (Final Energy).

    OptiFlow's demand on a commodity (ENDO_OPTIFLOW) is net of what it gives back, so what it
    gives back is added to it. Each flow is drawn once under each of Primary, Secondary and
    Final Energy at most, by the least detailed row that reports it there, as rows for e.g.
    'Final Energy|Bunkers' and 'Final Energy|Bunkers|Liquids' match the same flows.

    Args:
        rows (pd.DataFrame): Rows of the long table in the selection.
        tables (dict[str, pd.DataFrame]): The rule tables.
        links (list): Links (From, To, Kind, Value), appended to.
    """
    flows = rows[rows["quantity"] == "flow"]
    if flows.empty:
        return
    flows = flows[["from_process", "to_process", "flow", "value"]].assign(flow_row=np.arange(len(flows)))
    matched = match_optiflow_rules(flows, tables["optiflow"])
    matched = matched[(matched["role"] == "report") & matched["variable"].str.match(
        f"({primary_energy}|{secondary_energy}|{final_energy})\\|")]
    matched = matched.assign(level=matched["variable"].str.split("|").str[0],
                             depth=matched["variable"].str.count(r"\|"))
    matched = matched.sort_values("depth", kind="stable").drop_duplicates(["flow_row", "level"])
    sectors = {rule.split("|")[0] for rule in tables["optiflow"]["sector"] if rule}
    for row in matched.itertuples():
        if row.value_unit not in units_per_twh:
            print(f"Warning: the OptiFlow Mapping reports {row.variable} in '{row.value_unit}', not an energy "
                  "unit; left out of the Sankey.")
            continue
        value = row.value * to_twh(row.value_unit)
        segments = row.variable.split("|")
        if segments[0] == primary_energy:
            links.append((segments[1], optiflow_node, "flow", value))
        elif segments[0] == secondary_energy:
            links.append((optiflow_node, segments[1], "flow", value))
            links.append((segments[1], optiflow_node, "flow", value))
        elif row.sector:
            links.append((optiflow_node, row.sector.split("|")[0], "flow", value))
        else:
            sector = segments[1] if segments[1] in sectors or segments[1] not in iamc_carriers else final_energy
            links.append((optiflow_node, sector, "flow", value))


#%% ------------------------------- ###
###            3. IAMC Data         ###
### ------------------------------- ###

def iamc_flows(data: pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame],
               year: int,
               scenario: str | int = 0,
               countries: str | list[str] | None = None,
               rules: dict[str, str | Path | pd.DataFrame] | None = None,
               definitions: str | Path | None = None) -> pd.DataFrame:
    """Make the flow table of one IAMC Scenario and year from IAMC data.

    Args:
        data (pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]): IAMC data, wide or with Year
            and Value columns, or the (data, notes) tuple to_iamc returns.
        year (int): The year.
        scenario (str | int, optional): The IAMC Scenario, or its position. Defaults to 0.
        countries (str | list[str] | None, optional): IAMC Regions or Balmorel countries to sum
            over. Defaults to None, all regions in the data.
        rules (dict[str, str | Path | pd.DataFrame] | None, optional): Rule rows that take
            precedence over the shipped ones. Defaults to None.
        definitions (str | Path | None, optional): Folder with your own Definitions Snapshot.
            Defaults to None.

    Returns:
        pd.DataFrame: The flow table (From, To, Kind, Value) in TWh.
    """
    tables = load_rules(rules)
    values = iamc_values(data, year, scenario, as_list(countries), tables, definitions)
    aggregates = set(tables["aggregates"]["aggregate"])
    groups = {aggregate for aggregate in aggregates if "|" not in aggregate}

    made = first_levels(values, secondary_energy)
    used = first_levels(values, primary_energy)
    # Carriers that Primary Energy is reported by use for are nodes too, e.g. Liquids where
    # 'Primary Energy|Biomass|Liquids' counts what biofuel plants take in
    commodities = (set(commodity_nodes.values()) | {commodity for commodity, _ in made}
                   | {use for _, use in used if use in iamc_carriers and use != other})
    links = []
    for (commodity, source), amount in made.items():
        if source in groups:
            continue
        spent = used.get((source, commodity))
        if source in commodities or spent is None:
            links.append((source, commodity, "flow", amount))
            continue
        links.append((source, commodity, "flow", min(amount, spent)))
        if spent > amount:
            links.append((source, commodity, "loss", spent - amount))
            links.append((commodity, losses, "loss", spent - amount))
        elif amount > spent:
            links.append((unaccounted, commodity, "unaccounted", amount - spent))
    for (source, commodity), spent in used.items():
        if commodity in commodities and source not in groups and (commodity, source) not in made:
            links.append((source, commodity, "flow", spent))

    for commodity in sorted(commodities):
        net_exports = values.get(trade_variable.format(commodity), 0.0)
        if net_exports > 0:
            links.append((commodity, exports, "flow", net_exports))
        elif net_exports < 0:
            links.append((imports, commodity, "flow", -net_exports))

    fed = {}
    for start, end, kind, value in links:
        if kind == "flow" and end in commodities:
            fed[(start, end)] = fed.get((start, end), 0.0) + value
    links += final_energy_links(values, tables, commodities, aggregates, fed)
    balance(links, {node for link in links for node in link[:2] if node in commodities})
    return tidy(links)


def iamc_values(data: pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame], year: int, scenario: str | int,
                countries: list[str] | None, tables: dict[str, pd.DataFrame],
                definitions: str | Path | None) -> pd.Series:
    """The energy values of one IAMC Scenario and year, summed over the regions chosen, in TWh.

    Args:
        data (pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]): IAMC data, wide or with Year
            and Value columns, or the (data, notes) tuple to_iamc returns.
        year (int): The year.
        scenario (str | int): The IAMC Scenario, or its position.
        countries (list[str] | None): IAMC Regions or Balmorel countries; None for all.
        tables (dict[str, pd.DataFrame]): The rule tables.
        definitions (str | Path | None): Folder with your own Definitions Snapshot.

    Returns:
        pd.Series: Values by IAMC Variable; Variables in other than energy units are left out.
    """
    if isinstance(data, tuple):
        data = data[0]
    data = data.rename(columns={column: column.capitalize() for column in data.columns
                                if isinstance(column, str) and column.lower() in
                                {"model", "scenario", "region", "variable", "unit", "year", "value"}})
    missing = [column for column in iamc_columns if column not in data.columns]
    if missing:
        raise Exception(f"The IAMC data has no column {missing}; it needs {iamc_columns} and one column per year, "
                        "or Year and Value.")
    models = list(data["Model"].unique())
    if len(models) > 1:
        raise Exception(f"The IAMC data has several Models ({models}); pass the rows of one.")
    scenario = pick(scenario, list(data["Scenario"].unique()), "IAMC Scenario")
    data = data[data["Scenario"] == scenario]

    if "Year" in data.columns and "Value" in data.columns:
        data = data[data["Year"].astype(str) == str(year)].assign(value=data["Value"])
    else:
        columns = [column for column in data.columns if str(column) == str(year)]
        if not columns:
            years = [column for column in data.columns if column not in iamc_columns]
            raise Exception(f"IAMC Scenario {scenario} has no values for {year}; it has {years}.")
        data = data.assign(value=data[columns[0]])

    if countries is not None:
        present = set(data["Region"])
        _, regions = load_definitions(definitions)
        iso3 = tables["countries"].set_index("country")["iso3"]
        region_by_iso3 = regions.drop_duplicates("iso3").set_index("iso3")["region"]
        chosen = [name if name in present else region_by_iso3.get(iso3.get(name, ""), name) for name in countries]
        unknown = [name for name, region in zip(countries, chosen) if region not in present]
        if unknown:
            raise Exception(f"IAMC Scenario {scenario} has no IAMC Region for {unknown}; it has {sorted(present)}.")
        data = data[data["Region"].isin(chosen)]

    data = data[data["Unit"].isin(list(units_per_twh)) & data["value"].notna()]
    values = data["value"].astype(float) * data["Unit"].map(to_twh)
    return values.groupby(data["Variable"]).sum()


def first_levels(values: pd.Series, top: str) -> dict[tuple[str, str], float]:
    """Values of the IAMC Variables two levels below a top, e.g. 'Secondary Energy|Heat|Gas'.

    Where that variable isn't reported, its children at the highest level they are are summed.

    Args:
        values (pd.Series): Values by IAMC Variable.
        top (str): The top, e.g. 'Secondary Energy'.

    Returns:
        dict[tuple[str, str], float]: Value per pair of the segments below the top.
    """
    found = {}
    for variable, value in values.items():
        segments = variable.split("|")
        if segments[0] != top or len(segments) < 3:
            continue
        key = (segments[1], segments[2])
        depth = len(segments)
        if key not in found or depth < found[key][0]:
            found[key] = (depth, value)
        elif depth == found[key][0]:
            found[key] = (depth, found[key][1] + value)
    return {key: value for key, (_, value) in found.items()}


def final_energy_links(values: pd.Series, tables: dict[str, pd.DataFrame], commodities: set[str],
                       aggregates: set[str], fed: dict[tuple[str, str], float]) -> list[tuple[str, str, str, float]]:
    """Links of Final Energy: from each carrier's node to its sector, or to Final Energy for what
    no sector holds.

    A carrier's node is its Source, e.g. Gas for 'Gases|Gas', or, as far as that Source feeds
    the commodity it sits below, that commodity: 'Gases|Biomass' (biomethane) comes from Gases
    up to what Biomass flows into Gases, so its biomass doesn't count twice, and from Biomass
    beyond that, as fuel that is Primary Energy where it is used. Only the most detailed
    carriers count, not those with children or aggregates. A sector's Other, and sub-sectors
    (e.g. 'Final Energy|Carbon Management|Carbon Capture and Storage|...'), are left out.

    Args:
        values (pd.Series): Values by IAMC Variable.
        tables (dict[str, pd.DataFrame]): The rule tables.
        commodities (set[str]): Commodity nodes.
        aggregates (set[str]): Names in the 'aggregates' table.
        fed (dict[tuple[str, str], float]): What the data shows each Source flowing into each
            commodity, by (Source, commodity).

    Returns:
        list[tuple[str, str, str, float]]: The links.
    """
    fuels = tables["fuels"]
    carried = fuels[fuels["carrier"] != ""].drop_duplicates("carrier").set_index("carrier")["category"].to_dict()
    mapping = tables["mapping"]
    for carrier, template in mapping.loc[mapping["carrier"] != "", ["carrier", "segments"]].itertuples(index=False):
        if "{" not in template.split("|")[0]:
            carried.setdefault(carrier, template.split("|")[0])
    sources = set(fuels["category"]) | {other}
    roots = set(iamc_carriers) | {carrier.split("|")[0] for carrier in carried} | commodities

    left = dict(fed)

    def drawn(carrier: str, end: str, value: float) -> list[tuple[str, str, str, float]]:
        if carrier in commodities:
            return [(carrier, end, "flow", value)]
        last = carrier.split("|")[-1]
        source = carried.get(carrier, last if last in sources else other)
        root = carrier.split("|")[0]
        via = min(max(value, 0.0), left.get((source, root), 0.0))
        left[(source, root)] = left.get((source, root), 0.0) - via
        return [(root, end, "flow", via), (source, end, "flow", value - via)]

    def leaves(names: set[str]) -> set[str]:
        return {name for name in names
                if not any(child.startswith(f"{name}|") for child in names)
                and not any(name == aggregate or name.endswith(f"|{aggregate}") for aggregate in aggregates)}

    by_sector = {}
    for variable, value in values.items():
        segments = variable.split("|")
        if segments[0] != final_energy or len(segments) < 2:
            continue
        if segments[1] in roots:
            by_sector.setdefault("", {})["|".join(segments[1:])] = value
        elif len(segments) >= 3 and segments[2] in roots:
            by_sector.setdefault(segments[1], {})["|".join(segments[2:])] = value

    links = []
    in_sectors = {}
    for sector, carriers in by_sector.items():
        if not sector:
            continue
        for carrier in leaves(set(carriers)):
            if carrier == other:
                continue
            links += drawn(carrier, sector, carriers[carrier])
            in_sectors[carrier] = in_sectors.get(carrier, 0.0) + carriers[carrier]
    unsectored = by_sector.get("", {})
    for carrier in leaves(set(unsectored)):
        rest = unsectored[carrier] - in_sectors.get(carrier, 0.0)
        if rest > noise:
            links += drawn(carrier, final_energy, rest)
    return links


#%% ------------------------------- ###
###          4. Drawing             ###
### ------------------------------- ###

# Node colours: the package's fuel colours where there is one, with Hydrogen and Other darker
# than those, which links would not show against white
node_colours = {
    imports: fuel_colours["IMPORT"], exports: fuel_colours["IMPORT"], "Coal": fuel_colours["COAL"],
    "Gas": fuel_colours["NATGAS"], "Oil": fuel_colours["OIL"], "Nuclear": fuel_colours["NUCLEAR"],
    "Biomass": fuel_colours["BIOMASS"], "Hydro": fuel_colours["WATER"], "Wind": fuel_colours["WIND"],
    "Solar": fuel_colours["SOLAR"], "Electricity": fuel_colours["ELECTRIC"], "Heat": fuel_colours["HEAT"],
    "Gases": fuel_colours["BIOGAS"], "Liquids": "#b07d1a", "Hydrogen": "#9a9fd6", on_site_prefix + "Heat": "#6fbf73",
    "Geothermal": "#a0522d", "Ocean": "#1f78b4", ambient_heat: "#f4a261", optiflow_node: "#8e6bbf",
    other: "#9e9e9e", grid: "#7f7f7f", losses: "#c4c4c4", unaccounted: "#9b9b9b",
}
# Styles: background, text, colours of final uses without one of their own and of grey links, how
# opaque links are, and node colours. The dark style lightens the fuel colours that would fall
# below 3:1 contrast against its background, keeping their hue.
styles = {
    "light": {"background": "#ffffff", "text": "#333333", "sink": "#5b6770", "grey": "#c4c4c4", "alpha": 0.5,
              "nodes": node_colours},
    "dark": {"background": "#191919", "text": "#e6e6e6", "sink": "#9aa5ae", "grey": "#c4c4c4", "alpha": 0.55,
             "nodes": node_colours | {"Coal": "#717171", "Gas": "#b63d3f", "Oil": "#97655b", "Biomass": "#2a7d78",
                                      "Electricity": "#ec483f"}},
}
# Vertical order of sources and of final uses; names not listed go before Other and Final
# Energy. Commodities are ordered to cross the fewest links, ties in this order.
source_order = [imports, "Coal", "Gas", "Oil", "Nuclear", "Biomass", "Hydro", "Wind", "Solar", "Geothermal",
                "Ocean", ambient_heat, other, unaccounted, grid]
sink_order = ["Residential and Commercial", "Industry", "Transportation", "Carbon Management", "Bunkers",
              final_energy, optiflow_node, exports, losses, unaccounted, grid]
inner_order = ["Electricity", "Hydrogen", "Gases", "Heat", on_site_prefix + "Heat", optiflow_node]
# Geometry, in column spacings (x) and shares of the tallest column (y)
node_width = 0.04
gap_share = 0.04
loop_offset = 0.06
side_marker = "\x00"


def plot_sankey(flows: pd.DataFrame,
                unit: str | None = None,
                title: str | None = None,
                min_share: float = 1e-3,
                figsize: tuple[float, float] | None = None,
                label_size: float = 8,
                dark: bool = False) -> tuple[Figure, Axes | np.ndarray]:
    """Draw a Sankey diagram of a flow table, one panel per value column.

    Sources are on the left and final uses on the right, commodities in between: a commodity's
    inflow is what went into making it, and its outflow where it went. Links take the colour of
    the node they leave; links to Losses and to and from Unaccounted are grey. Flows that go
    back to a commodity further left loop below the diagram. Panels share one scale, so the
    same height is the same amount in each.

    The dark style draws on a near-black background with light text, and lightens the dark fuel
    colours (Coal, Gas, Oil, Biomass and Electricity) so they stand out from it.

    Args:
        flows (pd.DataFrame): Columns From and To and the values: Value, or several value
            columns (e.g. MainResults and IAMC from sankey_flows with iamc=), each drawn in a
            panel of its own. Kind and Difference are not drawn.
        unit (str | None, optional): Unit of the values, for the labels. Defaults to None.
        title (str | None, optional): Title of the figure. Defaults to None.
        min_share (float, optional): Links smaller than this share of the largest node in any
            panel are not drawn, so panels leave out the same links. Defaults to 1e-3.
        figsize (tuple[float, float] | None, optional): Figure size in inches. Defaults to None,
            11 by 6 inches per panel.
        label_size (float, optional): Font size of the node labels. Defaults to 8.
        dark (bool, optional): Draw in the dark style. Defaults to False.

    Returns:
        tuple[Figure, Axes | np.ndarray]: The figure, and its axes, or an array of them where
            there are several panels.
    """
    style = styles["dark" if dark else "light"]
    names = value_columns(flows)
    panels = panels_of(flows, names, min_share)
    if all(panel.empty for panel in panels):
        raise Exception("There are no flows to draw: every value is zero or below min_share of the largest node.")
    columns, order = arrange(panels)
    n_columns = max(columns.values()) + 1
    sizes = [node_sizes(panel) for panel in panels]
    gap = gap_share * max(column_heights(size, columns).max() for size in sizes if size)
    placed = [place(size, columns, order, gap) for size in sizes]
    loops = [panel[[columns[end] <= columns[start] for start, end in zip(panel["From"], panel["To"])]]
             for panel in panels]
    extent = max(top + size for nodes in placed for _, top, size in nodes.values())
    bottom = extent + gap + max(loop_depth(loop, gap) for loop in loops)
    top = -gap

    figure, axes = plt.subplots(1, len(names), figsize=figsize or (11 * len(names), 6), squeeze=False,
                                facecolor=style["background"])
    axes = axes[0]
    figure.subplots_adjust(left=0.01, right=0.99, top=0.9 if title and len(names) > 1 else 0.93, bottom=0.02,
                           wspace=0.04)
    side_inches = [max([len(label_text(node, size, unit)) for nodes in placed
                        for node, (column, _, size) in nodes.items() if column == side] + [0]) * 0.55 * label_size / 72
                   for side in (0, n_columns - 1)]
    for axis, panel, nodes, loop, name in zip(axes, panels, placed, loops, names):
        box = axis.get_position()
        width_inches = box.width * figure.get_figwidth()
        content = n_columns - 1 + node_width
        per_inch = content / max(width_inches - sum(side_inches), 1e-3)
        left, right = (inches * per_inch for inches in side_inches)
        axis.set_xlim(-left, content + right)
        axis.set_ylim(bottom, top)
        axis.axis("off")
        x_per_y = (box.height * figure.get_figheight() / (bottom - top)) * per_inch
        draw_panel(axis, panel, nodes, loop, n_columns, extent + gap, gap, x_per_y, unit, label_size, style)
        if len(names) > 1:
            axis.set_title(name, color=style["text"])
    if title:
        (figure.suptitle(title, color=style["text"]) if len(names) > 1
         else axes[0].set_title(title, color=style["text"]))
    return (figure, axes[0]) if len(names) == 1 else (figure, axes)


def value_columns(flows: pd.DataFrame) -> list[str]:
    """The value columns of a flow table, one panel each.

    Args:
        flows (pd.DataFrame): The flow table.

    Returns:
        list[str]: Value, or every column but From, To, Kind and Difference.
    """
    missing = [column for column in ("From", "To") if column not in flows.columns]
    if missing:
        raise Exception(f"The flow table has no column {missing}; make it with sankey_flows.")
    if "Value" in flows.columns:
        return ["Value"]
    names = [column for column in flows.columns if column not in ("From", "To", "Kind", "Difference")]
    if not names:
        raise Exception("The flow table has no values; it needs a Value column, or one column per panel.")
    return names


def panels_of(flows: pd.DataFrame, names: list[str], min_share: float) -> list[pd.DataFrame]:
    """The links of each panel, without those smaller than min_share of the largest node in any
    panel. One threshold for all panels makes them leave out the same links.

    Args:
        flows (pd.DataFrame): The flow table.
        names (list[str]): The value columns, one per panel.
        min_share (float): Share of the largest node below which links are left out.

    Returns:
        list[pd.DataFrame]: Each panel's links, as panel_links gives them.
    """
    panels = [panel_links(flows, name) for name in names]
    largest = max((max(node_sizes(panel).values()) for panel in panels if not panel.empty), default=0.0)
    return [panel[panel["Value"] >= min_share * largest].reset_index(drop=True) for panel in panels]


def panel_links(flows: pd.DataFrame, name: str) -> pd.DataFrame:
    """The links of one panel: kinds summed per pair of nodes, nodes drawn twice told apart.

    Args:
        flows (pd.DataFrame): The flow table.
        name (str): The value column.

    Returns:
        pd.DataFrame: Columns From, To and Value, From and To as node ids.
    """
    links = flows[flows["From"] != flows["To"]].groupby(["From", "To"], as_index=False)[name].sum()
    links = links.rename(columns={name: "Value"})
    links = links[links["Value"] > noise]
    links["From"] = links["From"].map(lambda node: f"{node}{side_marker}out" if node in two_sided else node)
    links["To"] = links["To"].map(lambda node: f"{node}{side_marker}in" if node in two_sided else node)
    return links.reset_index(drop=True)


def node_sizes(links: pd.DataFrame) -> dict[str, float]:
    """Each node's size: the larger of its inflow and outflow.

    Args:
        links (pd.DataFrame): Links (From, To, Value).

    Returns:
        dict[str, float]: Size per node.
    """
    inflow = links.groupby("To")["Value"].sum()
    outflow = links.groupby("From")["Value"].sum()
    return inflow.combine(outflow, max, fill_value=0.0).to_dict()


def label_of(node: str) -> str:
    """The name a node is labelled with.

    Args:
        node (str): The node id.

    Returns:
        str: The node's name, without the side of a node drawn twice.
    """
    return node.split(side_marker)[0]


def rank_in(node: str, order: list[str], before: str | None = None) -> tuple[float, str]:
    """Sort key of a node by a list of names; names not listed go just before another name.

    Args:
        node (str): The node id.
        order (list[str]): Names in order.
        before (str | None, optional): The listed name unlisted names go before. Defaults to
            None, after all.

    Returns:
        tuple[float, str]: The key.
    """
    name = label_of(node)
    if name in order:
        return order.index(name), name
    return (order.index(before) - 0.5 if before in order else len(order)), name


def arrange(panels: list[pd.DataFrame]) -> tuple[dict[str, int], dict[str, float]]:
    """Columns and vertical order of the nodes of all panels, so the panels match.

    Sources go in the first column and final uses in the last; commodities are ordered so that
    links go right where they can, starting with those fed by no other commodity, and placed
    one column right of the furthest commodity that feeds them. Within a column, commodities
    are ordered by where their inflow comes from.

    Args:
        panels (list[pd.DataFrame]): Links of each panel.

    Returns:
        tuple[dict[str, int], dict[str, float]]: Column per node, and its rank in the column.
    """
    union = pd.concat(panels).groupby(["From", "To"])["Value"].sum()
    nodes = set(union.index.get_level_values(0)) | set(union.index.get_level_values(1))
    has_in, has_out = set(union.index.get_level_values(1)), set(union.index.get_level_values(0))
    sources = sorted(nodes - has_in, key=lambda node: rank_in(node, source_order, other))
    sinks = sorted(nodes - has_out, key=lambda node: rank_in(node, sink_order, final_energy))
    inner = nodes & has_in & has_out

    sequence = []
    remaining = set(inner)
    while remaining:
        inflow = {node: sum(value for (start, end), value in union.items() if end == node and start in remaining)
                  for node in remaining}
        free = [node for node in remaining if inflow[node] <= 0] or list(remaining)
        chosen = min(free, key=lambda node: (inflow[node], rank_in(node, inner_order)))
        sequence.append(chosen)
        remaining.remove(chosen)

    position = {node: -1 for node in sources} | {node: index for index, node in enumerate(sequence)}
    position |= {node: len(sequence) for node in sinks}
    columns = {node: 0 for node in sources}
    for node in sequence:
        feeding = [columns[start] + 1 for (start, end) in union.index if end == node and position[start] < position[node]]
        columns[node] = max(feeding + [1])
    last = max([columns[node] for node in sequence], default=0) + 1
    columns |= {node: last for node in sinks}

    order = {node: rank for rank, node in enumerate(sources)}
    order |= {node: rank for rank, node in enumerate(sinks)}
    centres = stack_centres(sources, union)
    for column in range(1, last):
        members = [node for node in sequence if columns[node] == column]

        def weight_centre(node: str) -> float:
            feeding = [(centres[start], value) for (start, end), value in union.items()
                       if end == node and start in centres and columns[start] < column]
            total = sum(value for _, value in feeding)
            return sum(centre * value for centre, value in feeding) / total if total else np.inf

        members.sort(key=lambda node: (weight_centre(node), rank_in(node, inner_order)))
        order |= {node: rank for rank, node in enumerate(members)}
        centres |= stack_centres(members, union)
    return columns, order


def stack_centres(members: list[str], union: pd.Series) -> dict[str, float]:
    """Centres of nodes stacked in a column, as shares of the column, by their summed size.

    Args:
        members (list[str]): The nodes, top to bottom.
        union (pd.Series): Summed link values by (From, To).

    Returns:
        dict[str, float]: Centre per node.
    """
    frame = union.rename("Value").reset_index()
    sizes = node_sizes(frame)
    heights = np.array([sizes.get(node, 0.0) for node in members])
    total = heights.sum() or 1.0
    tops = np.concatenate([[0.0], np.cumsum(heights)[:-1]])
    return {node: (top + height / 2) / total for node, top, height in zip(members, tops, heights)}


def column_heights(sizes: dict[str, float], columns: dict[str, int]) -> pd.Series:
    """Summed node sizes per column.

    Args:
        sizes (dict[str, float]): Size per node.
        columns (dict[str, int]): Column per node.

    Returns:
        pd.Series: Height per column.
    """
    return pd.Series(sizes).groupby(pd.Series(columns)).sum()


def place(sizes: dict[str, float], columns: dict[str, int], order: dict[str, float],
          gap: float) -> dict[str, tuple[int, float, float]]:
    """Stack each column's nodes from the top, with a gap between them.

    Args:
        sizes (dict[str, float]): Size per node of the panel.
        columns (dict[str, int]): Column per node.
        order (dict[str, float]): Rank per node within its column.
        gap (float): Gap between nodes.

    Returns:
        dict[str, tuple[int, float, float]]: Column, top and size per node.
    """
    placed = {}
    for column in sorted(set(columns.values())):
        top = 0.0
        for node in sorted((node for node in sizes if columns[node] == column), key=lambda node: order[node]):
            placed[node] = (column, top, sizes[node])
            top += sizes[node] + gap
    return placed


def loop_depth(loops: pd.DataFrame, gap: float) -> float:
    """How far below the diagram a panel's loops reach.

    Args:
        loops (pd.DataFrame): The panel's loops.
        gap (float): Gap between nodes, and between loops.

    Returns:
        float: The depth.
    """
    return float(loops["Value"].sum() + gap * len(loops)) if len(loops) else 0.0


def label_text(node: str, value: float, unit: str | None) -> str:
    """A node's label: its name and size.

    Args:
        node (str): The node id.
        value (float): Its size.
        unit (str | None): Unit of the values.

    Returns:
        str: The label.
    """
    amount = f"{value:,.0f}" if abs(value) >= 100 else f"{value:.3g}"
    return f"{label_of(node)} {amount}" + (f" {unit}" if unit else "")


def link_colour(start: str, end: str, style: dict) -> str:
    """Colour of a link: grey to Losses and to and from Unaccounted, else that of its start.

    Args:
        start (str): The node it leaves.
        end (str): The node it enters.
        style (dict): The style, one of styles.

    Returns:
        str: The colour.
    """
    if label_of(end) in (losses, unaccounted) or label_of(start) == unaccounted:
        return style["grey"]
    return style["nodes"].get(label_of(start), style["sink"])


def draw_panel(axis: Axes, links: pd.DataFrame, placed: dict[str, tuple[int, float, float]], loops: pd.DataFrame,
               n_columns: int, bottom: float, gap: float, x_per_y: float, unit: str | None,
               label_size: float, style: dict) -> None:
    """Draw one panel's links, nodes and labels.

    Args:
        axis (Axes): The axes to draw on.
        links (pd.DataFrame): The panel's links.
        placed (dict[str, tuple[int, float, float]]): Column, top and size per node.
        loops (pd.DataFrame): The links drawn as loops.
        n_columns (int): Number of columns.
        bottom (float): Where loops start below the diagram.
        gap (float): Gap between nodes.
        x_per_y (float): Width in x units of one y unit, so loops are as thick across as along.
        unit (str | None): Unit of the values.
        label_size (float): Font size of labels.
        style (dict): The style, one of styles.
    """
    centre = {node: top + size / 2 for node, (_, top, size) in placed.items()}
    looped = set(zip(loops["From"], loops["To"]))
    # Slots: links leave and enter nodes ordered by where their other end is, loops last
    out_slot, in_slot = {}, {}
    for node in placed:
        leaving = links[links["From"] == node]
        leaving = leaving.assign(loop=[(start, end) in looped for start, end in zip(leaving["From"], leaving["To"])],
                                 other=leaving["To"].map(centre)).sort_values(["loop", "other"])
        entering = links[links["To"] == node]
        entering = entering.assign(loop=[(start, end) in looped for start, end in zip(entering["From"], entering["To"])],
                                   other=entering["From"].map(centre)).sort_values(["loop", "other"])
        top = placed[node][1]
        for start, end, value in zip(leaving["From"], leaving["To"], leaving["Value"]):
            out_slot[(start, end)] = top
            top += value
        top = placed[node][1]
        for start, end, value in zip(entering["From"], entering["To"], entering["Value"]):
            in_slot[(start, end)] = top
            top += value

    lane = bottom
    reach = loop_offset
    for start, end, value in zip(links["From"], links["To"], links["Value"]):
        colour = link_colour(start, end, style)
        x_start = placed[start][0] + node_width
        x_end = placed[end][0]
        y_start, y_end = out_slot[(start, end)], in_slot[(start, end)]
        if (start, end) in looped:
            across = value * x_per_y
            outline = [(x_start, y_start), (x_start + reach + across, y_start), (x_start + reach + across, lane + value),
                       (x_end - reach - across, lane + value), (x_end - reach - across, y_end), (x_end, y_end),
                       (x_end, y_end + value), (x_end - reach, y_end + value), (x_end - reach, lane),
                       (x_start + reach, lane), (x_start + reach, y_start + value), (x_start, y_start + value)]
            axis.add_patch(Polygon(outline, closed=True, facecolor=colour, edgecolor="none", alpha=style["alpha"],
                                       zorder=1))
            lane += value + gap
            reach += across + loop_offset / 2
            continue
        middle = (x_start + x_end) / 2
        vertices = [(x_start, y_start), (middle, y_start), (middle, y_end), (x_end, y_end),
                    (x_end, y_end + value), (middle, y_end + value), (middle, y_start + value), (x_start, y_start + value),
                    (x_start, y_start)]
        codes = [DrawPath.MOVETO] + [DrawPath.CURVE4] * 3 + [DrawPath.LINETO] + [DrawPath.CURVE4] * 3 + [DrawPath.CLOSEPOLY]
        axis.add_patch(PathPatch(DrawPath(vertices, codes), facecolor=colour, edgecolor="none", alpha=style["alpha"],
                                 zorder=1))

    for node, (column, top, size) in placed.items():
        name = label_of(node)
        colour = style["nodes"].get(name, style["sink"] if column == n_columns - 1 else style["nodes"][other])
        axis.add_patch(Rectangle((column, top), node_width, size, facecolor=colour, edgecolor="none", zorder=2))
        text = label_text(node, size, unit)
        if column == 0:
            axis.text(column - 0.01, centre[node], text, ha="right", va="center", fontsize=label_size,
                      color=style["text"], zorder=3)
        elif column == n_columns - 1:
            axis.text(column + node_width + 0.01, centre[node], text, ha="left", va="center", fontsize=label_size,
                      color=style["text"], zorder=3)
        else:
            axis.text(column + node_width + 0.01, centre[node], text, ha="left", va="center", fontsize=label_size,
                      color=style["text"], zorder=3,
                      bbox={"facecolor": style["background"], "alpha": 0.7, "edgecolor": "none",
                            "boxstyle": "round,pad=0.15"})

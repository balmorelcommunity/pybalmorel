"""
IAMC Conversion

Turns the Reader's long table into IAMC data (Model, Scenario, Region,
Variable, Unit, then one column per year) and Conversion Notes, using the
Mapping Rules and the Definitions Snapshot. Knows no Balmorel symbols, so it
runs without GAMS.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import re
from pathlib import Path
from typing import TYPE_CHECKING
import numpy as np
import pandas as pd

from .reader import read_mainresults
from .rules import (default_area_kind, fill_source, import_unit, load_definitions, load_rules, load_template,
                    match_area_kinds, match_mapping_rules, match_optiflow_rules, not_reported, on_site_final,
                    optiflow_unit, pool_roles, sector_variables, source_placeholder, stem_top)
from ..backcasting import pricelevel

if TYPE_CHECKING:
    from ..classes import MainResults

# Factor from a Balmorel unit to an IAMC unit, with 'money' for the currency in money units
unit_factors = {
    ("TWh", "EJ/yr"): 3.6e-3,
    ("GWh", "EJ/yr"): 3.6e-6,
    ("PJ", "EJ/yr"): 1e-3,
    ("MW", "GW"): 1e-3,
    ("kt CO2", "Mt CO2/yr"): 1e-3,
    ("Mt CO2", "Mt CO2/yr"): 1.0,
    ("money/MWh", "money/GJ"): 1 / 3.6,
    ("Mmoney/kt CO2", "money/t CO2"): 1e3,
}
# Balmorel's money in units; the currency argument says what it is worth in IAMC currencies
money = "money"
# Commodity of the carbon price, which units' CO2 tax and emissions give
carbon = "CO2"
# Relative difference between the CO2 tax rates units in one region pay above which a
# Conversion Note gives their range
rate_tolerance = 1e-2
# Magnitude of an average price, in Balmorel's money per MWh, above which it may be the penalty
# on an unmet balance rather than a market price, so a Conversion Note points it out
price_bound = 500.0
# The price year of Balmorel's money, which its input data are in, and that money as a currency
balmorel_price_year = 2016
balmorel_currency = f"EUR_{balmorel_price_year}"
# A currency the price-level tables (backcasting/pricelevel.py) can value Balmorel's money in
table_currency = r"(?<!\w)(EUR|USD)_(\d{4})(?!\w)"
# Unit CO2 amounts are compared in
carbon_unit = "Mt CO2/yr"
backup_choices = ("supply", "exclude")
# Values smaller than this, in Balmorel's units, are solver noise and reported as 0
noise = 1e-9
# Share of a scenario's total of a quantity in a year below which an amount left out is
# solver residue, too small for a Conversion Note
relative_noise = 1e-6
note_columns = ["Scenario", "Region", "Variable", "Note"]
# Conversion Notes printed at most; to_iamc returns them all
print_limit = 30
# Columns only some quantities have, '' for the others
optional_columns = ["demand_category", "to_area", "to_country", "stated_unit", "from_process", "to_process", "flow"]
# Columns that tell units apart
unit_columns = ["unit_name", "tech_type", "fuel", "commodity"]
# Quantities of CO2 given per unit but not per commodity
carbon_quantities = ("emissions", "captured")
# Quantities per unit but not per commodity, split over the commodities a unit makes
per_unit_quantities = carbon_quantities + ("primary",)
# Fuel Category of the fuels whose captured CO2 is removed from the atmosphere when stored
biogenic_category = "Biomass"
# Quantities that are means rather than amounts, so Conversion Notes don't sum them
mean_quantities = ("price",)
# Quantity of the rows the OptiFlow Mapping reports
optiflow_quantity = "optiflow"
# How Conversion Notes name quantities that aren't plain words
quantity_labels = {"captured": "captured CO2", "removal": "stored CO2 from biomass", "stored": "stored CO2",
                   "input": "fuel input", "primary": "primary energy", "imports": "net imports", "tax": "CO2 tax"}
# The commodity whose exchange between areas is Heat Exchange; exchange of the others is trade
heat_commodity = "HEAT"
# Demand category of the heat district heating sends net to an individual or industry area
net_exchange = "NET_EXCHANGE"
# Demand category of the part of an 'on-site' category that units use where what they make isn't reported
on_site = "ON_SITE"
# Share of a commodity's supply or demand in a region and year that may go unaccounted for before
# a Conversion Note says it doesn't add up (and of all its demand that year, for regions with
# little)
balance_tolerance = 1e-2


#%% ------------------------------- ###
###          1. Entry Points        ###
### ------------------------------- ###

def to_iamc(results: "MainResults",
            model: str,
            scenarios: dict[str, str] | None = None,
            template: str | Path | None = None,
            definitions: str | Path | None = None,
            rules: dict[str, str | Path | pd.DataFrame] | None = None,
            backup_units: str = "supply",
            backup_pattern: str = "GNR_BACKUP",
            optiflow: dict[str, str | Path | None] | None = None,
            currency: dict[str, float] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert MainResults to IAMC data.

    Reports the IAMC Variables that the rule tables cover (see pybalmorel/iamc/rule_tables/), in the
    units of the Definitions Snapshot, per Balmorel country and modelled year. Transmission
    between countries, and what import units bring in from outside the model, are reported as
    Trade (net exports). Capacity is that of the commodity a unit makes, so electrolysers' is
    their hydrogen output, as Balmorel states it. The electricity heat units in individual and
    industry areas use counts as final energy, as their heat isn't centralized heat. Demand
    categories with a Final Energy Sector are also reported under that sector, e.g. what carbon
    capture uses under Final Energy|Carbon Management. Emissions are net of the stored part of
    the CO2 captured from biomass, which is also reported as Carbon Removal. Where the results
    give no captured CO2, that of units marked w/ CCS is derived from their fuel input. Without
    OptiFlow, all captured CO2 counts as stored. For scenarios linked to OptiFlow, OptiFlow's
    results are reported as the 'optiflow' rules (the OptiFlow Mapping) say, which also give the
    stored part. Primary Energy is units' fuel input, or what they make for nuclear and the
    non-biomass renewables (direct equivalent), per Source and what it is used for; net imports
    of electricity and hydrogen count as Secondary Energy Trade. Primary Energy and its totals
    per Source (e.g. Primary Energy|Gas) sum all of that, with the fuel of heat units in
    individual and industry areas, which has no variable by use. Final Energy and Emissions|CO2
    sum the demand and emissions reported below them, with what the OptiFlow Mapping reports
    there. These totals count only what Balmorel models, as a Conversion Note says, so they can
    be lower than a whole-economy model's. The prices of electricity, hydrogen and district heat
    are Balmorel's yearly means of hourly marginal prices, averaged over a country's regions or
    district heating areas weighted by their annual demand; a country without demand has no
    price. The carbon price is the CO2 tax per tonne that emitting units pay; an emission cap's
    shadow price is not in MainResults. Prices are converted from Balmorel's money (EUR_2016) to
    the IAMC unit's currency at the worth `currency` gives, else by pybalmorel's price-level
    tables (backcasting/pricelevel.py) for EUR or USD of a year they cover, with a Conversion
    Note giving the worth; otherwise they are left out. Investment and capital costs are not
    reported, as MainResults holds only the annuities of capital costs. Conversion Notes say
    what was put under Other, what was left out, how backup units, import units and Heat
    Exchange were treated, and where a commodity's supply and demand don't add up; the first of
    them are printed. Values that can't be known without missing rules are left empty.

    Args:
        results (MainResults): The loaded result files.
        model (str): The IAMC Model label, e.g. 'Balmorel-DTU'.
        scenarios (dict[str, str] | None, optional): IAMC Scenario name per Balmorel scenario.
            Several Balmorel scenarios can share one, if their years don't overlap. Unmapped
            scenarios keep their own name. Defaults to None.
        template (str | Path | None, optional): A Template .xlsx; output is limited to the IAMC
            Variables its 'Extended List' sheet accepts. Defaults to None.
        definitions (str | Path | None, optional): Folder with your own Definitions Snapshot
            (variables.csv, regions.csv). Defaults to the snapshot shipped with pybalmorel.
        rules (dict[str, str | Path | pd.DataFrame] | None, optional): Rule rows that take
            precedence over the shipped ones, keyed by table ('fuels', 'mapping', 'stems',
            'aggregates', 'countries', 'areas', 'demand_categories', 'optiflow'). Defaults to None.
        backup_units (str, optional): 'supply' counts backup units' output as supply under their
            fuel, and reports their emissions; 'exclude' leaves both out. Their capacity is never
            reported. Defaults to 'supply'.
        backup_pattern (str, optional): Regular expression that marks backup units by name.
            Defaults to 'GNR_BACKUP'.
        optiflow (dict[str, str | Path | None] | None, optional): OptiFlow result file per
            Balmorel scenario, None to read none for it. Scenarios not listed use
            'Optiflow_<MainResults file>' next to their MainResults file, if there is one.
            A scenario is linked to OptiFlow if OptiFlow results are read for it, or if its
            MainResults carry OptiFlow's emissions (Mapping Rule 'optiflow'). Defaults to None.
        currency (dict[str, float] | None, optional): What one unit of Balmorel's money,
            EUR_2016, is worth in the currencies the IAMC units are in, keyed as the units name
            them, e.g. {'USD_2010': 1.1} if it is worth 1.1 USD_2010. It beats pybalmorel's
            price-level tables, which give EUR and USD of the years they cover. Prices in other
            currencies are left out. Defaults to None.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The IAMC data, and the Conversion Notes (columns
            Scenario, Region, Variable, Note).
    """
    long = read_mainresults(results, optiflow)
    return convert(long, model, scenarios, template, definitions, rules, backup_units, backup_pattern, currency)


def convert(long: pd.DataFrame,
            model: str,
            scenarios: dict[str, str] | None = None,
            template: str | Path | None = None,
            definitions: str | Path | None = None,
            rules: dict[str, str | Path | pd.DataFrame] | None = None,
            backup_units: str = "supply",
            backup_pattern: str = "GNR_BACKUP",
            currency: dict[str, float] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert the Reader's long table to IAMC data. See to_iamc for the arguments.

    Args:
        long (pd.DataFrame): The long table from read_mainresults.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The IAMC data and the Conversion Notes.
    """
    if backup_units not in backup_choices:
        raise Exception(f"backup_units must be one of {backup_choices}, not '{backup_units}'.")

    variables, regions = load_definitions(definitions)
    tables = load_rules(rules)
    notes = []

    names = set(variables["variable"])
    long = long.copy()
    for column in optional_columns:
        long[column] = long[column].fillna("") if column in long.columns else ""
    if "weight" not in long.columns:
        long["weight"] = np.nan
    long = name_scenarios(long, scenarios)
    modelled_years = long.groupby("iamc_scenario")["year"].unique()
    priced = long["quantity"].isin(["price", "tax"])
    prices = long[priced]
    long, carried, linked = drop_optiflow_units(long[~priced].drop(columns="weight"), tables["mapping"], notes)
    note_stated_units(pd.concat((long, prices)), notes)
    prices = pd.concat((prices, long[long["quantity"] == "emissions"]), ignore_index=True)
    flows = long[long["quantity"] == "flow"]
    long = long[long["quantity"] != "flow"]
    long = derive_capture(long, tables["mapping"], notes)
    long = derive_primary(long, tables, notes)
    shares = pool_shares(flows, tables["optiflow"], notes)
    check_fuel_rules(carried, flows, tables["optiflow"], notes)
    long = split_by_output(long, notes)
    long = count_trade(long, tables["mapping"], notes)
    long = name_regions(long, tables["countries"], regions, notes)
    flows = name_regions(flows, tables["countries"], regions, notes)
    long = attach_area_kinds(long, tables["areas"])
    long = exchange_heat(long, tables["mapping"], notes)
    long = carve_on_site(long, tables["stems"], tables["demand_categories"], tables["fuels"], notes)
    check_balances(long, tables["stems"], tables["mapping"], tables["demand_categories"], notes)
    long = select_demand(long, tables["demand_categories"], notes)
    long = net_emissions(long, shares, linked, tables, notes)
    long = attach_stems(long, tables["stems"], names, notes)
    long = attach_sectors(long, tables["demand_categories"], names, notes)
    long = attach_segments(long, tables, names, notes)
    long = treat_backup_units(long, backup_units, backup_pattern, notes)
    reported = report_optiflow(flows, tables["optiflow"], shares, tables["stems"], names, notes)
    if not reported.empty:
        long = pd.concat((long, reported), ignore_index=True)
    note_totals(long, tables["stems"], notes)
    long = copy_to_aggregates(long, tables["aggregates"], names)
    prices = report_prices(prices, tables, regions, variables, currency, notes)
    if not prices.empty:
        long = pd.concat((long, prices), ignore_index=True)

    data = sum_to_variables(long, variables, tables["aggregates"])
    if template is not None:
        data = limit_to_template(data, template, notes)
    data = to_wide(data, model, modelled_years, set(prices["variable"]))

    notes = pd.DataFrame(notes, columns=note_columns).drop_duplicates(ignore_index=True)
    print_notes(notes)
    return data, notes


def write_iamc(data: pd.DataFrame, notes: pd.DataFrame, path: str | Path) -> None:
    """Write IAMC data and its Conversion Notes.

    An .xlsx gets a 'data' sheet and a 'notes' sheet. A .csv gets the data, with the notes in
    '<name>_notes.csv' next to it.

    Args:
        data (pd.DataFrame): IAMC data from to_iamc.
        notes (pd.DataFrame): Conversion Notes from to_iamc.
        path (str | Path): The file to write, ending in .xlsx or .csv.
    """
    path = Path(path)
    if path.suffix == ".xlsx":
        with pd.ExcelWriter(path) as writer:
            data.to_excel(writer, sheet_name="data", index=False)
            notes.to_excel(writer, sheet_name="notes", index=False)
    elif path.suffix == ".csv":
        data.to_csv(path, index=False)
        notes.to_csv(path.with_name(f"{path.stem}_notes.csv"), index=False)
    else:
        raise Exception(f"Write IAMC data to an .xlsx or .csv file, not '{path.name}'.")


#%% ------------------------------- ###
### 2. Scenarios, Trade and Regions ###
### ------------------------------- ###

def name_scenarios(long: pd.DataFrame, scenarios: dict[str, str] | None) -> pd.DataFrame:
    """Add the IAMC Scenario of each row, refusing scenarios whose years overlap.

    Args:
        long (pd.DataFrame): The long table.
        scenarios (dict[str, str] | None): IAMC Scenario per Balmorel scenario.

    Returns:
        pd.DataFrame: The long table with an 'iamc_scenario' column.
    """
    long = long.copy()
    long["iamc_scenario"] = long["scenario"].map(scenarios or {}).fillna(long["scenario"])

    years = long[["iamc_scenario", "scenario", "year"]].drop_duplicates()
    shared = years[years.duplicated(["iamc_scenario", "year"], keep=False)]
    if not shared.empty:
        clashes = shared.groupby(["iamc_scenario", "year"])["scenario"].apply(lambda names: ", ".join(names))
        raise Exception(
            "Balmorel scenarios mapped to the same IAMC Scenario must not share years:\n"
            f"{clashes.to_string()}"
        )
    return long


def count_trade(long: pd.DataFrame, mapping: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Turn transmission between countries, and what import units bring in, into trade.

    Trade is net exports. Transmission from one country to another counts for the sender, and
    negative for the receiver; transmission within a country nets out and is dropped. Import units
    (Mapping Rule 'import') bring the commodity in from outside the model: their output counts as
    negative trade, and the rest of what they do is left out. Exchange of heat is Heat Exchange,
    which exchange_heat treats. Net imports, trade with the opposite sign, count as Primary
    Energy (quantity 'imports').

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios.
        mapping (pd.DataFrame): The 'mapping' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with trade and imports rows, which have no area or unit, in
            place of transmission and import units' rows.
    """
    blank = {"quantity": "trade", "area": "", "unit_name": "", "tech_type": "", "fuel": "",
             "demand_category": "", "to_area": "", "to_country": ""}
    is_transmission = (long["quantity"] == "exchange") & (long["commodity"] != heat_commodity)
    transmission = long[is_transmission]
    long = long[~is_transmission]

    units = long.loc[long["unit_name"] != "", unit_columns].drop_duplicates().reset_index(drop=True)
    importers = units[match_mapping_rules(units, mapping) == import_unit]
    by_importer = np.zeros(len(long), dtype=bool)
    if not importers.empty:
        by_importer = pd.MultiIndex.from_frame(long[unit_columns]).isin(pd.MultiIndex.from_frame(importers))
    imported = long[by_importer & (long["quantity"] == "output")]
    importer_carbon = long[by_importer & long["quantity"].isin(per_unit_quantities)]
    long = long[~by_importer]

    abroad = transmission[(transmission["to_country"] != "") & (transmission["to_country"] != transmission["country"])]
    trade = pd.concat((
        abroad.assign(**blank),
        abroad.assign(**blank, country=abroad["to_country"], value=-abroad["value"]),
        imported.assign(**blank, value=-imported["value"]),
    ), ignore_index=True)
    imports = trade.assign(quantity="imports", value=-trade["value"])

    for (scenario, commodity, value_unit), rows in imported.groupby(["iamc_scenario", "commodity", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        if (by_year.abs() < noise).all():
            continue
        units = ", ".join(f"{tech_type}/{fuel}" for tech_type, fuel in
                          rows[["tech_type", "fuel"]].drop_duplicates().itertuples(index=False))
        notes.append(note(scenario, "", "", (
            f"Import units ({units}) brought {amounts(by_year)} {value_unit} of {commodity} in from outside the "
            "model, counted as imports under Trade, not as output. Their capacity is not reported."
        )))
    for (scenario, quantity, value_unit), rows in importer_carbon.groupby(["iamc_scenario", "quantity", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        if (by_year.abs() < noise).all():
            continue
        notes.append(note(scenario, "", "", (
            f"Not reported: import units' {quantity_label(quantity)}, {amounts(by_year)} {value_unit}, as what "
            "they bring in is made outside the model."
        )))
    unknown = transmission[transmission["to_country"] == ""]
    for (scenario, commodity, value_unit), rows in unknown.groupby(["iamc_scenario", "commodity", "value_unit"]):
        notes.append(note(scenario, "", "", (
            f"Transmission of {commodity} to regions whose country the results don't give is not counted as "
            f"Trade: {amounts(rows.groupby('year')['value'].sum())} {value_unit}."
        )))

    return pd.concat((long, trade, imports), ignore_index=True)


def name_regions(long: pd.DataFrame, countries: pd.DataFrame, regions: pd.DataFrame,
                 notes: list[dict]) -> pd.DataFrame:
    """Add the IAMC Region of each row, leaving out countries without one.

    Args:
        long (pd.DataFrame): The long table.
        countries (pd.DataFrame): The 'countries' rule table (country, iso3).
        regions (pd.DataFrame): The snapshot's regions (region, iso3).
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows with an IAMC Region, with a 'region' column.
    """
    iso3 = long["country"].map(countries.set_index("country")["iso3"])
    region_by_iso3 = regions.drop_duplicates("iso3").set_index("iso3")["region"]
    long = long.assign(region=iso3.map(region_by_iso3))

    unnamed = long[long["region"].isna()]
    for (scenario, country), _ in unnamed.groupby(["iamc_scenario", "country"]):
        code = iso3[long["country"] == country].iloc[0]
        reason = (
            "has no ISO3 code in the 'countries' rules"
            if pd.isna(code)
            else f"has ISO3 code '{code}', which no IAMC Region in the Definitions Snapshot has"
        )
        notes.append(note(scenario, country, "", f"Balmorel country {country} {reason}; not reported."))
    return long[long["region"].notna()]


#%% ------------------------------- ###
###    3. Areas and Heat Exchange   ###
### ------------------------------- ###

def attach_area_kinds(long: pd.DataFrame, area_rules: pd.DataFrame) -> pd.DataFrame:
    """Add the Area Kind of each row's area, and of the receiving area of exchange rows.

    Args:
        long (pd.DataFrame): The long table.
        area_rules (pd.DataFrame): The 'areas' rule table.

    Returns:
        pd.DataFrame: The long table with 'area_kind' ('' for rows per region, without an area)
            and 'to_area_kind' ('' without a receiving area) columns.
    """
    kinds = match_area_kinds(long["area"], area_rules).where(long["area"] != "", "")
    long = long.assign(area_kind=kinds, to_area_kind="")
    receiving = long["to_area"] != ""
    long.loc[receiving, "to_area_kind"] = match_area_kinds(long.loc[receiving, "to_area"], area_rules)
    return long


def exchange_heat(long: pd.DataFrame, mapping: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Turn Heat Exchange between district heating and other areas into demand and output.

    Heat transmission is netted per pair of areas and year. Heat district heating sends net to
    an individual or industry area becomes demand of the district heating area, in the category
    NET_EXCHANGE. Heat it receives net becomes output of the district heating area, split over
    the units that made it: the sending area's units, and those of the individual and industry
    areas that sent heat to it, in proportion to the heat each area had (Output-Share Split).
    Units whose output the Mapping Rules don't report (storage) make no heat for this. Heat
    transmission between district heating areas stays inside centralized heat.

    Args:
        long (pd.DataFrame): The long table with Area Kinds.
        mapping (pd.DataFrame): The 'mapping' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table without exchange rows, with the demand and output rows
            Heat Exchange gives.
    """
    is_exchange = (long["quantity"] == "exchange") & (long["commodity"] == heat_commodity)
    exchange = long[is_exchange]
    long = long[~is_exchange]
    if exchange.empty:
        return long

    flows = net_flows(exchange)
    from_dh = flows["area_kind"] == default_area_kind
    to_dh = flows["to_area_kind"] == default_area_kind
    out_of_dh = flows[from_dh & ~to_dh]
    into_dh = flows[~from_dh & to_dh]
    among = flows[~from_dh & ~to_dh]

    demand = out_of_dh.assign(quantity="demand", demand_category=net_exchange, to_area="", to_country="",
                             to_area_kind="")
    supplied = trace_heat(long, into_dh, among, out_of_dh, mapping)

    # Say per scenario how much crossed, and what no unit could be traced to
    sent = out_of_dh.groupby(["iamc_scenario", "year"])["value"].sum()
    received = into_dh.groupby(["iamc_scenario", "year"])["value"].sum()
    value_unit = exchange["value_unit"].iloc[0]
    for scenario in flows["iamc_scenario"].unique():
        notes.append(note(scenario, "", "", (
            f"Heat Exchange: district heating sent {amounts(sent.get(scenario))} {value_unit} net to "
            f"individual and industry areas, counted as its demand ({net_exchange}), and received "
            f"{amounts(received.get(scenario))} {value_unit} net from them, counted as its output and "
            "split over the units that made the heat, traced through heat transmission between "
            "individual and industry areas. The output noted as not reported for those areas includes "
            "the heat they sent. Emissions, captured CO2 and primary energy of the units that made it stay "
            "with their own areas."
        )))
    untraced = supplied[supplied["unit_name"] == ""]
    for (scenario, source), rows in untraced.groupby(["iamc_scenario", "fuel"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        what = ("came from district heating through individual and industry areas" if source == "district heating"
                else "no unit could be traced to (the sending areas sent more than their units made)")
        notes.append(note(scenario, "", "", (
            f"Heat Exchange brought {amounts(by_region.sum())} {value_unit} into district heating in "
            f"{list_regions(by_region.index)} that {what}; reported under Other."
        )))
    supplied.loc[supplied["unit_name"] == "", "fuel"] = ""

    return pd.concat((long, demand, supplied), ignore_index=True)


def net_flows(exchange: pd.DataFrame) -> pd.DataFrame:
    """Net heat transmission per pair of areas and year, leaving out flows between district heating areas.

    Args:
        exchange (pd.DataFrame): The exchange rows, from 'area' to 'to_area'.

    Returns:
        pd.DataFrame: One row per pair of areas and year with a net flow, from 'area' to
            'to_area', with their Area Kinds and the (positive) value.
    """
    exchange = exchange[(exchange["area_kind"] != default_area_kind) | (exchange["to_area_kind"] != default_area_kind)]
    keys = ["scenario", "iamc_scenario", "year", "country", "region", "value_unit"]
    first = exchange["area"] <= exchange["to_area"]
    pairs = exchange[keys].assign(
        area_a=exchange["area"].where(first, exchange["to_area"]),
        area_b=exchange["to_area"].where(first, exchange["area"]),
        kind_a=exchange["area_kind"].where(first, exchange["to_area_kind"]),
        kind_b=exchange["to_area_kind"].where(first, exchange["area_kind"]),
        value=exchange["value"].where(first, -exchange["value"]),
    )
    net = pairs.groupby(keys + ["area_a", "area_b", "kind_a", "kind_b"], as_index=False)["value"].sum()

    forward = net["value"] >= 0
    flows = net[keys].assign(
        area=net["area_a"].where(forward, net["area_b"]),
        to_area=net["area_b"].where(forward, net["area_a"]),
        area_kind=net["kind_a"].where(forward, net["kind_b"]),
        to_area_kind=net["kind_b"].where(forward, net["kind_a"]),
        value=net["value"].abs(),
    )
    flows = flows[flows["value"] >= noise].reset_index(drop=True)
    for column in ("unit_name", "tech_type", "fuel", "demand_category"):
        flows[column] = ""
    flows["commodity"] = heat_commodity
    return flows


def trace_heat(long: pd.DataFrame, into_dh: pd.DataFrame, among: pd.DataFrame, out_of_dh: pd.DataFrame,
               mapping: pd.DataFrame) -> pd.DataFrame:
    """Split heat that individual and industry areas send into district heating over the units that made it.

    The heat an area has is what its units make, plus what other individual and industry
    areas and district heating send it; whatever it sends carries the mix of all of it. With
    A[s, t] the share of area t's heat that t sends to area s, and D the heat each area gets
    from outside the individual and industry areas, by origin, the heat each area has by origin
    is X = (I - A)^-1 D. An area that sends more than it has gets the gap as untraced heat.

    Args:
        long (pd.DataFrame): The long table, without exchange rows.
        into_dh (pd.DataFrame): Net flows from individual and industry areas into district heating.
        among (pd.DataFrame): Net flows between individual and industry areas.
        out_of_dh (pd.DataFrame): Net flows from district heating to individual and industry areas.
        mapping (pd.DataFrame): The 'mapping' rule table.

    Returns:
        pd.DataFrame: Output rows on the receiving district heating areas, with the units that
            made the heat. Heat that came from district heating or no unit could be traced to has
            no unit, and 'district heating' or 'untraced' as fuel.
    """
    columns = list(long.columns)
    if into_dh.empty:
        return long.iloc[0:0]

    made = long[(long["quantity"] == "output") & (long["commodity"] == heat_commodity)
                & (long["area_kind"] != default_area_kind)]
    units = made[["unit_name", "tech_type", "fuel", "commodity"]].drop_duplicates()
    units["template"] = match_mapping_rules(units, mapping)
    made = made.merge(units, on=["unit_name", "tech_type", "fuel", "commodity"])
    made = made[made["template"] != not_reported].drop(columns="template")
    mixed_units = set(made["value_unit"]) | set(into_dh["value_unit"])
    if len(mixed_units) > 1:
        raise Exception(f"Heat output and heat transmission come in different units {mixed_units}; can't trace them.")

    traced = []
    for (scenario, year), senders in into_dh.groupby(["scenario", "year"]):
        links = among[(among["scenario"] == scenario) & (among["year"] == year)]
        from_dh = out_of_dh[(out_of_dh["scenario"] == scenario) & (out_of_dh["year"] == year)]
        areas = sorted(set(senders["area"]) | set(links["area"]) | set(links["to_area"]))
        sources = made[(made["scenario"] == scenario) & (made["year"] == year)
                       & made["area"].isin(areas)].reset_index(drop=True)
        index = pd.Series(np.arange(len(areas)), index=areas)

        def per_area(rows: pd.DataFrame, column: str) -> np.ndarray:
            return rows.groupby(column)["value"].sum().reindex(areas, fill_value=0.0).to_numpy()

        own = per_area(sources, "area")
        dh_in = per_area(from_dh[from_dh["to_area"].isin(areas)], "to_area")
        supply = own + dh_in + per_area(links, "to_area")
        total = np.maximum(supply, per_area(links, "area") + per_area(senders, "area"))

        shares_sent = np.zeros((len(areas), len(areas)))
        np.add.at(shares_sent, (index.loc[links["to_area"]].to_numpy(), index.loc[links["area"]].to_numpy()),
                  links["value"].to_numpy() / total[index.loc[links["area"]].to_numpy()])
        origins = np.zeros((len(areas), len(sources) + 2))
        origins[index.loc[sources["area"]].to_numpy(), np.arange(len(sources))] = sources["value"].to_numpy()
        origins[:, -2] = dh_in
        origins[:, -1] = total - supply
        try:
            had = np.linalg.solve(np.eye(len(areas)) - shares_sent, origins)
        except np.linalg.LinAlgError:
            had = np.zeros_like(origins)
            had[:, -1] = total

        rows = index.loc[senders["area"]].to_numpy()
        sent = senders["value"].to_numpy()[:, None] * had[rows] / total[rows, None]
        flow, origin = np.nonzero(np.abs(sent) >= noise)
        receivers = senders.iloc[flow].reset_index(drop=True)
        by_unit = origin < len(sources)
        unit_rows = sources.iloc[origin[by_unit]].reset_index(drop=True)
        rows_out = receivers[["scenario", "iamc_scenario", "year", "country", "region", "value_unit"]].assign(
            area=receivers["to_area"], area_kind=default_area_kind, quantity="output", commodity=heat_commodity,
            demand_category="", to_area="", to_country="", to_area_kind="", value=sent[flow, origin],
            unit_name="", tech_type="", fuel=np.where(origin == len(sources), "district heating", "untraced"),
        )
        for column in ("unit_name", "tech_type", "fuel"):
            rows_out.loc[by_unit, column] = unit_rows[column].to_numpy()
        traced.append(rows_out)

    return pd.concat(traced, ignore_index=True).reindex(columns=columns, fill_value="")


def carve_on_site(long: pd.DataFrame, stems: pd.DataFrame, demand_categories: pd.DataFrame, fuels: pd.DataFrame,
                  notes: list[dict]) -> pd.DataFrame:
    """Move the part of 'on-site' demand categories that is used where what it makes isn't reported, and drop fuel input.

    A demand category the 'demand_categories' rules mark 'on-site', such as
    ENDOGENOUS_ELECT2HEAT (the electricity heat units take in), is split. Units none of whose
    output has an 'output' stem for their Area Kind, such as heat pumps in individual and
    industry areas, whose heat isn't centralized heat, are where the energy ends up: their
    fuel input of the row's Fuel Category moves from the category to category ON_SITE, per
    IAMC Region and year. Totals don't change, so the Commodity Balance is checked as before.

    Args:
        long (pd.DataFrame): The long table with Area Kinds, with fuel input.
        stems (pd.DataFrame): The 'stems' rule table.
        demand_categories (pd.DataFrame): The 'demand_categories' rule table.
        fuels (pd.DataFrame): The 'fuels' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table without fuel input, with demand rows moving the part used
            on site from each 'on-site' category to ON_SITE.
    """
    is_input = long["quantity"] == "input"
    used = long[is_input & (long["value"] >= noise)]
    long = long[~is_input]
    split = demand_categories[demand_categories["final"] == on_site_final]
    if split.empty or used.empty:
        return long

    # Units none of whose output is reported in their kind of area
    output = long[(long["quantity"] == "output") & (long["value"] >= noise)]
    output_stems = stems[stems["quantity"] == "output"]
    with_stem = set(zip(output_stems["commodity"], output_stems["area_kind"]))
    reported = [(commodity, kind) in with_stem or (commodity, "") in with_stem
                for commodity, kind in zip(output["commodity"], output["area_kind"])]
    unit_keys = ["scenario", "country", "area", "unit_name", "tech_type", "fuel"]
    any_reported = output.assign(reported=reported).groupby(unit_keys)["reported"].any()
    on_site_units = any_reported[~any_reported].index
    categories = fuels.set_index("fuel")["category"]

    keys = ["scenario", "iamc_scenario", "year", "country", "region", "value_unit"]
    moved = []
    for rule in split.itertuples(index=False):
        taken = used[(used["fuel"].map(categories) == rule.fuel_category)
                     & pd.MultiIndex.from_frame(used[unit_keys]).isin(on_site_units)]
        if taken.empty:
            continue
        amount = taken.groupby(keys)["value"].sum()
        demand = long[(long["quantity"] == "demand") & (long["commodity"] == rule.commodity)
                      & (long["demand_category"] == rule.demand_category)]
        given = demand.groupby(keys)["value"].sum().reindex(amount.index, fill_value=0.0)
        rest = demand.groupby(keys)["value"].sum().sub(amount, fill_value=0.0)
        carved = amount.reset_index().assign(quantity="demand", commodity=rule.commodity)
        moved += [carved.assign(demand_category=on_site),
                  carved.assign(demand_category=rule.demand_category, value=-carved["value"])]

        for (scenario, value_unit), rows in taken.groupby(["iamc_scenario", "value_unit"]):
            kinds = " and ".join(sorted(set(rows["area_kind"])))
            in_scenario = ((rest.index.get_level_values("iamc_scenario") == scenario)
                           & (rest.index.get_level_values("value_unit") == value_unit))
            left = rest[in_scenario].groupby(level="year").sum()
            notes.append(note(scenario, "", "", (
                f"Of {rule.commodity} demand in category {rule.demand_category}, what units in {kinds} areas take in "
                f"as {rule.fuel_category} fuels counts as final demand ({on_site}), as what they make there isn't "
                f"reported: {amounts(rows.groupby('year')['value'].sum())} {value_unit}. The rest, "
                f"{amounts(left)} {value_unit}, does not. Units: {list_names(rows['tech_type'])}."
            )))
        over = amount[amount - given > balance_tolerance * given.abs() + noise]
        for (scenario, value_unit), rows in over.groupby(level=["iamc_scenario", "value_unit"]):
            regions = rows.index.get_level_values("region")
            notes.append(note(scenario, "", "", (
                f"In {list_regions(regions)}, units in areas whose output isn't reported took in "
                f"{amounts(rows.groupby(level='year').sum())} {value_unit} of {rule.fuel_category} fuels, more than "
                f"{rule.commodity} demand in category {rule.demand_category} there "
                f"({amounts(given[rows.index].groupby(level='year').sum())} {value_unit}). All of it counts as final "
                f"demand ({on_site}); the category may not cover all their use."
            )))

    if not moved:
        return long
    moved = pd.concat(moved, ignore_index=True).reindex(columns=long.columns, fill_value="")
    return pd.concat((long, moved), ignore_index=True)


def select_demand(long: pd.DataFrame, demand_categories: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Keep the demand in categories that count as final demand.

    Args:
        long (pd.DataFrame): The long table.
        demand_categories (pd.DataFrame): The 'demand_categories' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table without demand in other categories.
    """
    is_demand = long["quantity"] == "demand"
    demand = long[is_demand].merge(demand_categories, on=["commodity", "demand_category"], how="left")

    unknown = demand[demand["final"].isna()]
    for (scenario, commodity, category, kind, value_unit), rows in unknown.groupby(
            ["iamc_scenario", "commodity", "demand_category", "area_kind", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        where = f" in {kind} areas" if kind else ""
        notes.append(note(scenario, "", "", (
            f"Demand of {commodity} in category {category}{where} is not reported (the "
            f"'demand_categories' rules have no row for it): {amounts(by_year)} {value_unit}."
        )))
    kept = demand.loc[demand["final"] == "yes", long.columns]
    return pd.concat((long[~is_demand], kept), ignore_index=True)


def check_balances(long: pd.DataFrame, stems: pd.DataFrame, mapping: pd.DataFrame,
                   demand_categories: pd.DataFrame, notes: list[dict]) -> None:
    """Note where a commodity's supply and demand don't add up in a region.

    Checked for every commodity with a stem for demand, in the Area Kinds of those stems (all of
    them, for a stem of any Area Kind). A commodity balances when the output of its units, without
    those whose output the Mapping Rules don't report (storage), less its trade (net exports),
    equals its demand in the categories the 'demand_categories' rules know, final or not. Heat
    Exchange is output and demand by now. What the results make, use or move where the Reader
    doesn't look, such as transmission they don't list or a model add-on's, breaks this, and then
    the reported supply and demand don't add up either. A category given with the wrong sign
    makes a gap of twice its size, with the opposite sign: regions where taking one category with
    the opposite sign closes the gap in every year get one note per scenario and category, so the
    gaps that remain stand out. A scenario whose results give output of the commodity but no
    demand of it gets one note instead.

    Args:
        long (pd.DataFrame): The long table after trade and Heat Exchange, with all demand categories.
        stems (pd.DataFrame): The 'stems' rule table.
        mapping (pd.DataFrame): The 'mapping' rule table.
        demand_categories (pd.DataFrame): The 'demand_categories' rule table.
        notes (list[dict]): Conversion Notes, appended to.
    """
    keys = ["iamc_scenario", "region", "value_unit", "year"]
    for commodity, demand_stems in stems[stems["quantity"] == "demand"].groupby("commodity"):
        kinds = set(demand_stems["area_kind"])
        rows = long[long["commodity"] == commodity]
        where = ""
        if "" not in kinds:
            rows = rows[rows["area_kind"].isin(kinds)]
            where = f" in {' and '.join(sorted(kinds))} areas"
        if rows.empty:
            continue
        output = rows[rows["quantity"] == "output"]
        output = output[(output["unit_name"] == "") | (match_mapping_rules(output, mapping) != not_reported)]
        trade = rows[rows["quantity"] == "trade"]
        demand = rows[rows["quantity"] == "demand"]
        with_demand = set(demand["iamc_scenario"])

        # Results that give no demand at all have nothing to balance against
        for (scenario, value_unit), made in output[~output["iamc_scenario"].isin(with_demand)].groupby(
                ["iamc_scenario", "value_unit"]):
            by_year = made.groupby("year")["value"].sum()
            if (by_year.abs() < noise).all():
                continue
            notes.append(note(scenario, "", "", (
                f"The results give no demand of {commodity}{where}, though its units made {amounts(by_year)} "
                f"{value_unit}: nothing is reported under {', '.join(sorted(set(demand_stems['stem'])))}, and "
                f"whether {commodity} adds up isn't checked."
            )))

        known = demand.merge(demand_categories, on=["commodity", "demand_category"])
        supply = output.groupby(keys)["value"].sum().sub(trade.groupby(keys)["value"].sum(), fill_value=0.0)
        balance = pd.concat({"supply": supply, "used": known.groupby(keys)["value"].sum()}, axis=1).fillna(0.0)
        balance = balance[balance.index.get_level_values("iamc_scenario").isin(with_demand)]
        balance["gap"] = balance["supply"] - balance["used"]
        # Off by more than the tolerance of the region's supply or demand, and of all demand that year
        everywhere = balance.groupby(level=["iamc_scenario", "value_unit", "year"])["used"].transform("sum")
        scale = np.maximum(balance[["supply", "used"]].abs().max(axis=1), balance_tolerance * everywhere)
        off = balance["gap"].abs() > balance_tolerance * scale
        off = off.groupby(level=["iamc_scenario", "region", "value_unit"]).transform("any")
        by_category = known.groupby(keys + ["demand_category"])["value"].sum().unstack(fill_value=0.0)
        wrong_sign = {}
        for (scenario, region, value_unit), gaps in balance[off].groupby(level=["iamc_scenario", "region", "value_unit"]):
            by_year = gaps["gap"].droplevel([0, 1, 2])
            categories = by_category.reindex(gaps.index, fill_value=0.0).droplevel([0, 1, 2])
            categories = categories.loc[:, (categories.abs() > noise).any()]
            # A category given with the wrong sign makes a gap of twice its size, with the opposite sign
            flipped = categories.mul(2.0).add(by_year, axis=0)
            closes = flipped.abs().le(balance_tolerance * scale[gaps.index].to_numpy(), axis=0).all()
            if closes.sum() == 1:
                category = closes[closes].index[0]
                wrong_sign.setdefault((scenario, value_unit, category), []).append((region, categories[category]))
                continue
            text = (
                f"{commodity}{where} doesn't add up: its output less net exports was "
                f"{amounts(by_year.where(by_year.abs() >= noise, 0.0))} {value_unit} more than its demand in the "
                "categories the 'demand_categories' rules know (negative: less). The results make, use or move "
                f"{commodity} where the Reader doesn't look, such as transmission they don't list or a model "
                "add-on's, so its reported supply and demand don't add up either."
            )
            negative = [category for category in categories if (categories[category] < -noise).any()]
            if negative:
                listed = "; ".join(f"{category}, {amounts(categories[category])} {value_unit}" for category in negative)
                left = "; ".join(f"{category} would leave a gap of {amounts(flipped[category])} {value_unit}"
                                 for category in negative)
                text += (f" Its demand there is negative in some years in categories {listed}. A category given with "
                         f"the wrong sign makes a gap of twice its size, with the opposite sign: taken with the "
                         f"opposite sign, {left}.")
            notes.append(note(scenario, region, "", text))
        final = demand_categories.set_index(["commodity", "demand_category"])["final"]
        for (scenario, value_unit, category), places in wrong_sign.items():
            regions = [region for region, _ in places]
            total = pd.concat([amount for _, amount in places]).groupby(level=0).sum()
            several = len(regions) > 1
            effect = ("As the category isn't final demand, nothing reported changes." if final[commodity, category] == "no"
                      else "Final Energy reports it as the results give it.")
            notes.append(note(scenario, "", "", (
                f"{commodity}{where} doesn't add up in "
                f"{f'{len(regions)} regions, ' if several else ''}{', '.join(regions)}: "
                f"{'in each' if several else 'there'}, its output less net exports differs from its demand in the "
                "categories the 'demand_categories' rules know by twice its demand in category "
                f"{category}, with the opposite sign ({category}{' in all of them' if several else ''}: "
                f"{amounts(total)} {value_unit}). The results likely give {category} with the wrong sign; taken with "
                f"the opposite sign, {commodity} adds up {'in all of them' if several else 'there'}. {effect}"
            )))


#%% ------------------------------- ###
###     4. Carbon and OptiFlow      ###
### ------------------------------- ###

def drop_optiflow_units(long: pd.DataFrame, mapping: pd.DataFrame,
                        notes: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    """Drop the rows by which Balmorel carries OptiFlow's own results, and find the scenarios linked to OptiFlow.

    Mapping Rule 'optiflow' marks the units by which a Balmorel run linked to OptiFlow carries
    OptiFlow's emissions and fuel use. They are not Balmorel's, so they are not reported, not even
    as Primary Energy; the OptiFlow Mapping ('optiflow' rules) reports OptiFlow's results.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios.
        mapping (pd.DataFrame): The 'mapping' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, set[str]]: The long table without those rows, those
            rows, and the Balmorel scenarios linked to OptiFlow: those with such rows or with
            OptiFlow flows.
    """
    units = long.loc[long["unit_name"] != "", unit_columns].drop_duplicates().reset_index(drop=True)
    marked = units[match_mapping_rules(units, mapping) == optiflow_unit]
    carried = np.zeros(len(long), dtype=bool)
    if not marked.empty:
        carried = pd.MultiIndex.from_frame(long[unit_columns]).isin(pd.MultiIndex.from_frame(marked))

    for (scenario, quantity, value_unit), rows in long[carried].groupby(["iamc_scenario", "quantity", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        if (by_year.abs() < noise).all():
            continue
        units = ", ".join(sorted(set(rows["tech_type"] + "/" + rows["fuel"])))
        rules = ("so Primary Energy leaves it out; its 'report' rules can give it, e.g. under Primary "
                 "Energy|Biomass|Liquids" if quantity == "input"
                 else "its 'fuel' rules give the emissions of the fuels these carry")
        notes.append(note(scenario, "", "", (
            f"Not reported as Balmorel's: OptiFlow's {quantity_label(quantity)} that the results carry on units "
            f"{units}, {amounts(by_year)} {value_unit}. The OptiFlow Mapping ('optiflow' rules) reports "
            f"OptiFlow's results; {rules}."
        )))
        if quantity == "emissions" and (by_year < -noise).any():
            notes[-1]["Note"] += (
                " They are negative, so they are likely CO2 that OptiFlow stores rather than that of fuels it "
                "burns; compare them with what goes to storage, which 'report' rules can give as "
                "Carbon Capture|Geological Storage."
            )
    linked = set(long.loc[carried, "scenario"]) | set(long.loc[long["quantity"] == "flow", "scenario"])
    return long[~carried], long[carried], linked


def note_stated_units(long: pd.DataFrame, notes: list[dict]) -> None:
    """Note where the results state another unit than the one the Reader takes a quantity in.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios.
        notes (list[dict]): Conversion Notes, appended to.
    """
    stated = long[long["stated_unit"] != ""]
    for (scenario, quantity, stated_unit, value_unit), _ in stated.groupby(
            ["iamc_scenario", "quantity", "stated_unit", "value_unit"]):
        notes.append(note(scenario, "", "", (
            f"The results state '{stated_unit}' as the unit of {quantity_label(quantity)}; it is taken to be "
            f"{value_unit}, the unit Balmorel writes it in. If '{stated_unit}' is right, its values are off by "
            "the factor between the two."
        )))


def derive_capture(long: pd.DataFrame, mapping: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Derive the CO2 that units marked w/ CCS capture where the results don't give it.

    For Balmorel scenarios whose results give no captured CO2, a unit the Mapping Rules mark
    w/ CCS captures what it would emit without CCS, less what it emits: its fuel input times
    the emission factor of its fuel, less its emissions. The emission factor is fitted to the
    units without CCS that burn the fuel in the same IAMC Scenario (their emissions over their
    fuel input), and only used if it fits each of them to within balance_tolerance.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios, without OptiFlow's flows.
        mapping (pd.DataFrame): The 'mapping' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with the derived captured CO2.
    """
    burnt = long[(long["quantity"] == "input") & (long["value"] >= noise)]
    without = set(burnt["scenario"]) - set(long.loc[long["quantity"] == "captured", "scenario"])
    burnt = burnt[burnt["scenario"].isin(without)]
    if burnt.empty:
        return long

    keys = ["scenario", "year", "country", "area", "unit_name", "tech_type", "fuel"]
    emissions = long[long["quantity"] == "emissions"]
    emitted = emissions.groupby(keys)["value"].sum().rename("emitted")
    burnt = burnt.join(emitted, on=keys)
    burnt["emitted"] = burnt["emitted"].fillna(0.0)
    # Units marked w/ CCS, by the Mapping Rule that wins for their output
    output = long.loc[long["quantity"] == "output", unit_columns].drop_duplicates().reset_index(drop=True)
    ccs = output[match_mapping_rules(output, mapping).str.contains("w/ CCS", regex=False)]
    unit_keys = ["unit_name", "tech_type", "fuel"]
    burnt["ccs"] = pd.MultiIndex.from_frame(burnt[unit_keys]).isin(pd.MultiIndex.from_frame(ccs[unit_keys]))

    derived = []
    for scenario, in_scenario in burnt.groupby("iamc_scenario"):
        units_of_emissions = emissions.loc[emissions["iamc_scenario"] == scenario, "value_unit"].unique()
        if not in_scenario["ccs"].any() or len(units_of_emissions) != 1:
            continue
        emission_unit = units_of_emissions[0]
        factors, skipped, pieces = [], [], []
        for fuel, rows in in_scenario.groupby("fuel"):
            marked = rows[rows["ccs"]]
            reference = rows[~rows["ccs"]]
            if marked.empty:
                continue
            per_input = f"{emission_unit}/{rows['value_unit'].iloc[0]}"
            if reference.empty:
                skipped.append(f"{fuel} (no units without CCS burn it)")
                continue
            emission_factor = reference["emitted"].sum() / reference["value"].sum()
            expected = emission_factor * reference["value"]
            if ((reference["emitted"] - expected).abs() > balance_tolerance * expected.abs() + noise).any():
                ratios = reference["emitted"] / reference["value"]
                skipped.append(f"{fuel} (units without CCS emit {ratios.min():.5g} to {ratios.max():.5g} {per_input})")
                continue
            would_emit = emission_factor * marked["value"]
            value = would_emit - marked["emitted"]
            if (value < -(balance_tolerance * would_emit.abs() + noise)).any():
                skipped.append(f"{fuel} (units w/ CCS emit more than units without CCS would)")
                continue
            factors.append(f"{fuel} {emission_factor:.5g} {per_input}")
            pieces.append(marked.assign(quantity="captured", value=value.clip(lower=0.0), value_unit=emission_unit,
                                       stated_unit=""))

        text = ""
        if pieces:
            found = pd.concat(pieces).drop(columns=["emitted", "ccs"])
            found = found[found["value"] >= noise]
            derived.append(found)
            text = (
                "The results give no captured CO2, so that of units the Mapping Rules mark w/ CCS is derived: their "
                "fuel input times what units without CCS emit per unit of the same fuel, less their own emissions. "
                f"Emission factors: {', '.join(factors)}. Captured CO2: "
                f"{amounts(found.groupby('year')['value'].sum())} {emission_unit}."
            )
        if skipped:
            text += (f" Captured CO2 of units w/ CCS can't be derived, and is not reported, for fuels: "
                     f"{'; '.join(skipped)}.")
        notes.append(note(scenario, "", "", text.strip()))

    return pd.concat([long] + derived, ignore_index=True)


def derive_primary(long: pd.DataFrame, tables: dict[str, pd.DataFrame], notes: list[dict]) -> pd.DataFrame:
    """Add the primary energy of each unit, as its fuel's or its Mapping Rule's 'primary' says.

    A unit counts by its fuel input ('input', the default), by what it makes ('output', the
    direct equivalent, as the common definitions count nuclear and the non-biomass
    renewables), or not at all ('no', for carriers other units make, so nothing counts twice).
    The winning Mapping Rule that sets 'primary' beats the fuel's. Primary energy is per unit,
    and split_by_output splits it over the commodities the unit makes.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios, with fuel input.
        tables (dict[str, pd.DataFrame]): The rule tables.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with 'primary' rows, which have no commodity.
    """
    used = long[long["quantity"].isin(["input", "output"]) & (long["unit_name"] != "") & (long["value"] >= noise)]
    unit_keys = ["unit_name", "tech_type", "fuel"]
    units = used[unit_keys].drop_duplicates().reset_index(drop=True).assign(commodity="")
    by_rule = match_mapping_rules(units, tables["mapping"], column="primary")
    by_fuel = units["fuel"].map(tables["fuels"].set_index("fuel")["primary"]).fillna("")
    units["method"] = by_rule.where(by_rule != "", by_fuel).replace("", "input")
    units["by_rule"] = (by_rule != "") & (by_rule != by_fuel.replace("", "input"))
    used = used.merge(units.drop(columns="commodity"), on=unit_keys)

    by_input = used[(used["method"] == "input") & (used["quantity"] == "input")]
    made = used[(used["method"] == "output") & (used["quantity"] == "output")]
    columns = [column for column in long.columns if column not in ("commodity", "value")]
    by_output = made.groupby(columns, as_index=False)["value"].sum().assign(commodity="")
    primary = pd.concat((by_input, by_output), ignore_index=True).assign(quantity="primary")[long.columns]

    labels = {"output": "by what they make (direct equivalent)", "no": "not at all", "input": "by their fuel input"}
    for scenario, rows in used.groupby("iamc_scenario"):
        methods = rows[unit_keys + ["method", "by_rule"]].drop_duplicates()
        overridden = set(methods.loc[methods["by_rule"], "fuel"])
        parts = []
        for method, label in labels.items():
            chosen = methods[methods["method"] == method]
            by_fuel = sorted(set(chosen.loc[~chosen["by_rule"] & (method != "input"), "fuel"]))
            whom = [f"{fuel} (other units)" if fuel in overridden else fuel for fuel in by_fuel]
            whom = [f"units of {', '.join(whom)}"] if whom else []
            for fuel, of_fuel in chosen[chosen["by_rule"]].groupby("fuel"):
                whom.append(f"units {list_names(of_fuel['unit_name'], 3)} ({fuel})")
            if whom:
                parts.append(f"{' and '.join(whom)} {label}")
        text = ("Primary Energy is units' fuel input, split over what they make in proportion to their output "
                "(Output-Share Split).")
        if parts:
            text += (f" Instead, the 'primary' rules count {'; and '.join(parts)}, so that energy other units "
                     f"made, or waste heat, counts once.")
        notes.append(note(scenario, "", "", text))

        # Units counted by their fuel input that made something, but whose fuel input the results don't give
        counted = rows[rows["method"] == "input"]
        burning = counted.loc[counted["quantity"] == "input", unit_keys].drop_duplicates()
        output = counted[counted["quantity"] == "output"]
        missing = output[~pd.MultiIndex.from_frame(output[unit_keys]).isin(pd.MultiIndex.from_frame(burning))]
        for value_unit, lacking in missing.groupby("value_unit"):
            by_year = lacking.groupby("year")["value"].sum()
            if burning.empty:
                text = (f"The results give no fuel input, so Primary Energy only has what units count by what they "
                        f"make. Units counted by their fuel input made {amounts(by_year)} {value_unit}.")
            else:
                text = (f"Units counted by their fuel input made {amounts(by_year)} {value_unit}, but the results "
                        f"give no fuel input for them: their primary energy is not reported. Units: "
                        f"{list_names(lacking['unit_name'])}.")
            notes.append(note(scenario, "", "", text))

    return pd.concat((long, primary), ignore_index=True)


def split_by_output(long: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Split emissions, captured CO2 and primary energy over the commodities each unit makes, by its output.

    Emissions, captured CO2 and primary energy are per unit but not per commodity. A unit that
    makes several commodities, such as a CHP unit, gets them split by its output of each
    (Output-Share Split). The unit's output is looked up by its fuel, else without it. What
    units with no output have of them is left out.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with emissions, captured CO2 and primary energy per commodity.
    """
    is_per_unit = long["quantity"].isin(per_unit_quantities)
    per_unit = long[is_per_unit].drop(columns="commodity")
    long = long[~is_per_unit]
    if per_unit.empty:
        return long

    output = long[(long["quantity"] == "output") & (long["value"] >= noise)]
    keys = ["scenario", "year", "country", "area", "unit_name", "tech_type", "fuel"]
    split, left = [], per_unit
    for unit_keys in (keys, [key for key in keys if key != "fuel"]):
        made = output.groupby(unit_keys + ["commodity"], as_index=False)["value"].sum()
        made["share"] = made["value"] / made.groupby(unit_keys)["value"].transform("sum")
        matched = left.merge(made[unit_keys + ["commodity", "share"]], on=unit_keys, how="left")
        found = matched["share"].notna()
        split.append(matched[found])
        left = matched.loc[~found, per_unit.columns]
    split = pd.concat(split, ignore_index=True)
    split["value"] = split["value"] * split.pop("share")

    # Say how the split was made, and what no output could be found for
    several = split.groupby(["iamc_scenario"] + keys + ["quantity"])["commodity"].transform("nunique") > 1
    for scenario, rows in split[several].groupby("iamc_scenario"):
        commodities = " and ".join(sorted(set(rows["commodity"])))
        notes.append(note(scenario, "", "", (
            "Emissions, captured CO2 and primary energy are per unit, not per commodity: for units that make "
            f"several commodities ({commodities}), they are split over them in proportion to the unit's output of "
            "each (Output-Share Split)."
        )))
    for (scenario, quantity, value_unit), rows in left.groupby(["iamc_scenario", "quantity", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        same = per_unit[(per_unit["iamc_scenario"] == scenario) & (per_unit["quantity"] == quantity)]
        total = same["value"].abs().groupby(same["year"]).sum().reindex(by_year.index)
        by_year = by_year[by_year.abs() >= noise + relative_noise * total]
        if by_year.empty:
            continue
        notes.append(note(scenario, "", "", (
            f"Units whose output the results don't give had {quantity_label(quantity)} of {amounts(by_year)} "
            f"{value_unit}; not reported, as it can't be split over commodities. Units: "
            f"{list_names(rows['unit_name'])}."
        )))

    split = split[split["value"].abs() >= noise]
    return pd.concat((long, split), ignore_index=True)


def pool_shares(flows: pd.DataFrame, optiflow: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Find the Stored Share of each CO2 pool of the OptiFlow Mapping.

    A pool's Stored Share is the CO2 its 'store' rules take out of it over the CO2 its 'balmorel'
    and 'capture' rules bring in, summed over all countries, per IAMC Scenario and year. A share
    above 1 is taken as 1.

    Args:
        flows (pd.DataFrame): OptiFlow flows (quantity 'flow') with IAMC Scenarios.
        optiflow (pd.DataFrame): The 'optiflow' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: Columns iamc_scenario, year, pool, share (NaN where nothing enters the
            pool) and balmorel (the CO2 'balmorel' rules bring in, in Mt CO2/yr).
    """
    matched = match_optiflow_rules(flows, optiflow)
    matched = matched[matched["role"].isin(pool_roles)]
    if matched.empty:
        return pd.DataFrame({"iamc_scenario": pd.Series(dtype=object), "year": pd.Series(dtype=int),
                             "pool": pd.Series(dtype=object), "share": pd.Series(dtype=float),
                             "balmorel": pd.Series(dtype=float)})

    factors = {unit: factor(unit, carbon_unit) for unit in matched["value_unit"].unique()}
    matched = matched.assign(value=matched["value"] * matched["value_unit"].map(factors))
    by_role = matched.groupby(["iamc_scenario", "year", "pool", "role"])["value"].sum().unstack("role", fill_value=0.0)
    by_role = by_role.reindex(columns=list(pool_roles), fill_value=0.0)
    entering = by_role["balmorel"] + by_role["capture"]
    shares = pd.DataFrame({
        "share": by_role["store"] / entering.where(entering >= noise),
        "balmorel": by_role["balmorel"],
    }).reset_index()

    for (scenario, pool), rows in shares.groupby(["iamc_scenario", "pool"]):
        by_year = rows.set_index("year")["share"]
        text = (f"OptiFlow stores {amounts(by_year.dropna())} of the CO2 entering pool '{pool}' (Stored Share, all "
                "countries)." if by_year.notna().any() else f"OptiFlow's pool '{pool}' has no Stored Share.")
        if (by_year > 1 + balance_tolerance).any():
            text += (" Where above 1, more leaves the pool for storage than its 'balmorel' and 'capture' rules "
                     "bring in, and 1 is taken: some flow into the pool has no rule.")
        if by_year.isna().any():
            text += f" Nothing enters it in {', '.join(str(year) for year in by_year.index[by_year.isna()])}."
        notes.append(note(scenario, "", "", text))
    shares["share"] = shares["share"].clip(upper=1.0)
    return shares[["iamc_scenario", "year", "pool", "share", "balmorel"]]


def check_fuel_rules(carried: pd.DataFrame, flows: pd.DataFrame, optiflow: pd.DataFrame, notes: list[dict]) -> None:
    """Compare the CO2 the 'fuel' rules give with the emissions the results carry for OptiFlow.

    A 'fuel' rule gives the CO2 of a fossil fuel OptiFlow burns, as the fuel's flow times the
    rule's factor. Balmorel's results carry the CO2 of those fuels on the units Mapping Rule
    'optiflow' marks, so per IAMC Scenario and year, summed over all countries, the two should
    match. Only done if there are 'fuel' rules.

    Args:
        carried (pd.DataFrame): The rows drop_optiflow_units dropped.
        flows (pd.DataFrame): OptiFlow flows (quantity 'flow') with IAMC Scenarios.
        optiflow (pd.DataFrame): The 'optiflow' rule table.
        notes (list[dict]): Conversion Notes, appended to.
    """
    if not (optiflow["role"] == "fuel").any():
        return
    unitless = optiflow[(optiflow["role"] == "fuel") & ~optiflow["unit"].map(
        lambda unit: unit == carbon_unit or (unit, carbon_unit) in unit_factors)]
    if not unitless.empty:
        raise Exception(
            f"'optiflow' rules of role 'fuel' need a unit of CO2, e.g. 'Mt CO2': the unit of their flows times "
            f"their factor.\n{unitless.to_string()}"
        )

    def in_carbon_unit(rows: pd.DataFrame) -> pd.Series:
        return rows["value"] * rows["value_unit"].map(lambda unit: factor(unit, carbon_unit))

    matched = match_optiflow_rules(flows, optiflow)
    fuels = matched[matched["role"] == "fuel"]
    fuels = fuels.assign(value=in_carbon_unit(fuels))
    emissions = carried[carried["quantity"] == "emissions"]
    emissions = emissions.assign(value=in_carbon_unit(emissions))

    for scenario in sorted(set(fuels["iamc_scenario"]) | set(emissions["iamc_scenario"])):
        given = fuels[fuels["iamc_scenario"] == scenario].groupby("year")["value"].sum()
        held = emissions[emissions["iamc_scenario"] == scenario].groupby("year")["value"].sum()
        given, held = given.align(held, fill_value=0.0)
        text = (f"The 'fuel' rules give OptiFlow's fossil fuels {amounts(given)} {carbon_unit}; the results carry "
                f"{amounts(held)} {carbon_unit} for OptiFlow (all countries).")
        if ((given - held).abs() > balance_tolerance * held.abs() + noise).any():
            text += " They differ: a fossil fuel may lack a 'fuel' rule, or have a factor that is off."
        unreported = fuels[(fuels["iamc_scenario"] == scenario) & (fuels["emissions"] == "")]
        if (unreported["value"].abs() >= noise).any():
            edges = unreported["from_process"] + " -> " + unreported["to_process"]
            text += (f" Not reported, as their rules give no emissions variable: {list_names(edges)}, "
                     f"{amounts(unreported.groupby('year')['value'].sum())} {carbon_unit}.")
        notes.append(note(scenario, "", "", text))


def net_emissions(long: pd.DataFrame, shares: pd.DataFrame, linked: set[str], tables: dict[str, pd.DataFrame],
                  notes: list[dict]) -> pd.DataFrame:
    """Count the stored part of the CO2 that units capture from biomass as negative emissions and as removal.

    Emissions are kept as the results give them, but for negative emissions of biomass (Fuel
    Category Biomass) on units that capture CO2: the stored part of the CO2 they capture from
    biomass takes their place, as negative emissions and as removal ('removal' rows). For
    scenarios not linked to OptiFlow, all CO2 units capture counts as stored ('stored' rows,
    and 'removal' rows for biomass); the OptiFlow Mapping reports storage for the linked ones,
    whose 'report' rules can give it. For linked ones, the Stored
    Share of the pools its 'balmorel' rules bring it into does, weighed by how much they bring
    into each. Where the OptiFlow Mapping gives no share, those rows are withheld, and the
    IAMC Variables they count towards are left empty.

    Args:
        long (pd.DataFrame): The long table after demand is selected, with Area Kinds.
        shares (pd.DataFrame): The pools' Stored Shares, from pool_shares.
        linked (set[str]): Balmorel scenarios linked to OptiFlow.
        tables (dict[str, pd.DataFrame]): The rule tables.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with a 'withheld' column and the rows for stored CO2.
    """
    categories = tables["fuels"].set_index("fuel")["category"]
    long = long.assign(withheld=False)
    emissions = long["quantity"] == "emissions"
    captured = long["quantity"] == "captured"

    for scenario in sorted(set(long.loc[emissions, "iamc_scenario"]) - set(long.loc[captured, "iamc_scenario"])):
        notes.append(note(scenario, "", "", (
            "The results give no captured CO2: Carbon Capture and Carbon Removal are not reported, and emissions "
            "are reported as the results give them. If units captured CO2 from biomass and stored it (BECCS), "
            "that removal is missing."
        )))

    # Units that capture CO2 but whose output isn't marked w/ CCS
    capturing = long[captured & (long["value"].abs() >= noise)]
    units = capturing[["iamc_scenario"] + unit_columns].drop_duplicates().reset_index(drop=True)
    unmarked = units[~match_mapping_rules(units, tables["mapping"]).str.contains("w/ CCS", regex=False)]
    for scenario, rows in unmarked.groupby("iamc_scenario"):
        notes.append(note(scenario, "", "", (
            "Units capture CO2, but the Mapping Rules don't mark them w/ CCS (by default, units with 'CCS' in "
            f"their name), so their output is reported w/o CCS: {list_names(rows['unit_name'])}."
        )))

    # Negative emissions of biomass the results give make way for the stored part of captured CO2
    keys = ["scenario", "year", "country", "area"] + unit_columns
    on_capture = pd.MultiIndex.from_frame(long[keys]).isin(pd.MultiIndex.from_frame(long.loc[captured, keys]))
    biogenic = long["fuel"].map(categories) == biogenic_category
    replaced = emissions & biogenic & on_capture & (long["value"] < 0)
    for (scenario, value_unit), rows in long[replaced].groupby(["iamc_scenario", "value_unit"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        notes.append(note(scenario, "", "", (
            f"The results give negative emissions of biomass on units that capture CO2, {amounts(by_region.sum())} "
            f"{value_unit} in {list_regions(by_region.index)}; minus the stored part of the CO2 they capture "
            "from biomass is reported instead."
        )))

    # The share of CO2 captured from biomass that is stored
    stored = long[captured & biogenic & (long["value"].abs() >= noise)]
    entering = shares[shares["balmorel"] > 0].assign(weighted=lambda rows: rows["share"] * rows["balmorel"])
    by_share = entering.groupby(["iamc_scenario", "year"], as_index=False)[["weighted", "balmorel"]].sum()
    by_share["share"] = by_share.pop("weighted") / by_share["balmorel"]
    brought = by_share.set_index(["iamc_scenario", "year"])["balmorel"]
    stored = stored.merge(by_share.drop(columns="balmorel"), on=["iamc_scenario", "year"], how="left")
    is_linked = stored["scenario"].isin(linked)
    stored["share"] = stored["share"].where(is_linked, 1.0)
    withheld = stored["share"].isna()
    value = stored["value"] * stored.pop("share").fillna(0.0)

    # Without OptiFlow, nothing uses captured CO2: it is all stored
    into_storage = long[captured & ~long["scenario"].isin(linked) & (long["value"].abs() >= noise)]
    for (scenario, value_unit), rows in into_storage.groupby(["iamc_scenario", "value_unit"]):
        text = (f"Not linked to OptiFlow, so all CO2 that units capture is taken to be stored: "
                f"{amounts(rows.groupby('year')['value'].sum())} {value_unit}")
        from_biomass = stored[~is_linked & (stored["iamc_scenario"] == scenario)
                              & (stored["value_unit"] == value_unit)].groupby("year")["value"].sum()
        if not from_biomass.empty:
            text += f", of which from biomass, so removed: {amounts(from_biomass)} {value_unit}"
        notes.append(note(scenario, "", "", text + "."))
    for (scenario, value_unit), rows in stored[withheld].groupby(["iamc_scenario", "value_unit"]):
        by_region = per_region(rows)
        notes.append(note(scenario, "", "", (
            "Linked to OptiFlow, but the OptiFlow Mapping ('optiflow' rules) gives no share stored of the CO2 "
            f"that units capture from biomass: {amounts(by_region.sum())} {value_unit} in "
            f"{list_regions(by_region.index)}. Carbon Removal, and the emissions it counts towards, are left "
            "empty there; emissions of other fuels are reported."
        )))
    # The CO2 captured from biomass should be what the 'balmorel' rules bring into the pools
    known = stored[is_linked & ~withheld]
    for scenario, rows in known.groupby("iamc_scenario"):
        factors = rows["value_unit"].map(lambda unit: factor(unit, carbon_unit))
        captured_by_year = (rows["value"] * factors).groupby(rows["year"]).sum()
        brought_by_year = brought[scenario].reindex(captured_by_year.index)
        share_by_year = (by_share[by_share["iamc_scenario"] == scenario].set_index("year")["share"]
                         .reindex(captured_by_year.index))
        text = (f"Of the CO2 that units capture from biomass, the share stored in OptiFlow is taken: "
                f"{amounts(share_by_year)}.")
        if ((captured_by_year - brought_by_year).abs() > balance_tolerance * captured_by_year.abs()).any():
            text += (f" But units captured {amounts(captured_by_year)} {carbon_unit}, while the 'balmorel' rules "
                     f"bring {amounts(brought_by_year)} {carbon_unit} into the pools: check those rules.")
        notes.append(note(scenario, "", "", text))

    negative = stored.assign(quantity="emissions", value=-value, withheld=withheld)
    removal = stored.assign(quantity="removal", value=value, withheld=withheld)
    into_storage = into_storage.assign(quantity="stored")
    return pd.concat((long[~replaced], negative, removal, into_storage), ignore_index=True)


def report_optiflow(flows: pd.DataFrame, optiflow: pd.DataFrame, shares: pd.DataFrame, stems: pd.DataFrame,
                    names: set[str], notes: list[dict]) -> pd.DataFrame:
    """Report OptiFlow's results as the OptiFlow Mapping says.

    'capture' rules report the CO2 OptiFlow captures under their variable, and the stored part
    of it, by its pool's Stored Share, under removal and, negative, under emissions. 'fuel'
    rules report the CO2 of a fossil fuel under emissions. 'report' rules report the flow as it
    is under their variable. Flows are times the rule's factor. Each sums up to the longest
    stem of the 'stems' rules its variable starts with, if there is one, and counts towards the
    broadest total of the 'stems' rules that is its variable or above it (copy_to_aggregates),
    e.g. 'Final Energy|Bunkers|Hydrogen' towards Final Energy. A rule's note becomes a
    Conversion Note on each IAMC Variable it reports values under.

    Args:
        flows (pd.DataFrame): OptiFlow flows with IAMC Regions.
        optiflow (pd.DataFrame): The 'optiflow' rule table.
        shares (pd.DataFrame): The pools' Stored Shares, from pool_shares.
        stems (pd.DataFrame): The 'stems' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: Reported rows (quantity optiflow_quantity) with the columns
            copy_to_aggregates and sum_to_variables need.
    """
    columns = ["iamc_scenario", "scenario", "region", "quantity", "stem", "path", "variable", "value_unit", "year",
               "value", "withheld", "template_stem", "source_path", "stem_total"]
    if not (optiflow["priority"] == 1).any():
        shipped = list_names(optiflow["variable"][optiflow["variable"] != ""])
        for scenario in sorted(set(flows["iamc_scenario"])):
            notes.append(note(scenario, "", "", (
                "Linked to OptiFlow, but no OptiFlow Mapping ('optiflow' rules) was given: of OptiFlow's results, "
                f"only what the rules shipped with pybalmorel cover is reported ({shipped or 'nothing'}). Pass the "
                "study's with rules={'optiflow': ...}."
            )))
    matched = match_optiflow_rules(flows, optiflow)
    matched = matched.merge(shares[["iamc_scenario", "year", "pool", "share"]], on=["iamc_scenario", "year", "pool"],
                            how="left")

    reported = []
    for target in ("variable", "removal", "emissions"):
        rows = matched[matched[target] != ""]
        # The stored part of captured CO2 is removal, and negative emissions
        stored = (rows["role"] == "capture") & (target != "variable")
        share = rows["share"].where(stored, 1.0)
        sign = np.where(stored & (target == "emissions"), -1.0, 1.0)
        reported.append(rows.assign(variable=rows[target], value=sign * rows["value"] * share.fillna(0.0),
                                    withheld=share.isna()))
    reported = pd.concat(reported, ignore_index=True)

    for (scenario, variable), _ in reported[~reported["variable"].isin(names)].groupby(["iamc_scenario", "variable"]):
        notes.append(note(scenario, "", variable, (
            "The OptiFlow Mapping reports OptiFlow results under this IAMC Variable, which is not in the "
            "Definitions Snapshot; not reported."
        )))
    reported = reported[reported["variable"].isin(names)]
    noted = reported[(reported["note"] != "") & (reported["value"].abs() >= noise)]
    for (scenario, variable, text), _ in noted.groupby(["iamc_scenario", "variable", "note"]):
        notes.append(note(scenario, "", variable, text))

    by_length = sorted(set(stems["stem"]), key=len, reverse=True)
    stem_of = {
        variable: next((stem for stem in by_length if variable == stem or variable.startswith(f"{stem}|")), variable)
        for variable in reported["variable"].unique()
    }
    by_breadth = sorted(set(stems["total"]) - {""}, key=len)
    total_of = {
        variable: next((total for total in by_breadth if variable == total or variable.startswith(f"{total}|")), "")
        for variable in reported["variable"].unique()
    }
    reported = reported.assign(stem=reported["variable"].map(stem_of), stem_total=reported["variable"].map(total_of),
                               quantity=optiflow_quantity, template_stem="", source_path="")
    reported["path"] = [variable[len(stem) + 1:] for variable, stem in zip(reported["variable"], reported["stem"])]
    return reported.reindex(columns=columns)


#%% ------------------------------- ###
###     5. Stems and Segments       ###
### ------------------------------- ###

def attach_stems(long: pd.DataFrame, stems: pd.DataFrame, names: set[str],
                 notes: list[dict]) -> pd.DataFrame:
    """Add the stem of each row, leaving out quantities and commodities without one.

    A stem row's note becomes a Conversion Note in every IAMC Scenario with values under its
    stem. A stem with the Source placeholder, e.g. 'Primary Energy|{source}|Electricity', is
    filled in by attach_segments, which also gives its note.

    Args:
        long (pd.DataFrame): The long table with Area Kinds.
        stems (pd.DataFrame): The 'stems' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows with a stem, with 'stem' and 'stem_note' columns.
    """
    long = match_stems(long, stems, names, notes)
    templated = long["stem"].str.contains(source_placeholder, regex=False)
    kept = long["stem"].isin(names) | templated
    noted = long["stem"].isin(names) & (long["stem_note"] != "") & (long["value"].abs() >= noise)
    for (scenario, stem, text), _ in long[noted].groupby(["iamc_scenario", "stem", "stem_note"]):
        notes.append(note(scenario, "", stem, text))
    return long.assign(stem_note=long["stem_note"].where(templated, ""))[kept]


def match_stems(long: pd.DataFrame, stems: pd.DataFrame, names: set[str], notes: list[dict]) -> pd.DataFrame:
    """Find the stem of each row, and note rows without one and stems the snapshot lacks.

    A stem row for the row's Area Kind beats one for any Area Kind.

    Args:
        long (pd.DataFrame): The long table with Area Kinds.
        stems (pd.DataFrame): The 'stems' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with 'stem' ('' for none), 'stem_note' and 'stem_total'
            columns.
    """
    for_kind = stems[stems["area_kind"] != ""].rename(columns={"note": "stem_note", "total": "stem_total"})
    for_any = stems[stems["area_kind"] == ""].drop(columns="area_kind").rename(
        columns={"stem": "stem_any", "note": "stem_note_any", "total": "stem_total_any"})
    long = long.merge(for_kind, on=["quantity", "commodity", "area_kind"], how="left")
    long = long.merge(for_any, on=["quantity", "commodity"], how="left")
    chosen = long["stem"].notna()
    long["stem"] = long["stem"].fillna(long.pop("stem_any")).fillna("")
    long["stem_note"] = long.pop("stem_note").where(chosen, long.pop("stem_note_any")).fillna("")
    long["stem_total"] = long.pop("stem_total").where(chosen, long.pop("stem_total_any")).fillna("")

    # Name the Area Kind only where the stems tell kinds apart. Prices without a stem go unnoted:
    # they say nothing of what is left out of a reported total.
    unreported = long[(long["stem"] == "") & ~long["quantity"].isin(mean_quantities)]
    kind_specific = for_kind.set_index(["quantity", "commodity"]).index
    by_kind = unreported.set_index(["quantity", "commodity"]).index.isin(kind_specific) & (unreported["area_kind"] != "")
    unreported = unreported.assign(where=np.where(by_kind, " in " + unreported["area_kind"] + " areas", ""))
    for (scenario, quantity, commodity, where, value_unit), rows in unreported.groupby(
            ["iamc_scenario", "quantity", "commodity", "where", "value_unit"]):
        what = f"{quantity_label(quantity)} of {commodity}{where}"
        by_region = per_region(rows)
        if by_region.empty:
            continue
        text = (f"Not reported, as the 'stems' rules have no row for it: {what}, "
                f"{amounts(by_region.sum())} {value_unit} in {list_regions(by_region.index)}.")
        if quantity == "primary":
            text += f" Fuels: {list_names(rows.loc[rows['value'].abs() >= noise, 'fuel'])}."
        notes.append(note(scenario, "", "", text))

    templated = long["stem"].str.contains(source_placeholder, regex=False)
    lacking = (long["stem"] != "") & ~long["stem"].isin(names) & ~templated
    for (scenario, stem), _ in long[lacking].groupby(["iamc_scenario", "stem"]):
        notes.append(note(scenario, "", stem, "This stem is not in the Definitions Snapshot; not reported."))
    return long


def attach_sectors(long: pd.DataFrame, demand_categories: pd.DataFrame, names: set[str],
                   notes: list[dict]) -> pd.DataFrame:
    """Copy final demand in categories with a Final Energy Sector to the sector's IAMC Variables.

    Each copy takes one of the sector's variables (sector_variables) as its stem, so it counts
    towards that variable only, while the demand still counts under its own stem, e.g.
    'Final Energy|Electricity', and towards the stem's total (e.g. Final Energy) once. A
    category's note becomes a Conversion Note on each sector variable with values under it.

    Args:
        long (pd.DataFrame): The long table with stems.
        demand_categories (pd.DataFrame): The 'demand_categories' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with the copies added.
    """
    with_sector = demand_categories.loc[demand_categories["sector"] != "",
                                        ["commodity", "demand_category", "sector", "note"]]
    demand = long[long["quantity"] == "demand"].merge(with_sector, on=["commodity", "demand_category"])
    copies = [
        rows.assign(stem=variable, stem_total="")
        for (stem, sector), rows in demand.groupby(["stem", "sector"])
        for variable in sector_variables(stem, sector)
    ]
    if not copies:
        return long
    copies = pd.concat(copies, ignore_index=True)

    for (scenario, stem), _ in copies[~copies["stem"].isin(names)].groupby(["iamc_scenario", "stem"]):
        notes.append(note(scenario, "", stem, (
            "The 'demand_categories' rules report a Final Energy Sector under this IAMC Variable, which is not in "
            "the Definitions Snapshot; not reported."
        )))
    copies = copies[copies["stem"].isin(names)]
    noted = copies[(copies["note"] != "") & (copies["value"].abs() >= noise)]
    for (scenario, stem, text), _ in noted.groupby(["iamc_scenario", "stem", "note"]):
        notes.append(note(scenario, "", stem, text))
    return pd.concat((long, copies.drop(columns=["sector", "note"])), ignore_index=True)


def attach_segments(long: pd.DataFrame, tables: dict[str, pd.DataFrame], names: set[str],
                    notes: list[dict]) -> pd.DataFrame:
    """Add the IAMC Variable each row is reported under.

    'path' holds the segments the Mapping Rules give, and 'variable' the longest of its
    prefixes in the snapshot, or '<stem>|Other' when even its first segment is missing. Rows
    without a unit skip the Mapping Rules: demand, trade and net imports are reported under the
    stem itself, and heat Heat Exchange could trace to no unit under Other.

    In a stem with the Source placeholder, e.g. 'Primary Energy|{source}|Electricity', the
    first segment is the Source and fills it in (fill_source): 'Gas|w/ CCS' is reported under
    'Primary Energy|Gas|Electricity|w/ CCS', and 'Wind|Onshore' under 'Primary Energy|Wind', as
    the common definitions don't split wind by what it makes. A Source the stem has no IAMC
    Variable for goes to Other, but where the snapshot has the Source under the stem's top
    (e.g. 'Primary Energy|Gas' for 'Primary Energy|{source}|Heat'), the row counts only towards
    that variable and the totals above it if the stem has a total (stems.csv), and is not
    reported if it hasn't, as that variable would count use beyond Balmorel.

    Args:
        long (pd.DataFrame): The long table with stems.
        tables (dict[str, pd.DataFrame]): The rule tables.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The reported rows, with 'category', 'path' and 'variable' columns, and for
            rows under a stem with the Source placeholder, the stem as the rules give it
            ('template_stem') and the segments before the Source was taken off ('source_path');
            '' for other rows.
    """
    categories = tables["fuels"].set_index("fuel")["category"]
    has_unit = long["unit_name"] != ""
    long = long.assign(category=long["fuel"].map(categories))
    long["reason"] = ""
    long.loc[has_unit & long["category"].isna(), "reason"] = "fuel has no Fuel Category"
    long["category"] = long["category"].fillna("Other")

    # Match rules once per unit, not per row
    units = long.loc[has_unit, unit_columns].drop_duplicates().reset_index(drop=True)
    units["template"] = match_mapping_rules(units, tables["mapping"])
    long = long.merge(units, on=unit_columns, how="left")
    long = long[long["template"] != not_reported].copy()

    no_unit = long["unit_name"] == ""
    unmatched = ~no_unit & (long["template"] == "")
    long.loc[unmatched, "reason"] = "no Mapping Rule matches"
    long.loc[unmatched, "template"] = "Other"
    under_stem = no_unit & long["quantity"].isin(["demand", "trade", "imports"])
    long.loc[under_stem, "template"] = ""
    long.loc[no_unit & ~under_stem, "template"] = "Other"
    long.loc[no_unit & ~under_stem, "reason"] = "Heat Exchange traced it to no unit"
    long["path"] = [
        template.replace("{category}", category)
        for template, category in zip(long["template"], long["category"])
    ]
    long = fill_sources(long, names, notes)

    resolved = long[["stem", "path"]].drop_duplicates()
    resolved["variable"] = [resolve(stem, path, names) for stem, path in zip(resolved["stem"], resolved["path"])]
    long = long.merge(resolved, on=["stem", "path"], how="left")

    # Note what went into Other, and why. Not for stems without children, nor for the total only
    # where an aggregate (e.g. Fossil) takes the row, nor for the Source's own variable, which
    # has no variable by use to go to (e.g. 'Primary Energy|Gas' for 'w/o CCS')
    at_source = long["template_stem"].str.endswith(f"|{source_placeholder}")
    other = long[(long["path"] != "")
                 & ((long["variable"] == long["stem"] + "|Other")
                    | ((long["variable"] == long["stem"]) & ~at_source))].copy()
    with_children = {stem for stem in other["stem"].unique() if any(name.startswith(f"{stem}|") for name in names)}
    pairs = other[["stem", "path"]].drop_duplicates()
    aggregated = {(stem, path) for stem, path in pairs.itertuples(index=False)
                  if aggregates_of(stem, path, names, tables["aggregates"])}
    in_aggregate = pd.Series([pair in aggregated for pair in zip(other["stem"], other["path"])], index=other.index)
    other = other[other["stem"].isin(with_children) & ~((other["variable"] == other["stem"]) & in_aggregate)]
    # Sources that went to Other, by the segments the Mapping Rules gave
    other = pd.concat((other, long[long["source_kind"] == "Other"].assign(path=lambda rows: rows["source_path"])))
    first_segment = other["path"].str.split("|").str[0]
    other.loc[(other["reason"] == "") & (first_segment == "Other"), "reason"] = "Fuel Category Other"
    other.loc[other["reason"] == "", "reason"] = "no such IAMC Variable"
    # One note per variable, as where a unit goes depends on its name, type and fuel, not its region
    for (scenario, variable), rows in other.groupby(["iamc_scenario", "variable"]):
        what = [
            f"{tech_type}/{fuel} ({reason}: '{path}')" if reason == "no such IAMC Variable"
            else f"{tech_type}/{fuel} ({reason})" if tech_type or fuel
            else f"heat ({reason})"
            for tech_type, fuel, path, reason in rows[["tech_type", "fuel", "path", "reason"]]
            .drop_duplicates().sort_values(["tech_type", "fuel", "path"]).itertuples(index=False)
        ]
        where = "Other" if variable.endswith("|Other") else "the total only, as there is no Other"
        notes.append(note(scenario, "", variable,
                          f"Reported under {where} in {list_regions(rows['region'])}: {'; '.join(what)}."))

    return long.drop(columns=["template", "reason", "source_kind"])


def fill_sources(long: pd.DataFrame, names: set[str], notes: list[dict]) -> pd.DataFrame:
    """Fill the Source into stems with the Source placeholder, taking it off the path.

    See attach_segments. Gives the notes of those stems' rows (attach_stems leaves them), and
    of what is not reported.

    Args:
        long (pd.DataFrame): The long table with stems and paths, and the 'stem_note' and
            'reason' columns.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows still reported, without 'stem_note', with 'template_stem' (for
            rows that count towards the totals only, '<top>|{source}'), 'source_path' and
            'source_kind' ('Other' for rows that went to Other, else '').
    """
    templated = long["stem"].str.contains(source_placeholder, regex=False)
    long = long.assign(template_stem=long["stem"].where(templated, ""), stem_rule=long["stem"],
                       source_path=long["path"].where(templated, ""), source_kind="")
    outcomes = []
    for stem, path, total in long.loc[templated, ["stem", "path", "stem_total"]].drop_duplicates().itertuples(
            index=False):
        source, _, rest = path.partition("|")
        top = stem_top(stem)
        filled = fill_source(stem, source, names)
        if filled:
            kind = "Other" if source == "Other" else ""
            outcomes.append((stem, path, total, stem, filled,
                             rest if filled == stem.replace(source_placeholder, source) else "", kind))
        elif f"{top}|{source}" in names and total:
            # Towards the Source's own variable and the totals only, as if the stem had no use
            outcomes.append((stem, path, total, f"{top}|{source_placeholder}", f"{top}|{source}", rest, "totals only"))
        elif f"{top}|{source}" in names:
            outcomes.append((stem, path, total, stem, "", "", "beyond"))
        else:
            other = fill_source(stem, "Other", names)
            outcomes.append((stem, path, total, stem, other, "", "Other" if other else "no Other"))
    if not outcomes:
        return long.drop(columns=["stem_note", "stem_rule"])
    outcomes = pd.DataFrame(outcomes,
                            columns=["stem", "path", "stem_total", "source_template", "filled", "rest", "kind"])
    long = long.merge(outcomes, on=["stem", "path", "stem_total"], how="left")
    filled = long["filled"].notna()
    long.loc[filled, "template_stem"] = long.loc[filled, "source_template"]
    long.loc[filled, "stem"] = long.loc[filled, "filled"]
    long.loc[filled, "path"] = long.loc[filled, "rest"]
    long.loc[filled, "source_kind"] = long.loc[filled, "kind"].where(long.loc[filled, "kind"] == "Other", "")

    # What has no IAMC Variable to go to, or counts towards the totals only
    dropped = long[long["kind"].isin(["beyond", "no Other", "totals only"])]
    for (scenario, stem, source_path, kind, quantity, value_unit), rows in dropped.groupby(
            ["iamc_scenario", "stem_rule", "source_path", "kind", "quantity", "value_unit"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        source = source_path.split("|")[0]
        missing = stem.replace(source_placeholder, source)
        top = stem_top(stem)
        units = ", ".join(f"{tech_type}/{fuel}" for tech_type, fuel in
                          rows[["tech_type", "fuel"]].drop_duplicates().itertuples(index=False))
        what = (f"{quantity_label(quantity)} of {units}, {amounts(by_region.sum())} {value_unit} in "
                f"{list_regions(by_region.index)}")
        if kind == "totals only":
            text = (f"Counted only towards '{top}|{source}' and the totals above it, as the Definitions Snapshot has "
                    f"no '{missing}': {what}.")
        else:
            why = (f"'{top}|{source}' would count use of {source} that Balmorel doesn't cover" if kind == "beyond"
                   else "it has no Other either")
            text = f"Not reported, as the Definitions Snapshot has no '{missing}', and {why}: {what}."
        notes.append(note(scenario, "", "", text))
    long = long[long["stem"] != ""]

    # A stem with nothing below the Source has no variable by use, so its note goes to the total
    noted = (long["template_stem"] != "") & (long["stem_note"] != "") & (long["value"].abs() >= noise)
    for (scenario, stem, rule, total, text), _ in long[noted].groupby(
            ["iamc_scenario", "stem", "stem_rule", "stem_total", "stem_note"]):
        at_total = total and rule.endswith(f"|{source_placeholder}")
        notes.append(note(scenario, "", total if at_total else stem, text))
    return long.drop(columns=["stem_note", "stem_rule", "source_template", "filled", "rest", "kind"])


def resolve(stem: str, path: str, names: set[str]) -> str:
    """Find the IAMC Variable that output with the given stem and segments is reported under.

    Args:
        stem (str): The stem, e.g. 'Secondary Energy|Electricity'.
        path (str): Segments below it, e.g. 'Wind|Onshore|w/o CCS'.
        names (set[str]): IAMC Variables in the Definitions Snapshot.

    Returns:
        str: The stem if the path is empty. Else the longest prefix of '<stem>|<path>' in
            `names` that keeps at least one segment, else '<stem>|Other', else the stem.
    """
    if path == "":
        return stem
    segments = path.split("|")
    for length in range(len(segments), 0, -1):
        candidate = "|".join([stem] + segments[:length])
        if candidate in names:
            return candidate
    return f"{stem}|Other" if f"{stem}|Other" in names else stem


#%% ------------------------------- ###
###         6. Backup Units         ###
### ------------------------------- ###

def treat_backup_units(long: pd.DataFrame, backup_units: str, backup_pattern: str,
                       notes: list[dict]) -> pd.DataFrame:
    """Drop backup units' capacity, and report or drop the rest of what they do, noting the amounts.

    Args:
        long (pd.DataFrame): The long table with variables.
        backup_units (str): 'supply' reports their output, emissions and captured CO2;
            'exclude' leaves them out.
        backup_pattern (str): Regular expression marking backup units by name.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows still reported.
    """
    backup = long["unit_name"].str.contains(backup_pattern, regex=True)
    capacity = long["quantity"] == "capacity"

    supply = backup_units == "supply"
    for (scenario, quantity, variable, value_unit), rows in long[backup & ~capacity].groupby(
            ["iamc_scenario", "quantity", "variable", "value_unit"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        if quantity == "output":
            what, treatment = "Backup units produced", "counted as supply" if supply else "left out"
        else:
            what, treatment = f"Backup units' {quantity_label(quantity)} came to", "reported" if supply else "left out"
        notes.append(note(scenario, "", variable, (
            f"{what} {amounts(by_region.sum())} {value_unit} in {list_regions(by_region.index)}; {treatment}."
        )))

    leave_out = backup & capacity if supply else backup
    return long[~leave_out]


#%% ------------------------------- ###
###            7. Prices            ###
### ------------------------------- ###

def report_prices(prices: pd.DataFrame, tables: dict[str, pd.DataFrame], regions: pd.DataFrame,
                  variables: pd.DataFrame, currency: dict[str, float] | None, notes: list[dict]) -> pd.DataFrame:
    """Report prices per IAMC Region, in the currencies the IAMC units are in.

    A country's price is the mean of its regions' or areas' prices weighted by the demand they
    hold for. Where none holds any, there is no price, as the LP's marginal cost of a demand that
    doesn't exist is no market price. The carbon price comes from the CO2 tax units pay
    (derive_carbon_price). Prices are reported under their stem, in the unit the snapshot gives
    it, if `currency` values Balmorel's money (balmorel_currency) in that unit's currency, or
    else pybalmorel's price-level tables do (table_worth). Conversion Notes name the countries
    without demand, those whose price takes in an average price beyond ±price_bound, the worth
    the tables gave, and the prices no worth was found for.

    Args:
        prices (pd.DataFrame): Rows of quantity 'price' (with 'weight'), 'tax' and 'emissions'
            from the long table, with IAMC Scenarios.
        tables (dict[str, pd.DataFrame]): The rule tables.
        regions (pd.DataFrame): The snapshot's regions (region, iso3).
        variables (pd.DataFrame): The snapshot's variables (variable, unit).
        currency (dict[str, float] | None): What one unit of Balmorel's money is worth, per
            currency, as in to_iamc; one balmorel_currency is always worth 1 of itself. It beats
            the price-level tables.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: Reported rows with the columns sum_to_variables needs, each its own
            variable.
    """
    columns = ["iamc_scenario", "region", "stem", "path", "variable", "value_unit", "year", "value"]
    prices = name_regions(prices, tables["countries"], regions, notes)
    carbon_prices = derive_carbon_price(prices, notes)
    prices = pd.concat((prices[prices["quantity"] == "price"].dropna(subset="value"), carbon_prices), ignore_index=True)
    if prices.empty:
        return pd.DataFrame(columns=columns)
    prices = attach_area_kinds(prices.assign(to_area=prices["to_area"].fillna("")), tables["areas"])

    names = set(variables["variable"])
    prices = match_stems(prices, tables["stems"], names, notes)
    prices = prices[prices["stem"].isin(names)]
    for (scenario, stem, text), _ in prices[prices["stem_note"] != ""].groupby(["iamc_scenario", "stem", "stem_note"]):
        notes.append(note(scenario, "", stem, text))
    if prices.empty:
        return pd.DataFrame(columns=columns)
    all_keys = prices[["iamc_scenario", "region", "stem", "value_unit", "year"]].drop_duplicates()

    # Mean per country, weighted by demand; without demand a price is an artifact of the LP
    keys = ["iamc_scenario", "region", "stem", "value_unit", "year"]
    prices = prices.assign(weight=prices["weight"].fillna(0.0))
    prices = prices[prices["weight"] > noise].assign(weighted=lambda rows: rows["value"] * rows["weight"])
    means = prices.groupby(keys, as_index=False)[["weighted", "weight"]].sum()
    means["value"] = means["weighted"] / means["weight"]
    found = set(map(tuple, means[keys].to_numpy()))
    without = all_keys[[key not in found for key in map(tuple, all_keys.to_numpy())]]
    for (scenario, stem), rows in without.groupby(["iamc_scenario", "stem"]):
        notes.append(note(scenario, "", stem, (
            f"Not reported for {list_regions(rows['region'])} in {list_names(rows['year'].astype(str))}: the results "
            "give no demand for it there, so the price would be an artifact of the LP."
        )))
    high = prices[(prices["commodity"] != carbon) & (prices["value"].abs() > price_bound)]
    for (scenario, stem, unit), rows in high.groupby(["iamc_scenario", "stem", "value_unit"]):
        notes.append(note(scenario, "", stem, (
            f"Average prices above {price_bound:g} {unit.replace(money, balmorel_currency)} in magnitude, which may "
            f"be the penalty on an unmet balance rather than a market price, are in the price of "
            f"{list_regions(rows['region'])} in "
            f"{list_names(rows['year'].astype(str))}. Check those results."
        )))

    # Into the IAMC unit's currency, as `currency` values Balmorel's money, else by the price-level tables
    currency = {balmorel_currency: 1.0} | (currency or {})
    means["unit"] = means["stem"].map(variables.set_index("variable")["unit"])
    factors, by_tables = {}, {}
    for from_unit, to_unit in means[["value_unit", "unit"]].drop_duplicates().itertuples(index=False):
        found = money_factor(from_unit, to_unit, currency)
        worth = table_worth(to_unit) if found is None else None
        if worth is not None:
            found = money_factor(from_unit, to_unit, {worth[0]: worth[1]})
            by_tables[to_unit] = worth
        factors[(from_unit, to_unit)] = found
    means["factor"] = [factors[pair] for pair in zip(means["value_unit"], means["unit"])]
    means["by_tables"] = means["unit"].map(lambda unit: by_tables.get(unit, ("",))[0])
    worths = {name: (worth, how) for name, worth, how in by_tables.values()}
    for (scenario, name), rows in means[means["by_tables"] != ""].groupby(["iamc_scenario", "by_tables"]):
        worth, how = worths[name]
        notes.append(note(scenario, "", "", (
            f"Converted from {balmorel_currency} (Balmorel's money) to {name} by pybalmorel's price-level tables "
            f"(backcasting/pricelevel.py: {how}): one {balmorel_currency} is worth {worth:.4g} {name}. Prices: "
            f"{list_names(rows['stem'])}. Pass currency={{'{name}': <worth>}} to use another worth."
        )))
    unconverted = means[means["factor"].isna()]
    for scenario, rows in unconverted.groupby("iamc_scenario"):
        wanted = list_names(rows["unit"].str.split("/").str[0])
        notes.append(note(scenario, "", "", (
            f"Not reported, as neither currency nor pybalmorel's price-level tables give a worth in {wanted}: "
            f"{list_names(rows['stem'])}. Pass currency={{'<currency>': <worth>}}, what one {balmorel_currency} "
            f"(Balmorel's money) is worth in it, or, for EUR or USD of a year the tables don't cover "
            f"(they cover {min(pricelevel.hicp_euro_area)} to {max(pricelevel.hicp_euro_area)}), extend them in "
            "pybalmorel/backcasting/pricelevel.py."
        )))
    means = means[means["factor"].notna()]
    return means.assign(path="", variable=means["stem"], value_unit=means["unit"],
                        value=means["value"] * means["factor"]).reindex(columns=columns)


def derive_carbon_price(long: pd.DataFrame, notes: list[dict]) -> pd.DataFrame:
    """Derive the carbon price from the CO2 tax units pay per tonne they emit.

    The carbon price of a region and year is the tax that emitting units pay over their
    emissions, counting the units that pay any. Units with net negative emissions pay none.
    Where emitting units pay different rates, a Conversion Note gives the range. A scenario
    without tax has no carbon price; MainResults doesn't hold an emission cap's shadow price.

    Args:
        long (pd.DataFrame): Rows of quantity 'tax' and 'emissions' per unit, with IAMC Regions;
            other quantities are ignored.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: Rows of quantity 'price' and commodity 'CO2' per IAMC Scenario, region
            and year, weighted by the taxed emissions.
    """
    keys = ["iamc_scenario", "scenario", "region", "country", "area", "year", "unit_name", "tech_type", "fuel"]
    per_unit = []
    for quantity in ("tax", "emissions"):
        rows = long[long["quantity"] == quantity]
        per_unit.append(rows.groupby(keys + ["value_unit"], as_index=False)["value"].sum().rename(
            columns={"value": quantity, "value_unit": f"{quantity}_unit"}))
    units = per_unit[0].merge(per_unit[1], on=keys)
    units = units[units["emissions"] > noise]
    rate_factors = {
        pair: factor(f"{pair[0]}/{pair[1]}", f"{money}/t CO2")
        for pair in set(zip(units["tax_unit"], units["emissions_unit"]))
    }
    units["tax"] = units["tax"] * [rate_factors[pair] for pair in zip(units["tax_unit"], units["emissions_unit"])]
    units["taxed"] = units["tax"].abs() > noise

    group = ["iamc_scenario", "region", "year"]
    taxed = units[units["taxed"]]
    prices = taxed.groupby(group, as_index=False).agg(tax=("tax", "sum"), weight=("emissions", "sum"))
    prices["value"] = prices["tax"] / prices["weight"]

    # Rates of the units emitting more than solver noise, from those that pay nothing up
    total = units.groupby(group)["emissions"].transform("sum")
    rates = units[units["emissions"] >= relative_noise * total].assign(rate=lambda rows: rows["tax"] / rows["emissions"])
    ranges = rates.groupby(group, as_index=False).agg(low=("rate", "min"), high=("rate", "max")).merge(prices, on=group)
    spread = ranges[(ranges["high"] - ranges["low"]) > rate_tolerance * ranges["value"].abs()]
    for (scenario, region), rows in spread.groupby(["iamc_scenario", "region"]):
        years = ", ".join(f"{year}: {low:.4g} to {high:.4g}" for year, low, high in
                          rows[["year", "low", "high"]].itertuples(index=False))
        notes.append(note(scenario, region, "", (
            f"Emitting units pay different CO2 tax rates ({years} {money}/t CO2); the carbon price is the tax "
            "of those that pay any, over their emissions."
        )))

    emitting = long[(long["quantity"] == "emissions") & (long["value"] > noise)].groupby("iamc_scenario")["year"]
    emitting = emitting.unique().apply(set)
    for scenario, modelled in long.groupby("iamc_scenario")["year"].unique().items():
        unpriced = sorted(set(modelled) - set(prices.loc[prices["iamc_scenario"] == scenario, "year"]))
        if len(unpriced) == len(set(modelled)):
            notes.append(note(scenario, "", "", (
                "Carbon price not reported: no unit pays CO2 tax in the results. If emissions are capped instead, "
                "the cap's shadow price would be the carbon price, but MainResults doesn't hold it."
            )))
        elif unpriced:
            clean = [year for year in unpriced if year not in emitting.get(scenario, set())]
            untaxed = [year for year in unpriced if year not in clean]
            reasons = [f"no unit {what} in {', '.join(map(str, years))}"
                       for what, years in (("emits CO2", clean), ("pays CO2 tax", untaxed)) if years]
            notes.append(note(scenario, "", "", f"Carbon price not reported for {', '.join(map(str, unpriced))}: "
                              f"{'; '.join(reasons)}."))
    return prices.assign(quantity="price", commodity=carbon, value_unit=f"{money}/t CO2", area="").drop(columns="tax")


def money_factor(from_unit: str, to_unit: str, currency: dict[str, float] | None) -> float | None:
    """Factor that converts a unit in Balmorel's money to an IAMC unit in a currency.

    Args:
        from_unit (str): The unit in money, e.g. 'money/MWh'.
        to_unit (str): The IAMC unit, e.g. 'USD_2010/GJ'.
        currency (dict[str, float] | None): What one unit of Balmorel's money is worth, per
            currency.

    Returns:
        float | None: The factor, or None if `currency` doesn't give the IAMC unit's currency.
    """
    for name, worth in (currency or {}).items():
        pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
        if re.search(pattern, to_unit):
            return factor(from_unit, re.sub(pattern, money, to_unit)) * worth
    return None


def table_worth(unit: str) -> tuple[str, float, str] | None:
    """What one unit of Balmorel's money is worth in an IAMC unit's currency, by pybalmorel's
    price-level tables (backcasting/pricelevel.py).

    Balmorel's money (balmorel_currency) is brought to the currency's year by the euro-area HICP,
    then, for USD, exchanged at that year's mean EUR/USD rate.

    Args:
        unit (str): The IAMC unit, e.g. 'USD_2010/GJ'.

    Returns:
        tuple[str, float, str] | None: The currency (e.g. 'USD_2010'), what one balmorel_currency
            is worth in it, and how the tables gave that; None if the unit's currency is neither
            EUR nor USD of a year the tables cover.
    """
    found = re.search(table_currency, unit)
    if found is None:
        return None
    kind, year = found.group(1), int(found.group(2))
    if year not in pricelevel.hicp_euro_area or (kind == "USD" and year not in pricelevel.usd_per_eur):
        return None
    worth = 1 / pricelevel.to_price_year(1.0, year, kind, balmorel_price_year)
    how = "the euro-area HICP" + (f" and the mean EUR/USD rate of {year}" if kind == "USD" else "")
    return found.group(0), worth, how


#%% ------------------------------- ###
###          8. Summing Up          ###
### ------------------------------- ###

def note_totals(long: pd.DataFrame, stems: pd.DataFrame, notes: list[dict]) -> None:
    """Say what a stem's total (stems.csv) counts, for every IAMC Scenario with values under it.

    A total only counts what the stems that name it count, as Balmorel models it, and what the
    OptiFlow Mapping reports under it, so it and the variables between it and those stems can be
    lower than a whole-economy model's.

    Args:
        long (pd.DataFrame): The reported rows, with the 'stem_total' column.
        stems (pd.DataFrame): The 'stems' rule table.
        notes (list[dict]): Conversion Notes, appended to.
    """
    counted = long[(long["stem_total"] != "") & (long["value"].abs() >= noise)]
    for (scenario, total), rows in counted.groupby(["iamc_scenario", "stem_total"]):
        parts = []
        for quantity, rules in stems[stems["total"] == total].groupby("quantity", sort=False):
            commodities = []
            for commodity, by_commodity in rules.groupby("commodity", sort=False):
                kinds = [kind for kind in by_commodity["area_kind"] if kind]
                where = (f" in {', '.join(kinds[:-1])} and {kinds[-1]} areas" if len(kinds) > 1
                         else f" in {kinds[0]} areas" if kinds else "")
                commodities.append(f"{commodity}{where}")
            parts.append(f"{quantity_label(quantity)} of {', '.join(commodities)}")
        text = f"Counts only {'; and '.join(parts)}, as Balmorel's results give them"
        if (rows["quantity"] == optiflow_quantity).any():
            text += ", and what the OptiFlow Mapping ('optiflow' rules) reports under it"
        notes.append(note(scenario, "", total, text + (
            ". What Balmorel doesn't model, such as the energy use and emissions of sectors it leaves out, or what "
            "the OptiFlow add-on does that its Mapping doesn't report, is not in it, nor in the IAMC Variables "
            "between it and those it sums, so they can be lower than a whole-economy model's.")))


def copy_to_aggregates(long: pd.DataFrame, aggregates: pd.DataFrame, names: set[str]) -> pd.DataFrame:
    """Copy rows to the aggregates of their Source, and to their stem's total.

    An aggregate (aggregates.csv) whose component the segments the Mapping Rules gave start
    with takes the Source's place, e.g. 'Gas|w/ CCS' under 'Primary Energy|{source}|Electricity'
    counts towards 'Primary Energy|Fossil|Electricity' and 'Primary Energy|Fossil|Electricity|w/ CCS',
    and 'Wind|Onshore' towards 'Primary Energy|Non-Biomass Renewables'. Other aggregates are
    summed by sum_to_variables.

    A row whose stem has a total (stems.csv) also counts towards the total and every IAMC
    Variable between it and the stem. Under a stem with the Source placeholder, it counts towards
    the Source's own variable too, with the rest of its segments, e.g. 'Primary Energy|Gas' and
    'Primary Energy|Gas|w/ CCS', and towards the aggregates there, e.g. 'Primary Energy|Fossil'.
    Each copy counts towards its own variable only, and no variable takes a row twice.

    Args:
        long (pd.DataFrame): The reported rows, with 'template_stem', 'source_path' and
            'stem_total' columns.
        aggregates (pd.DataFrame): The 'aggregates' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.

    Returns:
        pd.DataFrame: The rows with the copies added, without 'template_stem', 'source_path' and
            'stem_total'.
    """
    keys = ["stem", "path", "variable", "template_stem", "source_path", "stem_total"]
    copies = []
    for (stem, path, variable, template, source_path, total), rows in long.groupby(keys):
        if not (template or total):
            continue
        targets = source_aggregates(template, source_path, aggregates, names) if template else set()
        if total and template:
            at_source = f"{stem_top(template)}|{source_placeholder}"
            source, _, rest = source_path.partition("|")
            own = fill_source(at_source, source, names) or fill_source(at_source, "Other", names)
            targets |= source_aggregates(at_source, source_path, aggregates, names)
            targets |= parents(resolve(own, rest, names) if own else stem_top(template), total)
        elif total:
            targets |= parents(stem, total)
        targets &= names
        targets -= parents(variable, stem) | set(aggregates_of(stem, path, names, aggregates))
        copies += [rows.assign(stem=target, path="", variable=target) for target in sorted(targets)]
    long = pd.concat([long] + copies, ignore_index=True)
    return long.drop(columns=["template_stem", "source_path", "stem_total"])


def source_aggregates(template: str, source_path: str, aggregates: pd.DataFrame, names: set[str]) -> set[str]:
    """Find the aggregates a row under a stem with the Source placeholder counts towards.

    Args:
        template (str): The stem as the rules give it, e.g. 'Primary Energy|{source}|Electricity'.
        source_path (str): The segments the Mapping Rules gave, e.g. 'Gas|w/ CCS'.
        aggregates (pd.DataFrame): The 'aggregates' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.

    Returns:
        set[str]: E.g. {'Primary Energy|Fossil|Electricity', 'Primary Energy|Fossil|Electricity|w/ CCS'}.
    """
    targets = set()
    for aggregate, component in aggregates[["aggregate", "component"]].itertuples(index=False):
        if not (source_path == component or source_path.startswith(f"{component}|")):
            continue
        first, _, rest = aggregate.partition("|")
        filled = fill_source(template, first, names)
        target = "|".join(filter(None, [filled, rest]))
        if filled and target in names:
            targets.add(target)
    return targets


def parents(variable: str, top: str) -> set[str]:
    """Name a variable and each of its parents up to and including `top`.

    Args:
        variable (str): E.g. 'Primary Energy|Gas|w/ CCS'.
        top (str): A parent of it, or itself, e.g. 'Primary Energy'.

    Returns:
        set[str]: E.g. {'Primary Energy', 'Primary Energy|Gas', 'Primary Energy|Gas|w/ CCS'}.
    """
    segments = variable.split("|")
    return {"|".join(segments[:length]) for length in range(len(top.split("|")), len(segments) + 1)}


def sum_to_variables(long: pd.DataFrame, variables: pd.DataFrame, aggregates: pd.DataFrame) -> pd.DataFrame:
    """Sum the rows to every IAMC Variable they count towards, in its unit.

    A row counts towards its variable, every parent of it from the stem down that the
    snapshot has, and every aggregate under its stem whose component its path starts with. A
    variable that a withheld row counts towards is left empty (NaN).

    Args:
        long (pd.DataFrame): The reported rows.
        variables (pd.DataFrame): The snapshot's variables (variable, unit).
        aggregates (pd.DataFrame): The 'aggregates' rule table.

    Returns:
        pd.DataFrame: Columns Scenario, Region, Variable, Unit, Year, Value.
    """
    names = set(variables["variable"])
    keys = ["iamc_scenario", "region", "stem", "path", "variable", "value_unit", "year"]
    withheld = long["withheld"].eq(True) if "withheld" in long.columns else False
    leaves = long.assign(withheld=withheld).groupby(keys, as_index=False).agg(
        value=("value", "sum"), withheld=("withheld", "any"))

    # Every variable each leaf counts towards, once
    targets = []
    for stem, path, variable in leaves[["stem", "path", "variable"]].drop_duplicates().itertuples(index=False):
        segments = variable.split("|")
        for length in range(len(stem.split("|")), len(segments) + 1):
            targets.append((stem, path, variable, "|".join(segments[:length])))
        for aggregate in aggregates_of(stem, path, names, aggregates):
            targets.append((stem, path, variable, aggregate))
    targets = pd.DataFrame(targets, columns=["stem", "path", "variable", "target"]).drop_duplicates()

    summed = leaves.merge(targets, on=["stem", "path", "variable"])
    summed = summed[summed["target"].isin(names)]
    summed = summed.merge(variables.rename(columns={"variable": "target"}), on="target", how="left")
    pairs = list(zip(summed["value_unit"], summed["unit"]))
    factors = {pair: factor(*pair) for pair in set(pairs)}
    summed["value"] = summed["value"] * [factors[pair] for pair in pairs]
    summed.loc[summed["value"].abs() < noise, "value"] = 0.0

    summed = summed.groupby(["iamc_scenario", "region", "target", "unit", "year"], as_index=False).agg(
        value=("value", "sum"), withheld=("withheld", "any"))
    summed["value"] = summed["value"].where(~summed.pop("withheld"))
    return summed.rename(columns={
        "iamc_scenario": "Scenario", "region": "Region", "target": "Variable",
        "unit": "Unit", "year": "Year", "value": "Value",
    })


def aggregates_of(stem: str, path: str, names: set[str], aggregates: pd.DataFrame) -> list[str]:
    """Find the aggregates under a stem that a row with the given segments counts towards.

    Args:
        stem (str): The stem, e.g. 'Secondary Energy|Electricity'.
        path (str): Segments below it, e.g. 'Gas|w/ CCS'.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        aggregates (pd.DataFrame): The 'aggregates' rule table.

    Returns:
        list[str]: The IAMC Variables '<stem>|<aggregate>' in `names` with a component the
            path starts with, e.g. ['Secondary Energy|Electricity|Fossil', ...].
    """
    return sorted({
        f"{stem}|{aggregate}"
        for aggregate, component in aggregates[["aggregate", "component"]].itertuples(index=False)
        if f"{stem}|{aggregate}" in names and (path == component or path.startswith(f"{component}|"))
    })


def factor(from_unit: str, to_unit: str) -> float:
    """Factor that converts a Balmorel unit to an IAMC unit.

    Args:
        from_unit (str): Balmorel's unit, e.g. 'TWh'.
        to_unit (str): The IAMC Variable's unit, e.g. 'EJ/yr'.

    Returns:
        float: The factor.
    """
    if from_unit == to_unit:
        return 1.0
    if (from_unit, to_unit) not in unit_factors:
        raise Exception(f"No factor from '{from_unit}' to '{to_unit}'; add it to unit_factors in {__name__}.")
    return unit_factors[(from_unit, to_unit)]


def limit_to_template(data: pd.DataFrame, template: str | Path, notes: list[dict]) -> pd.DataFrame:
    """Keep the IAMC Variables a Template accepts, and note regions it doesn't list.

    Args:
        data (pd.DataFrame): Long IAMC data from sum_to_variables.
        template (str | Path): The Template .xlsx.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows whose variable the Template accepts.
    """
    accepted_variables, accepted_regions = load_template(template)
    if accepted_regions:
        for scenario, regions in data.groupby("Scenario")["Region"]:
            unlisted = sorted(set(regions) - set(accepted_regions))
            if unlisted:
                notes.append(note(scenario, "", "",
                                  f"The Template's Region sheet doesn't list {list_regions(unlisted)}."))
    return data[data["Variable"].isin(accepted_variables)]


def to_wide(data: pd.DataFrame, model: str, modelled_years: pd.Series, means: set[str] | None = None) -> pd.DataFrame:
    """Pivot long IAMC data to one column per year.

    A variable reported in some of a scenario's modelled years is 0 in the others, unless it
    is a mean, such as a price. Withheld values stay empty; a row empty in every year is
    dropped.

    Args:
        data (pd.DataFrame): Long IAMC data.
        model (str): The IAMC Model label.
        modelled_years (pd.Series): Modelled years per IAMC Scenario.
        means (set[str] | None, optional): IAMC Variables that are means, whose missing years
            stay empty. Defaults to None.

    Returns:
        pd.DataFrame: Columns Model, Scenario, Region, Variable, Unit, then the years.
    """
    index = ["Model", "Scenario", "Region", "Variable", "Unit"]
    if data.empty:
        return pd.DataFrame(columns=index)
    cells = data.assign(Model=model).set_index(index + ["Year"])["Value"]
    wide = cells.unstack("Year")
    given = pd.Series(True, index=cells.index).unstack("Year", fill_value=False)
    summed = ~wide.index.get_level_values("Variable").isin(list(means or ()))
    for scenario, years in modelled_years.items():
        rows = (wide.index.get_level_values("Scenario") == scenario) & summed
        columns = [year for year in years if year in wide.columns]
        wide.loc[rows, columns] = wide.loc[rows, columns].mask(~given.loc[rows, columns], 0.0)
    wide = wide.dropna(how="all").reindex(columns=sorted(wide.columns))
    wide.columns.name = None
    return wide.reset_index()


#%% ------------------------------- ###
###        9. Conversion Notes      ###
### ------------------------------- ###

def note(scenario: str, region: str, variable: str, text: str) -> dict:
    """Make one Conversion Note.

    Args:
        scenario (str): IAMC Scenario.
        region (str): IAMC Region, or Balmorel country if it has none; '' for all, or for a
            note that names its regions.
        variable (str): IAMC Variable; '' if none.
        text (str): What the note says.

    Returns:
        dict: The note as a row.
    """
    return {"Scenario": scenario, "Region": region, "Variable": variable, "Note": text}


def per_region(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum values per region and year, for a Conversion Note that names its regions.

    Args:
        rows (pd.DataFrame): Rows of the long table with 'region', 'year' and 'value'.

    Returns:
        pd.DataFrame: Values with regions as index and years as columns, without regions
            whose values are all solver noise.
    """
    by_region = rows.groupby(["region", "year"])["value"].sum().unstack("year", fill_value=0.0)
    return by_region[(by_region.abs() >= noise).any(axis=1)]


def list_regions(regions: pd.Index | pd.Series | list[str]) -> str:
    """Name the regions a Conversion Note is about, e.g. 'Denmark' or '2 regions: Denmark, Germany'.

    Args:
        regions (pd.Index | pd.Series | list[str]): The regions.

    Returns:
        str: The region, or how many there are and their names.
    """
    regions = sorted(set(regions))
    return regions[0] if len(regions) == 1 else f"{len(regions)} regions: {', '.join(regions)}"


def list_names(names: pd.Series | list[str], limit: int = 10) -> str:
    """Name things a Conversion Note is about, at most `limit` of them.

    Args:
        names (pd.Series | list[str]): The names.
        limit (int, optional): How many to name. Defaults to 10.

    Returns:
        str: The names, and how many more there are.
    """
    names = sorted(set(names))
    more = f" and {len(names) - limit} more" if len(names) > limit else ""
    return ", ".join(names[:limit]) + more


def quantity_label(quantity: str) -> str:
    """Name a quantity of the long table in a Conversion Note.

    Args:
        quantity (str): The quantity, e.g. 'captured'.

    Returns:
        str: Its name, e.g. 'captured CO2'.
    """
    return quantity_labels.get(quantity, quantity)


def amounts(by_year: pd.Series | None) -> str:
    """Write amounts per year for a Conversion Note, e.g. '2030: 1.2, 2050: 3.4'. Amounts a
    billion times smaller than the largest, such as rounding errors, are written as 0.

    Args:
        by_year (pd.Series | None): Values indexed by year; None for none.

    Returns:
        str: The amounts, or '0' if there are none.
    """
    if by_year is None or by_year.empty:
        return "0"
    by_year = by_year.where(by_year.abs() > 1e-9 * by_year.abs().max(), 0.0)
    return ", ".join(f"{year}: {value:.4g}" for year, value in by_year.items())


def print_notes(notes: pd.DataFrame) -> None:
    """Print Conversion Notes as warnings, at most print_limit of them.

    Args:
        notes (pd.DataFrame): Conversion Notes.
    """
    if notes.empty:
        return
    print(f"IAMC conversion: {len(notes)} Conversion Notes")
    for scenario, region, variable, text in notes.head(print_limit).itertuples(index=False):
        where = " | ".join(part for part in (scenario, region, variable) if part)
        print(f"  [{where}] {text}")
    if len(notes) > print_limit:
        print(f"  ... and {len(notes) - print_limit} more, in the Conversion Notes to_iamc returns.")

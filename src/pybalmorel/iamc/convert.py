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

from pathlib import Path
from typing import TYPE_CHECKING
import numpy as np
import pandas as pd

from .reader import read_mainresults
from .rules import (default_area_kind, import_unit, load_definitions, load_rules, load_template, match_area_kinds,
                    match_mapping_rules, not_reported)

if TYPE_CHECKING:
    from ..classes import MainResults

# Factor from a Balmorel unit to an IAMC unit
unit_factors = {
    ("TWh", "EJ/yr"): 3.6e-3,
    ("GWh", "EJ/yr"): 3.6e-6,
    ("PJ", "EJ/yr"): 1e-3,
    ("MW", "GW"): 1e-3,
}
backup_choices = ("supply", "exclude")
# Values smaller than this, in Balmorel's units, are solver noise and reported as 0
noise = 1e-9
note_columns = ["Scenario", "Region", "Variable", "Note"]
# Conversion Notes printed at most; to_iamc returns them all
print_limit = 30
# Columns only some quantities have, '' for the others
optional_columns = ["demand_category", "to_area", "to_country"]
# The commodity whose exchange between areas is Heat Exchange; exchange of the others is trade
heat_commodity = "HEAT"
# Demand category of the heat district heating sends net to an individual or industry area
net_exchange = "NET_EXCHANGE"
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
            backup_pattern: str = "GNR_BACKUP") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert MainResults to IAMC data.

    Reports the IAMC Variables that the rule tables cover (see pybalmorel/iamc/rule_tables/), in the
    units of the Definitions Snapshot, per Balmorel country and modelled year. Transmission
    between countries, and what import units bring in from outside the model, are reported as
    Trade (net exports). Conversion Notes say what was put under Other, what was left out, how
    backup units, import units and Heat Exchange were treated, and where a commodity's supply and
    demand don't add up; the first of them are printed.

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
            'aggregates', 'countries', 'areas', 'demand_categories'). Defaults to None.
        backup_units (str, optional): 'supply' counts backup units' output as supply under their
            fuel; 'exclude' leaves it out. Their capacity is never reported. Defaults to 'supply'.
        backup_pattern (str, optional): Regular expression that marks backup units by name.
            Defaults to 'GNR_BACKUP'.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The IAMC data, and the Conversion Notes (columns
            Scenario, Region, Variable, Note).
    """
    long = read_mainresults(results)
    return convert(long, model, scenarios, template, definitions, rules, backup_units, backup_pattern)


def convert(long: pd.DataFrame,
            model: str,
            scenarios: dict[str, str] | None = None,
            template: str | Path | None = None,
            definitions: str | Path | None = None,
            rules: dict[str, str | Path | pd.DataFrame] | None = None,
            backup_units: str = "supply",
            backup_pattern: str = "GNR_BACKUP") -> tuple[pd.DataFrame, pd.DataFrame]:
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

    long = long.copy()
    for column in optional_columns:
        long[column] = long[column].fillna("") if column in long.columns else ""
    long = name_scenarios(long, scenarios)
    modelled_years = long.groupby("iamc_scenario")["year"].unique()
    long = count_trade(long, tables["mapping"], notes)
    long = name_regions(long, tables["countries"], regions, notes)
    long = attach_area_kinds(long, tables["areas"])
    long = exchange_heat(long, tables["mapping"], notes)
    check_balances(long, tables["stems"], tables["mapping"], tables["demand_categories"], notes)
    long = select_demand(long, tables["demand_categories"], notes)
    long = attach_stems(long, tables["stems"], set(variables["variable"]), notes)
    long = attach_segments(long, tables, set(variables["variable"]), notes)
    long = treat_backup_units(long, backup_units, backup_pattern, notes)

    data = sum_to_variables(long, variables, tables["aggregates"])
    if template is not None:
        data = limit_to_template(data, template, notes)
    data = to_wide(data, model, modelled_years)

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
    negative trade, and their capacity is left out. Exchange of heat is Heat Exchange, which
    exchange_heat treats.

    Args:
        long (pd.DataFrame): The long table with IAMC Scenarios.
        mapping (pd.DataFrame): The 'mapping' rule table.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The long table with trade rows, which have no area or unit, in place of
            transmission and import units' rows.
    """
    blank = {"quantity": "trade", "area": "", "unit_name": "", "tech_type": "", "fuel": "",
             "demand_category": "", "to_area": "", "to_country": ""}
    is_transmission = (long["quantity"] == "exchange") & (long["commodity"] != heat_commodity)
    transmission = long[is_transmission]
    long = long[~is_transmission]

    unit_columns = ["unit_name", "tech_type", "fuel", "commodity"]
    units = long.loc[long["unit_name"] != "", unit_columns].drop_duplicates().reset_index(drop=True)
    importers = units[match_mapping_rules(units, mapping) == import_unit]
    by_importer = np.zeros(len(long), dtype=bool)
    if not importers.empty:
        by_importer = pd.MultiIndex.from_frame(long[unit_columns]).isin(pd.MultiIndex.from_frame(importers))
    imported = long[by_importer & (long["quantity"] == "output")]
    long = long[~by_importer]

    abroad = transmission[(transmission["to_country"] != "") & (transmission["to_country"] != transmission["country"])]
    trade = pd.concat((
        abroad.assign(**blank),
        abroad.assign(**blank, country=abroad["to_country"], value=-abroad["value"]),
        imported.assign(**blank, value=-imported["value"]),
    ), ignore_index=True)

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
    unknown = transmission[transmission["to_country"] == ""]
    for (scenario, commodity, value_unit), rows in unknown.groupby(["iamc_scenario", "commodity", "value_unit"]):
        notes.append(note(scenario, "", "", (
            f"Transmission of {commodity} to regions whose country the results don't give is not counted as "
            f"Trade: {amounts(rows.groupby('year')['value'].sum())} {value_unit}."
        )))

    return pd.concat((long, trade), ignore_index=True)


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
            "the heat they sent."
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

    return pd.concat(traced, ignore_index=True)[columns]


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
    kept = demand[demand["final"] == "yes"].drop(columns="final")
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
    the reported supply and demand don't add up either. A scenario whose results give output of
    the commodity but no demand of it gets one note instead.

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
        for (scenario, region, value_unit), gaps in balance[off].groupby(level=["iamc_scenario", "region", "value_unit"]):
            by_year = gaps["gap"].droplevel([0, 1, 2])
            notes.append(note(scenario, region, "", (
                f"{commodity}{where} doesn't add up: its output less net exports was "
                f"{amounts(by_year.where(by_year.abs() >= noise, 0.0))} {value_unit} more than its demand in the "
                "categories the 'demand_categories' rules know (negative: less). The results make, use or move "
                f"{commodity} where the Reader doesn't look, such as transmission they don't list or a model "
                "add-on's, so its reported supply and demand don't add up either."
            )))


#%% ------------------------------- ###
###     4. Stems and Segments       ###
### ------------------------------- ###

def attach_stems(long: pd.DataFrame, stems: pd.DataFrame, names: set[str],
                 notes: list[dict]) -> pd.DataFrame:
    """Add the stem of each row, leaving out quantities and commodities without one.

    A stem row for the row's Area Kind beats one for any Area Kind.

    Args:
        long (pd.DataFrame): The long table with Area Kinds.
        stems (pd.DataFrame): The 'stems' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows with a stem, with a 'stem' column.
    """
    for_kind = stems[stems["area_kind"] != ""]
    for_any = stems[stems["area_kind"] == ""].drop(columns="area_kind").rename(columns={"stem": "stem_any"})
    long = long.merge(for_kind, on=["quantity", "commodity", "area_kind"], how="left")
    long = long.merge(for_any, on=["quantity", "commodity"], how="left")
    long["stem"] = long["stem"].fillna(long.pop("stem_any")).fillna("")

    # Name the Area Kind only where the stems tell kinds apart
    unreported = long[long["stem"] == ""]
    kind_specific = for_kind.set_index(["quantity", "commodity"]).index
    by_kind = unreported.set_index(["quantity", "commodity"]).index.isin(kind_specific) & (unreported["area_kind"] != "")
    unreported = unreported.assign(where=np.where(by_kind, " in " + unreported["area_kind"] + " areas", ""))
    for (scenario, quantity, commodity, where, value_unit), rows in unreported.groupby(
            ["iamc_scenario", "quantity", "commodity", "where", "value_unit"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        notes.append(note(scenario, "", "", (
            f"{quantity.capitalize()} of {commodity}{where} is not reported (the 'stems' rules "
            f"have no row for it): {amounts(by_region.sum())} {value_unit} in {list_regions(by_region.index)}."
        )))

    for (scenario, stem), _ in long[(long["stem"] != "") & ~long["stem"].isin(names)].groupby(
            ["iamc_scenario", "stem"]):
        notes.append(note(scenario, "", stem, "This stem is not in the Definitions Snapshot; not reported."))

    return long[long["stem"].isin(names)]


def attach_segments(long: pd.DataFrame, tables: dict[str, pd.DataFrame], names: set[str],
                    notes: list[dict]) -> pd.DataFrame:
    """Add the IAMC Variable each row is reported under.

    'path' holds the segments the Mapping Rules give, and 'variable' the longest of its
    prefixes in the snapshot, or '<stem>|Other' when even its first segment is missing. Rows
    without a unit skip the Mapping Rules: demand and trade are reported under the stem itself,
    and heat Heat Exchange could trace to no unit under Other.

    Args:
        long (pd.DataFrame): The long table with stems.
        tables (dict[str, pd.DataFrame]): The rule tables.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The reported rows, with 'category', 'path' and 'variable' columns.
    """
    categories = tables["fuels"].set_index("fuel")["category"]
    has_unit = long["unit_name"] != ""
    long = long.assign(category=long["fuel"].map(categories))
    long["reason"] = ""
    long.loc[has_unit & long["category"].isna(), "reason"] = "fuel has no Fuel Category"
    long["category"] = long["category"].fillna("Other")

    # Match rules once per unit, not per row
    unit_columns = ["unit_name", "tech_type", "fuel", "commodity"]
    units = long.loc[has_unit, unit_columns].drop_duplicates().reset_index(drop=True)
    units["template"] = match_mapping_rules(units, tables["mapping"])
    long = long.merge(units, on=unit_columns, how="left")
    long = long[long["template"] != not_reported].copy()

    no_unit = long["unit_name"] == ""
    unmatched = ~no_unit & (long["template"] == "")
    long.loc[unmatched, "reason"] = "no Mapping Rule matches"
    long.loc[unmatched, "template"] = "Other"
    under_stem = no_unit & long["quantity"].isin(["demand", "trade"])
    long.loc[under_stem, "template"] = ""
    long.loc[no_unit & ~under_stem, "template"] = "Other"
    long.loc[no_unit & ~under_stem, "reason"] = "Heat Exchange traced it to no unit"
    long["path"] = [
        template.replace("{category}", category)
        for template, category in zip(long["template"], long["category"])
    ]

    resolved = long[["stem", "path"]].drop_duplicates()
    resolved["variable"] = [resolve(stem, path, names) for stem, path in zip(resolved["stem"], resolved["path"])]
    long = long.merge(resolved, on=["stem", "path"], how="left")

    # Note what went into Other, and why
    other = long[(long["path"] != "")
                 & ((long["variable"] == long["stem"] + "|Other") | (long["variable"] == long["stem"]))].copy()
    first_segment = other["path"].str.split("|").str[0]
    other.loc[(other["reason"] == "") & (first_segment == "Other"), "reason"] = "Fuel Category Other"
    other.loc[other["reason"] == "", "reason"] = "no such IAMC Variable"
    contents = []
    for (scenario, region, variable), rows in other.groupby(["iamc_scenario", "region", "variable"]):
        what = [
            f"{tech_type}/{fuel} ({reason}: '{path}')" if reason == "no such IAMC Variable"
            else f"{tech_type}/{fuel} ({reason})" if tech_type or fuel
            else f"heat ({reason})"
            for tech_type, fuel, path, reason in rows[["tech_type", "fuel", "path", "reason"]]
            .drop_duplicates().itertuples(index=False)
        ]
        contents.append((scenario, region, variable, "; ".join(what)))
    # One note for the regions where the same went into the same variable
    contents = pd.DataFrame(contents, columns=["iamc_scenario", "region", "variable", "what"])
    for (scenario, variable, what), rows in contents.groupby(["iamc_scenario", "variable", "what"]):
        where = "Other" if variable.endswith("|Other") else "the total only, as there is no Other"
        notes.append(note(scenario, "", variable,
                          f"Reported under {where} in {list_regions(rows['region'])}: {what}."))

    return long.drop(columns=["template", "reason"])


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
###         5. Backup Units         ###
### ------------------------------- ###

def treat_backup_units(long: pd.DataFrame, backup_units: str, backup_pattern: str,
                       notes: list[dict]) -> pd.DataFrame:
    """Drop backup units' capacity, and count or drop their output, noting the amounts.

    Args:
        long (pd.DataFrame): The long table with variables.
        backup_units (str): 'supply' or 'exclude'.
        backup_pattern (str): Regular expression marking backup units by name.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows still reported.
    """
    backup = long["unit_name"].str.contains(backup_pattern, regex=True)
    output = backup & (long["quantity"] == "output")

    treatment = "counted as supply" if backup_units == "supply" else "left out"
    for (scenario, variable, value_unit), rows in long[output].groupby(["iamc_scenario", "variable", "value_unit"]):
        by_region = per_region(rows)
        if by_region.empty:
            continue
        notes.append(note(scenario, "", variable, (
            f"Backup units produced {amounts(by_region.sum())} {value_unit} in "
            f"{list_regions(by_region.index)}; {treatment}."
        )))

    leave_out = backup & ~output if backup_units == "supply" else backup
    return long[~leave_out]


#%% ------------------------------- ###
###          6. Summing Up          ###
### ------------------------------- ###

def sum_to_variables(long: pd.DataFrame, variables: pd.DataFrame, aggregates: pd.DataFrame) -> pd.DataFrame:
    """Sum the rows to every IAMC Variable they count towards, in its unit.

    A row counts towards its variable, every parent of it from the stem down that the
    snapshot has, and every aggregate under its stem whose component its path starts with.

    Args:
        long (pd.DataFrame): The reported rows.
        variables (pd.DataFrame): The snapshot's variables (variable, unit).
        aggregates (pd.DataFrame): The 'aggregates' rule table.

    Returns:
        pd.DataFrame: Columns Scenario, Region, Variable, Unit, Year, Value.
    """
    names = set(variables["variable"])
    keys = ["iamc_scenario", "region", "stem", "path", "variable", "value_unit", "year"]
    leaves = long.groupby(keys, as_index=False)["value"].sum()

    # Every variable each leaf counts towards, once
    targets = []
    for stem, path, variable in leaves[["stem", "path", "variable"]].drop_duplicates().itertuples(index=False):
        segments = variable.split("|")
        for length in range(len(stem.split("|")), len(segments) + 1):
            targets.append((stem, path, variable, "|".join(segments[:length])))
        for aggregate, component in aggregates[["aggregate", "component"]].itertuples(index=False):
            if f"{stem}|{aggregate}" in names and (path == component or path.startswith(f"{component}|")):
                targets.append((stem, path, variable, f"{stem}|{aggregate}"))
    targets = pd.DataFrame(targets, columns=["stem", "path", "variable", "target"]).drop_duplicates()

    summed = leaves.merge(targets, on=["stem", "path", "variable"])
    summed = summed[summed["target"].isin(names)]
    summed = summed.merge(variables.rename(columns={"variable": "target"}), on="target", how="left")
    pairs = list(zip(summed["value_unit"], summed["unit"]))
    factors = {pair: factor(*pair) for pair in set(pairs)}
    summed["value"] = summed["value"] * [factors[pair] for pair in pairs]
    summed.loc[summed["value"].abs() < noise, "value"] = 0.0

    summed = summed.groupby(["iamc_scenario", "region", "target", "unit", "year"], as_index=False)["value"].sum()
    return summed.rename(columns={
        "iamc_scenario": "Scenario", "region": "Region", "target": "Variable",
        "unit": "Unit", "year": "Year", "value": "Value",
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


def to_wide(data: pd.DataFrame, model: str, modelled_years: pd.Series) -> pd.DataFrame:
    """Pivot long IAMC data to one column per year.

    A variable reported in some of a scenario's modelled years is 0 in the others.

    Args:
        data (pd.DataFrame): Long IAMC data.
        model (str): The IAMC Model label.
        modelled_years (pd.Series): Modelled years per IAMC Scenario.

    Returns:
        pd.DataFrame: Columns Model, Scenario, Region, Variable, Unit, then the years.
    """
    index = ["Model", "Scenario", "Region", "Variable", "Unit"]
    if data.empty:
        return pd.DataFrame(columns=index)
    wide = data.assign(Model=model).pivot_table(index=index, columns="Year", values="Value", aggfunc="sum")
    for scenario, years in modelled_years.items():
        rows = wide.index.get_level_values("Scenario") == scenario
        columns = [year for year in years if year in wide.columns]
        wide.loc[rows, columns] = wide.loc[rows, columns].fillna(0.0)
    wide = wide.reindex(columns=sorted(wide.columns))
    wide.columns.name = None
    return wide.reset_index()


#%% ------------------------------- ###
###        7. Conversion Notes      ###
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

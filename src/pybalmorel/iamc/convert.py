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
import pandas as pd

from .reader import read_mainresults
from .rules import load_definitions, load_rules, load_template, match_mapping_rules, not_reported

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
    units of the Definitions Snapshot, per Balmorel country and modelled year. Conversion Notes
    say what was put under Other, what was left out, and how backup units were treated; they are
    also printed.

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
            'aggregates', 'countries'). Defaults to None.
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

    long = name_scenarios(long, scenarios)
    modelled_years = long.groupby("iamc_scenario")["year"].unique()
    long = name_regions(long, tables["countries"], regions, notes)
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
###     2. Scenarios and Regions    ###
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
###     3. Stems and Segments       ###
### ------------------------------- ###

def attach_stems(long: pd.DataFrame, stems: pd.DataFrame, names: set[str],
                 notes: list[dict]) -> pd.DataFrame:
    """Add the stem of each row, leaving out quantities and commodities without one.

    Args:
        long (pd.DataFrame): The long table.
        stems (pd.DataFrame): The 'stems' rule table.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The rows with a stem, with a 'stem' column.
    """
    long = long.merge(stems, on=["quantity", "commodity"], how="left")
    long["stem"] = long["stem"].fillna("")

    for (scenario, quantity, commodity), _ in long[long["stem"] == ""].groupby(
            ["iamc_scenario", "quantity", "commodity"]):
        notes.append(note(scenario, "", "",
                          f"{quantity.capitalize()} of {commodity} is not reported: the 'stems' rules have no row for it."))

    for (scenario, stem), _ in long[(long["stem"] != "") & ~long["stem"].isin(names)].groupby(
            ["iamc_scenario", "stem"]):
        notes.append(note(scenario, "", stem, "This stem is not in the Definitions Snapshot; not reported."))

    return long[long["stem"].isin(names)]


def attach_segments(long: pd.DataFrame, tables: dict[str, pd.DataFrame], names: set[str],
                    notes: list[dict]) -> pd.DataFrame:
    """Add the IAMC Variable each row is reported under.

    'path' holds the segments the Mapping Rules give, and 'variable' the longest of its
    prefixes in the snapshot, or '<stem>|Other' when even its first segment is missing.

    Args:
        long (pd.DataFrame): The long table with stems.
        tables (dict[str, pd.DataFrame]): The rule tables.
        names (set[str]): IAMC Variables in the Definitions Snapshot.
        notes (list[dict]): Conversion Notes, appended to.

    Returns:
        pd.DataFrame: The reported rows, with 'category', 'path' and 'variable' columns.
    """
    categories = tables["fuels"].set_index("fuel")["category"]
    long = long.assign(category=long["fuel"].map(categories))
    long["reason"] = ""
    long.loc[long["category"].isna(), "reason"] = "fuel has no Fuel Category"
    long["category"] = long["category"].fillna("Other")

    # Match rules once per unit, not per row
    unit_columns = ["unit_name", "tech_type", "fuel", "commodity"]
    units = long[unit_columns].drop_duplicates().reset_index(drop=True)
    units["template"] = match_mapping_rules(units, tables["mapping"])
    long = long.merge(units, on=unit_columns, how="left")
    long = long[long["template"] != not_reported].copy()

    long.loc[long["template"] == "", "reason"] = "no Mapping Rule matches"
    long.loc[long["template"] == "", "template"] = "Other"
    long["path"] = [
        template.replace("{category}", category)
        for template, category in zip(long["template"], long["category"])
    ]

    resolved = long[["stem", "path"]].drop_duplicates()
    resolved["variable"] = [resolve(stem, path, names) for stem, path in zip(resolved["stem"], resolved["path"])]
    long = long.merge(resolved, on=["stem", "path"], how="left")

    # Note what went into Other, and why
    other = long[(long["variable"] == long["stem"] + "|Other") | (long["variable"] == long["stem"])].copy()
    first_segment = other["path"].str.split("|").str[0]
    other.loc[(other["reason"] == "") & (first_segment == "Other"), "reason"] = "Fuel Category Other"
    other.loc[other["reason"] == "", "reason"] = "no such IAMC Variable"
    for (scenario, region, variable), rows in other.groupby(["iamc_scenario", "region", "variable"]):
        contents = [
            f"{tech_type}/{fuel} ({reason}: '{path}')" if reason == "no such IAMC Variable"
            else f"{tech_type}/{fuel} ({reason})"
            for tech_type, fuel, path, reason in rows[["tech_type", "fuel", "path", "reason"]]
            .drop_duplicates().itertuples(index=False)
        ]
        where = "Other" if variable.endswith("|Other") else "the total only, as there is no Other"
        notes.append(note(scenario, region, variable, f"Reported under {where}: {'; '.join(contents)}."))

    return long.drop(columns=["template", "reason"])


def resolve(stem: str, path: str, names: set[str]) -> str:
    """Find the IAMC Variable that output with the given stem and segments is reported under.

    Args:
        stem (str): The stem, e.g. 'Secondary Energy|Electricity'.
        path (str): Segments below it, e.g. 'Wind|Onshore|w/o CCS'.
        names (set[str]): IAMC Variables in the Definitions Snapshot.

    Returns:
        str: The longest prefix of '<stem>|<path>' in `names` that keeps at least one segment,
            else '<stem>|Other', else the stem.
    """
    segments = path.split("|")
    for length in range(len(segments), 0, -1):
        candidate = "|".join([stem] + segments[:length])
        if candidate in names:
            return candidate
    return f"{stem}|Other" if f"{stem}|Other" in names else stem


#%% ------------------------------- ###
###         4. Backup Units         ###
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
    for (scenario, region, variable, value_unit), rows in long[output].groupby(
            ["iamc_scenario", "region", "variable", "value_unit"]):
        by_year = rows.groupby("year")["value"].sum()
        if (by_year.abs() < noise).all():
            continue
        amounts = ", ".join(f"{year}: {value:.4g}" for year, value in by_year.items())
        notes.append(note(scenario, region, variable,
                          f"Backup units produced {amounts} {value_unit}; {treatment}."))

    leave_out = backup & ~output if backup_units == "supply" else backup
    return long[~leave_out]


#%% ------------------------------- ###
###          5. Summing Up          ###
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
        for scenario, region in data[["Scenario", "Region"]].drop_duplicates().itertuples(index=False):
            if region not in accepted_regions:
                notes.append(note(scenario, region, "", "The Template's Region sheet doesn't list this region."))
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
###        6. Conversion Notes      ###
### ------------------------------- ###

def note(scenario: str, region: str, variable: str, text: str) -> dict:
    """Make one Conversion Note.

    Args:
        scenario (str): IAMC Scenario.
        region (str): IAMC Region, or Balmorel country if it has none; '' for all.
        variable (str): IAMC Variable; '' if none.
        text (str): What the note says.

    Returns:
        dict: The note as a row.
    """
    return {"Scenario": scenario, "Region": region, "Variable": variable, "Note": text}


def print_notes(notes: pd.DataFrame) -> None:
    """Print Conversion Notes as warnings.

    Args:
        notes (pd.DataFrame): Conversion Notes.
    """
    if notes.empty:
        return
    print(f"IAMC conversion: {len(notes)} Conversion Notes")
    for scenario, region, variable, text in notes.itertuples(index=False):
        where = " | ".join(part for part in (scenario, region, variable) if part)
        print(f"  [{where}] {text}")

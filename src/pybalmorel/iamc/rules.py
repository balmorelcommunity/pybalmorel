"""
IAMC Mapping Rules and Definitions Snapshot

Loads the rule tables in `rule_tables/` (with rows passed by whoever converts taking
precedence), the Definitions Snapshot in `definitions/` (or one passed in),
and a Template's Extended List. Also applies the Mapping Rules to units and
checks that every rule targets names the snapshot still has.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import re
from pathlib import Path
import numpy as np
import pandas as pd

rules_dir = Path(__file__).parent / "rule_tables"
definitions_dir = Path(__file__).parent / "definitions"

# Columns of each rule table, the columns a table may leave out (read as empty), and the key
# whose rows a caller's rows replace
rule_tables = {
    "fuels": {"columns": ["fuel", "category", "primary", "carrier"], "optional": ["primary", "carrier"],
              "key": ["fuel"]},
    "mapping": {"columns": ["tech_type", "fuel", "commodity", "unit_pattern", "segments", "primary", "carrier"],
                "optional": ["primary", "carrier"], "key": None},
    "stems": {"columns": ["quantity", "commodity", "area_kind", "stem", "total", "sector", "note"],
              "optional": ["total", "sector", "note"], "key": ["quantity", "commodity", "area_kind"]},
    "aggregates": {"columns": ["aggregate", "component"], "key": ["aggregate"]},
    "countries": {"columns": ["country", "iso3"], "key": ["country"]},
    "areas": {"columns": ["pattern", "area_kind"], "key": ["pattern"]},
    "demand_categories": {"columns": ["commodity", "demand_category", "final", "fuel_category", "sector", "note"],
                          "optional": ["fuel_category", "sector", "note"], "key": ["commodity", "demand_category"]},
    "optiflow": {"columns": ["from_process", "to_process", "flow", "role", "pool", "unit", "factor", "variable",
                             "removal", "emissions", "note"], "optional": ["factor", "note"], "key": None},
}
mapping_keys = ["tech_type", "fuel", "commodity", "unit_pattern"]
not_reported = "-"
# Segments of Mapping Rules for units that bring a commodity in from outside the model: their
# output is counted as imports, under trade, and their capacity is not reported
import_unit = "import"
# Segments of Mapping Rules for the rows by which results linked to OptiFlow carry OptiFlow's
# own emissions: they are not reported, as the 'optiflow' rules report OptiFlow's results
optiflow_unit = "optiflow"
# Roles of 'optiflow' rules (see rule_tables/optiflow.csv), and those that need a pool
optiflow_roles = ("balmorel", "capture", "store", "report", "fuel")
pool_roles = ("balmorel", "capture", "store")
optiflow_patterns = ["from_process", "to_process", "flow"]
optiflow_targets = ["variable", "removal", "emissions"]
# Area Kind of areas no pattern in the 'areas' table matches
default_area_kind = "district heating"
# What the 'final' column of the 'demand_categories' table may say: 'on-site' marks a category
# whose part that units use where what they make isn't reported counts as final demand
on_site_final = "on-site"
final_choices = ("yes", "no", on_site_final)
# How a unit counts as Primary Energy ('primary' column of the 'fuels' and 'mapping' tables): by
# its fuel input, by what it makes (direct equivalent), or not at all; empty is left to the
# next rule, and to 'input' in the end
primary_choices = ("input", "output", "no")
# Placeholder in a stem for the Source: the first segment the Mapping Rules give, e.g. 'Gas'
source_placeholder = "{source}"
# Placeholder at the end of a stem of on-site fuel use for the first segment of the fuel's
# carrier ('carrier' column of the 'fuels' and 'mapping' tables), e.g. 'Gases' of 'Gases|Gas'
carrier_placeholder = "{carrier}"
# Quantity of on-site fuel use: fuel input of units whose output isn't reported, as final energy
final_quantity = "final"


#%% ------------------------------- ###
###          1. Rule Tables         ###
### ------------------------------- ###

def read_table(source: str | Path | pd.DataFrame, columns: list[str], name: str,
               optional: list[str] | None = None) -> pd.DataFrame:
    """Read a rule or definitions table as strings, with empty cells as ''.

    Args:
        source (str | Path | pd.DataFrame): A CSV file ('#' starts a comment line) or a DataFrame.
        columns (list[str]): Columns the table must have; others are dropped.
        name (str): Name of the table, for error messages.
        optional (list[str] | None, optional): Columns of `columns` the table may leave out;
            they are then empty. Defaults to None.

    Returns:
        pd.DataFrame: The table with exactly `columns`, all strings, stripped.
    """
    if isinstance(source, pd.DataFrame):
        table = source.copy()
    else:
        table = pd.read_csv(source, dtype=str, keep_default_na=False, comment="#")

    for column in optional or []:
        if column not in table.columns:
            table[column] = ""
    missing = [column for column in columns if column not in table.columns]
    if missing:
        raise Exception(f"The '{name}' table lacks the columns {missing}; it needs {columns}.")

    table = table[columns].fillna("").astype(str)
    for column in columns:
        table[column] = table[column].str.strip()
    return table.reset_index(drop=True)


def load_rules(overrides: dict[str, str | Path | pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    """Load the shipped rule tables, with the caller's rows taking precedence.

    Args:
        overrides (dict[str, str | Path | pd.DataFrame] | None, optional): Rows to add per table,
            keyed by table name ('fuels', 'mapping', 'stems', 'aggregates', 'countries', 'areas',
            'demand_categories', 'optiflow'), as a CSV path or DataFrame with that table's
            columns. Defaults to None.

    Returns:
        dict[str, pd.DataFrame]: The tables by name. The 'mapping' and 'optiflow' tables have a
            'priority' column: 1 for the caller's rows, 0 for the shipped ones. The 'optiflow'
            table has the caller's rows first; every row applies to every flow it matches.
    """
    overrides = overrides or {}
    unknown = [name for name in overrides if name not in rule_tables]
    if unknown:
        raise Exception(f"Unknown rule tables {unknown}; choose from {list(rule_tables)}.")

    tables = {}
    for name, spec in rule_tables.items():
        optional = spec.get("optional")
        shipped = read_table(rules_dir / f"{name}.csv", spec["columns"], name, optional)
        caller = (
            read_table(overrides[name], spec["columns"], name, optional)
            if name in overrides
            else pd.DataFrame(columns=spec["columns"], dtype=str)
        )

        if name == "mapping":
            table = pd.concat((caller.assign(priority=1), shipped.assign(priority=0)), ignore_index=True)
        elif name == "optiflow":
            table = pd.concat((caller.assign(priority=1), shipped.assign(priority=0)), ignore_index=True)
        elif name == "aggregates":
            replaced = shipped["aggregate"].isin(caller["aggregate"])
            table = pd.concat((caller, shipped[~replaced]), ignore_index=True)
        else:
            for rows, source in ((shipped, "shipped"), (caller, "passed")):
                repeated = rows[rows.duplicated(spec["key"], keep=False)]
                if not repeated.empty:
                    raise Exception(f"The {source} '{name}' rules repeat keys {spec['key']}:\n{repeated.to_string()}")
            # The caller's rows replace shipped rows with the same key
            replaced = shipped.set_index(spec["key"]).index.isin(caller.set_index(spec["key"]).index)
            table = pd.concat((caller, shipped[~replaced]), ignore_index=True)
        tables[name] = table

    mapping = tables["mapping"]
    empty = mapping["segments"] == ""
    if empty.any():
        raise Exception(
            f"Mapping Rules need segments, or '{not_reported}' for not reported:\n{mapping[empty].to_string()}"
        )
    for name in ("fuels", "mapping"):
        unclear = ~tables[name]["primary"].isin(primary_choices + ("",))
        if unclear.any():
            raise Exception(
                f"The '{name}' rules need one of {list(primary_choices)}, or nothing, under primary:\n"
                f"{tables[name][unclear].to_string()}"
            )
    per_commodity = ((mapping["primary"] != "") | (mapping["carrier"] != "")) & (mapping["commodity"] != "")
    if per_commodity.any():
        raise Exception(
            "Mapping Rules with a commodity can't set primary or carrier, as primary energy and fuel input are per "
            f"unit, not per commodity:\n{mapping[per_commodity].to_string()}"
        )
    demand_categories = tables["demand_categories"]
    unclear = ~demand_categories["final"].isin(final_choices)
    if unclear.any():
        raise Exception(
            f"The 'demand_categories' rules need one of {list(final_choices)} under final:\n"
            f"{demand_categories[unclear].to_string()}"
        )
    unknown = ((demand_categories["final"] == on_site_final)
               & ~demand_categories["fuel_category"].isin(tables["fuels"]["category"]))
    if unknown.any():
        raise Exception(
            f"'demand_categories' rows marked '{on_site_final}' need a fuel_category that the 'fuels' rules give "
            f"some fuel: that of the fuels whose input counts.\n{demand_categories[unknown].to_string()}"
        )
    sector_not_final = (demand_categories["sector"] != "") & (demand_categories["final"] != "yes")
    if sector_not_final.any():
        raise Exception(
            "'demand_categories' rows with a sector need 'yes' under final, as a Final Energy Sector is a part of "
            f"final energy:\n{demand_categories[sector_not_final].to_string()}"
        )
    stem_rules = tables["stems"]
    misplaced = stem_rules["stem"].str.contains(carrier_placeholder, regex=False) & (
        (stem_rules["quantity"] != final_quantity)
        | (stem_rules["stem"].str.count(re.escape(carrier_placeholder)) != 1)
        | ~stem_rules["stem"].str.endswith(f"|{carrier_placeholder}"))
    if misplaced.any():
        raise Exception(
            f"Only stems of quantity '{final_quantity}' may hold '{carrier_placeholder}', once, as their last segment "
            f"after the first:\n{stem_rules[misplaced].to_string()}"
        )
    misplaced = (stem_rules["quantity"] == final_quantity) & stem_rules["stem"].str.contains(source_placeholder,
                                                                                              regex=False)
    if misplaced.any():
        raise Exception(
            f"Stems of quantity '{final_quantity}' can't hold '{source_placeholder}', as the Mapping Rules give no "
            f"segments for on-site fuel use:\n{stem_rules[misplaced].to_string()}"
        )
    misplaced = (stem_rules["sector"] != "") & (stem_rules["quantity"] != final_quantity)
    if misplaced.any():
        raise Exception(
            f"Only stems of quantity '{final_quantity}' take a sector; the 'demand_categories' rules give demand its "
            f"Final Energy Sectors:\n{stem_rules[misplaced].to_string()}"
        )
    output_rows = stem_rules[stem_rules["quantity"] == "output"]
    output_kinds = set(zip(output_rows["commodity"], output_rows["area_kind"]))
    overlapping = [
        (commodity, kind) in output_kinds or (commodity, "") in output_kinds
        or (kind == "" and commodity in set(output_rows["commodity"]))
        for commodity, kind in stem_rules[["commodity", "area_kind"]].itertuples(index=False)
    ]
    misplaced = (stem_rules["quantity"] == final_quantity) & pd.Series(overlapping, index=stem_rules.index, dtype=bool)
    if misplaced.any():
        raise Exception(
            f"Stems of quantity '{final_quantity}' can't cover a commodity and Area Kind that an 'output' stem "
            "covers: the fuel there makes reported output, so it would count twice.\n"
            f"{stem_rules[misplaced].to_string()}"
        )
    stems = tables["stems"]["stem"]
    misplaced = stems.str.contains(source_placeholder, regex=False) & (
        (stems.str.count(re.escape(source_placeholder)) != 1)
        | ~stems.map(lambda stem: source_placeholder in stem.split("|")[1:]))
    if misplaced.any():
        raise Exception(
            f"A stem may hold '{source_placeholder}' once, as a whole segment after the first:\n"
            f"{tables['stems'][misplaced].to_string()}"
        )
    below_total = [
        stem_top(stem).startswith(f"{total}|") or (stem_top(stem) == total and source_placeholder in stem)
        for stem, total in tables["stems"][["stem", "total"]].itertuples(index=False)
    ]
    misplaced = (tables["stems"]["total"] != "") & ~pd.Series(below_total, index=tables["stems"].index, dtype=bool)
    if misplaced.any():
        raise Exception(
            f"A stem's total must be above it, or above or at the part before '{source_placeholder}':\n"
            f"{tables['stems'][misplaced].to_string()}"
        )
    for pattern in tables["areas"]["pattern"]:
        try:
            re.compile(pattern)
        except re.error as error:
            raise Exception(f"The 'areas' pattern '{pattern}' is no regular expression: {error}")
    check_optiflow_rules(tables["optiflow"])
    return tables


def sector_variables(stem: str, sector: str) -> list[str]:
    """Name the IAMC Variables that demand under a stem is also reported under, by its Final Energy Sector.

    The sector goes after the stem's first segment, at each of its levels: demand under
    'Final Energy|Electricity' in sector 'Carbon Management|Carbon Capture and Storage' is
    also reported under 'Final Energy|Carbon Management|Electricity' and
    'Final Energy|Carbon Management|Carbon Capture and Storage|Electricity'.

    Args:
        stem (str): The demand stem, e.g. 'Final Energy|Electricity'.
        sector (str): The Final Energy Sector, e.g. 'Carbon Management|Carbon Capture and Storage'.

    Returns:
        list[str]: One IAMC Variable per level of the sector, the broadest first.
    """
    first, _, rest = stem.partition("|")
    levels = sector.split("|")
    return ["|".join([first, *levels[:length], rest]) for length in range(1, len(levels) + 1)]


def sector_other(variable: str, sector: str) -> str:
    """Name the sector's Other that a sector variable (sector_variables) falls back to.

    Args:
        variable (str): A sector variable, e.g. 'Final Energy|Residential and Commercial|Solar'.
        sector (str): The Final Energy Sector it was made with, e.g. 'Residential and Commercial'.

    Returns:
        str: The variable cut back to the sector, with 'Other' below it, e.g.
            'Final Energy|Residential and Commercial|Other'.
    """
    first = variable.split("|")[0]
    levels = sector.split("|")
    depth = next(length for length in range(len(levels), 0, -1)
                 if variable.startswith("|".join([first, *levels[:length]]) + "|"))
    return "|".join([first, *levels[:depth], "Other"])


def fill_carrier(stem: str, carrier: str) -> tuple[str, str]:
    """Fill a carrier into a stem of on-site fuel use.

    Args:
        stem (str): The stem, e.g. 'Final Energy|{carrier}'.
        carrier (str): The carrier, e.g. 'Gases|Gas'.

    Returns:
        tuple[str, str]: The stem with the carrier's first segment for the placeholder, and the
            carrier's other segments, to go below it: ('Final Energy|Gases', 'Gas'). A stem
            without the placeholder is given back with the whole carrier.
    """
    if not stem.endswith(f"|{carrier_placeholder}"):
        return stem, carrier
    first, _, rest = carrier.partition("|")
    return stem.replace(carrier_placeholder, first), rest


def check_optiflow_rules(optiflow: pd.DataFrame) -> None:
    """Refuse 'optiflow' rules with an unknown role, a pattern that is no regular expression, a
    factor that is no number, a missing pool, unit or variable, or targets their role doesn't take.

    Args:
        optiflow (pd.DataFrame): The 'optiflow' rule table.
    """
    def refuse(problem: str, rows: pd.Series) -> None:
        if rows.any():
            raise Exception(f"'optiflow' rules {problem}:\n{optiflow[rows].to_string()}")

    refuse(f"need a role of {optiflow_roles}", ~optiflow["role"].isin(optiflow_roles))
    refuse("need a unit", optiflow["unit"] == "")
    refuse(f"of roles {pool_roles} need a pool", optiflow["role"].isin(pool_roles) & (optiflow["pool"] == ""))
    refuse("of role 'report' need a variable", (optiflow["role"] == "report") & (optiflow["variable"] == ""))
    refuse("of roles other than 'capture' and 'fuel' take no removal or emissions",
           ~optiflow["role"].isin(["capture", "fuel"]) & ((optiflow["removal"] != "") | (optiflow["emissions"] != "")))
    refuse("of role 'fuel' take no variable or removal, only emissions",
           (optiflow["role"] == "fuel") & ((optiflow["variable"] != "") | (optiflow["removal"] != "")))
    refuse("need a number or nothing under factor", ~optiflow["factor"].map(is_number))
    for column in optiflow_patterns:
        for pattern in optiflow[column].unique():
            try:
                re.compile(pattern)
            except re.error as error:
                raise Exception(f"The 'optiflow' {column} pattern '{pattern}' is no regular expression: {error}")


def is_number(text: str) -> bool:
    """Tell whether a factor cell is empty or a number.

    Args:
        text (str): The cell.

    Returns:
        bool: True if it is empty or reads as a float.
    """
    try:
        float(text or 1)
    except ValueError:
        return False
    return True


def match_optiflow_rules(flows: pd.DataFrame, optiflow: pd.DataFrame) -> pd.DataFrame:
    """Pair OptiFlow flows with every 'optiflow' rule they match.

    Args:
        flows (pd.DataFrame): Rows with the columns 'from_process', 'to_process' and 'flow'.
        optiflow (pd.DataFrame): The 'optiflow' table from load_rules.

    Returns:
        pd.DataFrame: One row per flow and rule it matches: the flow's columns, its value times
            the rule's factor (empty is 1), and the rule's columns under their own names, with
            'unit' as 'value_unit'. A flow matching no rule is left out.
    """
    edges = flows[optiflow_patterns].drop_duplicates()
    pairs = []
    for rule in optiflow.itertuples(index=False):
        matches = pd.Series(True, index=edges.index)
        for column in optiflow_patterns:
            pattern = getattr(rule, column)
            if pattern:
                compiled = re.compile(pattern)
                matches &= edges[column].map(lambda name: compiled.fullmatch(name) is not None)
        rule_columns = {column: getattr(rule, column) for column in optiflow.columns if column not in optiflow_patterns}
        pairs.append(edges[matches].assign(**rule_columns))
    columns = optiflow_patterns + [column for column in optiflow.columns if column not in optiflow_patterns]
    pairs = pd.concat(pairs, ignore_index=True) if pairs else pd.DataFrame(columns=columns)
    matched = flows.drop(columns=["value_unit"], errors="ignore").merge(pairs, on=optiflow_patterns)
    matched["value"] = matched["value"] * matched.pop("factor").replace("", "1").astype(float)
    return matched.rename(columns={"unit": "value_unit"})


def match_area_kinds(areas: pd.Series, area_rules: pd.DataFrame) -> pd.Series:
    """Find the Area Kind of each area: that of the first 'areas' rule whose pattern it contains.

    Args:
        areas (pd.Series): Balmorel area names.
        area_rules (pd.DataFrame): The 'areas' table from load_rules.

    Returns:
        pd.Series: The Area Kind per area, default_area_kind where no pattern matches.
    """
    patterns = [(re.compile(pattern), kind) for pattern, kind in area_rules[["pattern", "area_kind"]].itertuples(index=False)]

    def kind_of(area: str) -> str:
        for pattern, kind in patterns:
            if pattern.search(area):
                return kind
        return default_area_kind

    kinds = {area: kind_of(area) for area in areas.unique()}
    return areas.map(kinds)


def match_mapping_rules(units: pd.DataFrame, mapping: pd.DataFrame, column: str = "segments") -> pd.Series:
    """Find the segments template, or another column, of the Mapping Rule that wins for each unit.

    Args:
        units (pd.DataFrame): Rows with the columns 'unit_name', 'tech_type', 'fuel' and 'commodity'.
        mapping (pd.DataFrame): The 'mapping' table from load_rules.
        column (str, optional): The rule column to give, e.g. 'primary'. Rules that leave it
            empty are passed over, so the next matching rule that fills it wins (segments are
            never empty). Defaults to 'segments'.

    Returns:
        pd.Series: The winning rule's value per row of `units`; '' where no rule matches.
    """
    ordered = mapping[mapping[column] != ""]
    ordered = ordered.assign(
        specificity=(ordered[mapping_keys] != "").sum(axis=1),
        order=np.arange(len(ordered)),
    ).sort_values(["priority", "specificity", "order"], ascending=False)

    segments = pd.Series("", index=units.index, dtype=object)
    for rule in ordered.itertuples():
        open_rows = segments == ""
        if not open_rows.any():
            break
        if rule.tech_type:
            open_rows &= units["tech_type"] == rule.tech_type
        if rule.fuel:
            open_rows &= units["fuel"] == rule.fuel
        if rule.commodity:
            open_rows &= units["commodity"] == rule.commodity
        if rule.unit_pattern:
            pattern = re.compile(rule.unit_pattern)
            open_rows &= units["unit_name"].map(lambda name: pattern.search(name) is not None)
        segments[open_rows] = getattr(rule, column)
    return segments


def stem_top(stem: str) -> str:
    """The part of a stem before the Source placeholder, or the whole stem if it has none.

    Args:
        stem (str): The stem, e.g. 'Primary Energy|{source}|Electricity'.

    Returns:
        str: E.g. 'Primary Energy'.
    """
    return stem.split(f"|{source_placeholder}")[0]


def fill_source(stem: str, source: str, names: set[str]) -> str:
    """Fill the Source into a stem that has the '{source}' placeholder.

    Args:
        stem (str): The stem, e.g. 'Primary Energy|{source}|Electricity'.
        source (str): The Source, the first segment the Mapping Rules give, e.g. 'Gas'.
        names (set[str]): IAMC Variables in the Definitions Snapshot.

    Returns:
        str: The filled stem if the snapshot has it, e.g. 'Primary Energy|Gas|Electricity'.
            Else the stem cut back to the Source, e.g. 'Primary Energy|Wind', if the snapshot has
            it without children, as for sources whose use the common definitions don't split.
            Else ''.
    """
    filled = stem.replace(source_placeholder, source)
    if filled in names:
        return filled
    cut_back = f"{stem_top(stem)}|{source}"
    if cut_back in names and not any(name.startswith(f"{cut_back}|") for name in names):
        return cut_back
    return ""


#%% ------------------------------- ###
###     2. Definitions Snapshot     ###
### ------------------------------- ###

def load_definitions(path: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a Definitions Snapshot: IAMC Variables with their units, and IAMC Regions.

    Args:
        path (str | Path | None, optional): Folder with 'variables.csv' (variable, unit, ...) and
            'regions.csv' (region, iso3). Defaults to the snapshot shipped with pybalmorel.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The variables and regions tables.
    """
    folder = Path(path) if path is not None else definitions_dir
    variables_file = folder / "variables.csv"
    regions_file = folder / "regions.csv"
    if not (variables_file.exists() and regions_file.exists()):
        hint = (
            " Generate it with `pixi run update-iamc-definitions` in the pybalmorel repository."
            if path is None
            else ""
        )
        raise Exception(f"No Definitions Snapshot in '{folder}': it needs variables.csv and regions.csv.{hint}")

    variables = read_table(variables_file, ["variable", "unit"], "variables").drop_duplicates("variable")
    regions = read_table(regions_file, ["region", "iso3"], "regions")
    return variables, regions


def load_template(path: str | Path) -> tuple[set[str], set[str]]:
    """Read the names a Template accepts.

    Args:
        path (str | Path): The Template, an .xlsx with an 'Extended List' sheet (column 'variable')
            and optionally a 'Region' sheet (column 'region'), e.g. NMSF Study 2's varlist.xlsx.

    Returns:
        tuple[set[str], set[str]]: The accepted IAMC Variables, and IAMC Regions (empty if the
            Template has no Region sheet).
    """
    sheets = pd.read_excel(path, sheet_name=None)
    by_lower_name = {name.strip().lower(): sheet for name, sheet in sheets.items()}
    if "extended list" not in by_lower_name:
        raise Exception(f"The Template '{path}' has no 'Extended List' sheet; it has {list(sheets)}.")

    extended = by_lower_name["extended list"]
    extended.columns = [str(column).strip().lower() for column in extended.columns]
    variables = set(extended["variable"].dropna().astype(str).str.strip())

    regions = set()
    if "region" in by_lower_name:
        region_sheet = by_lower_name["region"]
        region_sheet.columns = [str(column).strip().lower() for column in region_sheet.columns]
        regions = set(region_sheet["region"].dropna().astype(str).str.strip())
    return variables, regions


#%% ------------------------------- ###
###        3. Rule Checking         ###
### ------------------------------- ###

def check_rules(definitions: str | Path | None = None,
                rules: dict[str, str | Path | pd.DataFrame] | None = None) -> pd.DataFrame:
    """List rule rows that target names the Definitions Snapshot doesn't have.

    Run after updating the snapshot: every row listed needs fixing, or its output silently
    moves to a parent or to Other.

    Args:
        definitions (str | Path | None, optional): Snapshot folder. Defaults to the shipped one.
        rules (dict[str, str | Path | pd.DataFrame] | None, optional): Rule rows passed as in
            load_rules. Defaults to None.

    Returns:
        pd.DataFrame: One row per problem, with the columns 'table', 'value' and 'problem'.
    """
    variables, regions = load_definitions(definitions)
    tables = load_rules(rules)
    names = set(variables["variable"])
    stems = tables["stems"]["stem"].unique()
    segment_names = {segment for name in names for segment in name.split("|")}
    problems = []

    templated = [stem for stem in stems if source_placeholder in stem]
    for stem in stems:
        if stem not in names and stem not in templated and carrier_placeholder not in stem:
            problems.append(("stems", stem, "stem is not an IAMC Variable"))
    totals = tables["stems"].loc[tables["stems"]["total"] != "", ["stem", "total"]].drop_duplicates()
    for total in totals["total"].unique():
        if total not in names:
            problems.append(("stems", total, "total is not an IAMC Variable"))
    with_total = set(totals["stem"])

    # Sources: the Fuel Categories of fuels that count as Primary Energy, and the first
    # segments the Mapping Rules give literally
    fuels = tables["fuels"]
    sources = set(fuels.loc[fuels["primary"] != "no", "category"])
    for template in tables["mapping"]["segments"].unique():
        first = template.split("|")[0]
        if template not in (not_reported, import_unit, optiflow_unit) and "{category}" not in first:
            sources.add(first)
    for stem in templated:
        top = stem_top(stem)
        for source in sorted(sources):
            if fill_source(stem, source, names):
                continue
            if f"{top}|{source}" in names and stem in with_total:
                problems.append(("stems", stem, f"has no IAMC Variable for Source '{source}', which counts towards "
                                                f"'{top}|{source}' and the totals above it only"))
            elif f"{top}|{source}" in names:
                problems.append(("stems", stem, f"has no IAMC Variable for Source '{source}', which is not reported"))
            elif not fill_source(stem, "Other", names):
                problems.append(("stems", stem, f"has no IAMC Variable for Source '{source}', nor for Other"))
            else:
                problems.append(("stems", stem, f"has no IAMC Variable for Source '{source}', reported under Other"))

    for category in tables["fuels"]["category"].unique():
        if category not in segment_names:
            problems.append(("fuels", category, "category is no segment of any IAMC Variable"))

    for template in tables["mapping"]["segments"].unique():
        if template in (not_reported, import_unit, optiflow_unit):
            continue
        literal = template.replace("{category}|", "").replace("|{category}", "").replace("{category}", "")
        if not literal:
            continue
        if "{category}" in template:
            missing = [segment for segment in literal.split("|") if segment not in segment_names]
            if missing:
                problems.append(("mapping", template, f"segments {missing} occur in no IAMC Variable"))
        elif not any(f"{stem}|{literal}" in names for stem in stems):
            problems.append(("mapping", template, "is a child of no stem"))

    for aggregate in tables["aggregates"]["aggregate"].unique():
        first, _, rest = aggregate.partition("|")
        in_templated = any(
            fill_source(stem, first, names) and "|".join(filter(None, [fill_source(stem, first, names), rest])) in names
            for stem in templated
        )
        if not in_templated and not any(f"{stem}|{aggregate}" in names for stem in stems):
            problems.append(("aggregates", aggregate, "is a child of no stem"))

    known_iso3 = set(regions["iso3"])
    for country, iso3 in tables["countries"][["country", "iso3"]].itertuples(index=False):
        if iso3 not in known_iso3:
            problems.append(("countries", country, f"ISO3 code '{iso3}' has no IAMC Region"))

    for column in optiflow_targets:
        for target in tables["optiflow"][column].unique():
            if target and target not in names:
                problems.append(("optiflow", target, f"{column} is not an IAMC Variable"))

    demand_stems = tables["stems"][tables["stems"]["quantity"] == "demand"]
    with_sector = tables["demand_categories"][tables["demand_categories"]["sector"] != ""]
    for commodity, sector in with_sector[["commodity", "sector"]].drop_duplicates().itertuples(index=False):
        for stem in demand_stems.loc[demand_stems["commodity"] == commodity, "stem"].unique():
            for variable in sector_variables(stem, sector):
                if variable not in names:
                    problems.append(("demand_categories", variable, f"sector '{sector}' gives no IAMC Variable"))

    # On-site fuel use: every carrier under each of its stems, and under their sectors (or the sector's Other)
    carriers = sorted((set(tables["fuels"]["carrier"]) | set(tables["mapping"]["carrier"])) - {"", not_reported})
    final_stems = tables["stems"][tables["stems"]["quantity"] == final_quantity]
    for stem, sector in final_stems[["stem", "sector"]].drop_duplicates().itertuples(index=False):
        for carrier in carriers:
            filled, rest = fill_carrier(stem, carrier)
            if filled not in names or (rest and f"{filled}|{rest}" not in names):
                problems.append(("stems", stem, f"has no IAMC Variable for carrier '{carrier}'"))
                continue
            for variable in sector_variables(filled, sector) if sector else []:
                if variable in names and rest and f"{variable}|{rest}" not in names:
                    problems.append(("stems", variable, f"sector '{sector}' has no IAMC Variable for carrier "
                                                        f"'{carrier}'"))
                elif variable not in names and sector_other(variable, sector) not in names:
                    problems.append(("stems", variable, f"sector '{sector}' gives no IAMC Variable, nor an Other"))

    kinds = set(tables["areas"]["area_kind"]) | {default_area_kind}
    for kind in set(tables["stems"]["area_kind"]) - kinds - {""}:
        problems.append(("stems", kind, f"is no Area Kind of the 'areas' rules, which give {sorted(kinds)}"))

    return pd.DataFrame(problems, columns=["table", "value", "problem"])

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

# Columns of each rule table, and the key whose rows a caller's rows replace
rule_tables = {
    "fuels": {"columns": ["fuel", "category"], "key": ["fuel"]},
    "mapping": {"columns": ["tech_type", "fuel", "commodity", "unit_pattern", "segments"], "key": None},
    "stems": {"columns": ["quantity", "commodity", "area_kind", "stem"], "key": ["quantity", "commodity", "area_kind"]},
    "aggregates": {"columns": ["aggregate", "component"], "key": ["aggregate"]},
    "countries": {"columns": ["country", "iso3"], "key": ["country"]},
    "areas": {"columns": ["pattern", "area_kind"], "key": ["pattern"]},
    "demand_categories": {"columns": ["commodity", "demand_category", "final"], "key": ["commodity", "demand_category"]},
    "optiflow": {"columns": ["from_process", "to_process", "flow", "role", "pool", "unit", "variable", "removal",
                             "emissions"], "key": None},
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
optiflow_roles = ("balmorel", "capture", "store", "report")
pool_roles = ("balmorel", "capture", "store")
optiflow_patterns = ["from_process", "to_process", "flow"]
optiflow_targets = ["variable", "removal", "emissions"]
# Area Kind of areas no pattern in the 'areas' table matches
default_area_kind = "district heating"


#%% ------------------------------- ###
###          1. Rule Tables         ###
### ------------------------------- ###

def read_table(source: str | Path | pd.DataFrame, columns: list[str], name: str) -> pd.DataFrame:
    """Read a rule or definitions table as strings, with empty cells as ''.

    Args:
        source (str | Path | pd.DataFrame): A CSV file ('#' starts a comment line) or a DataFrame.
        columns (list[str]): Columns the table must have; others are dropped.
        name (str): Name of the table, for error messages.

    Returns:
        pd.DataFrame: The table with exactly `columns`, all strings, stripped.
    """
    if isinstance(source, pd.DataFrame):
        table = source.copy()
    else:
        table = pd.read_csv(source, dtype=str, keep_default_na=False, comment="#")

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
        dict[str, pd.DataFrame]: The tables by name. The 'mapping' table has a 'priority'
            column: 1 for the caller's rows, 0 for the shipped ones. The 'optiflow' table has
            the caller's rows first; every row applies to every flow it matches.
    """
    overrides = overrides or {}
    unknown = [name for name in overrides if name not in rule_tables]
    if unknown:
        raise Exception(f"Unknown rule tables {unknown}; choose from {list(rule_tables)}.")

    tables = {}
    for name, spec in rule_tables.items():
        shipped = read_table(rules_dir / f"{name}.csv", spec["columns"], name)
        caller = (
            read_table(overrides[name], spec["columns"], name)
            if name in overrides
            else pd.DataFrame(columns=spec["columns"], dtype=str)
        )

        if name == "mapping":
            table = pd.concat((caller.assign(priority=1), shipped.assign(priority=0)), ignore_index=True)
        elif name == "optiflow":
            table = pd.concat((caller, shipped), ignore_index=True)
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

    empty = tables["mapping"]["segments"] == ""
    if empty.any():
        raise Exception(
            f"Mapping Rules need segments, or '{not_reported}' for not reported:\n"
            f"{tables['mapping'][empty].to_string()}"
        )
    unclear = ~tables["demand_categories"]["final"].isin(["yes", "no"])
    if unclear.any():
        raise Exception(
            "The 'demand_categories' rules need 'yes' or 'no' under final:\n"
            f"{tables['demand_categories'][unclear].to_string()}"
        )
    for pattern in tables["areas"]["pattern"]:
        try:
            re.compile(pattern)
        except re.error as error:
            raise Exception(f"The 'areas' pattern '{pattern}' is no regular expression: {error}")
    check_optiflow_rules(tables["optiflow"])
    return tables


def check_optiflow_rules(optiflow: pd.DataFrame) -> None:
    """Refuse 'optiflow' rules with an unknown role, a pattern that is no regular expression, or a
    missing pool, unit or variable.

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
    refuse("of roles other than 'capture' take no removal or emissions",
           (optiflow["role"] != "capture") & ((optiflow["removal"] != "") | (optiflow["emissions"] != "")))
    for column in optiflow_patterns:
        for pattern in optiflow[column].unique():
            try:
                re.compile(pattern)
            except re.error as error:
                raise Exception(f"The 'optiflow' {column} pattern '{pattern}' is no regular expression: {error}")


def match_optiflow_rules(flows: pd.DataFrame, optiflow: pd.DataFrame) -> pd.DataFrame:
    """Pair OptiFlow flows with every 'optiflow' rule they match.

    Args:
        flows (pd.DataFrame): Rows with the columns 'from_process', 'to_process' and 'flow'.
        optiflow (pd.DataFrame): The 'optiflow' table from load_rules.

    Returns:
        pd.DataFrame: One row per flow and rule it matches: the flow's columns, and the rule's
            under their own names, with 'unit' as 'value_unit'. A flow matching no rule is left
            out.
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


def match_mapping_rules(units: pd.DataFrame, mapping: pd.DataFrame) -> pd.Series:
    """Find the segments template of the Mapping Rule that wins for each unit.

    Args:
        units (pd.DataFrame): Rows with the columns 'unit_name', 'tech_type', 'fuel' and 'commodity'.
        mapping (pd.DataFrame): The 'mapping' table from load_rules.

    Returns:
        pd.Series: The winning rule's segments per row of `units`; '' where no rule matches.
    """
    ordered = mapping.assign(
        specificity=(mapping[mapping_keys] != "").sum(axis=1),
        order=np.arange(len(mapping)),
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
        segments[open_rows] = rule.segments
    return segments


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

    for stem in stems:
        if stem not in names:
            problems.append(("stems", stem, "stem is not an IAMC Variable"))

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
        if not any(f"{stem}|{aggregate}" in names for stem in stems):
            problems.append(("aggregates", aggregate, "is a child of no stem"))

    known_iso3 = set(regions["iso3"])
    for country, iso3 in tables["countries"][["country", "iso3"]].itertuples(index=False):
        if iso3 not in known_iso3:
            problems.append(("countries", country, f"ISO3 code '{iso3}' has no IAMC Region"))

    for column in optiflow_targets:
        for target in tables["optiflow"][column].unique():
            if target and target not in names:
                problems.append(("optiflow", target, f"{column} is not an IAMC Variable"))

    kinds = set(tables["areas"]["area_kind"]) | {default_area_kind}
    for kind in set(tables["stems"]["area_kind"]) - kinds - {""}:
        problems.append(("stems", kind, f"is no Area Kind of the 'areas' rules, which give {sorted(kinds)}"))

    return pd.DataFrame(problems, columns=["table", "value", "problem"])

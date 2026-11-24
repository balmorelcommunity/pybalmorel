"""
GAMS-dependent tests of the IAMC conversion on the example MainResults: the
IAMC totals of electricity, heat, hydrogen and CO2 equal the raw results, centralized
heat and hydrogen balances, and Mapping Rules and Fuel Categories cover every
unit. Needs a GAMS installation and the shipped Definitions Snapshot.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
import os
import pandas as pd
import pytest

from pybalmorel import MainResults
from pybalmorel.iamc import load_definitions, load_rules, read_mainresults
from pybalmorel.iamc.rules import (default_area_kind, definitions_dir, import_unit, match_area_kinds,
                                   match_mapping_rules, not_reported)

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in your .env file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)

pytestmark = pytest.mark.skipif(not (definitions_dir / "variables.csv").exists(),
                                reason="No Definitions Snapshot yet: run `pixi run update-iamc-definitions`")

scenarios = ["Example1", "Example2", "Example3"]
twh_to_ej = 3.6e-3


#%% ------------------------------- ###
###            Fixtures             ###
### ------------------------------- ###

@pytest.fixture(scope="module")
def results() -> MainResults:
    return MainResults(files=[f"MainResults_{scenario}.gdx" for scenario in scenarios], paths="examples/files",
                       scenario_names=scenarios, system_directory=gams_system_directory)


@pytest.fixture(scope="module")
def converted(results: MainResults) -> tuple[pd.DataFrame, pd.DataFrame]:
    return results.to_iamc("Balmorel")


@pytest.fixture(scope="module")
def raw(results: MainResults) -> pd.DataFrame:
    """The raw long table."""
    return read_mainresults(results)


@pytest.fixture(scope="module")
def region_countries() -> pd.Series:
    """The Balmorel countries with an IAMC Region."""
    _, regions = load_definitions()
    return load_rules()["countries"].merge(regions, on="iso3")["country"]


@pytest.fixture(scope="module")
def in_regions(raw: pd.DataFrame, region_countries: pd.Series) -> pd.DataFrame:
    """The raw long table of countries with an IAMC Region, with Area Kinds ('' for rows
    without an area)."""
    area_rules = load_rules()["areas"]
    long = raw[raw["country"].isin(region_countries)]
    return long.assign(area_kind=match_area_kinds(long["area"], area_rules).where(long["area"] != "", ""),
                       to_area_kind=match_area_kinds(long["to_area"], area_rules).where(long["to_area"] != "", ""))


@pytest.fixture(scope="module")
def reported(in_regions: pd.DataFrame) -> pd.DataFrame:
    """The raw electricity rows the conversion should report: units without storage."""
    long = in_regions[in_regions["commodity"] == "ELECTRICITY"]
    return long[match_mapping_rules(long, load_rules()["mapping"]) != not_reported]


@pytest.fixture(scope="module")
def heat(in_regions: pd.DataFrame) -> dict[str, pd.Series]:
    """Raw centralized heat per scenario, in TWh: the output of district heating units
    without storage, its demand per category, and heat exchanged with other areas, netted
    per pair of areas and year."""
    long = in_regions[(in_regions["commodity"] == "HEAT") & (in_regions["quantity"] != "capacity")]
    assert set(long["value_unit"]) <= {"TWh"}
    in_dh = long[long["area_kind"] == default_area_kind]

    output = in_dh[in_dh["quantity"] == "output"]
    output = output[match_mapping_rules(output, load_rules()["mapping"]) != not_reported]
    demand = in_dh[in_dh["quantity"] == "demand"]

    exchange = long[(long["quantity"] == "exchange")
                    & ((long["area_kind"] == default_area_kind) != (long["to_area_kind"] == default_area_kind))]
    from_dh = exchange["area_kind"] == default_area_kind
    net = exchange.assign(
        dh=exchange["area"].where(from_dh, exchange["to_area"]),
        other=exchange["to_area"].where(from_dh, exchange["area"]),
        out_of_dh=exchange["value"].where(from_dh, -exchange["value"]),
    ).groupby(["scenario", "year", "dh", "other"])["out_of_dh"].sum()

    def per_scenario(values: pd.Series) -> pd.Series:
        return values.groupby("scenario").sum().reindex(scenarios, fill_value=0.0)

    return {
        "output": per_scenario(output["value"].groupby(output["scenario"]).sum()),
        "exogenous": per_scenario(demand.loc[demand["demand_category"] == "EXOGENOUS", "value"]
                                  .groupby(demand["scenario"]).sum()),
        "losses": per_scenario(demand.loc[demand["demand_category"] != "EXOGENOUS", "value"]
                               .groupby(demand["scenario"]).sum()),
        "net_out": per_scenario(net.clip(lower=0)),
        "net_in": per_scenario(-net.clip(upper=0)),
    }


@pytest.fixture(scope="module")
def hydrogen(raw: pd.DataFrame, in_regions: pd.DataFrame, region_countries: pd.Series) -> dict[str, pd.Series]:
    """Raw hydrogen per scenario: capacity (GW) and output (TWh) of units in any kind of area,
    without storage and import units, demand in final categories, and net exports (TWh):
    transmission to other countries, less transmission from them, less import units' output."""
    rules = load_rules()
    long = in_regions[in_regions["commodity"] == "HYDROGEN"]
    units = long[long["quantity"].isin(["capacity", "output"])]
    targets = match_mapping_rules(units, rules["mapping"])
    made = units[~targets.isin([not_reported, import_unit])]
    imported = units[(targets == import_unit) & (units["quantity"] == "output")]

    categories = rules["demand_categories"]
    final = categories.loc[(categories["commodity"] == "HYDROGEN") & (categories["final"] == "yes"),
                           "demand_category"]
    demand = long[(long["quantity"] == "demand") & long["demand_category"].isin(final)]

    exchange = raw[(raw["commodity"] == "HYDROGEN") & (raw["quantity"] == "exchange")]
    abroad = exchange[(exchange["to_country"] != "") & (exchange["to_country"] != exchange["country"])]
    exports = abroad[abroad["country"].isin(region_countries)]
    imports = abroad[abroad["to_country"].isin(region_countries)]

    def per_scenario(rows: pd.DataFrame) -> pd.Series:
        return rows.groupby("scenario")["value"].sum().reindex(scenarios, fill_value=0.0)

    assert set(long.loc[long["quantity"] != "capacity", "value_unit"]) | set(exchange["value_unit"]) <= {"TWh"}
    assert set(made.loc[made["quantity"] == "capacity", "value_unit"]) <= {"GW"}
    return {
        "capacity": per_scenario(made[made["quantity"] == "capacity"]),
        "output": per_scenario(made[made["quantity"] == "output"]),
        "final_demand": per_scenario(demand),
        "net_exports": per_scenario(exports) - per_scenario(imports) - per_scenario(imported),
        "has_demand": long[long["quantity"] == "demand"].groupby("scenario").size().reindex(scenarios) > 0,
    }


@pytest.fixture(scope="module")
def carbon(in_regions: pd.DataFrame) -> dict[str, pd.Series]:
    """Raw emissions and captured CO2 per scenario (Mt CO2), of the part of each unit's output
    that is reported: electricity and hydrogen in any kind of area, heat in district heating,
    without storage and import units."""
    output = in_regions[(in_regions["quantity"] == "output") & (in_regions["value"] > 0)]
    targets = match_mapping_rules(output, load_rules()["mapping"])
    reported = (~targets.isin([not_reported, import_unit])
                & (output["commodity"].isin(["ELECTRICITY", "HYDROGEN"])
                   | ((output["commodity"] == "HEAT") & (output["area_kind"] == default_area_kind))))
    keys = ["scenario", "year", "country", "area", "unit_name", "tech_type", "fuel"]
    share = (output["value"].where(reported, 0.0).groupby([output[key] for key in keys]).sum()
             / output.groupby(keys)["value"].sum()).rename("share").reset_index()

    rows = in_regions[in_regions["quantity"].isin(["emissions", "captured"])]
    assert set(rows["value_unit"]) <= {"kt CO2"}
    rows = rows.merge(share, on=keys, how="left").fillna({"share": 0.0})
    by_quantity = (rows["value"] * rows["share"] / 1e3).groupby([rows["quantity"], rows["scenario"]]).sum()
    return {quantity: by_quantity.get(quantity, pd.Series(dtype=float)).reindex(scenarios, fill_value=0.0)
            for quantity in ("emissions", "captured")}


def total(data: pd.DataFrame, variable: str) -> pd.Series:
    """Sum of one IAMC Variable over regions and years, per scenario."""
    years = [column for column in data.columns if isinstance(column, int)]
    rows = data[data["Variable"] == variable]
    return rows.groupby("Scenario")[years].sum().sum(axis=1).reindex(scenarios, fill_value=0.0)


#%% ------------------------------- ###
###              Tests              ###
### ------------------------------- ###

def test_electricity_totals_equal_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                              reported: pd.DataFrame) -> None:
    data, _ = converted

    output = reported[reported["quantity"] == "output"]
    assert set(output["value_unit"]) == {"TWh"}
    raw_output = output.groupby("scenario")["value"].sum().reindex(scenarios) * twh_to_ej
    pd.testing.assert_series_equal(total(data, "Secondary Energy|Electricity"), raw_output,
                                   check_names=False, check_index_type=False, rtol=1e-9)

    # Backup capacity is never reported
    capacity = reported[(reported["quantity"] == "capacity")
                        & ~reported["unit_name"].str.contains("GNR_BACKUP")]
    assert set(capacity["value_unit"]) == {"GW"}
    raw_capacity = capacity.groupby("scenario")["value"].sum().reindex(scenarios)
    pd.testing.assert_series_equal(total(data, "Capacity|Electricity"), raw_capacity,
                                   check_names=False, check_index_type=False, rtol=1e-9)


def test_heat_totals_equal_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                       heat: dict[str, pd.Series]) -> None:
    data, _ = converted
    pd.testing.assert_series_equal(total(data, "Secondary Energy|Heat"),
                                   (heat["output"] + heat["net_in"]) * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9)
    pd.testing.assert_series_equal(total(data, "Final Energy|Heat"),
                                   (heat["exogenous"] + heat["net_out"]) * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9)


def test_centralized_heat_balances(converted: tuple[pd.DataFrame, pd.DataFrame],
                                   heat: dict[str, pd.Series]) -> None:
    """What district heating makes and gets, less what it delivers, is its storage and
    transmission losses, unless the Conversion Notes say its heat doesn't add up. Example3's
    results have heat transmission (TRANS_LOSSES) but don't list it."""
    data, notes = converted
    off = set(notes.loc[notes["Note"].str.startswith("HEAT in district heating areas doesn't add up"), "Scenario"])
    assert off == {"Example3"}

    balanced = [scenario for scenario in scenarios if scenario not in off]
    difference = total(data, "Secondary Energy|Heat") - total(data, "Final Energy|Heat")
    pd.testing.assert_series_equal(difference[balanced], heat["losses"][balanced] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-3)


def test_hydrogen_totals_equal_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                           hydrogen: dict[str, pd.Series]) -> None:
    data, _ = converted
    pd.testing.assert_series_equal(total(data, "Capacity|Hydrogen"), hydrogen["capacity"],
                                   check_names=False, check_index_type=False, rtol=1e-9)
    pd.testing.assert_series_equal(total(data, "Secondary Energy|Hydrogen"), hydrogen["output"] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9)
    pd.testing.assert_series_equal(total(data, "Final Energy|Hydrogen"), hydrogen["final_demand"] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9)
    pd.testing.assert_series_equal(total(data, "Trade|Secondary Energy|Hydrogen [Volume]"),
                                   hydrogen["net_exports"] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9, atol=1e-12)


def test_hydrogen_balances(converted: tuple[pd.DataFrame, pd.DataFrame], hydrogen: dict[str, pd.Series]) -> None:
    """Scenarios with hydrogen demand add up; Example3's results have hydrogen units but no
    hydrogen demand, which the Conversion Notes say."""
    _, notes = converted
    assert not notes["Note"].str.startswith("HYDROGEN doesn't add up").any()
    no_demand = notes.loc[notes["Note"].str.startswith("The results give no demand of HYDROGEN"), "Scenario"]
    assert sorted(no_demand) == sorted(hydrogen["has_demand"].index[~hydrogen["has_demand"]])
    assert sorted(no_demand) == ["Example3"]


def test_rules_cover_every_unit(converted: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    _, notes = converted
    uncovered = notes[notes["Note"].str.contains("no Mapping Rule matches|fuel has no Fuel Category")]
    assert uncovered.empty, f"Units no rule covers:\n{uncovered.to_string()}"


def test_carbon_totals_equal_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                         carbon: dict[str, pd.Series]) -> None:
    """Emissions and captured CO2 of electricity, heat and hydrogen supply add up to the raw
    results, split by output. Only Example3 captures CO2, all of it fossil, so nothing is
    removed; Example1 and Example2 have no captured CO2, which the Conversion Notes say."""
    data, notes = converted
    supplies = ["Electricity", "Heat", "Hydrogen"]
    emissions = sum(total(data, f"Emissions|CO2|Energy|Supply|{supply}") for supply in supplies)
    captured = sum(total(data, f"Carbon Capture|Energy|Supply|{supply}") for supply in supplies)
    pd.testing.assert_series_equal(emissions, carbon["emissions"], check_names=False, check_index_type=False,
                                   rtol=1e-9)
    pd.testing.assert_series_equal(captured, carbon["captured"], check_names=False, check_index_type=False,
                                   rtol=1e-9)
    assert (carbon["captured"]["Example3"] > 0) and (total(data, "Carbon Removal|Geological Storage") == 0).all()

    no_captured = notes.loc[notes["Note"].str.startswith("The results give no captured CO2"), "Scenario"]
    assert sorted(no_captured) == ["Example1", "Example2"]
    assert not notes["Note"].str.contains("don't mark them w/ CCS|Units whose output the results don't give").any()


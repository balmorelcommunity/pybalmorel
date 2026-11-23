"""
GAMS-dependent tests of the IAMC conversion on the example MainResults: the
IAMC totals equal the raw results, centralized heat balances, and Mapping Rules
and Fuel Categories cover every unit. Needs a GAMS installation and the shipped
Definitions Snapshot.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
import os
import pandas as pd
import pytest

from pybalmorel import MainResults
from pybalmorel.iamc import load_definitions, load_rules, read_mainresults
from pybalmorel.iamc.rules import default_area_kind, definitions_dir, match_area_kinds, match_mapping_rules, not_reported

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
def in_regions(results: MainResults) -> pd.DataFrame:
    """The raw long table of countries with an IAMC Region, with Area Kinds."""
    long = read_mainresults(results)
    _, regions = load_definitions()
    rules = load_rules()
    countries = rules["countries"].merge(regions, on="iso3")["country"]
    long = long[long["country"].isin(countries)]
    return long.assign(area_kind=match_area_kinds(long["area"], rules["areas"]),
                       to_area_kind=match_area_kinds(long["to_area"], rules["areas"]))


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
    off = set(notes.loc[notes["Note"].str.startswith("District heating's heat doesn't add up"), "Scenario"])
    assert off == {"Example3"}

    balanced = [scenario for scenario in scenarios if scenario not in off]
    difference = total(data, "Secondary Energy|Heat") - total(data, "Final Energy|Heat")
    pd.testing.assert_series_equal(difference[balanced], heat["losses"][balanced] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-3)


def test_rules_cover_every_unit(converted: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    _, notes = converted
    uncovered = notes[notes["Note"].str.contains("no Mapping Rule matches|fuel has no Fuel Category")]
    assert uncovered.empty, f"Units no rule covers:\n{uncovered.to_string()}"

"""
GAMS-dependent tests of the IAMC conversion on the example MainResults: the
IAMC totals equal the raw results, and Mapping Rules and Fuel Categories cover
every unit. Needs a GAMS installation and the shipped Definitions Snapshot.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
import os
import pandas as pd
import pytest

from pybalmorel import MainResults
from pybalmorel.iamc import load_definitions, load_rules, read_mainresults
from pybalmorel.iamc.rules import definitions_dir, match_mapping_rules, not_reported

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
def reported(results: MainResults) -> pd.DataFrame:
    """The raw electricity rows the conversion should report: units in countries with an
    IAMC Region, without storage."""
    long = read_mainresults(results)
    _, regions = load_definitions()
    rules = load_rules()
    countries = rules["countries"].merge(regions, on="iso3")["country"]
    long = long[(long["commodity"] == "ELECTRICITY") & long["country"].isin(countries)]
    return long[match_mapping_rules(long, rules["mapping"]) != not_reported]


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


def test_rules_cover_every_unit(converted: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    _, notes = converted
    uncovered = notes[notes["Note"].str.contains("no Mapping Rule matches|fuel has no Fuel Category")]
    assert uncovered.empty, f"Units no rule covers:\n{uncovered.to_string()}"

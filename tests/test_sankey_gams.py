"""
Created on 26.11.2026

@author: Claude, Anthropic
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)

GAMS-dependent tests of the Sankey on the example MainResults: commodities balance at every
level of selection, what units make agrees with the IAMC data the converter makes of the same
results, and the MainResults methods draw. Needs a GAMS installation and the shipped
Definitions Snapshot.
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from pybalmorel import MainResults
from pybalmorel.iamc import read_mainresults
from pybalmorel.iamc.rules import definitions_dir
from pybalmorel.plotting import sankey_flows, compare_sankey_flows
from pybalmorel.plotting.sankey import mainresults_flows

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in your .env file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)

pytestmark = pytest.mark.skipif(not (definitions_dir / "variables.csv").exists(),
                                reason="No Definitions Snapshot yet: run `pixi run update-iamc-definitions`")

scenarios = ["Example1", "Example2", "Example3"]
scenario_years = [("Example1", 2030), ("Example1", 2050), ("Example2", 2030), ("Example2", 2050),
                  ("Example3", 2020), ("Example3", 2050)]
commodities = ["Electricity", "District Heat", "Hydrogen", "Gases", "On-site Heat"]
not_conversion = ["Imports", "Unaccounted", "Grid", "OptiFlow", "Ambient Heat"] + commodities


#%% ------------------------------- ###
###          1. Fixtures            ###
### ------------------------------- ###

@pytest.fixture(scope="module")
def results() -> MainResults:
    return MainResults(files=[f"MainResults_{scenario}.gdx" for scenario in scenarios], paths="examples/files",
                       scenario_names=scenarios, system_directory=gams_system_directory)


@pytest.fixture(scope="module")
def long(results: MainResults) -> pd.DataFrame:
    return read_mainresults(results, by_region=True)


@pytest.fixture(scope="module")
def converted(results: MainResults) -> tuple[pd.DataFrame, pd.DataFrame]:
    return results.to_iamc("Balmorel")


def selections(long: pd.DataFrame, scenario: str, year: int) -> list[dict[str, str | None]]:
    """All, one country, one region and one area of a scenario and year."""
    rows = long[(long["scenario"] == scenario) & (long["year"] == year) & (long["country"] == "DENMARK")]
    area = sorted(rows.loc[rows["quantity"] == "output", "area"].dropna().unique())[0]
    return [{}, {"countries": "DENMARK"}, {"regions": "DK1"}, {"areas": area}]


#%% ------------------------------- ###
###            2. Tests             ###
### ------------------------------- ###

@pytest.mark.parametrize("scenario, year", scenario_years)
def test_commodities_balance(long: pd.DataFrame, scenario: str, year: int):
    for selection in selections(long, scenario, year):
        flows = mainresults_flows(long, year, scenario, **selection)
        assert set(flows["Kind"]) <= {"flow", "loss", "ambient", "unaccounted"}
        assert (flows["Value"] > 0).all()
        inflow = flows.groupby("To")["Value"].sum()
        outflow = flows.groupby("From")["Value"].sum()
        for node in commodities:
            into, out_of = inflow.get(node, 0.0), outflow.get(node, 0.0)
            assert into == pytest.approx(out_of, rel=1e-6, abs=1e-6), (selection, node)


@pytest.mark.parametrize("scenario, year", scenario_years)
def test_conversion_agrees_with_iamc(long: pd.DataFrame, converted: tuple[pd.DataFrame, pd.DataFrame],
                                     scenario: str, year: int):
    # What units make from each Source is the same in MainResults and in the IAMC data of them
    left = mainresults_flows(long, year, scenario, countries="DENMARK")
    right = sankey_flows(converted, year, scenario=scenario, countries="DENMARK")
    compared = compare_sankey_flows(left, right)
    made = compared["To"].isin(["Electricity", "District Heat", "Hydrogen"])
    conversion = compared[(compared["Kind"] == "flow") & made & ~compared["From"].isin(not_conversion)]
    assert not conversion.empty
    scale = conversion[["MainResults", "IAMC"]].abs().max(axis=1)
    assert conversion["IAMC"].to_numpy() == pytest.approx(conversion["MainResults"].to_numpy(), rel=1e-6, abs=1e-6), (
        conversion[conversion["Difference"].abs() > 1e-6 * scale.clip(lower=1)])


def test_mainresults_methods(results: MainResults, long: pd.DataFrame, converted: tuple[pd.DataFrame, pd.DataFrame]):
    flows = results.sankey_flows(2050, scenario="Example1", countries="DENMARK", unit="PJ")
    expected = mainresults_flows(long, 2050, "Example1", countries="DENMARK")
    assert flows["Value"].to_numpy() == pytest.approx(expected["Value"].to_numpy() * 3.6)

    compared = results.sankey_flows(2050, scenario=0, countries="DENMARK", iamc=converted)
    assert list(compared.columns) == ["From", "To", "Kind", "MainResults", "IAMC", "Difference"]

    fig, ax = results.plot_sankey(2050, scenario="Example1", countries="DENMARK")
    assert isinstance(fig, Figure)
    assert "Example1" in ax.get_title() and "DENMARK" in ax.get_title()
    plt.close(fig)

    fig, axes = results.plot_sankey(2050, scenario="Example1", countries="DENMARK", iamc=converted, unit="PJ",
                                    filter="Kind != 'loss'")
    assert isinstance(axes, np.ndarray) and len(axes) == 2
    plt.close(fig)

    with pytest.raises(Exception, match="only be compared for countries"):
        results.sankey_flows(2050, scenario="Example1", regions="DK1", iamc=converted)

"""
Created on 26.11.2026

@author: Claude, Anthropic
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)

GAMS-free tests of the Sankey flow tables and drawing, from a hand-made long table (as
read_mainresults makes it) and hand-made IAMC data.
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from pybalmorel.plotting import sankey_flows, compare_sankey_flows, plot_sankey
from pybalmorel.plotting.sankey import mainresults_flows, finish_flows

long_columns = ["scenario", "year", "country", "balmorel_region", "area", "unit_name", "tech_type", "fuel",
                "commodity", "demand_category", "to_country", "to_balmorel_region", "to_area", "quantity",
                "value_unit", "value"]
district_heating = "DK1_Large"
individual = "DK1_IDVU-HOTWTR"
twh_to_ej = 3.6e-3


#%% ------------------------------- ###
###          1. Fixtures            ###
### ------------------------------- ###

@pytest.fixture
def long() -> pd.DataFrame:
    """A long table of one scenario and year in Denmark, in TWh.

    A biomass CHP (10 in, 3 electricity and 5 heat out) and a heat pump (1 electricity in, 3 heat
    out) in a district heating area, onshore wind (6), and a gas boiler in an individual area
    (2.5 in, 2 out). Electricity demand 7 plus 0.5 distribution losses, district heat demand 8,
    individual heat demand 2, and 0.5 electricity sent to Germany.
    """
    def unit(name: str, tech: str, fuel: str, area: str, quantity: str, commodity: str, value: float) -> list:
        return ["S1", 2050, "DENMARK", "DK1", area, name, tech, fuel, commodity, "", "", "", "", quantity, "TWh",
                value]

    def demand(commodity: str, category: str, area: str, value: float) -> list:
        return ["S1", 2050, "DENMARK", "DK1", area, "", "", "", commodity, category, "", "", "", "demand", "TWh",
                value]

    rows = [
        unit("CHP", "CHP-BACK-PRESSURE", "WOODCHIPS", district_heating, "input", "", 10.0),
        unit("CHP", "CHP-BACK-PRESSURE", "WOODCHIPS", district_heating, "output", "ELECTRICITY", 3.0),
        unit("CHP", "CHP-BACK-PRESSURE", "WOODCHIPS", district_heating, "output", "HEAT", 5.0),
        unit("HP", "HEATPUMP", "ELECTRIC", district_heating, "input", "", 1.0),
        unit("HP", "HEATPUMP", "ELECTRIC", district_heating, "output", "HEAT", 3.0),
        unit("WIND", "WIND-ON", "WIND", district_heating, "input", "", 6.0),
        unit("WIND", "WIND-ON", "WIND", district_heating, "output", "ELECTRICITY", 6.0),
        unit("BOILER", "BOILERS", "NATGAS", individual, "input", "", 2.5),
        unit("BOILER", "BOILERS", "NATGAS", individual, "output", "HEAT", 2.0),
        demand("ELECTRICITY", "EXOGENOUS", "", 7.0),
        demand("ELECTRICITY", "DIST_LOSSES", "", 0.5),
        demand("HEAT", "EXOGENOUS", district_heating, 8.0),
        demand("HEAT", "EXOGENOUS", individual, 2.0),
        ["S1", 2050, "DENMARK", "DK1", "", "", "", "", "ELECTRICITY", "", "GERMANY", "DE4-N", "", "exchange",
         "TWh", 0.5],
    ]
    return pd.DataFrame(rows, columns=long_columns)


@pytest.fixture
def iamc() -> pd.DataFrame:
    """IAMC data of one Scenario and year in Denmark, wide, in EJ/yr, that balances."""
    values = {
        "Secondary Energy|Electricity|Biomass|w/o CCS": 3.0,
        "Secondary Energy|Electricity|Wind|Onshore": 6.0,
        "Secondary Energy|Heat|Biomass|w/o CCS": 5.0,
        "Secondary Energy|Heat|Electricity": 3.0,
        "Primary Energy|Biomass|Electricity": 3.75,
        "Primary Energy|Biomass|Heat": 6.25,
        "Final Energy|Electricity": 5.5,
        "Final Energy|Heat": 8.0,
        "Final Energy|Gases|Gas": 2.5,
        "Final Energy|Residential and Commercial|Gases|Gas": 2.5,
        "Trade|Secondary Energy|Electricity [Volume]": 0.5,
    }
    rows = [["Balmorel", "S1", "Denmark", variable, "EJ/yr", value * twh_to_ej] for variable, value in values.items()]
    rows.append(["Balmorel", "S1", "Denmark", "Capacity|Electricity", "GW", 100.0])
    return pd.DataFrame(rows, columns=["Model", "Scenario", "Region", "Variable", "Unit", 2050])


def as_dict(flows: pd.DataFrame, column: str = "Value") -> dict[tuple[str, str, str], float]:
    """A flow table as {(From, To, Kind): value}."""
    return {(start, end, kind): value for start, end, kind, value
            in flows[["From", "To", "Kind", column]].itertuples(index=False)}


#%% ------------------------------- ###
###        2. MainResults Flows     ###
### ------------------------------- ###

def test_mainresults_flows(long: pd.DataFrame):
    flows = as_dict(mainresults_flows(long, 2050, "S1", countries="DENMARK"))
    expected = {
        ("Biomass", "Electricity", "flow"): 3.0,
        ("Biomass", "Electricity", "loss"): 0.75,
        ("Biomass", "Heat", "flow"): 5.0,
        ("Biomass", "Heat", "loss"): 1.25,
        ("Electricity", "Losses", "loss"): 0.75 + 0.5,
        ("Heat", "Losses", "loss"): 1.25,
        ("Electricity", "Heat", "flow"): 1.0,
        ("Ambient Heat", "Heat", "ambient"): 2.0,
        ("Wind", "Electricity", "flow"): 6.0,
        ("Gas", "On-site Heat", "flow"): 2.0,
        ("Gas", "On-site Heat", "loss"): 0.5,
        ("On-site Heat", "Losses", "loss"): 0.5,
        ("On-site Heat", "Residential and Commercial", "flow"): 2.0,
        ("Electricity", "Final Energy", "flow"): 7.0,
        ("Heat", "Final Energy", "flow"): 8.0,
        ("Electricity", "Exports", "flow"): 0.5,
    }
    assert flows.keys() == expected.keys()
    for link, value in expected.items():
        assert flows[link] == pytest.approx(value), link


def test_unaccounted_without_selection(long: pd.DataFrame):
    # Without a selection there is no outside to export to, so the exchange is unaccounted for
    flows = as_dict(mainresults_flows(long, 2050, "S1"))
    assert ("Electricity", "Exports", "flow") not in flows
    assert flows[("Electricity", "Unaccounted", "unaccounted")] == pytest.approx(0.5)


def test_regions_and_areas(long: pd.DataFrame):
    by_country = mainresults_flows(long, 2050, "S1", countries="DENMARK")
    by_region = mainresults_flows(long, 2050, "S1", regions=["DK1"])
    pd.testing.assert_frame_equal(by_country, by_region)

    # Electricity demand is per region, so an area's electricity goes to the Grid
    flows = as_dict(mainresults_flows(long, 2050, "S1", areas=district_heating))
    assert flows[("Electricity", "Grid", "flow")] == pytest.approx(9.0 - 1.0)
    assert flows[("Heat", "Final Energy", "flow")] == pytest.approx(8.0)
    assert not any(end == "On-site Heat" for _, end, _ in flows)


def test_selection_errors(long: pd.DataFrame):
    with pytest.raises(Exception, match="not country and region"):
        mainresults_flows(long, 2050, "S1", countries="DENMARK", regions="DK1")
    with pytest.raises(Exception, match="no country"):
        mainresults_flows(long, 2050, "S1", countries="NORWAY")
    with pytest.raises(Exception, match="no results for 2030"):
        mainresults_flows(long, 2030, "S1")


def test_unit_and_filter(long: pd.DataFrame):
    flows = mainresults_flows(long, 2050, "S1", countries="DENMARK")
    in_pj = finish_flows(flows, "PJ", None)
    assert in_pj["Value"].to_numpy() == pytest.approx(flows["Value"].to_numpy() * 3.6)

    made = finish_flows(flows, "TWh", "Kind != 'loss'")
    assert set(made["Kind"]) == {"flow", "ambient"}
    assert len(made) == (flows["Kind"] != "loss").sum()

    with pytest.raises(Exception, match="Unknown energy unit"):
        finish_flows(flows, "kWh", None)
    with pytest.raises(Exception, match="Could not filter"):
        finish_flows(flows, "TWh", "Nonsense > 1")


#%% ------------------------------- ###
###          3. IAMC Flows          ###
### ------------------------------- ###

def test_iamc_flows(iamc: pd.DataFrame):
    flows = as_dict(sankey_flows(iamc, 2050))
    expected = {
        ("Biomass", "Electricity", "flow"): 3.0,
        ("Biomass", "Electricity", "loss"): 0.75,
        ("Biomass", "Heat", "flow"): 5.0,
        ("Biomass", "Heat", "loss"): 1.25,
        ("Electricity", "Losses", "loss"): 0.75,
        ("Heat", "Losses", "loss"): 1.25,
        ("Electricity", "Heat", "flow"): 3.0,
        ("Wind", "Electricity", "flow"): 6.0,
        ("Gas", "Residential and Commercial", "flow"): 2.5,
        ("Electricity", "Final Energy", "flow"): 5.5,
        ("Heat", "Final Energy", "flow"): 8.0,
        ("Electricity", "Exports", "flow"): 0.5,
    }
    assert flows.keys() == expected.keys()
    for link, value in expected.items():
        assert flows[link] == pytest.approx(value), link


def test_iamc_shapes_and_selection(iamc: pd.DataFrame):
    wide = sankey_flows(iamc, 2050)
    long_iamc = iamc.melt(id_vars=["Model", "Scenario", "Region", "Variable", "Unit"], var_name="Year",
                          value_name="Value")
    pd.testing.assert_frame_equal(sankey_flows(long_iamc, 2050), wide)
    pd.testing.assert_frame_equal(sankey_flows((iamc, pd.DataFrame()), 2050), wide)
    pd.testing.assert_frame_equal(sankey_flows(iamc.rename(columns={2050: "2050"}), 2050, scenario="S1"), wide)
    # Balmorel countries are found by their IAMC Region
    pd.testing.assert_frame_equal(sankey_flows(iamc, 2050, countries="DENMARK"), wide)

    with pytest.raises(Exception, match="no IAMC Region"):
        sankey_flows(iamc, 2050, countries="NORWAY")
    with pytest.raises(Exception, match="no IAMC Scenario 'S2'"):
        sankey_flows(iamc, 2050, scenario="S2")
    with pytest.raises(Exception, match="no values for 2030"):
        sankey_flows(iamc, 2030)
    with pytest.raises(Exception, match="several Models"):
        sankey_flows(pd.concat([iamc, iamc.assign(Model="Other")]), 2050)
    with pytest.raises(Exception, match="not regions or areas"):
        sankey_flows(iamc, 2050, regions="DK1")


def test_iamc_unaccounted(iamc: pd.DataFrame):
    # Without trade, the electricity exported is unaccounted for
    flows = as_dict(sankey_flows(iamc[~iamc["Variable"].str.startswith("Trade")], 2050))
    assert flows[("Electricity", "Unaccounted", "unaccounted")] == pytest.approx(0.5)


def test_compare(long: pd.DataFrame, iamc: pd.DataFrame):
    left = mainresults_flows(long, 2050, "S1", countries="DENMARK")
    right = sankey_flows(iamc, 2050)
    compared = compare_sankey_flows(left, right)
    assert list(compared.columns) == ["From", "To", "Kind", "MainResults", "IAMC", "Difference"]
    assert compared["Difference"].to_numpy() == pytest.approx((compared["IAMC"] - compared["MainResults"]).to_numpy())
    both = as_dict(compared, "Difference")
    assert both[("Wind", "Electricity", "flow")] == pytest.approx(0.0)
    assert both[("Ambient Heat", "Heat", "ambient")] == pytest.approx(-2.0)
    assert both[("Gas", "Residential and Commercial", "flow")] == pytest.approx(2.5)


#%% ------------------------------- ###
###            4. Drawing           ###
### ------------------------------- ###

def test_plot_sankey(long: pd.DataFrame, iamc: pd.DataFrame):
    flows = mainresults_flows(long, 2050, "S1", countries="DENMARK")
    fig, ax = plot_sankey(flows, unit="TWh", title="Denmark 2050")
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    plt.close(fig)

    compared = compare_sankey_flows(flows, sankey_flows(iamc, 2050))
    fig, axes = plot_sankey(compared, unit="TWh")
    assert isinstance(axes, np.ndarray) and len(axes) == 2
    plt.close(fig)

    with pytest.raises(Exception, match="no flows to draw"):
        plot_sankey(flows.assign(Value=0.0))

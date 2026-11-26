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
from matplotlib.colors import to_rgba
from matplotlib.patches import Rectangle

from pybalmorel.plotting import sankey_flows, compare_sankey_flows, plot_sankey
from pybalmorel.plotting.sankey import mainresults_flows, finish_flows, panels_of

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


def test_optiflow_flow_drawn_once(long: pd.DataFrame):
    # Rows for a variable and for variables below it match the same flows; each is drawn once
    def flow(start: str, end: str, name: str, value: float) -> dict:
        return {"scenario": "S1", "year": 2050, "country": "DENMARK", "quantity": "flow", "from_process": start,
                "to_process": end, "flow": name, "value_unit": "PJ", "value": value}

    long = pd.concat([long, pd.DataFrame([flow("Liquid_Hydrogen", "Hydrogen_Eff", "HYDROGEN_FLOW", 36.0),
                                          flow("Biogas_Upgrading", "Gas_Grid", "GAS_FLOW", 7.2)])],
                     ignore_index=True)
    mapping = pd.DataFrame([
        ["Liquid_Hydrogen", "Hydrogen_Eff", "", "report", "PJ", "Final Energy|Bunkers|Hydrogen"],
        ["Liquid_Hydrogen", "Hydrogen_Eff", "", "report", "PJ", "Final Energy|Bunkers"],
        ["Liquid_Hydrogen", "Hydrogen_Eff", "", "report", "PJ", "Final Energy|Bunkers|International Shipping"],
        ["Biogas_Upgrading", "Gas_Grid", "", "report", "PJ", "Secondary Energy|Gases|Biomass"],
        ["Biogas_Upgrading", "Gas_Grid", "", "report", "PJ", "Secondary Energy|Gases"],
    ], columns=["from_process", "to_process", "flow", "role", "unit", "variable"]).assign(
        pool="", removal="", emissions="")
    flows = as_dict(mainresults_flows(long, 2050, "S1", countries="DENMARK", rules={"optiflow": mapping}))
    assert flows[("OptiFlow", "Bunkers", "flow")] == pytest.approx(10.0)
    assert flows[("OptiFlow", "Gases", "flow")] == pytest.approx(2.0)
    assert flows[("Gases", "OptiFlow", "flow")] == pytest.approx(2.0)


def test_optiflow_primary_energy(long: pd.DataFrame):
    # Primary Energy rows are what OptiFlow takes from a Source, drawn once though two rows match
    long = pd.concat([long, pd.DataFrame([{
        "scenario": "S1", "year": 2050, "country": "DENMARK", "quantity": "flow", "from_process": "Biomass_Solid",
        "to_process": "BioFT_30", "flow": "BIOMASS_FLOW", "value_unit": "PJ", "value": 18.0}])], ignore_index=True)
    mapping = pd.DataFrame([
        ["Biomass_Solid", "BioFT_30", "", "report", "PJ", "Primary Energy|Biomass|Liquids|w/o CCS"],
        ["Biomass_Solid", "BioFT_30", "", "report", "PJ", "Primary Energy|Biomass|Liquids"],
    ], columns=["from_process", "to_process", "flow", "role", "unit", "variable"]).assign(
        pool="", removal="", emissions="")
    flows = as_dict(mainresults_flows(long, 2050, "S1", countries="DENMARK", rules={"optiflow": mapping}))
    assert flows[("Biomass", "OptiFlow", "flow")] == pytest.approx(5.0)


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


def test_iamc_biomethane(iamc: pd.DataFrame):
    # Biomethane's final energy comes from Gases, which Primary Energy|Biomass|Gases feeds, not again
    # from Biomass; fossil gas still comes from Gas
    extra = {"Primary Energy|Biomass|Gases": 2.0, "Final Energy|Gases|Biomass": 1.5,
             "Final Energy|Industry|Gases|Biomass": 1.5}
    rows = pd.DataFrame([["Balmorel", "S1", "Denmark", variable, "EJ/yr", value * twh_to_ej]
                         for variable, value in extra.items()], columns=iamc.columns)
    flows = as_dict(sankey_flows(pd.concat([iamc, rows]), 2050))
    assert flows[("Biomass", "Gases", "flow")] == pytest.approx(2.0)
    assert flows[("Gases", "Industry", "flow")] == pytest.approx(1.5)
    assert flows[("Gases", "Unaccounted", "unaccounted")] == pytest.approx(0.5)
    assert ("Biomass", "Industry", "flow") not in flows
    assert flows[("Gas", "Residential and Commercial", "flow")] == pytest.approx(2.5)


def test_iamc_primary_energy_by_use(iamc: pd.DataFrame):
    # Primary Energy reported by use makes the use a node, e.g. Liquids for what biofuel plants take
    # in. A carrier's final energy comes from that node only up to what its Source fed into it: LNG's
    # 1 of the 2.5 of fossil gas, the rest straight from Gas
    extra = {"Primary Energy|Biomass|Liquids|w/o CCS": 4.0, "Primary Energy|Biomass|Liquids": 4.0,
             "Final Energy|Bunkers|Liquids|Biomass": 3.0, "Primary Energy|Gas|Gases": 1.0}
    rows = pd.DataFrame([["Balmorel", "S1", "Denmark", variable, "EJ/yr", value * twh_to_ej]
                         for variable, value in extra.items()], columns=iamc.columns)
    flows = as_dict(sankey_flows(pd.concat([iamc, rows]), 2050))
    assert flows[("Biomass", "Liquids", "flow")] == pytest.approx(4.0)
    assert flows[("Liquids", "Bunkers", "flow")] == pytest.approx(3.0)
    assert flows[("Liquids", "Unaccounted", "unaccounted")] == pytest.approx(1.0)
    assert ("Biomass", "Bunkers", "flow") not in flows
    assert flows[("Gas", "Gases", "flow")] == pytest.approx(1.0)
    assert flows[("Gases", "Residential and Commercial", "flow")] == pytest.approx(1.0)
    assert flows[("Gas", "Residential and Commercial", "flow")] == pytest.approx(1.5)


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


def contrast(colour_a: tuple, colour_b: tuple) -> float:
    """WCAG contrast ratio of two RGBA colours."""
    def luminance(colour: tuple) -> float:
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in colour[:3]]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    high, low = sorted([luminance(colour_a), luminance(colour_b)], reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("dark", [False, True])
def test_plot_sankey_style(long: pd.DataFrame, dark: bool):
    flows = mainresults_flows(long, 2050, "S1", countries="DENMARK")
    fig, ax = plot_sankey(flows, unit="TWh", title="Denmark 2050", dark=dark)
    background = fig.get_facecolor()
    assert (sum(background[:3]) < 0.5) == dark
    # Labels are readable in either style
    texts = [ax.title] + [text for text in ax.texts]
    assert all(contrast(to_rgba(text.get_color()), background) >= 4.5 for text in texts)
    # The dark style lightens dark fuel colours so every node stands out. The light style keeps
    # the package's fuel colours, of which Wind, Solar and Heat are pale against white.
    if dark:
        nodes = [patch for patch in ax.patches if isinstance(patch, Rectangle)]
        assert nodes and all(contrast(patch.get_facecolor(), background) >= 3 for patch in nodes)
    plt.close(fig)


def test_panels_share_one_threshold():
    # 0.9 is below 0.1% of panel A's largest node (1050), so neither panel draws it, though it is
    # above 0.1% of panel B's own largest node (150)
    flows = pd.DataFrame({"From": ["Gas", "Wind", "Gas"], "To": ["Heat", "Electricity", "Electricity"],
                          "Kind": "flow", "A": [0.9, 1000.0, 50.0], "B": [0.9, 100.0, 50.0]})
    panels = panels_of(flows, ["A", "B"], 1e-3)
    for panel in panels:
        assert set(zip(panel["From"], panel["To"])) == {("Wind", "Electricity"), ("Gas", "Electricity")}

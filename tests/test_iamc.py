"""
GAMS-free tests of the IAMC conversion: the long table the Reader would give is
built by hand, and converted against a small Definitions Snapshot.

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
from pathlib import Path
import pandas as pd
import pytest

from pybalmorel.iamc import check_rules, convert, load_rules, write_iamc
from pybalmorel.iamc.convert import amounts
from pybalmorel.iamc.rules import definitions_dir

#%% ------------------------------- ###
###            Fixtures             ###
### ------------------------------- ###

capacity_names = [
    "Capacity|Electricity", "Capacity|Electricity|Gas", "Capacity|Electricity|Gas|w/ CCS",
    "Capacity|Electricity|Gas|w/o CCS", "Capacity|Electricity|Wind", "Capacity|Electricity|Wind|Onshore",
    "Capacity|Electricity|Wind|Offshore", "Capacity|Electricity|Other",
    "Capacity|Electricity|Non-Biomass Renewables",
]
generation_names = [
    "Secondary Energy|Electricity", "Secondary Energy|Electricity|Gas",
    "Secondary Energy|Electricity|Gas|w/ CCS", "Secondary Energy|Electricity|Gas|w/o CCS",
    "Secondary Energy|Electricity|Fossil", "Secondary Energy|Electricity|Fossil|w/ CCS",
    "Secondary Energy|Electricity|Fossil|w/o CCS", "Secondary Energy|Electricity|Wind",
    "Secondary Energy|Electricity|Wind|Onshore", "Secondary Energy|Electricity|Wind|Offshore",
    "Secondary Energy|Electricity|Other", "Secondary Energy|Electricity|Non-Biomass Renewables",
]
heat_capacity_names = ["Capacity|Heat", "Capacity|Heat|Gas"]
heat_names = [
    "Secondary Energy|Heat", "Secondary Energy|Heat|Gas", "Secondary Energy|Heat|Biomass",
    "Secondary Energy|Heat|Electricity", "Secondary Energy|Heat|Other", "Final Energy|Heat",
]
hydrogen_capacity_names = ["Capacity|Hydrogen", "Capacity|Hydrogen|Electricity", "Capacity|Hydrogen|Gas",
                           "Capacity|Hydrogen|Gas|w/o CCS"]
hydrogen_names = [
    "Secondary Energy|Hydrogen", "Secondary Energy|Hydrogen|Electricity", "Secondary Energy|Hydrogen|Gas",
    "Secondary Energy|Hydrogen|Gas|w/o CCS", "Secondary Energy|Hydrogen|Fossil", "Final Energy|Hydrogen",
    "Trade|Secondary Energy|Hydrogen [Volume]",
]
carbon_names = [
    "Emissions|CO2|Energy|Supply|Electricity", "Emissions|CO2|Energy|Supply|Heat",
    "Emissions|CO2|Energy|Supply|Heat|Biomass", "Emissions|CO2|Energy|Supply|Heat|Gas",
    "Emissions|CO2|Energy|Supply|Heat|Fossil", "Emissions|CO2|Energy|Supply|Heat|Other",
    "Emissions|CO2|Energy|Supply|Hydrogen", "Emissions|CO2|Other Capture and Removal",
    "Carbon Capture|Energy|Supply|Electricity", "Carbon Capture|Energy|Supply|Electricity|Biomass",
    "Carbon Capture|Energy|Supply|Electricity|Fossil", "Carbon Capture|Energy|Supply|Heat",
    "Carbon Capture|Energy|Supply|Heat|Biomass", "Carbon Capture|Energy|Supply|Hydrogen",
    "Carbon Capture|Energy|Supply|Hydrogen|Fossil", "Carbon Capture|Direct Air Capture",
    "Carbon Removal|Geological Storage", "Carbon Removal|Geological Storage|Biomass",
    "Carbon Removal|Geological Storage|Direct Air Capture",
    "Emissions|CO2|Energy|Demand|Industry", "Emissions|CO2|Energy|Demand|Industry|Biomass",
    "Emissions|CO2|Energy|Demand|Residential and Commercial", "Carbon Capture|Energy|Demand|Industry",
    "Carbon Capture|Energy|Demand|Industry|Biomass", "Carbon Capture|Geological Storage",
    "Carbon Capture|Geological Storage|Biomass", "Carbon Capture|Geological Storage|Fossil",
    "Emissions|CO2|Energy|Demand|Bunkers|International Aviation",
    "Emissions|CO2|Energy|Demand|Bunkers|International Shipping",
]
bunker_names = ["Final Energy|Bunkers|Hydrogen"]
electricity_names = ["Final Energy|Electricity", "Trade|Secondary Energy|Electricity [Volume]"]
twh = 3.6e-3


@pytest.fixture
def definitions(tmp_path: Path) -> Path:
    """A small Definitions Snapshot with Denmark and Germany."""
    capacity = capacity_names + heat_capacity_names + hydrogen_capacity_names
    energy = generation_names + heat_names + hydrogen_names + bunker_names + electricity_names
    pd.DataFrame({
        "variable": capacity + energy + carbon_names,
        "unit": ["GW"] * len(capacity) + ["EJ/yr"] * len(energy) + ["Mt CO2/yr"] * len(carbon_names),
    }).to_csv(tmp_path / "variables.csv", index=False)
    pd.DataFrame({"region": ["Denmark", "Germany"], "iso3": ["DNK", "DEU"]}).to_csv(
        tmp_path / "regions.csv", index=False)
    return tmp_path


def unit_rows(scenario: str, year: int, country: str, unit_name: str, tech_type: str, fuel: str,
              capacity: float | None, output: float | None, commodity: str = "ELECTRICITY",
              area: str | None = None) -> list[dict]:
    """Long-table rows for one unit's capacity (GW) and output (TWh), in area '<country>_A' by default."""
    rows = []
    for quantity, value, value_unit in (("capacity", capacity, "GW"), ("output", output, "TWh")):
        if value is not None:
            rows.append({
                "scenario": scenario, "year": year, "country": country, "area": area or f"{country}_A",
                "unit_name": unit_name, "tech_type": tech_type, "fuel": fuel, "commodity": commodity,
                "quantity": quantity, "value_unit": value_unit, "value": value,
            })
    return rows


def demand_row(year: int, area: str, category: str, value: float, commodity: str = "HEAT",
               country: str = "DENMARK") -> dict:
    """A long-table row of demand (TWh) in scenario S1, of Danish heat by default."""
    return {"scenario": "S1", "year": year, "country": country, "area": area, "unit_name": "", "tech_type": "",
            "fuel": "", "commodity": commodity, "demand_category": category, "quantity": "demand",
            "value_unit": "TWh", "value": value}


def exchange_row(year: int, from_area: str, to_area: str, value: float) -> dict:
    """A long-table row of Danish heat transmission (TWh) in scenario S1."""
    return {"scenario": "S1", "year": year, "country": "DENMARK", "area": from_area, "to_area": to_area,
            "unit_name": "", "tech_type": "", "fuel": "", "commodity": "HEAT", "quantity": "exchange",
            "value_unit": "TWh", "value": value}


@pytest.fixture
def long() -> pd.DataFrame:
    """Danish units in 2030 and 2050, and one unit in a country without an ISO3 code."""
    rows = []
    for year in (2030, 2050):
        rows += unit_rows("S1", year, "DENMARK", "GNR_CC_NGAS", "CONDENSING", "NATGAS", 2, 10)
        rows += unit_rows("S1", year, "DENMARK", "GNR_CC_NGASCCS", "CONDENSING", "NATGAS", 1, 5)
        rows += unit_rows("S1", year, "DENMARK", "GNR_WT_ON", "WIND-ON", "WIND", 3, 6)
        rows += unit_rows("S1", year, "DENMARK", "GNR_WT_OFF", "WIND-OFF", "WIND", 4, 12)
        rows += unit_rows("S1", year, "DENMARK", "GNR_ESTO", "INTRASEASONAL-ELECT-STORAGE", "ELECTRIC", 1, 2)
        rows += unit_rows("S1", year, "DENMARK", "GNR_BACKUP_ELECTRICITY", "CONDENSING", "NATGAS", 100, 1)
        rows += unit_rows("S1", year, "DENMARK", "GNR_CC_MYSTERY", "CONDENSING", "MYSTERYFUEL", None, 1)
        rows += unit_rows("S1", year, "DENMARK", "GNR_BO_NGAS", "BOILERS", "NATGAS", 1, 3, commodity="HEAT")
        rows += unit_rows("S1", year, "ATLANTIS", "GNR_WT_ON", "WIND-ON", "WIND", 1, 1)
    # Gas capacity is fully decommissioned in 2050
    gone = [row for row in rows if row["unit_name"] == "GNR_CC_NGAS" and row["year"] == 2050]
    for row in gone:
        row["value"] = 0.0 if row["quantity"] == "output" else 1e-16
    return pd.DataFrame(rows)


@pytest.fixture
def heat_long(long: pd.DataFrame) -> pd.DataFrame:
    """The units of `long`, with heat in a district heating area (DENMARK_A, the gas boiler's),
    two industry areas and an individual one, in 2030:

    - DK_IND-MT-DH makes 8 TWh with wood chips and sends 4 to DK_IND-LT-DH, which has no units
      and sends 3.5 into district heating, getting 0.5 back: 3 net from the wood chips.
    - District heating sends 1 net to DK_IND-HT-DH, and 5 to another district heating area.
    - District heating's storage gives 0.5, which is not output.
    - District heating balances: its 6 TWh go to demand, storage, losses and DK_IND-HT-DH; in
      2050 its gas boiler's 3 TWh go to demand.
    """
    year = 2030
    rows = unit_rows("S1", year, "DENMARK", "GNR_BO_WOOD", "BOILERS", "WOODCHIPS", 2, 8, "HEAT", "DK_IND-MT-DH")
    rows += unit_rows("S1", year, "DENMARK", "GNR_HP", "HEATPUMP", "ELECTRIC", 1, 2, "HEAT", "DK_IDVU-SPACEHEAT")
    rows += unit_rows("S1", year, "DENMARK", "GNR_HSTO", "INTRASEASONAL-HEAT-STORAGE", "HEAT", 1, 0.5, "HEAT")
    rows += [
        demand_row(year, "DENMARK_A", "EXOGENOUS", 4),
        demand_row(year, "DENMARK_A", "ENDO_INTRASTO", 0.1),
        demand_row(year, "DENMARK_A", "ENDO_OPTIFLOW", 0.2),
        demand_row(year, "DENMARK_A", "TRANS_LOSSES", 0.9),
        demand_row(2050, "DENMARK_A", "EXOGENOUS", 3),
        demand_row(year, "DK_IND-MT-DH", "EXOGENOUS", 4),
        exchange_row(year, "DK_IND-MT-DH", "DK_IND-LT-DH", 4),
        exchange_row(year, "DK_IND-LT-DH", "DENMARK_A", 3.5),
        exchange_row(year, "DENMARK_A", "DK_IND-LT-DH", 0.5),
        exchange_row(year, "DENMARK_A", "DK_IND-HT-DH", 1),
        exchange_row(year, "DENMARK_A", "DENMARK_B", 5),
    ]
    return pd.concat((long, pd.DataFrame(rows)), ignore_index=True)


def transmission_row(from_country: str, to_country: str, value: float, commodity: str = "HYDROGEN") -> dict:
    """A long-table row of transmission (TWh) in scenario S1 in 2030, between regions, of
    hydrogen by default."""
    return {"scenario": "S1", "year": 2030, "country": from_country, "area": "", "to_area": "",
            "to_country": to_country, "unit_name": "", "tech_type": "", "fuel": "", "commodity": commodity,
            "quantity": "exchange", "value_unit": "TWh", "value": value}


@pytest.fixture
def hydrogen_long() -> pd.DataFrame:
    """Hydrogen in Denmark and Germany in 2030, which balances in both:

    - Denmark makes 10 TWh with an electrolyser and 4 with a steam reformer, imports 3 with an
      import unit, and its storage gives 1, which is not output. It sends 6 to Germany, gets 1
      back, and sends 2 between its own regions: net exports 6 - 1 - 3 = 2. Its 12 go to
      exogenous demand (9), fuel cells (2), distribution losses and storage.
    - Germany makes 2 TWh with an electrolyser in an industry area and gets 5 net from Denmark.
      Its 7 go to exogenous demand (6), transport (0.5) and transmission losses.

    The electrolysers take in 1.25 TWh of electricity per TWh of hydrogen, so their 2 and 1 GW
    of hydrogen output are 2.5 and 1.25 GW of electricity input.
    """
    rows = unit_rows("S1", 2030, "DENMARK", "GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 2, 10, "HYDROGEN")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_SMR", "STEAMREFORMING", "NATGAS", 1, 4, "HYDROGEN")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_H2STO", "H2-STORAGE", "HYDROGEN", 1, 1, "HYDROGEN")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_H2_IMPORT", "ELECTROLYZER", "IMPORT_H2", 5, 3, "HYDROGEN")
    rows += unit_rows("S1", 2030, "GERMANY", "GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 1, 2, "HYDROGEN",
                      area="DE4-W_IND-HT-NODH")
    rows += [
        transmission_row("DENMARK", "GERMANY", 6),
        transmission_row("GERMANY", "DENMARK", 1),
        transmission_row("DENMARK", "DENMARK", 2),
        demand_row(2030, "", "EXOGENOUS", 9, "HYDROGEN"),
        demand_row(2030, "", "ENDO_FUELCELL", 2, "HYDROGEN"),
        demand_row(2030, "", "DIST_LOSSES", 0.5, "HYDROGEN"),
        demand_row(2030, "", "ENDO_INTERSTO", 0.5, "HYDROGEN"),
        demand_row(2030, "", "EXOGENOUS", 6, "HYDROGEN", "GERMANY"),
        demand_row(2030, "", "ENDO_OTHERTRANS", 0.5, "HYDROGEN", "GERMANY"),
        demand_row(2030, "", "TRANS_LOSSES", 0.5, "HYDROGEN", "GERMANY"),
        input_row("GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 12.5),
        input_row("GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 2.5, country="GERMANY", area="DE4-W_IND-HT-NODH"),
        input_row("GNR_SMR", "STEAMREFORMING", "NATGAS", 4 / 0.7),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def electricity_long() -> pd.DataFrame:
    """Electricity in Denmark and Germany in 2030, which balances in both:

    - Denmark makes 30 TWh, sends 5 to Germany and gets 1 back: net exports 4. Its 26 go to
      exogenous demand (15), electric vehicles (2), heat units (5), an electrolyser (2.5),
      carbon capture (1) and distribution losses (0.5).
    - Of the 5 heat units take in, a heat pump in an individual area takes 3, whose heat isn't
      reported, so they are final; an electric boiler in district heating takes 2, whose heat is.
      The electrolyser, in an industry area, takes 2.5 for 2 TWh of hydrogen, which is reported.
    - Germany makes 6 TWh and gets 4 net from Denmark. Its 10 go to exogenous demand (8) and
      the OptiFlow add-on (2).
    """
    rows = unit_rows("S1", 2030, "DENMARK", "GNR_CC_NGAS", "CONDENSING", "NATGAS", 5, 20)
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_WT_ON", "WIND-ON", "WIND", 4, 10)
    rows += unit_rows("S1", 2030, "GERMANY", "GNR_WT_ON", "WIND-ON", "WIND", 3, 6)
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_HP", "HEATPUMP", "ELECTRIC", 1, 9, "HEAT", "DK_IDVU-SPACEHEAT")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_EB", "ELECT-TO-HEAT", "ELECTRIC", 1, 2, "HEAT")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 0.5, 2, "HYDROGEN",
                      area="DK_IND-HT-NODH")
    rows += [
        input_row("GNR_HP", "HEATPUMP", "ELECTRIC", 3, area="DK_IDVU-SPACEHEAT"),
        input_row("GNR_EB", "ELECT-TO-HEAT", "ELECTRIC", 2),
        input_row("GNR_ELYS", "ELECTROLYZER", "ELECTRIC", 2.5, area="DK_IND-HT-NODH"),
        transmission_row("DENMARK", "GERMANY", 5, "ELECTRICITY"),
        transmission_row("GERMANY", "DENMARK", 1, "ELECTRICITY"),
        demand_row(2030, "DENMARK_A", "EXOGENOUS", 2),
        demand_row(2030, "", "EXOGENOUS", 2, "HYDROGEN"),
    ]
    for category, amount in (("EXOGENOUS", 15), ("ENDO_EV", 2), ("ENDOGENOUS_ELECT2HEAT", 5), ("ENDO_H2", 2.5),
                             ("ENDO_CCS", 1), ("DIST_LOSSES", 0.5)):
        rows.append(demand_row(2030, "", category, amount, "ELECTRICITY"))
    rows.append(demand_row(2030, "", "EXOGENOUS", 8, "ELECTRICITY", "GERMANY"))
    rows.append(demand_row(2030, "", "ENDO_OPTIFLOW", 2, "ELECTRICITY", "GERMANY"))
    return pd.DataFrame(rows)


def carbon_row(unit_name: str, tech_type: str, fuel: str, quantity: str, value: float, year: int = 2030,
               country: str = "DENMARK", stated_unit: str = "", area: str | None = None) -> dict:
    """A long-table row of one unit's emissions or captured CO2 (kt CO2) in scenario S1, in area
    '<country>_A' by default; as from the Reader, it has no commodity."""
    return {"scenario": "S1", "year": year, "country": country, "area": area or f"{country}_A", "unit_name": unit_name,
            "tech_type": tech_type, "fuel": fuel, "commodity": "", "quantity": quantity, "value_unit": "kt CO2",
            "stated_unit": stated_unit, "value": value}


def input_row(unit_name: str, tech_type: str, fuel: str, value: float, year: int = 2030, country: str = "DENMARK",
              area: str | None = None) -> dict:
    """A long-table row of one unit's fuel input (TWh) in scenario S1, in area '<country>_A' by
    default, as from the Reader."""
    return carbon_row(unit_name, tech_type, fuel, "input", value, year, country, area=area) | {"value_unit": "TWh"}


def flow_row(from_process: str, to_process: str, flow: str, value: float) -> dict:
    """A long-table row of one Danish OptiFlow flow in scenario S1 in 2030, as from the Reader."""
    return {"scenario": "S1", "year": 2030, "country": "DENMARK", "area": "", "unit_name": "", "tech_type": "",
            "fuel": "", "commodity": "", "from_process": from_process, "to_process": to_process, "flow": flow,
            "quantity": "flow", "value_unit": "", "value": value}


@pytest.fixture
def carbon_long() -> pd.DataFrame:
    """Danish units in a district heating area in 2030 that emit or capture CO2:

    - A gas unit with CCS makes 5 TWh of electricity, emits 50 kt CO2 and captures 450.
    - A wood chips CHP unit with CCS makes 6 TWh of electricity and 2 of heat, and captures
      200 kt CO2, which the results also give as -200 kt of emissions.
    - A gas boiler makes 3 TWh of heat and emits 60 kt CO2.
    """
    rows = unit_rows("S1", 2030, "DENMARK", "GNR_CC_NGASCCS", "CONDENSING", "NATGAS", 1, 5)
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_ST_WOODCHIPS_CCS", "CHP-EXTRACTION", "WOODCHIPS", 1, 6)
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_ST_WOODCHIPS_CCS", "CHP-EXTRACTION", "WOODCHIPS", None, 2, "HEAT")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_BO_NGAS", "BOILERS", "NATGAS", 1, 3, "HEAT")
    rows += [
        carbon_row("GNR_CC_NGASCCS", "CONDENSING", "NATGAS", "emissions", 50),
        carbon_row("GNR_CC_NGASCCS", "CONDENSING", "NATGAS", "captured", 450),
        carbon_row("GNR_ST_WOODCHIPS_CCS", "CHP-EXTRACTION", "WOODCHIPS", "emissions", -200),
        carbon_row("GNR_ST_WOODCHIPS_CCS", "CHP-EXTRACTION", "WOODCHIPS", "captured", 200),
        carbon_row("GNR_BO_NGAS", "BOILERS", "NATGAS", "emissions", 60),
        demand_row(2030, "DENMARK_A", "EXOGENOUS", 5),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def optiflow_rules() -> pd.DataFrame:
    """An OptiFlow Mapping with two CO2 pools, like 2027_fristed's: 'bio' gets the CO2 Balmorel's
    units capture from biomass, 'gen' the CO2 of direct air capture and biogas upgrading, which
    is reported as Carbon Capture only for direct air capture. It also reports hydrogen for ships."""
    columns = ["from_process", "to_process", "flow", "role", "pool", "unit", "variable", "removal", "emissions"]
    return pd.DataFrame([
        ["CO2_Source_Biogen", "CO2_Comp_Bio", "", "balmorel", "bio", "kt CO2", "", "", ""],
        ["CO2_Grid", "CO2_Seq", "CO2_FLOW_BIO", "store", "bio", "kt CO2", "", "", ""],
        ["CO2_DAC_.*", "CO2_Comp_Gen", "", "capture", "gen", "kt CO2", "Carbon Capture|Direct Air Capture",
         "Carbon Removal|Geological Storage|Direct Air Capture", "Emissions|CO2|Other Capture and Removal"],
        ["Biogas_Upgrading_.*", "CO2_Comp_Gen", "", "capture", "gen", "kt CO2", "", "", ""],
        ["CO2_Grid", "CO2_Seq", "CO2_FLOW", "store", "gen", "kt CO2", "", "", ""],
        ["Liquid_Hydrogen", "Hydrogen_(FC_)?Eff", "HYDROGEN_FLOW", "report", "", "PJ", "Final Energy|Bunkers|Hydrogen",
         "", ""],
    ], columns=columns)


@pytest.fixture
def flows() -> pd.DataFrame:
    """OptiFlow flows in Denmark in 2030: 150 of the 200 kt CO2 Balmorel's units capture from
    biomass are stored (Stored Share 0.75), and 100 of the 200 kt that direct air capture and
    biogas upgrading capture (0.5). Ships' fuel cells and engines take in 10 PJ of hydrogen, and
    the fuel cells pass 5 PJ on, which the Mapping must not count again."""
    return pd.DataFrame([
        flow_row("CO2_Source_Biogen", "CO2_Comp_Bio", "CO2_FLOW_BIO", 200),
        flow_row("CO2_Comp_Bio", "CO2_Grid", "CO2_FLOW_BIO", 200),
        flow_row("CO2_Grid", "CO2_Seq", "CO2_FLOW_BIO", 150),
        flow_row("CO2_DAC_Large", "CO2_Comp_Gen", "CO2_FLOW", 80),
        flow_row("Biogas_Upgrading_1", "CO2_Comp_Gen", "CO2_FLOW", 120),
        flow_row("CO2_Grid", "CO2_Seq", "CO2_FLOW", 100),
        flow_row("Liquid_Hydrogen", "Hydrogen_FC_Eff", "HYDROGEN_FLOW", 6),
        flow_row("Liquid_Hydrogen", "Hydrogen_Eff", "HYDROGEN_FLOW", 4),
        flow_row("Hydrogen_FC_Eff", "Shipping_Fuel_Medium", "HYDROGEN_FLOW", 5),
    ])


def value(data: pd.DataFrame, variable: str, year: int, region: str = "Denmark") -> float:
    """The value of one variable, region and year."""
    rows = data[(data["Variable"] == variable) & (data["Region"] == region)]
    assert len(rows) == 1, f"{variable} in {region}: {len(rows)} rows"
    return rows[year].iloc[0]


def is_empty(data: pd.DataFrame, variable: str, year: int, region: str = "Denmark") -> bool:
    """Whether one variable, region and year is left empty: no row, or no value."""
    rows = data[(data["Variable"] == variable) & (data["Region"] == region)]
    return rows.empty or rows[year].isna().all()


#%% ------------------------------- ###
###              Tests              ###
### ------------------------------- ###

def test_electricity_variables(long: pd.DataFrame, definitions: Path) -> None:
    data, _ = convert(long, "Balmorel", definitions=definitions)

    assert list(data.columns[:5]) == ["Model", "Scenario", "Region", "Variable", "Unit"]
    assert value(data, "Capacity|Electricity", 2030) == pytest.approx(2 + 1 + 3 + 4)
    assert value(data, "Capacity|Electricity|Gas|w/ CCS", 2030) == pytest.approx(1)
    # w/o CCS is dropped where the snapshot has no such child
    assert value(data, "Capacity|Electricity|Wind|Onshore", 2030) == pytest.approx(3)
    assert value(data, "Capacity|Electricity|Non-Biomass Renewables", 2030) == pytest.approx(7)
    # Solver noise is 0
    assert value(data, "Capacity|Electricity|Gas|w/o CCS", 2050) == 0.0

    # Backup output counts as supply, storage and heat don't
    assert value(data, "Secondary Energy|Electricity", 2030) == pytest.approx((10 + 5 + 6 + 12 + 1 + 1) * twh)
    assert value(data, "Secondary Energy|Electricity|Gas|w/o CCS", 2030) == pytest.approx((10 + 1) * twh)
    assert value(data, "Secondary Energy|Electricity|Fossil", 2030) == pytest.approx(16 * twh)
    assert value(data, "Secondary Energy|Electricity|Fossil|w/ CCS", 2030) == pytest.approx(5 * twh)
    assert value(data, "Secondary Energy|Electricity|Other", 2030) == pytest.approx(1 * twh)
    assert set(data["Region"]) == {"Denmark"}


def test_notes(long: pd.DataFrame, definitions: Path) -> None:
    _, notes = convert(long, "Balmorel", definitions=definitions)
    text = " ".join(notes["Note"])

    assert "MYSTERYFUEL" in text and "fuel has no Fuel Category" in text
    assert "ATLANTIS" in text
    backup = notes[notes["Note"].str.startswith("Backup units produced")]
    assert backup["Variable"].tolist() == ["Secondary Energy|Electricity|Gas|w/o CCS"]


def test_heat_variables(heat_long: pd.DataFrame, definitions: Path) -> None:
    data, notes = convert(heat_long, "Balmorel", definitions=definitions)

    # The district heating area's gas boiler, and 3 TWh traced to the wood chips boiler
    assert value(data, "Secondary Energy|Heat", 2030) == pytest.approx((3 + 3) * twh)
    assert value(data, "Secondary Energy|Heat|Gas", 2030) == pytest.approx(3 * twh)
    assert value(data, "Secondary Energy|Heat|Biomass", 2030) == pytest.approx(3 * twh)
    assert value(data, "Secondary Energy|Heat", 2050) == pytest.approx(3 * twh)
    # Exogenous demand and the 1 TWh sent net to an industry area
    assert value(data, "Final Energy|Heat", 2030) == pytest.approx((4 + 1) * twh)
    # Capacity in district heating only, without storage
    assert value(data, "Capacity|Heat", 2030) == pytest.approx(1)
    assert "Secondary Energy|Heat|Electricity" not in set(data["Variable"])

    text = " ".join(notes["Note"])
    assert "Not reported, as the 'stems' rules have no row for it: output of HEAT in industry areas, 2030: 8 TWh" in text
    assert "output of HEAT in individual areas" in text
    assert "Demand of HEAT in category ENDO_OPTIFLOW in district heating areas is not reported" in text
    assert "Heat Exchange: district heating sent 2030: 1 TWh" in text
    assert "received 2030: 3 TWh" in text
    assert "doesn't add up" not in text


def test_notes_name_their_regions(heat_long: pd.DataFrame, definitions: Path) -> None:
    """Heat left out in several regions gets one note per scenario, with the total, that names them."""
    german = unit_rows("S1", 2030, "GERMANY", "GNR_BO_WOOD", "BOILERS", "WOODCHIPS", 1, 2, "HEAT", "DE_IND-MT-DH")
    _, notes = convert(pd.concat((heat_long, pd.DataFrame(german)), ignore_index=True), "Balmorel",
                       definitions=definitions)
    industry = notes[notes["Note"].str.contains("output of HEAT in industry areas", regex=False)]
    assert len(industry) == 1 and industry["Region"].iloc[0] == ""
    assert industry["Note"].iloc[0].endswith("2030: 10 TWh in 2 regions: Denmark, Germany.")


def test_heat_balance_is_checked(heat_long: pd.DataFrame, definitions: Path) -> None:
    """Results that don't list heat transmission leave district heating short of the 3 TWh it got
    and with 1 TWh it sent unused."""
    without_exchange = heat_long[heat_long["quantity"] != "exchange"]
    _, notes = convert(without_exchange, "Balmorel", definitions=definitions)
    off = notes[notes["Note"].str.startswith("HEAT in district heating areas doesn't add up")]
    assert off["Region"].tolist() == ["Denmark"]
    assert "was 2030: -2, 2050: 0 TWh more" in off["Note"].iloc[0]


def test_final_electricity(electricity_long: pd.DataFrame, definitions: Path) -> None:
    data, notes = convert(electricity_long, "Balmorel", definitions=definitions)

    # Exogenous demand, electric vehicles and the heat pump outside district heating
    assert value(data, "Final Energy|Electricity", 2030) == pytest.approx((15 + 2 + 3) * twh)
    assert value(data, "Final Energy|Electricity", 2030, "Germany") == pytest.approx(8 * twh)
    assert value(data, "Trade|Secondary Energy|Electricity [Volume]", 2030) == pytest.approx(4 * twh)
    assert value(data, "Trade|Secondary Energy|Electricity [Volume]", 2030, "Germany") == pytest.approx(-4 * twh)
    # Fuel input is not reported as such
    assert value(data, "Secondary Energy|Heat", 2030) == pytest.approx(2 * twh)
    assert value(data, "Secondary Energy|Hydrogen", 2030) == pytest.approx(2 * twh)

    text = " ".join(notes["Note"])
    assert ("Of ELECTRICITY demand in category ENDOGENOUS_ELECT2HEAT, what units in individual areas take in as "
            "Electricity fuels counts as final demand (ON_SITE), as what they make there isn't reported: 2030: 3 TWh. "
            "The rest, 2030: 2 TWh, does not. Units: HEATPUMP.") in text
    assert "doesn't add up" not in text
    assert "more than ELECTRICITY demand" not in text
    assert "Demand of ELECTRICITY" not in text


def test_on_site_use_beyond_its_category(electricity_long: pd.DataFrame, definitions: Path) -> None:
    """Heat units outside district heating that take in more than the category gives count in full."""
    is_heat_units = electricity_long["demand_category"] == "ENDOGENOUS_ELECT2HEAT"
    long = electricity_long.assign(value=electricity_long["value"].where(~is_heat_units, 1.0))
    data, notes = convert(long, "Balmorel", definitions=definitions)

    assert value(data, "Final Energy|Electricity", 2030) == pytest.approx((15 + 2 + 3) * twh)
    text = " ".join(notes["Note"])
    assert ("In Denmark, units in areas whose output isn't reported took in 2030: 3 TWh of Electricity fuels, more "
            "than ELECTRICITY demand in category ENDOGENOUS_ELECT2HEAT there (2030: 1 TWh).") in text


def test_negative_demand_category_is_hinted(electricity_long: pd.DataFrame, definitions: Path) -> None:
    """OptiFlow's use given with the wrong sign leaves Germany 4 TWh short, twice its size."""
    is_optiflow = electricity_long["demand_category"] == "ENDO_OPTIFLOW"
    long = electricity_long.assign(value=electricity_long["value"].where(~is_optiflow, -2.0))
    data, notes = convert(long, "Balmorel", definitions=definitions)

    assert value(data, "Final Energy|Electricity", 2030, "Germany") == pytest.approx(8 * twh)
    off = notes[notes["Note"].str.startswith("ELECTRICITY doesn't add up")]
    assert off["Region"].tolist() == ["Germany"]
    assert "was 2030: 4 TWh more" in off["Note"].iloc[0]
    assert ("Its demand is negative there in categories ENDO_OPTIFLOW 2030: -2 TWh: if that is use given with the "
            "wrong sign, it accounts for a gap of twice its size.") in off["Note"].iloc[0]


def test_hydrogen_variables(hydrogen_long: pd.DataFrame, definitions: Path) -> None:
    data, notes = convert(hydrogen_long, "Balmorel", definitions=definitions)

    # Without storage and the import unit; electrolysers by electricity input
    assert value(data, "Capacity|Hydrogen", 2030) == pytest.approx(2.5 + 1)
    assert value(data, "Capacity|Hydrogen|Electricity", 2030) == pytest.approx(2.5)
    assert value(data, "Capacity|Hydrogen|Gas|w/o CCS", 2030) == pytest.approx(1)
    assert value(data, "Secondary Energy|Hydrogen", 2030) == pytest.approx((10 + 4) * twh)
    assert value(data, "Secondary Energy|Hydrogen|Electricity", 2030) == pytest.approx(10 * twh)
    assert value(data, "Secondary Energy|Hydrogen|Fossil", 2030) == pytest.approx(4 * twh)
    # Hydrogen units count in every kind of area, here an industry area
    assert value(data, "Capacity|Hydrogen", 2030, "Germany") == pytest.approx(1.25)
    assert value(data, "Secondary Energy|Hydrogen", 2030, "Germany") == pytest.approx(2 * twh)
    # Fuel cells, losses and storage are not final
    assert value(data, "Final Energy|Hydrogen", 2030) == pytest.approx(9 * twh)
    assert value(data, "Final Energy|Hydrogen", 2030, "Germany") == pytest.approx(6.5 * twh)
    # Net exports: transmission between countries, less imports from outside the model
    assert value(data, "Trade|Secondary Energy|Hydrogen [Volume]", 2030) == pytest.approx((6 - 1 - 3) * twh)
    assert value(data, "Trade|Secondary Energy|Hydrogen [Volume]", 2030, "Germany") == pytest.approx(-5 * twh)

    text = " ".join(notes["Note"])
    assert "Import units (ELECTROLYZER/IMPORT_H2) brought 2030: 3 TWh of HYDROGEN" in text
    assert "doesn't add up" not in text
    assert "have no row for it" not in text


@pytest.mark.parametrize("case", ["with input", "without input"])
def test_electrolyser_capacity_is_electricity_input(hydrogen_long: pd.DataFrame, definitions: Path,
                                                    case: str) -> None:
    """Electrolysers' capacity is their hydrogen output capacity times their electricity input per
    hydrogen output, over the years they run in. A Danish electrolyser that also delivers heat
    takes in 6 TWh for 4 of hydrogen (1.5), all of which counts: its 0.8 GW are 1.2 GW in 2030,
    and in 2050, when it stands idle. One that never runs can't be restated, nor can any without
    fuel input in the results."""
    rows = unit_rows("S1", 2030, "DENMARK", "GNR_ELYS_DH", "ELECTROLYZER", "ELECTRIC", 0.8, 4, "HYDROGEN")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_ELYS_DH", "ELECTROLYZER", "ELECTRIC", None, 1, "HEAT")
    rows += unit_rows("S1", 2050, "DENMARK", "GNR_ELYS_DH", "ELECTROLYZER", "ELECTRIC", 0.8, 0, "HYDROGEN")
    rows += unit_rows("S1", 2030, "DENMARK", "GNR_ELYS_NEW", "ELECTROLYZER", "ELECTRIC", 0.5, None, "HYDROGEN")
    rows.append(input_row("GNR_ELYS_DH", "ELECTROLYZER", "ELECTRIC", 6))
    long = pd.concat((hydrogen_long, pd.DataFrame(rows)), ignore_index=True)
    if case == "without input":
        long = long[long["quantity"] != "input"]
    data, notes = convert(long, "Balmorel", definitions=definitions)

    text = " ".join(notes["Note"])
    if case == "with input":
        assert value(data, "Capacity|Hydrogen|Electricity", 2030) == pytest.approx(2.5 + 1.2)
        assert value(data, "Capacity|Hydrogen|Electricity", 2050) == pytest.approx(1.2)
        assert "electricity input per hydrogen output in the results (1.25 to 1.5)" in text
        assert "2030: 4.95, 2050: 1.2 GW of electricity input, from 2030: 3.8, 2050: 0.8 GW" in text
        assert "not reported: 2030: 0.5 GW of hydrogen output. Units: GNR_ELYS_NEW." in text
    else:
        assert is_empty(data, "Capacity|Hydrogen|Electricity", 2030)
        assert value(data, "Capacity|Hydrogen", 2030) == pytest.approx(1)
        assert "not reported: 2030: 4.3, 2050: 0.8 GW of hydrogen output." in text
    # Steam reforming stays on the output side
    assert value(data, "Capacity|Hydrogen|Gas|w/o CCS", 2030) == pytest.approx(1)


def test_hydrogen_balance_is_checked(hydrogen_long: pd.DataFrame, definitions: Path) -> None:
    """Results that don't list hydrogen transmission leave Denmark with 5 TWh more than it uses,
    and Germany 5 short; transmission to a region of unknown country is noted."""
    without_transmission = hydrogen_long[hydrogen_long["quantity"] != "exchange"]
    lost = pd.DataFrame([transmission_row("DENMARK", "", 0.5)])
    _, notes = convert(pd.concat((without_transmission, lost)), "Balmorel", definitions=definitions)

    off = notes[notes["Note"].str.startswith("HYDROGEN doesn't add up")]
    assert off["Region"].tolist() == ["Denmark", "Germany"]
    assert "was 2030: 5 TWh more" in off["Note"].iloc[0]
    assert "was 2030: -5 TWh more" in off["Note"].iloc[1]
    assert notes["Note"].str.contains("whose country the results don't give is not counted as Trade: 2030: 0.5").any()


def test_hydrogen_without_demand(hydrogen_long: pd.DataFrame, definitions: Path) -> None:
    """Results without hydrogen demand get one note, not one per region."""
    data, notes = convert(hydrogen_long[hydrogen_long["quantity"] != "demand"], "Balmorel", definitions=definitions)

    assert "Final Energy|Hydrogen" not in set(data["Variable"])
    assert not notes["Note"].str.contains("HYDROGEN doesn't add up").any()
    missing = notes[notes["Note"].str.startswith("The results give no demand of HYDROGEN")]
    assert len(missing) == 1 and "made 2030: 16 TWh" in missing["Note"].iloc[0]


def test_note_amounts_drop_rounding_errors() -> None:
    assert amounts(pd.Series({2030: -2.297e-17, 2050: 2.273})) == "2030: 0, 2050: 2.273"
    assert amounts(pd.Series({2030: 0.0, 2050: -0.0})) == "2030: 0, 2050: 0"


def test_heat_exchange_without_units(long: pd.DataFrame, definitions: Path) -> None:
    """Heat an industry area sends without making it goes to Other, as does heat that went
    out of district heating and back in."""
    rows = unit_rows("S1", 2030, "DENMARK", "GNR_BO_WOOD", "BOILERS", "WOODCHIPS", 1, 1, "HEAT", "DK_IND-MT-DH")
    rows += [
        exchange_row(2030, "DK_IND-HT-DH", "DENMARK_A", 2),
        exchange_row(2030, "DENMARK_A", "DK_IND-MT-DH", 1),
        exchange_row(2030, "DK_IND-MT-DH", "DK_IND-LT-DH", 2),
        exchange_row(2030, "DK_IND-LT-DH", "DENMARK_A", 2),
    ]
    data, notes = convert(pd.concat((long, pd.DataFrame(rows))), "Balmorel", definitions=definitions)

    assert value(data, "Secondary Energy|Heat", 2030) == pytest.approx((3 + 2 + 2) * twh)
    # Half of what DK_IND-LT-DH sends is the wood chips', half came from district heating
    assert value(data, "Secondary Energy|Heat|Biomass", 2030) == pytest.approx(1 * twh)
    assert value(data, "Secondary Energy|Heat|Other", 2030) == pytest.approx((2 + 1) * twh)
    assert value(data, "Final Energy|Heat", 2030) == pytest.approx(1 * twh)
    text = " ".join(notes["Note"])
    assert "no unit could be traced to" in text and "came from district heating" in text


def test_backup_units_excluded(long: pd.DataFrame, definitions: Path) -> None:
    data, notes = convert(long, "Balmorel", definitions=definitions, backup_units="exclude")
    assert value(data, "Secondary Energy|Electricity|Gas|w/o CCS", 2030) == pytest.approx(10 * 3.6e-3)
    assert notes["Note"].str.contains("left out").any()


def test_caller_rules_take_precedence(long: pd.DataFrame, definitions: Path) -> None:
    rules = {
        "fuels": pd.DataFrame({"fuel": ["MYSTERYFUEL"], "category": ["Gas"]}),
        "mapping": pd.DataFrame({
            "tech_type": ["WIND-OFF"], "fuel": [""], "commodity": [""], "unit_pattern": [""], "segments": ["-"],
        }),
    }
    data, notes = convert(long, "Balmorel", definitions=definitions, rules=rules)
    assert value(data, "Capacity|Electricity|Wind", 2030) == pytest.approx(3)
    assert value(data, "Secondary Energy|Electricity|Gas|w/o CCS", 2030) == pytest.approx(12 * 3.6e-3)
    assert not notes["Note"].str.contains("MYSTERYFUEL").any()


def test_scenarios_with_shared_years_are_refused(long: pd.DataFrame, definitions: Path) -> None:
    other_run = long.assign(scenario="S2")
    with pytest.raises(Exception, match="must not share years"):
        convert(pd.concat((long, other_run)), "Balmorel", scenarios={"S1": "LTS", "S2": "LTS"},
                definitions=definitions)

    later_run = other_run.assign(year=other_run["year"] + 5)
    data, _ = convert(pd.concat((long, later_run)), "Balmorel", scenarios={"S1": "LTS", "S2": "LTS"},
                      definitions=definitions)
    assert set(data["Scenario"]) == {"LTS"}
    assert [column for column in data.columns if isinstance(column, int)] == [2030, 2035, 2050, 2055]


def test_template_limits_variables(long: pd.DataFrame, definitions: Path, tmp_path: Path) -> None:
    template = tmp_path / "template.xlsx"
    with pd.ExcelWriter(template) as writer:
        pd.DataFrame({"variable": ["Capacity|Electricity", "Capacity|Electricity|Wind"]}).to_excel(
            writer, sheet_name="Extended List", index=False)
        pd.DataFrame({"region": ["Germany"]}).to_excel(writer, sheet_name="Region", index=False)

    data, notes = convert(long, "Balmorel", template=template, definitions=definitions)
    assert set(data["Variable"]) == {"Capacity|Electricity", "Capacity|Electricity|Wind"}
    assert notes["Note"].str.contains("Region sheet").any()


def test_write_iamc(long: pd.DataFrame, definitions: Path, tmp_path: Path) -> None:
    data, notes = convert(long, "Balmorel", definitions=definitions)
    write_iamc(data, notes, tmp_path / "iamc.xlsx")
    sheets = pd.read_excel(tmp_path / "iamc.xlsx", sheet_name=None)
    assert set(sheets) == {"data", "notes"}
    assert len(sheets["data"]) == len(data)


def test_area_kinds_follow_caller_rules(heat_long: pd.DataFrame, definitions: Path) -> None:
    """Calling the industry areas district heating reports their heat, and leaves no Heat Exchange to split."""
    rules = {"areas": pd.DataFrame({"pattern": ["(^|_)IND-"], "area_kind": ["district heating"]})}
    data, _ = convert(heat_long, "Balmorel", definitions=definitions, rules=rules)
    assert value(data, "Secondary Energy|Heat|Biomass", 2030) == pytest.approx(8 * twh)
    assert value(data, "Final Energy|Heat", 2030) == pytest.approx((4 + 4) * twh)


@pytest.mark.parametrize("change", ["final", "fuel_category"])
def test_unclear_demand_categories_are_refused(change: str) -> None:
    demand_categories = load_rules()["demand_categories"]
    on_site = demand_categories["final"] == "on-site"
    if change == "final":
        demand_categories.loc[on_site, "final"] = "maybe"
        message = "need one of"
    else:
        demand_categories.loc[on_site, "fuel_category"] = "Moonlight"
        message = "need a fuel_category"
    with pytest.raises(Exception, match=message):
        load_rules({"demand_categories": demand_categories[on_site]})


def test_repeated_rule_keys_are_refused() -> None:
    fuels = pd.DataFrame({"fuel": ["NATGAS", "NATGAS"], "category": ["Gas", "Oil"]})
    with pytest.raises(Exception, match="repeat keys"):
        load_rules({"fuels": fuels})


@pytest.mark.skipif(not (definitions_dir / "variables.csv").exists(),
                    reason="No Definitions Snapshot yet: run `pixi run update-iamc-definitions`")
def test_shipped_rules_match_shipped_snapshot() -> None:
    problems = check_rules()
    assert problems.empty, f"Rules target names the Definitions Snapshot lacks:\n{problems.to_string()}"


def test_carbon_not_linked_to_optiflow(carbon_long: pd.DataFrame, definitions: Path) -> None:
    """Without OptiFlow, all captured CO2 counts as stored, as Geological Storage; that from
    biomass also as Carbon Removal, and as negative emissions in place of those the results give.
    The CHP unit's CO2 is split by its output: 3/4 to electricity, 1/4 to heat."""
    data, notes = convert(carbon_long, "Balmorel", definitions=definitions)

    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2030) == pytest.approx((50 - 150) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat", 2030) == pytest.approx((60 - 50) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Gas", 2030) == pytest.approx(60 / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Fossil", 2030) == pytest.approx(60 / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Biomass", 2030) == pytest.approx(-50 / 1e3)
    # Gas has no child of Carbon Capture: it counts towards the stem and Fossil
    assert value(data, "Carbon Capture|Energy|Supply|Electricity", 2030) == pytest.approx((450 + 150) / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Electricity|Fossil", 2030) == pytest.approx(450 / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Electricity|Biomass", 2030) == pytest.approx(150 / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Heat|Biomass", 2030) == pytest.approx(50 / 1e3)
    assert value(data, "Carbon Removal|Geological Storage", 2030) == pytest.approx(200 / 1e3)
    assert value(data, "Carbon Removal|Geological Storage|Biomass", 2030) == pytest.approx(200 / 1e3)
    # Gas has no child of Geological Storage either
    assert value(data, "Carbon Capture|Geological Storage", 2030) == pytest.approx((450 + 200) / 1e3)
    assert value(data, "Carbon Capture|Geological Storage|Fossil", 2030) == pytest.approx(450 / 1e3)
    assert value(data, "Carbon Capture|Geological Storage|Biomass", 2030) == pytest.approx(200 / 1e3)

    text = " ".join(notes["Note"])
    assert "(ELECTRICITY and HEAT)" in text and "(Output-Share Split)" in text
    assert ("Not linked to OptiFlow, so all CO2 that units capture is taken to be stored: 2030: 650 kt CO2, of which "
            "from biomass, so removed: 2030: 200 kt CO2.") in text
    assert "negative emissions of biomass on units that capture CO2, 2030: -200 kt CO2 in Denmark" in text
    assert "don't mark them w/ CCS" not in text and "no captured CO2" not in text


@pytest.mark.parametrize("case", ["consistent", "inconsistent", "given"])
def test_capture_derived_from_fuel_input(long: pd.DataFrame, definitions: Path, case: str) -> None:
    """Where the results give no captured CO2, that of units w/ CCS is their fuel input times what
    units without CCS emit per unit of the same fuel, less their own emissions: 10 TWh of gas at
    201.96 kt CO2/TWh, of which 10% is emitted, makes 1817.64 kt captured, all stored. The factor
    must fit every unit without CCS of that fuel. Captured CO2 the results give is kept."""
    boiler_emissions = 900 if case == "inconsistent" else 3.3 * 201.96
    rows = [
        input_row("GNR_CC_NGAS", "CONDENSING", "NATGAS", 20),
        input_row("GNR_BO_NGAS", "BOILERS", "NATGAS", 3.3),
        input_row("GNR_CC_NGASCCS", "CONDENSING", "NATGAS", 10),
        input_row("GNR_WT_ON", "WIND-ON", "WIND", 7),
        carbon_row("GNR_CC_NGAS", "CONDENSING", "NATGAS", "emissions", 20 * 201.96),
        carbon_row("GNR_BO_NGAS", "BOILERS", "NATGAS", "emissions", boiler_emissions),
        carbon_row("GNR_CC_NGASCCS", "CONDENSING", "NATGAS", "emissions", 201.96),
    ]
    if case == "given":
        rows.append(carbon_row("GNR_CC_NGASCCS", "CONDENSING", "NATGAS", "captured", 1000))
    data, notes = convert(pd.concat((long, pd.DataFrame(rows))), "Balmorel", definitions=definitions)

    text = " ".join(notes["Note"])
    captured = {"consistent": 10 * 201.96 - 201.96, "given": 1000}.get(case)
    if captured is None:
        assert is_empty(data, "Carbon Capture|Energy|Supply|Electricity", 2030)
        assert "can't be derived, and is not reported, for fuels: NATGAS (units without CCS emit 201.96 to 272.73" in text
        assert "The results give no captured CO2: Carbon Capture and Carbon Removal are not reported" in text
    else:
        for variable in ("Carbon Capture|Energy|Supply|Electricity", "Carbon Capture|Energy|Supply|Electricity|Fossil",
                         "Carbon Capture|Geological Storage", "Carbon Capture|Geological Storage|Fossil"):
            assert value(data, variable, 2030) == pytest.approx(captured / 1e3)
        assert ("Emission factors: NATGAS 201.96 kt CO2/TWh. Captured CO2: 2030: 1818 kt CO2." in text) == (
            case == "consistent")
    # Fuel input itself is not reported
    assert "input" not in " ".join(notes.loc[notes["Note"].str.contains("Not reported"), "Note"])


def test_demand_side_carbon(carbon_long: pd.DataFrame, definitions: Path) -> None:
    """Emissions and captured CO2 of heat units in industry and individual areas are reported on
    the demand side, with a note on what they cover; the electricity those units make counts as
    supply."""
    industry, individual = "DK_IND-MT-DH", "DK_IDVU-SPACEHEAT"
    rows = unit_rows("S1", 2030, "DENMARK", "IND_ENG_NGAS", "CHP-BACK-PRESSURE", "NATGAS", 1, 1, area=industry)
    rows += unit_rows("S1", 2030, "DENMARK", "IND_ENG_NGAS", "CHP-BACK-PRESSURE", "NATGAS", None, 3, "HEAT", industry)
    rows += unit_rows("S1", 2030, "DENMARK", "IND_BO_WOODCHIPS_CCS", "BOILERS", "WOODCHIPS", 1, 2, "HEAT", industry)
    rows += unit_rows("S1", 2030, "DENMARK", "IDVU_BO_NGAS", "BOILERS", "NATGAS", 1, 1, "HEAT", individual)
    rows += [
        carbon_row("IND_ENG_NGAS", "CHP-BACK-PRESSURE", "NATGAS", "emissions", 40, area=industry),
        carbon_row("IND_BO_WOODCHIPS_CCS", "BOILERS", "WOODCHIPS", "emissions", -20, area=industry),
        carbon_row("IND_BO_WOODCHIPS_CCS", "BOILERS", "WOODCHIPS", "captured", 20, area=industry),
        carbon_row("IDVU_BO_NGAS", "BOILERS", "NATGAS", "emissions", 15, area=individual),
    ]
    data, notes = convert(pd.concat((carbon_long, pd.DataFrame(rows))), "Balmorel", definitions=definitions)

    # Gas has no child of the industry stem: it counts towards the total only
    assert value(data, "Emissions|CO2|Energy|Demand|Industry", 2030) == pytest.approx((30 - 20) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Demand|Industry|Biomass", 2030) == pytest.approx(-20 / 1e3)
    assert value(data, "Emissions|CO2|Energy|Demand|Residential and Commercial", 2030) == pytest.approx(15 / 1e3)
    assert value(data, "Carbon Capture|Energy|Demand|Industry|Biomass", 2030) == pytest.approx(20 / 1e3)
    assert value(data, "Carbon Removal|Geological Storage|Biomass", 2030) == pytest.approx((200 + 20) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2030) == pytest.approx((50 - 150 + 10) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat", 2030) == pytest.approx((60 - 50) / 1e3)

    covered = set(notes.loc[notes["Note"].str.startswith("Covers only the heat units"), "Variable"])
    assert covered == {"Emissions|CO2|Energy|Demand|Industry", "Emissions|CO2|Energy|Demand|Residential and Commercial",
                       "Carbon Capture|Energy|Demand|Industry"}


def test_carbon_linked_to_optiflow(carbon_long: pd.DataFrame, flows: pd.DataFrame, optiflow_rules: pd.DataFrame,
                                   definitions: Path) -> None:
    """Linked to OptiFlow, the stored part of the CO2 captured from biomass is its pool's Stored
    Share. OptiFlow's direct air capture, and hydrogen for ships, are reported as the OptiFlow
    Mapping says."""
    data, notes = convert(pd.concat((carbon_long, flows)), "Balmorel", definitions=definitions,
                          rules={"optiflow": optiflow_rules})

    stored = 200 * 0.75
    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2030) == pytest.approx((50 - 0.75 * stored) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Biomass", 2030) == pytest.approx(-0.25 * stored / 1e3)
    assert value(data, "Carbon Removal|Geological Storage|Biomass", 2030) == pytest.approx(stored / 1e3)
    assert value(data, "Carbon Removal|Geological Storage|Direct Air Capture", 2030) == pytest.approx(80 * 0.5 / 1e3)
    assert value(data, "Carbon Removal|Geological Storage", 2030) == pytest.approx((stored + 40) / 1e3)
    assert value(data, "Carbon Capture|Direct Air Capture", 2030) == pytest.approx(80 / 1e3)
    assert value(data, "Emissions|CO2|Other Capture and Removal", 2030) == pytest.approx(-40 / 1e3)
    # Captured CO2 is what units capture, stored or not
    assert value(data, "Carbon Capture|Energy|Supply|Electricity|Biomass", 2030) == pytest.approx(150 / 1e3)
    assert value(data, "Final Energy|Bunkers|Hydrogen", 2030) == pytest.approx(10 / 1e3)

    text = " ".join(notes["Note"])
    assert "OptiFlow stores 2030: 0.75 of the CO2 entering pool 'bio'" in text
    assert "OptiFlow stores 2030: 0.5 of the CO2 entering pool 'gen'" in text
    assert "the share stored in OptiFlow is taken: 2030: 0.75." in text
    assert "check those rules" not in text and "Not linked" not in text


@pytest.mark.parametrize("link", ["flows", "carried", "stored"])
def test_carbon_linked_without_optiflow_mapping(carbon_long: pd.DataFrame, flows: pd.DataFrame, definitions: Path,
                                                link: str) -> None:
    """Linked to OptiFlow by its flows, or by OptiFlow's emissions the results carry, but without
    an OptiFlow Mapping, the stored part of the CO2 captured from biomass can't be known: what
    it counts towards is left empty, and the rest is reported. Negative carried emissions, as
    in 2027_madsen, are flagged as likely stored CO2."""
    carried_kt = -500 if link == "stored" else 500
    carried = pd.DataFrame([carbon_row("AROS3_ST_FUELOIL_EXT", "OPTIFLOW", "FUELOIL", "emissions", carried_kt)])
    data, notes = convert(pd.concat((carbon_long, flows if link == "flows" else carried)), "Balmorel",
                          definitions=definitions)

    for variable in ("Emissions|CO2|Energy|Supply|Electricity", "Emissions|CO2|Energy|Supply|Heat",
                     "Emissions|CO2|Energy|Supply|Heat|Biomass", "Carbon Removal|Geological Storage",
                     "Carbon Removal|Geological Storage|Biomass"):
        assert is_empty(data, variable, 2030), variable
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Gas", 2030) == pytest.approx(60 / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Electricity", 2030) == pytest.approx((450 + 150) / 1e3)

    text = " ".join(notes["Note"])
    assert "gives no share stored of the CO2 that units capture from biomass: 2030: 200 kt CO2 in Denmark" in text
    if link == "flows":
        assert "no OptiFlow Mapping ('optiflow' rules) was given" in text
        assert "Final Energy|Bunkers|Hydrogen" not in set(data["Variable"])
    else:
        assert "Not reported as Balmorel's: OptiFlow's emissions that the results carry on units OPTIFLOW/FUELOIL, " \
               f"2030: {carried_kt} kt CO2." in text
        assert "Units whose output the results don't give" not in text
        assert ("likely CO2 that OptiFlow stores" in text) == (link == "stored")


@pytest.fixture
def fuel_rules() -> pd.DataFrame:
    """'fuel' rules for OptiFlow's fossil jet fuel, LNG for ships and diesel for road transport,
    whose CO2 Balmorel's results carry, as in 2026_fristed. Ships capture CO2 on board into
    pool 'occ', and the stored part of it is taken off their emissions; diesel's CO2 is not
    reported. What 'occ' stores is reported as Geological Storage. The jet fuel rule has a note."""
    columns = ["from_process", "to_process", "flow", "role", "pool", "unit", "factor", "variable", "removal",
               "emissions", "note"]
    aviation = "Emissions|CO2|Energy|Demand|Bunkers|International Aviation"
    shipping = "Emissions|CO2|Energy|Demand|Bunkers|International Shipping"
    return pd.DataFrame([
        ["Jet_Source", "Aviation_Fuel", "", "fuel", "", "Mt CO2", "0.0732", "", "", aviation,
         "All aviation counted as international."],
        ["LNG_Source", "OCC", "", "fuel", "", "Mt CO2", "0.057", "", "", shipping, ""],
        ["Diesel_Source", "Road_Fuels", "", "fuel", "", "Mt CO2", "0.0741", "", "", "", ""],
        ["OCC", "CO2_Grid_In", "CO2_FLOW_OCC", "capture", "occ", "Mt CO2", "", "", "", shipping, ""],
        ["CO2_Grid_Out", "CO2_Seq", "CO2_FLOW_OCC_SEQ", "store", "occ", "Mt CO2", "", "", "", "", ""],
        ["CO2_Grid_Out", "CO2_Seq", "CO2_FLOW_OCC_SEQ", "report", "", "Mt CO2", "",
         "Carbon Capture|Geological Storage|Fossil", "", "", ""],
    ], columns=columns)


@pytest.mark.parametrize("carried_kt", [1091.1, 1500])
def test_optiflow_fuel_rules(carbon_long: pd.DataFrame, flows: pd.DataFrame, optiflow_rules: pd.DataFrame,
                             fuel_rules: pd.DataFrame, definitions: Path, carried_kt: float) -> None:
    """'fuel' rules report the CO2 of OptiFlow's fossil fuels, as flow times factor, net of the
    stored part of CO2 captured from them, and are checked against the emissions the results
    carry for OptiFlow: 10 PJ of jet fuel, 5 of LNG and 1 of diesel make 1091.1 kt CO2."""
    fuel_flows = pd.DataFrame([
        flow_row("Jet_Source", "Aviation_Fuel", "JET_FLOW", 10),
        flow_row("LNG_Source", "OCC", "LNG_FLOW", 5),
        flow_row("Diesel_Source", "Road_Fuels", "DIESEL_FLOW", 1),
        flow_row("OCC", "CO2_Grid_In", "CO2_FLOW_OCC", 0.2),
        flow_row("CO2_Grid_Out", "CO2_Seq", "CO2_FLOW_OCC_SEQ", 0.16),
    ])
    carried = pd.DataFrame([carbon_row("AROS3_ST_FUELOIL_EXT", "OPTIFLOW", "FUELOIL", "emissions", carried_kt)])
    data, notes = convert(pd.concat((carbon_long, flows, fuel_flows, carried)), "Balmorel", definitions=definitions,
                          rules={"optiflow": pd.concat((optiflow_rules, fuel_rules))})

    assert value(data, "Emissions|CO2|Energy|Demand|Bunkers|International Aviation", 2030) == pytest.approx(0.732)
    assert value(data, "Emissions|CO2|Energy|Demand|Bunkers|International Shipping", 2030) == pytest.approx(
        0.285 - 0.2 * 0.8)
    assert value(data, "Carbon Capture|Geological Storage|Fossil", 2030) == pytest.approx(0.16)
    # Balmorel's own emissions are reported as without the fuel rules
    assert value(data, "Emissions|CO2|Energy|Supply|Heat|Gas", 2030) == pytest.approx(60 / 1e3)

    text = " ".join(notes["Note"])
    assert ("The 'fuel' rules give OptiFlow's fossil fuels 2030: 1.091 Mt CO2/yr; the results carry "
            f"2030: {carried_kt / 1e3:.4g} Mt CO2/yr for OptiFlow") in text
    assert "Not reported, as their rules give no emissions variable: Diesel_Source -> Road_Fuels, 2030: 0.0741" in text
    assert ("They differ" in text) == (carried_kt == 1500)
    # A rule's note goes to the IAMC Variable it reports under
    noted = notes[notes["Note"] == "All aviation counted as international."]
    assert set(noted["Variable"]) == {"Emissions|CO2|Energy|Demand|Bunkers|International Aviation"}


def test_carbon_notes(long: pd.DataFrame, definitions: Path) -> None:
    """Results without captured CO2 report emissions as they are; emissions of units without
    output can't be split over commodities, unless they are solver residue, and a unit the
    results state wrongly is noted."""
    rows = [
        carbon_row("GNR_CC_NGAS", "CONDENSING", "NATGAS", "emissions", 30, stated_unit="mton"),
        carbon_row("GNR_BACKUP_ELECTRICITY", "CONDENSING", "NATGAS", "emissions", 20),
        carbon_row("GNR_ENG_NOOUTPUT", "ENGINE", "NATGAS", "emissions", 7),
        carbon_row("GNR_BO_NGAS", "BOILERS", "NATGAS", "emissions", 60, year=2050),
        carbon_row("GNR_ENG_NOOUTPUT", "ENGINE", "NATGAS", "emissions", 1e-8, year=2050),
    ]
    data, notes = convert(pd.concat((long, pd.DataFrame(rows))), "Balmorel", definitions=definitions)

    # Backup units' emissions are reported with their output
    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2030) == pytest.approx((30 + 20) / 1e3)
    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2050) == 0.0
    assert "Carbon Removal|Geological Storage" not in set(data["Variable"])

    text = " ".join(notes["Note"])
    assert "The results give no captured CO2" in text
    assert "Units whose output the results don't give had emissions of 2030: 7 kt CO2;" in text
    assert "GNR_ENG_NOOUTPUT" in text
    assert "The results state 'mton' as the unit of emissions; it is taken to be kt CO2" in text
    assert "Backup units' emissions came to 2030: 20 kt CO2 in Denmark; reported." in text

    data, notes = convert(pd.concat((long, pd.DataFrame(rows))), "Balmorel", definitions=definitions,
                          backup_units="exclude")
    assert value(data, "Emissions|CO2|Energy|Supply|Electricity", 2030) == pytest.approx(30 / 1e3)
    assert notes["Note"].str.contains("Backup units' emissions came to 2030: 20 kt CO2 in Denmark; left out.").any()


def test_hydrogen_carbon(hydrogen_long: pd.DataFrame, definitions: Path) -> None:
    """A steam reformer that captures CO2 without 'CCS' in its name is reported w/o CCS, with a
    note; import units' emissions are made outside the model and not reported."""
    rows = [
        carbon_row("GNR_SMR", "STEAMREFORMING", "NATGAS", "emissions", 10),
        carbon_row("GNR_SMR", "STEAMREFORMING", "NATGAS", "captured", 30),
        carbon_row("GNR_H2_IMPORT", "ELECTROLYZER", "IMPORT_H2", "emissions", 5),
    ]
    data, notes = convert(pd.concat((hydrogen_long, pd.DataFrame(rows))), "Balmorel", definitions=definitions)

    assert value(data, "Emissions|CO2|Energy|Supply|Hydrogen", 2030) == pytest.approx(10 / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Hydrogen|Fossil", 2030) == pytest.approx(30 / 1e3)
    assert value(data, "Carbon Capture|Energy|Supply|Hydrogen", 2030) == pytest.approx(30 / 1e3)

    text = " ".join(notes["Note"])
    assert "the Mapping Rules don't mark them w/ CCS" in text and "reported w/o CCS: GNR_SMR." in text
    assert "Not reported: import units' emissions, 2030: 5 kt CO2" in text


def test_invalid_optiflow_rules_are_refused(optiflow_rules: pd.DataFrame) -> None:
    with pytest.raises(Exception, match="need a role"):
        load_rules({"optiflow": optiflow_rules.assign(role="sink")})
    with pytest.raises(Exception, match="need a pool"):
        load_rules({"optiflow": optiflow_rules.assign(pool="")})
    with pytest.raises(Exception, match="no regular expression"):
        load_rules({"optiflow": optiflow_rules.assign(from_process="CO2_(")})
    with pytest.raises(Exception, match="need a number or nothing under factor"):
        load_rules({"optiflow": optiflow_rules.assign(factor="0,0732")})


def test_invalid_fuel_rules_are_refused(fuel_rules: pd.DataFrame, carbon_long: pd.DataFrame, flows: pd.DataFrame,
                                        definitions: Path) -> None:
    with pytest.raises(Exception, match="of role 'fuel' take no variable or removal"):
        load_rules({"optiflow": fuel_rules.assign(variable="Final Energy|Bunkers|Liquids|Oil")})
    with pytest.raises(Exception, match="need a unit of CO2"):
        convert(pd.concat((carbon_long, flows)), "Balmorel", definitions=definitions,
                rules={"optiflow": fuel_rules.assign(unit="PJ")})


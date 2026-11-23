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
    "Secondary Energy|Heat",
]


@pytest.fixture
def definitions(tmp_path: Path) -> Path:
    """A small Definitions Snapshot with Denmark and Germany."""
    pd.DataFrame({
        "variable": capacity_names + generation_names,
        "unit": ["GW"] * len(capacity_names) + ["EJ/yr"] * len(generation_names),
    }).to_csv(tmp_path / "variables.csv", index=False)
    pd.DataFrame({"region": ["Denmark", "Germany"], "iso3": ["DNK", "DEU"]}).to_csv(
        tmp_path / "regions.csv", index=False)
    return tmp_path


def unit_rows(scenario: str, year: int, country: str, unit_name: str, tech_type: str, fuel: str,
              capacity: float | None, output: float | None, commodity: str = "ELECTRICITY") -> list[dict]:
    """Long-table rows for one unit's capacity (GW) and output (TWh)."""
    rows = []
    for quantity, value, value_unit in (("capacity", capacity, "GW"), ("output", output, "TWh")):
        if value is not None:
            rows.append({
                "scenario": scenario, "year": year, "country": country, "area": f"{country}_A",
                "unit_name": unit_name, "tech_type": tech_type, "fuel": fuel, "commodity": commodity,
                "quantity": quantity, "value_unit": value_unit, "value": value,
            })
    return rows


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


def value(data: pd.DataFrame, variable: str, year: int, region: str = "Denmark") -> float:
    """The value of one variable, region and year."""
    rows = data[(data["Variable"] == variable) & (data["Region"] == region)]
    assert len(rows) == 1, f"{variable} in {region}: {len(rows)} rows"
    return rows[year].iloc[0]


#%% ------------------------------- ###
###              Tests              ###
### ------------------------------- ###

def test_electricity_variables(long: pd.DataFrame, definitions: Path) -> None:
    data, _ = convert(long, "Balmorel", definitions=definitions)
    twh = 3.6e-3

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
    assert "Secondary Energy|Heat" not in set(data["Variable"])
    assert set(data["Region"]) == {"Denmark"}


def test_notes(long: pd.DataFrame, definitions: Path) -> None:
    _, notes = convert(long, "Balmorel", definitions=definitions)
    text = " ".join(notes["Note"])

    assert "MYSTERYFUEL" in text and "fuel has no Fuel Category" in text
    assert "ATLANTIS" in text
    assert "Output of HEAT is not reported" in text
    backup = notes[notes["Note"].str.startswith("Backup units produced")]
    assert backup["Variable"].tolist() == ["Secondary Energy|Electricity|Gas|w/o CCS"]


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


def test_repeated_rule_keys_are_refused() -> None:
    fuels = pd.DataFrame({"fuel": ["NATGAS", "NATGAS"], "category": ["Gas", "Oil"]})
    with pytest.raises(Exception, match="repeat keys"):
        load_rules({"fuels": fuels})


@pytest.mark.skipif(not (definitions_dir / "variables.csv").exists(),
                    reason="No Definitions Snapshot yet: run `pixi run update-iamc-definitions`")
def test_shipped_rules_match_shipped_snapshot() -> None:
    problems = check_rules()
    assert problems.empty, f"Rules target names the Definitions Snapshot lacks:\n{problems.to_string()}"

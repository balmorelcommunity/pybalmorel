"""
GAMS-dependent tests of the IAMC conversion on the example MainResults: the
IAMC totals of electricity, heat, hydrogen, CO2 and primary energy equal the raw results, as
do electricity trade per region, centralized heat and hydrogen balances, and the electricity and
carbon prices, and Mapping Rules and Fuel Categories cover every unit. Needs a GAMS installation and the shipped Definitions Snapshot.

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
    """The raw long table of amounts of countries with an IAMC Region, with Area Kinds ('' for
    rows without an area). Leaves out prices and CO2 tax."""
    area_rules = load_rules()["areas"]
    long = raw[raw["country"].isin(region_countries) & ~raw["quantity"].isin(["price", "tax"])]
    return long.assign(area_kind=match_area_kinds(long["area"], area_rules).where(long["area"] != "", ""),
                       to_area_kind=match_area_kinds(long["to_area"], area_rules).where(long["to_area"] != "", ""))


@pytest.fixture(scope="module")
def reported(in_regions: pd.DataFrame) -> pd.DataFrame:
    """The raw electricity rows the conversion should report: units without storage."""
    long = in_regions[in_regions["commodity"] == "ELECTRICITY"]
    return long[match_mapping_rules(long, load_rules()["mapping"]) != not_reported]


@pytest.fixture(scope="module")
def electricity(raw: pd.DataFrame, in_regions: pd.DataFrame) -> dict[str, pd.Series]:
    """Raw electricity in TWh: final demand per scenario, and net exports per scenario and
    IAMC Region. Final demand is that of the 'yes' categories, plus what heat units in
    individual and industry areas, which make nothing else, take in as electricity fuels.
    Net exports are transmission to other countries less transmission from them."""
    rules = load_rules()
    long = in_regions[in_regions["commodity"] == "ELECTRICITY"]
    categories = rules["demand_categories"]
    final = categories.loc[(categories["commodity"] == "ELECTRICITY") & (categories["final"] == "yes"),
                           "demand_category"]
    demand = long[(long["quantity"] == "demand") & long["demand_category"].isin(final)]

    unit_keys = ["scenario", "country", "area", "unit_name", "tech_type", "fuel"]
    output = in_regions[(in_regions["quantity"] == "output") & (in_regions["value"] > 0)]
    makes_other = output.assign(other=output["commodity"] != "HEAT").groupby(unit_keys)["other"].any()
    on_site = makes_other[~makes_other].index
    electric = rules["fuels"].loc[rules["fuels"]["category"] == "Electricity", "fuel"]
    used = in_regions[(in_regions["quantity"] == "input") & in_regions["fuel"].isin(electric)
                      & ~in_regions["area_kind"].isin(["", default_area_kind])]
    used = used[pd.MultiIndex.from_frame(used[unit_keys]).isin(on_site)]
    assert not used.empty

    _, regions = load_definitions()
    region_of = rules["countries"].merge(regions, on="iso3").set_index("country")["region"]
    exchange = raw[(raw["commodity"] == "ELECTRICITY") & (raw["quantity"] == "exchange")]
    abroad = exchange[(exchange["to_country"] != "") & (exchange["to_country"] != exchange["country"])]
    net_exports = pd.concat((
        abroad.assign(region=abroad["country"].map(region_of)),
        abroad.assign(region=abroad["to_country"].map(region_of), value=-abroad["value"]),
    )).dropna(subset="region").groupby(["scenario", "region"])["value"].sum()

    assert set(long.loc[long["quantity"] != "capacity", "value_unit"]) | set(exchange["value_unit"]) <= {"TWh"}

    def per_scenario(rows: pd.DataFrame) -> pd.Series:
        return rows.groupby("scenario")["value"].sum().reindex(scenarios, fill_value=0.0)

    return {"final_demand": per_scenario(demand) + per_scenario(used), "net_exports": net_exports}


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


unit_keys = ["scenario", "year", "country", "area", "unit_name", "tech_type", "fuel"]


def reported_output(in_regions: pd.DataFrame, all_heat: bool = False) -> pd.DataFrame:
    """Units' output, with whether it is reported: electricity, hydrogen and biomethane in any
    kind of area, heat in district heating (in any kind of area with `all_heat`), without
    storage and import units."""
    output = in_regions[(in_regions["quantity"] == "output") & (in_regions["value"] > 0)]
    targets = match_mapping_rules(output, load_rules()["mapping"])
    heat = (output["commodity"] == "HEAT") & (all_heat | (output["area_kind"] == default_area_kind))
    return output.assign(reported=~targets.isin([not_reported, import_unit])
                         & (output["commodity"].isin(["ELECTRICITY", "HYDROGEN", "BIOMETHANE"]) | heat))


def reported_share(in_regions: pd.DataFrame, all_heat: bool = False) -> pd.DataFrame:
    """The share of each unit's output that is reported, per unit and year."""
    output = reported_output(in_regions, all_heat)
    share = (output["value"].where(output["reported"], 0.0).groupby([output[key] for key in unit_keys]).sum()
             / output.groupby(unit_keys)["value"].sum())
    return share.rename("share").reset_index()


@pytest.fixture(scope="module")
def carbon(in_regions: pd.DataFrame) -> dict[str, pd.Series]:
    """Raw emissions and captured CO2 per scenario (Mt CO2), of the part of each unit's output
    that is reported (reported_output)."""
    rows = in_regions[in_regions["quantity"].isin(["emissions", "captured"])]
    assert set(rows["value_unit"]) <= {"kt CO2"}
    rows = rows.merge(reported_share(in_regions), on=unit_keys, how="left").fillna({"share": 0.0})
    by_quantity = (rows["value"] * rows["share"] / 1e3).groupby([rows["quantity"], rows["scenario"]]).sum()
    return {quantity: by_quantity.get(quantity, pd.Series(dtype=float)).reindex(scenarios, fill_value=0.0)
            for quantity in ("emissions", "captured")}


@pytest.fixture(scope="module")
def primary(in_regions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Raw primary energy per Fuel Category (rows) and scenario (columns), in TWh, of the part of
    each unit's output that is reported (reported_output), with heat in any kind of area:

    - 'input': the fuel input of units whose fuel the 'fuels' rules count by input,
    - 'input_by_use': the same with heat in district heating only, which has variables by use,
    - 'output': the output of units whose fuel they count by output (direct equivalent).

    Geothermal units, whose fuel is waste heat, are left out."""
    fuels = load_rules()["fuels"]
    by_input = fuels.loc[fuels["primary"].isin(["", "input"]), ["fuel", "category"]]
    inputs = in_regions[in_regions["quantity"] == "input"].merge(by_input, on="fuel")
    assert set(inputs["value_unit"]) <= {"TWh"}

    def per_category(rows: pd.DataFrame, values: pd.Series) -> pd.DataFrame:
        return values.groupby([rows["category"], rows["scenario"]]).sum().unstack("scenario").reindex(
            columns=scenarios, fill_value=0.0).fillna(0.0)

    def counted(all_heat: bool) -> pd.DataFrame:
        rows = inputs.merge(reported_share(in_regions, all_heat), on=unit_keys, how="left").fillna({"share": 0.0})
        return per_category(rows, rows["value"] * rows["share"])

    output = reported_output(in_regions, all_heat=True)
    output = output[output["reported"]].merge(fuels[fuels["primary"] == "output"], on="fuel")
    return {"input": counted(True), "input_by_use": counted(False), "output": per_category(output, output["value"])}


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


def test_final_electricity_equals_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                              electricity: dict[str, pd.Series]) -> None:
    """Final electricity is the final categories' demand plus what heat units outside district
    heating use, which the Conversion Notes say."""
    data, notes = converted
    pd.testing.assert_series_equal(total(data, "Final Energy|Electricity"),
                                   electricity["final_demand"] * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9)
    on_site = notes.loc[notes["Note"].str.startswith("Of ELECTRICITY demand in category ENDOGENOUS_ELECT2HEAT"),
                        "Scenario"]
    assert "Example3" in set(on_site)


def test_electricity_trade_equals_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                              electricity: dict[str, pd.Series]) -> None:
    """Net exports per region; they cancel out over all regions, so totals can't show them."""
    data, _ = converted
    years = [column for column in data.columns if isinstance(column, int)]
    rows = data[data["Variable"] == "Trade|Secondary Energy|Electricity [Volume]"]
    reported_trade = rows.groupby(["Scenario", "Region"])[years].sum().sum(axis=1)
    expected = electricity["net_exports"] * twh_to_ej
    assert (expected.abs() > 1e-6).any()
    pd.testing.assert_series_equal(reported_trade.reindex(expected.index, fill_value=0.0), expected,
                                   check_names=False, check_index_type=False, rtol=1e-9, atol=1e-12)
    assert set(reported_trade.index) <= set(expected.index)


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
    removed, but it is all stored; Example1 and Example2 have no captured CO2, which the
    Conversion Notes say."""
    data, notes = converted
    supplies = ["Electricity", "Heat", "Hydrogen"]
    emissions = sum(total(data, f"Emissions|CO2|Energy|Supply|{supply}") for supply in supplies)
    captured = sum(total(data, f"Carbon Capture|Energy|Supply|{supply}") for supply in supplies)
    pd.testing.assert_series_equal(emissions, carbon["emissions"], check_names=False, check_index_type=False,
                                   rtol=1e-9)
    pd.testing.assert_series_equal(captured, carbon["captured"], check_names=False, check_index_type=False,
                                   rtol=1e-9)
    assert (carbon["captured"]["Example3"] > 0) and (total(data, "Carbon Removal|Geological Storage") == 0).all()
    # Not linked to OptiFlow, so all of it is stored
    pd.testing.assert_series_equal(total(data, "Carbon Capture|Geological Storage"), carbon["captured"],
                                   check_names=False, check_index_type=False, rtol=1e-9)

    no_captured = notes.loc[notes["Note"].str.startswith("The results give no captured CO2"), "Scenario"]
    assert sorted(no_captured) == ["Example1", "Example2"]
    assert not notes["Note"].str.contains("don't mark them w/ CCS|Units whose output the results don't give").any()



def test_primary_energy_equals_raw_results(converted: tuple[pd.DataFrame, pd.DataFrame],
                                           primary: dict[str, pd.DataFrame], electricity: dict[str, pd.Series],
                                           hydrogen: dict[str, pd.Series]) -> None:
    """Primary Energy by Source and purpose adds up to the fuel input of the reported part of
    units' output; nuclear and the renewables count what they make. Heat units outside district
    heating count towards the totals per Source only. Net imports of electricity and hydrogen,
    which cancel out between regions but for import units and trade with countries without an
    IAMC Region, are Secondary Energy Trade. Primary Energy sums all of it, each Source once."""
    data, _ = converted
    by_input = ["Coal", "Gas", "Oil", "Biomass"]
    by_use = sum(total(data, f"Primary Energy|{source}|{purpose}")
                 for source in by_input for purpose in ("Electricity", "Heat", "Hydrogen", "Gases"))
    expected = primary["input_by_use"].reindex(by_input, fill_value=0.0).sum()
    pd.testing.assert_series_equal(by_use, expected * twh_to_ej, check_names=False, check_index_type=False,
                                   rtol=1e-9)
    assert (primary["input"].sum() > primary["input_by_use"].sum()).any()

    counted = primary["input"].add(primary["output"], fill_value=0.0)
    assert {"Nuclear", "Solar", "Wind", "Hydro", "Biomass"} <= set(counted.index)
    for category in set(counted.index) - {"Geothermal"}:
        pd.testing.assert_series_equal(total(data, f"Primary Energy|{category}"), counted.loc[category] * twh_to_ej,
                                       check_names=False, check_index_type=False, rtol=1e-9, atol=1e-12)

    net_imports = -electricity["net_exports"].groupby(level="scenario").sum().reindex(scenarios, fill_value=0.0)
    net_imports -= hydrogen["net_exports"]
    pd.testing.assert_series_equal(total(data, "Primary Energy|Secondary Energy Trade"), net_imports * twh_to_ej,
                                   check_names=False, check_index_type=False, rtol=1e-9, atol=1e-12)

    def sum_of(sources: list[str]) -> pd.Series:
        return sum(total(data, f"Primary Energy|{source}") for source in sources)

    renewables = ["Geothermal", "Hydro", "Ocean", "Solar", "Wind"]
    sources = by_input + renewables + ["Nuclear", "Other", "Secondary Energy Trade"]
    for variable, expected in (("Primary Energy", sum_of(sources)), ("Primary Energy|Fossil", sum_of(by_input[:3])),
                               ("Primary Energy|Non-Biomass Renewables", sum_of(renewables)),
                               ("Primary Energy|Biomass|Modern", sum_of(["Biomass"]))):
        pd.testing.assert_series_equal(total(data, variable), expected, check_names=False, check_index_type=False,
                                       rtol=1e-9, atol=1e-12)
    assert (total(data, "Primary Energy") > 0).all()


def test_prices_equal_raw_results(results: MainResults, raw: pd.DataFrame) -> None:
    """Denmark's electricity price is its regions' prices weighted by their demand, and its
    carbon price the CO2 tax over the emissions of the units that pay it, in each scenario and
    year. Without a currency, pybalmorel's price-level tables give USD_2010 (docs/adr/0017)."""
    data, _ = results.to_iamc("Balmorel", currency={"USD_2010": 1.0})
    data = data[data["Region"] == "Denmark"].set_index(["Scenario", "Variable"])
    long = raw[raw["country"] == "DENMARK"]

    electricity = long[(long["quantity"] == "price") & (long["commodity"] == "ELECTRICITY")]
    assert not electricity.empty
    for (scenario, year), rows in electricity.groupby(["scenario", "year"]):
        expected = (rows["value"] * rows["weight"]).sum() / rows["weight"].sum() / 3.6
        assert data.loc[(scenario, "Price|Secondary Energy|Electricity"), year] == pytest.approx(expected)

    keys = ["scenario", "year", "area", "unit_name", "tech_type", "fuel"]
    units = pd.concat([long[long["quantity"] == quantity].groupby(keys)["value"].sum().rename(quantity)
                       for quantity in ("tax", "emissions")], axis=1, join="inner")
    units = units[(units["emissions"] > 0) & (units["tax"] > 0)]
    assert not units.empty
    for (scenario, year), rows in units.groupby(level=["scenario", "year"]):
        expected = rows["tax"].sum() / rows["emissions"].sum() * 1e3
        assert data.loc[(scenario, "Price|Carbon"), year] == pytest.approx(expected)

    by_tables, _ = results.to_iamc("Balmorel")
    by_tables = by_tables[by_tables["Region"] == "Denmark"].set_index(["Scenario", "Variable"])
    prices = data.index.get_level_values("Variable").str.startswith("Price|")
    years = [column for column in data.columns if isinstance(column, int)]
    worth = (by_tables.loc[data.index[prices], years] / data.loc[prices, years]).stack().dropna()
    assert len(worth) > 0
    assert worth.to_numpy() == pytest.approx(1.2319, abs=1e-4)


def test_read_only_some_scenarios(results: MainResults, raw: pd.DataFrame) -> None:
    """Reading some scenarios gives their rows of the full long table, and the results keep all
    of theirs. OptiFlow results given for a scenario not read are left alone, those for one the
    results lack are refused, as is a scenario they lack."""
    one = read_mainresults(results, scenarios="Example2", optiflow={"Example1": "nowhere/Optiflow_MainResults.gdx"})
    two = read_mainresults(results, scenarios=["Example3", "Example1"])

    assert set(one["scenario"]) == {"Example2"}
    assert set(two["scenario"]) == {"Example1", "Example3"}
    for selected, names in ((one, ["Example2"]), (two, ["Example1", "Example3"])):
        expected = raw[raw["scenario"].isin(names)]
        pd.testing.assert_frame_equal(selected.reset_index(drop=True), expected.reset_index(drop=True),
                                      check_dtype=False, check_categorical=False)
    assert results.sc == scenarios and list(results.db) == scenarios

    with pytest.raises(Exception, match="have no scenarios \\['Example4'\\]"):
        read_mainresults(results, scenarios=["Example4"])
    with pytest.raises(Exception, match="OptiFlow results are given for scenarios \\['Example4'\\]"):
        read_mainresults(results, scenarios="Example2", optiflow={"Example4": None})

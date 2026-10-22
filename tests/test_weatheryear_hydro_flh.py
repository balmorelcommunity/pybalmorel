"""
Absolute Hydro FLH Tests

Tests the absolute hydro FLH mode of the weatheryear module (see CONTEXT.md,
ADR 0011) on small synthetic inflow series. GAMS-free: Balmorel's capacity,
areas and base FLH are given as DataFrames.

Created on 22.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pathlib import Path

import pandas as pd
import pytest

from pybalmorel.weatheryear.config_models import (
    ConfigValidationError,
    HydroFlhConfig,
    HydroModuleConfig,
)
from pybalmorel.weatheryear.hydro_flh import (
    absolute_flh,
    area_countries,
    hydro_capacity,
    move_spilled_run_of_river,
    plausibility_failures,
)
from pybalmorel.weatheryear.hydro_to_btc import _write_flh_inc_files
from pybalmorel.weatheryear.scenario_data import write_scenario_data

YEAR = 2023

# Two hours per year, two years: energies are easy to sum by hand
HOURS = pd.DatetimeIndex(
    ["2022-01-01 00:00", "2022-06-01 00:00", "2023-01-01 00:00", "2023-06-01 00:00"]
)


def inflow(**columns: list[float]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=HOURS, dtype=float)


def capacity(**areas: tuple[float, float]) -> pd.DataFrame:
    """Capacity per area as (reservoir, run-of-river) MW."""
    return pd.DataFrame(areas, index=["WTRRSFLH", "WTRRRFLH"], dtype=float).T


def countries(*areas: str) -> pd.Series:
    return area_countries(pd.DataFrame({"RRR": [area[:2] for area in areas], "AAA": list(areas)}))


def factors(value: float = 1.0, *areas: str) -> pd.Series:
    return pd.Series(value, index=list(areas), dtype=float)


def covering(res: pd.DataFrame, ror: pd.DataFrame) -> pd.DataFrame:
    """Capacity for exactly the CorRES columns, so the coverage check passes."""
    return pd.DataFrame(
        {"WTRRSFLH": 1.0, "WTRRRFLH": 1.0}, index=res.columns.union(ror.columns)
    ).assign(WTRRSFLH=lambda df: df.index.isin(res.columns) * 1.0, WTRRRFLH=lambda df: df.index.isin(ror.columns) * 1.0)


NO_BASE = pd.DataFrame(columns=["WTRRSFLH", "WTRRRFLH"], dtype=float)


# %% ------------------------------- ###
###       1. Balmorel inputs        ###
### ------------------------------- ###


def test_capacity_sums_gkfx_per_hydro_type():
    gkfx = pd.DataFrame(
        {
            "Scenario": "backcast",
            "YYY": ["2023", "2023", "2023", "2050"],
            "AAA": ["AT_A", "AT_A", "AT_A", "AT_A"],
            "GGG": ["HYRS1", "HYRS2", "HYRR1", "HYRS1"],
            "Value": [100.0, 50.0, 30.0, 999.0],
        }
    )
    result = hydro_capacity(
        gkfx, pd.DataFrame({"G": ["HYRS1", "HYRS2"]}), pd.DataFrame({"G": ["HYRR1"]}), YEAR
    )
    assert result.loc["AT_A"].to_dict() == {"WTRRSFLH": 150.0, "WTRRRFLH": 30.0}


def test_empty_hydro_sets_raise():
    gkfx = pd.DataFrame({"YYY": ["2023"], "AAA": ["AT_A"], "GGG": ["HYRS1"], "Value": [1.0]})
    with pytest.raises(Exception, match="IGHYRS and IGHYRR are empty"):
        hydro_capacity(gkfx, pd.DataFrame(), pd.DataFrame(), YEAR)


def test_areas_are_grouped_by_country():
    result = area_countries(
        pd.DataFrame({"RRR": ["DE4-E", "FIN", "NO1", "AT"], "AAA": ["DE4-E_A", "FinA", "NO1_A1", "AT_A"]})
    )
    assert result.to_dict() == {"DE4-E_A": "DE", "FinA": "FI", "NO1_A1": "NO", "AT_A": "AT"}


# %% ------------------------------- ###
###     2. Absolute FLH and spill   ###
### ------------------------------- ###


def test_absolute_flh_is_energy_over_capacity():
    res = inflow(AT_A=[10, 30, 20, 40])
    ror = inflow(AT_A=[50, 50, 60, 80])
    flh = absolute_flh(
        res, ror, factors(1, "AT_A"), factors(1, "AT_A"), YEAR,
        capacity(AT_A=(10, 100)), countries("AT_A"), NO_BASE, reference={"AT": 0.0002},
    )
    # 2023: 60 MWh / 10 MW and 140 MWh / 100 MW; long term: mean of 2022 and 2023
    assert flh["WTRRSFLH"][0]["AT_A"] == pytest.approx(6.0)
    assert flh["WTRRRFLH"][0]["AT_A"] == pytest.approx(1.4)
    assert flh["WTRRSFLH"][1]["AT_A"] == pytest.approx(5.0)
    assert flh["WTRRRFLH"][1]["AT_A"] == pytest.approx(1.2)


def test_run_of_river_above_capacity_moves_to_reservoir():
    res = inflow(PT_A=[10, 10, 10, 10])
    ror = inflow(PT_A=[50, 120, 150, 80])
    res_energy, ror_energy = move_spilled_run_of_river(res, ror, capacity(PT_A=(100, 100)))
    # 2022 spills 20 MWh, 2023 spills 50 MWh
    assert res_energy["PT_A"].to_dict() == {2022: 40.0, 2023: 70.0}
    assert ror_energy["PT_A"].to_dict() == {2022: 150.0, 2023: 180.0}
    assert (res_energy + ror_energy)["PT_A"].to_dict() == {2022: 190.0, 2023: 250.0}


def test_run_of_river_without_capacity_moves_entirely():
    res = inflow(ES_A=[10, 10, 10, 10])
    ror = inflow(ES_A=[5, 5, 5, 5])
    res_energy, ror_energy = move_spilled_run_of_river(res, ror, capacity(ES_A=(100, 0)))
    assert res_energy["ES_A"].to_dict() == {2022: 30.0, 2023: 30.0}
    assert ror_energy["ES_A"].to_dict() == {2022: 0.0, 2023: 0.0}


def test_run_of_river_into_a_new_reservoir_column():
    res = inflow(AT_A=[1, 1, 1, 1])
    ror = inflow(RS_A=[5, 5, 5, 5])
    res_energy, _ = move_spilled_run_of_river(res, ror, capacity(RS_A=(100, 0)))
    assert res_energy["RS_A"].to_dict() == {2022: 10.0, 2023: 10.0}


def test_inflow_without_capacity_gets_no_line(capsys):
    res = inflow(AT_A=[10, 10, 10, 10], UK_A=[1, 1, 1, 1])
    ror = inflow(AT_A=[5, 5, 5, 5], UK_A=[2, 2, 2, 2])
    flh = absolute_flh(
        res, ror, factors(1), factors(1), YEAR,
        capacity(AT_A=(100, 100)), countries("AT_A", "UK_A"), NO_BASE,
        reference={"AT": 0.00003, "UK": 0.000006},
    )
    assert "UK_A" not in flh["WTRRSFLH"][0] and "UK_A" not in flh["WTRRRFLH"][0]
    output = capsys.readouterr().out
    assert "UK_A has 0.00 TWh of reservoir inflow" in output
    assert "UK_A has 0.00 TWh of run-of-river inflow" in output


def test_country_without_corres_columns_gets_the_reference_level(capsys):
    res = inflow(AT_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5])
    flh_base = pd.DataFrame({"WTRRSFLH": [3000.0], "WTRRRFLH": [float("nan")]}, index=["TR_A"])
    flh = absolute_flh(
        res, ror, factors(1), factors(1), YEAR,
        capacity(AT_A=(100, 100), TR_A=(20, 0)), countries("AT_A", "TR_A"), flh_base,
        reference={"AT": 0.00003, "TR": 0.0001},
    )
    # f = 1 in the year files too: no variation without CorRES data
    assert flh["WTRRSFLH"][0]["TR_A"] == pytest.approx(100 / 20)
    assert flh["WTRRSFLH"][1]["TR_A"] == pytest.approx(100 / 20)
    assert "Hydro Inflow Fallback for TR: CorRES has no column for it" in capsys.readouterr().out


def test_partly_covered_country_falls_back_with_its_country_factor(capsys):
    # RS has run-of-river data but no reservoir column; 2023 is 1.5 x its long-term mean
    res = inflow(AT_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5], RS_A=[10, 10, 30, 30])
    flh_base = pd.DataFrame({"WTRRSFLH": [1000.0], "WTRRRFLH": [2000.0]}, index=["RS_A"])
    flh = absolute_flh(
        res, ror, factors(1, "AT_A"), factors(1.1, "AT_A", "RS_A"), YEAR,
        capacity(AT_A=(100, 100), RS_A=(10, 10)), countries("AT_A", "RS_A"), flh_base,
        reference={"AT": 0.00003, "RS": 0.00006},
    )
    # Long term: 60 MWh split 1000*10 : 2000*10
    assert flh["WTRRSFLH"][1]["RS_A"] == pytest.approx(2.0)
    assert flh["WTRRRFLH"][1]["RS_A"] == pytest.approx(4.0)
    # 2023: the reservoir takes the country's factor, run-of-river its own
    assert flh["WTRRSFLH"][0]["RS_A"] == pytest.approx(2.0 * 1.5)
    assert flh["WTRRRFLH"][0]["RS_A"] == pytest.approx(4.0 * 1.1)
    assert "RS: CorRES covers it only partly, with no column for RS_A (reservoir)" in capsys.readouterr().out


def test_missing_base_flh_gives_its_share_to_the_others():
    # LV: a reservoir without base FLH, run-of-river in another area
    res = inflow(AT_A=[10, 10, 10, 10], LV_B=[1, 1, 1, 1])
    ror = inflow(AT_A=[5, 5, 5, 5], LV_C=[1, 1, 1, 1])
    flh_base = pd.DataFrame({"WTRRSFLH": [float("nan")], "WTRRRFLH": [2000.0]}, index=["LV_C"])
    flh = absolute_flh(
        res, ror, factors(1), factors(1), YEAR,
        capacity(AT_A=(100, 100), LV_B=(10, 0), LV_C=(0, 10)), countries("AT_A", "LV_B", "LV_C"),
        flh_base, reference={"AT": 0.00003, "LV": 0.00001},
    )
    assert "LV_B" not in flh["WTRRSFLH"][1]
    assert flh["WTRRRFLH"][1]["LV_C"] == pytest.approx(1.0)


def test_fallback_without_reference_keeps_base_flh_times_factor(capsys):
    res = inflow(AT_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5])
    flh_base = pd.DataFrame({"WTRRSFLH": [3000.0], "WTRRRFLH": [float("nan")]}, index=["XX_A"])
    flh = absolute_flh(
        res, ror, factors(1), factors(1), YEAR,
        capacity(AT_A=(100, 100), XX_A=(20, 0)), countries("AT_A", "XX_A"), flh_base,
        reference={"AT": 0.00003},
    )
    assert flh["WTRRSFLH"][0]["XX_A"] == pytest.approx(3000.0)
    assert "XX needs the Hydro Inflow Fallback but has no reference" in capsys.readouterr().out


def test_flh_above_a_year_raises():
    res = inflow(AT_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5])
    with pytest.raises(Exception, match="above 8760 h"):
        absolute_flh(
            res, ror, factors(1), factors(1), YEAR,
            capacity(AT_A=(0.001, 100)), countries("AT_A"), NO_BASE, reference={"AT": 0.00003},
        )


# %% ------------------------------- ###
###  3. Plausibility and fallback   ###
### ------------------------------- ###


# Long-term energy of each area below: 30 MWh/yr, i.e. 0.00003 TWh/yr
PLAUSIBLE = {"AT": 0.00003, "FR": 0.00003, "SE": 0.00003}


def test_identical_reservoir_and_run_of_river_fail():
    res = inflow(SE1A=[1, 2, 3, 4], AT_A=[10, 10, 10, 10])
    ror = inflow(SE1A=[1, 2, 3, 4], AT_A=[5, 5, 5, 5])
    failures = plausibility_failures(
        res, ror, covering(res, ror), countries("SE1A", "AT_A"), {"SE": 0.00001, "AT": 0.00003}
    )
    assert set(failures) == {"SE"}
    assert "identical to its run-of-river" in failures["SE"]


def test_identical_columns_in_two_areas_fail():
    res = inflow(AT_A=[10, 10, 10, 10], FR_A=[1, 2, 3, 4])
    ror = inflow(AT_A=[5, 5, 5, 5], SE1A=[1, 2, 3, 4])
    failures = plausibility_failures(
        res, ror, covering(res, ror), countries("AT_A", "FR_A", "SE1A"), {"AT": 0.00003, "FR": 0.000005, "SE": 0.000005}
    )
    assert set(failures) == {"FR", "SE"}


@pytest.mark.parametrize("deviation, fails", [(0.25, True), (-0.25, True), (0.15, False), (-0.15, False)])
def test_level_off_the_reference(deviation: float, fails: bool):
    res = inflow(AT_A=[10, 10, 10, 10], FR_A=[11, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5], FR_A=[6, 5, 5, 5])
    # FR: 31 MWh/yr in the long term
    reference = {"AT": 0.00003, "FR": 0.000031 / (1 + deviation)}
    assert ("FR" in plausibility_failures(res, ror, covering(res, ror), countries("AT_A", "FR_A"), reference)) == fails


def test_country_missing_from_reference_is_kept(capsys):
    res = inflow(AT_A=[10, 10, 10, 10], XX_A=[1, 1, 1, 1])
    ror = inflow(AT_A=[5, 5, 5, 5], XX_A=[2, 2, 2, 2])
    failures = plausibility_failures(res, ror, covering(res, ror), countries("AT_A", "XX_A"), {"AT": 0.00003})
    assert failures == {}
    assert "XX has no reference" in capsys.readouterr().out


def test_every_country_failing_raises():
    res = inflow(AT_A=[10, 10, 10, 10], FR_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5], FR_A=[6, 5, 5, 5])
    with pytest.raises(Exception, match="Every country with CorRES inflow fails"):
        plausibility_failures(res, ror, covering(res, ror), countries("AT_A", "FR_A"), {"AT": 1.0, "FR": 1.0})


def test_countries_without_columns_dont_count_towards_every_country_failing():
    res = inflow(AT_A=[10, 10, 10, 10])
    ror = inflow(AT_A=[5, 5, 5, 5])
    cap = capacity(AT_A=(100, 100), TR_A=(100, 0))
    failures = plausibility_failures(res, ror, cap, countries("AT_A", "TR_A"), {"AT": 0.00003, "TR": 1.0})
    assert set(failures) == {"TR"}


def test_fallback_gives_the_reference_split_by_base_flh_and_capacity(capsys):
    # SE fails (reservoir = run-of-river); AT passes
    res = inflow(AT_A=[10, 10, 10, 10], SE1A=[1, 2, 3, 4], SE2A=[4, 4, 4, 4])
    ror = inflow(AT_A=[5, 5, 5, 5], SE1A=[1, 2, 3, 4], SE2A=[1, 1, 1, 1])
    cap = capacity(AT_A=(100, 100), SE1A=(10, 20), SE2A=(30, 0))
    flh_base = pd.DataFrame(
        {"WTRRSFLH": [3000.0, 2000.0], "WTRRRFLH": [5000.0, 4000.0]}, index=["SE1A", "SE2A"]
    )
    reference = {"AT": 0.00003, "SE": 0.1}
    flh = absolute_flh(
        res, ror, factors(1.2, "SE1A", "SE2A"), factors(1.2, "SE1A", "SE2A"), YEAR,
        cap, countries("AT_A", "SE1A", "SE2A"), flh_base, reference,
    )

    se_areas = ["SE1A", "SE2A"]
    for horizon, factor in ((0, 1.2), (1, 1.0)):
        total = sum(
            flh[symbol][horizon].reindex(se_areas).fillna(0) @ cap.loc[se_areas, symbol]
            for symbol in ("WTRRSFLH", "WTRRRFLH")
        )
        assert total == pytest.approx(0.1e6 * factor)
    # The split between areas and types follows FLHbase x K: 3000*10 : 5000*20 : 2000*30
    year = flh["WTRRSFLH"][1]
    assert year["SE1A"] / year["SE2A"] == pytest.approx(3000 / 2000)
    assert "SE2A" not in flh["WTRRRFLH"][0]  # no run-of-river capacity
    # AT keeps its CorRES-based FLH
    assert flh["WTRRSFLH"][0]["AT_A"] == pytest.approx(0.2)
    assert "Hydro Inflow Fallback for SE" in capsys.readouterr().out


# %% ------------------------------- ###
###        4. Config and files      ###
### ------------------------------- ###


CONFIG = """\
hydro_model_results: hydro
CapDev_timesteps_to_keep:
  S: [S01]
  T: [T001]
"""


def test_mode_defaults_to_relative(tmp_path: Path):
    config_fn = tmp_path / "config.yml"
    config_fn.write_text(CONFIG)
    assert HydroModuleConfig.from_file(str(config_fn)).hydro_flh == HydroFlhConfig()


def test_absolute_mode_resolves_balmorel_path_from_the_config(tmp_path: Path):
    config_fn = tmp_path / "weatheryear" / "config.yml"
    config_fn.parent.mkdir()
    config_fn.write_text(
        CONFIG + "hydro_flh:\n  mode: absolute\n  balmorel_path: ../..\n  scenario: backcast\n  capacity_year: 2023\n"
    )
    hydro_flh = HydroModuleConfig.from_file(str(config_fn)).hydro_flh
    assert hydro_flh == HydroFlhConfig("absolute", str(tmp_path.parent), "backcast", 2023)


def test_absolute_mode_without_scenario_raises(tmp_path: Path):
    config_fn = tmp_path / "config.yml"
    config_fn.write_text(CONFIG + "hydro_flh:\n  mode: absolute\n  balmorel_path: ..\n  capacity_year: 2023\n")
    with pytest.raises(ConfigValidationError, match="scenario"):
        HydroModuleConfig.from_file(str(config_fn))


def _write_flh(folder: Path, series: pd.Series, symbol: str, absolute_header: str | None = None) -> list[Path]:
    folders = [folder / name for name in ("hd_raw", "hd_scaled", "lt", "fy", "raw")]
    for path in folders:
        path.mkdir(parents=True)
    _write_flh_inc_files(series, series, symbol, "flh.csv", *map(str, folders), absolute_header=absolute_header)
    return folders


def test_relative_lines_are_unchanged(tmp_path: Path):
    folders = _write_flh(tmp_path, pd.Series({"AT_A": 1.25, "FinA": 0.9}), "WTRRSFLH")
    assert (folders[0] / "WTRRSFLH_WY.inc").read_text() == (
        "*File created from weatheryear module\n"
        "WTRRSFLH('AT_A') = 1.25 * WTRRSFLH('AT_A') ;\n"
        "WTRRSFLH('FinA') = 0.9 * WTRRSFLH('FinA') ;\n"
    )


def test_absolute_lines_survive_the_scenario_data_step(tmp_path: Path):
    header = "* Absolute hydro FLH: CorRES inflow energy / GKFX of backcast in 2023 (see CONTEXT.md, ADR 0011)"
    folders = _write_flh(tmp_path / "wy", pd.Series({"AT_A": 586.6612}), "WTRRSFLH", header)
    written = (folders[4] / "WTRRSFLH_WY.inc").read_text()
    assert written == f"*File created from weatheryear module\n{header}\nWTRRSFLH('AT_A') = 586.66 ;\n"

    write_scenario_data(folders[4], tmp_path / "wy", tmp_path / "data")
    scenario_text = (tmp_path / "data" / "WTRRSFLH.inc").read_text()
    assert "WTRRSFLH('AT_A') = 586.66 ;" in scenario_text
    assert "*WTRRSFLH('AT_A')" not in scenario_text

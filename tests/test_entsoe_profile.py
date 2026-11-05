"""
ENTSO-E Production Profile Tests

GAMS-free tests of the ENTSO-E production profile on synthetic generation,
load, day_ahead_prices and crossborder_flows csv's: required data, zone
spellings, summing zones, load-weighted prices, net import and the plot.

Created on 05.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from pybalmorel.entsoe import plot_profile, read_profile  # noqa: E402
from pybalmorel.entsoe.profile import _group_production  # noqa: E402

START, END = "2023-01-02", "2023-01-03"


def _index(periods: int, freq: str = "1h") -> pd.DatetimeIndex:
    """Brussels time, as the fetched csv's are saved."""
    return pd.date_range(START, periods=periods, freq=freq, tz="Europe/Brussels")


def _write_series(path, file_name, values, column, freq="1h"):
    pd.Series(values, index=_index(len(values), freq), name=column).to_csv(path / file_name)


def _write_generation(path, file_name, columns, freq="1h"):
    pd.DataFrame(columns, index=_index(len(next(iter(columns.values()))), freq)).to_csv(path / file_name)


@pytest.fixture
def entsoe_folder(tmp_path):
    # DK_1, saved under its EIC code, at hourly resolution
    _write_generation(
        tmp_path,
        "2023_10YDK-1--------W_generation.csv",
        {"Wind Onshore": [100.0] * 24, "Fossil Gas": [50.0] * 24},
    )
    _write_series(tmp_path, "2023_10YDK-1--------W_load.csv", [120.0] * 24, "Actual Load")
    _write_series(tmp_path, "2023_10YDK-1--------W_day_ahead_prices.csv", [10.0] * 24, "0")

    # DK_2, saved under its area name, at 15-minute resolution, with pumping
    # saved as 'Actual Consumption' in a second header row
    index = _index(96, "15min")
    generation = pd.DataFrame(
        {
            ("Solar", "Actual Aggregated"): [30.0] * 96,
            ("Hydro Pumped Storage", "Actual Aggregated"): [5.0] * 96,
            ("Hydro Pumped Storage", "Actual Consumption"): [99.0] * 96,
        },
        index=index,
    )
    generation.to_csv(tmp_path / "2023_DK_2_generation.csv")
    _write_series(tmp_path, "2023_DK_2_load.csv", [40.0] * 96, "Actual Load", "15min")
    _write_series(tmp_path, "2023_DK_2_day_ahead_prices.csv", [20.0, 40.0] * 48, "0", "15min")

    # Flows: DE_LU <-> DK_1, DK_1 -> DK_2 and DK_2 -> SE_4
    _write_series(tmp_path, "2023_DE_LU-DK_1_crossborder_flows.csv", [20.0] * 24, "0")
    _write_series(tmp_path, "2023_DK_1-DE_LU_crossborder_flows.csv", [5.0] * 24, "0")
    _write_series(tmp_path, "2023_DK_1-DK_2_crossborder_flows.csv", [7.0] * 24, "0")
    _write_series(tmp_path, "2023_DK_2-SE_4_crossborder_flows.csv", [3.0] * 24, "0")
    return tmp_path


# %% ------------------------------- ###
###          1. Reading data        ###
### ------------------------------- ###


def test_single_zone(entsoe_folder, capsys):
    profile = read_profile(entsoe_folder, 2023, "DK1", start=START, end=END)

    assert profile.zones == ["DK_1"]
    assert len(profile.load) == 24
    assert str(profile.load.index.tz) == "Europe/Brussels"
    assert profile.generation["Wind Onshore"].eq(100).all()
    assert profile.generation["Fossil Gas"].eq(50).all()
    assert profile.load.eq(120).all()
    assert profile.price.eq(10).all()
    # In from DE_LU, out to DE_LU and DK_2, which is outside the selection
    assert profile.net_import.eq(20 - 5 - 7).all()

    scope = capsys.readouterr().out
    assert "DK_1 (10YDK-1--------W)" in scope
    assert "(24 hours)" in scope
    assert "borders with DE_LU, DK_2" in scope


def test_two_header_generation_keeps_actual_aggregated(entsoe_folder):
    profile = read_profile(entsoe_folder, 2023, "DK_2", start=START, end=END, verbose=False)

    assert sorted(profile.generation.columns) == ["Hydro Pumped Storage", "Solar"]
    assert profile.generation["Hydro Pumped Storage"].eq(5).all()
    # Quarter hours averaged to hours
    assert profile.price.eq(30).all()


def test_zones_summed_and_price_weighted_by_load(entsoe_folder, capsys):
    profile = read_profile(entsoe_folder, 2023, ["DK1", "DK2"], start=START, end=END)

    assert profile.zones == ["DK_1", "DK_2"]
    assert profile.load.eq(120 + 40).all()
    assert profile.price.eq((10 * 120 + 30 * 40) / (120 + 40)).all()
    # The DK_1 -> DK_2 flow is internal, so left out
    assert profile.net_import.eq(20 - 5 - 3).all()
    assert "load-weighted over 2 zones" in capsys.readouterr().out


def test_hour_missing_for_one_zone_is_a_gap_in_the_sum(entsoe_folder, capsys):
    generation = [30.0] * 24
    generation[3] = np.nan
    _write_generation(entsoe_folder, "2023_DK_2_generation.csv", {"Solar": generation})

    profile = read_profile(entsoe_folder, 2023, ["DK1", "DK2"], start=START, end=END)

    assert profile.generation.iloc[3].isna().all()
    assert profile.generation.iloc[4].sum() == 100 + 50 + 30
    scope = capsys.readouterr().out
    assert "1 of 24 hours missing" in scope
    assert "missing for DK_2 (1)" in scope
    assert "over the 23 hours with generation and load of every zone" in scope


@pytest.mark.parametrize("zones", ["all", ["ALL"]])
def test_all_zones(entsoe_folder, capsys, zones):
    # AL has load only, GB has nothing, as ENTSO-E has no data for it
    _write_series(entsoe_folder, "2023_AL_load.csv", [10.0] * 24, "Actual Load")
    (entsoe_folder / "2023_generation_nodata.txt").write_text("10YGB----------A\n")
    (entsoe_folder / "2023_load_nodata.txt").write_text("10YGB----------A\n")

    profile = read_profile(entsoe_folder, 2023, zones, start=START, end=END)

    assert profile.zones == ["DK_1", "DK_2"]
    assert profile.load.eq(120 + 40).all()
    assert profile.net_import.eq(20 - 5 - 3).all()
    scope = capsys.readouterr().out
    assert "Left out:    AL (no generation downloaded), GB (no generation or load from ENTSO-E)" in scope


def test_all_zones_leaves_out_zones_without_data_in_the_period(tmp_path, capsys):
    two_days = pd.date_range(START, periods=48, freq="1h", tz="Europe/Brussels")
    pd.DataFrame({"Nuclear": 10.0}, index=two_days).to_csv(tmp_path / "2023_SE_3_generation.csv")
    pd.Series(5.0, index=two_days, name="Actual Load").to_csv(tmp_path / "2023_SE_3_load.csv")
    _write_generation(tmp_path, "2023_SE_4_generation.csv", {"Nuclear": [1.0] * 24})
    _write_series(tmp_path, "2023_SE_4_load.csv", [1.0] * 24, "Actual Load")

    profile = read_profile(tmp_path, 2023, "all", start=END, end="2023-01-04")

    assert profile.zones == ["SE_3"]
    assert "SE_4 (no generation or load in the period)" in capsys.readouterr().out
    with pytest.raises(Exception, match="No ENTSO-E data in"):
        read_profile(tmp_path, 2023, "all", start="2023-01-04", end="2023-01-05")


def test_all_zones_without_data_raises(tmp_path):
    with pytest.raises(Exception, match="no generation or load csv's"):
        read_profile(tmp_path, 2023, "all")

    _write_series(tmp_path, "2023_AL_load.csv", [10.0] * 24, "Actual Load")
    with pytest.raises(Exception, match="generation of AL .*: not downloaded"):
        read_profile(tmp_path, 2023, "all")


def test_flow_to_zone_inside_a_selected_zone_is_internal(tmp_path):
    for zone in ("BE", "DE_LU"):
        _write_generation(tmp_path, f"2023_{zone}_generation.csv", {"Nuclear": [10.0] * 24})
        _write_series(tmp_path, f"2023_{zone}_load.csv", [10.0] * 24, "Actual Load")
    _write_series(tmp_path, "2023_BE-LU_crossborder_flows.csv", [4.0] * 24, "0")
    _write_series(tmp_path, "2023_BE-NL_crossborder_flows.csv", [1.0] * 24, "0")

    # LU is part of DE_LU, so BE-LU is internal to BE + DE_LU
    profile = read_profile(tmp_path, 2023, ["BE", "DE_LU"], start=START, end=END, verbose=False)
    assert profile.net_import.eq(-1).all()

    # Alone, BE exports to LU
    profile = read_profile(tmp_path, 2023, "BE", start=START, end=END, verbose=False)
    assert profile.net_import.eq(-5).all()


def test_load_of_smaller_area_is_used_and_noted(tmp_path, capsys):
    _write_generation(tmp_path, "2023_IE_SEM_generation.csv", {"Wind Onshore": [10.0] * 24})
    _write_series(tmp_path, "2023_IE_load.csv", [8.0] * 24, "Actual Load")
    # Superseded all-island load, never read
    _write_series(tmp_path, "2023_IE_SEM_load.csv", [999.0] * 24, "Actual Load")

    profile = read_profile(tmp_path, 2023, "IE", start=START, end=END)

    assert profile.load.eq(8).all()
    assert profile.price is None and profile.net_import is None
    scope = capsys.readouterr().out
    assert "load of IE_SEM is for IE only" in scope
    assert "plotted without price" in scope


# %% ------------------------------- ###
###          2. Missing data        ###
### ------------------------------- ###


def test_missing_zone_raises(entsoe_folder):
    (entsoe_folder / "2023_generation_nodata.txt").write_text("10YGB----------A\n")

    with pytest.raises(Exception, match="No ENTSO-E data to plot") as error:
        read_profile(entsoe_folder, 2023, ["DK1", "SE4", "UK"])

    message = str(error.value)
    assert "generation of SE_4 (10Y1001A1001A47J): not downloaded" in message
    assert "load of SE_4 (10Y1001A1001A47J): not downloaded" in message
    assert "generation of GB (10YGB----------A): ENTSO-E has no data for it" in message
    assert "download" in message and "--query generation" in message
    assert "DK_1" not in message


def test_period_without_data_raises(entsoe_folder):
    with pytest.raises(Exception, match="No ENTSO-E data in .* generation of DK_1, load of DK_1"):
        read_profile(entsoe_folder, 2023, "DK1", start="2023-03-01", end="2023-03-02")


def test_start_after_end_raises(entsoe_folder):
    with pytest.raises(ValueError, match="must be before end"):
        read_profile(entsoe_folder, 2023, "DK1", start=END, end=START)


def test_hour_without_any_generation_stays_a_gap():
    generation = pd.DataFrame(
        {
            "Fossil Oil": [1.0, np.nan, np.nan],
            "Wind Onshore": [2.0, 3.0, np.nan],
            "Wind Offshore": [4.0, 5.0, np.nan],
            "Nuclear": [6.0, 7.0, np.nan],
        }
    )

    grouped = _group_production(generation)

    # Stacking order, with unlisted types in 'Oil & other'
    assert list(grouped.columns) == ["Nuclear", "Wind", "Oil & other"]
    assert grouped.iloc[0].tolist() == [6.0, 6.0, 1.0]
    assert grouped.iloc[1].tolist() == [7.0, 8.0, 0.0]
    assert grouped.iloc[2].isna().all()


# %% ------------------------------- ###
###             3. Plot             ###
### ------------------------------- ###


def test_plot_with_price_panel(entsoe_folder):
    fig, axes = plot_profile(entsoe_folder, 2023, "DK1", start=START, end=END)

    assert len(axes) == 2
    labels = axes[0].get_legend().get_texts()
    assert [label.get_text() for label in labels] == [
        "Load",
        "Net import (export below 0)",
        "Wind",
        "Gas",
    ]
    assert axes[1].lines[0].get_ydata().tolist() == [10.0] * 24
    assert axes[0].get_title(loc="left").startswith("DK1 - ENTSO-E")


def test_plot_all_zones_title(entsoe_folder):
    fig, axes = plot_profile(entsoe_folder, 2023, "all", start=START, end=END)

    assert axes[0].get_title(loc="left").startswith("All zones - ENTSO-E")
    assert axes[1].get_ylabel().startswith("Load-weighted price")


def test_plot_without_price(entsoe_folder):
    (entsoe_folder / "2023_10YDK-1--------W_day_ahead_prices.csv").unlink()

    fig, axes = plot_profile(entsoe_folder, 2023, "DK1", start=START, end=END)

    assert len(axes) == 1

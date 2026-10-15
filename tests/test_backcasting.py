"""
Backcasting Tests

GAMS-free tests of the backcast toolbox on synthetic data: the UTC Backcast
Calendar (docs/adr/0008), Price Year conversion (docs/adr/0009), the CO2 tax
and fuel price grids, balopt.opt checks and the cross-border flow validation.

Created on 15.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import numpy as np
import pandas as pd
import pytest

from pybalmorel.backcasting.calendar import (
    backcast_hours,
    daily_to_backcast_grid,
    first_monday,
    from_backcast_grid,
    to_backcast_grid,
)
from pybalmorel.backcasting.co2tax import parse_co2_overrides, write_co2_tax_override
from pybalmorel.backcasting.flows import (
    align_flows,
    entsoe_flow_limits,
    flow_statistics,
    format_balmorel_flows,
    load_entsoe_flows,
    parse_flow_filename,
)
from pybalmorel.backcasting.pricelevel import deflator, eur_per_usd, to_price_year
from pybalmorel.backcasting.scenariochecks import (
    check_balopt_option,
    check_hardcoded_fuelprices,
)

# %% ------------------------------- ###
###        1. Backcast Calendar     ###
### ------------------------------- ###


@pytest.mark.parametrize(
    "year, expected",
    [(2023, "2023-01-02"), (2024, "2024-01-01"), (2022, "2022-01-03")],
)
def test_first_monday(year, expected):
    assert first_monday(year) == pd.Timestamp(expected, tz="UTC")


def test_backcast_hours_are_52_full_utc_weeks():
    hours = backcast_hours(2023)
    assert len(hours) == 52 * 168
    assert str(hours.tz) == "UTC"
    assert hours[0] == pd.Timestamp("2023-01-02 00:00", tz="UTC")
    # No DST gaps or duplicates: every day has exactly 24 terms
    assert (hours.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()
    assert (hours.normalize().value_counts() == 24).all()


def test_from_backcast_grid_matches_by_label_not_position():
    df = pd.DataFrame(
        {
            "Region": ["DK1", "DK1", "DK1"],
            "Season": ["S52", "S01", "S13"],
            "Time": ["T168", "T001", "T001"],
            "Value": [3.0, 1.0, 2.0],
        }
    )
    out = from_backcast_grid(df, 2023).set_index("Time")["Value"]

    assert out[pd.Timestamp("2023-01-02 00:00", tz="UTC")] == 1.0
    # S13 T001 is 12 weeks after S01 T001, unaffected by the March DST change
    assert out[pd.Timestamp("2023-03-27 00:00", tz="UTC")] == 2.0
    assert out[pd.Timestamp("2023-12-31 23:00", tz="UTC")] == 3.0


def test_from_backcast_grid_rejects_unknown_labels():
    df = pd.DataFrame({"Season": ["S53"], "Time": ["T001"], "Value": [1.0]})
    with pytest.raises(ValueError, match="S53"):
        from_backcast_grid(df, 2023)


def test_to_backcast_grid_converts_local_time_to_utc():
    hours = backcast_hours(2023)
    local = pd.Series(np.arange(len(hours)), index=hours.tz_convert("Europe/Copenhagen"))
    grid = to_backcast_grid(local, 2023)

    assert grid.shape == (52, 168)
    assert grid.loc["S01", "T001"] == 0
    assert grid.loc["S52", "T168"] == len(hours) - 1


def test_daily_to_backcast_grid_uses_utc_days_and_carries_forward():
    # Friday 6 Jan and Monday 9 Jan 2023 traded; the weekend carries Friday's price
    daily = pd.Series(
        [10.0, 20.0, 30.0],
        index=pd.to_datetime(["2022-12-30", "2023-01-06", "2023-01-09"]),
    )
    grid = daily_to_backcast_grid(daily, 2023)

    # Mon 2 Jan - Thu 5 Jan carry the 30 Dec price forward
    assert (grid.loc["S01", "T001":"T096"] == 10.0).all()
    assert (grid.loc["S01", "T097":"T168"] == 20.0).all()  # Fri-Sun
    assert (grid.loc["S02", "T001":"T024"] == 30.0).all()  # Mon 9 Jan, 00-23 UTC
    assert (grid.loc["S52"] == 30.0).all()


def test_daily_to_backcast_grid_rejects_wrong_year():
    daily = pd.Series([10.0], index=pd.to_datetime(["2021-06-01"]))
    with pytest.raises(ValueError, match="2023"):
        daily_to_backcast_grid(daily, 2023)


# %% ------------------------------- ###
###        2. Price Year            ###
### ------------------------------- ###


def test_deflator_is_hicp_ratio():
    assert deflator(2016) == 1.0
    assert deflator(2024) == pytest.approx(100.23 / 126.07)


def test_usd_prices_are_converted_then_deflated():
    assert to_price_year(1.0824, 2024, currency="USD") == pytest.approx(
        100.23 / 126.07
    )
    assert eur_per_usd(2023) == pytest.approx(1 / 1.0813)


def test_price_year_missing_year_raises():
    with pytest.raises(Exception, match="2030"):
        deflator(2030)


def test_price_year_applies_to_grids():
    grid = pd.DataFrame([[10.0, 20.0]])
    assert to_price_year(grid, 2016).equals(grid)


# %% ------------------------------- ###
###        3. CO2 tax               ###
### ------------------------------- ###


def test_parse_co2_overrides():
    assert parse_co2_overrides(["united_kingdom=85", "SERBIA=0"]) == {
        "UNITED_KINGDOM": 85.0,
        "SERBIA": 0.0,
    }
    with pytest.raises(Exception, match="Unknown country"):
        parse_co2_overrides(["MARS=1"])
    with pytest.raises(Exception, match="COUNTRY=VALUE"):
        parse_co2_overrides(["DENMARK"])


def test_write_co2_tax_override(tmp_path):
    grid = daily_to_backcast_grid(
        pd.Series([50.0], index=pd.to_datetime(["2023-01-02"])), 2023
    )
    write_co2_tax_override(grid, 2023, tmp_path, {"SERBIA": 0.0})
    content = (tmp_path / "TAX_CO2_ST.inc").read_text()

    assert "TAX_CO2_ST('2023',C,SSS,TTT) = TAX_CO2_ST_EUA(SSS,TTT);" in content
    assert "TAX_CO2_ST('2023','SERBIA',SSS,TTT) = 0.0000;" in content
    # The country override comes after, so it wins
    assert content.index("'SERBIA'") > content.index("TAX_CO2_ST('2023',C,")


# %% ------------------------------- ###
###        4. Scenario checks       ###
### ------------------------------- ###


def test_check_balopt_option_falls_back_to_base(tmp_path, capsys):
    (tmp_path / "base" / "model").mkdir(parents=True)
    (tmp_path / "base" / "model" / "balopt.opt").write_text(
        "$setglobal TAX_CO2_DOL YYY_CCC\n* $setglobal TAX_CO2_DOL YYY_CCC_SSS_TTT\n"
    )
    scenario = tmp_path / "backcast"
    scenario.mkdir()

    assert not check_balopt_option(scenario, "TAX_CO2_DOL", "YYY_CCC_SSS_TTT")
    assert "TAX_CO2_DOL=YYY_CCC" in capsys.readouterr().out

    (scenario / "model").mkdir()
    (scenario / "model" / "balopt.opt").write_text(
        "$setglobal TAX_CO2_DOL YYY_CCC_SSS_TTT\n"
    )
    assert check_balopt_option(scenario, "TAX_CO2_DOL", "YYY_CCC_SSS_TTT")


def test_check_hardcoded_fuelprices(tmp_path):
    (tmp_path / "backcast" / "data").mkdir(parents=True)
    (tmp_path / "backcast" / "data" / "HYDROGEN_FUELPRICE.inc").write_text(
        "* FUELPRICE_HYDROGEN('2023',AAA,'COAL') = 1;\n"
        "$ontext\nFUELPRICE_HYDROGEN('2023',AAA,'COAL') = 2;\n$offtext\n"
        "FUELPRICE_HYDROGEN('2023',AAA,'FUELOIL') = 3;\n"
        "FUELPRICE_HYDROGEN('2023',AAA,'NATGAS') = 4;\n"
    )
    offending = check_hardcoded_fuelprices(tmp_path / "backcast", ["NATGAS", "COAL"])
    assert offending == ["FUELPRICE_HYDROGEN('2023',AAA,'NATGAS') = 4;"]


# %% ------------------------------- ###
###        5. Flow validation       ###
### ------------------------------- ###


@pytest.mark.parametrize(
    "file_name, expected",
    [
        ("2023_FR-ES_crossborder_flows.csv", ("FR", "ES")),
        ("2023_DE_LU-10YDK-1--------W_crossborder_flows.csv", ("DE_LU", "10YDK-1--------W")),
        (
            "2023_10YNO-1--------2-10Y1001A1001A48H_crossborder_flows.csv",
            ("10YNO-1--------2", "10Y1001A1001A48H"),
        ),
        ("2024_FR-ES_crossborder_flows.csv", None),
    ],
)
def test_parse_flow_filename(file_name, expected):
    assert parse_flow_filename(file_name, 2023) == expected


def _write_flow_csv(path, file_name, values, freq="15min"):
    index = pd.date_range("2023-01-02 00:00", periods=len(values), freq=freq, tz="UTC")
    pd.Series(values, index=index.tz_convert("Europe/Brussels")).to_csv(path / file_name)


def test_flow_validation(tmp_path):
    # Two Italian sub-zones into CH sum to one canonical IT -> CH border
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A73I-CH_crossborder_flows.csv", [100.0] * 8)
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A70O-CH_crossborder_flows.csv", [50.0] * 4 + [10.0] * 4)
    _write_flow_csv(tmp_path, "2023_CH-10Y1001A1001A73I_crossborder_flows.csv", [0.0] * 8)
    # An internal link between two Italian sub-zones is dropped
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A73I-10Y1001A1001A70O_crossborder_flows.csv", [1.0] * 8)

    entsoe = load_entsoe_flows(tmp_path, 2023)
    assert set(map(tuple, entsoe[["From", "To"]].to_numpy())) == {("IT", "CH"), ("CH", "IT")}
    it_ch = entsoe.query("From == 'IT'").set_index("Time")["Value"]
    assert it_ch.tolist() == [150.0, 110.0]  # hourly means of 15-min data, summed

    limits = entsoe_flow_limits(tmp_path, 2023)
    assert limits[("IT", "CH")] == 150.0

    # Balmorel only reports the first hour IT-NORD -> CH; the rest is zero flow
    balmorel = format_balmorel_flows(
        pd.DataFrame(
            {
                "From": ["IT-NORD", "IT-CNOR", "IT-NORD"],
                "To": ["CH", "CH", "IT-CNOR"],
                "Season": ["S01"] * 3,
                "Time": ["T001"] * 3,
                "Value": [100.0, 50.0, 999.0],
            }
        ),
        2023,
    )
    flows = align_flows(entsoe, balmorel, limits)
    assert flows.loc[("IT", "CH"), "BALMOREL"].tolist() == [150.0, 0.0]
    assert flows.loc[("CH", "IT"), "BALMOREL"].tolist() == [0.0, 0.0]

    stats = flow_statistics(flows)
    assert stats.loc[("IT", "CH"), "ENTSOE_TWh"] == pytest.approx(260 / 1e6)
    assert stats.loc[("IT", "CH"), "BALMOREL_AtLimit"] == 0.5
    assert stats.loc[("IT", "CH"), "ENTSOE_AtLimit"] == 0.5

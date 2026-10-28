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
from pybalmorel.backcasting.fuelprices import load_ttf_gas_prices, split_yahoo_ttf_html
from pybalmorel.backcasting.flows import (
    align_flows,
    canonical_region,
    compute_entsoe_transmission_overrides,
    flow_statistics,
    format_balmorel_flows,
    load_entsoe_flows,
    observed_flow_limits,
)
from pybalmorel.backcasting.pricelevel import deflator, eur_per_usd, to_price_year
from pybalmorel.entsoe import (
    find_transmission_file,
    neighbour_pairs,
    parse_transmission_filename,
    transmission_files,
    zone_eic_code,
)
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


def test_split_yahoo_ttf_html_round_trips_through_loader(tmp_path):
    def row(*cells):
        tds = "".join(f'<td class="yf">{cell}</td>' for cell in cells)
        return f'<tr class="yf">{tds}  </tr>'

    html = (
        "<tbody>"
        + row("Jan 2, 2025", "50.0", "51.0", "49.0", "50.4", "50.4", "1,153")
        + row("Dec 31, 2024", "48.0", "48.5", "47.0", "36.0", "36.0", "-")
        + row("Dec 30, 2024", "48.3", "48.3", "47.2", "47.6", "47.6", "212")
        + '<tr><td>Jan 2, 2024</td><td colspan="6">0.5 Dividend</td></tr>'
        + "</tbody>"
    )
    html_path = tmp_path / "ttf.html"
    html_path.write_text(html)

    written = split_yahoo_ttf_html(html_path, tmp_path)

    assert [path.name for path in written] == [
        "natural_gas_TTF_2024.csv",
        "natural_gas_TTF_2025.csv",
    ]
    df = pd.read_csv(tmp_path / "natural_gas_TTF_2024.csv")
    assert list(df["Date"]) == ["Dec 31", "Dec 30"]
    assert pd.read_csv(tmp_path / "natural_gas_TTF_2025.csv")["Volume"].item() == 1153

    prices = load_ttf_gas_prices(tmp_path / "natural_gas_TTF_2024.csv", 2024)
    assert prices[pd.Timestamp("2024-12-31")] == pytest.approx(36.0 / 3.6)


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
        ("2023_DK_1-NO_2_crossborder_flows.csv", ("DK_1", "NO_2")),
        ("2023_AT-IT_NORD_crossborder_flows.csv", ("AT", "IT_NORD")),
        ("2024_FR-ES_crossborder_flows.csv", None),
    ],
)
def test_parse_transmission_filename(file_name, expected):
    assert parse_transmission_filename(file_name, 2023) == expected


@pytest.mark.parametrize(
    "spellings, region",
    [
        (["DK1", "DK_1", "10YDK-1--------W"], "DK1"),
        (["UK", "GB", "10YGB----------A"], "UK"),
        (["NO2", "NO_2", "10YNO-2--------T"], "NO2"),
        (["IT-NORD", "IT_NORD", "10Y1001A1001A73I"], "IT"),
        (["DE", "DE_LU"], "DE"),
        (["FR"], "FR"),
    ],
)
def test_zone_spellings_agree(spellings, region):
    assert len({zone_eic_code(zone) for zone in spellings}) == 1
    assert {canonical_region(zone) for zone in spellings} == {region}


def test_transmission_files_found_under_any_spelling(tmp_path):
    # The same DK1 -> DE border fetched under both spellings
    _write_flow_csv(tmp_path, "2023_DK_1-DE_LU_crossborder_flows.csv", [100.0] * 4)
    _write_flow_csv(tmp_path, "2023_10YDK-1--------W-DE_LU_crossborder_flows.csv", [100.0] * 4)
    _write_flow_csv(tmp_path, "2023_NO_2-DK_1_crossborder_flows.csv", [50.0] * 4)

    assert len(transmission_files(tmp_path, 2023)) == 2
    assert find_transmission_file(tmp_path, 2023, "10YNO-2--------T", "10YDK-1--------W") == (
        tmp_path / "2023_NO_2-DK_1_crossborder_flows.csv"
    )
    assert find_transmission_file(tmp_path, 2023, "DK_1", "NO_2") is None

    # Read once, not summed twice
    flows = load_entsoe_flows(tmp_path, 2023)
    assert flows.query("From == 'DK1' and To == 'DE'")["Value"].tolist() == [100.0]
    # A constant series, so every percentile is 100
    assert observed_flow_limits(tmp_path, 2023)[("DK1", "DE")] == 100.0


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

    limits = observed_flow_limits(tmp_path, 2023)
    assert limits[("IT", "CH")] == pytest.approx(149.6)  # 99th percentile of [150, 110]
    assert observed_flow_limits(tmp_path, 2023, percentile=100)[("IT", "CH")] == 150.0

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


def test_flow_limit_sums_pairs_before_the_percentile(tmp_path):
    # Two Italian sub-zones into CH peaking in different hours
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A73I-CH_crossborder_flows.csv", [100.0, 0.0], freq="h")
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A70O-CH_crossborder_flows.csv", [0.0, 100.0], freq="h")

    # The old sum of per-file maxima gave 200
    assert observed_flow_limits(tmp_path, 2023, percentile=100)[("IT", "CH")] == 100.0


def test_flow_limit_percentile_100_is_the_maximum(tmp_path):
    values = list(np.linspace(0.0, 500.0, 50))
    _write_flow_csv(tmp_path, "2023_FR-ES_crossborder_flows.csv", values, freq="h")

    assert observed_flow_limits(tmp_path, 2023, percentile=100)[("FR", "ES")] == 500.0
    assert observed_flow_limits(tmp_path, 2023)[("FR", "ES")] < 500.0


def test_flow_limit_of_rare_and_absent_directions(tmp_path):
    # Flows in 3 hours out of 200 in one direction, never in the other
    _write_flow_csv(tmp_path, "2023_SE_3-SE_2_crossborder_flows.csv", [0.0] * 197 + [1000.0, 1200.0, 1500.0], freq="h")
    _write_flow_csv(tmp_path, "2023_SE_2-SE_3_crossborder_flows.csv", [0.0] * 200, freq="h")

    limits = observed_flow_limits(tmp_path, 2023)
    assert limits[("SE3", "SE2")] == pytest.approx(1494.0)  # not closed
    assert limits[("SE2", "SE3")] == 0.0


def test_overrides_split_the_canonical_limit(tmp_path, monkeypatch):
    import pybalmorel.backcasting.flows as flows_module

    monkeypatch.setattr(
        flows_module,
        "get_current_borders",
        lambda *args: pd.DataFrame(
            {
                "RegionFrom": ["BE", "BE", "IT-NORD"],
                "RegionTo": ["DE4-S", "DE4-W", "CH"],
            }
        ),
    )
    monkeypatch.setattr(flows_module, "fetch_annual_transmission_data", lambda *args: None)
    _write_flow_csv(tmp_path, "2023_BE-DE_LU_crossborder_flows.csv", [800.0] * 4, freq="h")
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A73I-CH_crossborder_flows.csv", [300.0] * 4, freq="h")

    overrides, failed_pairs = compute_entsoe_transmission_overrides("balmorel", "backcast", 2023, tmp_path, "key")

    values = overrides.set_index(["RegionFrom", "RegionTo"])["Value"]
    assert values[("BE", "DE4-S")] == 400.0
    assert values[("BE", "DE4-W")] == 400.0
    assert values[("IT-NORD", "CH")] == 300.0
    assert ("10Y1001A1001A70O", "CH") in failed_pairs
    assert ("BE", "DE_LU") not in failed_pairs


def test_fetch_transmission_remembers_no_data_and_survives_timeouts(tmp_path, monkeypatch):
    import requests
    from entsoe.exceptions import NoMatchingDataError
    import pybalmorel.entsoe as entsoe_module

    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def query_crossborder_flows(self, region_from, region_to, start, end):
            calls.append((region_from, region_to))
            if region_from == "FR":
                raise NoMatchingDataError
            if region_from == "DK_1":
                raise requests.exceptions.ReadTimeout
            return pd.Series([1.0], index=[start])

    monkeypatch.setattr(entsoe_module, "EntsoePandasClient", FakeClient)
    pairs = [("FR", "LU"), ("DK_1", "NO_2"), ("NO_2", "DK_1")]

    entsoe_module.fetch_annual_transmission_data("crossborder_flows", pairs, 2023, tmp_path, "key")
    assert len(calls) == 3

    # Second run: the no-data pair and the fetched pair are skipped, the timed out one retried
    calls.clear()
    entsoe_module.fetch_annual_transmission_data("crossborder_flows", pairs, 2023, tmp_path, "key")
    assert calls == [("DK_1", "NO_2")]


# %% ------------------------------- ###
###        6. ENTSO-E Download      ###
### ------------------------------- ###


def _write_series_csv(path, file_name, year, values):
    index = pd.date_range(f"{year}-01-02 00:00", periods=len(values), freq="h", tz="Europe/Brussels")
    pd.Series(values, index=index).to_csv(path / file_name)


def test_load_entsoe_data_reads_only_requested_year(tmp_path):
    from pybalmorel.backcasting.__main__ import load_entsoe_data

    _write_series_csv(tmp_path, "2023_FR_load.csv", 2023, [1.0, 2.0])
    _write_series_csv(tmp_path, "2023_10YDK-1--------W_load.csv", 2023, [3.0, 4.0])
    # Another year's file, which used to be read and mangled to region '4_FR'
    _write_series_csv(tmp_path, "2024_FR_load.csv", 2024, [9.0, 9.0])
    _write_series_csv(tmp_path, "2023_FR_day_ahead_prices.csv", 2023, [50.0, 60.0])

    with pytest.warns(Warning, match="No ENTSO-E generation files for 2023"):
        load, prices, generation = load_entsoe_data(str(tmp_path), 2023)

    assert set(load.Region) == {"FR", "DK1"}
    assert load.Time.dt.year.unique().tolist() == [2023]
    assert prices.Value.tolist() == [50.0, 60.0]
    assert generation.empty


def test_generation_ignores_actual_consumption(tmp_path):
    from pybalmorel.backcasting.__main__ import entsoe_to_category, format_entsoe_data

    # ENTSO-E two-row header; in the second hour pumped storage only reports pumping
    (tmp_path / "2023_FR_generation.csv").write_text(
        ",Hydro Pumped Storage,Hydro Pumped Storage,Nuclear\n"
        ",Actual Aggregated,Actual Consumption,Actual Aggregated\n"
        "2023-01-02 00:00:00+01:00,100.0,0.0,500.0\n"
        "2023-01-02 01:00:00+01:00,,80.0,500.0\n"
    )
    file_path = tmp_path / "2023_FR_generation.csv"

    generation = format_entsoe_data(pd.read_csv(file_path), "h", file_path, 2023, "generation")

    assert generation["Hydro Pumped Storage"].fillna(0).tolist() == [100.0, 0.0]
    assert generation["Nuclear"].tolist() == [500.0, 500.0]
    assert entsoe_to_category["Hydro Pumped Storage"] == "Storage"


def test_neighbour_pairs_are_symmetric_and_include_missing_borders():
    pairs = neighbour_pairs(["FR", "BE", "10YDK-1--------W", "DE_LU", "GR", "10Y1001A1001A788", "XK", "AL"])

    assert all((to, frm) in pairs for frm, to in pairs)
    assert ("FR", "BE") in pairs
    # Saved under the spelling transmission-flow-limit looks up
    assert ("10YDK-1--------W", "DE_LU") in pairs
    # Missing from entsoe-py's NEIGHBOURS
    assert ("GR", "10Y1001A1001A788") in pairs
    assert ("XK", "AL") in pairs
    # Not neighbours
    assert ("FR", "GR") not in pairs


@pytest.mark.parametrize(
    "args, expected",
    [
        ([], ["load", "day_ahead_prices", "generation", "crossborder_flows"]),
        (["--query", "load", "--query", "crossborder_flows"], ["load", "crossborder_flows"]),
        (
            ["--query", "installed_generation_capacity", "--query", "unavailability_of_generation_units"],
            ["installed_generation_capacity", "unavailability_of_generation_units"],
        ),
    ],
)
def test_download_command(tmp_path, monkeypatch, args, expected):
    from click.testing import CliRunner
    import pybalmorel.entsoe as entsoe_module
    from pybalmorel.backcasting.__main__ import main

    calls = []
    monkeypatch.setattr(entsoe_module, "get_api_key", lambda: "key")
    monkeypatch.setattr(
        entsoe_module,
        "fetch_annual_data",
        lambda query, year, zones, path, api_key: calls.append((query, year)),
    )
    monkeypatch.setattr(
        entsoe_module,
        "fetch_annual_transmission_data",
        lambda query, pairs, year, path, api_key: calls.append((query, year)),
    )

    data_path = tmp_path / "entsoedata"
    result = CliRunner().invoke(main, ["download", str(data_path), "2023", *args])

    assert result.exit_code == 0, result.output
    assert calls == [(query, 2023) for query in expected]
    assert data_path.is_dir()


def test_fetch_annual_data_remembers_no_data_and_survives_timeouts(tmp_path, monkeypatch):
    import requests
    from entsoe.exceptions import NoMatchingDataError
    import pybalmorel.entsoe as entsoe_module

    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def query_load(self, zone, start, end):
            calls.append(zone)
            if zone == "XK":
                raise NoMatchingDataError
            if zone == "AL":
                raise requests.exceptions.ReadTimeout
            return pd.Series([1.0], index=[start])

    monkeypatch.setattr(entsoe_module, "EntsoePandasClient", FakeClient)
    zones = ["FR", "XK", "AL"]

    entsoe_module.fetch_annual_data("load", 2023, zones, tmp_path, "key")
    assert calls == zones
    assert (tmp_path / "2023_load_nodata.txt").read_text() == "XK\n"

    # Second run: the no-data zone and the fetched zone are skipped, the timed out one retried
    calls.clear()
    entsoe_module.fetch_annual_data("load", 2023, zones, tmp_path, "key")
    assert calls == ["AL"]


# %% ------------------------------- ###
###     7. Nuclear Availability     ###
### ------------------------------- ###

NUCLEAR, NATGAS = 3.94e303, 3.95e303


def _nuclear_inputs():
    gkfx = pd.DataFrame(
        {
            "YYY": ["2023", "2023", "2023", "2023", "2022"],
            "AAA": ["DE4-S_A", "DE4-W_A", "DE4-S_A", "FR_A", "FR_A"],
            "GGG": ["NUCL_1", "NUCL_1", "GAS_NUCL_NAMED", "NUCL_1", "NUCL_1"],
            "Value": [600.0, 400.0, 999.0, 100.0, 5000.0],
        }
    )
    gdata = pd.DataFrame(
        {
            "GGG": ["NUCL_1", "NUCL_1", "GAS_NUCL_NAMED"],
            "GDATASET": ["GDFUEL", "GDTYPE", "GDFUEL"],
            "Value": [NUCLEAR, 2.2e303, NATGAS],
        }
    )
    fdata = pd.DataFrame(
        {
            "FFF": ["NUCLEAR", "NATGAS"],
            "FDATASET": ["FDACRONYM", "FDACRONYM"],
            "Value": [NUCLEAR, NATGAS],
        }
    )
    rrraaa = pd.DataFrame({"RRR": ["DE4-S", "DE4-W", "FR"], "AAA": ["DE4-S_A", "DE4-W_A", "FR_A"]})
    return gkfx, gdata, fdata, rrraaa


def _weekly_series(weekly_values: list[float], year: int = 2023) -> pd.Series:
    hours = backcast_hours(year)
    return pd.Series(np.repeat(weekly_values, 168), index=hours)


def test_nuclear_capacity_found_by_fuel_acronym():
    from pybalmorel.backcasting.nuclear import nuclear_capacity

    capacity = nuclear_capacity(*_nuclear_inputs(), 2023)

    # The gas technology named like nuclear and the 2022 capacity are ignored
    assert set(capacity.Technology) == {"NUCL_1"}
    assert capacity.groupby("Region").Capacity.sum().to_dict() == {"DE": 1000.0, "FR": 100.0}


def test_nuclear_ratings_and_override(tmp_path):
    from pybalmorel.backcasting.nuclear import nuclear_capacity, nuclear_ratings, write_gkrate_override

    capacity = nuclear_capacity(*_nuclear_inputs(), 2023)
    # DE: at capacity, above it, zero, then no data; the rest at half
    de = _weekly_series([1000.0, 1200.0, 0.0, np.nan] + [500.0] * 48)
    observed = {"DE": de, "BE": _weekly_series([100.0] * 52)}

    with pytest.warns(Warning) as record:
        ratings = nuclear_ratings(observed, capacity, 2023)
    messages = " ".join(str(warning.message) for warning in record)
    assert "FR has 100 MW of nuclear GKFX but no ENTSO-E nuclear output" in messages
    assert "BE has 0.87 TWh of ENTSO-E nuclear output" in messages
    assert "above its GKFX of 1000 MW in 1 week(s)" in messages
    assert "week(s) ['S04']" in messages

    assert list(ratings.columns) == ["DE"]
    assert ratings.loc[["S01", "S02", "S03", "S05"], "DE"].tolist() == [1.0, 1.0, 0.0, 0.5]

    # Both DE areas share the rating, computed against their summed GKFX
    content = write_gkrate_override(ratings, capacity, tmp_path).body
    assert "GKRATE('DE4-S_A','NUCL_1','S03')=eps;" in content
    assert "GKRATE('DE4-W_A','NUCL_1','S05')=0.5000;" in content
    assert "=0;" not in content
    assert "'S04'" not in content
    assert "FR_A" not in content
    assert (tmp_path / "GKRATE_ENTSOE.inc").exists()


def test_nuclear_weeks_after_the_series_ends_are_a_closure(tmp_path):
    from pybalmorel.backcasting.nuclear import nuclear_capacity, nuclear_ratings, write_gkrate_override

    capacity = nuclear_capacity(*_nuclear_inputs(), 2023)
    # DE: a gap in S02, data until S15, then nothing
    de = _weekly_series([600.0, np.nan] + [700.0] * 13 + [np.nan] * 37)
    fr = _weekly_series([50.0] * 52)

    with pytest.warns(Warning) as record:
        ratings = nuclear_ratings({"DE": de, "FR": fr}, capacity, 2023)
    messages = " ".join(str(warning.message) for warning in record)
    assert "CLOSURE: DE" in messages and "S16-S52" in messages
    assert "6.22 TWh" in messages  # 1000 MW x 168 h x 37 weeks
    assert "week(s) ['S02']" in messages

    content = write_gkrate_override(ratings, capacity, tmp_path).body
    assert "GKRATE('DE4-S_A','NUCL_1','S16')=eps;" in content
    assert "GKRATE('DE4-W_A','NUCL_1','S52')=eps;" in content
    assert "GKRATE('DE4-S_A','NUCL_1','S02')" not in content


def test_stale_input_cache_warns(tmp_path):
    import os

    from pybalmorel.backcasting.nuclear import check_input_cache

    input_gdx = tmp_path / "backcast_input_data.gdx"
    input_gdx.write_text("")
    data = tmp_path / "data"
    data.mkdir()
    (data / "GKFX.inc").write_text("")
    (data / "OLD.inc").write_text("")
    os.utime(input_gdx, (1_000_000, 1_000_000))
    os.utime(data / "OLD.inc", (0, 0))

    with pytest.warns(Warning, match="older than GKFX.inc in") as record:
        check_input_cache(input_gdx, data)
    assert "OLD.inc" not in str(record[0].message)


def test_tiny_nuclear_rating_is_eps():
    from pybalmorel.backcasting.nuclear import format_rating

    assert format_rating(0.00001) == "eps"
    assert format_rating(1.0) == "1.0000"


# %% ------------------------------- ###
###     8. Generation categories    ###
### ------------------------------- ###

# PSR types that are grid assets, not production types
GRID_ASSET_TYPES = {"AC Link", "DC Link", "Substation", "Transformer"}


def test_every_entsoe_production_type_has_a_category():
    from entsoe.mappings import PSRTYPE_MAPPINGS

    from pybalmorel.backcasting.__main__ import entsoe_to_category

    production_types = {
        name for code, name in PSRTYPE_MAPPINGS.items() if code.startswith("B")
    } - GRID_ASSET_TYPES

    assert "Hydro Run-of-river and pondage" in production_types
    assert production_types - entsoe_to_category.keys() == set()


def test_older_run_of_river_spelling_is_still_hydro():
    # Files fetched with older entsoe-py versions spell it "poundage"
    from pybalmorel.backcasting.__main__ import entsoe_to_category

    assert entsoe_to_category["Hydro Run-of-river and poundage"] == "Hydro"
    assert entsoe_to_category["Hydro Run-of-river and pondage"] == "Hydro"


def test_oil_shale_has_the_same_category_on_both_sides():
    from pybalmorel.backcasting.__main__ import balmorel_to_category, entsoe_to_category

    assert entsoe_to_category["Fossil Oil shale"] == "Fossil Solid"
    assert balmorel_to_category["CHP-EXTRACTION - SHALE"] == "Fossil Solid"
    assert balmorel_to_category["CONDENSING - SHALE"] == "Fossil Solid"


def _generation_frame():
    time = pd.date_range("2023-01-02", periods=2, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "Region": ["EE"] * 4,
            "Technology": ["Wind Onshore", "Wind Onshore", "Fossil Mystery", "Fossil Mystery"],
            "Time": list(time) * 2,
            "Value": [100.0, 200.0, 1.5e6, 0.5e6],
        }
    )


def test_unmapped_technology_raises_with_its_energy():
    from pybalmorel.backcasting.__main__ import entsoe_to_category, map_technology_categories

    with pytest.raises(ValueError, match=r"'Fossil Mystery' \(2.00 TWh\)"):
        map_technology_categories(_generation_frame(), entsoe_to_category, "ENTSO-E")


def test_unmapped_technology_is_kept_as_unmapped():
    from pybalmorel.backcasting.__main__ import (
        UNMAPPED_CATEGORY,
        entsoe_to_category,
        map_technology_categories,
    )

    with pytest.warns(Warning, match="Fossil Mystery"):
        generation = map_technology_categories(
            _generation_frame(), entsoe_to_category, "ENTSO-E", allow_unmapped=True
        )

    totals = generation.groupby("Technology")["Value"].sum()
    assert totals.to_dict() == {UNMAPPED_CATEGORY: 2e6, "Wind": 300.0}


# %% ------------------------------- ###
###   9. Observed demand profiles   ###
### ------------------------------- ###


def test_grid_to_profile_keeps_labels_order_and_missing_hours():
    from pybalmorel.backcasting.calendar import SEASONS, TERMS
    from pybalmorel.backcasting.demand import grid_to_profile

    hourly = pd.Series(range(8736), index=backcast_hours(2023), dtype=float)
    hourly.iloc[5] = np.nan

    profile = grid_to_profile(to_backcast_grid(hourly, 2023))

    assert len(profile) == 8736
    assert profile.index[0] == ("S01", "T001")
    assert profile.index[-1] == ("S52", "T168")
    assert profile[("S02", "T001")] == 168.0
    assert np.isnan(profile[("S01", "T006")])
    assert list(profile.index.get_level_values(0).unique()) == SEASONS
    assert list(profile.index.get_level_values(1).unique()) == TERMS


def test_zones_are_summed_and_a_missing_hour_is_missing_for_the_region():
    from pybalmorel.backcasting.demand import sum_zones

    time = pd.date_range("2023-01-02", periods=3, freq="h", tz="UTC")
    zones = pd.DataFrame(
        {
            "IT-NORD": [10.0, 10.0, 10.0],
            "IT-SUD": [5.0, np.nan, 5.0],
            "DK1": [1.0, 2.0, 3.0],
        },
        index=time,
    )

    regions = sum_zones(zones)

    assert set(regions.columns) == {"IT", "DK1"}
    assert regions["IT"].iloc[0] == 15.0
    assert np.isnan(regions["IT"].iloc[1])
    assert regions["DK1"].tolist() == [1.0, 2.0, 3.0]


def test_clean_profile_interpolates_implausible_and_missing_hours():
    from pybalmorel.backcasting.demand import clean_profile

    profile = pd.Series([100.0, 100.0, 1000.0, np.nan, 100.0, 10.0, 100.0])

    cleaned, n_implausible = clean_profile(profile)

    assert n_implausible == 3
    assert cleaned.tolist() == [100.0] * 7


def test_clean_profile_rejects_a_negative_profile():
    from pybalmorel.backcasting.demand import clean_profile

    _, n_implausible = clean_profile(pd.Series([-1e13, -5.0, -3.0, 2.0]))

    assert n_implausible == 4


def _flat_hourly(value: float, year: int = 2023) -> pd.Series:
    return pd.Series(value, index=backcast_hours(year))


def test_demand_profiles_use_entsoe_and_fall_back_above_the_threshold():
    from pybalmorel.backcasting.demand import (
        MAX_IMPLAUSIBLE_SHARE,
        current_profiles,
        demand_profiles,
    )
    from pybalmorel.backcasting.calendar import backcast_calendar

    # Just at the threshold for DK1, one hour above it for NL
    n_allowed = int(MAX_IMPLAUSIBLE_SHARE * 8736)
    dk1 = _flat_hourly(100.0)
    dk1.iloc[:n_allowed] = np.nan
    nl = _flat_hourly(200.0)
    nl.iloc[: n_allowed + 1] = 1e6
    observed = pd.DataFrame({"DK1": dk1, "NL": nl, "DE": _flat_hourly(300.0)})

    calendar = backcast_calendar(2023)
    de_var_t = pd.concat(
        [
            pd.DataFrame(
                {
                    "Scenario": "backcast",
                    "RRR": region,
                    "DEUSER": "OTHER",
                    "SSS": calendar.Season,
                    "TTT": calendar.Term,
                    "Value": value,
                }
            )
            for region, value in (("NL", 7.0), ("AL", 9.0), ("LV", -1.0))
        ]
    )

    with pytest.warns(Warning, match="LV keeps its current demand profile unchanged"):
        profiles, report = demand_profiles(
            ["DK1", "NL", "DE4-E", "AL", "LV", "MT"], observed, current_profiles(de_var_t), 2023
        )

    assert set(profiles) == {"DK1", "NL", "DE4-E", "AL"}
    assert (profiles["DK1"] == 100.0).all()
    assert (profiles["NL"] == 7.0).all()
    assert (profiles["DE4-E"] == 300.0).all()
    assert (profiles["AL"] == 9.0).all()
    assert f"DK1: ENTSO-E DK1, {n_allowed} hours interpolated" in report
    assert any(line.startswith("NL: input data") and "ENTSO-E NL has" in line for line in report)
    assert "MT: no ENTSO-E load or input profile, keeps its current profile" in report


def test_write_de_var_t_override(tmp_path):
    from pybalmorel.backcasting.demand import grid_to_profile, write_de_var_t_override

    profile = grid_to_profile(to_backcast_grid(_flat_hourly(123.456), 2023))

    write_de_var_t_override({"DK1": profile}, ["DK1: ENTSO-E DK1, 0 hours interpolated"], 2023, tmp_path)

    lines = (tmp_path / "DE_VAR_T_ENTSOE.inc").read_text().splitlines()
    assert "* DK1: ENTSO-E DK1, 0 hours interpolated" in lines
    assert "DE_VAR_T('DK1','OTHER','S01','T001')=123.46;" in lines
    assert "DE_VAR_T('DK1','RESE',SSS,TTT)=DE_VAR_T('DK1','OTHER',SSS,TTT);" in lines
    assert sum(line.startswith("DE_VAR_T('DK1','OTHER'") for line in lines) == 8736


def test_de_var_t_include_is_appended_once(tmp_path):
    from pybalmorel.backcasting.demand import DE_VAR_T_INCLUDE, append_de_var_t_include

    de_var_t = tmp_path / "DE_VAR_T.inc"
    de_var_t.write_text("$include '../../base/data/DE_VAR_T.inc';\nDE_VAR_T('DK1', 'OTHER', 'S01', 'T001') = 1;")

    append_de_var_t_include(de_var_t)
    append_de_var_t_include(de_var_t)

    content = de_var_t.read_text()
    assert content.count(DE_VAR_T_INCLUDE) == 1
    assert content.endswith(DE_VAR_T_INCLUDE + "\n")
    assert "= 1;\n" in content


def test_de_var_t_include_creates_a_missing_file_on_base(tmp_path):
    from pybalmorel.backcasting.demand import DE_VAR_T_INCLUDE, append_de_var_t_include

    de_var_t = tmp_path / "DE_VAR_T.inc"
    append_de_var_t_include(de_var_t)

    lines = de_var_t.read_text().splitlines()
    assert lines[0] == "$include '../../base/data/DE_VAR_T.inc';"
    assert lines[-1] == DE_VAR_T_INCLUDE


def test_load_observed_load_reads_zones(tmp_path):
    from pybalmorel.backcasting.__main__ import load_observed_load

    _write_series_csv(tmp_path, "2023_IT-NORD_load.csv", 2023, [1.0, 2.0])
    _write_series_csv(tmp_path, "2023_10YDK-1--------W_load.csv", 2023, [3.0, 4.0])

    zones = load_observed_load(str(tmp_path), 2023)

    assert set(zones.columns) == {"IT-NORD", "DK1"}
    assert str(zones.index.tz) == "UTC"


# %% ------------------------------- ###
### 10. Comparison on the full grid ###
### ------------------------------- ###


def _hours(n: int, year: int = 2023) -> pd.DatetimeIndex:
    return backcast_hours(year)[:n]


def _long(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Region", "Technology", "Time", "Value"])


def test_generation_join_fills_balmorel_zeros_and_drops_hours_without_entsoe():
    from pybalmorel.backcasting.__main__ import join_generation

    h0, h1, h2 = _hours(3)
    entsoe = _long(
        [
            ("DE", "Biomass & Bioenergy", h0, 5000.0),
            ("DE", "Nuclear", h0, 3000.0),
            ("DE", "Nuclear", h1, 3000.0),
            # Only in ENTSO-E: dropped as Balmorel doesn't have the region
            ("NO1", "Hydro", h0, 100.0),
        ]
    )
    balmorel = _long(
        [
            ("DE", "Nuclear", h0, 2500.0),
            ("DE", "Wind", h1, 700.0),
            # No ENTSO-E generation for DE in h2 at all: dropped on both sides
            ("DE", "Wind", h2, 900.0),
        ]
    )

    generation = join_generation(entsoe, balmorel, {"DE"}, 2023)

    assert generation.loc[("DE", "Biomass & Bioenergy", h0)].tolist() == [5000.0, 0.0]
    assert generation.loc[("DE", "Wind", h1)].tolist() == [0.0, 700.0]
    assert h2 not in generation.index.get_level_values("Time")
    # Sums equal each input over the common regions and the hours both have
    assert generation["ENTSOE"].sum() == 11000.0
    assert generation["BALMOREL"].sum() == 3200.0


def test_generation_join_leaves_out_hours_outside_the_backcast_calendar():
    from pybalmorel.backcasting.__main__ import join_generation

    before = backcast_hours(2023)[0] - pd.Timedelta(hours=1)
    entsoe = _long([("DE", "Nuclear", before, 3000.0), ("DE", "Nuclear", _hours(1)[0], 3000.0)])
    balmorel = _long([("DE", "Nuclear", _hours(1)[0], 2000.0)])

    generation = join_generation(entsoe, balmorel, {"DE"}, 2023)

    assert len(generation) == 1


def test_hourly_join_warns_about_regions_with_missing_hours():
    from pybalmorel.backcasting.__main__ import join_hourly

    hours = backcast_hours(2023)
    entsoe = pd.DataFrame({"Region": "FR", "Time": hours, "Value": 1.0})
    balmorel = pd.DataFrame({"Region": "FR", "Time": hours[:-10], "Value": 2.0})

    with pytest.warns(Warning, match="Balmorel load of FR has 8726 of the 8736 hours"):
        loads = join_hourly(entsoe, balmorel, 2023, "load")

    assert len(loads) == 8726
    assert loads.columns.tolist() == ["ENTSOE", "BALMOREL"]


def test_balmorel_prices_are_converted_to_the_backcast_year():
    from pybalmorel.backcasting.__main__ import balmorel_prices_in_year

    prices = pd.DataFrame({"Region": ["DE"], "Value": [100.0]})

    assert balmorel_prices_in_year(prices, 2023)["Value"].iloc[0] == pytest.approx(122.87, abs=0.01)
    assert prices["Value"].iloc[0] == 100.0


def _write_balmorel_cache(scenario_path, year: int = 2023) -> None:
    cache = scenario_path / "backcastoutput"
    cache.mkdir(parents=True)
    st = {"Year": year, "Season": "S01", "Time": "T001"}
    pd.DataFrame([{**st, "Region": "DE4-E", "Value": 100.0}]).to_csv(
        cache / "balmorel_prices.csv", index=False
    )
    pd.DataFrame(
        [
            {**st, "Region": "DE4-E", "Category": "EXOGENOUS", "Value": 1000.0},
            {**st, "Region": "DE4-E", "Category": "ENDO_INTRASTO", "Value": 200.0},
        ]
    ).to_csv(cache / "balmorel_load.csv", index=False)
    pd.DataFrame(
        [{**st, "Region": "DE4-E", "Technology": "CONDENSING", "Fuel": "NUCLEAR", "Value": 900.0}]
    ).to_csv(cache / "balmorel_generation.csv", index=False)
    pd.DataFrame([{**st, "From": "DE4-E", "To": "DK1", "Value": 10.0}]).to_csv(
        cache / "balmorel_flows.csv", index=False
    )


def test_balmorel_load_leaves_out_storage_charging_and_prices_are_nominal(tmp_path):
    from pybalmorel.backcasting.__main__ import get_and_format_balmorel, load_components_table

    _write_balmorel_cache(tmp_path)
    cached_prices = (tmp_path / "backcastoutput" / "balmorel_prices.csv").read_text()

    load, prices, *_, components = get_and_format_balmorel("sc", str(tmp_path), 2023, "mean", False)

    assert load.Value.tolist() == [1000.0]
    assert prices.Value.iloc[0] == pytest.approx(122.87, abs=0.01)
    assert (tmp_path / "backcastoutput" / "balmorel_prices.csv").read_text() == cached_prices

    entsoe_load = pd.DataFrame({"Region": "DE", "Time": _hours(1), "Value": 1100.0})
    table = load_components_table(components, entsoe_load, 2023).set_index("Category")
    assert table.loc["ENDO_INTRASTO", "Excluded"]
    assert table.loc["ENDO_INTRASTO", "BALMOREL"] == pytest.approx(200.0 / 1e6)
    assert table.loc["Total compared", "BALMOREL"] == pytest.approx(1000.0 / 1e6)
    assert table.loc["Total compared", "ENTSOE"] == pytest.approx(1100.0 / 1e6)


def test_storage_and_flexibility_is_split():
    from pybalmorel.backcasting.__main__ import balmorel_to_category, colors, entsoe_to_category

    categories = set(balmorel_to_category.values()) | set(entsoe_to_category.values())
    assert "Storage & Flexibility" not in categories
    assert categories <= colors.keys()
    assert entsoe_to_category["Other"] == "Other"
    assert entsoe_to_category["Geothermal"] == "Other renewable"
    assert balmorel_to_category["INTRASEASONAL-ELECT-STORAGE - ELECTRIC"] == "Storage"
    assert balmorel_to_category["CONDENSING - DUMMY"] == "Backup"


def test_price_duration_plot_has_a_panel_per_region():
    import matplotlib

    matplotlib.use("Agg")
    from pybalmorel.backcasting.__main__ import plot_price_duration_curves

    rng = np.random.default_rng(0)
    prices = pd.concat(
        pd.DataFrame(
            {"Region": region, "ENTSOE": rng.normal(90, 50, 100), "BALMOREL": rng.normal(90, 25, 100)}
        )
        for region in ["XX", "FR", "DE"]
    )

    fig, axes = plot_price_duration_curves(prices, "test")

    assert [ax.get_title(loc="left") for ax in axes[1:]] == ["DE", "FR", "XX"]
    assert all(ax.get_ylim() == (-60, 320) for ax in axes)


# %% ------------------------------- ###
###    11. Thermal availability     ###
### ------------------------------- ###

ACRONYMS = {
    "GCND": 224, "GBPR": 225, "GEXT": 226, "GSOLE": 236, "GSOLH": 237, "GWND": 238,
    "COAL": 396, "LIGNITE": 397, "NATGAS": 395, "SUN": 400, "HYDROGEN": 401, "WIND": 402,
}


def _thermal_inputs(fuels: dict[str, tuple[str, str]], gkfx: list[tuple[str, str, float]]):
    """GKFX, GDATA, RRRAAA and acronym names for technologies {name: (type, fuel)} at [(area, technology, MW)]."""
    from pybalmorel.backcasting.thermal import ACRONYM_SCALE

    names = {index * ACRONYM_SCALE: name for name, index in ACRONYMS.items()}
    gdata = pd.DataFrame(
        [
            (technology, parameter, ACRONYMS[value] * ACRONYM_SCALE)
            for technology, (technology_type, fuel) in fuels.items()
            for parameter, value in (("GDTYPE", technology_type), ("GDFUEL", fuel))
        ],
        columns=["GGG", "GDATASET", "Value"],
    )
    gkfx = pd.DataFrame(
        [("2023", area, technology, mw) for area, technology, mw in gkfx],
        columns=["YYY", "AAA", "GGG", "Value"],
    )
    areas = sorted(set(gkfx["AAA"]))
    rrraaa = pd.DataFrame({"RRR": [area.removesuffix("_A") for area in areas], "AAA": areas})
    return gkfx, gdata, rrraaa, names


def _outage(mrid, revision, start, end, nominal=500.0, available=0.0, docstatus="Active", kind="Unplanned outage"):
    return {
        "mrid": mrid,
        "revision": revision,
        "docstatus": docstatus,
        "businesstype": kind,
        "plant_type": "Fossil Hard coal",
        "nominal_power": nominal,
        "avail_qty": available,
        "start": start,
        "end": end,
        "Region": "DE",
    }


def _coal_capacity(mw: float = 1000.0):
    from pybalmorel.backcasting.thermal import group_capacity

    return group_capacity(
        *_thermal_inputs({"COAL_CND": ("GCND", "COAL")}, [("DE4-S_A", "COAL_CND", mw)]), 2023
    )


def test_thermal_groups_are_selected_by_acronym_name():
    from pybalmorel.backcasting.thermal import group_capacity

    inputs = _thermal_inputs(
        {
            "COAL_CND": ("GCND", "COAL"),
            "LIG_EXT": ("GEXT", "LIGNITE"),
            "GAS_BPR": ("GBPR", "NATGAS"),
            "PV": ("GSOLE", "SUN"),
        },
        [("DE4-S_A", "COAL_CND", 600.0), ("DE4-W_A", "COAL_CND", 400.0), ("DE4-S_A", "LIG_EXT", 300.0),
         ("FR_A", "GAS_BPR", 200.0), ("FR_A", "PV", 50.0)],
    )

    capacity = group_capacity(*inputs, 2023)
    with_checks = group_capacity(*inputs, 2023, check_only=True)

    assert capacity.groupby(["Region", "Group"]).Capacity.sum().to_dict() == {
        ("DE", "HARDCOAL"): 1000.0, ("DE", "LIGNITE"): 300.0, ("FR", "GAS"): 200.0,
    }
    assert with_checks.query("Group == 'SOLAR'").Capacity.sum() == 50.0


def test_unmapped_thermal_fuel_stops():
    from pybalmorel.backcasting.thermal import group_capacity

    inputs = _thermal_inputs({"H2_CND": ("GCND", "HYDROGEN")}, [("DE4-S_A", "H2_CND", 100.0)])

    with pytest.raises(ValueError, match="HYDROGEN"):
        group_capacity(*inputs, 2023)


@pytest.mark.parametrize("installed, k", [(600.0, 0.6), (1500.0, 1.0)])
def test_installed_capacity_scales_and_caps_the_rating(installed, k):
    from pybalmorel.backcasting.thermal import thermal_ratings

    installed = pd.Series({("DE", "HARDCOAL"): installed})

    ratings = thermal_ratings(_coal_capacity(), installed, None)

    assert ratings["k"].unique().tolist() == [k]
    assert np.allclose(ratings["Rating"], k)


def test_outage_lowers_its_week_by_lost_hours():
    from pybalmorel.backcasting.thermal import latest_outages, thermal_ratings, weekly_outage_energy

    monday = first_monday(2023) + pd.Timedelta(weeks=1)
    outages = pd.DataFrame([_outage("a", 1, monday, monday + pd.Timedelta(days=2))])

    energy = weekly_outage_energy(latest_outages(outages), 2023)
    ratings = thermal_ratings(_coal_capacity(), pd.Series({("DE", "HARDCOAL"): 1000.0}), energy)

    u = 500 * 48 / (1000 * 168)
    week = ratings.set_index("Season")
    assert week.loc["S02", "Forced"] == pytest.approx(u)
    assert week.loc["S02", "Rating"] == pytest.approx(1 - u)
    assert week.drop("S02")["Rating"].eq(1).all()


def test_latest_revision_counts_once_and_withdrawn_events_count_nothing():
    from pybalmorel.backcasting.thermal import latest_outages, weekly_outage_energy

    monday = first_monday(2023)
    outages = pd.DataFrame(
        [
            _outage("a", 1, monday, monday + pd.Timedelta(days=4)),
            _outage("a", 2, monday, monday + pd.Timedelta(days=1)),
            _outage("b", 1, monday, monday + pd.Timedelta(days=7)),
            _outage("b", 2, monday, monday + pd.Timedelta(days=7), docstatus="Withdrawn"),
        ]
    )

    energy = weekly_outage_energy(latest_outages(outages), 2023)

    assert energy.loc[("DE", "HARDCOAL", "S01"), "Forced"] == 500 * 24


def test_outage_spanning_two_weeks_is_split_by_hours():
    from pybalmorel.backcasting.thermal import latest_outages, weekly_outage_energy

    sunday = first_monday(2023) + pd.Timedelta(days=6)
    outages = pd.DataFrame(
        [_outage("a", 1, sunday, sunday + pd.Timedelta(days=2), kind="Planned maintenance")]
    )

    energy = weekly_outage_energy(latest_outages(outages), 2023)

    assert energy["Planned"].to_dict() == {
        ("DE", "HARDCOAL", "S01"): 500 * 24, ("DE", "HARDCOAL", "S02"): 500 * 24,
    }
    assert energy["Forced"].eq(0).all()


def test_zero_thermal_rating_is_eps(tmp_path):
    from pybalmorel.backcasting.thermal import thermal_ratings, write_thermal_gkrate_override

    capacity = _coal_capacity()
    ratings = thermal_ratings(capacity, pd.Series({("DE", "HARDCOAL"): 0.0}), None)
    write_thermal_gkrate_override(ratings, capacity, tmp_path)

    text = (tmp_path / "GKRATE_THERMAL_ENTSOE.inc").read_text()
    assert "GKRATE('DE4-S_A','COAL_CND','S01')=eps;" in text
    assert "=0;" not in text
    assert text.count("GKRATE(") == 52


def test_group_without_installed_capacity_gets_no_rating():
    from pybalmorel.backcasting.thermal import thermal_ratings

    with pytest.warns(UserWarning, match="no ENTSO-E installed"):
        ratings = thermal_ratings(_coal_capacity(), pd.Series(dtype=float), None)

    assert ratings.empty


def test_installed_capacity_sums_zones_of_a_region(tmp_path):
    from pybalmorel.backcasting.thermal import group_installed, load_installed_capacity

    for zone, coal in (("IT_NORD", 1000.0), ("IT_SUD", 200.0)):
        pd.DataFrame(
            {"Fossil Hard coal": [coal], "Biomass": [50.0]},
            index=pd.DatetimeIndex(["2023-01-01 00:00+01:00"]),
        ).to_csv(tmp_path / f"2023_{zone}_installed_generation_capacity.csv")
    pd.DataFrame(
        {"Fossil Gas": [300.0]}, index=pd.DatetimeIndex(["2023-01-01 00:00+01:00"])
    ).to_csv(tmp_path / "2023_FR_installed_generation_capacity.csv")

    installed = group_installed(
        load_installed_capacity(tmp_path, 2023),
        {"HARDCOAL": ("Fossil Hard coal",), "GAS": ("Fossil Gas",)},
    )

    assert installed.to_dict() == {("FR", "GAS"): 300.0, ("IT", "HARDCOAL"): 1200.0}


# %% ------------------------------- ###
###       12. Must-run floor        ###
### ------------------------------- ###


def _weekly_hours(week: int = 0, year: int = 2023) -> pd.DatetimeIndex:
    return backcast_hours(year)[week * 168 : (week + 1) * 168]


def _one_week_output(gas: np.ndarray, biomass: np.ndarray) -> pd.DataFrame:
    hours = _weekly_hours()
    return pd.DataFrame({("DE", "GAS"): gas, ("DE", "BIOMASS"): biomass}, index=hours).rename_axis(
        columns=["Region", "Group"]
    )


def _one_week_prices(low_hours: int) -> pd.DataFrame:
    price = np.full(168, 100.0)
    price[:low_hours] = 10.0
    return pd.DataFrame({"DE": price}, index=_weekly_hours())


def test_min_hours_decide_the_floor_except_for_every_week_groups():
    from pybalmorel.backcasting.mustrun import must_run_floors

    output = _one_week_output(np.full(168, 2000.0), np.full(168, 3000.0))

    floors = must_run_floors(output, _one_week_prices(3), 2023, min_hours=4).set_index("Group")

    assert np.isnan(floors.loc["GAS", "Floor"])
    assert floors.loc["BIOMASS", "Floor"] == 3000.0
    assert floors.loc["GAS", "LowPriceHours"] == 3
    # Weeks without data have no row
    assert len(floors) == 2


def test_floor_is_the_minimum_over_all_hours_of_the_week():
    from pybalmorel.backcasting.mustrun import must_run_floors

    gas = np.full(168, 2000.0)
    gas[:4] = 1500.0  # the low-price hours
    gas[100] = 800.0  # an hour at a high price
    output = _one_week_output(gas, np.full(168, 3000.0))

    floors = must_run_floors(output, _one_week_prices(4), 2023).set_index("Group")

    assert floors.loc["GAS", "Floor"] == 800.0


def test_week_with_too_little_data_or_a_tiny_floor_gets_none():
    from pybalmorel.backcasting.mustrun import must_run_floors

    gas = np.full(168, 2000.0)
    gas[:90] = np.nan
    output = _one_week_output(gas, np.full(168, 0.5))

    floors = must_run_floors(output, _one_week_prices(10), 2023)

    assert floors["Floor"].isna().all()


def test_zones_of_a_region_are_summed_before_the_minimum(tmp_path):
    from pybalmorel.backcasting.__main__ import load_observed_generation
    from pybalmorel.backcasting.mustrun import group_output

    hours = _weekly_hours()
    north, south = np.full(168, 1000.0), np.full(168, 500.0)
    north[0], south[1] = 0.0, 0.0
    for zone, gas in (("IT_NORD", north), ("IT_SUD", south)):
        pd.DataFrame({"Fossil Gas": gas}, index=hours).to_csv(tmp_path / f"2023_{zone}_generation.csv")

    output = group_output(load_observed_generation(str(tmp_path), 2023))

    assert output[("IT", "GAS")].min() == 500.0


def test_region_price_is_weighted_by_zone_load():
    from pybalmorel.backcasting.mustrun import region_prices

    hours = _weekly_hours()[:2]
    prices = pd.DataFrame({"IT-NORD": [10.0, 10.0], "IT-SUD": [100.0, 100.0], "FR": [50.0, 50.0]}, index=hours)
    load = pd.DataFrame({"IT-NORD": [3000.0, np.nan], "IT-SUD": [1000.0, np.nan]}, index=hours)

    regional = region_prices(prices, load)

    assert regional["IT"].tolist() == [32.5, 55.0]
    assert regional["FR"].tolist() == [50.0, 50.0]


def _floors(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(region, group, season, floor, 10, 0.5) for region, group, season, floor in rows],
        columns=["Region", "Group", "Season", "Floor", "LowPriceHours", "ObservedTWh"],
    )


def test_floor_above_available_capacity_is_capped_and_without_gkfx_dropped():
    from pybalmorel.backcasting.mustrun import cap_floors

    capacity = _coal_capacity(1000.0)
    gkrate = pd.DataFrame(
        {"AAA": ["DE4-S_A"], "GGG": ["COAL_CND"], "SSS": ["S01"], "Value": [0.5]}
    )
    floors = _floors(
        [("DE", "HARDCOAL", "S01", 800.0), ("DE", "HARDCOAL", "S02", 800.0),
         ("DE", "GAS", "S01", 300.0), ("XX", "GAS", "S01", 300.0)]
    )

    with pytest.warns(UserWarning) as warnings:
        capped = cap_floors(floors, capacity, gkrate, ["DE4-S", "DE4-W"]).set_index(["Group", "Season"])

    assert capped.loc[("HARDCOAL", "S01"), ["Floor", "K", "Capped"]].tolist() == [500.0, 500.0, True]
    assert capped.loc[("HARDCOAL", "S02"), ["Floor", "Capped"]].tolist() == [800.0, False]
    assert np.isnan(capped.loc[("GAS", "S01"), "Floor"])
    assert set(capped["Region"]) == {"DE"}
    messages = " ".join(str(warning.message) for warning in warnings)
    assert "DE GAS" in messages and "capped" in messages


def test_must_run_files_list_zones_groups_and_floors(tmp_path):
    from pybalmorel.backcasting.mustrun import write_must_run_files

    floors = _floors([("DE", "LIGNITE", "S01", 3000.0), ("DE", "BIOMASS", "S02", 3600.04), ("DK1", "GAS", "S01", np.nan)])

    inc_files = write_must_run_files(floors, ["DE4-W", "DE4-E", "DK1"], ["LIGNITE", "WOODCHIPS", "STRAW"], tmp_path)

    assert [inc_file.name for inc_file in inc_files][-1] == "MUSTRUN_FLOOR.inc"
    read = lambda name: (tmp_path / f"{name}.inc").read_text()
    assert "/\nDE\n/;" in read("MUSTRUN_ZONE")
    assert "DE.(DE4-E,DE4-W)" in read("MUSTRUN_ZONE_RRR")
    assert "/\nLIGNITE\nBIOMASS\n/;" in read("MUSTRUN_GROUP")
    assert "BIOMASS.(WOODCHIPS,STRAW)" in read("MUSTRUN_GROUP_FFF")
    assert "DE.BIOMASS.S02 3600.0\nDE.LIGNITE.S01 3000.0\n" in read("MUSTRUN_FLOOR")


class _FakeModel:
    def __init__(self, inputs: dict[str, pd.DataFrame]):
        self.inputs = inputs

    def get_input(self, symbol: str) -> pd.DataFrame:
        return self.inputs[symbol]


@pytest.mark.parametrize("threshold, written", [(-1000.0, False), (40.0, True)])
def test_must_run_floor_writes_nothing_without_a_floor(tmp_path, monkeypatch, threshold, written):
    import pybalmorel.backcasting.mustrun as mustrun

    gkfx, gdata, rrraaa, names = _thermal_inputs({"GAS_CND": ("GCND", "NATGAS")}, [("DE4-S_A", "GAS_CND", 5000.0)])
    model = _FakeModel(
        {"GKFX": gkfx, "GDATA": gdata, "RRRAAA": rrraaa, "FFF": pd.DataFrame({"*": ["NATGAS"]}),
         "GKRATE": pd.DataFrame(columns=["AAA", "GGG", "SSS", "Value"])}
    )
    monkeypatch.setattr(mustrun, "load_scenario_input", lambda *args, **kwargs: (model, names))
    (tmp_path / "backcast" / "data").mkdir(parents=True)
    hours = backcast_hours(2023)
    generation = {"DE": pd.DataFrame({"Fossil Gas": 2000.0}, index=hours)}
    prices = pd.DataFrame({"DE": 10.0}, index=hours)

    with pytest.warns(UserWarning, match="GKRATE_THERMAL_ENTSOE"):
        inc_files = mustrun.generate_must_run_floor(
            tmp_path, "backcast", 2023, generation, prices, pd.DataFrame(), price_threshold=threshold
        )

    assert (tmp_path / "backcast" / "data" / "MUSTRUN_FLOOR.inc").exists() == written
    assert bool(inc_files) == written
    assert (tmp_path / "backcast" / "backcastoutput" / "must_run_floor.csv").exists()


def test_nuclear_is_in_no_fuel_group():
    from pybalmorel.backcasting.thermal import GROUP_FUELS, GROUP_PRODUCTION_TYPES

    assert not any("NUCLEAR" in fuels for fuels in GROUP_FUELS.values())
    assert not any("Nuclear" in types for types in GROUP_PRODUCTION_TYPES.values())


# %% ------------------------------- ###
###          13. VRE level          ###
### ------------------------------- ###

VRE_TECHNOLOGIES = {
    "WT_ONS": ("GWND", "WIND"),
    "WT_OFF": ("GWND", "WIND"),
    "PV": ("GSOLE", "SUN"),
    "SOLAR_HEAT": ("GSOLH", "SUN"),
}


def _vre_inputs(gkfx: list[tuple[str, str, float]], wndflh: dict[str, float], soleflh: dict[str, float] | None = None):
    """GKFX, GDATA, RRRAAA, WNDFLH, SOLEFLH, GKRATE and acronym names; an area's region is its name up to the first '_'."""
    gkfx_df, gdata, _, names = _thermal_inputs(VRE_TECHNOLOGIES, gkfx)
    areas = sorted(set(gkfx_df["AAA"]) | set(wndflh) | set(soleflh or {}))
    rrraaa = pd.DataFrame({"RRR": [area.split("_")[0] for area in areas], "AAA": areas})
    flh = lambda values: pd.DataFrame({"AAA": list(values), "Value": list(values.values())})
    gkrate = pd.DataFrame(columns=["AAA", "GGG", "SSS", "Value"])
    return gkfx_df, gdata, rrraaa, flh(wndflh), flh(soleflh or {}), gkrate, names


def _vre_factors(inputs, observed: dict[str, dict[str, float]], bounds=(0.6, 1.5)):
    from pybalmorel.backcasting.vre import available_vre, flh_areas, scaled_flh, vre_factors

    available = available_vre(*inputs, 2023)
    observed = pd.DataFrame.from_dict(observed, orient="index").reindex(columns=["Solar", "Onshore", "Offshore"])
    factors = vre_factors(available, observed, bounds)
    scaled = scaled_flh(flh_areas(inputs[3], inputs[4], inputs[2]), factors)
    return available, factors, scaled


def test_observed_vre_sums_the_backcast_calendar():
    from pybalmorel.backcasting.vre import observed_vre

    hours = backcast_hours(2023)
    generation = {"DE": pd.DataFrame({"Solar": 1000.0, "Wind Onshore": 2000.0}, index=hours)}

    observed = observed_vre(generation, 2023)

    assert observed.loc["DE", "Solar"] == pytest.approx(1000.0 * len(hours) / 1e6)
    assert observed.loc["DE", "Onshore"] == pytest.approx(2.0 * observed.loc["DE", "Solar"])
    assert np.isnan(observed.loc["DE", "Offshore"])


def test_areas_of_a_region_and_kind_share_one_factor():
    inputs = _vre_inputs(
        [("DE4-N_A", "WT_ONS", 1000.0), ("DE4-S_A", "WT_ONS", 1000.0), ("DE4-S_A", "PV", 2000.0)],
        {"DE4-N_A": 2000.0, "DE4-S_A": 3000.0},
        {"DE4-S_A": 1000.0},
    )

    available, factors, scaled = _vre_factors(inputs, {"DE": {"Solar": 1.6, "Onshore": 4.0}})

    factors = factors.set_index(["Region", "Kind"])
    assert factors.loc[("DE", "Onshore"), "Factor"] == pytest.approx(0.8)
    assert factors.loc[("DE", "Solar"), "Factor"] == pytest.approx(0.8)
    onshore = scaled[scaled["Symbol"] == "WNDFLH"].set_index("Area")["NewFLH"]
    assert onshore["DE4-N_A"] == pytest.approx(1600.0)
    assert onshore["DE4-S_A"] / onshore["DE4-N_A"] == pytest.approx(1.5)
    # Available output x factor is the observed output
    capacity = available.merge(scaled[["Area", "Symbol", "NewFLH"]].assign(
        Kind=lambda df: np.where(df["Symbol"] == "SOLEFLH", "Solar", "Onshore")), on=["Area", "Kind"])
    scaled_twh = (capacity["Capacity"] * capacity["NewFLH"] * capacity["Rating"] / 1e6).groupby(capacity["Kind"]).sum()
    assert scaled_twh.to_dict() == pytest.approx({"Onshore": 4.0, "Solar": 1.6})


def test_rating_reduces_available_output():
    gkfx, gdata, rrraaa, wndflh, soleflh, _, names = _vre_inputs([("DK1_A", "WT_ONS", 1000.0)], {"DK1_A": 3000.0})
    gkrate = pd.DataFrame({"AAA": "DK1_A", "GGG": "WT_ONS", "SSS": ["S01", "S02"], "Value": [0.0, 0.48]})

    available, _, _ = _vre_factors((gkfx, gdata, rrraaa, wndflh, soleflh, gkrate, names), {"DK1": {"Onshore": 3.0}})

    # S01 at 0 (eps), S02 at 0.48 and 50 unset weeks at 1
    assert available["Rating"].iloc[0] == pytest.approx(50.48 / 52)
    assert available["Available"].iloc[0] == pytest.approx(3.0 * 50.48 / 52)


def test_region_without_entsoe_offshore_gets_one_wind_factor():
    inputs = _vre_inputs(
        [("SE4_A", "WT_ONS", 1000.0), ("SE4_OFF_OFF_Existing_RG1", "WT_OFF", 500.0)],
        {"SE4_A": 2000.0, "SE4_OFF_OFF_Existing_RG1": 4000.0},
    )

    _, factors, scaled = _vre_factors(inputs, {"SE4": {"Onshore": 4.8}})

    assert factors[["Region", "Kind"]].values.tolist() == [["SE4", "Wind"]]
    assert factors["Factor"].iloc[0] == pytest.approx(1.2)
    assert scaled.set_index("Area")["NewFLH"].to_dict() == pytest.approx(
        {"SE4_A": 2400.0, "SE4_OFF_OFF_Existing_RG1": 4800.0}
    )


def test_region_with_entsoe_offshore_keeps_separate_factors():
    inputs = _vre_inputs(
        [("DE4-N_A", "WT_ONS", 1000.0), ("DE4-N_OFF_VRE-OFF_SP316_RG1", "WT_OFF", 500.0)],
        {"DE4-N_A": 2000.0, "DE4-N_OFF_VRE-OFF_SP316_RG1": 4000.0},
    )
    inputs[2].loc[inputs[2]["AAA"].str.contains("OFF"), "RRR"] = "DE4-N"

    _, factors, _ = _vre_factors(inputs, {"DE": {"Onshore": 1.6, "Offshore": 2.4}})

    assert factors.set_index("Kind")["Factor"].to_dict() == pytest.approx({"Onshore": 0.8, "Offshore": 1.2})


def test_factor_outside_bounds_writes_nothing_and_warns(tmp_path):
    from pybalmorel.backcasting.vre import write_flh_override

    inputs = _vre_inputs([("IT_A", "PV", 1000.0)], {}, {"IT_A": 1000.0})

    with pytest.warns(UserWarning, match="IT solar: factor 2.50"):
        _, factors, scaled = _vre_factors(inputs, {"IT": {"Solar": 2.5}})

    assert not factors["Written"].any()
    assert scaled.empty
    write_flh_override(scaled, factors, "SOLEFLH", 2023, tmp_path)
    assert "SOLEFLH(" not in (tmp_path / "SOLEFLH_ENTSOE.inc").read_text()


def test_region_without_generation_file_warns():
    inputs = _vre_inputs([("NO3_A", "WT_ONS", 1000.0)], {"NO3_A": 3000.0})

    with pytest.warns(UserWarning, match="NO3 .* no ENTSO-E generation file"):
        _, factors, _ = _vre_factors(inputs, {"DE": {"Onshore": 1.0}})

    assert not factors["Written"].any()


def test_area_without_flh_warns_and_is_not_scaled():
    inputs = _vre_inputs([("DE4-N_A", "WT_ONS", 1000.0), ("DE4-S_A", "WT_ONS", 700.0)], {"DE4-N_A": 2000.0})

    with pytest.warns(UserWarning, match="DE4-S_A has 700 MW of GKFX but no WNDFLH"):
        available, factors, scaled = _vre_factors(inputs, {"DE": {"Onshore": 1.6}})

    assert factors["AvailableTWh"].iloc[0] == pytest.approx(2.0)
    assert factors["GKFX"].iloc[0] == pytest.approx(1700.0)
    assert scaled["Area"].tolist() == ["DE4-N_A"]


def test_solar_heat_is_not_counted():
    import warnings

    inputs = _vre_inputs([("DK1_A", "PV", 1000.0), ("DK1_A", "SOLAR_HEAT", 5000.0)], {}, {"DK1_A": 1000.0})

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        available, factors, _ = _vre_factors(inputs, {"DK1": {"Solar": 0.9}})

    assert available["Technology"].tolist() == ["PV"]
    assert factors["Factor"].iloc[0] == pytest.approx(0.9)


def test_rerun_on_the_scaled_input_writes_the_same_file(tmp_path):
    from pybalmorel.backcasting.vre import write_flh_override

    gkfx = [("DE4-N_A", "WT_ONS", 1000.0), ("DE4-S_A", "WT_ONS", 1000.0)]
    observed = {"DE": {"Onshore": 4.0}}
    _, factors, scaled = _vre_factors(_vre_inputs(gkfx, {"DE4-N_A": 2000.0, "DE4-S_A": 3000.0}), observed)
    first = write_flh_override(scaled, factors, "WNDFLH", 2023, tmp_path)
    first_text = (tmp_path / "WNDFLH_ENTSOE.inc").read_text()

    rerun_flh = scaled.set_index("Area")["NewFLH"].to_dict()
    _, factors, scaled = _vre_factors(_vre_inputs(gkfx, rerun_flh), observed)
    write_flh_override(scaled, factors, "WNDFLH", 2023, tmp_path)

    assert factors["Factor"].iloc[0] == pytest.approx(1.0)
    assert (tmp_path / "WNDFLH_ENTSOE.inc").read_text() == first_text
    assert "WNDFLH('DE4-N_A')=1600.0;" in first_text
    assert first.name == "WNDFLH_ENTSOE.inc"


def test_flh_include_is_appended_once(tmp_path):
    from pybalmorel.backcasting.vre import append_flh_include

    wndflh_inc = tmp_path / "WNDFLH.inc"
    wndflh_inc.write_text("PARAMETER WNDFLH(AAA) /\nDK1_A 3000\n/;")

    for _ in range(3):
        append_flh_include(wndflh_inc, "WNDFLH")
    append_flh_include(tmp_path / "SOLEFLH.inc", "SOLEFLH")

    content = wndflh_inc.read_text()
    assert content.startswith("PARAMETER WNDFLH(AAA) /\nDK1_A 3000\n/;\n")
    assert content.count("$if     EXIST '../data/WNDFLH_ENTSOE.inc'") == 1
    assert content.count("$if not EXIST '../data/WNDFLH_ENTSOE.inc' $INCLUDE '../../base/data/WNDFLH_ENTSOE.inc';") == 1
    assert (tmp_path / "SOLEFLH.inc").read_text().startswith("$include '../../base/data/SOLEFLH.inc';\n")


def test_offshore_areas_are_classified_by_name():
    from pybalmorel.backcasting.vre import OFFSHORE_AREA

    assert OFFSHORE_AREA.search("DE4-N_OFF_OFF_Existing_RG2")
    assert OFFSHORE_AREA.search("IT_OFF2_VRE-OFF_bottom_fixed_SP316-HH155_RG1")
    assert not OFFSHORE_AREA.search("DE4-N_VRE-ONS_SP335-HH100_RG1")
    assert not OFFSHORE_AREA.search("DK1_A")


# %% ------------------------------- ###
###         14. Demand Level        ###
### ------------------------------- ###

HEATING_GWH = {"FC_OTH_HH_E_SH": 4000.0, "FC_OTH_HH_E_WH": 1000.0, "TI_EHG_EB": 500.0, "TI_EHG_EDHP": 500.0}


def _balances(rows: dict[str, dict[str, float]]) -> pd.DataFrame:
    from pybalmorel.backcasting.demand import HEATING
    from pybalmorel.backcasting.eurostat import FINAL_CONSUMPTION

    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=[FINAL_CONSUMPTION, *HEATING])


def _de(rows: list[tuple[str, str, float]], year: str = "2023") -> pd.DataFrame:
    return pd.DataFrame([(year, region, user, value) for region, user, value in rows], columns=["YYY", "RRR", "DEUSER", "Value"])


def _disloss(losses: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({"RRR": list(losses), "Value": list(losses.values())})


def test_decode_jsonstat_keeps_missing_cells_missing():
    from pybalmorel.backcasting.eurostat import decode_jsonstat

    response = {
        "id": ["geo", "nrg_bal"],
        "size": [2, 3],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0, "EL": 1}}},
            "nrg_bal": {"category": {"index": {"FC_E": 0, "TI_EHG_EB": 1, "TI_EHG_EDHP": 2}}},
        },
        "value": {"0": 464000.0, "2": 120.5, "4": 300.0},
    }

    decoded = decode_jsonstat(response)

    assert decoded[["geo", "nrg_bal", "Value"]].values.tolist() == [
        ["DE", "FC_E", 464000.0],
        ["DE", "TI_EHG_EDHP", 120.5],
        ["EL", "TI_EHG_EB", 300.0],
    ]


def test_cached_eurostat_file_is_used_without_a_request(tmp_path, monkeypatch):
    import json

    import pybalmorel.backcasting.eurostat as eurostat

    response = {
        "id": ["geo", "nrg_bal", "time"],
        "size": [1, 1, 1],
        "dimension": {
            "geo": {"category": {"index": {"EL": 0}}},
            "nrg_bal": {"category": {"index": {"FC_E": 0}}},
            "time": {"category": {"index": {"2023": 0}}},
        },
        "value": {"0": 50000.0},
    }
    requests_made = []

    def fake_download(url):
        requests_made.append(url)
        return response

    monkeypatch.setattr(eurostat, "download_json", fake_download)

    first = eurostat.fetch_eurostat("nrg_bal_c", 2023, tmp_path)
    second = eurostat.fetch_eurostat("nrg_bal_c", 2023, tmp_path)

    assert len(requests_made) == 1
    assert "nrg_bal=FC_E&nrg_bal=TI_EHG_EB&nrg_bal=TI_EHG_EDHP" in requests_made[0]
    assert json.loads((tmp_path / "2023_nrg_bal_c.json").read_text()) == response
    assert first.values.tolist() == second.values.tolist() == [["GR", "FC_E", 50000.0]]


def test_level_is_load_net_of_losses_less_heating():
    from pybalmorel.backcasting.demand import demand_levels

    load = pd.Series({"DK1": 20e6})
    balances = _balances({"DK": {"FC_E": 19000.0, **HEATING_GWH}})

    levels, summary = demand_levels(
        _de([("DK1", "RESE", 6e6), ("DK1", "OTHER", 12e6)]), _disloss({"DK1": 0.05}), load, balances, 2023
    )

    level = levels["Value"].sum()
    heating = sum(HEATING_GWH.values()) * 1e3
    assert level == pytest.approx(20e6 * 0.95 - heating)
    # Balmorel's load with electric heating equal to Eurostat's is ENTSO-E's
    assert (level + heating) / (1 - 0.05) == pytest.approx(load["DK1"])
    assert levels.set_index("User")["Value"]["OTHER"] == pytest.approx(2 * levels.set_index("User")["Value"]["RESE"])
    assert summary.iloc[0]["Written"]
    assert summary.iloc[0]["Coverage"] == pytest.approx(20e6 * 0.95 / 19e6)


def test_eurostat_basis_is_final_consumption_less_heating():
    from pybalmorel.backcasting.demand import demand_levels

    levels, _ = demand_levels(
        _de([("DK1", "OTHER", 12e6)]),
        _disloss({"DK1": 0.05}),
        pd.Series({"DK1": 20e6}),
        _balances({"DK": {"FC_E": 19000.0, **HEATING_GWH}}),
        2023,
        basis="eurostat",
    )

    assert levels["Value"].sum() == pytest.approx(19e6 - 6e6)


def test_shared_de_lu_load_is_split_by_final_consumption():
    from pybalmorel.backcasting.demand import split_shared_load

    balances = _balances({"DE": {"FC_E": 464000.0}, "LU": {"FC_E": 6000.0}})

    load = split_shared_load(pd.Series({"DE": 470e6, "DK1": 20e6}), balances)

    assert load["LU"] == pytest.approx(470e6 * 6 / 470)
    assert load["DE"] + load["LU"] == pytest.approx(470e6)
    assert load["DK1"] == 20e6


def test_regions_and_users_keep_their_base_ratios():
    from pybalmorel.backcasting.demand import demand_levels

    de = _de(
        [("DE4-E", "RESE", 10e6), ("DE4-E", "OTHER", 30e6), ("DE4-N", "OTHER", 60e6),
         ("DE4-S", "OTHER", 150e6), ("DE4-W", "OTHER", 200e6)]
    )

    levels, _ = demand_levels(
        de, _disloss({}), pd.Series({"DE": 450e6}), _balances({"DE": {"FC_E": 460000.0, **HEATING_GWH}}), 2023
    )

    new = levels.set_index(["Region", "User"])["Value"]
    assert new.sum() == pytest.approx(450e6 - 6e6)
    base = de.set_index(["RRR", "DEUSER"])["Value"]
    assert (new / new.sum()).to_dict() == pytest.approx((base / base.sum()).rename_axis(["Region", "User"]).to_dict())


def test_country_of_several_canonical_regions_splits_heating_by_load():
    from pybalmorel.backcasting.demand import demand_levels

    de = _de([("NO1", "OTHER", 30e6), ("NO2", "OTHER", 40e6)])

    levels, summary = demand_levels(
        de, _disloss({"NO1": 0.1, "NO2": 0.0}), pd.Series({"NO1": 40e6, "NO2": 60e6}),
        _balances({"NO": {"FC_E": 90000.0, **HEATING_GWH}}), 2023,
    )

    new = levels.set_index("Region")["Value"]
    assert new["NO1"] == pytest.approx(40e6 * 0.9 - 6e6 * 0.4)
    assert new["NO2"] == pytest.approx(60e6 - 6e6 * 0.6)
    assert summary.iloc[0]["DisLoss"] == pytest.approx(0.04)


@pytest.mark.parametrize(
    "eurostat, note",
    [
        ({"FC_E": 30000.0, **HEATING_GWH}, "coverage 0.67"),
        ({**HEATING_GWH}, "no Eurostat final consumption"),
        ({"FC_E": 19000.0}, "no Eurostat electricity for heating"),
    ],
)
def test_country_that_fails_a_check_is_not_written(eurostat, note):
    from pybalmorel.backcasting.demand import demand_levels

    with pytest.warns(UserWarning, match=f"DK keeps the input data's DE: {note}"):
        levels, summary = demand_levels(
            _de([("DK1", "OTHER", 12e6), ("FR", "OTHER", 400e6)]), _disloss({}),
            pd.Series({"DK1": 20e6, "FR": 420e6}),
            _balances({"DK": eurostat, "FR": {"FC_E": 400000.0, **HEATING_GWH}}), 2023,
        )

    assert set(levels["Region"]) == {"FR"}
    assert not summary.set_index("Country").loc["DK", "Written"]


def test_country_without_entsoe_load_is_not_written():
    from pybalmorel.backcasting.demand import demand_levels

    with pytest.warns(UserWarning, match="UK keeps the input data's DE: no ENTSO-E load"):
        levels, _ = demand_levels(
            _de([("UK", "OTHER", 300e6)]), _disloss({}), pd.Series(dtype=float), _balances({}), 2023
        )

    assert levels.empty


def test_de_override_lines(tmp_path):
    from pybalmorel.backcasting.demand import write_de_override

    levels = pd.DataFrame({"Region": ["DE4-E", "DE4-E"], "User": ["RESE", "OTHER"], "Value": [123456789.04, 5.0]})

    write_de_override(levels, 2023, "entsoe", tmp_path)

    content = (tmp_path / "DE_ENTSOE.inc").read_text()
    assert "DE('2023','DE4-E','OTHER')=5.0;\nDE('2023','DE4-E','RESE')=123456789.0;\n" in content
    assert "ENTSO-E load net of distribution losses" in content


def test_annual_load_fills_missing_hours_with_the_mean():
    from pybalmorel.backcasting.demand import annual_load

    hours = backcast_hours(2023)
    observed = pd.DataFrame({"IE": 4000.0, "DK1": 2000.0}, index=hours)
    observed.iloc[:1000, 0] = np.nan

    with pytest.warns(UserWarning, match="IE misses 1000 of 8736 hours"):
        load = annual_load(observed, 2023)

    assert load.to_dict() == pytest.approx({"IE": 4000.0 * 8736, "DK1": 2000.0 * 8736})

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
    entsoe_flow_limits,
    flow_statistics,
    format_balmorel_flows,
    load_entsoe_flows,
    observed_max_flow,
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
    assert observed_max_flow(2023, "10YNO-2--------T", "10YDK-1--------W", tmp_path) == 50.0

    # Read once, not summed twice
    flows = load_entsoe_flows(tmp_path, 2023)
    assert flows.query("From == 'DK1' and To == 'DE'")["Value"].tolist() == [100.0]
    assert entsoe_flow_limits(tmp_path, 2023)[("DK1", "DE")] == 100.0


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


def test_neighbour_pairs_are_symmetric_and_include_missing_borders():
    pairs = neighbour_pairs(["FR", "BE", "10YDK-1--------W", "DE_LU", "GR", "10Y1001A1001A788", "XK", "AL"])

    assert all((to, frm) in pairs for frm, to in pairs)
    assert ("FR", "BE") in pairs
    # Saved under the spelling transmission-max-flow looks up
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

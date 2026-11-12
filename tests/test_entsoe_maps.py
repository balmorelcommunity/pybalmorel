"""
ENTSO-E Transmission Map Tests

GAMS-free tests of the ENTSO-E transmission map on synthetic crossborder_flows
csv's: flows keep ENTSO-E's raw zone names, net and gross border flows, zone
outlines and the map itself.

Created on 05.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import matplotlib
import pandas as pd
import pytest
from matplotlib.patches import FancyArrowPatch

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pybalmorel.entsoe import (  # noqa: E402
    load_zone_geometries,
    plot_transmission_map,
    sum_crossborder_flows,
)
from pybalmorel.entsoe.maps import (  # noqa: E402
    _border_flows,
    _format_flow,
    _period_label,
    _round_down,
)


def _write_flow_csv(path, file_name, values, freq="15min", start="2023-01-02 00:00"):
    index = pd.date_range(start, periods=len(values), freq=freq, tz="UTC")
    pd.Series(values, index=index.tz_convert("Europe/Brussels")).to_csv(path / file_name)


@pytest.fixture
def flow_folder(tmp_path):
    # DK_1 <-> DE_LU, the DK_1 -> DE_LU direction saved under two spellings
    _write_flow_csv(tmp_path, "2023_DK_1-DE_LU_crossborder_flows.csv", [100.0] * 4)
    _write_flow_csv(tmp_path, "2023_10YDK-1--------W-DE_LU_crossborder_flows.csv", [100.0] * 4)
    _write_flow_csv(tmp_path, "2023_DE_LU-DK_1_crossborder_flows.csv", [30.0] * 4)
    # One direction only, between two zones Balmorel would rename (IT, UK)
    _write_flow_csv(tmp_path, "2023_10Y1001A1001A73I-CH_crossborder_flows.csv", [50.0] * 8)
    _write_flow_csv(tmp_path, "2023_10YGB----------A-IE_SEM_crossborder_flows.csv", [20.0] * 4)
    return tmp_path


# %% ------------------------------- ###
###          1. Flow totals         ###
### ------------------------------- ###


def test_flows_keep_raw_entsoe_zone_names(flow_folder):
    flows = sum_crossborder_flows(flow_folder, 2023).set_index(["From", "To"])["Value"]

    # Hourly means summed to MWh; the twice-saved direction is read once
    assert flows.to_dict() == {
        ("DE_LU", "DK_1"): 30.0,
        ("DK_1", "DE_LU"): 100.0,
        ("GB", "IE_SEM"): 20.0,
        ("IT_NORD", "CH"): 100.0,
    }


def test_flows_within_period(tmp_path):
    _write_flow_csv(tmp_path, "2023_FR-ES_crossborder_flows.csv", list(range(24)), freq="1h")

    # 01:00 and 02:00 UTC, given as Brussels time (UTC+1 in winter)
    flows = sum_crossborder_flows(tmp_path, 2023, start="2023-01-02 02:00", end="2023-01-02 04:00")
    assert flows["Value"].tolist() == [1.0 + 2.0]

    flows = sum_crossborder_flows(tmp_path, 2023, start=pd.Timestamp("2023-01-02 22:00", tz="UTC"))
    assert flows["Value"].tolist() == [22.0 + 23.0]


def test_no_flow_files_raises(tmp_path):
    with pytest.raises(ValueError, match="No 2023 crossborder_flows"):
        sum_crossborder_flows(tmp_path, 2023)


def test_border_flows_net_and_gross(flow_folder):
    borders = _border_flows(sum_crossborder_flows(flow_folder, 2023)).set_index(["ZoneA", "ZoneB"])

    # Net is ZoneA -> ZoneB minus ZoneB -> ZoneA, a missing direction counting as 0
    assert borders.loc[("DE_LU", "DK_1"), "Net"] == 30.0 - 100.0
    assert borders.loc[("DE_LU", "DK_1"), "Gross"] == 130.0
    assert borders.loc[("CH", "IT_NORD"), "Net"] == -100.0
    assert len(borders) == 3


# %% ------------------------------- ###
###          2. Zone outlines       ###
### ------------------------------- ###


def test_zone_outlines_from_entsoe_py_and_pybalmorel():
    zones = ["DK_1", "IT_NORD", "DE_LU", "GB", "IE_SEM", "XK", "MT"]
    geometries = load_zone_geometries(zones)

    assert sorted(geometries.index) == sorted(zones)
    assert geometries.crs == "EPSG:4326"
    assert geometries.is_valid.all() and not geometries.is_empty.any()


def test_italian_zones_before_2021_get_earlier_outline():
    before, after = load_zone_geometries(["IT_CNOR"], 2020), load_zone_geometries(["IT_CNOR"], 2023)
    assert not before["IT_CNOR"].equals(after["IT_CNOR"])


def test_unknown_zone_outline_warns():
    with pytest.warns(UserWarning, match="No outline found for ENTSO-E zone"):
        geometries = load_zone_geometries(["DK_1", "NOT_A_ZONE"])
    assert list(geometries.index) == ["DK_1"]


# %% ------------------------------- ###
###              3. Map             ###
### ------------------------------- ###


def test_net_map_draws_one_line_and_arrow_per_border(flow_folder):
    fig, ax = plot_transmission_map(flow_folder, 2023, unit="MWh", line_label_show=True)

    assert len(ax.lines) == 3
    assert len([patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)]) == 3
    texts = {text.get_text() for text in ax.texts}
    assert {"DK_1", "DE_LU", "IT_NORD", "CH", "GB", "IE_SEM"} <= texts
    assert {"70", "100", "20"} <= texts
    assert ax.get_title(loc="left") == "Net physical cross-border flows, ENTSO-E, 2023"
    plt.close(fig)


def test_net_arrow_points_at_importer(flow_folder):
    fig, ax = plot_transmission_map(flow_folder, 2023, line_show_min=80e-6, zone_label_show=False)

    # Only IT_NORD -> CH (100 MWh) is at least 80 MWh, so it's the one line
    (line,) = ax.lines
    (arrow,) = [patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)]
    (x_from, x_to), (y_from, y_to) = line.get_xdata(), line.get_ydata()
    (tail_x, tail_y), (tip_x, tip_y) = arrow._posA_posB
    assert (tip_x - tail_x) * (x_to - x_from) + (tip_y - tail_y) * (y_to - y_from) > 0
    # Drawn from IT_NORD, south of CH
    assert y_from < y_to
    plt.close(fig)


def test_gross_map_has_no_arrows(flow_folder):
    fig, ax = plt.subplots()
    returned_fig, returned_ax = plot_transmission_map(flow_folder, 2023, value="gross", unit="MWh", ax=ax, title="")

    assert returned_ax is ax and returned_fig is fig
    assert len(ax.lines) == 3
    assert not [patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)]
    assert ax.get_legend().get_title().get_text() == "Gross flow (MWh)"
    assert ax.get_title(loc="left") == ""
    plt.close(fig)


@pytest.mark.parametrize("kwargs", [{"value": "max"}, {"unit": "PJ"}])
def test_invalid_options_raise(flow_folder, kwargs):
    with pytest.raises(ValueError):
        plot_transmission_map(flow_folder, 2023, **kwargs)


@pytest.mark.parametrize(
    "value, expected", [(44.0, 40.0), (0.37, 0.3), (0.3, 0.3), (2.0, 2.0), (1458.0, 1000.0)]
)
def test_round_down(value, expected):
    assert _round_down(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "flow, expected", [(44.4, "44"), (5.24, "5.2"), (3.0, "3.0"), (0.374, "0.37"), (0.00033, "<0.01")]
)
def test_format_flow(flow, expected):
    assert _format_flow(flow) == expected


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (None, None, "2024"),
        ("2024-01-15", "2024-02-01", "15 Jan 2024 to 31 Jan 2024"),
        (None, "2024-07-01", "01 Jan 2024 to 30 Jun 2024"),
        ("2024-07-01", None, "01 Jul 2024 to 31 Dec 2024"),
    ],
)
def test_period_label_names_last_day_included(start, end, expected):
    assert _period_label(2024, start, end) == expected

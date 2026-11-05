"""
ENTSO-E Transmission Map

Map of the physical cross-border flows fetched from the ENTSO-E transparency
platform, drawn on ENTSO-E's own bidding zones as entsoe-py names them
(e.g. 'DE_LU', 'DK_1', 'IT_NORD', 'IE_SEM'). Nothing is translated to
Balmorel regions or Canonical Region Names (see CONTEXT.md).

Created on 05.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import math
from pathlib import Path
from warnings import warn
import entsoe
import geopandas as gpd
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd
from entsoe.mappings import lookup_area
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from . import read_flow_csv, transmission_files

# Zone outlines bundled with entsoe-py, named by area name ('DK_1.geojson')
_entsoe_geojson_folder = Path(entsoe.__file__).parent / "geo" / "geojson"
# pybalmorel's region outlines, used for zones entsoe-py has no outline for
_pybalmorel_geojson_folder = Path(__file__).parents[1] / "geofiles" / "geojson_files"
# Zones whose pybalmorel outline is named differently: GB is drawn with the
# UK's outline (incl. Northern Ireland) and IE_SEM with Ireland's
_fallback_geofiles = {"GB": "UK", "IE_SEM": "IE"}

_unit_mwh = {"MWh": 1.0, "GWh": 1e3, "TWh": 1e6}

# Colours: neutral zones and one sequential blue for the flows
_zone_colour = "#e8e6e1"
_zone_edge_colour = "#ffffff"
_text_primary = "#0b0b0b"
_text_secondary = "#52514e"
_halo = [path_effects.withStroke(linewidth=2.5, foreground="#ffffff")]

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def zone_area_name(zone: str) -> str:
    """The entsoe-py area name of an ENTSO-E zone given by EIC code or area name.

    Args:
        zone (str): E.g. '10YDK-1--------W' or 'DK_1'.

    Returns:
        str: E.g. 'DK_1', or `zone` itself if entsoe-py doesn't know it.
    """
    try:
        return lookup_area(zone).name
    except ValueError:
        return zone


def _to_brussels_time(time: str | pd.Timestamp) -> pd.Timestamp:
    """A timestamp, read as Brussels time unless it carries a time zone."""
    timestamp = pd.Timestamp(time)
    return timestamp.tz_localize("Europe/Brussels") if timestamp.tz is None else timestamp


def sum_crossborder_flows(
    path: str | Path,
    year: int,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """The energy that physically flowed over each directed border between ENTSO-E zones.

    Reads every '<year>_<from>-<to>_crossborder_flows.csv' in `path` (a pair
    fetched under several spellings is read once), resamples it to hourly
    mean MW and sums the hours from `start` up to, not including, `end`.
    Missing hours count as no flow. Zones keep their entsoe-py area names:
    nothing is translated to Balmorel regions.

    Args:
        path (str | Path): Folder with the fetched crossborder_flows csv's.
        year (int): The year the files are for.
        start (str | pd.Timestamp | None, optional): First hour to include, read as
            Brussels time unless it has a time zone, e.g. '2024-01-15'. Defaults to None (start of the files).
        end (str | pd.Timestamp | None, optional): Hour to stop before. Defaults to None (end of the files).

    Returns:
        pd.DataFrame: Columns 'From', 'To' and 'Value' (MWh), one row per directed border.
    """
    files = transmission_files(path, year)
    if not files:
        raise ValueError(f"No {year} crossborder_flows csv's found in '{path}'")

    rows = []
    for (zone_from, zone_to), csv_path in files.items():
        flow = read_flow_csv(csv_path)
        if start is not None:
            flow = flow[flow.index >= _to_brussels_time(start)]
        if end is not None:
            flow = flow[flow.index < _to_brussels_time(end)]
        rows.append(
            {
                "From": zone_area_name(zone_from),
                "To": zone_area_name(zone_to),
                "Value": flow.sum(),
            }
        )

    return pd.DataFrame(rows, columns=["From", "To", "Value"])


def load_zone_geometries(zones: list[str], year: int | None = None) -> gpd.GeoSeries:
    """Outlines of ENTSO-E bidding zones, in lon/lat (EPSG:4326).

    Taken from the geojson files bundled with entsoe-py, and for zones it has
    none for (e.g. GB, IE_SEM, LU, MT and the Western Balkans) from
    pybalmorel's geofiles. GB is drawn with the UK's outline and IE_SEM with
    Ireland's, so Northern Ireland appears under GB.

    Args:
        zones (list[str]): entsoe-py area names, e.g. ['DK_1', 'IT_NORD', 'GB'].
        year (int | None, optional): The year to draw the zones for. Before 2021, the
            Italian zones redrawn on 1 January 2021 get their earlier outline. Defaults to None (current outlines).

    Returns:
        gpd.GeoSeries: One (multi)polygon per zone, indexed by zone. Zones without
            an outline are left out, with a warning.
    """
    geometries = {}
    for zone in zones:
        candidates = [
            _entsoe_geojson_folder / f"{zone}.geojson",
            _pybalmorel_geojson_folder / f"{_fallback_geofiles.get(zone, zone)}.geojson",
        ]
        if year is not None and year < 2021:
            candidates.insert(0, _entsoe_geojson_folder / f"{zone}_2020.geojson")

        geofile = next((candidate for candidate in candidates if candidate.exists()), None)
        if geofile is None:
            continue
        geometries[zone] = unary_union(gpd.read_file(geofile).to_crs("EPSG:4326").geometry)

    missing = [zone for zone in zones if zone not in geometries]
    if missing:
        warn(f"No outline found for ENTSO-E zone(s) {', '.join(missing)}")

    return gpd.GeoSeries(geometries, crs="EPSG:4326")


def _border_flows(flows: pd.DataFrame) -> pd.DataFrame:
    """One row per border: 'ZoneA' < 'ZoneB', 'Net' (A to B minus B to A) and 'Gross' (both directions).

    A direction without a file counts as no flow.
    """
    a_to_b = flows["From"] < flows["To"]
    borders = pd.DataFrame(
        {
            "ZoneA": flows["From"].where(a_to_b, flows["To"]),
            "ZoneB": flows["To"].where(a_to_b, flows["From"]),
            "Net": flows["Value"].where(a_to_b, -flows["Value"]),
            "Gross": flows["Value"],
        }
    )
    return borders.groupby(["ZoneA", "ZoneB"], as_index=False)[["Net", "Gross"]].sum()


def _zone_anchor(geometry: BaseGeometry) -> Point:
    """Where a zone's lines meet: the centroid of its largest part, or a point inside that part
    if the centroid falls outside it (e.g. a crescent-shaped zone)."""
    largest = max(getattr(geometry, "geoms", [geometry]), key=lambda part: part.area)
    centroid = largest.centroid
    return centroid if largest.contains(centroid) else largest.representative_point()


def _round_down(value: float) -> float:
    """`value` rounded down to one significant figure, e.g. 44 -> 40, 0.37 -> 0.3."""
    magnitude = 10 ** math.floor(math.log10(value))
    # Rounded first, so float error doesn't floor 0.3 / 0.1 = 2.9999... to 2
    return math.floor(round(value / magnitude, 9)) * magnitude


def _format_flow(flow: float) -> str:
    """A line label: 44, 5.2, 0.37, or '<0.01' for a flow too small to matter on the map."""
    if flow >= 10:
        return f"{flow:.0f}"
    if flow >= 1:
        return f"{flow:.1f}"
    return f"{flow:.2f}" if flow >= 0.01 else "<0.01"


def _period_label(year: int, start: str | pd.Timestamp | None, end: str | pd.Timestamp | None) -> str:
    """E.g. '2024', or '15 Jan 2024 to 31 Jan 2024' for a part of the year, naming the last day included."""
    if start is None and end is None:
        return str(year)
    first = pd.Timestamp(start).strftime("%d %b %Y") if start is not None else f"01 Jan {year}"
    # `end` itself is excluded, so the last day shown is that of the hour before it
    last = (pd.Timestamp(end) - pd.Timedelta(hours=1)).strftime("%d %b %Y") if end is not None else f"31 Dec {year}"
    return f"{first} to {last}"


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def plot_transmission_map(
    path: str | Path,
    year: int,
    value: str = "net",
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    unit: str = "TWh",
    ax: Axes | None = None,
    extent: tuple[float, float, float, float] | None = (-11.0, 34.0, 33.0, 71.5),
    crs: str = "EPSG:3035",
    line_show_min: float = 0.0,
    line_width_min: float = 0.5,
    line_width_max: float = 8.0,
    line_value_max: float | None = None,
    line_color: str = "#256abf",
    line_label_show: bool = False,
    zone_label_show: bool = True,
    zone_coordinates: dict[str, tuple[float, float]] | None = None,
    legend_loc: str = "upper left",
    title: str | None = None,
) -> tuple[Figure, Axes]:
    """Map the physical cross-border flows fetched from ENTSO-E, between ENTSO-E's raw bidding zones.

    Every border with a fetched '<year>_<from>-<to>_crossborder_flows.csv' in
    `path` is drawn as a line between the two zones, its width proportional to
    the energy that flowed over it. Zones are ENTSO-E's own (e.g. DE_LU, DK_1,
    the Italian zones), not Balmorel regions. Flows are physical, so they
    include loop flows.

    Args:
        path (str | Path): Folder with the fetched crossborder_flows csv's.
        year (int): The year to map.
        value (str, optional): 'net' for the flow one way minus the other, with an arrow
            towards the net importer, or 'gross' for both ways added. Defaults to 'net'.
        start (str | pd.Timestamp | None, optional): First hour to include, read as Brussels
            time unless it has a time zone. Defaults to None (whole year).
        end (str | pd.Timestamp | None, optional): Hour to stop before. Defaults to None (whole year).
        unit (str, optional): 'MWh', 'GWh' or 'TWh', for the legend, labels, `line_show_min`
            and `line_value_max`. Defaults to 'TWh'.
        ax (Axes | None, optional): Axes to draw on. Defaults to None (a new figure).
        extent (tuple[float, float, float, float] | None, optional): (lon min, lat min, lon max,
            lat max) to show. Zones partly outside are clipped, and their lines meet in the part
            shown. None shows every zone. Defaults to (-11, 34, 33, 71.5).
        crs (str, optional): The map projection. Defaults to 'EPSG:3035' (equal-area Europe).
        line_show_min (float, optional): Borders with less flow than this, in `unit`, are not drawn. Defaults to 0.
        line_width_min (float, optional): Narrowest line width, in points. Defaults to 0.5.
        line_width_max (float, optional): Line width of `line_value_max`, in points. Defaults to 8.
        line_value_max (float | None, optional): Flow drawn at `line_width_max`, in `unit`; set it
            to compare several maps. Defaults to None (the largest flow on the map).
        line_color (str, optional): Colour of the lines and arrows. Defaults to '#256abf'.
        line_label_show (bool, optional): Write the flow next to each line. Defaults to False.
        zone_label_show (bool, optional): Write each zone's name where its lines meet. Defaults to True.
        zone_coordinates (dict[str, tuple[float, float]] | None, optional): (lon, lat) where a
            zone's lines meet, overriding the centroid of its largest part, e.g. {'NO_4': (18.0, 68.5)}.
            Also places zones without an outline. Defaults to None.
        legend_loc (str, optional): Where the legend of line widths goes, as in matplotlib's
            `Axes.legend`. Defaults to 'upper left'.
        title (str | None, optional): The title. '' shows none. Defaults to None (describes the map).

    Returns:
        tuple[Figure, Axes]: The figure and axes of the map.
    """
    if value not in ("net", "gross"):
        raise ValueError(f"value must be 'net' or 'gross', not '{value}'")
    if unit not in _unit_mwh:
        raise ValueError(f"unit must be one of {list(_unit_mwh)}, not '{unit}'")

    # 2.1 Flows per border, in `unit`
    borders = _border_flows(sum_crossborder_flows(path, year, start, end))
    if value == "net":
        borders["Value"] = borders["Net"].abs()
        # Lines are drawn from the net exporter to the net importer
        exports = borders["Net"] >= 0
        borders["From"] = borders["ZoneA"].where(exports, borders["ZoneB"])
        borders["To"] = borders["ZoneB"].where(exports, borders["ZoneA"])
    else:
        borders["Value"] = borders["Gross"]
        borders["From"], borders["To"] = borders["ZoneA"], borders["ZoneB"]
    borders["Value"] = borders["Value"] / _unit_mwh[unit]
    borders = borders[(borders["Value"] > 0) & (borders["Value"] >= line_show_min)]

    # 2.2 Zone outlines, clipped to the extent, and where their lines meet
    zones = sorted(set(borders["From"]) | set(borders["To"]))
    zone_coordinates = zone_coordinates or {}
    geometries = load_zone_geometries(zones, year).to_crs(crs)
    unplaced = [zone for zone in zones if zone not in geometries.index and zone not in zone_coordinates]
    if unplaced:
        warn(f"Borders of {', '.join(unplaced)} are not drawn, as they have no outline: pass their zone_coordinates")
    if extent is not None:
        view = box(*gpd.GeoSeries([box(*extent)], crs="EPSG:4326").segmentize(0.5).to_crs(crs).total_bounds)
    else:
        view = box(*geometries.total_bounds).buffer(100_000, join_style="mitre")
    geometries = geometries.intersection(view)
    geometries = geometries[~geometries.is_empty]

    anchors = {zone: _zone_anchor(geometry) for zone, geometry in geometries.items()}
    if zone_coordinates:
        overrides = gpd.GeoSeries(
            [Point(lon, lat) for lon, lat in zone_coordinates.values()], index=list(zone_coordinates), crs="EPSG:4326"
        ).to_crs(crs)
        anchors.update(overrides.to_dict())

    # 2.3 Draw
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 9))
    else:
        fig = ax.figure
    ax.set_facecolor("#ffffff")

    # Largest zones first, so zones inside others (LU in DE_LU) stay visible
    geometries.loc[geometries.area.sort_values(ascending=False).index].plot(
        ax=ax, color=_zone_colour, edgecolor=_zone_edge_colour, linewidth=0.6, zorder=1
    )

    value_max = line_value_max if line_value_max is not None else borders["Value"].max()

    def line_width(flow: float) -> float:
        return max(line_width_min, line_width_max * flow / value_max)

    # Widest lines first, so narrow lines crossing them stay visible
    drawn = borders[borders["From"].isin(anchors) & borders["To"].isin(anchors)]
    for _, border in drawn.sort_values("Value", ascending=False).iterrows():
        point_from, point_to = anchors[border["From"]], anchors[border["To"]]
        width = line_width(border["Value"])
        ax.plot(
            [point_from.x, point_to.x],
            [point_from.y, point_to.y],
            color=line_color,
            linewidth=width,
            solid_capstyle="round",
            zorder=3,
        )

        dx, dy = point_to.x - point_from.x, point_to.y - point_from.y
        middle = (point_from.x + dx / 2, point_from.y + dy / 2)
        if value == "net":
            # Arrowhead centred on the middle of the line, pointing at the importer
            ax.add_patch(
                FancyArrowPatch(
                    (middle[0] - dx * 0.05, middle[1] - dy * 0.05),
                    (middle[0] + dx * 0.05, middle[1] + dy * 0.05),
                    arrowstyle="-|>,head_length=0.5,head_width=0.35",
                    mutation_scale=6 + 2 * width,
                    color=line_color,
                    linewidth=0,
                    shrinkA=0,
                    shrinkB=0,
                    zorder=4,
                )
            )
        if line_label_show:
            # Beside the line, on its left seen from the exporter
            length = math.hypot(dx, dy)
            offset = width / 2 + 5
            ax.annotate(
                _format_flow(border["Value"]),
                xy=middle,
                xytext=(-dy / length * offset, dx / length * offset),
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=7,
                color=_text_primary,
                path_effects=_halo,
                zorder=6,
            )

    if zone_label_show:
        drawn_zones = set(drawn["From"]) | set(drawn["To"])
        for zone, anchor in anchors.items():
            if zone in drawn_zones:
                ax.text(
                    anchor.x,
                    anchor.y,
                    zone,
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=_text_secondary,
                    path_effects=_halo,
                    zorder=5,
                )

    # Legend of line widths, at up to three round flows
    legend_values = sorted({_round_down(value_max * share) for share in (0.25, 0.5, 1.0)})
    handles = [
        Line2D([], [], color=line_color, linewidth=line_width(flow), label=f"{flow:g}")
        for flow in legend_values
    ]
    ax.legend(
        handles=handles,
        title=f"{value.capitalize()} flow ({unit})",
        loc=legend_loc,
        frameon=False,
        fontsize=8,
        title_fontsize=8,
        handlelength=3,
        alignment="left",
        labelcolor=_text_secondary,
    )

    minx, miny, maxx, maxy = view.bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal")
    ax.set_axis_off()
    if title is None:
        title = f"{value.capitalize()} physical cross-border flows, ENTSO-E, {_period_label(year, start, end)}"
    if title:
        ax.set_title(title, loc="left", fontsize=11, color=_text_primary)

    return fig, ax

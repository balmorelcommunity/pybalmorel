"""
ENTSO-E Production Profile

Hourly electricity production per production type, load, net import and
day-ahead price of one or more ENTSO-E bidding zones, read from the csv's
fetched from the ENTSO-E transparency platform. Zones keep ENTSO-E's own
names (e.g. 'DK_1', 'DE_LU', 'IT_NORD'): nothing is translated to Balmorel
regions (see CONTEXT.md).

Created on 05.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from dataclasses import dataclass
from pathlib import Path
import textwrap
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from . import (
    entsoe_subzones,
    get_full_year,
    load_files,
    read_flow_csv,
    read_no_data_zones,
    transmission_files,
    zone_eic_code,
)
from .maps import _period_label, _to_brussels_time, zone_area_name
from ..formatting import fuel_colours, fuel_groups

# ENTSO-E production type -> group drawn in the profile, so at most eight areas
# are stacked. Types not listed here, e.g. 'Fossil Oil', 'Geothermal', 'Marine',
# 'Energy storage', 'Other renewable' and 'Other', are drawn as 'Oil & other'.
production_groups = {
    "Nuclear": "Nuclear",
    "Fossil Hard coal": "Coal & lignite",
    "Fossil Brown coal/Lignite": "Coal & lignite",
    "Fossil Peat": "Coal & lignite",
    "Fossil Oil shale": "Coal & lignite",
    "Fossil Gas": "Gas",
    "Fossil Coal-derived gas": "Gas",
    "Hydro Run-of-river and pondage": "Hydro",
    # Spelling of older entsoe-py versions, still in files fetched with them
    "Hydro Run-of-river and poundage": "Hydro",
    "Hydro Water Reservoir": "Hydro",
    "Hydro Pumped Storage": "Hydro",
    "Biomass": "Biomass & waste",
    "Waste": "Biomass & waste",
    "Wind Onshore": "Wind",
    "Wind Offshore": "Wind",
    "Solar": "Solar",
}
_other_group = "Oil & other"

# Stacked bottom to top in the order of pybalmorel.formatting.fuel_groups, as in
# a Balmorel profile, and drawn in the colour of the group's first Balmorel fuel,
# so a group looks the same as that fuel in a Balmorel fuel profile
# (plot_profile(..., columns='Fuel')). The order keeps neighbouring areas apart
# for colour-blind readers (checked with the dataviz palette validator)
group_colours = {group: fuel_colours[fuels[0]] for group, fuels in fuel_groups.items()}

_net_import_colour = fuel_colours["IMPORT"]
_load_colour = "#0b0b0b"
_price_colour = "#e34948"
_grid_colour = "#e8e6e1"
_text_secondary = "#52514e"
_time_zone = "Europe/Brussels"
# Up to this many hours, stacked areas are separated by a thin white edge;
# over longer periods the edges would cover the areas
_max_hours_with_edges = 14 * 24

# Zones with flow data that lie inside a bidding zone, e.g. LU inside DE_LU
_zones_inside = {"LU": "DE_LU"}

# ------------------------------- #
#          1. Data Loading        #
# ------------------------------- #


@dataclass
class EntsoeProfile:
    """Hourly ENTSO-E data of a set of bidding zones, indexed by hour in Brussels time.

    Args:
        zones (list[str]): entsoe-py area names of the zones, e.g. ['DK_1'].
        generation (pd.DataFrame): Production (MW) per ENTSO-E production type, summed over the zones.
        load (pd.Series): Actual load (MW), summed over the zones.
        price (pd.Series | None): Day-ahead price (€/MWh), weighted by load over the zones
            with prices. None if none of the zones have prices.
        net_import (pd.Series | None): Physical flow into the zones minus out of them (MW),
            leaving out flows between them. None without crossborder_flows csv's for the zones.
    """

    zones: list[str]
    generation: pd.DataFrame
    load: pd.Series
    price: pd.Series | None
    net_import: pd.Series | None


def _selects_all(zones: str | list[str]) -> bool:
    """Whether `zones` is 'all' (or ['all'], as from a comma-separated command line argument)."""
    zone_list = [zones] if isinstance(zones, str) else list(zones)
    return [zone.lower() for zone in zone_list] == ["all"]


def _resolve_zones(zones: str | list[str]) -> dict[str, str]:
    """{EIC code: entsoe-py area name} of `zones`, with a canonical region like 'IT' split into its bidding zones."""
    if isinstance(zones, str):
        zones = [zones]
    resolved = {}
    for zone in zones:
        for subzone in entsoe_subzones(zone):
            eic = zone_eic_code(subzone)
            resolved.setdefault(eic, zone_area_name(eic))
    return resolved


def _zone_files(path: Path, year: int, entsoe_query: str) -> dict[str, Path]:
    """{EIC code: file} of the '<year>_<zone>_<entsoe_query>.csv' files, a zone saved under several spellings read once."""
    if entsoe_query == "load":
        csv_paths = load_files(path, year)
    else:
        csv_paths = sorted(path.glob(f"{year}_*_{entsoe_query}.csv"))
    files = {}
    for csv_path in csv_paths:
        zone = csv_path.name.removeprefix(f"{year}_").removesuffix(f"_{entsoe_query}.csv")
        files.setdefault(zone_eic_code(zone), csv_path)
    return files


def _read_generation_csv(csv_path: Path) -> pd.DataFrame:
    """Hourly mean production (MW) per production type from one generation csv, indexed by UTC time.

    Files with two header rows also hold consumption (e.g. pumping) as 'Actual
    Consumption', which is left out, so only 'Actual Aggregated' is kept.
    """
    with open(csv_path) as csv_file:
        csv_file.readline()
        second_line = csv_file.readline()

    if "Actual Aggregated" in second_line or "Actual Consumption" in second_line:
        df = pd.read_csv(csv_path, header=[0, 1], index_col=0)
        df = df.loc[:, df.columns.get_level_values(1) == "Actual Aggregated"]
        df.columns = df.columns.get_level_values(0)
    else:
        df = pd.read_csv(csv_path, index_col=0)

    df.index = pd.to_datetime(df.index, utc=True)
    return df.resample("1h").mean()


def _read_series_csv(csv_path: Path) -> pd.Series:
    """Hourly mean of the first column of a load or day_ahead_prices csv, indexed by UTC time."""
    series = pd.read_csv(csv_path, index_col=0).iloc[:, 0]
    series.index = pd.to_datetime(series.index, utc=True)
    return series.resample("1h").mean()


_no_data_reason = "ENTSO-E has no data for it"
_not_downloaded_reason = "not downloaded"


def _missing_files(
    zones: dict[str, str], files: dict[str, dict[str, Path]], path: Path, year: int
) -> list[tuple[str, str, str]]:
    """(query, EIC code, reason) of each generation or load csv missing for `zones`."""
    missing = []
    for entsoe_query in ("generation", "load"):
        no_data = {zone_eic_code(zone) for zone in read_no_data_zones(path, year, entsoe_query)}
        for eic in zones:
            if eic not in files[entsoe_query]:
                reason = _no_data_reason if eic in no_data else _not_downloaded_reason
                missing.append((entsoe_query, eic, reason))
    return missing


def _missing_data_message(
    missing: list[tuple[str, str, str]], zones: dict[str, str], path: Path, year: int
) -> str:
    """The error for `missing` csv's (see _missing_files), with the commands that download them."""
    problems = [f"{entsoe_query} of {zones[eic]} ({eic}): {reason}" for entsoe_query, eic, reason in missing]
    message = f"No ENTSO-E data to plot for {year} in '{path}':\n  " + "\n  ".join(problems)
    not_downloaded = [entsoe_query for entsoe_query, _, reason in missing if reason == _not_downloaded_reason]
    for entsoe_query in dict.fromkeys(not_downloaded):
        message += f"\nRun `python -m pybalmorel.backcasting download {path} {year} --query {entsoe_query}`"
    return message


def _zones_with_data(
    files: dict[str, dict[str, Path]], path: Path, year: int
) -> tuple[dict[str, str], dict[str, str]]:
    """The zones of `path` with both generation and load csv's, and why the other zones were left out.

    The other zones are those with only one of the two, or listed in a
    generation or load '_nodata.txt' file.

    Returns:
        tuple[dict[str, str], dict[str, str]]: {EIC code: area name} of the zones with
            both, sorted by name, and {area name: reason} of the zones left out.
    """
    found = set(files["generation"]) | set(files["load"])
    for entsoe_query in ("generation", "load"):
        found |= {zone_eic_code(zone) for zone in read_no_data_zones(path, year, entsoe_query)}
    names = dict(sorted(((eic, zone_area_name(eic)) for eic in found), key=lambda item: item[1]))

    if not names:
        raise Exception(f"No ENTSO-E data to plot for {year} in '{path}': no generation or load csv's")
    missing = _missing_files(names, files, path, year)

    # E.g. {'AL': {'ENTSO-E has no data for it': ['generation']}}
    reasons = {}
    for entsoe_query, eic, reason in missing:
        reasons.setdefault(names[eic], {}).setdefault(reason, []).append(entsoe_query)
    left_out = {
        name: ", ".join(
            f"no {' or '.join(queries)} "
            + ("from ENTSO-E" if reason == _no_data_reason else "downloaded")
            for reason, queries in zone_reasons.items()
        )
        for name, zone_reasons in reasons.items()
    }

    with_data = {eic: name for eic, name in names.items() if name not in left_out}
    if not with_data:
        raise Exception(_missing_data_message(missing, names, path, year))
    return with_data, left_out


def _load_weighted_price(prices: pd.DataFrame, loads: pd.DataFrame) -> pd.Series:
    """The price of each hour, weighted by the load of the zones with both a price and a load that hour."""
    if prices.shape[1] == 1:
        return prices.iloc[:, 0]
    weights = loads[prices.columns].where(prices.notna())
    weighted = (prices * weights).sum(axis=1, min_count=1)
    return weighted / weights.sum(axis=1, min_count=1)


def _format_hours(missing: int, hours: int) -> str:
    """E.g. 'all 168 hours', or '6 of 168 hours missing'."""
    return f"{missing} of {hours} hours missing" if missing else f"all {hours} hours"


def read_profile(
    path: str | Path,
    year: int,
    zones: str | list[str],
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    verbose: bool = True,
) -> EntsoeProfile:
    """Hourly ENTSO-E production, load, net import and day-ahead price of one or more bidding zones.

    Reads the '<year>_<zone>_<query>.csv' files of `path` for the generation,
    load and day_ahead_prices queries, and the crossborder_flows files of the
    borders of the zones. Several zones are summed, except their prices, which
    are weighted by load. An hour missing for any of the zones is NaN in
    the summed generation or load. Generation and load are required for
    every zone; prices and flows are used if they were downloaded. With
    `verbose`, the zones, period and data found are printed.

    Args:
        path (str | Path): Folder with the fetched csv's.
        year (int): The year the files are for.
        zones (str | list[str]): ENTSO-E zone(s) in any spelling, e.g. 'DK1', 'DK_1' or
            '10YDK-1--------W'. A canonical region with several bidding zones, e.g. 'IT',
            means all of them. 'all' means every zone in `path` with generation and load
            in the period; the other zones are left out and listed in the printout.
        start (str | pd.Timestamp | None, optional): First hour to include, read as Brussels
            time unless it has a time zone, e.g. '2023-06-26'. Defaults to None (start of the year).
        end (str | pd.Timestamp | None, optional): Hour to stop before. Defaults to None (end of the year).
        verbose (bool, optional): Print the scope of the data. Defaults to True.

    Raises:
        Exception: If generation or load is missing for any of the zones, in the files
            or in the period. With 'all', if no zone has both.

    Returns:
        EntsoeProfile: The hourly data, indexed by hour in Brussels time.
    """
    path = Path(path)

    # Period, as whole hours
    year_start, year_end = get_full_year(year)
    period_start = _to_brussels_time(start) if start is not None else year_start
    period_end = _to_brussels_time(end) if end is not None else year_end
    if period_start >= period_end:
        raise ValueError(f"start ({period_start}) must be before end ({period_end})")
    hours = pd.date_range(
        period_start.tz_convert("UTC").ceil("1h"),
        period_end.tz_convert("UTC"),
        freq="1h",
        inclusive="left",
    )
    if len(hours) == 0:
        raise ValueError(f"No whole hour between start ({period_start}) and end ({period_end})")

    # Generation and load are required for every zone
    files = {
        entsoe_query: _zone_files(path, year, entsoe_query)
        for entsoe_query in ("generation", "load", "day_ahead_prices")
    }
    select_all = _selects_all(zones)
    if select_all:
        zone_names, left_out = _zones_with_data(files, path, year)
    else:
        zone_names, left_out = _resolve_zones(zones), {}
        missing = _missing_files(zone_names, files, path, year)
        if missing:
            raise Exception(_missing_data_message(missing, zone_names, path, year))

    generation = {
        eic: _read_generation_csv(files["generation"][eic]).reindex(hours) for eic in zone_names
    }
    loads = {eic: _read_series_csv(files["load"][eic]).reindex(hours) for eic in zone_names}
    period = _period_label(year, start, end)
    empty = {}
    for eic in zone_names:
        for entsoe_query, values in (("generation", generation[eic]), ("load", loads[eic])):
            if values.isna().all(axis=None):
                empty.setdefault(eic, []).append(entsoe_query)
    if empty and not select_all:
        raise Exception(
            f"No ENTSO-E data in '{path}' for {period}: "
            + ", ".join(f"{entsoe_query} of {zone_names[eic]}" for eic in empty for entsoe_query in empty[eic])
        )
    if empty:
        # With 'all', zones without data in the period are left out
        for eic, queries in empty.items():
            left_out[zone_names.pop(eic)] = f"no {' or '.join(queries)} in the period"
            generation.pop(eic)
            loads.pop(eic)
        if not zone_names:
            raise Exception(f"No ENTSO-E data in '{path}' for {period}")
    loads = pd.DataFrame(loads, index=hours)

    # Summed over the zones, NaN in hours missing for any of them
    generation_missing = pd.DataFrame(
        {eic: zone_generation.isna().all(axis=1) for eic, zone_generation in generation.items()}
    )
    generation_sum = pd.concat(generation.values(), axis=1).T.groupby(level=0).sum(min_count=1).T
    generation_sum.loc[generation_missing.any(axis=1)] = np.nan
    load_missing = loads.isna()
    load = loads.sum(axis=1).where(~load_missing.any(axis=1))

    # Prices, if downloaded for any of the zones
    price_zones = [eic for eic in zone_names if eic in files["day_ahead_prices"]]
    prices = pd.DataFrame(
        {eic: _read_series_csv(files["day_ahead_prices"][eic]).reindex(hours) for eic in price_zones},
        index=hours,
    ).dropna(axis=1, how="all")
    price = _load_weighted_price(prices, loads) if prices.shape[1] > 0 else None

    # Net import over the borders with zones outside the selection. A flow
    # between a selected zone and a zone inside another selected zone (e.g.
    # BE-LU with DE_LU selected) is internal too.
    inside = {zone_eic_code(zone): zone_eic_code(container) for zone, container in _zones_inside.items()}
    net_import = pd.Series(0.0, index=hours)
    neighbours = set()
    for (zone_from, zone_to), csv_path in transmission_files(path, year).items():
        if (zone_from in zone_names) == (zone_to in zone_names):
            continue
        if inside.get(zone_from, zone_from) in zone_names and inside.get(zone_to, zone_to) in zone_names:
            continue
        flow = read_flow_csv(csv_path).reindex(hours).fillna(0)
        if zone_to in zone_names:
            net_import += flow
            neighbours.add(zone_area_name(zone_from))
        else:
            net_import -= flow
            neighbours.add(zone_area_name(zone_to))
    if not neighbours:
        net_import = None

    profile = EntsoeProfile(
        zones=list(zone_names.values()),
        generation=generation_sum.tz_convert(_time_zone),
        load=load.tz_convert(_time_zone),
        price=price.tz_convert(_time_zone) if price is not None else None,
        net_import=net_import.tz_convert(_time_zone) if net_import is not None else None,
    )

    if verbose:
        _print_scope(
            profile,
            zone_names,
            left_out,
            files,
            prices.columns,
            hours,
            {"generation": generation_missing, "load": load_missing},
            neighbours,
            year,
        )

    return profile


def _scope_line(label: str, text: str) -> list[str]:
    """A line of the scope printout, wrapped below its text column."""
    return textwrap.wrap(
        text,
        width=100,
        initial_indent=f"  {label:<13}",
        subsequent_indent=" " * 15,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _missing_by_zone(missing: pd.DataFrame, zone_names: dict[str, str]) -> str:
    """E.g. 'missing for BA (414), MK (96) and 3 more zones', the zones with most missing hours first."""
    counts = missing.sum().sort_values(ascending=False, kind="stable")
    counts = counts[counts > 0]
    shown = [f"{zone_names[eic]} ({count})" for eic, count in counts.iloc[:5].items()]
    more = f" and {len(counts) - 5} more zones" if len(counts) > 5 else ""
    return "missing for " + ", ".join(shown) + more


def _print_scope(
    profile: EntsoeProfile,
    zone_names: dict[str, str],
    left_out: dict[str, str],
    files: dict[str, dict[str, Path]],
    price_zones: pd.Index,
    hours: pd.DatetimeIndex,
    missing: dict[str, pd.DataFrame],
    neighbours: set[str],
    year: int,
) -> None:
    """Print which zones, hours and data a profile covers."""

    def file_names(entsoe_query: str) -> str:
        names = [files[entsoe_query][eic].name for eic in zone_names if eic in files[entsoe_query]]
        return ", ".join(names) if len(names) <= 3 else f"{len(names)} files"

    def missing_hours(entsoe_query: str) -> list[str]:
        """How many hours are missing, and for which zones if several."""
        zone_missing = missing[entsoe_query]
        lines = []
        if len(zone_names) > 1 and zone_missing.any(axis=None):
            lines = _scope_line("", _missing_by_zone(zone_missing, zone_names))
        return [_format_hours(int(zone_missing.any(axis=1).sum()), len(hours))] + lines

    if len(zone_names) <= 3:
        zones_text = ", ".join(f"{name} ({eic})" for eic, name in zone_names.items())
    else:
        zones_text = f"{len(zone_names)} zones: " + ", ".join(zone_names.values())
    local = hours.tz_convert(_time_zone)
    time_format = "%Y-%m-%d %H:%M"
    end_local = local[-1] + pd.Timedelta(hours=1)
    end_utc = hours[-1] + pd.Timedelta(hours=1)
    generation_hours, *generation_zones = missing_hours("generation")
    load_hours, *load_zones = missing_hours("load")
    lines = (
        ["ENTSO-E profile scope"]
        + _scope_line("Zones:", zones_text)
        + (
            _scope_line("Left out:", ", ".join(f"{name} ({reason})" for name, reason in left_out.items()))
            if left_out
            else []
        )
        + [
            f"  Period:      {local[0].strftime(time_format)} to {end_local.strftime(time_format)} "
            f"Europe/Brussels ({len(hours)} hours)",
            f"               = {hours[0].strftime(time_format)} to {end_utc.strftime(time_format)} UTC",
            f"  Generation:  {file_names('generation')} - {profile.generation.shape[1]} production types, "
            + generation_hours,
            *generation_zones,
            f"  Load:        {file_names('load')} - {load_hours}",
            *load_zones,
        ]
    )

    # Price
    without_price = [name for eic, name in zone_names.items() if eic not in price_zones]
    if profile.price is None:
        lines += _scope_line("Price:", f"none for {', '.join(without_price)} - plotted without price")
    else:
        weighting = "" if len(price_zones) == 1 else f", load-weighted over {len(price_zones)} zones"
        lines.append(
            f"  Price:       {file_names('day_ahead_prices')}{weighting} - "
            + _format_hours(int(profile.price.isna().sum()), len(hours))
        )
        if without_price:
            lines += _scope_line("", f"no prices for {', '.join(without_price)}")

    # Net import and energy balance, over the hours with both generation and load
    complete = ~(missing["generation"].any(axis=1) | missing["load"].any(axis=1)).to_numpy()
    if profile.net_import is None:
        lines.append(f"  Net import:  no {year} crossborder_flows csv's for the zones - plotted without")
        net_import_energy = 0.0
    else:
        lines += _scope_line("Net import:", f"borders with {', '.join(sorted(neighbours))}")
        net_import_energy = profile.net_import[complete].sum()
    lines += _scope_line(
        "Energy:",
        f"generation {profile.generation[complete].sum().sum() / 1e3:,.0f} GWh, "
        f"net import {net_import_energy / 1e3:,.0f} GWh, load {profile.load[complete].sum() / 1e3:,.0f} GWh",
    )
    if not complete.all():
        lines += _scope_line("", f"over the {complete.sum()} hours with generation and load of every zone")

    # The load of a bidding zone can be fetched for a smaller area (see load_zones)
    for eic, name in zone_names.items():
        load_zone = files["load"][eic].name.removeprefix(f"{year}_").removesuffix("_load.csv")
        if zone_area_name(load_zone) != name:
            lines.append(
                f"  Note:        load of {name} is for {load_zone} only (see pybalmorel.entsoe.load_zones)"
            )

    print("\n".join(lines))


# ------------------------------- #
#            2. Plotting          #
# ------------------------------- #


def _group_production(generation: pd.DataFrame) -> pd.DataFrame:
    """Production (MW) per group of `group_colours`, in stacking order, without empty groups.

    A group without data in an hour counts as 0, unless no type has data that
    hour: then the hour stays NaN, so it is drawn as a gap rather than a dip to 0.
    """
    grouped = generation.T.groupby(
        lambda production_type: production_groups.get(production_type, _other_group)
    ).sum(min_count=1).T
    grouped = grouped.reindex(columns=[group for group in group_colours if group in grouped.columns])
    grouped = grouped.loc[:, grouped.fillna(0).abs().sum() > 0]
    return grouped.fillna(0).where(grouped.notna().any(axis=1), np.nan)


def _style_axes(ax: Axes) -> None:
    """Recessive axes: no top or right spine, hairline horizontal grid behind the data."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_grid_colour)
    ax.tick_params(colors=_text_secondary, which="both")
    ax.grid(axis="y", color=_grid_colour, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_profile(
    path: str | Path,
    year: int,
    zones: str | list[str],
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    title: str | None = None,
) -> tuple[Figure, np.ndarray]:
    """Plot the hourly ENTSO-E production, load, net import and day-ahead price of one or more bidding zones.

    Production is stacked per group of production types (see
    `production_groups`), with net import on top and net export below zero,
    and load drawn as a line. The day-ahead price, if downloaded, is drawn
    in a panel below. Hours without data are left as gaps. Raises if
    generation or load of any of the zones is missing, and prints the zones,
    period and data found (see `read_profile`).

    Args:
        path (str | Path): Folder with the fetched csv's.
        year (int): The year the files are for.
        zones (str | list[str]): ENTSO-E zone(s) in any spelling, e.g. 'DK1', 'DK_1' or
            '10YDK-1--------W'. A canonical region with several bidding zones, e.g. 'IT',
            means all of them. 'all' means every zone in `path` with generation and load.
        start (str | pd.Timestamp | None, optional): First hour to plot, read as Brussels
            time unless it has a time zone, e.g. '2023-06-26'. Defaults to None (start of the year).
        end (str | pd.Timestamp | None, optional): Hour to stop before, e.g. '2023-07-03'.
            Defaults to None (end of the year).
        title (str | None, optional): Defaults to None (the zones and period).

    Returns:
        tuple[Figure, np.ndarray]: The figure, and its axes: production, then price if plotted.
    """
    profile = read_profile(path, year, zones, start, end)

    if profile.price is None:
        fig, axes = plt.subplots(figsize=(10, 3.6), layout="constrained")
        axes = np.array([axes])
    else:
        fig, axes = plt.subplots(
            2, 1, figsize=(10, 5), sharex=True, height_ratios=[3, 1], layout="constrained"
        )

    # Matplotlib dates are UTC, shown in Brussels time by the tick formatter
    time = profile.load.index.tz_convert("UTC").tz_localize(None).to_numpy()
    short_period = len(time) <= _max_hours_with_edges
    edges = {"edgecolor": "white", "linewidth": 0.4} if short_period else {"linewidth": 0}
    line_width = 1.5 if short_period else 0.6
    ax = axes[0]
    grouped = _group_production(profile.generation) / 1e3
    ax.stackplot(
        time,
        grouped.T.to_numpy(),
        labels=grouped.columns,
        colors=[group_colours[group] for group in grouped.columns],
        **edges,
    )
    if profile.net_import is not None:
        net_import = profile.net_import.to_numpy() / 1e3
        top = grouped.sum(axis=1, min_count=1).to_numpy()
        ax.fill_between(
            time,
            top,
            top + np.clip(net_import, 0, None),
            facecolor=_net_import_colour,
            label="Net import (export below 0)",
            **edges,
        )
        ax.fill_between(time, 0, np.clip(net_import, None, 0), facecolor=_net_import_colour, **edges)
        ax.axhline(0, color=_text_secondary, linewidth=0.8)
    ax.plot(time, profile.load.to_numpy() / 1e3, color=_load_colour, linewidth=line_width, label="Load")
    ax.set_ylabel("Power [GW]")

    # Legend in stacking order, top first, beside the plot
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)

    if profile.price is not None:
        axes[1].plot(time, profile.price.to_numpy(), color=_price_colour, linewidth=line_width)
        price_name = "Price" if len(profile.zones) == 1 else "Load-weighted price"
        axes[1].set_ylabel(f"{price_name}\n[€/MWh]")

    for ax in axes:
        _style_axes(ax)
        ax.set_xlim(time[0], time[-1])
    locator = mdates.AutoDateLocator(tz=_time_zone)
    axes[-1].xaxis.set_major_locator(locator)
    axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=_time_zone))

    if title is None:
        if _selects_all(zones):
            zone_label = "All zones"
        else:
            zone_label = zones if isinstance(zones, str) else " + ".join(zones)
        title = f"{zone_label} - ENTSO-E - {_period_label(year, start, end)}"
    axes[0].set_title(title, loc="left")

    return fig, axes

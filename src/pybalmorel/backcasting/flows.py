"""
Flows

Analyse transmission flows in ENTSO-E data: the Observed Flow Limit XKFX
overrides (docs/adr/0005, 0006, 0010) and the validation of Balmorel's flows
against ENTSO-E's, both aggregated to Canonical Region Names (see CONTEXT.md)

Created on 09.07.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from warnings import warn
from itertools import product
from matplotlib.figure import Figure
from ..entsoe import (
    bidding_zone_translation,
    entsoe_subzones,
    fetch_annual_transmission_data,
    find_transmission_file,
    region_to_entsoe_code,
    transmission_files,
    zone_to_region,
)
from ..classes import Balmorel, IncFile
from .calendar import backcast_hours, from_backcast_grid

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

OBSERVED_FLOW_PERCENTILE = 99.0


def read_flow_csv(csv_path: str | Path) -> pd.Series:
    """Hourly mean flow (MW) from one fetched crossborder_flows csv, indexed by UTC time.

    Args:
        csv_path (str | Path): The csv.

    Returns:
        pd.Series: Hourly flows.
    """
    temp = pd.read_csv(csv_path)
    temp.columns = ["Time", "Value"]
    temp.Time = pd.to_datetime(temp.Time, utc=True)
    return temp.set_index("Time")["Value"].resample("1h").mean()


# ------------------------------- #
#   2. XKFX overrides (backcast)  #
# ------------------------------- #


def get_current_borders(
    balmorel_model_folder: str | Path,
    scenario: str,
    gams_system_directory: str | None = None,
) -> pd.DataFrame:
    """The non-zero XKFX borders currently defined for a Balmorel scenario.

    Reads XKFX through GAMS (via Balmorel.load_incfiles/.get_input) rather than
    parsing XKFX.inc, since it is a hand-formatted GAMS TABLE not safe to parse
    with a text-based parser (see docs/adr/0006).

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to read XKFX from.
        gams_system_directory (str | None, optional): GAMS system directory.

    Returns:
        pd.DataFrame: Columns 'RegionFrom', 'RegionTo' for every non-zero border.
    """
    m = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    m.load_incfiles(scenario)
    xkfx = m.get_input("XKFX")

    value_col = xkfx.columns[-1]
    region_from_col, region_to_col = xkfx.columns[-3], xkfx.columns[-2]

    xkfx = xkfx[xkfx[value_col].astype(float) != 0]
    borders = xkfx[[region_from_col, region_to_col]].drop_duplicates()
    borders.columns = ["RegionFrom", "RegionTo"]

    return borders.reset_index(drop=True)


def compute_entsoe_transmission_overrides(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    api_key: str,
    gams_system_directory: str | None = None,
    percentile: float = OBSERVED_FLOW_PERCENTILE,
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Compute Observed Flow Limit XKFX overrides for a Balmorel scenario's borders.

    Borders are read from the scenario's current XKFX (see get_current_borders).
    Internal links that ENTSO-E can't distinguish (both sides sharing a canonical
    name, e.g. DE4-N <-> DE4-W) are left out untouched, per docs/adr/0006. Where
    several ENTSO-E zones collapse to one Balmorel region, their flows are summed
    hour by hour before the percentile is taken (see observed_flow_limits); where
    several Balmorel regions collapse to one ENTSO-E zone, the limit is split
    evenly across them.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to read/derive borders for.
        year (int): The backcast target year.
        entsoe_data_path (str | Path): Folder to fetch/read ENTSO-E csv's from.
        api_key (str): ENTSO-E transparency platform API key.
        gams_system_directory (str | None, optional): GAMS system directory.
        percentile (float, optional): Percentile of the hourly flow, in percent.
            100 gives the maximum. Defaults to OBSERVED_FLOW_PERCENTILE.

    Returns:
        tuple[pd.DataFrame, list[tuple[str, str]]]: Overrides (Year, RegionFrom,
            RegionTo, Value) and the ENTSO-E zone pairs that could not be fetched.
    """
    borders = get_current_borders(
        balmorel_model_folder, scenario, gams_system_directory
    )

    borders["CanonicalFrom"] = borders.RegionFrom.map(
        lambda r: bidding_zone_translation.get(r, r)
    )
    borders["CanonicalTo"] = borders.RegionTo.map(
        lambda r: bidding_zone_translation.get(r, r)
    )

    # Drop internal links ENTSO-E can't distinguish (e.g. DE4-N <-> DE4-W)
    borders = borders[borders.CanonicalFrom != borders.CanonicalTo]

    canonical_pairs = borders[["CanonicalFrom", "CanonicalTo"]].drop_duplicates()
    fetch_pairs = []
    for canon_from, canon_to in canonical_pairs.itertuples(index=False):
        from_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_from)]
        to_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_to)]
        fetch_pairs += list(product(from_codes, to_codes))
    fetch_pairs = list(dict.fromkeys(fetch_pairs))  # de-duplicate, keep order

    entsoe_data_path = Path(entsoe_data_path)
    entsoe_data_path.mkdir(parents=True, exist_ok=True)
    fetch_annual_transmission_data(
        "crossborder_flows", fetch_pairs, year, str(entsoe_data_path), api_key
    )

    limits = observed_flow_limits(entsoe_data_path, year, percentile)

    failed_pairs = []
    results = []
    for (canon_from, canon_to), group in borders.groupby(
        ["CanonicalFrom", "CanonicalTo"]
    ):
        from_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_from)]
        to_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_to)]

        any_succeeded = False
        for region_from, region_to in product(from_codes, to_codes):
            if find_transmission_file(entsoe_data_path, year, region_from, region_to) is None:
                failed_pairs.append((region_from, region_to))
            else:
                any_succeeded = True

        if not any_succeeded:
            continue

        total = limits.get((canon_from, canon_to), 0.0)

        split_factor = len(group)
        value_per_border = total / split_factor
        for row in group.itertuples():
            results.append(
                {
                    "Year": year,
                    "RegionFrom": row.RegionFrom,
                    "RegionTo": row.RegionTo,
                    "Value": value_per_border,
                }
            )

    return pd.DataFrame(results), list(dict.fromkeys(failed_pairs))


def write_xkfx_override(
    overrides: pd.DataFrame,
    scenario_data_path: str | Path,
    percentile: float = OBSERVED_FLOW_PERCENTILE,
) -> IncFile:
    """Write XKFX_ENTSOE.inc with the ENTSO-E-derived transmission overrides.

    Args:
        overrides (pd.DataFrame): Output of compute_entsoe_transmission_overrides.
        scenario_data_path (str | Path): The scenario's 'data' folder.
        percentile (float, optional): The percentile the overrides were computed
            with, written in the file header. Defaults to OBSERVED_FLOW_PERCENTILE.

    Returns:
        IncFile: The saved IncFile instance.
    """
    body = "".join(
        f"XKFX('{int(row.Year)}','{row.RegionFrom}','{row.RegionTo}')={row.Value:.1f};\n"
        for row in overrides.itertuples()
    )

    inc_file = IncFile(
        prefix=(
            f"* Transmission limits: ENTSO-E Observed Flow Limit, the {percentile:g}th percentile "
            "of hourly flow over the hours with flow, summed per canonical border\n"
            "* (see CONTEXT.md and docs/adr/0005, 0006, 0010) - generated, do not hand-edit\n"
        ),
        body=body,
        suffix="",
        name="XKFX_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def append_xkfx_include(xkfx_inc_path: str | Path) -> None:
    """Idempotently append the scenario-fallback $include for XKFX_ENTSOE.inc.

    Args:
        xkfx_inc_path (str | Path): Path to the scenario's XKFX.inc.
    """
    xkfx_inc_path = Path(xkfx_inc_path)
    content = xkfx_inc_path.read_text()

    if "XKFX_ENTSOE.inc" in content:
        return

    include_block = (
        "\n"
        "$if     EXIST '../data/XKFX_ENTSOE.inc' $INCLUDE         '../data/XKFX_ENTSOE.inc';\n"
        "$if not EXIST '../data/XKFX_ENTSOE.inc' $INCLUDE '../../base/data/XKFX_ENTSOE.inc';\n"
    )

    with open(xkfx_inc_path, "a") as f:
        f.write(include_block)


def generate_transmission_flow_limit_overrides(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    api_key: str,
    gams_system_directory: str | None = None,
    percentile: float = OBSERVED_FLOW_PERCENTILE,
) -> None:
    """Fetch ENTSO-E flows and write the XKFX_ENTSOE.inc backcast overrides.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to generate overrides for.
        year (int): The backcast target year.
        entsoe_data_path (str | Path): Folder to fetch/read ENTSO-E csv's from.
        api_key (str): ENTSO-E transparency platform API key.
        gams_system_directory (str | None, optional): GAMS system directory.
        percentile (float, optional): Percentile of the hourly flow, in percent.
            100 gives the maximum. Defaults to OBSERVED_FLOW_PERCENTILE.
    """
    overrides, failed_pairs = compute_entsoe_transmission_overrides(
        balmorel_model_folder,
        scenario,
        year,
        entsoe_data_path,
        api_key,
        gams_system_directory,
        percentile,
    )

    if failed_pairs:
        warn(
            f"Could not fetch ENTSO-E data for {len(failed_pairs)} zone pair(s): "
            f"{failed_pairs}. These were left out of XKFX_ENTSOE.inc - fix the "
            "zone-code mapping or proceed with the borders that were available."
        )

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    write_xkfx_override(overrides, scenario_data_path, percentile)
    append_xkfx_include(scenario_data_path / "XKFX.inc")


# ------------------------------- #
#      3. Flow validation         #
# ------------------------------- #

def canonical_region(name: str) -> str:
    """The Canonical Region Name of a Balmorel region or any ENTSO-E zone spelling."""
    region = zone_to_region(name)
    return bidding_zone_translation.get(region, region)


def load_entsoe_flows(entsoe_data_path: str | Path, year: int) -> pd.DataFrame:
    """Hourly ENTSO-E physical flows per directed canonical border.

    Each file is resampled to hourly means (MW, i.e. MWh per hour), then
    summed over every ENTSO-E zone pair that collapses to the same canonical
    border (e.g. the Italian sub-zones). Internal links, where both sides
    share a canonical name, are dropped. A pair fetched under several zone
    spellings (e.g. 'DK_1' and '10YDK-1--------W') is read once.

    Args:
        entsoe_data_path (str | Path): Folder with the fetched crossborder_flows csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Columns 'From', 'To', 'Time' (UTC) and 'Value', restricted
            to the Backcast Calendar.
    """
    hours = backcast_hours(year)
    flows = []
    for zones, csv_path in transmission_files(entsoe_data_path, year).items():
        region_from, region_to = (canonical_region(zone) for zone in zones)
        if region_from == region_to:
            continue

        temp = read_flow_csv(csv_path).reset_index()
        temp = temp[temp.Time.isin(hours)]
        temp["From"], temp["To"] = region_from, region_to
        flows.append(temp)

    if not flows:
        return pd.DataFrame(columns=["From", "To", "Time", "Value"])

    return (
        pd.concat(flows, ignore_index=True)
        .groupby(["From", "To", "Time"], as_index=False)["Value"]
        .sum(min_count=1)
    )


def observed_flow_limits(
    entsoe_data_path: str | Path, year: int, percentile: float = OBSERVED_FLOW_PERCENTILE
) -> pd.Series:
    """The Observed Flow Limit per directed canonical border (see CONTEXT.md, ADR 0010).

    The percentile is taken over the hours with flow in that direction, on the
    hourly series summed over every ENTSO-E zone pair of the border (see
    load_entsoe_flows). Over all hours, a rarely used direction would get a
    limit near 0. A direction without any flowing hour gets 0.

    Args:
        entsoe_data_path (str | Path): Folder with the fetched crossborder_flows csv's.
        year (int): The Backcast Year.
        percentile (float, optional): Percentile of the hourly flow, in percent.
            100 gives the maximum. Defaults to OBSERVED_FLOW_PERCENTILE.

    Returns:
        pd.Series: Limit in MW, indexed by ('From', 'To').
    """
    flows = load_entsoe_flows(entsoe_data_path, year)
    borders = pd.MultiIndex.from_frame(
        flows[["From", "To"]].drop_duplicates(), names=["From", "To"]
    )
    limits = (
        flows[flows["Value"] > 0]
        .groupby(["From", "To"])["Value"]
        .quantile(percentile / 100)
    )

    return limits.reindex(borders, fill_value=0.0).astype(float).rename("Limit")


def format_balmorel_flows(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Hourly Balmorel flows per directed canonical border.

    Args:
        df (pd.DataFrame): X_FLOW_YCRST from MainResults ('From', 'To',
            'Season', 'Time', 'Value').
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Columns 'Time' (UTC), 'From', 'To' and 'Value'.
    """
    df = df.copy()
    df["From"] = df["From"].map(canonical_region)
    df["To"] = df["To"].map(canonical_region)
    df = df[df["From"] != df["To"]]
    df = df.groupby(["From", "To", "Season", "Time"], as_index=False)["Value"].sum()

    return from_backcast_grid(df, year)


def align_flows(
    entsoe_flows: pd.DataFrame,
    balmorel_flows: pd.DataFrame,
    limits: pd.Series | None = None,
) -> pd.DataFrame:
    """Join ENTSO-E and Balmorel flows on every border both datasets know.

    A border counts as known to Balmorel if it appears in either direction in
    its results. Hours Balmorel leaves out of the GDX are zero flow, so they
    are filled with 0 rather than dropped - dropping them would bias every
    statistic towards the hours Balmorel used the border.

    Args:
        entsoe_flows (pd.DataFrame): Output of load_entsoe_flows.
        balmorel_flows (pd.DataFrame): Output of format_balmorel_flows.
        limits (pd.Series | None, optional): Observed Flow Limit per border (see
            observed_flow_limits), added as a 'Limit' column. Defaults to None.

    Returns:
        pd.DataFrame: Index ('From', 'To', 'Time'), columns 'ENTSOE', 'BALMOREL'
            and, if limits are given, 'Limit'.
    """
    balmorel_links = {
        frozenset(border)
        for border in balmorel_flows[["From", "To"]].itertuples(index=False)
    }
    entsoe_flows = entsoe_flows[
        [
            frozenset(border) in balmorel_links
            for border in entsoe_flows[["From", "To"]].itertuples(index=False)
        ]
    ]
    missing = balmorel_links.difference(
        frozenset(border) for border in entsoe_flows[["From", "To"]].itertuples(index=False)
    )
    if missing:
        warn(
            f"These Balmorel borders have no ENTSO-E flow data and are left out: "
            f"{sorted('-'.join(sorted(link)) for link in missing)}"
        )

    index = ["From", "To", "Time"]
    flows = (
        entsoe_flows.set_index(index)
        .rename(columns={"Value": "ENTSOE"})
        .join(
            balmorel_flows.set_index(index).rename(columns={"Value": "BALMOREL"}),
            how="left",
        )
    )
    flows["BALMOREL"] = flows["BALMOREL"].fillna(0.0)
    if limits is not None:
        flows = flows.join(limits, on=["From", "To"])

    return flows.dropna(subset=["ENTSOE"])


def flow_statistics(flows: pd.DataFrame, tolerance: float = 0.01) -> pd.DataFrame:
    """Per-border comparison of Balmorel and ENTSO-E flows.

    Args:
        flows (pd.DataFrame): Output of align_flows, optionally with a 'Limit'
            column (Observed Flow Limit, see observed_flow_limits).
        tolerance (float, optional): Relative distance to the limit that still
            counts as 'at the limit'. Defaults to 0.01.

    Returns:
        pd.DataFrame: Indexed by ('From', 'To'), with annual energy (TWh),
            correlation, RMSE (MW) and, if 'Limit' is given, the share of
            hours at the limit in each dataset.
    """
    grouped = flows.groupby(level=["From", "To"])
    stats = pd.DataFrame(
        {
            "ENTSOE_TWh": grouped["ENTSOE"].sum() / 1e6,
            "BALMOREL_TWh": grouped["BALMOREL"].sum() / 1e6,
            "Correlation": grouped.apply(lambda df: df["ENTSOE"].corr(df["BALMOREL"])),
            "RMSE_MW": grouped.apply(
                lambda df: np.sqrt(((df["BALMOREL"] - df["ENTSOE"]) ** 2).mean())
            ),
        }
    )

    if "Limit" in flows.columns:
        limited = flows[flows["Limit"].gt(0)]
        at_limit = limited[["ENTSOE", "BALMOREL"]].ge(
            limited["Limit"] * (1 - tolerance), axis=0
        )
        shares = at_limit.groupby(level=["From", "To"]).mean()
        stats["Limit_MW"] = limited.groupby(level=["From", "To"])["Limit"].first()
        stats["ENTSOE_AtLimit"] = shares["ENTSOE"]
        stats["BALMOREL_AtLimit"] = shares["BALMOREL"]

    return stats


def plot_flow_duration_curves(flows: pd.DataFrame, ncols: int = 6) -> tuple[Figure, np.ndarray]:
    """Duration curves of ENTSO-E and Balmorel flows, one subplot per directed border.

    Args:
        flows (pd.DataFrame): Output of align_flows.
        ncols (int, optional): Subplot columns. Defaults to 6.

    Returns:
        tuple[Figure, np.ndarray]: The figure and its axes.
    """
    borders = flows.index.droplevel("Time").unique()
    nrows = int(np.ceil(len(borders) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(3 * ncols, 2.2 * nrows), squeeze=False, sharex=True
    )

    for ax, (region_from, region_to) in zip(axes.flat, borders):
        border = flows.loc[(region_from, region_to)]
        for source in ["ENTSOE", "BALMOREL"]:
            curve = np.sort(border[source].to_numpy())[::-1]
            ax.plot(np.linspace(0, 100, len(curve)), curve, label=source)
        ax.set_title(f"{region_from} → {region_to}", fontsize=9)
    for ax in axes.flat[len(borders) :]:
        ax.set_visible(False)

    axes[0, 0].legend(fontsize=8)
    fig.supxlabel("Share of hours (%)")
    fig.supylabel("Flow (MW)")
    fig.tight_layout()

    return fig, axes

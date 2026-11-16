"""
Transmission Availability

Turn ENTSO-E's transmission outage reports into weekly XKRATE overrides
(XKRATE_ENTSOE.inc) for a Backcast: per direction of a canonical border and
Backcast Calendar week, the mean over the week of the capacity the reports
leave in service, capped at the Observed Flow Limit, as a share of that limit
(see CONTEXT.md and docs/adr/0016).

Only directions whose reports describe the whole border are rated: the
largest capacity reported is at least half the Observed Flow Limit (smaller
values describe a single line of the border), the border is not in Core's
flow-based market coupling, and observed flow did not exceed the reported
capacity in a fifth or more of the outage hours. Every other direction keeps
a rating of 1. Observed flows, a Validation Metric, never set a rating; they
only decide once per direction whether its reports are credible.

Created on 16.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from pathlib import Path
from warnings import warn

import numpy as np
import pandas as pd

from ..classes import IncFile
from ..entsoe import TRANSMISSION_OUTAGES, transmission_files
from .calendar import N_SEASONS, backcast_hours, first_monday
from .flows import canonical_region, load_entsoe_flows
from .nuclear import format_rating
from .thermal import OUTAGE_KINDS, VOID_DOCSTATUS, load_scenario_input

# Reports are at minute resolution, and so is the remaining capacity
MINUTE = pd.Timedelta(minutes=1)
MINUTES_PER_WEEK = 7 * 24 * 60

# Countries in Core's flow-based day-ahead market coupling in 2023 (since
# June 2022). Their reports on Core borders are regional or empty, as the
# capacity between them is set by the flow-based parameters.
CORE_FLOW_BASED = frozenset(
    {"AT", "BE", "CZ", "DE", "FR", "HR", "HU", "NL", "PL", "RO", "SI", "SK"}
)

# The largest reported capacity, as a share of the Observed Flow Limit, below
# which a direction's reports describe single lines, not the border
MIN_REPORTED_SHARE = 0.5

# The share of outage hours in which observed flow may exceed the reported
# capacity before a direction's reports are not credible
MAX_EXCEEDED_SHARE = 0.2

# Flow exceeds the reported capacity by more than the larger of these
EXCEEDED_TOLERANCE_MW = 10.0
EXCEEDED_TOLERANCE_SHARE = 0.02  # of the largest reported capacity

XKRATE_ENTSOE_INCLUDE = "$if EXIST '../data/XKRATE_ENTSOE.inc' $INCLUDE '../data/XKRATE_ENTSOE.inc';"

BORDER_COLUMNS = [
    "From",
    "To",
    "Limit",
    "Events",
    "Planned",
    "Forced",
    "LargestReported",
    "ReportedShare",
    "CoreFlowBased",
    "EventHours",
    "ExceededShare",
    "MeanRating",
    "MinRating",
    "Rated",
    "Reason",
    "Assets",
]

# ------------------------------- #
#        1. ENTSO-E reports       #
# ------------------------------- #


def load_transmission_outages(entsoe_data_path: str | Path, year: int) -> pd.DataFrame:
    """ENTSO-E's transmission outage reports of `year`, with the zones and canonical border of each file.

    Files of an internal border, whose zones share a canonical region (e.g.
    the Italian zones), are left out.

    Args:
        entsoe_data_path (str | Path): Folder with the unavailability_of_transmission csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: The reports as fetch_annual_transmission_outages saves
            them, plus 'ZoneFrom' and 'ZoneTo' (EIC codes) and 'From' and 'To'
            (canonical regions). Empty if there are no files.
    """
    frames = []
    for (zone_from, zone_to), path in transmission_files(entsoe_data_path, year, TRANSMISSION_OUTAGES).items():
        region_from, region_to = canonical_region(zone_from), canonical_region(zone_to)
        if region_from == region_to:
            continue
        df = pd.read_csv(path)
        df["ZoneFrom"], df["ZoneTo"] = zone_from, zone_to
        df["From"], df["To"] = region_from, region_to
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def latest_events(outages: pd.DataFrame) -> pd.DataFrame:
    """The periods of the latest revision of every outage event, without cancelled or withdrawn events.

    Exact duplicate rows are dropped first, as are time series of another
    direction than their file's and periods without a capacity (the
    flow-based borders' reports).

    Args:
        outages (pd.DataFrame): Output of load_transmission_outages.

    Returns:
        pd.DataFrame: Columns 'From', 'To', 'ZoneFrom', 'ZoneTo', 'Event'
            (the report's mRID), 'Kind' ('Planned' or 'Forced'), 'Start',
            'End' (UTC), 'Available' (MW the border keeps in service) and
            'Asset', one row per period of an event.
    """
    columns = ["From", "To", "ZoneFrom", "ZoneTo", "Event", "Kind", "Start", "End", "Available", "Asset"]
    if outages.empty:
        return pd.DataFrame(columns=columns)

    outages = outages.drop_duplicates()
    latest = outages.groupby(["ZoneFrom", "ZoneTo", "mrid"])["revision"].transform("max")
    events = outages[
        (outages["revision"] == latest)
        & ~outages["docstatus"].isin(VOID_DOCSTATUS)
        & (outages["out_domain"] == outages["ZoneFrom"])
        & (outages["in_domain"] == outages["ZoneTo"])
    ].dropna(subset=["start", "end", "avail_qty"])

    return pd.DataFrame(
        {
            "From": events["From"],
            "To": events["To"],
            "ZoneFrom": events["ZoneFrom"],
            "ZoneTo": events["ZoneTo"],
            "Event": events["mrid"],
            "Kind": events["businesstype"].map(OUTAGE_KINDS).fillna("Forced"),
            "Start": pd.to_datetime(events["start"], utc=True),
            "End": pd.to_datetime(events["end"], utc=True),
            "Available": events["avail_qty"].astype(float),
            "Asset": events["asset_name"],
        }
    )[columns].reset_index(drop=True)


# ------------------------------- #
#     2. Remaining capacity       #
# ------------------------------- #


def _minute_index(times: pd.Series, calendar_start: pd.Timestamp, n_minutes: int, rounding) -> np.ndarray:
    minutes = ((times - calendar_start) / MINUTE).to_numpy(dtype=float)
    return np.clip(rounding(minutes), 0, n_minutes).astype(int)


def remaining_capacity(events: pd.DataFrame, year: int) -> np.ndarray:
    """The capacity one direction's reports leave in service, per minute of the Backcast Calendar.

    Overlapping events of one pair of zones take the smallest capacity. A
    direction of several pairs of zones (a canonical border spanning
    several ENTSO-E zones) sums them minute by minute, a pair without an
    event counting its largest reported capacity.

    Args:
        events (pd.DataFrame): The rows of latest_events for one direction.
        year (int): The Backcast Year.

    Returns:
        np.ndarray: MW per minute, inf where no event is reported.
    """
    calendar_start = first_monday(year)
    n_minutes = N_SEASONS * MINUTES_PER_WEEK
    pairs, largest = [], []
    for _, pair in events.groupby(["ZoneFrom", "ZoneTo"]):
        available = np.full(n_minutes, np.nan)
        first = _minute_index(pair["Start"], calendar_start, n_minutes, np.floor)
        last = _minute_index(pair["End"], calendar_start, n_minutes, np.ceil)
        for begin, end, capacity in zip(first, last, pair["Available"]):
            if end > begin:
                available[begin:end] = np.fmin(available[begin:end], capacity)
        pairs.append(available)
        largest.append(pair["Available"].max())

    if not pairs:
        return np.full(n_minutes, np.inf)
    stack = np.vstack(pairs)
    reported = ~np.isnan(stack)
    remaining = np.where(reported, stack, np.array(largest)[:, None]).sum(axis=0)
    remaining[~reported.any(axis=0)] = np.inf

    return remaining


def weekly_ratings(remaining: np.ndarray, limit: float) -> np.ndarray:
    """The 52 weekly means of the remaining capacity, capped at the Observed Flow Limit, as a share of it.

    Args:
        remaining (np.ndarray): Output of remaining_capacity.
        limit (float): The direction's Observed Flow Limit (MW), > 0.

    Returns:
        np.ndarray: One rating per Backcast Calendar week, in [0, 1].
    """
    return (np.minimum(remaining, limit) / limit).reshape(N_SEASONS, MINUTES_PER_WEEK).mean(axis=1)


def exceeded_share(
    remaining: np.ndarray, flow: pd.Series, year: int, tolerance: float
) -> tuple[int, float]:
    """The outage hours with observed flow, and the share of them in which flow exceeded the reported capacity.

    An hour is an outage hour if an event is reported at its middle, and its
    capacity is the one reported then.

    Args:
        remaining (np.ndarray): Output of remaining_capacity.
        flow (pd.Series): Hourly observed flow (MW) of the direction, indexed by UTC time.
        year (int): The Backcast Year.
        tolerance (float): MW by which flow must exceed the capacity to count.

    Returns:
        tuple[int, float]: The number of outage hours with flow, and the
            share exceeded (NaN without any).
    """
    middle = remaining[30::60]
    observed = flow.reindex(backcast_hours(year)).to_numpy(dtype=float)
    hours = np.isfinite(middle) & ~np.isnan(observed)
    if not hours.any():
        return 0, np.nan
    return int(hours.sum()), float((observed[hours] > middle[hours] + tolerance).mean())


# ------------------------------- #
#           3. Ratings            #
# ------------------------------- #


def border_lines(xkfx: pd.DataFrame, year: int) -> pd.DataFrame:
    """The Balmorel lines with an XKFX in `year`, with their canonical border.

    Args:
        xkfx (pd.DataFrame): XKFX from get_input, ending in (Y, IRRRE, IRRRI, Value).
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Columns 'RegionFrom', 'RegionTo', 'From', 'To'
            (canonical) and 'Capacity' (MW), without internal lines.
    """
    xkfx = xkfx.iloc[:, -4:].set_axis(["Year", "RegionFrom", "RegionTo", "Capacity"], axis=1)
    xkfx = xkfx[(xkfx["Year"].astype(str) == str(year)) & (xkfx["Capacity"].astype(float) > 0)]
    lines = xkfx[["RegionFrom", "RegionTo"]].assign(
        From=xkfx["RegionFrom"].map(canonical_region),
        To=xkfx["RegionTo"].map(canonical_region),
        Capacity=xkfx["Capacity"].astype(float),
    )
    return lines[lines["From"] != lines["To"]].reset_index(drop=True)


def transmission_ratings(
    events: pd.DataFrame,
    limits: pd.Series,
    flows: pd.DataFrame,
    year: int,
    min_reported_share: float = MIN_REPORTED_SHARE,
    max_exceeded_share: float = MAX_EXCEEDED_SHARE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The weekly Transmission Availability of every direction whose reports describe its whole border.

    Args:
        events (pd.DataFrame): Output of latest_events.
        limits (pd.Series): Observed Flow Limit (MW) per canonical (From, To),
            the XKFX summed over a border's lines.
        flows (pd.DataFrame): Output of flows.load_entsoe_flows, for the
            credibility check only.
        year (int): The Backcast Year.
        min_reported_share (float, optional): The largest reported capacity
            must be at least this share of the limit. Defaults to MIN_REPORTED_SHARE.
        max_exceeded_share (float, optional): Flow may exceed the reported
            capacity in less than this share of the outage hours. Defaults to
            MAX_EXCEEDED_SHARE.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The ratings, with columns 'From',
            'To', 'Season' and 'Rating', of the rated directions; and one row
            per direction with a limit or with reports (BORDER_COLUMNS), saying
            why a direction is not rated.
    """
    calendar_start = first_monday(year)
    calendar_end = calendar_start + pd.Timedelta(weeks=N_SEASONS)
    events = events[(events["End"] > calendar_start) & (events["Start"] < calendar_end)]
    flow_by_direction = {
        direction: flow.set_index("Time")["Value"] for direction, flow in flows.groupby(["From", "To"])
    }
    directions = sorted(set(limits.index) | set(zip(events["From"], events["To"])))
    by_direction = dict(list(events.groupby(["From", "To"])))
    seasons = [f"S{season:02d}" for season in range(1, N_SEASONS + 1)]

    borders, ratings = [], []
    for direction in directions:
        limit = float(limits.get(direction, 0.0))
        direction_events = by_direction.get(direction, events.iloc[:0])
        row = {
            "From": direction[0],
            "To": direction[1],
            "Limit": limit,
            "Events": direction_events["Event"].nunique(),
            "Planned": direction_events.loc[direction_events["Kind"] == "Planned", "Event"].nunique(),
            "Forced": direction_events.loc[direction_events["Kind"] == "Forced", "Event"].nunique(),
            "CoreFlowBased": set(direction) <= CORE_FLOW_BASED,
            "Assets": "; ".join(sorted(direction_events["Asset"].dropna().astype(str).unique()))[:300],
        }
        if limit <= 0:
            borders.append({**row, "Rated": False, "Reason": "no Observed Flow Limit"})
            continue
        if direction_events.empty:
            borders.append({**row, "Rated": False, "Reason": "no outage reports"})
            continue

        largest = direction_events.groupby(["ZoneFrom", "ZoneTo"])["Available"].max().sum()
        remaining = remaining_capacity(direction_events, year)
        tolerance = max(EXCEEDED_TOLERANCE_MW, EXCEEDED_TOLERANCE_SHARE * largest)
        flow = flow_by_direction.get(direction, pd.Series(dtype=float))
        event_hours, exceeded = exceeded_share(remaining, flow, year, tolerance)
        weekly = weekly_ratings(remaining, limit)
        row.update(
            LargestReported=largest,
            ReportedShare=largest / limit,
            EventHours=event_hours,
            ExceededShare=exceeded,
            MeanRating=weekly.mean(),
            MinRating=weekly.min(),
        )

        if row["CoreFlowBased"]:
            reason = "flow-based border (Core)"
        elif largest < min_reported_share * limit:
            reason = f"reports single lines (largest {largest / limit:.0%} of the limit)"
        elif np.isnan(exceeded):
            reason = "no observed flow in the outage hours"
        elif exceeded >= max_exceeded_share:
            reason = f"flow exceeded the reports in {exceeded:.0%} of the outage hours"
        else:
            reason = ""
            ratings.append(pd.DataFrame({"From": direction[0], "To": direction[1], "Season": seasons, "Rating": weekly}))
        borders.append({**row, "Rated": not reason, "Reason": reason})

    ratings = (
        pd.concat(ratings, ignore_index=True)
        if ratings
        else pd.DataFrame(columns=["From", "To", "Season", "Rating"])
    )
    return ratings, pd.DataFrame(borders).reindex(columns=BORDER_COLUMNS)


# ------------------------------- #
#           4. Output             #
# ------------------------------- #


def write_xkrate_override(
    ratings: pd.DataFrame, lines: pd.DataFrame, scenario_data_path: str | Path
) -> IncFile:
    """Write XKRATE_ENTSOE.inc with the weekly transmission ratings.

    Every Balmorel line of a rated border direction gets its rating, in all
    52 weeks.

    Args:
        ratings (pd.DataFrame): The ratings of transmission_ratings.
        lines (pd.DataFrame): Output of border_lines.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    rated = lines.merge(ratings, on=["From", "To"])
    body = "".join(
        f"XKRATE('{row.RegionFrom}','{row.RegionTo}','{row.Season}')={format_rating(row.Rating)};\n"
        for row in rated.sort_values(["RegionFrom", "RegionTo", "Season"]).itertuples()
    )

    inc_file = IncFile(
        prefix=(
            "* Transmission availability per week: the mean capacity ENTSO-E's outage reports leave\n"
            "* in service, capped at the Observed Flow Limit, as a share of it; only directions whose\n"
            "* reports describe the whole border (see CONTEXT.md and pybalmorel docs/adr/0016)\n"
            "* - generated, do not hand-edit\n"
        ),
        body=body,
        suffix="",
        name="XKRATE_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def check_xkrate_include(xkrate_inc_path: str | Path) -> None:
    """Warn if the scenario's XKRATE.inc doesn't include XKRATE_ENTSOE.inc.

    Args:
        xkrate_inc_path (str | Path): Path to the scenario's XKRATE.inc.
    """
    xkrate_inc_path = Path(xkrate_inc_path)
    if not xkrate_inc_path.exists() or "XKRATE_ENTSOE.inc" not in xkrate_inc_path.read_text():
        warn(
            f"{xkrate_inc_path} doesn't include XKRATE_ENTSOE.inc, so the transmission "
            f"availability has no effect. Add, after the base ratings:\n{XKRATE_ENTSOE_INCLUDE}"
        )


def generate_transmission_availability(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    gams_system_directory: str | None = None,
    reload_input: bool = False,
    min_reported_share: float = MIN_REPORTED_SHARE,
    max_exceeded_share: float = MAX_EXCEEDED_SHARE,
) -> IncFile | None:
    """Write XKRATE_ENTSOE.inc and the backcastoutput/transmission_availability*.csv tables for a scenario.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the override for.
        year (int): The Backcast Year.
        entsoe_data_path (str | Path): Folder with the outage reports and
            cross-border flows (from `download`).
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.
        min_reported_share (float, optional): See transmission_ratings.
        max_exceeded_share (float, optional): See transmission_ratings.

    Returns:
        IncFile | None: The saved IncFile instance, or None without outage reports.
    """
    outages = load_transmission_outages(entsoe_data_path, year)
    if outages.empty:
        warn(
            f"No ENTSO-E transmission outage reports for {year} in {entsoe_data_path}, so nothing "
            f"is written. Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} "
            f"--query {TRANSMISSION_OUTAGES}`"
        )
        return None
    flows = load_entsoe_flows(entsoe_data_path, year)
    if flows.empty:
        warn(
            f"No ENTSO-E cross-border flows for {year} in {entsoe_data_path}, so no direction "
            "passes the credibility check and nothing is rated."
        )

    model, _ = load_scenario_input(
        balmorel_model_folder, scenario, gams_system_directory, reload_input,
        ignore=("XKRATE.inc", "XKRATE_ENTSOE.inc"),  # only XKFX is read
    )
    lines = border_lines(model.get_input("XKFX"), year)
    limits = lines.groupby(["From", "To"])["Capacity"].sum()

    ratings, borders = transmission_ratings(
        latest_events(outages), limits, flows, year, min_reported_share, max_exceeded_share
    )

    output_path = Path(balmorel_model_folder) / scenario / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    ratings.to_csv(output_path / "transmission_availability.csv", index=False)
    borders.to_csv(output_path / "transmission_availability_borders.csv", index=False)
    print(f"Wrote the ratings and the table of directions to {output_path}")

    rated = borders[borders["Rated"]]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(f"Rated directions ({len(rated)}), mean and lowest weekly rating:")
        print(rated.set_index(["From", "To"])[["Limit", "Events", "MeanRating", "MinRating"]].round(3))
        unrated = borders.loc[~borders["Rated"] & (borders["Limit"] > 0), "Reason"]
        print("Directions with a limit that keep a rating of 1, by reason:")
        print(unrated.str.replace(r" \(.*\)| in \d+%.*", "", regex=True).value_counts())
    if len(rated):
        weights = rated["Limit"] / rated["Limit"].sum()
        print(f"Limit-weighted mean rating of the rated directions: {(rated['MeanRating'] * weights).sum():.3f}")

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    check_xkrate_include(scenario_data_path / "XKRATE.inc")

    return write_xkrate_override(ratings, lines, scenario_data_path)

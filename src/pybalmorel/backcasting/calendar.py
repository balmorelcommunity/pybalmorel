"""
Backcast Calendar

The single mapping between a Backcast Year's clock time and Balmorel's
52 seasons (S01-S52) x 168 terms (T001-T168), see CONTEXT.md and
docs/adr/0008. S01 T001 is 00:00 UTC on the first Monday of the year, every
day has exactly 24 terms, and the days outside the 52 full weeks are dropped.

Every conversion between timestamps and (Season, Time) labels goes through
this module - nowhere else should build its own hourly index or assign by
position.

Created on 15.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import pandas as pd

N_SEASONS = 52
N_TERMS = 168
SEASONS = [f"S{season:02d}" for season in range(1, N_SEASONS + 1)]
TERMS = [f"T{term:03d}" for term in range(1, N_TERMS + 1)]

# ------------------------------- #
#          1. Calendar            #
# ------------------------------- #


def first_monday(year: int) -> pd.Timestamp:
    """00:00 UTC on the first Monday of `year` - the timestamp of S01 T001.

    Args:
        year (int): The Backcast Year.

    Returns:
        pd.Timestamp: Timezone-aware (UTC) timestamp.
    """
    new_year = pd.Timestamp(f"{year}-01-01", tz="UTC")
    return new_year + pd.Timedelta(days=(7 - new_year.dayofweek) % 7)


def backcast_hours(year: int) -> pd.DatetimeIndex:
    """The 52 x 168 = 8736 UTC hours of the Backcast Calendar, in (S,T) order.

    Args:
        year (int): The Backcast Year.

    Returns:
        pd.DatetimeIndex: Hourly UTC timestamps, S01 T001 first.
    """
    return pd.date_range(
        first_monday(year), periods=N_SEASONS * N_TERMS, freq="h", name="Time"
    )


def backcast_calendar(year: int) -> pd.DataFrame:
    """Lookup table between (Season, Term) labels and their UTC timestamp.

    Args:
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Columns 'Season', 'Term' and 'Timestamp', one row per hour.
    """
    return pd.DataFrame(
        {
            "Season": [season for season in SEASONS for _ in TERMS],
            "Term": TERMS * N_SEASONS,
            "Timestamp": backcast_hours(year),
        }
    )


# ------------------------------- #
#     2. Conversion helpers       #
# ------------------------------- #


def from_backcast_grid(
    df: pd.DataFrame,
    year: int,
    season_col: str = "Season",
    term_col: str = "Time",
) -> pd.DataFrame:
    """Replace (Season, Term) label columns with a UTC 'Time' timestamp column.

    Rows are matched by label, never by position, so missing or reordered
    (S,T) rows can't shift the rest of the year.

    Args:
        df (pd.DataFrame): Long-format data with season and term label columns,
            e.g. a MainResults symbol with 'Season' and 'Time'.
        year (int): The Backcast Year.
        season_col (str, optional): Name of the season column. Defaults to 'Season'.
        term_col (str, optional): Name of the term column. Defaults to 'Time'.

    Returns:
        pd.DataFrame: `df` without the label columns and with a 'Time' column
            of UTC timestamps first.
    """
    unknown = set(df[season_col].unique()).difference(SEASONS).union(
        set(df[term_col].unique()).difference(TERMS)
    )
    if unknown:
        raise ValueError(
            f"Temporal structure not recognised - labels outside the "
            f"S01-S52 x T001-T168 Backcast Calendar: {sorted(unknown)}"
        )

    calendar = backcast_calendar(year).rename(
        columns={"Season": season_col, "Term": term_col}
    )
    df_out = df.merge(calendar, on=[season_col, term_col], how="left").drop(
        columns=[season_col, term_col]
    )
    df_out = df_out.rename(columns={"Timestamp": "Time"})

    return df_out[["Time"] + [col for col in df_out.columns if col != "Time"]]


def to_backcast_grid(hourly: pd.Series, year: int) -> pd.DataFrame:
    """Reshape an hourly, timezone-aware series onto the 52 x 168 (S,T) grid.

    Args:
        hourly (pd.Series): Values indexed by timezone-aware hourly timestamps.
            Converted to UTC before matching; hours outside the Backcast
            Calendar are dropped.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index 'S01'..'S52', columns 'T001'..'T168'. Hours
            missing from `hourly` are NaN.
    """
    if hourly.index.tz is None:
        raise ValueError(
            "to_backcast_grid needs timezone-aware timestamps - localize the "
            "series first (see docs/adr/0008)."
        )
    hourly = hourly.copy()
    hourly.index = hourly.index.tz_convert("UTC")
    values = hourly.reindex(backcast_hours(year)).to_numpy()

    return pd.DataFrame(
        values.reshape(N_SEASONS, N_TERMS), index=SEASONS, columns=TERMS
    )


def daily_to_backcast_grid(daily: pd.Series, year: int) -> pd.DataFrame:
    """Map a daily series onto the (S,T) grid, each value covering its UTC day.

    Days missing from `daily` (weekends/holidays without trading data) carry
    the last available value forward, or the first one backward for gaps
    before the first observation.

    Args:
        daily (pd.Series): Values indexed by calendar date (timezone-naive).
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index 'S01'..'S52', columns 'T001'..'T168'.
    """
    daily = daily.copy()
    daily.index = pd.to_datetime(daily.index).normalize()
    daily = daily[~daily.index.duplicated(keep="last")].sort_index()

    hours = backcast_hours(year)
    in_window = daily[
        (daily.index >= hours[0].tz_localize(None).normalize())
        & (daily.index <= hours[-1].tz_localize(None).normalize())
    ]
    if in_window.empty:
        raise ValueError(
            f"No observations between {hours[0].date()} and {hours[-1].date()} - "
            f"does the source file cover the Backcast Year {year}?"
        )

    days = hours.tz_localize(None).normalize()
    all_days = daily.index.union(days.unique())
    values = daily.reindex(all_days).ffill().bfill().reindex(days).to_numpy()

    return pd.DataFrame(
        values.reshape(N_SEASONS, N_TERMS), index=SEASONS, columns=TERMS
    )

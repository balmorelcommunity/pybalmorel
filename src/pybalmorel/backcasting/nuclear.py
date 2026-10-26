"""
Nuclear Availability

Turn ENTSO-E's observed nuclear output into weekly GKRATE overrides
(GKRATE_ENTSOE.inc) for a Backcast: per country and Backcast Calendar week,
the highest hourly nuclear output divided by the country's nuclear GKFX,
clipped at 1 (see CONTEXT.md). Reuses the override-file pattern of
docs/adr/0006; the scenario's GKRATE.inc includes the file itself.

Created on 22.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from pathlib import Path
from warnings import warn

import pandas as pd

from ..classes import Balmorel, IncFile
from .calendar import to_backcast_grid
from .flows import canonical_region

# Decimals written to GKRATE_ENTSOE.inc
RATING_DECIMALS = 4

# ------------------------------- #
#     1. Capacity and rating      #
# ------------------------------- #


def nuclear_capacity(
    gkfx: pd.DataFrame,
    gdata: pd.DataFrame,
    fdata: pd.DataFrame,
    rrraaa: pd.DataFrame,
    year: int,
) -> pd.DataFrame:
    """The nuclear GKFX of `year` per area and technology, with its canonical region.

    Nuclear technologies are those whose GDATA(G,'GDFUEL') equals
    FDATA('NUCLEAR','FDACRONYM'). Both are GAMS acronyms that get_input returns
    as the same large float, so the two values are compared rather than
    hard-coded. Columns are taken by position, as get_input may name them after
    the raw GAMS domains.

    Args:
        gkfx (pd.DataFrame): GKFX from get_input, ending in (Y, AAA, G, Value).
        gdata (pd.DataFrame): GDATA from get_input, ending in (G, GDATASET, Value).
        fdata (pd.DataFrame): FDATA from get_input, ending in (FFF, FDATASET, Value).
        rrraaa (pd.DataFrame): RRRAAA from get_input, ending in (RRR, AAA).
        year (int): The Backcast Year, the Y of GKFX.

    Returns:
        pd.DataFrame: Columns 'Area', 'Technology', 'Region' (canonical) and
            'Capacity' (MW), for every nuclear (area, technology) with GKFX > 0.
    """
    gdata = gdata.iloc[:, -3:].set_axis(["Technology", "Parameter", "Value"], axis=1)
    fdata = fdata.iloc[:, -3:].set_axis(["Fuel", "Parameter", "Value"], axis=1)
    gkfx = gkfx.iloc[:, -4:].set_axis(["Year", "Area", "Technology", "Capacity"], axis=1)
    rrraaa = rrraaa.iloc[:, -2:].set_axis(["Region", "Area"], axis=1)

    nuclear_acronym = fdata.query("Fuel == 'NUCLEAR' and Parameter == 'FDACRONYM'")["Value"]
    if nuclear_acronym.empty:
        raise Exception("FDATA has no FDACRONYM for NUCLEAR, so nuclear technologies can't be found")
    nuclear_technologies = gdata.query("Parameter == 'GDFUEL'").loc[
        lambda df: df["Value"] == nuclear_acronym.iloc[0], "Technology"
    ]

    capacity = gkfx[
        (gkfx["Year"].astype(str) == str(year))
        & gkfx["Technology"].isin(nuclear_technologies)
        & (gkfx["Capacity"].astype(float) > 0)
    ]
    capacity = capacity.merge(rrraaa, on="Area", how="left")
    capacity["Region"] = capacity["Region"].map(canonical_region, na_action="ignore")

    return capacity[["Area", "Technology", "Region", "Capacity"]].reset_index(drop=True)


def nuclear_ratings(
    observed: dict[str, pd.Series], capacity: pd.DataFrame, year: int
) -> pd.DataFrame:
    """The weekly Nuclear Availability per canonical region.

    The rating of week s is the highest hourly nuclear output in that week of
    the Backcast Calendar divided by the region's summed nuclear GKFX. Missing
    hours are ignored. Weeks without any data after the region's last week
    with data are a closure and get 0, since ENTSO-E stops reporting a closed
    fleet; any other week without data gets NaN. Ratings above 1 are clipped.
    All of these are reported.

    Args:
        observed (dict[str, pd.Series]): Hourly nuclear output (MW) per
            canonical region, indexed by timezone-aware timestamps.
        capacity (pd.DataFrame): Output of nuclear_capacity.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index 'S01'..'S52', one column per region that has both
            nuclear GKFX and observed nuclear output.
    """
    region_capacity = capacity.groupby("Region")["Capacity"].sum()

    for region in sorted(set(region_capacity.index) - set(observed)):
        warn(
            f"{region} has {region_capacity[region]:.0f} MW of nuclear GKFX but no "
            "ENTSO-E nuclear output, so it keeps its base GKRATE."
        )
    for region in sorted(set(observed) - set(region_capacity.index)):
        warn(
            f"{region} has {observed[region].sum() / 1e6:.2f} TWh of ENTSO-E nuclear "
            f"output in {year} but no nuclear GKFX, so it can't be placed."
        )

    ratings = {}
    for region in sorted(set(observed) & set(region_capacity.index)):
        weekly_max = to_backcast_grid(observed[region], year).max(axis=1)
        rating = weekly_max / region_capacity[region]

        clipped = rating.gt(1).sum()
        if clipped:
            warn(
                f"{region}'s nuclear output is above its GKFX of {region_capacity[region]:.0f} MW "
                f"in {clipped} week(s) (up to {weekly_max.max():.0f} MW); clipped at a rating of 1."
            )
        if rating.isna().all():
            warn(f"{region} has no ENTSO-E nuclear output in {year}, so it keeps its base GKRATE.")
            continue

        closed = rating.index[rating.index > rating.last_valid_index()]
        if len(closed):
            warn(
                f"CLOSURE: {region}'s ENTSO-E nuclear output ends at "
                f"{observed[region].last_valid_index()}, so week(s) {closed[0]}-{closed[-1]} "
                f"are rated 0 (eps). The base GKRATE would have allowed up to "
                f"{region_capacity[region] * 168 * len(closed) / 1e6:.2f} TWh in those weeks at full "
                "capacity. Check that the fleet really closed and the feed didn't just stop."
            )
            rating[closed] = 0.0

        missing = rating.index[rating.isna()].tolist()
        if missing:
            warn(
                f"{region} has no ENTSO-E nuclear output in week(s) {missing}, "
                "which keep their base GKRATE."
            )
        ratings[region] = rating.clip(upper=1)

    return pd.DataFrame(ratings)


# ------------------------------- #
#           2. Output             #
# ------------------------------- #


def format_rating(rating: float) -> str:
    """A GAMS value for a rating; anything that rounds to 0 is 'eps', since Balmorel reads 0 as 1."""
    rounded = round(rating, RATING_DECIMALS)
    return "eps" if rounded == 0 else f"{rounded:.{RATING_DECIMALS}f}"


def write_gkrate_override(
    ratings: pd.DataFrame, capacity: pd.DataFrame, scenario_data_path: str | Path
) -> IncFile:
    """Write GKRATE_ENTSOE.inc with the weekly nuclear ratings.

    Every nuclear technology in an area gets its country's rating, since
    ENTSO-E only reports nuclear output per bidding zone. Weeks without data
    get no line.

    Args:
        ratings (pd.DataFrame): Output of nuclear_ratings.
        capacity (pd.DataFrame): Output of nuclear_capacity.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    lines = []
    for row in capacity[capacity["Region"].isin(ratings.columns)].itertuples():
        for season, rating in ratings[row.Region].dropna().items():
            lines.append(
                f"GKRATE('{row.Area}','{row.Technology}','{season}')={format_rating(rating)};\n"
            )

    inc_file = IncFile(
        prefix=(
            "* Nuclear availability per week: highest hourly ENTSO-E nuclear output / nuclear GKFX,\n"
            "* clipped at 1 (see CONTEXT.md) - generated, do not hand-edit\n"
        ),
        body="".join(lines),
        suffix="",
        name="GKRATE_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def check_gkrate_include(gkrate_inc_path: str | Path) -> None:
    """Warn if the scenario's GKRATE.inc doesn't include GKRATE_ENTSOE.inc.

    Args:
        gkrate_inc_path (str | Path): Path to the scenario's GKRATE.inc.
    """
    gkrate_inc_path = Path(gkrate_inc_path)
    if not gkrate_inc_path.exists() or "GKRATE_ENTSOE.inc" not in gkrate_inc_path.read_text():
        warn(
            f"{gkrate_inc_path} doesn't include GKRATE_ENTSOE.inc, so the nuclear "
            "availability has no effect. Add, after the base ratings:\n"
            "$if EXIST '../data/GKRATE_ENTSOE.inc' $INCLUDE '../data/GKRATE_ENTSOE.inc';"
        )


def check_input_cache(
    input_gdx: Path, scenario_data_path: Path, ignore: tuple[str, ...] = ()
) -> None:
    """Warn if a scenario data file is newer than the cached input GDX, which then misses it.

    Args:
        input_gdx (Path): The cached <scenario>_input_data.gdx.
        scenario_data_path (Path): The scenario's 'data' folder.
        ignore (tuple[str, ...], optional): File names not to check, e.g. the
            override file the caller writes itself. Defaults to ().
    """
    newer = sorted(
        inc_file.name
        for inc_file in scenario_data_path.glob("*.inc")
        if inc_file.name not in ignore and inc_file.stat().st_mtime > input_gdx.stat().st_mtime
    )
    if newer:
        warn(
            f"{input_gdx} is older than {', '.join(newer)} in {scenario_data_path}, so the "
            "inputs read from it may be stale. Run again with --reload-input to read the data again."
        )


def generate_nuclear_availability(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    observed: dict[str, pd.Series],
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> IncFile:
    """Write GKRATE_ENTSOE.inc for a Balmorel scenario from observed nuclear output.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the override for.
        year (int): The Backcast Year.
        observed (dict[str, pd.Series]): Hourly nuclear output (MW) per
            canonical region.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Returns:
        IncFile: The saved IncFile instance.
    """
    model = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    input_gdx = Path(balmorel_model_folder) / scenario / "model" / f"{scenario}_input_data.gdx"
    if input_gdx.exists() and not reload_input:
        print(f"Reading GKFX from the cached {input_gdx}")
        check_input_cache(input_gdx, Path(balmorel_model_folder) / scenario / "data")
    else:
        print(f"Running ReadData for {scenario} into {input_gdx}, this may take a while")
    model.load_incfiles(scenario, overwrite=reload_input)
    capacity = nuclear_capacity(
        model.get_input("GKFX"),
        model.get_input("GDATA"),
        model.get_input("FDATA"),
        model.get_input("RRRAAA"),
        year,
    )

    ratings = nuclear_ratings(observed, capacity, year)
    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    check_gkrate_include(scenario_data_path / "GKRATE.inc")

    return write_gkrate_override(ratings, capacity, scenario_data_path)

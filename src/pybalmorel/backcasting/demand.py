"""
Observed Demand Profiles

Turn ENTSO-E's actual load into DE_VAR_T overrides (DE_VAR_T_ENTSOE.inc) for
a Backcast: the hourly load of the Backcast Year on the Backcast Calendar,
for the exogenous electricity users OTHER and RESE of every region. Balmorel
scales DE_VAR_T to the annual DE, so only the shape matters. Reuses the
override-file pattern of docs/adr/0006 and appends the $include to the
scenario's DE_VAR_T.inc itself.

Implausible or missing hours are interpolated. A region with too many of
them takes its profile from the input data instead, with the same cleaning,
or keeps it unchanged if that fails too.

Created on 26.10.2026
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
from .calendar import SEASONS, TERMS, to_backcast_grid
from .flows import canonical_region
from .nuclear import check_input_cache

# Hours outside [LOW, HIGH] x the profile's median are implausible and get interpolated
PLAUSIBLE_LOW = 0.2
PLAUSIBLE_HIGH = 3.0
# A profile with a larger share of implausible or missing hours is not used
MAX_IMPLAUSIBLE_SHARE = 0.02

# The users that get the observed profile; the first one holds the values
DEMAND_USERS = ("OTHER", "RESE")

DE_VAR_T_INCLUDE = "$if EXIST '../data/DE_VAR_T_ENTSOE.inc' $INCLUDE '../data/DE_VAR_T_ENTSOE.inc';"

# ------------------------------- #
#          1. Profiles            #
# ------------------------------- #


def sum_zones(zones: pd.DataFrame) -> pd.DataFrame:
    """Sum hourly ENTSO-E load of bidding zones to their canonical region.

    An hour missing in one zone is missing for the region, so a partial sum
    is never taken for the region's load.

    Args:
        zones (pd.DataFrame): Hourly load (MW), one column per zone (any
            spelling canonical_region knows, e.g. 'IT-NORD' or 'DK1').

    Returns:
        pd.DataFrame: Hourly load (MW), one column per canonical region.
    """
    regions = zones.columns.map(canonical_region)
    return pd.DataFrame(
        {
            region: zones.loc[:, regions == region].sum(axis=1, min_count=(regions == region).sum())
            for region in sorted(set(regions))
        }
    )


def grid_to_profile(grid: pd.DataFrame) -> pd.Series:
    """Flatten an S x T grid into a series indexed by (Season, Term), keeping missing hours.

    Args:
        grid (pd.DataFrame): Index 'S01'..'S52', columns 'T001'..'T168'.

    Returns:
        pd.Series: 8736 values in (S,T) order.
    """
    grid = grid.reindex(index=SEASONS, columns=TERMS)
    return pd.Series(
        grid.to_numpy().ravel(),
        index=pd.MultiIndex.from_product([SEASONS, TERMS], names=["Season", "Term"]),
    )


def current_profiles(de_var_t: pd.DataFrame, user: str = DEMAND_USERS[0]) -> pd.DataFrame:
    """The DE_VAR_T profile of `user` per region, from the scenario's input data.

    Columns are taken by position, as get_input may name them after the raw
    GAMS domains.

    Args:
        de_var_t (pd.DataFrame): DE_VAR_T from get_input, ending in
            (RRR, DEUSER, SSS, TTT, Value).
        user (str, optional): The demand user. Defaults to 'OTHER'.

    Returns:
        pd.DataFrame: Index (Season, Term) in (S,T) order, one column per region.
    """
    de_var_t = de_var_t.iloc[:, -5:].set_axis(["Region", "User", "Season", "Term", "Value"], axis=1)
    profiles = de_var_t[de_var_t["User"] == user].pivot_table(
        index=["Season", "Term"], columns="Region", values="Value", aggfunc="first"
    )
    return profiles.reindex(pd.MultiIndex.from_product([SEASONS, TERMS], names=["Season", "Term"]))


def clean_profile(profile: pd.Series) -> tuple[pd.Series, int]:
    """Interpolate the implausible or missing hours of a profile.

    An hour is implausible outside PLAUSIBLE_LOW-PLAUSIBLE_HIGH times the
    profile's median.

    Args:
        profile (pd.Series): Values in (S,T) order.

    Returns:
        tuple[pd.Series, int]: The cleaned profile and the number of hours replaced.
    """
    median = profile.median()
    implausible = (
        profile.isna()
        | (profile < PLAUSIBLE_LOW * median)
        | (profile > PLAUSIBLE_HIGH * median)
        | (not median > 0)
    )
    if implausible.all():
        return profile, int(implausible.sum())
    cleaned = profile.mask(implausible).interpolate(limit_direction="both")
    return cleaned, int(implausible.sum())


def demand_profiles(
    regions: list[str],
    observed: pd.DataFrame,
    current: pd.DataFrame,
    year: int,
) -> tuple[dict[str, pd.Series], list[str]]:
    """The observed demand profile per Balmorel region, with a report line per region.

    A region takes the ENTSO-E load of its canonical region, so DE4-* take
    DE's. If that is missing or has more than MAX_IMPLAUSIBLE_SHARE
    implausible or missing hours, it takes its current profile from the input
    data instead, with the same cleaning. A region where both fail gets no
    profile and keeps its current one unchanged, which is warned about.

    Args:
        regions (list[str]): Balmorel regions with electricity demand.
        observed (pd.DataFrame): Hourly ENTSO-E load (MW) per canonical region,
            indexed by timezone-aware timestamps (output of sum_zones).
        current (pd.DataFrame): Output of current_profiles.
        year (int): The Backcast Year.

    Returns:
        tuple[dict[str, pd.Series], list[str]]: Profile in (S,T) order per
            region, and one report line per region.
    """
    profiles, report = {}, []
    for region in regions:
        key = canonical_region(region)
        candidates = []
        if key in observed.columns:
            candidates.append((f"ENTSO-E {key}", grid_to_profile(to_backcast_grid(observed[key], year))))
        if region in current.columns:
            candidates.append(("input data", current[region]))
        if not candidates:
            report.append(f"{region}: no ENTSO-E load or input profile, keeps its current profile")
            continue

        rejected = []
        for source, profile in candidates:
            cleaned, n_implausible = clean_profile(profile)
            if n_implausible > MAX_IMPLAUSIBLE_SHARE * len(profile):
                rejected.append(f"{source} has {n_implausible} implausible or missing hours")
                continue
            profiles[region] = cleaned
            report.append(
                f"{region}: {source}, {n_implausible} hours interpolated"
                + (f" ({'; '.join(rejected)})" if rejected else "")
            )
            break
        else:
            warn(
                f"{region} keeps its current demand profile unchanged: {'; '.join(rejected)}. "
                "Check it before running the backcast."
            )
            report.append(f"{region}: keeps its current profile ({'; '.join(rejected)})")

    return profiles, report


# ------------------------------- #
#           2. Output             #
# ------------------------------- #


def write_de_var_t_override(
    profiles: dict[str, pd.Series],
    report: list[str],
    year: int,
    scenario_data_path: str | Path,
) -> IncFile:
    """Write DE_VAR_T_ENTSOE.inc with the observed demand profiles.

    The first of DEMAND_USERS gets the values, the others are set equal to it.

    Args:
        profiles (dict[str, pd.Series]): Output of demand_profiles.
        report (list[str]): Report lines of demand_profiles, written in the header.
        year (int): The Backcast Year.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    user, *other_users = DEMAND_USERS
    lines = []
    for region, profile in profiles.items():
        for (season, term), value in profile.items():
            lines.append(f"DE_VAR_T('{region}','{user}','{season}','{term}')={value:.2f};\n")
        for other_user in other_users:
            lines.append(
                f"DE_VAR_T('{region}','{other_user}',SSS,TTT)=DE_VAR_T('{region}','{user}',SSS,TTT);\n"
            )

    inc_file = IncFile(
        prefix=(
            f"* Electricity demand profiles for {year} from ENTSO-E actual load on the Backcast\n"
            "* Calendar (see CONTEXT.md) - generated, do not hand-edit\n"
            + "".join(f"* {line}\n" for line in report)
        ),
        body="".join(lines),
        suffix="",
        name="DE_VAR_T_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def append_de_var_t_include(de_var_t_inc_path: str | Path, base_data_dir: str = "../../base/data") -> None:
    """Idempotently append the $include of DE_VAR_T_ENTSOE.inc to the scenario's DE_VAR_T.inc.

    A scenario without its own DE_VAR_T.inc gets one that loads base's first.

    Args:
        de_var_t_inc_path (str | Path): Path to the scenario's DE_VAR_T.inc.
        base_data_dir (str, optional): GAMS path, relative to the scenario's
            model/ folder, of the base data. Defaults to '../../base/data'.
    """
    de_var_t_inc_path = Path(de_var_t_inc_path)
    if not de_var_t_inc_path.exists():
        de_var_t_inc_path.write_text(f"$include '{base_data_dir}/DE_VAR_T.inc';\n")

    content = de_var_t_inc_path.read_text()
    if "DE_VAR_T_ENTSOE.inc" in content:
        return

    with open(de_var_t_inc_path, "a") as f:
        f.write(("" if content.endswith("\n") else "\n") + "\n" + DE_VAR_T_INCLUDE + "\n")
    print(f"Added the $include of DE_VAR_T_ENTSOE.inc to {de_var_t_inc_path}")


def generate_demand_profile(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    zones: pd.DataFrame,
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> IncFile:
    """Write DE_VAR_T_ENTSOE.inc for a Balmorel scenario from observed ENTSO-E load.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the override for.
        year (int): The Backcast Year.
        zones (pd.DataFrame): Hourly ENTSO-E load (MW) per bidding zone,
            indexed by timezone-aware timestamps.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Returns:
        IncFile: The saved IncFile instance.
    """
    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    model = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    input_gdx = Path(balmorel_model_folder) / scenario / "model" / f"{scenario}_input_data.gdx"
    if input_gdx.exists() and not reload_input:
        print(f"Reading DE and DE_VAR_T from the cached {input_gdx}")
        check_input_cache(input_gdx, scenario_data_path, ignore=("DE_VAR_T_ENTSOE.inc",))
    else:
        print(f"Running ReadData for {scenario} into {input_gdx}, this may take a while")
    model.load_incfiles(scenario, overwrite=reload_input)

    regions = sorted(model.get_input("DE").iloc[:, -3].unique())
    current = current_profiles(model.get_input("DE_VAR_T"))
    profiles, report = demand_profiles(regions, sum_zones(zones), current, year)
    print("\n".join(report))

    inc_file = write_de_var_t_override(profiles, report, year, scenario_data_path)
    append_de_var_t_include(scenario_data_path / "DE_VAR_T.inc")
    print(f"Wrote {len(profiles)} regions to {scenario_data_path / 'DE_VAR_T_ENTSOE.inc'}")

    return inc_file

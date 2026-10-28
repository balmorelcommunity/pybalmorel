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

Also sets the annual level of that demand, the Demand Level (DE_ENTSOE.inc):
ENTSO-E's annual load net of Balmorel's distribution losses, less the
electricity Eurostat reports for heating, which Balmorel adds endogenously.

Created on 26.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
from pathlib import Path
from warnings import warn

import pandas as pd

from ..classes import Balmorel, IncFile
from .calendar import SEASONS, TERMS, backcast_hours, to_backcast_grid
from .eurostat import FINAL_CONSUMPTION, HEATING_BALANCES, electricity_balances
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

# Demand Level bases: ENTSO-E load net of losses, or Eurostat final consumption, each less heating
DEMAND_LEVEL_BASES = ("entsoe", "eurostat")

# Load net of losses over Eurostat final consumption outside these bounds is a coverage gap
COVERAGE_BOUNDS = (0.8, 1.3)

# Canonical regions whose ENTSO-E load covers several countries, split by Eurostat final consumption
SHARED_LOAD = {"DE": ("DE", "LU")}

# Eurostat's electricity-for-heat balances, which Balmorel's ELECT2HEAT adds endogenously
HEATING = tuple(balance for balances in HEATING_BALANCES.values() for balance in balances)

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
#         2. Demand Level         #
# ------------------------------- #


def country_of(region: str) -> str:
    """The country code of a Balmorel region or canonical region, e.g. 'NO' for 'NO3' and 'DE' for 'DE4-E'."""
    return re.sub(r"\d+$", "", canonical_region(region))


def annual_load(observed: pd.DataFrame, year: int) -> pd.Series:
    """ENTSO-E's load per canonical region over the Backcast Calendar (MWh).

    Missing hours are filled with the region's mean, so a gap doesn't lower
    the level.

    Args:
        observed (pd.DataFrame): Hourly load (MW) per canonical region (output of sum_zones).
        year (int): The Backcast Year.

    Returns:
        pd.Series: Index canonical region. A region without any hour is NaN.
    """
    hours = backcast_hours(year)
    hourly = observed.reindex(hours)
    for region, n_missing in hourly.isna().sum().items():
        if n_missing > MAX_IMPLAUSIBLE_SHARE * len(hours) and n_missing < len(hours):
            warn(
                f"{region} misses {n_missing} of {len(hours)} hours of ENTSO-E load, filled with the mean "
                f"({hourly[region].mean() * len(hours) / 1e6:.1f} TWh against {hourly[region].sum() / 1e6:.1f} "
                "TWh summed). Check its coverage before using its demand level."
            )
        elif 0 < n_missing < len(hours):
            print(f"{region}: {n_missing} hours of ENTSO-E load missing, filled with the mean")

    return hourly.mean() * len(hours)


def split_shared_load(load: pd.Series, balances: pd.DataFrame) -> pd.Series:
    """Split the load of a canonical region covering several countries (DE_LU) by Eurostat final consumption.

    Args:
        load (pd.Series): Output of annual_load.
        balances (pd.DataFrame): Output of eurostat.electricity_balances.

    Returns:
        pd.Series: The load with one entry per country of SHARED_LOAD.
    """
    load = load.copy()
    for region, countries in SHARED_LOAD.items():
        if region not in load.index:
            continue
        consumption = balances[FINAL_CONSUMPTION].reindex(list(countries))
        if consumption.isna().any():
            warn(
                f"No Eurostat final consumption for {', '.join(consumption.index[consumption.isna()])}, "
                f"so ENTSO-E's {region} load stays with {region} and is not split over {', '.join(countries)}."
            )
            continue
        shares = consumption / consumption.sum()
        total = load[region]
        for country, share in shares.items():
            load[country] = total * share

    return load


def demand_levels(
    de: pd.DataFrame,
    disloss: pd.DataFrame,
    load: pd.Series,
    balances: pd.DataFrame,
    year: int,
    basis: str = "entsoe",
    coverage_bounds: tuple[float, float] = COVERAGE_BOUNDS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The Demand Level of `year` per region and user, with a summary per country.

    Per country c, with L its ENTSO-E load, d its load-weighted DISLOSS_E and
    H its Eurostat electricity for heating, the level is L(1-d) - H
    ('entsoe') or FC_E - H ('eurostat'). A country with several canonical
    regions (NO1-5) gets L_r(1-d_r) - H L_r/L per region ('entsoe') or its
    level split by L_r(1-d_r) ('eurostat'). Within a canonical region
    (DE4-*) and then over the users, the level is split by the shares of
    `de`, so a rerun on its own output writes the same level. A country is
    not written, and warns, without ENTSO-E load, without Eurostat final
    consumption or heating, or if L(1-d)/FC_E is outside `coverage_bounds`.

    Args:
        de (pd.DataFrame): DE from get_input, ending in (YYY, RRR, DEUSER, Value).
        disloss (pd.DataFrame): DISLOSS_E from get_input, ending in (RRR, Value).
            A region without one has no losses.
        load (pd.Series): Output of split_shared_load (MWh per canonical region or country).
        balances (pd.DataFrame): Output of eurostat.electricity_balances (GWh).
        year (int): The Backcast Year.
        basis (str, optional): 'entsoe' or 'eurostat'. Defaults to 'entsoe'.
        coverage_bounds (tuple[float, float], optional): Lowest and highest
            L(1-d)/FC_E written. Defaults to COVERAGE_BOUNDS.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The level per 'Region' and 'User'
            ('Value', MWh) of the countries written, and the summary per
            country (TWh).
    """
    if basis not in DEMAND_LEVEL_BASES:
        raise ValueError(f"Unknown demand level basis '{basis}', use one of {DEMAND_LEVEL_BASES}")

    de = de.iloc[:, -4:].set_axis(["Year", "Region", "User", "Value"], axis=1)
    de = de[de["Year"].astype(str) == str(year)].assign(Value=lambda df: df["Value"].astype(float))
    disloss = disloss.iloc[:, -2:].set_axis(["Region", "DisLoss"], axis=1).set_index("Region")["DisLoss"]

    regions = de.groupby("Region")["Value"].sum().rename("Base").to_frame()
    regions["Canonical"] = regions.index.map(canonical_region)
    regions["Country"] = regions.index.map(country_of)
    regions["DisLoss"] = disloss.reindex(regions.index).astype(float).fillna(0.0)

    # Distribution losses of a canonical region, weighted by its regions' DE
    canonical = (
        regions.assign(WeightedLoss=regions["DisLoss"] * regions["Base"])
        .groupby("Canonical")
        .agg(
            Country=("Country", "first"),
            Base=("Base", "sum"),
            WeightedLoss=("WeightedLoss", "sum"),
            MeanLoss=("DisLoss", "mean"),
        )
    )
    canonical["DisLoss"] = (canonical["WeightedLoss"] / canonical["Base"]).where(
        canonical["Base"] > 0, canonical["MeanLoss"]
    )
    canonical["Load"] = load.reindex(canonical.index).astype(float)
    canonical["NetLoad"] = canonical["Load"] * (1 - canonical["DisLoss"])

    balances = balances.reindex(columns=[FINAL_CONSUMPTION, *HEATING]) * 1e3
    summary, levels = [], []
    for country, group in canonical.groupby("Country"):
        load_c, net_c = group["Load"].sum(min_count=len(group)), group["NetLoad"].sum(min_count=len(group))
        eurostat = balances.loc[country] if country in balances.index else pd.Series(index=balances.columns, dtype=float)
        heating = eurostat[list(HEATING)]
        heat_c = heating.sum()
        final_c = eurostat[FINAL_CONSUMPTION]
        coverage = net_c / final_c if final_c > 0 else float("nan")
        level_c = net_c - heat_c if basis == "entsoe" else final_c - heat_c

        if pd.isna(load_c):
            note = "no ENTSO-E load"
        elif pd.isna(final_c):
            note = "no Eurostat final consumption"
        elif heating.isna().all():
            note = "no Eurostat electricity for heating"
        elif not coverage_bounds[0] <= coverage <= coverage_bounds[1]:
            note = f"coverage {coverage:.2f} outside {coverage_bounds[0]}-{coverage_bounds[1]}"
        elif not level_c > 0:
            note = "level not positive"
        elif (group["Base"] <= 0).any():
            note = "a canonical region without base DE to split by"
        else:
            note = ""

        summary.append(
            {
                "Country": country,
                "LoadTWh": load_c / 1e6,
                "DisLoss": 1 - net_c / load_c if load_c > 0 else float("nan"),
                "FC_E_TWh": final_c / 1e6,
                "Coverage": coverage,
                **{f"{balance}_TWh": heating[balance] / 1e6 for balance in HEATING},
                "HeatTWh": heat_c / 1e6,
                "BaseTWh": group["Base"].sum() / 1e6,
                "NewTWh": level_c / 1e6 if not note else float("nan"),
                "Written": not note,
                "Note": note,
            }
        )
        if note:
            warn(f"{country} keeps the input data's DE: {note}.")
            continue

        for region, row in group.iterrows():
            if basis == "entsoe":
                level = row["NetLoad"] - heat_c * row["Load"] / load_c
            else:
                level = level_c * row["NetLoad"] / net_c
            users = de[de["Region"].isin(regions.index[regions["Canonical"] == region])]
            levels.append(users.assign(Value=users["Value"] * level / row["Base"])[["Region", "User", "Value"]])

    levels = pd.concat(levels, ignore_index=True) if levels else pd.DataFrame(columns=["Region", "User", "Value"])

    return levels, pd.DataFrame(summary)


# ------------------------------- #
#           3. Output             #
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


def write_de_override(levels: pd.DataFrame, year: int, basis: str, scenario_data_path: str | Path) -> IncFile:
    """Write DE_ENTSOE.inc with the Demand Level of `year`.

    Args:
        levels (pd.DataFrame): The levels of demand_levels.
        year (int): The Backcast Year.
        basis (str): 'entsoe' or 'eurostat'.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    source = (
        "ENTSO-E load net of distribution losses"
        if basis == "entsoe"
        else "Eurostat final electricity consumption"
    )
    lines = [
        f"DE('{year}','{row.Region}','{row.User}')={row.Value:.1f};\n"
        for row in levels.sort_values(["Region", "User"]).itertuples()
    ]

    inc_file = IncFile(
        prefix=(
            f"* Electricity demand level for {year}: {source}, less\n"
            "* Eurostat electricity for heating (see CONTEXT.md) - generated, do not hand-edit\n"
        ),
        body="".join(lines),
        suffix="",
        name="DE_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def load_input_data(
    balmorel_model_folder: str | Path,
    scenario: str,
    gams_system_directory: str | None,
    reload_input: bool,
    ignore: tuple[str, ...],
) -> Balmorel:
    """Load a scenario's input data, warning if the cached GDX is stale.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario.
        gams_system_directory (str | None): GAMS system directory.
        reload_input (bool): Run ReadData again instead of reusing the cached input GDX.
        ignore (tuple[str, ...]): Data files the stale-cache check ignores.

    Returns:
        Balmorel: The model with the input data loaded.
    """
    model = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    input_gdx = Path(balmorel_model_folder) / scenario / "model" / f"{scenario}_input_data.gdx"
    if input_gdx.exists() and not reload_input:
        print(f"Reading the input data from the cached {input_gdx}")
        check_input_cache(input_gdx, Path(balmorel_model_folder) / scenario / "data", ignore=ignore)
    else:
        print(f"Running ReadData for {scenario} into {input_gdx}, this may take a while")
    model.load_incfiles(scenario, overwrite=reload_input)

    return model


def generate_demand_level(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    zones: pd.DataFrame,
    eurostat_data_path: str | Path | None = None,
    basis: str = "entsoe",
    coverage_bounds: tuple[float, float] = COVERAGE_BOUNDS,
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> IncFile:
    """Write DE_ENTSOE.inc and backcastoutput/demand_level.csv for a Balmorel scenario.

    The scenario's DE.inc must include DE_ENTSOE.inc after base's DE.inc.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the override for.
        year (int): The Backcast Year.
        zones (pd.DataFrame): Hourly ENTSO-E load (MW) per bidding zone,
            indexed by timezone-aware timestamps.
        eurostat_data_path (str | Path | None, optional): Cache folder of the
            Eurostat responses. Defaults to <scenario>/eurostatdata.
        basis (str, optional): 'entsoe' or 'eurostat'. Defaults to 'entsoe'.
        coverage_bounds (tuple[float, float], optional): Lowest and highest
            L(1-d)/FC_E written. Defaults to COVERAGE_BOUNDS.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Returns:
        IncFile: The saved IncFile instance.
    """
    scenario_path = Path(balmorel_model_folder) / scenario
    if eurostat_data_path is None:
        eurostat_data_path = scenario_path / "eurostatdata"
    balances = electricity_balances(year, eurostat_data_path)

    model = load_input_data(balmorel_model_folder, scenario, gams_system_directory, reload_input, ("DE_ENTSOE.inc",))
    load = split_shared_load(annual_load(sum_zones(zones), year), balances)
    levels, summary = demand_levels(
        model.get_input("DE"), model.get_input("DISLOSS_E"), load, balances, year, basis, coverage_bounds
    )

    output_path = scenario_path / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    summary.to_csv(output_path / "demand_level.csv", index=False)
    written = summary[summary["Written"]]
    with pd.option_context("display.max_rows", None, "display.width", 250):
        print(summary.set_index("Country").round(2))
    print(
        f"DE of the {len(written)} countries written goes from {written['BaseTWh'].sum():.1f} TWh "
        f"to {written['NewTWh'].sum():.1f} TWh"
    )

    inc_file = write_de_override(levels, year, basis, scenario_path / "data")
    de_inc = scenario_path / "data" / "DE.inc"
    if not de_inc.exists() or "DE_ENTSOE.inc" not in de_inc.read_text():
        warn(
            f"{de_inc} doesn't include DE_ENTSOE.inc, so Balmorel won't read the demand level. Add\n"
            "$include '../../base/data/DE.inc';\n"
            "$if EXIST '../data/DE_ENTSOE.inc' $INCLUDE '../data/DE_ENTSOE.inc';"
        )

    return inc_file


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
    model = load_input_data(
        balmorel_model_folder, scenario, gams_system_directory, reload_input, ("DE_VAR_T_ENTSOE.inc",)
    )

    regions = sorted(model.get_input("DE").iloc[:, -3].unique())
    current = current_profiles(model.get_input("DE_VAR_T"))
    profiles, report = demand_profiles(regions, sum_zones(zones), current, year)
    print("\n".join(report))

    inc_file = write_de_var_t_override(profiles, report, year, scenario_data_path)
    append_de_var_t_include(scenario_data_path / "DE_VAR_T.inc")
    print(f"Wrote {len(profiles)} regions to {scenario_data_path / 'DE_VAR_T_ENTSOE.inc'}")

    return inc_file

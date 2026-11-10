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
ENTSO-E's annual load less the previous backcast run's transmission losses,
net of Balmorel's distribution losses, less the electricity that run used for
heat, which Balmorel adds back endogenously (`heat='model'`, docs/adr/0015).
That heating responds to prices, so the level is iterated over runs. The
first run of a new Backcast Year takes Eurostat's electricity for heating
instead (`heat='eurostat'`).

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

# Balmorel spreads an annual quantity such as DE over 8760 hours (IOF8760 in
# IHOURSINST), whatever the time steps cover; the Backcast Calendar has 8736
BALMOREL_YEAR_HOURS = 8760

# Eurostat's electricity-for-heat balances, which Balmorel's ELECT2HEAT adds endogenously
HEATING = tuple(balance for balances in HEATING_BALANCES.values() for balance in balances)

# Where the heating the Demand Level leaves out comes from: Eurostat, or the previous backcast run
HEAT_SOURCES = ("eurostat", "model")

# The previous run's load categories the Demand Level uses, in balmorel_load.csv (written by `format`)
PREVIOUS_RUN_CATEGORIES = {"EXOGENOUS": "EXO", "ENDOGENOUS_ELECT2HEAT": "E2H", "TRANS_LOSSES": "TLoss"}

# A previous run whose EXOGENOUS differs more than this from DE_ENTSOE.inc did not solve with it
PREVIOUS_RUN_TOLERANCE = 0.01

# Addons that adjust DE after DE.inc, so the scenario's own copy must apply DE_ENTSOE.inc again
DE_ADDONS = ("INDUSTRY_DE.inc", "INDIVUSERS_DE.inc")

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
    """ENTSO-E's load per canonical region over Balmorel's year (MWh).

    The mean hourly load over the Backcast Calendar times Balmorel's 8760
    hours, so that a DE built on it gives back the observed load in the
    calendar's 8736 hours, and is on the same annual footing as Eurostat's
    heating and final consumption. Missing hours are filled with the mean, so
    a gap doesn't lower the level.

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

    return hourly.mean() * BALMOREL_YEAR_HOURS


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


def previous_run_heat(load_results: str | Path, year: int) -> pd.DataFrame:
    """The previous backcast run's exogenous load, electric heating and transmission losses per region.

    Args:
        load_results (str | Path): balmorel_load.csv of one solved backcast,
            as `format` writes it (MWh per hour on the Backcast Calendar).
        year (int): The Backcast Year.

    Raises:
        ValueError: If the file holds more than one scenario, another year,
            or not every hour of the Backcast Calendar.

    Returns:
        pd.DataFrame: 'EXO', 'E2H' and 'TLoss' (MWh over the calendar's 8736
            hours) per Balmorel region, with the scenario in attrs['scenario'].
    """
    frame = pd.read_csv(load_results, usecols=["Scenario", "Year", "Region", "Season", "Time", "Category", "Value"])
    scenarios = frame["Scenario"].unique()
    if len(scenarios) != 1:
        raise ValueError(
            f"{load_results} holds {len(scenarios)} scenarios ({', '.join(map(str, scenarios))}), "
            "expected the one scenario of the previous run"
        )
    years = sorted(frame["Year"].astype(str).unique())
    if years != [str(year)]:
        raise ValueError(f"{load_results} is for {', '.join(years)}, not {year}")
    n_hours, calendar_hours = len(frame[["Season", "Time"]].drop_duplicates()), len(SEASONS) * len(TERMS)
    if n_hours != calendar_hours:
        raise ValueError(
            f"{load_results} has {n_hours} of the {calendar_hours} hours of the Backcast Calendar, "
            "so it is not a full-year run"
        )

    used = frame[frame["Category"].isin(list(PREVIOUS_RUN_CATEGORIES))]
    previous = (
        used.pivot_table(index="Region", columns="Category", values="Value", aggfunc="sum")
        .reindex(columns=list(PREVIOUS_RUN_CATEGORIES))
        .rename(columns=PREVIOUS_RUN_CATEGORIES)
        .fillna(0.0)
        .rename_axis(columns=None)
    )
    previous.attrs["scenario"] = str(scenarios[0])

    return previous


def demand_levels(
    de: pd.DataFrame,
    disloss: pd.DataFrame,
    load: pd.Series,
    balances: pd.DataFrame,
    year: int,
    basis: str = "entsoe",
    coverage_bounds: tuple[float, float] = COVERAGE_BOUNDS,
    heat: str = "eurostat",
    previous: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The Demand Level of `year` per region and user, with a summary per country.

    With `heat='eurostat'`, per country c, with L its ENTSO-E load, d its
    load-weighted DISLOSS_E and H its Eurostat electricity for heating, the
    level is L(1-d) - H ('entsoe') or FC_E - H ('eurostat'). A country with
    several canonical regions (NO1-5) gets L_r(1-d_r) - H L_r/L per region
    ('entsoe') or its level split by L_r(1-d_r) ('eurostat').

    With `heat='model'` (basis 'entsoe' only), per canonical region k, with
    T_k and E_k the previous run's transmission losses and electricity for
    heat (ENDOGENOUS_ELECT2HEAT) summed over its Balmorel regions and scaled
    from the calendar's 8736 hours to Balmorel's 8760, the level is
    (L_k - T_k)(1 - d_k) - E_k. Balmorel's load is then ENTSO-E's if the
    run's heating and losses stay as they were, so the level is iterated.

    Within a canonical region (DE4-*) and then over the users, the level is
    split by the shares of `de`, so a rerun on its own output keeps them. A
    country is not written, and warns, without ENTSO-E load, if
    L(1-d)/FC_E is outside `coverage_bounds`, if a level is not positive,
    and with 'eurostat' heat without Eurostat final consumption or heating,
    or with 'model' heat if a region is not in the previous run. With 'model'
    heat, a country without Eurostat final consumption (CH) is written with
    its coverage unchecked.

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
        heat (str, optional): 'eurostat' or 'model', where the heating left
            out comes from. Defaults to 'eurostat'.
        previous (pd.DataFrame | None, optional): Output of previous_run_heat.
            Needed for 'model' heat; with 'eurostat' heat it only fills the
            previous-run columns of the summary.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: The level per 'Region' and 'User'
            ('Value', MWh) of the countries written, and the summary per
            country (TWh). 'InputTWh' is the input data's DE, which after a
            first run is the previous level. 'ResidualTWh' is the model-heat
            level less the previous run's exogenous load: what that run's
            load missed ENTSO-E's by, at final-consumption level.
    """
    if basis not in DEMAND_LEVEL_BASES:
        raise ValueError(f"Unknown demand level basis '{basis}', use one of {DEMAND_LEVEL_BASES}")
    if heat not in HEAT_SOURCES:
        raise ValueError(f"Unknown heat source '{heat}', use one of {HEAT_SOURCES}")
    model_heat = heat == "model"
    if model_heat and basis != "entsoe":
        raise ValueError("Heat from the previous run ('model') needs the 'entsoe' basis")
    if model_heat and previous is None:
        raise ValueError("Heat from the previous run ('model') needs the previous run's results (previous_run_heat)")

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

    # The previous run over Balmorel's year, summed to canonical regions (DE4-* to DE, LU on its own)
    if previous is not None:
        to_year = BALMOREL_YEAR_HOURS / (len(SEASONS) * len(TERMS))
        prev = (previous[["EXO", "E2H", "TLoss"]] * to_year).groupby(previous.index.map(canonical_region)).sum()
        canonical = canonical.join(prev.rename(columns={"EXO": "PrevExo"}))
        canonical["InPrevious"] = canonical.index.isin(prev.index)
        canonical["ModelLevel"] = (canonical["Load"] - canonical["TLoss"]) * (1 - canonical["DisLoss"]) - canonical["E2H"]
    else:
        canonical[["PrevExo", "E2H", "TLoss", "ModelLevel"]] = float("nan")
        canonical["InPrevious"] = False

    balances = balances.reindex(columns=[FINAL_CONSUMPTION, *HEATING]) * 1e3
    summary, levels = [], []
    for country, group in canonical.groupby("Country"):
        load_c, net_c = group["Load"].sum(min_count=len(group)), group["NetLoad"].sum(min_count=len(group))
        eurostat = balances.loc[country] if country in balances.index else pd.Series(index=balances.columns, dtype=float)
        heating = eurostat[list(HEATING)]
        heat_c = heating.sum(min_count=1)
        final_c = eurostat[FINAL_CONSUMPTION]
        coverage = net_c / final_c if final_c > 0 else float("nan")
        e2h_c, tloss_c, prev_exo_c = (group[column].sum(min_count=len(group)) for column in ("E2H", "TLoss", "PrevExo"))
        model_level_c = group["ModelLevel"].sum(min_count=len(group))

        if model_heat:
            region_levels = group["ModelLevel"]
        elif basis == "entsoe":
            region_levels = group["NetLoad"] - heat_c * group["Load"] / load_c
        else:
            region_levels = (final_c - heat_c) * group["NetLoad"] / net_c
        level_c = region_levels.sum(min_count=len(group))
        missing = list(group.index[~group["InPrevious"]])

        if pd.isna(load_c):
            note = "no ENTSO-E load"
        elif model_heat and missing:
            note = "not in the previous run" + (f" ({', '.join(missing)})" if len(missing) < len(group) else "")
        elif not model_heat and pd.isna(final_c):
            note = "no Eurostat final consumption"
        elif not model_heat and heating.isna().all():
            note = "no Eurostat electricity for heating"
        elif pd.notna(final_c) and not coverage_bounds[0] <= coverage <= coverage_bounds[1]:
            note = f"coverage {coverage:.2f} outside {coverage_bounds[0]}-{coverage_bounds[1]}"
        elif not (level_c > 0 and (region_levels > 0).all()):
            note = "level not positive"
        elif (group["Base"] <= 0).any():
            note = "a canonical region without base DE to split by"
        else:
            note = ""
        written = not note
        if written and pd.isna(final_c):
            note = "no Eurostat final consumption, coverage not checked"

        summary.append(
            {
                "Country": country,
                "LoadTWh": load_c / 1e6,
                "DisLoss": 1 - net_c / load_c if load_c > 0 else float("nan"),
                "FC_E_TWh": final_c / 1e6,
                "Coverage": coverage,
                **{f"{balance}_TWh": heating[balance] / 1e6 for balance in HEATING},
                "HeatTWh": heat_c / 1e6,
                "HeatSource": heat,
                "TransLossTWh": tloss_c / 1e6,
                "E2H_TWh": e2h_c / 1e6,
                "E2H_minus_H_TWh": (e2h_c - heat_c) / 1e6,
                "PrevExoTWh": prev_exo_c / 1e6,
                "InputTWh": group["Base"].sum() / 1e6,
                "NewTWh": level_c / 1e6 if written else float("nan"),
                "ResidualTWh": (model_level_c - prev_exo_c) / 1e6,
                "Written": written,
                "Note": note,
            }
        )
        if not written:
            warn(f"{country} keeps the input data's DE: {note}.")
            continue

        for region, row in group.iterrows():
            users = de[de["Region"].isin(regions.index[regions["Canonical"] == region])]
            levels.append(
                users.assign(Value=users["Value"] * region_levels[region] / row["Base"])[["Region", "User", "Value"]]
            )

    levels = pd.concat(levels, ignore_index=True) if levels else pd.DataFrame(columns=["Region", "User", "Value"])

    return levels, pd.DataFrame(summary)


def check_previous_run(previous: pd.DataFrame, de_entsoe_path: str | Path, year: int) -> None:
    """Warn where the previous run's exogenous load isn't the Demand Level it should have solved with.

    The previous run's EXOGENOUS over the calendar's 8736 hours is DE x
    8736/8760. A region more than PREVIOUS_RUN_TOLERANCE off means that run
    solved with another DE_ENTSOE.inc (or none), so its heating and losses
    belong to another level.

    Args:
        previous (pd.DataFrame): Output of previous_run_heat.
        de_entsoe_path (str | Path): The scenario's current DE_ENTSOE.inc.
        year (int): The Backcast Year.
    """
    de_entsoe_path = Path(de_entsoe_path)
    run = previous.attrs.get("scenario", "the previous run")
    if not de_entsoe_path.exists():
        warn(f"There is no {de_entsoe_path}, so {run} can't be checked against the demand level it solved with.")
        return

    pattern = re.compile(rf"^DE\('{year}','([^']+)','[^']+'\)\s*=\s*([-+0-9.eE]+);", re.MULTILINE)
    current = pd.DataFrame(pattern.findall(de_entsoe_path.read_text()), columns=["Region", "Value"])
    if current.empty:
        warn(f"{de_entsoe_path} has no DE for {year}, so {run} can't be checked against it.")
        return
    current = current.astype({"Value": float}).groupby("Region")["Value"].sum()

    solved = previous["EXO"].reindex(current.index).fillna(0.0) * BALMOREL_YEAR_HOURS / (len(SEASONS) * len(TERMS))
    off = solved / current - 1
    off = off[off.abs() > PREVIOUS_RUN_TOLERANCE]
    if not off.empty:
        warn(
            f"{run} did not solve with this {de_entsoe_path.name}: its exogenous load is more than "
            f"{PREVIOUS_RUN_TOLERANCE:.0%} off the level in {len(off)} regions "
            f"({', '.join(f'{region} {value:+.1%}' for region, value in off.items())}). Its heating and "
            "losses belong to another level: `format` the run that solved with this file first."
        )


def check_de_wrappers(data_path: str | Path, base_data_path: str | Path) -> None:
    """Warn if a DE addon of base runs without the scenario re-applying DE_ENTSOE.inc after it.

    The INDUSTRY and INDIVUSERS addons adjust DE after DE.inc, so the
    scenario needs its own INDUSTRY_DE.inc and INDIVUSERS_DE.inc that include
    base's and then DE_ENTSOE.inc again. Otherwise Balmorel solves with
    another DE than the Demand Level.

    Args:
        data_path (str | Path): The scenario's 'data' folder.
        base_data_path (str | Path): base/data.
    """
    for addon in DE_ADDONS:
        if not (Path(base_data_path) / addon).exists():
            continue
        wrapper = Path(data_path) / addon
        if not wrapper.exists():
            warn(
                f"There is no {wrapper}, so base's {addon} adjusts DE after DE_ENTSOE.inc and Balmorel "
                f"doesn't solve with the demand level. Add one with\n$include '../../base/data/{addon}';\n"
                "$if EXIST '../data/DE_ENTSOE.inc' $INCLUDE '../data/DE_ENTSOE.inc';"
            )
            continue
        lines = [line for line in wrapper.read_text().splitlines() if not line.lstrip().startswith("*")]
        if not any("DE_ENTSOE.inc" in line for line in lines):
            warn(
                f"{wrapper} doesn't include DE_ENTSOE.inc after base's {addon}, so Balmorel doesn't solve "
                "with the demand level. End it with\n$if EXIST '../data/DE_ENTSOE.inc' $INCLUDE '../data/DE_ENTSOE.inc';"
            )


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


def write_de_override(
    levels: pd.DataFrame,
    year: int,
    basis: str,
    scenario_data_path: str | Path,
    heat: str = "eurostat",
    previous_scenario: str | None = None,
) -> IncFile:
    """Write DE_ENTSOE.inc with the Demand Level of `year`.

    Args:
        levels (pd.DataFrame): The levels of demand_levels.
        year (int): The Backcast Year.
        basis (str): 'entsoe' or 'eurostat'.
        scenario_data_path (str | Path): The scenario's 'data' folder.
        heat (str, optional): 'eurostat' or 'model'. Defaults to 'eurostat'.
        previous_scenario (str | None, optional): The run the heating came
            from, named in the header with 'model' heat.

    Returns:
        IncFile: The saved IncFile instance.
    """
    if heat == "model":
        prefix = (
            f"* Electricity demand level for {year}: ENTSO-E load less transmission losses, net of\n"
            f"* distribution losses, less the electricity {previous_scenario or 'the previous run'} used for heat\n"
            "* (ENDOGENOUS_ELECT2HEAT, see CONTEXT.md) - generated, do not hand-edit\n"
        )
    else:
        source = (
            "ENTSO-E load net of distribution losses"
            if basis == "entsoe"
            else "Eurostat final electricity consumption"
        )
        prefix = (
            f"* Electricity demand level for {year}: {source}, less\n"
            "* Eurostat electricity for heating (see CONTEXT.md) - generated, do not hand-edit\n"
        )
    lines = [
        f"DE('{year}','{row.Region}','{row.User}')={row.Value:.1f};\n"
        for row in levels.sort_values(["Region", "User"]).itertuples()
    ]

    inc_file = IncFile(
        prefix=prefix,
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
    heat: str = "model",
    load_results: str | Path | None = None,
) -> IncFile:
    """Write DE_ENTSOE.inc and backcastoutput/demand_level.csv for a Balmorel scenario.

    The scenario's DE.inc must include DE_ENTSOE.inc after base's DE.inc, and
    its INDUSTRY_DE.inc and INDIVUSERS_DE.inc again after base's. With 'model'
    heat, the heating and transmission losses come from the previous run's
    balmorel_load.csv, which must be the run that solved with the scenario's
    current DE_ENTSOE.inc (warned about if not). Its residual is printed, for
    the user to decide whether to iterate again.

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
        heat (str, optional): 'model' takes the heating from the previous
            run, 'eurostat' from Eurostat (the first run of a new Backcast
            Year). Defaults to 'model'.
        load_results (str | Path | None, optional): The previous run's
            balmorel_load.csv. Defaults to <scenario>/backcastoutput/balmorel_load.csv.

    Raises:
        FileNotFoundError: With 'model' heat, if there is no previous run.

    Returns:
        IncFile: The saved IncFile instance.
    """
    scenario_path = Path(balmorel_model_folder) / scenario
    if heat not in HEAT_SOURCES:
        raise ValueError(f"Unknown heat source '{heat}', use one of {HEAT_SOURCES}")
    if heat == "model" and basis != "entsoe":
        raise ValueError("Heat from the previous run ('model') needs the 'entsoe' basis")

    previous = None
    if heat == "model":
        load_results = Path(load_results) if load_results else scenario_path / "backcastoutput" / "balmorel_load.csv"
        if not load_results.exists():
            raise FileNotFoundError(
                f"No previous backcast run at {load_results}: run `format` on a solved backcast first, "
                "or use `--heat eurostat` for the first run of a new backcast year"
            )
        previous = previous_run_heat(load_results, year)
        print(f"Taking electric heating and transmission losses from {previous.attrs['scenario']} ({load_results})")
        check_previous_run(previous, scenario_path / "data" / "DE_ENTSOE.inc", year)
    check_de_wrappers(scenario_path / "data", Path(balmorel_model_folder) / "base" / "data")

    if eurostat_data_path is None:
        eurostat_data_path = scenario_path / "eurostatdata"
    balances = electricity_balances(year, eurostat_data_path)

    model = load_input_data(balmorel_model_folder, scenario, gams_system_directory, reload_input, ("DE_ENTSOE.inc",))
    load = split_shared_load(annual_load(sum_zones(zones), year), balances)
    levels, summary = demand_levels(
        model.get_input("DE"), model.get_input("DISLOSS_E"), load, balances, year, basis, coverage_bounds,
        heat=heat, previous=previous,
    )

    output_path = scenario_path / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    summary.to_csv(output_path / "demand_level.csv", index=False)
    written = summary[summary["Written"]]
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 250):
        print(summary.set_index("Country").round(2))
    print(
        f"DE of the {len(written)} countries written goes from {written['InputTWh'].sum():.1f} TWh "
        f"to {written['NewTWh'].sum():.1f} TWh"
    )
    if previous is not None:
        residual = written["ResidualTWh"]
        print(
            f"Residual of {previous.attrs['scenario']} over these countries: {residual.sum():+.1f} TWh in "
            f"Europe, {residual.abs().sum():.1f} TWh summed over countries. Its load missed ENTSO-E's by this; "
            "iterate while it falls (about 10 TWh summed is as close as other errors allow)."
        )

    inc_file = write_de_override(
        levels, year, basis, scenario_path / "data", heat=heat,
        previous_scenario=previous.attrs["scenario"] if previous is not None else None,
    )
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

"""
Absolute Hydro FLH

Hydro full-load hours as CorRES inflow energy divided by the Balmorel capacity
that receives it (`hydro_flh: mode: absolute`), instead of a factor on
Balmorel's base FLH. Run-of-river energy above the run-of-river capacity moves
to the same area's reservoir, and countries whose CorRES inflow fails a
plausibility check, or that CorRES covers only partly or not at all, get the
Hydro Inflow Fallback (see CONTEXT.md, ADR 0011).

Everything but load_balmorel_hydro_inputs works on DataFrames, so it can be
tested without GAMS.

Created on 22.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import hashlib
import re

import pandas as pd

from .config_models import HydroFlhConfig
from .hydro_reference import hydro_natural_inflow_twh

# Balmorel symbols per hydro type: reservoir and run-of-river
RESERVOIR = "WTRRSFLH"
RUN_OF_RIVER = "WTRRRFLH"
HYDRO_SYMBOLS = (RESERVOIR, RUN_OF_RIVER)

# Largest relative deviation of a country's long-term CorRES energy from the reference
PLAUSIBLE_DEVIATION = 0.2

HOURS_PER_YEAR = 8760

#%% ------------------------------- ###
###     1. Balmorel inputs          ###
### ------------------------------- ###


def region_country(region: str) -> str:
    """The country of a Balmorel region: its first two letters ('DE4-E' -> 'DE', 'FIN' -> 'FI', 'NO1' -> 'NO')."""
    match = re.match(r"[A-Z]{2}", region)
    return match.group(0) if match else region


def hydro_capacity(
    gkfx: pd.DataFrame, ighyrs: pd.DataFrame, ighyrr: pd.DataFrame, year: int
) -> pd.DataFrame:
    """The reservoir and run-of-river GKFX per area in `year`.

    Columns are taken by position, as get_input may name them after the raw
    GAMS domains.

    Args:
        gkfx (pd.DataFrame): GKFX from get_input, ending in (Y, AAA, G, Value).
        ighyrs (pd.DataFrame): IGHYRS from get_input, ending in G.
        ighyrr (pd.DataFrame): IGHYRR from get_input, ending in G.
        year (int): The Y of GKFX.

    Returns:
        pd.DataFrame: Index area, columns 'WTRRSFLH' (reservoir) and
            'WTRRRFLH' (run-of-river), MW.
    """
    if ighyrs.empty and ighyrr.empty:
        raise Exception(
            "IGHYRS and IGHYRR are empty, so the hydro capacity can't be found. The input "
            "data was probably read with an old Balmorelbb4_ReadData.inc that doesn't assign "
            "them: delete <scenario>/model/<scenario>_input_data.gdx and "
            "<scenario>/model/Balmorelbb4_ReadData.inc, then run again."
        )
    gkfx = gkfx.iloc[:, -4:].set_axis(["Year", "Area", "Technology", "Capacity"], axis=1)
    gkfx = gkfx[gkfx["Year"].astype(str) == str(year)]

    capacity = {}
    for symbol, technologies in ((RESERVOIR, ighyrs), (RUN_OF_RIVER, ighyrr)):
        technologies = technologies.iloc[:, -1] if not technologies.empty else pd.Series(dtype=object)
        capacity[symbol] = (
            gkfx[gkfx["Technology"].isin(technologies)]
            .groupby("Area")["Capacity"]
            .sum()
            .astype(float)
        )

    return pd.DataFrame(capacity).fillna(0.0).rename_axis("Area")


def area_countries(rrraaa: pd.DataFrame) -> pd.Series:
    """The country of every area, from RRRAAA (from get_input, ending in (RRR, AAA))."""
    rrraaa = rrraaa.iloc[:, -2:].set_axis(["Region", "Area"], axis=1)
    return rrraaa.set_index("Area")["Region"].map(region_country)


def base_flh(wtrrsflh: pd.DataFrame, wtrrrflh: pd.DataFrame) -> pd.DataFrame:
    """Balmorel's base FLH per area, from WTRRSFLH and WTRRRFLH (from get_input, ending in (AAA, Value))."""
    return pd.DataFrame(
        {
            symbol: df.iloc[:, -2:].set_axis(["Area", "Value"], axis=1).set_index("Area")["Value"].astype(float)
            for symbol, df in ((RESERVOIR, wtrrsflh), (RUN_OF_RIVER, wtrrrflh))
        }
    ).rename_axis("Area")


def load_balmorel_hydro_inputs(
    config: HydroFlhConfig, gams_system_directory: str | None = None
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Read hydro capacity, area countries and base FLH from the Balmorel model.

    Capacity and countries come from `config.scenario`, the base FLH from the
    'base' scenario, since the scenario's own FLH files are the ones being written.

    Args:
        config (HydroFlhConfig): The absolute-mode config.
        gams_system_directory (str | None, optional): GAMS system directory.

    Returns:
        tuple[pd.DataFrame, pd.Series, pd.DataFrame]: Output of hydro_capacity,
            area_countries and base_flh.
    """
    # Imported here, as classes imports this module's caller
    from ..classes import Balmorel

    model = Balmorel(config.balmorel_path, gams_system_directory=gams_system_directory)
    model.load_incfiles(config.scenario)
    capacity = hydro_capacity(
        model.get_input("GKFX"),
        model.get_input("IGHYRS"),
        model.get_input("IGHYRR"),
        config.capacity_year,
    )
    countries = area_countries(model.get_input("RRRAAA"))

    base_model = Balmorel(config.balmorel_path, gams_system_directory=gams_system_directory)
    base_model.load_incfiles("base")
    flh_base = base_flh(base_model.get_input("WTRRSFLH"), base_model.get_input("WTRRRFLH"))

    return capacity, countries, flh_base


#%% ------------------------------- ###
###     2. Energy and spill         ###
### ------------------------------- ###


def yearly_energy(inflow: pd.DataFrame) -> pd.DataFrame:
    """The inflow energy per year and area (MWh), from hourly mean MW."""
    return inflow.groupby(inflow.index.year).sum()


def move_spilled_run_of_river(
    res: pd.DataFrame, ror: pd.DataFrame, capacity: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The yearly energies after moving run-of-river energy Balmorel can't take to the reservoir.

    Per year and area, the spill is the run-of-river inflow above the
    run-of-river capacity, summed over the hours (all of it without
    run-of-river capacity). With reservoir capacity in the area it moves to
    the reservoir; without, it stays and is reported.

    Args:
        res (pd.DataFrame): Hourly reservoir inflow (MW) per area.
        ror (pd.DataFrame): Hourly run-of-river inflow (MW) per area.
        capacity (pd.DataFrame): Output of hydro_capacity.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: Yearly reservoir and run-of-river
            energy (MWh), index year, one column per area.
    """
    res_energy = yearly_energy(res)
    ror_energy = yearly_energy(ror)

    for area in ror.columns:
        ror_capacity = capacity[RUN_OF_RIVER].get(area, 0.0)
        res_capacity = capacity[RESERVOIR].get(area, 0.0)
        spill = yearly_energy((ror[[area]] - ror_capacity).clip(lower=0))[area]
        if spill.sum() == 0:
            continue
        if res_capacity > 0:
            ror_energy[area] -= spill
            res_energy[area] = res_energy.get(area, 0.0) + spill
        elif ror_capacity > 0:
            print(
                f"Warning: {area} has run-of-river inflow above its {ror_capacity:.0f} MW of capacity "
                f"but no reservoir to take it; Balmorel will spill {spill.mean() / 1e6:.2f} TWh/yr on average."
            )

    return res_energy, ror_energy


#%% ------------------------------- ###
###  3. Plausibility and fallback   ###
### ------------------------------- ###


def _column_digest(column: pd.Series) -> str:
    return hashlib.sha1(column.to_numpy().tobytes()).hexdigest()


def missing_columns(res: pd.DataFrame, ror: pd.DataFrame, capacity: pd.DataFrame) -> dict[str, list[str]]:
    """The (area, type) pairs with hydro capacity but no CorRES column, per symbol."""
    return {
        symbol: sorted(capacity.index[capacity[symbol] > 0].difference(inflow.columns))
        for symbol, inflow in ((RESERVOIR, res), (RUN_OF_RIVER, ror))
    }


def plausibility_failures(
    res: pd.DataFrame,
    ror: pd.DataFrame,
    capacity: pd.DataFrame,
    countries: pd.Series,
    reference: dict[str, float],
) -> dict[str, str]:
    """The countries whose CorRES inflow fails the plausibility check, with the reason.

    A country fails if a reservoir column equals the run-of-river column of
    the same area, if a column equals another area's column in either file,
    if its long-term CorRES energy is more than PLAUSIBLE_DEVIATION from the
    reference, or if CorRES covers its hydro capacity only partly or not at
    all. A country missing from the reference can't be checked on its level
    and is reported.

    Args:
        res (pd.DataFrame): Hourly reservoir inflow (MW) per area.
        ror (pd.DataFrame): Hourly run-of-river inflow (MW) per area.
        capacity (pd.DataFrame): Output of hydro_capacity.
        countries (pd.Series): Output of area_countries.
        reference (dict[str, float]): Long-term Natural-Inflow Hydro per country (TWh/yr).

    Returns:
        dict[str, str]: Failing country -> reason.
    """
    failures = {}

    columns = {}
    for kind, inflow in (("reservoir", res), ("run-of-river", ror)):
        for area in inflow.columns:
            if inflow[area].abs().sum() > 0:
                columns.setdefault(_column_digest(inflow[area]), []).append((area, kind))
    for duplicates in columns.values():
        areas = sorted({area for area, _ in duplicates})
        for area, kind in duplicates:
            country = countries.get(area)
            if country is None or country in failures:
                continue
            if len(areas) > 1:
                others = ", ".join(f"{other} ({other_kind})" for other, other_kind in duplicates if other != area)
                failures[country] = f"{area}'s {kind} inflow is identical to {others}"
            elif len(duplicates) > 1:
                failures[country] = f"{area}'s reservoir inflow is identical to its run-of-river inflow"

    long_term = pd.concat((yearly_energy(res), yearly_energy(ror)), axis=1).mean()
    long_term = long_term.groupby(long_term.index.map(countries.get)).sum() / 1e6

    uncovered = {}
    for symbol, areas in missing_columns(res, ror, capacity).items():
        kind = "reservoir" if symbol == RESERVOIR else "run-of-river"
        for area in areas:
            uncovered.setdefault(countries.get(area), []).append(f"{area} ({kind})")
    uncovered.pop(None, None)
    for country, pairs in sorted(uncovered.items()):
        if country in failures:
            continue
        if country in long_term.index:
            failures[country] = f"CorRES covers it only partly, with no column for {', '.join(pairs)}"
        else:
            failures[country] = "CorRES has no column for it"

    for country, energy in long_term.items():
        if country not in reference:
            print(
                f"Warning: {country} has no reference Natural-Inflow Hydro, so its CorRES "
                f"inflow ({energy:.2f} TWh/yr) can't be checked on its level."
            )
            continue
        deviation = energy / reference[country] - 1 if reference[country] else float("inf")
        if abs(deviation) > PLAUSIBLE_DEVIATION and country not in failures:
            failures[country] = (
                f"long-term CorRES inflow of {energy:.2f} TWh/yr is {deviation:+.0%} "
                f"from the observed {reference[country]:.2f} TWh/yr"
            )

    if not long_term.empty and set(long_term.index) <= set(failures):
        raise Exception(
            f"Every country with CorRES inflow fails the hydro plausibility check ({failures}). "
            "That points to wrong units in the inflow files, not to the data."
        )

    return failures


def country_factor(res: pd.DataFrame, ror: pd.DataFrame, areas: list[str], year: int) -> float:
    """The relative factor of a country's CorRES inflow in `year`: its energy in `year` / its long-term mean.

    1 if the country has no CorRES column.
    """
    energy = pd.concat(
        (yearly_energy(res[res.columns.intersection(areas)]), yearly_energy(ror[ror.columns.intersection(areas)])),
        axis=1,
    ).sum(axis=1)
    long_term = energy.mean() if not energy.empty else 0.0
    return energy.get(year, 0.0) / long_term if long_term > 0 else 1.0


def fallback_flh(
    country: str,
    capacity: pd.DataFrame,
    countries: pd.Series,
    flh_base: pd.DataFrame,
    factors: dict[str, pd.Series],
    missing_factor: float,
    reference: dict[str, float],
) -> pd.DataFrame:
    """The Hydro Inflow Fallback FLH for every hydro area and type of a country.

    FLH_a,t = E_c x f_a,t x FLHbase_a,t / sum over the country of (FLHbase x K),
    with E_c the reference long-term energy and f the relative factor of the
    year: the pair's own, or the country's for a pair without a CorRES column
    (1 in the long-term files). A missing FLHbase counts as 0, so that pair
    gets no line. A country without a reference value gets FLHbase x f.

    Args:
        country (str): The country.
        capacity (pd.DataFrame): Output of hydro_capacity.
        countries (pd.Series): Output of area_countries.
        flh_base (pd.DataFrame): Output of base_flh.
        factors (dict[str, pd.Series]): The relative factor per area with a
            CorRES column, for each symbol.
        missing_factor (float): The factor for pairs without a CorRES column.
        reference (dict[str, float]): Long-term Natural-Inflow Hydro per country (TWh/yr).

    Returns:
        pd.DataFrame: Index area, one column per symbol, NaN where the area
            has no capacity or base FLH of that type.
    """
    areas = [area for area in capacity.index if countries.get(area) == country]
    base = flh_base.reindex(index=areas, columns=list(HYDRO_SYMBOLS))
    weights = (base * capacity.loc[areas]).where(lambda df: df > 0)
    total = weights.sum().sum()
    if total == 0:
        print(f"Warning: {country} has no hydro capacity with a base FLH, so it gets no fallback.")
        return pd.DataFrame(columns=list(HYDRO_SYMBOLS), dtype=float)

    if country in reference:
        scale = reference[country] * 1e6 / total
    else:
        print(
            f"Warning: {country} needs the Hydro Inflow Fallback but has no reference "
            "Natural-Inflow Hydro, so it keeps Balmorel's base FLH times the relative factor."
        )
        scale = 1.0

    flh = pd.DataFrame(index=areas, columns=list(HYDRO_SYMBOLS), dtype=float)
    for symbol in HYDRO_SYMBOLS:
        factor = factors[symbol].reindex(areas).fillna(missing_factor)
        flh[symbol] = (scale * factor * base[symbol]).where(weights[symbol].notna())

    return flh


#%% ------------------------------- ###
###        4. Absolute FLH          ###
### ------------------------------- ###


def absolute_flh(
    res: pd.DataFrame,
    ror: pd.DataFrame,
    res_factors: pd.Series,
    ror_factors: pd.Series,
    year: int,
    capacity: pd.DataFrame,
    countries: pd.Series,
    flh_base: pd.DataFrame,
    reference: dict[str, float] = hydro_natural_inflow_twh,
) -> dict[str, tuple[pd.Series, pd.Series]]:
    """The Absolute Hydro FLH of `year` and of the long term, per symbol.

    Args:
        res (pd.DataFrame): Hourly reservoir inflow (MW) per area, all years.
        ror (pd.DataFrame): Hourly run-of-river inflow (MW) per area, all years.
        res_factors (pd.Series): The relative reservoir factor of `year` per area.
        ror_factors (pd.Series): The relative run-of-river factor of `year` per area.
        year (int): The weather year.
        capacity (pd.DataFrame): Output of hydro_capacity.
        countries (pd.Series): Output of area_countries.
        flh_base (pd.DataFrame): Output of base_flh.
        reference (dict[str, float], optional): Long-term Natural-Inflow Hydro
            per country (TWh/yr). Defaults to the bundled table.

    Returns:
        dict[str, tuple[pd.Series, pd.Series]]: Symbol -> (FLH of `year`,
            long-term FLH), indexed by area. Areas without a value get no line.
    """
    failures = plausibility_failures(res, ror, capacity, countries, reference)
    for country, reason in sorted(failures.items()):
        print(f"Warning: Hydro Inflow Fallback for {country}: {reason}.")

    # Fallback countries take their split from Balmorel's base FLH, so they skip the move
    def checked(inflow: pd.DataFrame) -> pd.DataFrame:
        return inflow[[area for area in inflow.columns if countries.get(area) not in failures]]

    res_energy, ror_energy = move_spilled_run_of_river(checked(res), checked(ror), capacity)
    energies = {RESERVOIR: res_energy, RUN_OF_RIVER: ror_energy}

    flh = {}
    for symbol, energy in energies.items():
        kind = "reservoir" if symbol == RESERVOIR else "run-of-river"
        type_capacity = capacity[symbol].reindex(energy.columns).fillna(0.0)

        for area in energy.columns[type_capacity == 0]:
            if energy.loc[year, area] > 0:
                print(
                    f"Warning: {area} has {energy.loc[year, area] / 1e6:.2f} TWh of {kind} inflow "
                    f"in {year} but no {kind} capacity, so it gets no {symbol}."
                )
        keep = type_capacity > 0
        flh[symbol] = (
            energy.loc[year, keep] / type_capacity[keep],
            energy.loc[:, keep].mean() / type_capacity[keep],
        )

    for country in sorted(failures):
        areas = [area for area in countries.index if countries[area] == country]
        year_flh = fallback_flh(
            country,
            capacity,
            countries,
            flh_base,
            {RESERVOIR: res_factors, RUN_OF_RIVER: ror_factors},
            country_factor(res, ror, areas, year),
            reference,
        )
        long_term_flh = fallback_flh(
            country,
            capacity,
            countries,
            flh_base,
            {RESERVOIR: pd.Series(dtype=float), RUN_OF_RIVER: pd.Series(dtype=float)},
            1.0,
            reference,
        )
        for symbol in HYDRO_SYMBOLS:
            flh[symbol] = (
                pd.concat((flh[symbol][0], year_flh[symbol].dropna())),
                pd.concat((flh[symbol][1], long_term_flh[symbol].dropna())),
            )

    for symbol, (year_values, long_term_values) in flh.items():
        flh[symbol] = (year_values.sort_index(), long_term_values.sort_index())
        too_high = pd.concat(flh[symbol]).loc[lambda values: values > HOURS_PER_YEAR]
        if not too_high.empty:
            raise Exception(
                f"{symbol} is above {HOURS_PER_YEAR} h in {too_high.round(0).to_dict()}. "
                "The inflow units are wrong or a country should have had the Hydro Inflow Fallback."
            )

    return flh


def absolute_flh_assignment_lines(series: pd.Series, symbol: str, header: str) -> pd.DataFrame:
    """Balmorel assignment lines setting `symbol` per area, after a header comment.

    Args:
        series (pd.Series): FLH per area.
        symbol (str): 'WTRRSFLH' or 'WTRRRFLH'.
        header (str): Comment line saying how the values were made.

    Returns:
        pd.DataFrame: A single column (symbol) of lines, for build_inc_file_list_type.
    """
    lines = [header] + [f"{symbol}('{area}') = {value:.2f} ;" for area, value in series.items()]
    return pd.DataFrame({symbol: lines})

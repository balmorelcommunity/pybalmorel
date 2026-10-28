"""
Thermal Availability

Turn ENTSO-E's installed generation capacity and outage reports into weekly
GKRATE overrides (GKRATE_THERMAL_ENTSOE.inc) for the fossil, biomass and
waste technologies of a Backcast: per canonical region, fuel group and
Backcast Calendar week, the installed capacity as a share of GKFX (at most 1)
less the share of it reported out of service (see CONTEXT.md). Observed
output is never an input here, since the fossil mix is a Validation Metric;
it only serves as a check in thermal_capacity.csv.

Also defines the fuel groups and the technology selection by acronym name
that the must-run floor shares.

Created on 28.10.2026
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

from ..classes import Balmorel, IncFile
from .calendar import N_SEASONS, SEASONS, first_monday
from .flows import canonical_region
from .nuclear import check_input_cache, format_rating

# A GAMS acronym is stored as its index times this
ACRONYM_SCALE = 1e301

# Technology types that produce electricity from a fuel
THERMAL_TYPES = ("GCND", "GBPR", "GEXT")

# Fuel groups, with GAMS-safe labels: Balmorel GDFUEL names and ENTSO-E production types
GROUP_FUELS = {
    "LIGNITE": ("LIGNITE",),
    "HARDCOAL": ("COAL",),
    # Retort gas is coke-oven gas, ENTSO-E's coal-derived gas
    "GAS": ("NATGAS", "OTHERGAS", "LNG", "RETORTGAS"),
    "OIL": ("FUELOIL", "LIGHTOIL"),
    "OILSHALE_PEAT": ("SHALE", "PEAT"),
    "BIOMASS": (
        "WOODCHIPS", "WOODPELLETS", "WOOD", "WOODWASTE", "STRAW", "BIOGAS", "BIOOIL", "BIOMETHANE",
    ),
    "WASTE": ("MUNIWASTE",),
}
GROUP_PRODUCTION_TYPES = {
    "LIGNITE": ("Fossil Brown coal/Lignite",),
    "HARDCOAL": ("Fossil Hard coal",),
    "GAS": ("Fossil Gas", "Fossil Coal-derived gas"),
    "OIL": ("Fossil Oil",),
    "OILSHALE_PEAT": ("Fossil Oil shale", "Fossil Peat"),
    "BIOMASS": ("Biomass",),
    "WASTE": ("Waste",),
}

# Thermal fuels that belong to no group, and why
UNGROUPED_FUELS = {
    "NUCLEAR": "rated by nuclear-availability",
    "DUMMY": "the backup generator",
    "HEAT": "no fuel of its own",
    "WASTEHEAT": "no fuel of its own",
}

# Groups in thermal_capacity.csv only, as a check for the VRE level: (GDTYPE, ENTSO-E types)
CHECK_ONLY_GROUPS = {
    "SOLAR": ("GSOLE", ("Solar",)),
    "WIND": ("GWND", ("Wind Onshore", "Wind Offshore")),
}

# Document statuses of outage events that didn't happen
VOID_DOCSTATUS = ("Cancelled", "Withdrawn")

# Business types of outage events
OUTAGE_KINDS = {"Planned maintenance": "Planned", "Unplanned outage": "Forced"}

GKRATE_THERMAL_INCLUDE = (
    "$if EXIST '../data/GKRATE_THERMAL_ENTSOE.inc' $INCLUDE '../data/GKRATE_THERMAL_ENTSOE.inc';"
)

# ------------------------------- #
#     1. Technologies by name     #
# ------------------------------- #


def acronym_names(gdx_path: str | Path, system_directory: str | None = None) -> dict[float, str]:
    """The names of the GAMS acronyms in a GDX file, keyed by the value GAMS stores for them.

    A GAMS acronym is stored as its index times ACRONYM_SCALE, so e.g. GCND
    with index 224 is 2.24e303 in GDATA. Look values up with acronym_name.

    Args:
        gdx_path (str | Path): The GDX file, e.g. <scenario>_input_data.gdx.
        system_directory (str | None, optional): GAMS system directory, whose
            GDX library is used. Defaults to None.

    Returns:
        dict[float, str]: Acronym name per stored value.
    """
    import gams.core.gdx as gdx

    handle = gdx.new_gdxHandle_tp()
    created, message = (
        gdx.gdxCreateD(handle, system_directory, gdx.GMS_SSSIZE)
        if system_directory
        else gdx.gdxCreate(handle, gdx.GMS_SSSIZE)
    )
    if not created:
        raise Exception(
            f"Could not load the GDX library to read acronyms: {message}. "
            "Set GAMS_SYSTEM_DIR to your GAMS installation."
        )
    try:
        opened, error = gdx.gdxOpenRead(handle, str(gdx_path))
        if not opened:
            raise Exception(f"Could not open {gdx_path} (GDX error {error})")
        names = {}
        for number in range(1, gdx.gdxAcronymCount(handle) + 1):
            _, name, _, index = gdx.gdxAcronymGetInfo(handle, number)
            names[index * ACRONYM_SCALE] = name
        gdx.gdxClose(handle)
    finally:
        gdx.gdxFree(handle)

    return names


def acronym_name(value: float, names: dict[float, str]) -> str | None:
    """The name of the acronym stored as `value`, or None if it isn't one."""
    if not np.isfinite(value) or value < ACRONYM_SCALE:
        return None
    return names.get(round(value / ACRONYM_SCALE) * ACRONYM_SCALE)


def technology_fuels(gdata: pd.DataFrame, names: dict[float, str]) -> pd.DataFrame:
    """GDTYPE and GDFUEL of every technology, by acronym name.

    Args:
        gdata (pd.DataFrame): GDATA from get_input, ending in (G, GDATASET, Value).
        names (dict[float, str]): Output of acronym_names.

    Returns:
        pd.DataFrame: Index 'Technology', columns 'Type' and 'Fuel'.
    """
    gdata = gdata.iloc[:, -3:].set_axis(["Technology", "Parameter", "Value"], axis=1)
    gdata = gdata[gdata["Parameter"].isin(["GDTYPE", "GDFUEL"])]
    gdata = gdata.assign(Value=gdata["Value"].astype(float).map(lambda value: acronym_name(value, names)))

    return (
        gdata.pivot_table(index="Technology", columns="Parameter", values="Value", aggfunc="first")
        .reindex(columns=["GDTYPE", "GDFUEL"])
        .set_axis(["Type", "Fuel"], axis=1)
    )


def group_capacity(
    gkfx: pd.DataFrame,
    gdata: pd.DataFrame,
    rrraaa: pd.DataFrame,
    names: dict[float, str],
    year: int,
    check_only: bool = False,
) -> pd.DataFrame:
    """The GKFX of `year` per area and technology of every fuel group, with its canonical region.

    Technologies are selected by the names of their GDTYPE (THERMAL_TYPES)
    and GDFUEL acronyms. Columns are taken by position, as get_input may
    name them after the raw GAMS domains.

    Args:
        gkfx (pd.DataFrame): GKFX from get_input, ending in (Y, AAA, G, Value).
        gdata (pd.DataFrame): GDATA from get_input, ending in (G, GDATASET, Value).
        rrraaa (pd.DataFrame): RRRAAA from get_input, ending in (RRR, AAA).
        names (dict[float, str]): Output of acronym_names.
        year (int): The Backcast Year, the Y of GKFX.
        check_only (bool, optional): Also include CHECK_ONLY_GROUPS (solar
            and wind). Defaults to False.

    Raises:
        ValueError: If a thermal technology with GKFX > 0 has a fuel that is
            in no group and not in UNGROUPED_FUELS.

    Returns:
        pd.DataFrame: Columns 'Area', 'Technology', 'BalmorelRegion',
            'Region' (canonical), 'Fuel', 'Group' and 'Capacity' (MW), for
            every grouped (area, technology) with GKFX > 0.
    """
    gkfx = gkfx.iloc[:, -4:].set_axis(["Year", "Area", "Technology", "Capacity"], axis=1)
    gkfx = gkfx[(gkfx["Year"].astype(str) == str(year)) & (gkfx["Capacity"].astype(float) > 0)]
    rrraaa = rrraaa.iloc[:, -2:].set_axis(["BalmorelRegion", "Area"], axis=1)
    capacity = gkfx.merge(technology_fuels(gdata, names), left_on="Technology", right_index=True)
    capacity["Capacity"] = capacity["Capacity"].astype(float)

    fuel_group = {fuel: group for group, fuels in GROUP_FUELS.items() for fuel in fuels}
    thermal = capacity[capacity["Type"].isin(THERMAL_TYPES)]
    unmapped = set(thermal["Fuel"]) - fuel_group.keys() - UNGROUPED_FUELS.keys()
    if unmapped:
        energy = thermal[thermal["Fuel"].isin(unmapped)].groupby("Fuel")["Capacity"].sum()
        listing = ", ".join(f"{fuel} ({mw:.0f} MW)" for fuel, mw in energy.items())
        raise ValueError(
            f"Electricity-producing fuels in no fuel group: {listing}. Add them to GROUP_FUELS "
            "or UNGROUPED_FUELS in pybalmorel/backcasting/thermal.py."
        )
    capacity["Group"] = np.where(
        capacity["Type"].isin(THERMAL_TYPES), capacity["Fuel"].map(fuel_group), None
    )
    if check_only:
        for group, (technology_type, _) in CHECK_ONLY_GROUPS.items():
            capacity.loc[capacity["Type"] == technology_type, "Group"] = group

    capacity = capacity.dropna(subset=["Group"]).merge(rrraaa, on="Area", how="left")
    capacity["Region"] = capacity["BalmorelRegion"].map(canonical_region, na_action="ignore")

    return capacity[
        ["Area", "Technology", "BalmorelRegion", "Region", "Fuel", "Group", "Capacity"]
    ].reset_index(drop=True)


# ------------------------------- #
#        2. ENTSO-E reports       #
# ------------------------------- #


def _region_from_file(path: Path, year: int, query: str) -> str:
    from ..entsoe import entsoe_code_to_region

    return canonical_region(
        entsoe_code_to_region(path.name.removeprefix(f"{year}_").removesuffix(f"_{query}.csv"))
    )


def load_installed_capacity(entsoe_data_path: str | Path, year: int) -> pd.DataFrame:
    """ENTSO-E's installed generation capacity of `year` per canonical region and production type.

    Zones of one canonical region are summed. A production type a zone
    doesn't report is missing, not 0.

    Args:
        entsoe_data_path (str | Path): Folder with the installed_generation_capacity csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index canonical region, one column per production type (MW).
    """
    installed = {}
    query = "installed_generation_capacity"
    for path in sorted(Path(entsoe_data_path).glob(f"{year}_*_{query}.csv")):
        df = pd.read_csv(path, index_col=0)
        if df.shape[0] and any(isinstance(value, str) for value in df.iloc[0]):
            df = pd.read_csv(path, index_col=0, header=[0, 1])
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.apply(pd.to_numeric, errors="coerce")
        in_year = df[df.index.tz_convert("Europe/Brussels").year == year]
        row = (in_year if not in_year.empty else df).iloc[-1]
        region = _region_from_file(path, year, query)
        installed[region] = row if region not in installed else installed[region].add(row, fill_value=0)

    return pd.DataFrame(installed).T


def load_unavailability(entsoe_data_path: str | Path, year: int) -> pd.DataFrame:
    """ENTSO-E's outage reports of generation units, with the canonical region of each file.

    Args:
        entsoe_data_path (str | Path): Folder with the unavailability_of_generation_units csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: The reports as entsoe-py returns them, plus 'Region'.
            Empty if there are no files.
    """
    query = "unavailability_of_generation_units"
    frames = []
    for path in sorted(Path(entsoe_data_path).glob(f"{year}_*_{query}.csv")):
        df = pd.read_csv(path)
        df["Region"] = _region_from_file(path, year, query)
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def group_installed(installed: pd.DataFrame, groups: dict[str, tuple[str, ...]]) -> pd.Series:
    """Installed capacity per canonical region and group; missing where no type of the group is reported.

    Args:
        installed (pd.DataFrame): Output of load_installed_capacity.
        groups (dict[str, tuple[str, ...]]): ENTSO-E production types per group.

    Returns:
        pd.Series: Index (Region, Group), MW.
    """
    grouped = {
        group: installed.reindex(columns=list(production_types)).sum(axis=1, min_count=1)
        for group, production_types in groups.items()
    }
    return pd.DataFrame(grouped, index=installed.index).stack().rename_axis(["Region", "Group"])


def latest_outages(unavailability: pd.DataFrame) -> pd.DataFrame:
    """The outage periods of the latest revision of every event, without cancelled or withdrawn events.

    Args:
        unavailability (pd.DataFrame): Output of load_unavailability.

    Returns:
        pd.DataFrame: Columns 'Region', 'Group', 'Kind' ('Planned' or
            'Forced'), 'Start', 'End' (UTC) and 'Lost' (MW out of service),
            one row per period of an event.
    """
    columns = ["Region", "Group", "Kind", "Start", "End", "Lost"]
    if unavailability.empty:
        return pd.DataFrame(columns=columns)

    latest = unavailability.groupby("mrid")["revision"].transform("max")
    outages = unavailability[
        (unavailability["revision"] == latest) & ~unavailability["docstatus"].isin(VOID_DOCSTATUS)
    ]
    type_group = {
        production_type: group
        for group, production_types in GROUP_PRODUCTION_TYPES.items()
        for production_type in production_types
    }

    return pd.DataFrame(
        {
            "Region": outages["Region"],
            "Group": outages["plant_type"].map(type_group),
            "Kind": outages["businesstype"].map(OUTAGE_KINDS).fillna("Forced"),
            "Start": pd.to_datetime(outages["start"], utc=True),
            "End": pd.to_datetime(outages["end"], utc=True),
            "Lost": (outages["nominal_power"] - outages["avail_qty"]).clip(lower=0),
        }
    ).dropna(subset=["Group", "Lost"])[columns].reset_index(drop=True)


def weekly_outage_energy(outages: pd.DataFrame, year: int) -> pd.DataFrame:
    """Energy out of service (MWh) per region, group, kind and Backcast Calendar week.

    Each period counts its MW out of service times its hours of overlap with
    the week.

    Args:
        outages (pd.DataFrame): Output of latest_outages.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index (Region, Group, Season), columns 'Planned' and 'Forced' (MWh).
    """
    calendar_start = first_monday(year)
    week = pd.Timedelta(days=7)
    calendar_end = calendar_start + N_SEASONS * week
    energy = {}
    for row in outages.itertuples():
        start, end = max(row.Start, calendar_start), min(row.End, calendar_end)
        if end <= start:
            continue
        for index in range((start - calendar_start) // week, (end - calendar_start - pd.Timedelta(1)) // week + 1):
            week_start = calendar_start + index * week
            hours = (min(end, week_start + week) - max(start, week_start)) / pd.Timedelta(hours=1)
            key = (row.Region, row.Group, SEASONS[index], row.Kind)
            energy[key] = energy.get(key, 0.0) + row.Lost * hours

    if not energy:
        return pd.DataFrame(
            columns=["Planned", "Forced"],
            index=pd.MultiIndex.from_tuples([], names=["Region", "Group", "Season"]),
        )
    energy = pd.Series(energy)
    energy.index.names = ["Region", "Group", "Season", "Kind"]

    return energy.unstack("Kind").reindex(columns=["Planned", "Forced"]).fillna(0.0)


# ------------------------------- #
#           3. Ratings            #
# ------------------------------- #


def thermal_ratings(
    capacity: pd.DataFrame,
    installed: pd.Series,
    outage_energy: pd.DataFrame | None,
) -> pd.DataFrame:
    """The weekly Thermal Availability per canonical region and group.

    k = min(1, installed / GKFX); u = energy out of service in the week /
    (installed x 168); rating = k (1 - u), clipped to [0, 1]. A group without
    an installed capacity gets no rating. Without outage reports for a
    region, u is 0.

    Args:
        capacity (pd.DataFrame): Output of group_capacity.
        installed (pd.Series): Output of group_installed for GROUP_PRODUCTION_TYPES.
        outage_energy (pd.DataFrame | None): Output of weekly_outage_energy,
            or None if there are no outage reports at all.

    Returns:
        pd.DataFrame: Columns 'Region', 'Group', 'Season', 'GKFX', 'Installed',
            'k', 'Planned', 'Forced' (u of each kind) and 'Rating'.
    """
    gkfx = capacity.groupby(["Region", "Group"])["Capacity"].sum()
    outage_regions = (
        set(outage_energy.index.get_level_values("Region")) if outage_energy is not None else set()
    )

    ratings = []
    for (region, group), group_gkfx in gkfx.items():
        group_installed = installed.get((region, group), np.nan)
        if pd.isna(group_installed):
            warn(
                f"{region} {group} has {group_gkfx:.0f} MW of GKFX but no ENTSO-E installed "
                "capacity, so it keeps its base GKRATE."
            )
            continue

        k = min(1.0, group_installed / group_gkfx)
        weekly = pd.DataFrame(0.0, index=SEASONS, columns=["Planned", "Forced"])
        if outage_energy is not None and (region, group) in outage_energy.index.droplevel("Season"):
            weekly = outage_energy.loc[(region, group)].reindex(SEASONS, fill_value=0.0)
        if group_installed > 0:
            weekly = weekly / (group_installed * 168)
        rating = (k * (1 - weekly.sum(axis=1))).clip(0, 1)
        ratings.append(
            pd.DataFrame(
                {
                    "Region": region,
                    "Group": group,
                    "Season": SEASONS,
                    "GKFX": group_gkfx,
                    "Installed": group_installed,
                    "k": k,
                    "Planned": weekly["Planned"].to_numpy(),
                    "Forced": weekly["Forced"].to_numpy(),
                    "Rating": rating.to_numpy(),
                }
            )
        )

    rated_regions = {frame["Region"].iloc[0] for frame in ratings}
    for region in sorted(rated_regions - outage_regions):
        warn(
            f"{region} has no ENTSO-E outage reports, so its thermal ratings only "
            "scale GKFX to the installed capacity."
        )

    columns = ["Region", "Group", "Season", "GKFX", "Installed", "k", "Planned", "Forced", "Rating"]
    return pd.concat(ratings, ignore_index=True) if ratings else pd.DataFrame(columns=columns)


def capacity_check(
    capacity: pd.DataFrame,
    installed: pd.DataFrame,
    observed: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Balmorel GKFX against ENTSO-E's installed capacity and observed output, per region and group.

    The observed maximum and 99th percentile are a check only, never an input.

    Args:
        capacity (pd.DataFrame): Output of group_capacity with check_only=True.
        installed (pd.DataFrame): Output of load_installed_capacity.
        observed (dict[str, pd.DataFrame]): Hourly ENTSO-E output (MW) per
            canonical region, one column per production type.

    Returns:
        pd.DataFrame: Columns 'Region', 'Group', 'GKFX', 'Installed', 'Ratio'
            (installed / GKFX), 'ObservedMax' and 'ObservedP99' (MW).
    """
    groups = {
        **GROUP_PRODUCTION_TYPES,
        **{group: production_types for group, (_, production_types) in CHECK_ONLY_GROUPS.items()},
    }
    table = capacity.groupby(["Region", "Group"])["Capacity"].sum().rename("GKFX").to_frame()
    table = table.join(group_installed(installed, groups).rename("Installed"), how="outer")

    observed_max, observed_p99 = {}, {}
    for region, generation in observed.items():
        for group, production_types in groups.items():
            output = generation.reindex(columns=list(production_types)).sum(axis=1, min_count=1)
            if output.notna().any():
                observed_max[(region, group)] = output.max()
                observed_p99[(region, group)] = output.quantile(0.99)
    table["ObservedMax"] = pd.Series(observed_max)
    table["ObservedP99"] = pd.Series(observed_p99)
    table["Ratio"] = table["Installed"] / table["GKFX"]

    return table.reset_index()[
        ["Region", "Group", "GKFX", "Installed", "Ratio", "ObservedMax", "ObservedP99"]
    ]


# ------------------------------- #
#           4. Output             #
# ------------------------------- #


def write_thermal_gkrate_override(
    ratings: pd.DataFrame, capacity: pd.DataFrame, scenario_data_path: str | Path
) -> IncFile:
    """Write GKRATE_THERMAL_ENTSOE.inc with the weekly thermal ratings.

    Every technology of a group in an area gets its region's rating of the group.

    Args:
        ratings (pd.DataFrame): Output of thermal_ratings.
        capacity (pd.DataFrame): Output of group_capacity.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    rated = capacity.merge(ratings[["Region", "Group", "Season", "Rating"]], on=["Region", "Group"])
    lines = [
        f"GKRATE('{row.Area}','{row.Technology}','{row.Season}')={format_rating(row.Rating)};\n"
        for row in rated.sort_values(["Area", "Technology", "Season"]).itertuples()
    ]

    inc_file = IncFile(
        prefix=(
            "* Thermal availability per week: ENTSO-E installed capacity / GKFX (at most 1),\n"
            "* less the share reported out of service (see CONTEXT.md) - generated, do not hand-edit\n"
        ),
        body="".join(lines),
        suffix="",
        name="GKRATE_THERMAL_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def check_thermal_gkrate_include(gkrate_inc_path: str | Path) -> None:
    """Warn if the scenario's GKRATE.inc doesn't include GKRATE_THERMAL_ENTSOE.inc.

    Args:
        gkrate_inc_path (str | Path): Path to the scenario's GKRATE.inc.
    """
    gkrate_inc_path = Path(gkrate_inc_path)
    if not gkrate_inc_path.exists() or "GKRATE_THERMAL_ENTSOE.inc" not in gkrate_inc_path.read_text():
        warn(
            f"{gkrate_inc_path} doesn't include GKRATE_THERMAL_ENTSOE.inc, so the thermal "
            f"availability has no effect. Add, after the base ratings:\n{GKRATE_THERMAL_INCLUDE}"
        )


def load_scenario_input(
    balmorel_model_folder: str | Path,
    scenario: str,
    gams_system_directory: str | None,
    reload_input: bool,
    ignore: tuple[str, ...] = (),
) -> tuple[Balmorel, dict[float, str]]:
    """Load a scenario's input data, warning if the cached GDX is stale, and its acronym names.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario.
        gams_system_directory (str | None): GAMS system directory.
        reload_input (bool): Run ReadData again instead of reusing the cached input GDX.
        ignore (tuple[str, ...], optional): Data files the stale-cache check
            ignores, e.g. the override the caller writes. Defaults to ().

    Returns:
        tuple[Balmorel, dict[float, str]]: The model with the input data
            loaded, and the output of acronym_names.
    """
    model = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    input_gdx = Path(balmorel_model_folder) / scenario / "model" / f"{scenario}_input_data.gdx"
    if input_gdx.exists() and not reload_input:
        print(f"Reading the input data from the cached {input_gdx}")
        check_input_cache(input_gdx, Path(balmorel_model_folder) / scenario / "data", ignore=ignore)
    else:
        print(f"Running ReadData for {scenario} into {input_gdx}, this may take a while")
    model.load_incfiles(scenario, overwrite=reload_input)

    return model, acronym_names(input_gdx, gams_system_directory)


def generate_thermal_availability(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    observed: dict[str, pd.DataFrame],
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> IncFile | None:
    """Write GKRATE_THERMAL_ENTSOE.inc and backcastoutput/thermal_capacity.csv for a scenario.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the override for.
        year (int): The Backcast Year.
        entsoe_data_path (str | Path): Folder with the installed capacity and
            outage csv's (from `download`).
        observed (dict[str, pd.DataFrame]): Hourly ENTSO-E output per
            canonical region and production type, for the capacity check.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Returns:
        IncFile | None: The saved IncFile instance, or None without installed capacity.
    """
    installed = load_installed_capacity(entsoe_data_path, year)
    unavailability = load_unavailability(entsoe_data_path, year)
    download = f"python -m pybalmorel.backcasting download {entsoe_data_path} {year}"
    if unavailability.empty:
        warn(
            f"No ENTSO-E outage reports for {year} in {entsoe_data_path}, so the ratings only scale "
            f"GKFX to the installed capacity. Run `{download} --query unavailability_of_generation_units`"
        )

    model, names = load_scenario_input(
        balmorel_model_folder, scenario, gams_system_directory, reload_input,
        ignore=("GKRATE_THERMAL_ENTSOE.inc",),
    )
    capacity = group_capacity(
        model.get_input("GKFX"),
        model.get_input("GDATA"),
        model.get_input("RRRAAA"),
        names,
        year,
        check_only=True,
    )

    output_path = Path(balmorel_model_folder) / scenario / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    capacity_check(capacity, installed, observed).to_csv(output_path / "thermal_capacity.csv", index=False)
    print(f"Wrote the capacity check to {output_path / 'thermal_capacity.csv'}")

    if installed.empty:
        warn(
            f"No ENTSO-E installed capacity for {year} in {entsoe_data_path}, so nothing is written. "
            f"Run `{download} --query installed_generation_capacity`"
        )
        return None

    capacity = capacity[capacity["Group"].isin(GROUP_FUELS)]
    ratings = thermal_ratings(
        capacity,
        group_installed(installed, GROUP_PRODUCTION_TYPES),
        weekly_outage_energy(latest_outages(unavailability), year) if not unavailability.empty else None,
    )
    ratings.to_csv(output_path / "thermal_availability.csv", index=False)
    summary = ratings.groupby(["Region", "Group"]).agg(
        GKFX=("GKFX", "first"), k=("k", "first"), Planned=("Planned", "mean"),
        Forced=("Forced", "mean"), Rating=("Rating", "mean"),
    )
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print("Mean weekly ratings (Planned and Forced are mean weekly shares of installed capacity):")
        print(summary.round(3))

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    check_thermal_gkrate_include(scenario_data_path / "GKRATE.inc")

    return write_thermal_gkrate_override(ratings, capacity, scenario_data_path)

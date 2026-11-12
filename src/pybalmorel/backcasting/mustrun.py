"""
Must-run Floor

Turn ENTSO-E's observed generation and day-ahead prices into the data of
Balmorel's MUSTRUN addon: per canonical region, fuel group and Backcast
Calendar week, the lowest hourly output the group kept in a week where it
would have paid to stop (see CONTEXT.md). Writes MUSTRUN_ZONE.inc,
MUSTRUN_ZONE_RRR.inc, MUSTRUN_GROUP.inc, MUSTRUN_GROUP_FFF.inc and, last,
MUSTRUN_FLOOR.inc, whose existence switches the addon on.

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

from ..classes import IncFile
from .calendar import SEASONS, backcast_calendar
from .flows import canonical_region
from .thermal import GROUP_FUELS, GROUP_PRODUCTION_TYPES, group_capacity, load_scenario_input

# Day-ahead price (nominal €/MWh) at or below which a group running is must-run
PRICE_THRESHOLD = 40.0

# Hours at or below the threshold a week needs to show must-run
MIN_HOURS = 4

# Groups paid regardless of the price (feed-in tariffs, gate fees), floored every week
EVERY_WEEK_GROUPS = ("BIOMASS", "WASTE")

# Floors below this (MW) are dropped
MIN_FLOOR = 1.0

# Generated files in the order they are written; MUSTRUN_FLOOR switches the addon on, so it is last
MUSTRUN_FILES = (
    "MUSTRUN_ZONE",
    "MUSTRUN_ZONE_RRR",
    "MUSTRUN_GROUP",
    "MUSTRUN_GROUP_FFF",
    "MUSTRUN_FLOOR",
)

GENERATED_HEADER = (
    "* Must-run floor from ENTSO-E output in low-price weeks (see CONTEXT.md)"
    " - generated, do not hand-edit\n"
)

# ------------------------------- #
#        1. Observed data         #
# ------------------------------- #


def group_output(generation: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Hourly observed output per canonical region and fuel group.

    Args:
        generation (dict[str, pd.DataFrame]): Hourly ENTSO-E output (MW) per
            canonical region, one column per production type, with the
            zones of a region already summed.

    Returns:
        pd.DataFrame: Index UTC hour, columns (Region, Group), MW. A group
            none of whose production types a region reports is left out.
    """
    output = {}
    for region, df in generation.items():
        for group, production_types in GROUP_PRODUCTION_TYPES.items():
            series = df.reindex(columns=list(production_types)).sum(axis=1, min_count=1)
            if series.notna().any():
                output[(region, group)] = series

    if not output:
        return pd.DataFrame(columns=pd.MultiIndex.from_tuples([], names=["Region", "Group"]))
    return pd.DataFrame(output).rename_axis(columns=["Region", "Group"])


def region_prices(prices: pd.DataFrame, load: pd.DataFrame) -> pd.DataFrame:
    """Hourly day-ahead price per canonical region, weighted by the load of its zones.

    An hour without load for any priced zone of the region takes the plain mean.

    Args:
        prices (pd.DataFrame): Hourly price (€/MWh) indexed by UTC hour, one column per zone.
        load (pd.DataFrame): Hourly load (MW) indexed by UTC hour, one column per zone.

    Returns:
        pd.DataFrame: Index UTC hour, one column per canonical region.
    """
    zones = pd.Series(prices.columns, index=prices.columns).map(canonical_region)
    regional = {}
    for region, region_zones in zones.groupby(zones):
        price = prices[region_zones.index]
        weight = load.reindex(index=price.index, columns=region_zones.index)
        weight = weight.where(price.notna() & weight.notna())
        weighted = (price * weight).sum(axis=1) / weight.sum(axis=1)
        regional[region] = weighted.where(weight.sum(axis=1) > 0, price.mean(axis=1))

    return pd.DataFrame(regional, index=prices.index)


def must_run_floors(
    output: pd.DataFrame,
    prices: pd.DataFrame,
    year: int,
    price_threshold: float = PRICE_THRESHOLD,
    min_hours: int = MIN_HOURS,
    every_week: tuple[str, ...] = EVERY_WEEK_GROUPS,
) -> pd.DataFrame:
    """The observed must-run floor per canonical region, fuel group and Backcast Calendar week.

    The floor is the week's lowest hourly output over all its hours, for
    every-week groups and for weeks with at least `min_hours` hours priced at
    or below `price_threshold`. A week with less than half its hours of
    output data gets no floor, nor does a floor below MIN_FLOOR.

    Args:
        output (pd.DataFrame): Output of group_output.
        prices (pd.DataFrame): Output of region_prices.
        year (int): The Backcast Year.
        price_threshold (float, optional): Nominal €/MWh. Defaults to PRICE_THRESHOLD.
        min_hours (int, optional): Low-price hours a week needs. Defaults to MIN_HOURS.
        every_week (tuple[str, ...], optional): Groups floored every week.
            Defaults to EVERY_WEEK_GROUPS.

    Returns:
        pd.DataFrame: Columns 'Region', 'Group', 'Season', 'Floor' (MW, NaN
            without one), 'LowPriceHours' and 'ObservedTWh', one row per
            region, group and week with output data.
    """
    columns = ["Region", "Group", "Season", "Floor", "LowPriceHours", "ObservedTWh"]
    calendar = backcast_calendar(year).set_index("Timestamp")["Season"]
    output = output.reindex(calendar.index)
    low_price = (
        prices.reindex(index=calendar.index).le(price_threshold).groupby(calendar).sum()
    )

    weekly = output.groupby(calendar)
    lowest, hours, energy = weekly.min(), weekly.count(), weekly.sum(min_count=1) / 1e6
    floors = []
    for region, group in output.columns:
        n_low = (
            low_price[region] if region in low_price.columns else pd.Series(0, index=SEASONS)
        ).reindex(SEASONS, fill_value=0)
        qualifies = (n_low >= min_hours) | (group in every_week)
        has_data = hours[(region, group)] >= 168 / 2
        floor = lowest[(region, group)].where(qualifies & has_data)
        floor = floor.where(floor >= MIN_FLOOR)
        floors.append(
            pd.DataFrame(
                {
                    "Region": region,
                    "Group": group,
                    "Season": SEASONS,
                    "Floor": floor.reindex(SEASONS).to_numpy(),
                    "LowPriceHours": n_low.to_numpy(),
                    "ObservedTWh": energy[(region, group)].reindex(SEASONS).to_numpy(),
                }
            )
        )

    floors = pd.concat(floors, ignore_index=True) if floors else pd.DataFrame(columns=columns)
    return floors.dropna(subset=["ObservedTWh"]).reset_index(drop=True)


# ------------------------------- #
#     2. Check against Balmorel   #
# ------------------------------- #


def available_capacity(capacity: pd.DataFrame, gkrate: pd.DataFrame) -> pd.DataFrame:
    """Available capacity K = sum of GKFX x GKRATE per canonical region, group and week.

    Where GKRATE is not set, the rating is 1. A stored 0 is GAMS eps, since
    a GDX file doesn't store zeros, so it counts as 0.

    Args:
        capacity (pd.DataFrame): Output of thermal.group_capacity.
        gkrate (pd.DataFrame): GKRATE from get_input, ending in (AAA, G, SSS, Value).

    Returns:
        pd.DataFrame: Columns 'Region', 'Group', 'Season' and 'K' (MW).
    """
    gkrate = gkrate.iloc[:, -4:].set_axis(["Area", "Technology", "Season", "Rating"], axis=1)
    gkrate = gkrate[gkrate["Season"].isin(SEASONS)]
    weeks = capacity.merge(pd.DataFrame({"Season": SEASONS}), how="cross")
    weeks = weeks.merge(gkrate, on=["Area", "Technology", "Season"], how="left")
    weeks["K"] = weeks["Capacity"] * weeks["Rating"].astype(float).fillna(1.0)

    return weeks.groupby(["Region", "Group", "Season"], as_index=False)["K"].sum()


def cap_floors(
    floors: pd.DataFrame,
    capacity: pd.DataFrame,
    gkrate: pd.DataFrame,
    balmorel_regions: list[str],
) -> pd.DataFrame:
    """Cap the floors at Balmorel's available capacity, and drop those Balmorel can't meet at all.

    Floors of a canonical region without a Balmorel region are dropped. A
    group without GKFX in a region gets no floor and a warning; a floor
    above K is capped and warns.

    Args:
        floors (pd.DataFrame): Output of must_run_floors.
        capacity (pd.DataFrame): Output of thermal.group_capacity.
        gkrate (pd.DataFrame): GKRATE from get_input, ending in (AAA, G, SSS, Value).
        balmorel_regions (list[str]): The scenario's RRR.

    Returns:
        pd.DataFrame: `floors` of the modelled regions, with 'K' (MW) and 'Capped' added.
    """
    modelled = {canonical_region(region) for region in balmorel_regions}
    skipped = sorted(set(floors["Region"]) - modelled)
    if skipped:
        print(f"No Balmorel region for {', '.join(skipped)}, so they get no must-run floor")
    floors = floors[floors["Region"].isin(modelled)].merge(
        available_capacity(capacity, gkrate), on=["Region", "Group", "Season"], how="left"
    )
    floors["K"] = floors["K"].fillna(0.0)

    has_floor = floors["Floor"].notna()
    no_capacity = has_floor & (floors["K"] <= 0)
    for (region, group), weeks in floors[no_capacity].groupby(["Region", "Group"]):
        warn(
            f"{region} {group} has a must-run floor in {len(weeks)} weeks "
            f"({weeks['ObservedTWh'].sum():.1f} TWh observed in them) but no available "
            "capacity in Balmorel, so it gets no floor there."
        )
    floors.loc[no_capacity, "Floor"] = np.nan

    capped = floors["Floor"] > floors["K"]
    for (region, group), weeks in floors[capped].groupby(["Region", "Group"]):
        warn(
            f"{region} {group}'s must-run floor exceeds Balmorel's available capacity in "
            f"{len(weeks)} weeks (by up to {(weeks['Floor'] - weeks['K']).max():.0f} MW), so it is "
            "capped there. Run thermal-availability first so the cap uses its ratings."
        )
    floors["Capped"] = capped
    floors["Floor"] = floors["Floor"].where(~capped, floors["K"])

    return floors


# ------------------------------- #
#           3. Output             #
# ------------------------------- #


def _set_file(declaration: str, members: list[str]) -> str:
    return f"{declaration}\n/\n" + "".join(f"{member}\n" for member in members) + "/;\n"


def write_must_run_files(
    floors: pd.DataFrame,
    balmorel_regions: list[str],
    fuels: list[str],
    scenario_data_path: str | Path,
) -> list[IncFile]:
    """Write the five MUSTRUN files, MUSTRUN_FLOOR.inc last, since it switches the addon on.

    Args:
        floors (pd.DataFrame): Output of cap_floors; rows without a floor are ignored.
        balmorel_regions (list[str]): The scenario's RRR, to list the regions of each zone.
        fuels (list[str]): The scenario's FFF; group fuels outside it are left out.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        list[IncFile]: The saved IncFile instances, in the order written.
    """
    floors = floors.dropna(subset=["Floor"]).sort_values(["Region", "Group", "Season"])
    zones = sorted(floors["Region"].unique())
    groups = [group for group in GROUP_FUELS if group in set(floors["Group"])]
    zone_regions = {
        zone: sorted(region for region in balmorel_regions if canonical_region(region) == zone)
        for zone in zones
    }
    group_fuels = {group: [fuel for fuel in GROUP_FUELS[group] if fuel in fuels] for group in groups}

    bodies = {
        "MUSTRUN_ZONE": _set_file(
            "SET MUSTRUN_ZONE 'Zones with a must-run floor (countries or bidding zones)'", zones
        ),
        "MUSTRUN_ZONE_RRR": _set_file(
            "SET MUSTRUN_ZONE_RRR(MUSTRUN_ZONE,RRR) 'Regions in each must-run zone'",
            [f"{zone}.({','.join(regions)})" for zone, regions in zone_regions.items()],
        ),
        "MUSTRUN_GROUP": _set_file("SET MUSTRUN_GROUP 'Fuel groups with a must-run floor'", groups),
        "MUSTRUN_GROUP_FFF": _set_file(
            "SET MUSTRUN_GROUP_FFF(MUSTRUN_GROUP,FFF) 'Fuels in each must-run fuel group'",
            [f"{group}.({','.join(group_fuels[group])})" for group in groups if group_fuels[group]],
        ),
        "MUSTRUN_FLOOR": _set_file(
            "PARAMETER MUSTRUN_FLOOR(MUSTRUN_ZONE,MUSTRUN_GROUP,SSS) "
            "'Minimum electricity output of a fuel group in a zone, per season (MW)'",
            [f"{row.Region}.{row.Group}.{row.Season} {row.Floor:.1f}" for row in floors.itertuples()],
        ),
    }

    inc_files = []
    for name in MUSTRUN_FILES:
        inc_file = IncFile(
            prefix=GENERATED_HEADER,
            body=bodies[name],
            suffix="",
            name=name,
            path=str(scenario_data_path),
        )
        inc_file.save()
        inc_files.append(inc_file)

    return inc_files


def floor_summary(floors: pd.DataFrame) -> pd.DataFrame:
    """Per zone and group: weeks floored, floor min/median/max (GW), floored and observed TWh.

    Args:
        floors (pd.DataFrame): Output of must_run_floors or cap_floors.

    Returns:
        pd.DataFrame: Index (Region, Group), sorted by floored TWh, largest first.
    """
    floored = floors.dropna(subset=["Floor"])
    observed = floors.groupby(["Region", "Group"])["ObservedTWh"].sum()
    summary = floored.groupby(["Region", "Group"]).agg(
        Weeks=("Floor", "size"),
        MinGW=("Floor", lambda floor: floor.min() / 1e3),
        MedianGW=("Floor", lambda floor: floor.median() / 1e3),
        MaxGW=("Floor", lambda floor: floor.max() / 1e3),
        FlooredTWh=("Floor", lambda floor: floor.sum() * 168 / 1e6),
    )
    summary["ObservedTWh"] = observed.reindex(summary.index)

    return summary.sort_values("FlooredTWh", ascending=False)


def generate_must_run_floor(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    generation: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    load: pd.DataFrame,
    price_threshold: float = PRICE_THRESHOLD,
    min_hours: int = MIN_HOURS,
    every_week: tuple[str, ...] = EVERY_WEEK_GROUPS,
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> list[IncFile]:
    """Write the MUSTRUN files and backcastoutput/must_run_floor.csv for a scenario.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the floor for.
        year (int): The Backcast Year.
        generation (dict[str, pd.DataFrame]): Hourly ENTSO-E output per
            canonical region and production type.
        prices (pd.DataFrame): Hourly day-ahead price per zone.
        load (pd.DataFrame): Hourly load per zone, to weight the prices of a region's zones.
        price_threshold (float, optional): Nominal €/MWh. Defaults to PRICE_THRESHOLD.
        min_hours (int, optional): Low-price hours a week needs. Defaults to MIN_HOURS.
        every_week (tuple[str, ...], optional): Groups floored every week.
            Defaults to EVERY_WEEK_GROUPS.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Raises:
        ValueError: If an every-week group isn't a fuel group.

    Returns:
        list[IncFile]: The saved IncFile instances; empty if no floor qualifies.
    """
    unknown = set(every_week) - GROUP_FUELS.keys()
    if unknown:
        raise ValueError(
            f"--every-week {', '.join(sorted(unknown))} is not a fuel group. "
            f"Choose from {', '.join(GROUP_FUELS)}."
        )

    floors = must_run_floors(
        group_output(generation),
        region_prices(prices, load),
        year,
        price_threshold=price_threshold,
        min_hours=min_hours,
        every_week=tuple(every_week),
    )

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    if not (scenario_data_path / "GKRATE_THERMAL_ENTSOE.inc").exists():
        warn(
            f"{scenario_data_path} has no GKRATE_THERMAL_ENTSOE.inc, so the cap on the floor uses "
            "the base ratings. Run thermal-availability first."
        )
    model, names = load_scenario_input(
        balmorel_model_folder,
        scenario,
        gams_system_directory,
        reload_input,
        ignore=tuple(f"{name}.inc" for name in MUSTRUN_FILES),
    )
    capacity = group_capacity(
        model.get_input("GKFX"), model.get_input("GDATA"), model.get_input("RRRAAA"), names, year
    )
    balmorel_regions = model.get_input("RRRAAA").iloc[:, -2].unique().tolist()
    floors = cap_floors(floors, capacity, model.get_input("GKRATE"), balmorel_regions)

    output_path = Path(balmorel_model_folder) / scenario / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    floors.to_csv(output_path / "must_run_floor.csv", index=False)
    print(f"Wrote the floors per week to {output_path / 'must_run_floor.csv'}")

    if floors["Floor"].isna().all():
        print(
            f"No must-run floor qualifies at a price threshold of {price_threshold} €/MWh "
            f"and {min_hours} hours, so no MUSTRUN files are written."
        )
        if (scenario_data_path / "MUSTRUN_FLOOR.inc").exists():
            warn(
                f"{scenario_data_path / 'MUSTRUN_FLOOR.inc'} from an earlier run still switches "
                "the floor on. Delete it to switch it off."
            )
        return []

    with pd.option_context("display.max_rows", None, "display.width", 200):
        print("Must-run floor per zone and fuel group:")
        print(floor_summary(floors).round(2))

    fuels = model.get_input("FFF").iloc[:, -1].tolist()
    return write_must_run_files(floors, balmorel_regions, fuels, scenario_data_path)

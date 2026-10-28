"""
Validation through Backcasting

Download data from ENTSO-E and compare to Balmorel simulation of similar year

Created on 24.06.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
import pandas as pd
import numpy as np
from pathlib import Path
import click
from decouple import config
from .. import MainResults
from ..entsoe import bidding_zone_translation, entsoe_code_to_region
from .calendar import backcast_hours, from_backcast_grid
from .flows import (
    OBSERVED_FLOW_PERCENTILE,
    align_flows,
    canonical_region,
    flow_statistics,
    format_balmorel_flows,
    load_entsoe_flows,
    observed_flow_limits,
    plot_flow_duration_curves,
)
from .pricelevel import PRICE_YEAR, to_price_year
from warnings import warn

balmorel_to_category = {
    # Wind
    "WIND-ON - WIND": "Wind",
    "WIND-OFF - WIND": "Wind",
    # Solar
    "SOLAR-PV - SUN": "Solar",
    "SOLAR-HEATING - SUN": "Solar",
    # Hydro
    "HYDRO-RUN-OF-RIVER - WATER": "Hydro",
    "HYDRO-RESERVOIRS - WATER": "Hydro",
    # Nuclear
    "CONDENSING - NUCLEAR": "Nuclear",
    # Biomass & Bioenergy
    "CONDENSING - STRAW": "Biomass & Bioenergy",
    "CONDENSING - WOODPELLETS": "Biomass & Bioenergy",
    "CHP-EXTRACTION - STRAW": "Biomass & Bioenergy",
    "CHP-EXTRACTION - WOOD": "Biomass & Bioenergy",
    "CHP-EXTRACTION - BIOGAS": "Biomass & Bioenergy",
    "CONDENSING - BIOGAS": "Biomass & Bioenergy",
    "CONDENSING - WOOD": "Biomass & Bioenergy",
    "BOILERS - BIOMETHANE": "Biomass & Bioenergy",
    "BOILERS - WOODPELLETS": "Biomass & Bioenergy",
    "BOILERS - WOODCHIPS": "Biomass & Bioenergy",
    "BOILERS - WOODWASTE": "Biomass & Bioenergy",
    "BOILERS - WOOD": "Biomass & Bioenergy",
    "BOILERS - STRAW": "Biomass & Bioenergy",
    "BOILERS - BIOGAS": "Biomass & Bioenergy",
    "BOILERS - BIOOIL": "Biomass & Bioenergy",
    "CONDENSING - BIOMETHANE": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - BIOMETHANE": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - WOODCHIPS": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - WOODPELLETS": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - WOODWASTE": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - BIOGAS": "Biomass & Bioenergy",
    "CHP-BACK-PRESSURE - STRAW": "Biomass & Bioenergy",
    "CHP-EXTRACTION - BIOMETHANE": "Biomass & Bioenergy",
    "CHP-EXTRACTION - WOODPELLETS": "Biomass & Bioenergy",
    "CHP-EXTRACTION - BIOOIL": "Biomass & Bioenergy",
    # Fossil Gas
    "BOILERS - NATGAS": "Fossil Gas",
    "CONDENSING - NATGAS": "Fossil Gas",
    "CHP-BACK-PRESSURE - NATGAS": "Fossil Gas",
    "CHP-EXTRACTION - NATGAS": "Fossil Gas",
    "CHP-EXTRACTION - RETORTGAS": "Fossil Gas",
    "CONDENSING - RETORTGAS": "Fossil Gas",
    "STEAMREFORMING - NATGAS": "Fossil Gas",
    "BOILERS - OTHERGAS": "Fossil Gas",
    "CHP-BACK-PRESSURE - OTHERGAS": "Fossil Gas",
    "CHP-EXTRACTION - OTHERGAS": "Fossil Gas",
    # Fossil Solid
    "CHP-BACK-PRESSURE - LIGNITE": "Fossil Solid",
    "CHP-EXTRACTION - LIGNITE": "Fossil Solid",
    "CONDENSING - COAL": "Fossil Solid",
    "CONDENSING - LIGNITE": "Fossil Solid",
    "CHP-EXTRACTION - SHALE": "Fossil Solid",
    "CONDENSING - SHALE": "Fossil Solid",
    "BOILERS - COAL": "Fossil Solid",
    "BOILERS - PEAT": "Fossil Solid",
    "CHP-BACK-PRESSURE - COAL": "Fossil Solid",
    "CHP-BACK-PRESSURE - PEAT": "Fossil Solid",
    "CHP-EXTRACTION - COAL": "Fossil Solid",
    "CHP-EXTRACTION - PEAT": "Fossil Solid",
    # Fossil Liquid & Other Fossil
    "BOILERS - LIGHTOIL": "Fossil Liquid & Other Fossil",
    "CONDENSING - FUELOIL": "Fossil Liquid & Other Fossil",
    "CONDENSING - LIGHTOIL": "Fossil Liquid & Other Fossil",
    "BOILERS - FUELOIL": "Fossil Liquid & Other Fossil",
    "CHP-BACK-PRESSURE - LIGHTOIL": "Fossil Liquid & Other Fossil",
    "CHP-BACK-PRESSURE - FUELOIL": "Fossil Liquid & Other Fossil",
    "CHP-EXTRACTION - FUELOIL": "Fossil Liquid & Other Fossil",
    # Waste & Heat Recovery
    "BOILERS - MUNIWASTE": "Waste & Heat Recovery",
    "BOILERS - WASTEHEAT": "Waste & Heat Recovery",
    "CONDENSING - MUNIWASTE": "Waste & Heat Recovery",
    "CONDENSING - WASTEHEAT": "Waste & Heat Recovery",
    "CHP-BACK-PRESSURE - MUNIWASTE": "Waste & Heat Recovery",
    "CHP-EXTRACTION - MUNIWASTE": "Waste & Heat Recovery",
    # Storage
    "INTRASEASONAL-ELECT-STORAGE - ELECTRIC": "Storage",
    # Other
    "INTRASEASONAL-HEAT-STORAGE - HEAT": "Other",
    "INTERSEASONAL-HEAT-STORAGE - HEAT": "Other",
    "ELECT-TO-HEAT - ELECTRIC": "Other",
    "CHP-BACK-PRESSURE - HEAT": "Other",
    # Backup: covers demand Balmorel can't otherwise meet, no ENTSO-E counterpart
    "CONDENSING - DUMMY": "Backup",
}

entsoe_to_category = {
    # Wind
    "Wind Onshore": "Wind",
    "Wind Offshore": "Wind",
    # Solar
    "Solar": "Solar",
    # Hydro
    "Hydro Run-of-river and pondage": "Hydro",
    # Spelling of older entsoe-py versions, still in files fetched with them
    "Hydro Run-of-river and poundage": "Hydro",
    "Hydro Water Reservoir": "Hydro",
    # Nuclear
    "Nuclear": "Nuclear",
    # Biomass & Bioenergy
    "Biomass": "Biomass & Bioenergy",
    # Fossil Gas
    "Fossil Gas": "Fossil Gas",
    "Fossil Coal-derived gas": "Fossil Gas",
    # Fossil Solid
    "Fossil Brown coal/Lignite": "Fossil Solid",
    "Fossil Hard coal": "Fossil Solid",
    "Fossil Peat": "Fossil Solid",
    # Oil shale is burned as a solid fuel, as Balmorel's SHALE technologies are
    "Fossil Oil shale": "Fossil Solid",
    # Fossil Liquid & Other Fossil
    "Fossil Oil": "Fossil Liquid & Other Fossil",
    # Waste & Heat Recovery
    "Waste": "Waste & Heat Recovery",
    # Storage
    # Pumped storage is storage on the Balmorel side too (INTRASEASONAL-ELECT-STORAGE),
    # so Hydro means natural-inflow hydro on both sides
    "Hydro Pumped Storage": "Storage",
    "Energy storage": "Storage",
    # Other renewable
    "Geothermal": "Other renewable",
    "Marine": "Other renewable",
    "Other renewable": "Other renewable",
    # Other: mostly gas CHP of unreported fuel (NL, IT)
    "Other": "Other",
}

# ENTSO-E queries the download command fetches
entsoe_queries = ["load", "day_ahead_prices", "generation", "crossborder_flows"]

# ENTSO-E queries for thermal-availability, downloaded only on request
entsoe_capacity_queries = ["installed_generation_capacity", "unavailability_of_generation_units"]

# Category of technologies missing from the mappings, with format --allow-unmapped
UNMAPPED_CATEGORY = "Unmapped"

colors = {
    "Wind": "#4ECDC4",
    "Solar": "#FFE66D",
    "Hydro": "#0077B6",
    "Nuclear": "#FF6B6B",
    "Biomass & Bioenergy": "#6B8E23",
    "Fossil Gas": "#8B4513",
    "Fossil Solid": "#555555",
    "Fossil Liquid & Other Fossil": "#333333",
    "Waste & Heat Recovery": "#9B59B6",
    "Storage": "#F39C12",
    "Other renewable": "#A3D977",
    "Other": "#CCCCCC",
    "Backup": "#C0392B",
    UNMAPPED_CATEGORY: "#FF00FF",
}

# Balmorel load categories that are storage charging, which ENTSO-E's
# Actual Total Load excludes
STORAGE_CHARGING_CATEGORIES = ("ENDO_INTRASTO",)

# Line colours of the price plots, checked for colour-blind separation
ENTSOE_COLOUR = "#2a78d6"
BALMOREL_COLOUR = "#eb6834"

# Order of the per-region panels of price-duration; other regions follow alphabetically
PRICE_DURATION_REGION_ORDER = [
    "DE", "FR", "NL", "BE", "AT", "CH", "PL", "CZ", "SK", "HU", "SI", "HR",
    "DK1", "DK2", "NO1", "NO2", "NO3", "NO4", "NO5", "SE1", "SE2", "SE3", "SE4", "FI",
    "EE", "LV", "LT", "ES", "PT", "IT", "GR", "IE", "BG", "RO", "RS", "MK", "AL", "ME",
]

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


class DataContainer:
    """Container for ENTSO-E data."""

    def __init__(self, data_items):
        super(DataContainer, self).__init__()
        for item in data_items:
            setattr(self, item, pd.DataFrame())


def format_entsoe_region_name(path, year, parameter):
    raw_region_name = path.name.removeprefix(f"{year}_").removesuffix(
        f"_{parameter}.csv"
    )
    return entsoe_code_to_region(raw_region_name)


def format_entsoe_data(df, resampling: str, filepath: Path, year: int, parameter: str):
    """Format ENTSO-E data"""

    if "generation" not in filepath.name:
        df.columns = ["Time", "Value"]
        aggregation = {"Value": "mean"}
    else:
        df.columns = ["Time"] + list(df.columns[1:])
        aggregation = {col: "mean" for col in df.columns[1:]}

        # Multi-columned data
        if any([type(val) is str for val in df.iloc[0, 1:]]):
            df = pd.read_csv(filepath, header=[0, 1])
            # Keep only 'Actual Aggregated', so pumping and other 'Actual Consumption'
            # is never counted as generation, even where 'Actual Aggregated' is empty
            temp = df.iloc[:, 1:]
            temp = temp.loc[:, temp.columns.get_level_values(1) == "Actual Aggregated"]
            temp.columns = temp.columns.get_level_values(0)
            temp["Time"] = df.iloc[:, 0]
            df = temp
            aggregation = {col: "mean" for col in df.columns[:-1]}

    # Get time and resample to hours
    df.Time = pd.to_datetime(df.Time, utc=True)
    df = (
        df.resample(
            resampling,
            on="Time",
        )
        .aggregate(aggregation)
        .reset_index()
    )

    region = format_entsoe_region_name(filepath, year, parameter)
    df["Region"] = region

    return df


def load_entsoe_data(entsoe_data_path: str, year: int, resampling: str = "h"):
    "Load the csvs for `year`"
    path = Path(entsoe_data_path)
    data_items = ["load", "day_ahead_prices", "generation"]
    data = DataContainer(data_items)

    for data_item in data_items:
        files = sorted(path.glob(f"{year}_*_{data_item}.csv"))
        if not files:
            warn(
                f"No ENTSO-E {data_item} files for {year} in {path}, so its comparison will be empty. "
                f"Run `python -m pybalmorel.backcasting download {path} {year} --query {data_item}`",
                Warning,
            )
        for item in files:
            # Load data for a specific region
            temp = format_entsoe_data(pd.read_csv(item), resampling, item, year, data_item)
            setattr(
                data,
                data_item,
                pd.concat((getattr(data, data_item), temp), ignore_index=True),
            )

    # Cross-border flows are loaded separately, see flows.load_entsoe_flows
    # and capacities and outages by thermal.py
    known_suffixes = tuple(
        f"_{data_item}.csv"
        for data_item in data_items + ["crossborder_flows"] + entsoe_capacity_queries
    ) + ("_nodata.txt",)
    for item in path.glob(f"{year}_*"):
        if not item.name.endswith(known_suffixes):
            warn(
                f"{item} was not loaded as it did not match naming pattern.",
                Warning,
            )

    return [getattr(data, data_item) for data_item in data_items]


def load_observed_nuclear(entsoe_data_path: str, year: int) -> dict[str, pd.Series]:
    """Hourly ENTSO-E nuclear output per canonical region, from the generation csv's.

    Files of several zones in one canonical region are summed hour by hour. A
    file without a 'Nuclear' column, or with only NaN or zeros in it, has no
    nuclear.

    Args:
        entsoe_data_path (str): Folder with the fetched generation csv's.
        year (int): The Backcast Year.

    Returns:
        dict[str, pd.Series]: Nuclear output (MW) indexed by UTC hour, per region.
    """
    nuclear = {}
    for item in sorted(Path(entsoe_data_path).glob(f"{year}_*_generation.csv")):
        df = format_entsoe_data(pd.read_csv(item, low_memory=False), "h", item, year, "generation")
        if "Nuclear" not in df.columns or not df["Nuclear"].fillna(0).gt(0).any():
            continue
        region = canonical_region(df["Region"].iloc[0])
        series = df.set_index("Time")["Nuclear"]
        nuclear[region] = (
            series
            if region not in nuclear
            else pd.concat([nuclear[region], series], axis=1).sum(axis=1, min_count=1)
        )

    return nuclear


def load_observed_generation(entsoe_data_path: str, year: int) -> dict[str, pd.DataFrame]:
    """Hourly ENTSO-E output per canonical region and production type, from the generation csv's.

    Files of several zones in one canonical region are summed hour by hour.

    Args:
        entsoe_data_path (str): Folder with the fetched generation csv's.
        year (int): The Backcast Year.

    Returns:
        dict[str, pd.DataFrame]: Output (MW) indexed by UTC hour, one column
            per production type, per region.
    """
    generation = {}
    for item in sorted(Path(entsoe_data_path).glob(f"{year}_*_generation.csv")):
        df = format_entsoe_data(pd.read_csv(item, low_memory=False), "h", item, year, "generation")
        region = canonical_region(df["Region"].iloc[0])
        df = df.drop(columns="Region").set_index("Time")
        generation[region] = (
            df
            if region not in generation
            else generation[region].add(df, fill_value=0)
        )

    return generation


def load_observed_prices(entsoe_data_path: str, year: int) -> pd.DataFrame:
    """Hourly ENTSO-E day-ahead price per bidding zone, from the day_ahead_prices csv's.

    Args:
        entsoe_data_path (str): Folder with the fetched day_ahead_prices csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Price (nominal €/MWh) indexed by UTC hour, one column per zone.
    """
    files = sorted(Path(entsoe_data_path).glob(f"{year}_*_day_ahead_prices.csv"))
    if not files:
        return pd.DataFrame()

    return pd.concat(
        [
            format_entsoe_data(pd.read_csv(item), "h", item, year, "day_ahead_prices")
            for item in files
        ]
    ).pivot_table(index="Time", columns="Region", values="Value")


def load_observed_load(entsoe_data_path: str, year: int) -> pd.DataFrame:
    """Hourly ENTSO-E actual load per bidding zone, from the load csv's.

    Args:
        entsoe_data_path (str): Folder with the fetched load csv's.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Load (MW) indexed by UTC hour, one column per zone.
    """
    files = sorted(Path(entsoe_data_path).glob(f"{year}_*_load.csv"))
    if not files:
        return pd.DataFrame()

    return pd.concat(
        [format_entsoe_data(pd.read_csv(item), "h", item, year, "load") for item in files]
    ).pivot_table(index="Time", columns="Region", values="Value")


def format_balmorel_df(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Sum Balmorel results per region (and technology) and map (S,T) onto UTC time.

    Args:
        df (pd.DataFrame): MainResults symbol with 'Region', 'Season', 'Time'
            and 'Value' columns, optionally 'Technology'.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Columns 'Time' (UTC timestamps), 'Region', optionally
            'Technology', and 'Value'.
    """
    group_columns = ["Region", "Technology"] if "Technology" in df.columns else ["Region"]
    df_out = df.groupby(group_columns + ["Season", "Time"], as_index=False)[
        "Value"
    ].sum()

    return from_backcast_grid(df_out, year)


def load_balmorel_data(
    scenario_name: str, scenario_folder_path: str, year: int, overwrite: bool
):
    "Load df from MainResults"

    path = Path(scenario_folder_path).joinpath("backcastoutput")
    path.mkdir(exist_ok=True)
    cached_files = [
        "balmorel_prices.csv",
        "balmorel_load.csv",
        "balmorel_generation.csv",
        "balmorel_flows.csv",
    ]
    if (
        not all(path.joinpath(file).exists() for file in cached_files)
    ) or overwrite:
        print(
            "Loading Balmorel timeseries results from .gdx file (may take a while - will be cached afterwards)"
        )
        results = MainResults(
            f"MainResults_{scenario_name}.gdx",
            paths=Path(scenario_folder_path).joinpath("model").absolute().__str__(),
            system_directory=config("GAMS_SYSTEM_DIR", None),
        )  # pyright: ignore
        load = results.get_result("EL_DEMAND_YCRST").query(f"Year == '{year}'")
        elprices = results.get_result("EL_PRICE_YCRST").query(f"Year == '{year}'")
        generation = results.get_result("PRO_YCRAGFST").query(
            f"Year == '{year}' and Commodity == 'ELECTRICITY'"
        )
        flows = results.get_result("X_FLOW_YCRST").query(f"Year == '{year}'")
        load.to_csv(path.joinpath("balmorel_load.csv"), index=False)
        elprices.to_csv(path.joinpath("balmorel_prices.csv"), index=False)
        generation.to_csv(path.joinpath("balmorel_generation.csv"), index=False)
        flows.to_csv(path.joinpath("balmorel_flows.csv"), index=False)
    else:
        print(
            "Loading cached Balmorel results (set overwrite=True to reload MainResults)"
        )
        load = pd.read_csv(path.joinpath("balmorel_load.csv"))
        elprices = pd.read_csv(path.joinpath("balmorel_prices.csv"))
        generation = pd.read_csv(path.joinpath("balmorel_generation.csv"))
        flows = pd.read_csv(path.joinpath("balmorel_flows.csv"))

    return load, elprices, generation, flows


def calculate_statistics(
    df: pd.DataFrame, timeslicing: int = 0, per_region: bool = False
):
    "Get std. dev, mean, max etc..."

    if timeslicing != 0:
        time = df.index.get_level_values(1).unique()
        idx = time[:timeslicing]
        df = df.loc[(slice(None), idx), :]

    if per_region:
        for region in df.index.get_level_values(0).unique():
            temp = df.loc[region]
            print(
                f"\nStatistics for {region}:\nStd. dev:\n{temp.std().round()}\nMean:\n{temp.mean().round()}\nMin:\n{temp.min().round()}\nMax:\n{temp.max().round()}"
            )
    else:
        print(
            f"\nStd. dev:\n{df.std().round()}\nMean:\n{df.mean().round()}\nMin:\n{df.min().round()}\nMax:\n{df.max().round()}"
        )


def aggregate_regions(df: pd.DataFrame, aggfunc: str, time_columns: list):
    "Aggregate DE4, IT-* etc"

    # Combine technology and fuel column for Balmorel
    if "Technology" in df.columns and "Fuel" in df.columns:
        df.Technology = df.Technology + " - " + df.Fuel

    # Prepare correct indices
    if "Technology" in df.columns:
        new_index = ["Region", "Technology"] + time_columns
    else:
        new_index = ["Region"] + time_columns

    for region in df.Region.unique():
        if region in bidding_zone_translation:
            df = (
                df.replace({"Region": {region: bidding_zone_translation[region]}})
                .pivot_table(
                    index=new_index,
                    values="Value",
                    aggfunc=aggfunc,
                )
                .reset_index()
            )
            print(f"Aggregating {region} to {bidding_zone_translation[region]}")

    return df


def map_technology_categories(
    df: pd.DataFrame, mapping: dict[str, str], source: str, allow_unmapped: bool = False
) -> pd.DataFrame:
    """Map 'Technology' onto the overarching categories and sum per region, category and hour.

    A technology missing from `mapping` is never dropped: it raises, or with
    `allow_unmapped` it is compared as UNMAPPED_CATEGORY.

    Args:
        df (pd.DataFrame): Hourly generation (MW) with columns 'Region',
            'Technology', 'Time' and 'Value'.
        mapping (dict[str, str]): Technology -> category, e.g. entsoe_to_category.
        source (str): 'Balmorel' or 'ENTSO-E', named in the error.
        allow_unmapped (bool, optional): Put unmapped technologies in
            UNMAPPED_CATEGORY instead of raising. Defaults to False.

    Raises:
        ValueError: If a technology is not in `mapping` and `allow_unmapped` is False.

    Returns:
        pd.DataFrame: Columns 'Region', 'Technology', 'Time' and 'Value'.
    """
    unmapped = set(df.Technology.unique()) - mapping.keys()
    if unmapped:
        energy = (
            df[df.Technology.isin(unmapped)].groupby("Technology")["Value"].sum() / 1e6
        ).sort_values(ascending=False)
        listing = ", ".join(f"'{technology}' ({twh:.2f} TWh)" for technology, twh in energy.items())
        message = f"{source} technologies without a category: {listing}."
        if not allow_unmapped:
            raise ValueError(
                f"{message} Add them to the category mapping in "
                "pybalmorel/backcasting/__main__.py, or run `format` with "
                f"--allow-unmapped to compare them as '{UNMAPPED_CATEGORY}'."
            )
        warn(f"{message} They are compared as '{UNMAPPED_CATEGORY}'.")

    df = df.assign(Technology=df.Technology.map(mapping).fillna(UNMAPPED_CATEGORY))
    return df.groupby(["Region", "Technology", "Time"], as_index=False).sum(numeric_only=True)


def balmorel_load_components(load: pd.DataFrame) -> pd.DataFrame:
    """Annual Balmorel load (TWh) per region and load category.

    Args:
        load (pd.DataFrame): EL_DEMAND_YCRST of the Backcast Year, with
            'Region', 'Category' and 'Value' (MW per hour).

    Returns:
        pd.DataFrame: Columns 'Region' (DE4-* as DE, IT-* as IT), 'Category',
            'BALMOREL' (TWh) and 'Excluded' (True for storage charging, which
            the comparison leaves out).
    """
    components = (
        load.assign(Region=load.Region.replace(bidding_zone_translation))
        .groupby(["Region", "Category"], as_index=False)["Value"]
        .sum()
        .rename(columns={"Value": "BALMOREL"})
    )
    components["BALMOREL"] = components["BALMOREL"] / 1e6
    components["Excluded"] = components["Category"].isin(STORAGE_CHARGING_CATEGORIES)

    return components


def balmorel_prices_in_year(prices: pd.DataFrame, year: int) -> pd.DataFrame:
    """Convert Balmorel's prices from the Price Year (€2016) to nominal euros of `year`.

    Args:
        prices (pd.DataFrame): Balmorel prices with a 'Value' column.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: A copy of `prices` with 'Value' in nominal euros of `year`.
    """
    return prices.assign(
        Value=to_price_year(prices["Value"], year=PRICE_YEAR, price_year=year)
    )


def get_and_format_balmorel(
    balmorel_scenario,
    balmorel_scenario_path,
    year,
    elpriceaggfunc,
    overwrite,
    allow_unmapped: bool = False,
):
    balmorel_load, balmorel_elprices, balmorel_generation, balmorel_flows = (
        load_balmorel_data(balmorel_scenario, balmorel_scenario_path, year, overwrite)
    )
    balmorel_flows = format_balmorel_flows(balmorel_flows, year)

    # ENTSO-E's Actual Total Load excludes storage charging, so leave it out here too
    balmorel_load_components_twh = balmorel_load_components(balmorel_load)
    balmorel_load = balmorel_load[
        ~balmorel_load.Category.isin(STORAGE_CHARGING_CATEGORIES)
    ]
    balmorel_load = format_balmorel_df(
        aggregate_regions(balmorel_load, "sum", ["Season", "Time"]), year
    )

    # The cached balmorel_prices.csv stays in the Price Year, convert after reading it
    balmorel_elprices = format_balmorel_df(
        aggregate_regions(balmorel_elprices, elpriceaggfunc, ["Season", "Time"]),
        year,
    )
    balmorel_elprices = balmorel_prices_in_year(balmorel_elprices, year)
    balmorel_generation = format_balmorel_df(
        aggregate_regions(balmorel_generation, "sum", ["Season", "Time"]),
        year,
    )

    # Aggregate technology groups
    balmorel_generation = map_technology_categories(
        balmorel_generation, balmorel_to_category, "Balmorel", allow_unmapped
    )

    # Check unique regions in Balmorel results
    balmorel_load_unique_regions = set(balmorel_load.Region.unique())
    balmorel_elprices_unique_regions = set(balmorel_elprices.Region.unique())
    balmorel_generation_unique_regions = set(balmorel_generation.Region.unique())
    set_difference = balmorel_load_unique_regions.difference(
        balmorel_elprices_unique_regions
    ).union(balmorel_load_unique_regions.difference(balmorel_generation_unique_regions))

    if set_difference:
        warn(f"Difference in region sets between Balmorel results: {set_difference}")

    return (
        balmorel_load,
        balmorel_elprices,
        balmorel_generation,
        balmorel_flows,
        balmorel_load_unique_regions,
        balmorel_elprices_unique_regions,
        balmorel_generation_unique_regions,
        balmorel_load_components_twh,
    )


def get_and_format_entsoe(entsoe_data_path, year, elpriceaggfunc, allow_unmapped: bool = False):
    # Load
    entsoe_load, entsoe_elprices, entsoe_generation = load_entsoe_data(
        entsoe_data_path, year
    )
    entsoe_load = aggregate_regions(entsoe_load, "sum", ["Time"])

    # Electricity prices
    entsoe_elprices = aggregate_regions(entsoe_elprices, elpriceaggfunc, ["Time"])

    # Generation of electricity
    entsoe_generation = (
        entsoe_generation.pivot_table(index=["Time", "Region"]).stack().reset_index()
    )
    entsoe_generation.columns = ["Time", "Region", "Technology", "Value"]
    entsoe_generation = aggregate_regions(entsoe_generation, "sum", ["Time"])

    # Aggregate technology groups
    entsoe_generation = map_technology_categories(
        entsoe_generation, entsoe_to_category, "ENTSO-E", allow_unmapped
    )

    entsoe_load_unique_regions = set(entsoe_load.Region.unique())
    entsoe_elprices_unique_regions = set(entsoe_elprices.Region.unique())
    entsoe_generation_unique_regions = set(entsoe_generation.Region.unique())

    # Find amount of unique regions in ENTSO-E datasets
    set_difference = entsoe_load_unique_regions.difference(
        entsoe_elprices_unique_regions
    ).union(entsoe_load_unique_regions.difference(entsoe_generation_unique_regions))

    if set_difference:
        warn(f"Difference in region sets between ENTSO-E datasets: {set_difference}")

    return (
        entsoe_load,
        entsoe_elprices,
        entsoe_generation,
        entsoe_load_unique_regions,
        entsoe_elprices_unique_regions,
        entsoe_generation_unique_regions,
    )


def join_hourly(
    entsoe: pd.DataFrame, balmorel: pd.DataFrame, year: int, quantity: str
) -> pd.DataFrame:
    """Join hourly ENTSO-E and Balmorel values on (Region, Time), keeping the hours both have.

    Warns, per region in both, when either side has fewer hours than the
    Backcast Calendar, since the comparison then leaves those hours out.

    Args:
        entsoe (pd.DataFrame): Columns 'Region', 'Time' and 'Value'.
        balmorel (pd.DataFrame): Columns 'Region', 'Time' and 'Value'.
        year (int): The Backcast Year.
        quantity (str): What is joined, e.g. 'load', named in the warning.

    Returns:
        pd.DataFrame: Index (Region, Time), columns 'ENTSOE' and 'BALMOREL'.
    """
    hours = backcast_hours(year)
    regions = set(entsoe.Region) & set(balmorel.Region)
    for source, df in (("ENTSO-E", entsoe), ("Balmorel", balmorel)):
        counts = (
            df[df.Region.isin(regions) & df.Time.isin(hours) & df.Value.notna()]
            .groupby("Region")["Time"]
            .nunique()
            .reindex(sorted(regions), fill_value=0)
        )
        for region, n_hours in counts[counts < len(hours)].items():
            warn(
                f"{source} {quantity} of {region} has {n_hours} of the {len(hours)} hours of the "
                f"Backcast Calendar, so the {quantity} comparison leaves out "
                f"{len(hours) - n_hours} hours."
            )

    return (
        entsoe.set_index(["Region", "Time"])
        .rename(columns={"Value": "ENTSOE"})
        .join(
            balmorel.rename(columns={"Value": "BALMOREL"}).set_index(["Region", "Time"]),
            how="inner",
        )
    )


def join_generation(
    entsoe: pd.DataFrame, balmorel: pd.DataFrame, regions: set[str], year: int
) -> pd.DataFrame:
    """Join hourly generation per category on the full grid of the Backcast Calendar.

    MainResults leaves out zeros, so a category Balmorel has no row for in an
    hour produced 0. ENTSO-E's missing categories are 0 too, but only in
    hours where ENTSO-E reports some generation for the region; a region-hour
    without any ENTSO-E generation is left out on both sides.

    Args:
        entsoe (pd.DataFrame): Columns 'Region', 'Technology', 'Time' and 'Value'.
        balmorel (pd.DataFrame): Columns 'Region', 'Technology', 'Time' and 'Value'.
        regions (set[str]): The regions both datasets have.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index (Region, Technology, Time), columns 'ENTSOE' and 'BALMOREL'.
    """
    keys = ["Region", "Technology", "Time"]
    hours = backcast_hours(year)
    entsoe = entsoe[entsoe.Region.isin(regions) & entsoe.Time.isin(hours)]
    balmorel = balmorel[balmorel.Region.isin(regions) & balmorel.Time.isin(hours)]

    generation = (
        entsoe.rename(columns={"Value": "ENTSOE"})
        .set_index(keys)
        .join(balmorel.rename(columns={"Value": "BALMOREL"}).set_index(keys), how="outer")
        .reset_index()
    )
    reported = entsoe.loc[entsoe.Value.notna(), ["Region", "Time"]].drop_duplicates()
    generation = generation.merge(reported, on=["Region", "Time"], how="inner")
    generation[["ENTSOE", "BALMOREL"]] = generation[["ENTSOE", "BALMOREL"]].fillna(0)

    return generation.set_index(keys).sort_index()


def load_components_table(
    components: pd.DataFrame, entsoe_load: pd.DataFrame, year: int
) -> pd.DataFrame:
    """Balmorel's annual load per category next to ENTSO-E's annual load, per region.

    Args:
        components (pd.DataFrame): Output of balmorel_load_components.
        entsoe_load (pd.DataFrame): Hourly ENTSO-E load (MW) with 'Region',
            'Time' and 'Value'.
        year (int): The Backcast Year; ENTSO-E is summed over its Backcast Calendar.

    Returns:
        pd.DataFrame: Columns 'Region', 'Category', 'BALMOREL', 'Excluded' and
            'ENTSOE' (TWh). Per region, a 'Total compared' row sums the
            categories that aren't excluded and holds ENTSO-E's annual load.
    """
    entsoe_annual = (
        entsoe_load[entsoe_load.Time.isin(backcast_hours(year))].groupby("Region")["Value"].sum()
        / 1e6
    )
    totals = (
        components[~components.Excluded]
        .groupby("Region", as_index=False)["BALMOREL"]
        .sum()
        .assign(Category="Total compared", Excluded=False)
    )
    totals["ENTSOE"] = totals.Region.map(entsoe_annual)

    return (
        pd.concat([components, totals], ignore_index=True)
        .sort_values(["Region", "Category"], key=lambda col: col.replace("Total compared", "~"))
        .reset_index(drop=True)[["Region", "Category", "BALMOREL", "Excluded", "ENTSOE"]]
    )


def load_and_align(
    balmorel_scenario: str,
    balmorel_scenario_path: str,
    entsoe_data_path: str,
    year: int,
    elpriceaggfunc: str,
    overwrite: bool,
    percentile: float = OBSERVED_FLOW_PERCENTILE,
    allow_unmapped: bool = False,
):

    # Load and format data
    (
        entsoe_load,
        entsoe_elprices,
        entsoe_generation,
        entsoe_load_unique_regions,
        entsoe_elprices_unique_regions,
        entsoe_generation_unique_regions,
    ) = get_and_format_entsoe(entsoe_data_path, year, elpriceaggfunc, allow_unmapped)

    (
        balmorel_load,
        balmorel_elprices,
        balmorel_generation,
        balmorel_flows,
        balmorel_load_unique_regions,
        balmorel_elprices_unique_regions,
        balmorel_generation_unique_regions,
        balmorel_load_components_twh,
    ) = get_and_format_balmorel(
        balmorel_scenario,
        balmorel_scenario_path,
        year,
        elpriceaggfunc,
        overwrite,
        allow_unmapped,
    )

    # Get unique regions
    entsoe_unique_regions = entsoe_load_unique_regions.intersection(
        entsoe_elprices_unique_regions
    ).intersection(entsoe_generation_unique_regions)
    balmorel_unique_regions = balmorel_load_unique_regions.intersection(
        balmorel_elprices_unique_regions
    ).intersection(balmorel_generation_unique_regions)
    dataset_difference = entsoe_unique_regions.difference(balmorel_unique_regions)
    if dataset_difference:
        warn(
            f"These regions are either only in the ENTSO-E dataset or Balmorel results and will be filtered away when data is joined: {dataset_difference}"
        )

    # Join datasets
    prices = join_hourly(entsoe_elprices, balmorel_elprices, year, "price")
    loads = join_hourly(entsoe_load, balmorel_load, year, "load")
    generation = join_generation(
        entsoe_generation,
        balmorel_generation,
        entsoe_unique_regions.intersection(balmorel_unique_regions),
        year,
    )

    components_file = Path(balmorel_scenario_path).joinpath("backcastoutput/load_components.csv")
    load_components_table(balmorel_load_components_twh, entsoe_load, year).to_csv(
        components_file, index=False
    )
    print(f"Wrote the annual load per category to {components_file}")

    flows = align_flows(
        load_entsoe_flows(entsoe_data_path, year),
        balmorel_flows,
        observed_flow_limits(entsoe_data_path, year, percentile),
    )

    return prices, loads, generation, flows


def plot_bar_chart(
    df: pd.DataFrame, columns_to_keep: list = [], per_region: bool = False
):

    if per_region:
        fig, ax = plt.subplots(figsize=(12, 5), dpi=300)

        if len(columns_to_keep) > 0:
            df_agg = df.pivot_table(
                index=columns_to_keep,
                columns="Region",
                values=["ENTSOE", "BALMOREL"],
                aggfunc=lambda x: np.sum(x) / 1e6,
            ).T
            df_agg.index.names = ["Value", "Region"]
            df_agg = df_agg.sort_index(level=["Region", "Value"])
            df_agg = df_agg.reset_index().set_index(["Region", "Value"])
        else:
            df_agg = df.pivot_table(
                index="Region",
                values=["ENTSOE", "BALMOREL"],
                aggfunc=lambda x: np.sum(x) / 1e6,
            )

        df_agg.plot(ax=ax, kind="bar", stacked=True, color=colors)
        ax.set_ylabel("Generation (TWh)")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
        fig.savefig("generation_per_region.png", bbox_inches="tight")
    else:
        fig, ax = plt.subplots()

        if len(columns_to_keep) > 0:
            df_agg = df.pivot_table(
                index=columns_to_keep, aggfunc=lambda x: np.sum(x) / 1e6
            ).T
        else:
            df_agg = df.T.sum() / 1e6

        df_agg.plot(ax=ax, kind="bar", stacked=True, color=colors)
        ax.set_ylabel("Generation (TWh)")
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
        fig.savefig(
            "generation.png",
            bbox_inches="tight",
        )


def plot_price_profile(prices: pd.DataFrame):

    prices = prices.reset_index()
    prices.Time = pd.to_datetime(prices.Time, utc=True)

    df = (
        prices.pivot_table(index="Time", values=["ENTSOE", "BALMOREL"])
        .resample("1D")
        .aggregate("mean")
    )

    fig, ax = plt.subplots()
    df.plot(ax=ax, color={"ENTSOE": ENTSOE_COLOUR, "BALMOREL": BALMOREL_COLOUR})
    ax.set_ylabel(f"El. Price (nominal €{df.index.year.max()}/MWh)")
    fig.savefig("prices.png", bbox_inches="tight")


def plot_price_duration_curves(
    prices: pd.DataFrame, title: str, ylim: tuple[float, float] = (-60, 320)
) -> tuple[Figure, np.ndarray]:
    """Price duration curves of ENTSO-E and Balmorel, pooled and per region.

    One large panel pools all region-hours; small multiples follow per region
    in PRICE_DURATION_REGION_ORDER, then any other region alphabetically.
    Every panel has the same, clipped y-range; the subtitle says how many
    region-hours each side has outside it.

    Args:
        prices (pd.DataFrame): Columns 'Region', 'ENTSOE' and 'BALMOREL'
            (nominal €/MWh of the Backcast Year), as in prices.csv.
        title (str): Figure title.
        ylim (tuple[float, float], optional): Y-range in €/MWh. Defaults to (-60, 320).

    Returns:
        tuple[Figure, np.ndarray]: The figure and its axes, pooled panel first.
    """
    ink, ink2, muted, grid, axis_colour, surface = (
        "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    )
    y_low, y_high = ylim
    n_columns = 8
    prices = prices.dropna(subset=["ENTSOE", "BALMOREL"])
    regions = set(prices.Region)
    order = [region for region in PRICE_DURATION_REGION_ORDER if region in regions]
    order += sorted(regions - set(order))
    lines = [
        ("ENTSOE", ENTSOE_COLOUR, "ENTSO-E (observed)"),
        ("BALMOREL", BALMOREL_COLOUR, "Balmorel (Price Year → nominal)"),
    ]

    def duration_curve(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        values = np.sort(values)[::-1]
        return np.linspace(0, 100, len(values)), values

    def draw(ax: Axes, df: pd.DataFrame, panel_title: str, big: bool = False) -> None:
        for column, colour, label in lines:
            x, y = duration_curve(df[column].to_numpy())
            ax.plot(
                x, np.clip(y, y_low, y_high), color=colour, lw=2 if big else 1.4,
                solid_capstyle="round", label=label,
            )
        ax.set_ylim(y_low, y_high)
        ax.set_xlim(0, 100)
        ax.grid(axis="y", color=grid, lw=0.8)
        ax.set_axisbelow(True)
        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)
        ax.axhline(0, color=axis_colour, lw=0.8)
        ax.set_xticks([0, 50, 100])
        ax.set_yticks([tick for tick in range(0, int(y_high) + 1, 100) if tick >= y_low])
        ax.tick_params(length=0, labelsize=9 if big else 7)
        ax.set_title(
            panel_title, loc="left", color=ink, fontsize=12 if big else 9,
            fontweight="bold", pad=3,
        )
        entsoe, balmorel = df["ENTSOE"], df["BALMOREL"]
        ax.text(
            0.98, 0.97,
            f"mean {entsoe.mean():.0f} / {balmorel.mean():.0f}\n"
            f"std {entsoe.std():.0f} / {balmorel.std():.0f}\n"
            f"h ≤ 0: {(entsoe <= 0).sum()} / {(balmorel <= 0).sum()}",
            transform=ax.transAxes, ha="right", va="top", fontsize=9 if big else 6.5,
            color=ink2, linespacing=1.25,
        )

    style = {
        "font.family": "sans-serif", "font.size": 8, "axes.edgecolor": axis_colour,
        "axes.labelcolor": ink2, "xtick.color": muted, "ytick.color": muted,
        "figure.facecolor": surface, "axes.facecolor": surface,
    }
    with plt.rc_context(style):
        fig = plt.figure(figsize=(17, 13.5))
        grid_spec = GridSpec(
            6, n_columns, figure=fig, hspace=0.55, wspace=0.18,
            left=0.04, right=0.99, top=0.9, bottom=0.04,
        )
        pooled = fig.add_subplot(grid_spec[0:2, 0:3])
        draw(pooled, prices, "All bidding zones (pooled region-hours)", big=True)
        pooled.set_ylabel("€/MWh (nominal)")
        pooled.set_xlabel("share of hours (%)")

        slots = [(row, col) for row in range(0, 2) for col in range(3, n_columns)]
        slots += [(row, col) for row in range(2, 6) for col in range(n_columns)]
        if len(order) > len(slots):
            warn(f"Only the first {len(slots)} of {len(order)} regions fit in the price duration plot.")
        axes = [pooled]
        for (row, col), region in zip(slots, order):
            ax = fig.add_subplot(grid_spec[row, col])
            draw(ax, prices[prices.Region == region], region)
            if col not in (0, 3):
                ax.set_yticklabels([])
            axes.append(ax)
        for row, col in slots[len(order):]:
            fig.add_subplot(grid_spec[row, col]).axis("off")

        n_outside = (
            (prices[["ENTSOE", "BALMOREL"]] < y_low) | (prices[["ENTSOE", "BALMOREL"]] > y_high)
        ).sum()
        fig.suptitle(title, x=0.04, ha="left", fontsize=15, fontweight="bold", color=ink, y=0.975)
        fig.text(
            0.04, 0.935,
            "Balmorel prices converted from the Price Year to nominal euros of the Backcast Year. "
            f"Panel text: ENTSO-E / Balmorel. Y-axis clipped to [{y_low:g}, {y_high:g}] €/MWh "
            f"(ENTSO-E region-hours outside: {n_outside.ENTSOE}, Balmorel: {n_outside.BALMOREL}).",
            fontsize=10, color=ink2,
        )
        handles, labels = pooled.get_legend_handles_labels()
        fig.legend(
            handles, labels, loc="upper right", bbox_to_anchor=(0.99, 0.975),
            frameon=False, fontsize=10, ncol=2, labelcolor=ink,
        )

    return fig, np.array(axes)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.group()
def main():
    pass


# TODO: Reformat this, so it just needs a Balmorel model folder, scenario name and entsoe-data-path
# After that, the remaining folders should be created automatically, and the other functions should 'just'
# be provided a scenario folder name
@main.command()
@click.argument("balmorel-scenario", type=str)
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--elpriceaggfunc",
    type=str,
    default="mean",
    help="The function used for spatial aggregation of electricity prices.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite last generated .csv files?",
)
@click.option(
    "--percentile",
    type=float,
    default=OBSERVED_FLOW_PERCENTILE,
    show_default=True,
    help="Percentile (in percent) of the hourly flow used as the Observed Flow Limit "
    "in flows.csv; use the same value as transmission-flow-limit. 100 gives the maximum.",
)
@click.option(
    "--allow-unmapped",
    is_flag=True,
    default=False,
    help="Compare technologies missing from the category mappings as 'Unmapped' "
    "instead of stopping with an error.",
)
def format(
    balmorel_scenario,
    balmorel_scenario_path,
    entsoe_data_path,
    year,
    elpriceaggfunc,
    overwrite,
    percentile,
    allow_unmapped,
):

    load_file, price_file, generation_file, flow_file = (
        Path(balmorel_scenario_path).joinpath("backcastoutput/loads.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/prices.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/generation.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/flows.csv"),
    )

    prices, loads, generation, flows = load_and_align(
        balmorel_scenario,
        balmorel_scenario_path,
        entsoe_data_path,
        year,
        elpriceaggfunc,
        overwrite,
        percentile,
        allow_unmapped,
    )
    loads.to_csv(load_file)
    prices.to_csv(price_file)
    generation.to_csv(generation_file)
    flows.to_csv(flow_file)


@main.command()
@click.argument("balmorel-scenario-path", type=str)
def statistics(balmorel_scenario_path):

    load_file, price_file, generation_file = (
        Path(balmorel_scenario_path).joinpath("backcastoutput/loads.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/prices.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/generation.csv"),
    )

    if not (load_file.exists() and price_file.exists() and generation_file.exists()):
        raise FileNotFoundError(
            "Couldn't find data and/or results.\nRun `python -m pybalmorel.backcasting format`"
        )
    else:
        print("Load csv's from last loading")
        loads = pd.read_csv(load_file, index_col=[0, 1])
        prices = pd.read_csv(price_file, index_col=[0, 1])
        generation = pd.read_csv(generation_file, index_col=[0, 1, 2])

    print("\n\n")
    print("-" * 100)
    print("Statistics on load in MWh")
    calculate_statistics(loads)
    # plot_bar_chart()
    print("\n\n")
    print("-" * 100)
    print("Statistics on prices in €/MWh")
    calculate_statistics(prices)
    # plot_bar_chart()
    print("\n\n")
    print("-" * 100)
    print("Statistics on generation in MWh")
    for technology in generation.index.get_level_values(1).unique():
        print(f"\n{technology}:")
        calculate_statistics(generation.loc[(slice(None), technology, slice(None))])
    print("-" * 100)

    flow_file = Path(balmorel_scenario_path).joinpath("backcastoutput/flows.csv")
    if flow_file.exists():
        flows = pd.read_csv(flow_file, index_col=[0, 1, 2])
        print("\n\n")
        print("-" * 100)
        print("Statistics on cross-border flows per directed border")
        print(
            "(AtLimit: share of hours within 1% of the Observed Flow Limit; "
            "ENTSO-E exceeds it in about 1% of its flowing hours, Balmorel cannot)"
        )
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(flow_statistics(flows).round(2))
        print("-" * 100)
    else:
        warn(f"No {flow_file} - rerun `format` to include cross-border flows.")


@main.command()
@click.argument("balmorel-scenario-path", type=str)
def generation(balmorel_scenario_path):

    generation_file = Path(balmorel_scenario_path).joinpath(
        "backcastoutput/generation.csv"
    )

    if not (generation_file.exists()):
        raise FileNotFoundError(
            "Couldn't find generation data and/or results.\nRun `python -m pybalmorel.backcasting format`"
        )
    else:
        print("Load csv's from last loading")
        generation = pd.read_csv(generation_file, index_col=[0, 1, 2])

    plot_bar_chart(generation, ["Technology"])
    plot_bar_chart(generation, ["Technology"], True)


@main.command()
@click.argument("balmorel-scenario-path", type=str)
def prices(balmorel_scenario_path):

    prices_file = Path(balmorel_scenario_path).joinpath("backcastoutput/prices.csv")

    if not (prices_file.exists()):
        raise FileNotFoundError(
            "Couldn't find generation data and/or results.\nRun `python -m pybalmorel.backcasting format`"
        )
    else:
        print("Load csv's from last loading")
        prices = pd.read_csv(prices_file, index_col=[0, 1, 2])

    plot_price_profile(prices)


@main.command(name="price-duration")
@click.argument("balmorel-scenario-path", type=str)
@click.option(
    "--ylim",
    type=(float, float),
    default=(-60, 320),
    show_default=True,
    help="Y-range of every panel in €/MWh; prices outside are clipped and counted in the subtitle.",
)
def price_duration(balmorel_scenario_path, ylim):
    """Plot price duration curves of Balmorel vs ENTSO-E, pooled and per region.

    Reads <balmorel-scenario-path>/backcastoutput/prices.csv from `format`, in
    nominal euros of the Backcast Year, and saves price_duration_curves.png.
    """
    prices_file = Path(balmorel_scenario_path).joinpath("backcastoutput/prices.csv")
    if not prices_file.exists():
        raise FileNotFoundError(
            "Couldn't find price data and/or results.\nRun `python -m pybalmorel.backcasting format`"
        )
    prices = pd.read_csv(prices_file)
    year = pd.to_datetime(prices.Time, utc=True).dt.year.mode().iloc[0]
    scenario = Path(balmorel_scenario_path).resolve().name

    fig, _ = plot_price_duration_curves(
        prices, f"Price duration curves {year} — {scenario} vs ENTSO-E day-ahead", tuple(ylim)
    )
    fig.savefig("price_duration_curves.png", dpi=130)
    print(f"Saved price_duration_curves.png with {prices.Region.nunique()} regions")


@main.command()
@click.argument("balmorel-scenario-path", type=str)
def flows(balmorel_scenario_path):
    """Plot duration curves of Balmorel vs ENTSO-E flows per directed border."""

    flow_file = Path(balmorel_scenario_path).joinpath("backcastoutput/flows.csv")

    if not (flow_file.exists()):
        raise FileNotFoundError(
            "Couldn't find flow data and/or results.\nRun `python -m pybalmorel.backcasting format`"
        )
    else:
        print("Load csv's from last loading")
        flows = pd.read_csv(flow_file, index_col=[0, 1, 2])

    fig, _ = plot_flow_duration_curves(flows)
    fig.savefig("flow_duration_curves.png", bbox_inches="tight")


@main.command(name="transmission-flow-limit")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--percentile",
    type=float,
    default=OBSERVED_FLOW_PERCENTILE,
    show_default=True,
    help="Percentile (in percent) of the hourly flow over the hours with flow. "
    "100 gives the maximum.",
)
def transmission_flow_limit(balmorel_scenario_path, entsoe_data_path, year, percentile):
    """Write XKFX_ENTSOE.inc: backcast transmission overrides from the ENTSO-E Observed Flow Limit.

    Reads the scenario's current XKFX borders, fetches matching ENTSO-E
    cross-border flows for YEAR, and writes/updates
    <balmorel-scenario-path>/data/XKFX_ENTSOE.inc plus the $include in XKFX.inc.
    See CONTEXT.md and docs/adr/0005, 0006, 0010.
    """
    from .flows import generate_transmission_flow_limit_overrides
    from ..entsoe import get_api_key

    balmorel_scenario_path = Path(balmorel_scenario_path)
    balmorel_model_folder = balmorel_scenario_path.parent
    scenario = balmorel_scenario_path.name

    api_key = get_api_key()
    gams_system_directory = config("GAMS_SYSTEM_DIR", None)

    generate_transmission_flow_limit_overrides(
        balmorel_model_folder,
        scenario,
        year,
        entsoe_data_path,
        api_key,
        gams_system_directory=gams_system_directory,
        percentile=percentile,
    )


@main.command(name="nuclear-availability")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def nuclear_availability(balmorel_scenario_path, entsoe_data_path, year, reload_input):
    """Write GKRATE_ENTSOE.inc: weekly Nuclear Availability from ENTSO-E nuclear output.

    Per country and Backcast Calendar week: the highest hourly nuclear output
    in the generation csv's under ENTSOE_DATA_PATH (from `download --query
    generation`), divided by the country's nuclear GKFX in YEAR, clipped at 1.
    Writes <balmorel-scenario-path>/data/GKRATE_ENTSOE.inc, which the scenario's
    GKRATE.inc must include. See CONTEXT.md.
    """
    from .nuclear import generate_nuclear_availability

    balmorel_scenario_path = Path(balmorel_scenario_path)
    observed = load_observed_nuclear(entsoe_data_path, year)
    if not observed:
        warn(
            f"No ENTSO-E nuclear output for {year} in {entsoe_data_path}. "
            f"Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} --query generation`"
        )

    generate_nuclear_availability(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        observed,
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command(name="thermal-availability")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def thermal_availability(balmorel_scenario_path, entsoe_data_path, year, reload_input):
    """Write GKRATE_THERMAL_ENTSOE.inc: weekly Thermal Availability from ENTSO-E capacity and outages.

    Per country, fuel group and Backcast Calendar week: ENTSO-E's installed
    capacity in YEAR as a share of the group's GKFX (at most 1), less the share
    reported out of service that week (from `download --query
    installed_generation_capacity --query unavailability_of_generation_units`).
    Writes <balmorel-scenario-path>/data/GKRATE_THERMAL_ENTSOE.inc, which the
    scenario's GKRATE.inc must include, and backcastoutput/thermal_capacity.csv,
    which checks GKFX against installed capacity and observed output. See CONTEXT.md.
    """
    from .thermal import generate_thermal_availability

    balmorel_scenario_path = Path(balmorel_scenario_path)
    generate_thermal_availability(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        entsoe_data_path,
        load_observed_generation(entsoe_data_path, year),
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command(name="must-run-floor")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--price-threshold",
    type=float,
    default=40.0,
    show_default=True,
    help="Nominal day-ahead price (€/MWh) at or below which a group still running shows must-run.",
)
@click.option(
    "--min-hours",
    type=int,
    default=4,
    show_default=True,
    help="Hours at or below the price threshold a week needs to get a floor.",
)
@click.option(
    "--every-week",
    multiple=True,
    default=("BIOMASS", "WASTE"),
    show_default=True,
    help="Fuel group floored in every week, whatever the price. Repeatable.",
)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def must_run_floor(
    balmorel_scenario_path, entsoe_data_path, year, price_threshold, min_hours, every_week, reload_input
):
    """Write the MUSTRUN files: weekly must-run floors from ENTSO-E output in low-price weeks.

    Per country, fuel group and Backcast Calendar week: the lowest hourly
    output in the generation csv's under ENTSOE_DATA_PATH, for weeks with at
    least MIN_HOURS day-ahead prices at or below PRICE_THRESHOLD, and for the
    --every-week groups in all weeks. Capped at Balmorel's available capacity,
    so run thermal-availability first. Writes MUSTRUN_ZONE, MUSTRUN_ZONE_RRR,
    MUSTRUN_GROUP, MUSTRUN_GROUP_FFF and, last, MUSTRUN_FLOOR (.inc) to
    <balmorel-scenario-path>/data/; MUSTRUN_FLOOR.inc switches Balmorel's
    MUSTRUN addon on. See CONTEXT.md.
    """
    from .mustrun import generate_must_run_floor

    balmorel_scenario_path = Path(balmorel_scenario_path)
    generation = load_observed_generation(entsoe_data_path, year)
    prices = load_observed_prices(entsoe_data_path, year)
    for name, data in (("generation", generation), ("day_ahead_prices", prices)):
        if len(data) == 0:
            warn(
                f"No ENTSO-E {name} for {year} in {entsoe_data_path}. "
                f"Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} --query {name}`"
            )

    generate_must_run_floor(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        generation,
        prices,
        load_observed_load(entsoe_data_path, year),
        price_threshold=price_threshold,
        min_hours=min_hours,
        every_week=tuple(every_week),
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command(name="demand-profile")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def demand_profile(balmorel_scenario_path, entsoe_data_path, year, reload_input):
    """Write DE_VAR_T_ENTSOE.inc: electricity demand profiles from ENTSO-E actual load.

    Per Balmorel region with electricity demand: the hourly ENTSO-E load of
    its canonical region in YEAR (from `download --query load`) on the
    Backcast Calendar, as DE_VAR_T for the users OTHER and RESE. Implausible
    hours are interpolated. Writes <balmorel-scenario-path>/data/DE_VAR_T_ENTSOE.inc
    and appends its $include to the scenario's DE_VAR_T.inc. Rerun after
    writing new weather-year data, which overwrites DE_VAR_T.inc. See CONTEXT.md.
    """
    from .demand import generate_demand_profile

    balmorel_scenario_path = Path(balmorel_scenario_path)
    zones = load_observed_load(entsoe_data_path, year)
    if zones.empty:
        warn(
            f"No ENTSO-E load for {year} in {entsoe_data_path}. "
            f"Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} --query load`"
        )

    generate_demand_profile(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        zones,
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command(name="demand-level")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--basis",
    type=click.Choice(["entsoe", "eurostat"]),
    default="entsoe",
    show_default=True,
    help="Level from ENTSO-E load net of distribution losses, or from Eurostat final consumption.",
)
@click.option(
    "--coverage-bounds",
    type=(float, float),
    default=(0.8, 1.3),
    show_default=True,
    help="Bounds on ENTSO-E load net of losses over Eurostat final consumption; outside them a country keeps its DE.",
)
@click.option(
    "--eurostat-data-path",
    type=str,
    default=None,
    help="Cache folder of the Eurostat responses. Defaults to <balmorel-scenario-path>/eurostatdata.",
)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def demand_level(
    balmorel_scenario_path, entsoe_data_path, year, basis, coverage_bounds, eurostat_data_path, reload_input
):
    """Write DE_ENTSOE.inc: the annual electricity demand level from ENTSO-E load and Eurostat heating.

    Per country: ENTSO-E's load in YEAR (from `download --query load`) net of
    Balmorel's distribution losses, less the electricity Eurostat reports for
    household space and water heating and for district heating, which
    Balmorel adds endogenously. Split over regions and users by the input
    data's DE. Eurostat responses are fetched once and cached. Writes
    <balmorel-scenario-path>/data/DE_ENTSOE.inc, which the scenario's DE.inc
    must include, and backcastoutput/demand_level.csv. See CONTEXT.md.
    """
    from .demand import generate_demand_level

    balmorel_scenario_path = Path(balmorel_scenario_path)
    zones = load_observed_load(entsoe_data_path, year)
    if zones.empty:
        warn(
            f"No ENTSO-E load for {year} in {entsoe_data_path}. "
            f"Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} --query load`"
        )

    generate_demand_level(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        zones,
        eurostat_data_path=eurostat_data_path,
        basis=basis,
        coverage_bounds=coverage_bounds,
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command(name="vre-flh")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--bounds",
    type=(float, float),
    default=(0.6, 1.5),
    show_default=True,
    help="Lowest and highest factor written; a region and kind outside them keeps its full-load hours.",
)
@click.option(
    "--reload-input",
    is_flag=True,
    help="Run ReadData again instead of reusing the cached <scenario>_input_data.gdx (takes a while).",
)
def vre_flh(balmorel_scenario_path, entsoe_data_path, year, bounds, reload_input):
    """Write WNDFLH_ENTSOE.inc and SOLEFLH_ENTSOE.inc: VRE full-load hours scaled to ENTSO-E output.

    Per country and kind (solar, onshore, offshore): one factor that makes
    Balmorel's available output in YEAR (GKFX x FLH x GKRATE) equal ENTSO-E's
    reported output (from `download --query generation`), applied to the
    full-load hours of every area of that country and kind. Writes both files
    to <balmorel-scenario-path>/data/, appends their $include to the
    scenario's WNDFLH.inc and SOLEFLH.inc, and writes backcastoutput/vre_flh.csv.
    Rerun after every weather-year run, which overwrites WNDFLH.inc and
    SOLEFLH.inc. See CONTEXT.md.
    """
    from .vre import generate_vre_flh

    balmorel_scenario_path = Path(balmorel_scenario_path)
    generation = load_observed_generation(entsoe_data_path, year)
    if len(generation) == 0:
        warn(
            f"No ENTSO-E generation for {year} in {entsoe_data_path}. "
            f"Run `python -m pybalmorel.backcasting download {entsoe_data_path} {year} --query generation`"
        )

    generate_vre_flh(
        balmorel_scenario_path.parent,
        balmorel_scenario_path.name,
        year,
        generation,
        bounds=bounds,
        gams_system_directory=config("GAMS_SYSTEM_DIR", None),
        reload_input=reload_input,
    )


@main.command()
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--query",
    "queries",
    multiple=True,
    type=click.Choice(entsoe_queries + entsoe_capacity_queries),
    help=(
        "ENTSO-E data to download. Repeatable. Defaults to "
        f"{', '.join(entsoe_queries)}; {' and '.join(entsoe_capacity_queries)} "
        "(for thermal-availability) only on request."
    ),
)
def download(entsoe_data_path, year, queries):
    """Download ENTSO-E data for YEAR into ENTSOE_DATA_PATH, for `format` and `transmission-flow-limit`.

    Fetches every zone in pybalmorel.entsoe.bidding_zones, and the flows of
    every neighbouring pair of them. Files already downloaded, and pairs
    ENTSO-E had no data for on an earlier run, are skipped, so rerun to retry
    failed requests.
    """
    from ..entsoe import (
        bidding_zones,
        fetch_annual_data,
        fetch_annual_transmission_data,
        get_api_key,
        neighbour_pairs,
    )

    path = Path(entsoe_data_path)
    path.mkdir(parents=True, exist_ok=True)
    api_key = get_api_key()

    for query in queries or entsoe_queries:
        print(f"Downloading {year} {query} to {path}")
        if query == "crossborder_flows":
            fetch_annual_transmission_data(
                query, neighbour_pairs(bidding_zones), year, path, api_key
            )
        else:
            fetch_annual_data(query, year, bidding_zones, path, api_key)


@main.command(name="ttf-csv")
@click.argument("html-path", type=str)
@click.argument("historicalprices-path", type=str)
def ttf_csv(html_path, historicalprices_path):
    """Split a saved Yahoo Finance TTF=F history page into natural_gas_TTF_<year>.csv.

    HTML_PATH is the page https://finance.yahoo.com/quote/TTF%3DF/history/
    saved from a browser, covering any number of years. One CSV per year is
    written to HISTORICALPRICES_PATH in the format the fuelprices command reads.
    """
    from .fuelprices import split_yahoo_ttf_html

    for csv_path in split_yahoo_ttf_html(html_path, historicalprices_path):
        print(f"Wrote {csv_path}")


@main.command(name="fuelprices")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("historicalprices-path", type=str)
@click.argument("year", type=int)
def fuelprices(balmorel_scenario_path, historicalprices_path, year):
    """Write FUELPRICE.inc + FUELPRICE_CONSTANT.inc: (S,T)-resolved historical
    NATGAS/COAL prices for backcasting.

    Reads HISTORICALPRICES_PATH's CSVs, converts them to the Price Year
    (EUR2016, bundled HICP and EUR/USD tables), maps them onto the UTC Backcast
    Calendar and writes <balmorel-scenario-path>/data/FUELPRICE.inc and
    FUELPRICE_CONSTANT.inc. See docs/adr/0001-fuelprice-season-term-resolution.md
    in the Balmorel repo. Warns if balopt.opt doesn't set
    FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT (it is never edited).
    """
    from .fuelprices import generate_fuelprice_overrides

    generate_fuelprice_overrides(historicalprices_path, year, balmorel_scenario_path)


@main.command(name="co2-tax")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("historicalprices-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--co2-override",
    "co2_overrides",
    multiple=True,
    metavar="COUNTRY=VALUE",
    help="Flat nominal EUR/tCO2 for a Balmorel CCC country instead of the EUA "
    "price, e.g. UNITED_KINGDOM=85 or SERBIA=0. Repeatable.",
)
def co2_tax(balmorel_scenario_path, historicalprices_path, year, co2_overrides):
    """Write TAX_CO2_ST.inc: (S,T)-resolved historical CO2 tax for backcasting.

    Reads the EEX EUA primary-auction report for YEAR under
    HISTORICALPRICES_PATH, converts it to the Price Year (EUR2016), maps it onto
    the UTC Backcast Calendar and writes <balmorel-scenario-path>/data/TAX_CO2_ST.inc.
    See docs/adr/0002-co2-tax-season-term-resolution.md in the Balmorel repo.
    Warns if balopt.opt doesn't set TAX_CO2_DOL=YYY_CCC_SSS_TTT (it is never edited).
    """
    from .co2tax import generate_co2_tax_override, parse_co2_overrides

    generate_co2_tax_override(
        historicalprices_path,
        year,
        balmorel_scenario_path,
        parse_co2_overrides(co2_overrides),
    )


if __name__ == "__main__":
    main()

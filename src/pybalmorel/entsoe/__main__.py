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
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo
from pathlib import Path
import click
from decouple import config
from pybalmorel import MainResults
from warnings import warn

# Replace with pybalmorel.entsoe import in the future
# import sys
# sys.path.append("/home/mberos/Repos/pybalmorel/src/pybalmorel")
# print(sys.path)
# from entsoe import bidding_zone_codes, bidding_zones
reversed_bidding_zone_codes = {
    "IT-NORD": "10Y1001A1001A73I",
    "IT-CNOR": "10Y1001A1001A70O",
    "IT-CSUD": "10Y1001A1001A71M",
    "IT-SUD": "10Y1001A1001A788",
    "IT-Calabria": "10Y1001C--00096J",
    "IT-Sicily": "10Y1001A1001A75E",
    "IT-Sardinia": "10Y1001A1001A74G",
    "NO1": "10YNO-1--------2",
    "NO2": "10YNO-2--------T",
    "NO3": "10YNO-3--------J",
    "NO4": "10YNO-4--------9",
    "NO5": "10Y1001A1001A48H",
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
    "BA": "10YBA-JPCC-----D",
}

bidding_zone_codes = {
    "10Y1001A1001A73I": "IT-NORD",
    "10Y1001A1001A70O": "IT-CNOR",
    "10Y1001A1001A71M": "IT-CSUD",
    "10Y1001A1001A788": "IT-SUD",
    "10Y1001C--00096J": "IT-Calabria",
    "10Y1001A1001A75E": "IT-Sicily",
    "10Y1001A1001A74G": "IT-Sardinia",
    "10YNO-1--------2": "NO1",
    "10YNO-2--------T": "NO2",
    "10YNO-3--------J": "NO3",
    "10YNO-4--------9": "NO4",
    "10Y1001A1001A48H": "NO5",
    "10Y1001A1001A44P": "SE1",
    "10Y1001A1001A45N": "SE2",
    "10Y1001A1001A46L": "SE3",
    "10Y1001A1001A47J": "SE4",
    "10YBA-JPCC-----D": "BA",
    "10YDK-1--------W": "DK1",
    "10YDK-2--------M": "DK2",
    "IE_SEM": "IE",
    "DE_LU": "DE",
}


bidding_zones = [
    "IE_SEM",
    "10YGB----------A",
    "PT",
    "ES",
    "FR",
    "BE",
    "NL",
    "DE_LU",
    "10YDK-1--------W",
    "10YDK-2--------M",
    "10YNO-1--------2",
    "10YNO-2--------T",
    "10YNO-3--------J",
    "10YNO-4--------9",
    "10Y1001A1001A48H",
    "10Y1001A1001A47J",
    "10Y1001A1001A45N",
    "10Y1001A1001A46L",
    "10Y1001A1001A47J",
    "FI",
    "EE",
    "LV",
    "LT",
    "PL",
    "CZ",
    "SK",
    "HU",
    "RO",
    "BG",
    "GR",
    "AL",
    "MK",
    "XK",
    "ME",
    "RS",
    "10YBA-JPCC-----D",
    "HR",
    "SI",
    "AT",
    "CH",
    "10Y1001A1001A73I",
    "10Y1001A1001A70O",
    "10Y1001A1001A71M",
    "10Y1001A1001A788",
    "10Y1001C--00096J",
    "10Y1001A1001A75E",
    "10Y1001A1001A74G",
]

balmorel_regions = [
    "DK1",
    "DK2",
    "NO1",
    "NO2",
    "NO3",
    "NO4",
    "NO5",
    "FIN",
    "DE4-E",
    "DE4-N",
    "DE4-S",
    "DE4-W",
    "NL",
    "SE1",
    "SE2",
    "SE3",
    "SE4",
    "UK",
    "EE",
    "LV",
    "LT",
    "PL",
    "BE",
    "FR",
    "IT",
    "CH",
    "AT",
    "CZ",
    "ES",
    "PT",
    "SK",
    "HU",
    "SI",
    "HR",
    "RO",
    "BG",
    "GR",
    "IE",
    "LU",
    "AL",
    "ME",
    "MK",
    "BA",
    "RS",
    "MT",
    "CY",
]

bidding_zone_translation = {
    "IT-NORD": "IT",
    "IT-CNOR": "IT",
    "IT-CSUD": "IT",
    "IT-SUD": "IT",
    "IT-Calabria": "IT",
    "IT-Sicily": "IT",
    "IT-Sardinia": "IT",
    "DE4-E": "DE",
    "DE4-N": "DE",
    "DE4-S": "DE",
    "DE4-W": "DE",
    "FIN": "FI",
}

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
    # Storage & Flexibility
    "INTRASEASONAL-ELECT-STORAGE - ELECTRIC": "Storage & Flexibility",
    "INTRASEASONAL-HEAT-STORAGE - HEAT": "Storage & Flexibility",
    "INTERSEASONAL-HEAT-STORAGE - HEAT": "Storage & Flexibility",
    "ELECT-TO-HEAT - ELECTRIC": "Storage & Flexibility",
    "CHP-BACK-PRESSURE - HEAT": "Storage & Flexibility",
    # Uncategorised (catch-all)
    "CONDENSING - DUMMY": "Other",
}

entsoe_to_category = {
    # Wind
    "Wind Onshore": "Wind",
    "Wind Offshore": "Wind",
    # Solar
    "Solar": "Solar",
    # Hydro
    "Hydro Run-of-river and poundage": "Hydro",
    "Hydro Water Reservoir": "Hydro",
    "Hydro Pumped Storage": "Hydro",
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
    # Fossil Liquid & Other Fossil
    "Fossil Oil": "Fossil Liquid & Other Fossil",
    "Fossil Oil shale": "Fossil Liquid & Other Fossil",
    # Waste & Heat Recovery
    "Waste": "Waste & Heat Recovery",
    # Storage & Flexibility
    "Geothermal": "Storage & Flexibility",
    "Marine": "Storage & Flexibility",
    "Other renewable": "Storage & Flexibility",
    "Other": "Storage & Flexibility",
}

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
    "Storage & Flexibility": "#F39C12",
    "Other": "#CCCCCC",
}

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
    raw_region_name = path.name.lstrip(f"{year}_").rstrip(f"_{parameter}.csv")
    if raw_region_name in bidding_zone_codes:
        region = bidding_zone_codes[raw_region_name]
    else:
        region = raw_region_name
    return region


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
            temp = df.iloc[:, 1:].T.groupby(level=0).first().T
            temp["Time"] = df.iloc[:, 0]
            df = temp
            aggregation = {col: "mean" for col in df.columns[:-1]}

    # Get time and resample to hours
    df.Time = pd.to_datetime(df.Time, utc=True).dt.tz_convert(
        "Europe/Copenhagen",
    )
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
    "Load csvs"
    path = Path(entsoe_data_path)
    data_items = ["load", "day_ahead_prices", "generation"]
    data = DataContainer(data_items)

    for item in path.iterdir():
        # Load data for a specific region
        tries = 0
        for data_item in data_items:
            if item.match(f"*_{data_item}.csv"):
                temp = format_entsoe_data(
                    pd.read_csv(item), resampling, item, year, data_item
                )
                setattr(
                    data,
                    data_item,
                    pd.concat((getattr(data, data_item), temp), ignore_index=True),
                )
            else:
                tries += 1

        if tries == len(data_items):
            warn(
                f"{item} was not loaded as it did not match naming pattern.",
                Warning,
            )

    return [getattr(data, data_item) for data_item in data_items]


def format_balmorel_df(df: pd.DataFrame, year: int):
    if not (df.Season.unique().shape[0] == 52 and df.Time.unique().shape[0] == 168):
        raise ValueError("Temporal structure not recognised!")

    new_timeindex = (
        pd.date_range(
            f"{year}-01-01 00:00",
            f"{year}-12-31 23:00",
            freq="h",
            tz=ZoneInfo("Europe/Copenhagen"),
        )
        .isocalendar()
        .reset_index()
    )

    # Get index of first monday and last sunday
    first_monday_hour = new_timeindex.iloc[:168, :].query("day == 1").index[0]
    last_sunday_hour = new_timeindex.query("day == 7").index[-1]
    new_timeindex = new_timeindex.loc[first_monday_hour:last_sunday_hour, "index"]

    # Insert to Balmorel df
    if "Technology" in df.columns:
        columns_in = ["Region", "Technology"]
        columns_out = columns_in[::-1]
    else:
        columns_in = ["Region"]
        columns_out = columns_in

    df_out = df.pivot_table(
        index=["Season", "Time"],
        columns=columns_in,
        values="Value",
        aggfunc="sum",
    )

    df_out.index = new_timeindex

    if type(df_out.columns) is pd.Index:
        df_out = df_out.stack().reset_index()
    elif type(df_out.columns) is pd.MultiIndex:
        df_out = df_out.stack().stack().reset_index()
    df_out.columns = ["Time"] + columns_out + ["Value"]

    return df_out


def load_balmorel_data(
    scenario_name: str, scenario_folder_path: str, year: int, overwrite: bool
):
    "Load df from MainResults"

    path = Path(scenario_folder_path).joinpath("backcastoutput")
    if (
        not path.joinpath("balmorel_prices.csv").exists()
        or not path.joinpath("balmorel_load.csv").exists()
        or not path.joinpath("balmorel_generation.csv").exists()
    ) or overwrite:
        print(
            "Loading balmorel timeseries results (may take a while - will be cached afterwards)"
        )
        results = MainResults(
            f"MainResults_{scenario_name}.gdx",
            paths=Path(scenario_folder_path).absolute().__str__(),
            system_directory=config("GAMS_SYSTEM_DIR", None),
        )  # pyright: ignore
        load = results.get_result("EL_DEMAND_YCRST").query(f"Year == '{year}'")
        elprices = results.get_result("EL_PRICE_YCRST").query(f"Year == '{year}'")
        generation = results.get_result("PRO_YCRAGFST").query(
            f"Year == '{year}' and Commodity == 'ELECTRICITY'"
        )
        load.to_csv(path.joinpath("balmorel_load.csv"), index=False)
        elprices.to_csv(path.joinpath("balmorel_prices.csv"), index=False)
        generation.to_csv(path.joinpath("balmorel_generation.csv"), index=False)
    else:
        print(
            "Loading cached Balmorel results (set overwrite=True to reload MainResults)"
        )
        load = pd.read_csv(path.joinpath("balmorel_load.csv"))
        elprices = pd.read_csv(path.joinpath("balmorel_prices.csv"))
        generation = pd.read_csv(path.joinpath("balmorel_generation.csv"))

    return load, elprices, generation


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
                f"\nStatistics for {region}:\nStd. dev:\n{temp.std().round()}\nMean:\n{temp.mean().round()}\nMin:\n{temp.mean().round()}\nMax:\n{temp.max().round()}"
            )
    else:
        print(
            f"\nStd. dev:\n{df.std().round()}\nMean:\n{df.mean().round()}\nMin:\n{df.mean().round()}\nMax:\n{df.max().round()}"
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


def get_and_format_balmorel(
    balmorel_scenario, balmorel_scenario_path, year, elpriceaggfunc, overwrite
):
    balmorel_load, balmorel_elprices, balmorel_generation = load_balmorel_data(
        balmorel_scenario, balmorel_scenario_path, year, overwrite
    )
    balmorel_load = format_balmorel_df(
        aggregate_regions(balmorel_load, "sum", ["Season", "Time"]), year
    )
    balmorel_elprices = format_balmorel_df(
        aggregate_regions(balmorel_elprices, elpriceaggfunc, ["Season", "Time"]),
        year,
    )
    balmorel_generation = format_balmorel_df(
        aggregate_regions(balmorel_generation, "sum", ["Season", "Time"]),
        year,
    )

    # Aggregate technology groups
    for tech_category in balmorel_generation.Technology:
        if tech_category not in balmorel_to_category:
            warn(
                f"{tech_category} technology category in Balmorel has not been mapped to overarching category in the balmorel_to_category dictionary!"
            )
    balmorel_generation.Technology = balmorel_generation.Technology.map(
        balmorel_to_category
    )
    balmorel_generation = balmorel_generation.groupby(
        ["Region", "Technology", "Time"], as_index=False
    ).sum(numeric_only=True)

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
        balmorel_load_unique_regions,
        balmorel_elprices_unique_regions,
        balmorel_generation_unique_regions,
    )


def get_and_format_entsoe(entsoe_data_path, year, elpriceaggfunc):
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

    for tech_category in entsoe_generation.Technology:
        if tech_category not in entsoe_to_category:
            warn(
                f"{tech_category} technology category in ENTSO-E has not been mapped to overarching category in the entsoe_to_category dictionary!"
            )

    # Aggregate technology groups
    entsoe_generation.Technology = entsoe_generation.Technology.map(entsoe_to_category)
    entsoe_generation = entsoe_generation.groupby(
        ["Region", "Technology", "Time"], as_index=False
    ).sum(numeric_only=True)

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


def load_and_align(
    balmorel_scenario: str,
    balmorel_scenario_path: str,
    entsoe_data_path: str,
    year: int,
    elpriceaggfunc: str,
    overwrite: bool,
):

    # Load and format data
    (
        entsoe_load,
        entsoe_elprices,
        entsoe_generation,
        entsoe_load_unique_regions,
        entsoe_elprices_unique_regions,
        entsoe_generation_unique_regions,
    ) = get_and_format_entsoe(entsoe_data_path, year, elpriceaggfunc)

    (
        balmorel_load,
        balmorel_elprices,
        balmorel_generation,
        balmorel_load_unique_regions,
        balmorel_elprices_unique_regions,
        balmorel_generation_unique_regions,
    ) = get_and_format_balmorel(
        balmorel_scenario, balmorel_scenario_path, year, elpriceaggfunc, overwrite
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
    prices = (
        entsoe_elprices.set_index(["Region", "Time"])
        .rename(columns={"Value": "ENTSOE"})
        .join(
            (
                balmorel_elprices.rename(columns={"Value": "BALMOREL"}).set_index(
                    ["Region", "Time"]
                )
            ),
            how="inner",
        )
    )

    loads = (
        entsoe_load.set_index(["Region", "Time"])
        .rename(columns={"Value": "ENTSOE"})
        .join(
            balmorel_load.rename(columns={"Value": "BALMOREL"}).set_index(
                ["Region", "Time"]
            ),
            how="inner",
        )
    )

    generation = (
        entsoe_generation.set_index(["Region", "Technology", "Time"])
        .rename(columns={"Value": "ENTSOE"})
        .join(
            balmorel_generation.rename(columns={"Value": "BALMOREL"}).set_index(
                ["Region", "Technology", "Time"]
            ),
            how="inner",
        )
    )

    return prices, loads, generation


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
    df.plot(ax=ax)
    ax.set_ylabel("El. Price (€/MWh)")
    fig.savefig("prices.png", bbox_inches="tight")


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.group()
def main():

    pass


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
def collect_and_format(
    balmorel_scenario,
    balmorel_scenario_path,
    entsoe_data_path,
    year,
    elpriceaggfunc,
    overwrite,
):

    load_file, price_file, generation_file = (
        Path(balmorel_scenario_path).joinpath("backcastoutput/loads.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/prices.csv"),
        Path(balmorel_scenario_path).joinpath("backcastoutput/generation.csv"),
    )

    print("Load ENTSO-E raw csvs and Balmorel results")
    prices, loads, generation = load_and_align(
        balmorel_scenario,
        balmorel_scenario_path,
        entsoe_data_path,
        year,
        elpriceaggfunc,
        overwrite,
    )
    loads.to_csv(load_file)
    prices.to_csv(price_file)
    generation.to_csv(generation_file)


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
            "Couldn't find data and/or results.\nRun `python -m pybalmorel.entsoe collect_and_format`"
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


@main.command()
@click.argument("balmorel-scenario-path", type=str)
def generation(balmorel_scenario_path):

    generation_file = Path(balmorel_scenario_path).joinpath(
        "backcastoutput/generation.csv"
    )

    if not (generation_file.exists()):
        raise FileNotFoundError(
            "Couldn't find generation data and/or results.\nRun `python -m pybalmorel.entsoe collect_and_format`"
        )
    else:
        print("Load csv's from last loading")
        generation = pd.read_csv(generation_file, index_col=[0, 1, 2])

    plot_bar_chart(generation, ["Technology"])
    plot_bar_chart(generation, ["Technology"], True)

    # plot_price_profile(prices)


if __name__ == "__main__":
    main()

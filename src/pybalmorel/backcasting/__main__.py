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
from pathlib import Path
import click
from decouple import config
from .. import MainResults
from ..entsoe import bidding_zone_translation, entsoe_code_to_region
from .calendar import from_backcast_grid
from .flows import (
    align_flows,
    entsoe_flow_limits,
    flow_statistics,
    format_balmorel_flows,
    load_entsoe_flows,
    plot_flow_duration_curves,
)
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
    # Pumped storage is storage on the Balmorel side too (INTRASEASONAL-ELECT-STORAGE),
    # so Hydro means natural-inflow hydro on both sides
    "Hydro Pumped Storage": "Storage & Flexibility",
    "Geothermal": "Storage & Flexibility",
    "Marine": "Storage & Flexibility",
    "Other renewable": "Storage & Flexibility",
    "Other": "Storage & Flexibility",
}

# ENTSO-E queries the download command fetches
entsoe_queries = ["load", "day_ahead_prices", "generation", "crossborder_flows"]

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
    known_suffixes = tuple(
        f"_{data_item}.csv" for data_item in data_items + ["crossborder_flows"]
    ) + ("_nodata.txt",)
    for item in path.glob(f"{year}_*"):
        if not item.name.endswith(known_suffixes):
            warn(
                f"{item} was not loaded as it did not match naming pattern.",
                Warning,
            )

    return [getattr(data, data_item) for data_item in data_items]


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


def get_and_format_balmorel(
    balmorel_scenario, balmorel_scenario_path, year, elpriceaggfunc, overwrite
):
    balmorel_load, balmorel_elprices, balmorel_generation, balmorel_flows = (
        load_balmorel_data(balmorel_scenario, balmorel_scenario_path, year, overwrite)
    )
    balmorel_flows = format_balmorel_flows(balmorel_flows, year)
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
        balmorel_flows,
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
        balmorel_flows,
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

    flows = align_flows(
        load_entsoe_flows(entsoe_data_path, year),
        balmorel_flows,
        entsoe_flow_limits(entsoe_data_path, year),
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
    df.plot(ax=ax)
    ax.set_ylabel("El. Price (€/MWh)")
    fig.savefig("prices.png", bbox_inches="tight")


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
def format(
    balmorel_scenario,
    balmorel_scenario_path,
    entsoe_data_path,
    year,
    elpriceaggfunc,
    overwrite,
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
        print("(AtLimit: share of hours within 1% of the ENTSO-E Observed Max Flow)")
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


@main.command(name="transmission-max-flow")
@click.argument("balmorel-scenario-path", type=str)
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
def transmission_max_flow(balmorel_scenario_path, entsoe_data_path, year):
    """Write XKFX_ENTSOE.inc: backcast transmission overrides from ENTSO-E Observed Max Flow.

    Reads the scenario's current XKFX borders, fetches matching ENTSO-E
    cross-border flows for YEAR, and writes/updates
    <balmorel-scenario-path>/data/XKFX_ENTSOE.inc plus the $include in XKFX.inc.
    See CONTEXT.md and docs/adr/0005, 0006.
    """
    from .flows import generate_transmission_max_flow_overrides
    from ..entsoe import get_api_key

    balmorel_scenario_path = Path(balmorel_scenario_path)
    balmorel_model_folder = balmorel_scenario_path.parent
    scenario = balmorel_scenario_path.name

    api_key = get_api_key()
    gams_system_directory = config("GAMS_SYSTEM_DIR", None)

    generate_transmission_max_flow_overrides(
        balmorel_model_folder,
        scenario,
        year,
        entsoe_data_path,
        api_key,
        gams_system_directory=gams_system_directory,
    )


@main.command()
@click.argument("entsoe-data-path", type=str)
@click.argument("year", type=int)
@click.option(
    "--query",
    "queries",
    multiple=True,
    type=click.Choice(entsoe_queries),
    help="ENTSO-E data to download. Repeatable. Defaults to all.",
)
def download(entsoe_data_path, year, queries):
    """Download ENTSO-E data for YEAR into ENTSOE_DATA_PATH, for `format` and `transmission-max-flow`.

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

"""
Functions to assemble CorRES VRE time-series outputs into Balmorel .inc files.

Reads per-technology scaled and raw Excel files produced by corres_to_energy_system_model,
combines them into area-indexed DataFrames, and writes WND_VAR_T / SOLE_VAR_T capacity-factor
series and WNDFLH / SOLEFLH full-load-hour tables for both the DA and CapDev resolutions.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

import os

import pandas as pd

from .to_inc import create_SSS_TTT_AAA_inc,create_AAA_inc
from .auxiliary_functions import (
    compute_capdev_timeseries,
    create_directory_if_needed,
    create_balmorel_time_mapping,
    parse_technology_folder_name,
)
from .config_models import ToBalmorelConfig
from .exceptions import EmptyMergeResultError, MissingRequiredColumnsError


def add_WND_VAR_T_Existing_RG2_RG3(combined_scaled_dfs):


    df_existing_RG2 = combined_scaled_dfs.filter(like='_Existing_RG1')
    df_existing_RG2.columns = df_existing_RG2.columns.str.replace('RG1', 'RG2')
    
    df_existing_RG3 = combined_scaled_dfs.filter(like='_Existing_RG1')
    df_existing_RG3.columns = df_existing_RG3.columns.str.replace('RG1', 'RG3')
    
    combined_scaled_dfs=pd.concat([combined_scaled_dfs,df_existing_RG2,df_existing_RG3],axis=1)

    return combined_scaled_dfs
    
def add_FLH_existing_RG2_RG3(combined_scaled_FLH):
    combined_scaled_FLH_existing_RG2 = combined_scaled_FLH[combined_scaled_FLH.index.str.contains('_Existing_RG1', regex=True)]
    combined_scaled_FLH_existing_RG2.index = combined_scaled_FLH_existing_RG2.index.str.replace('RG1', 'RG2')
    combined_scaled_FLH_existing_RG3 = combined_scaled_FLH_existing_RG2.copy()
    combined_scaled_FLH_existing_RG3.index = combined_scaled_FLH_existing_RG3.index.str.replace('RG2', 'RG3')

    combined_scaled_FLH=pd.concat([combined_scaled_FLH,combined_scaled_FLH_existing_RG2,combined_scaled_FLH_existing_RG3])

    return combined_scaled_FLH

def format_wind_column_names_for_balmorel(df: pd.DataFrame, tech_csv: str, onoff: str) -> pd.DataFrame:
    if onoff == "Existing":
        if "Offshore" in tech_csv:
            onoff_suf = "_OFF"
            tech = ""
            rg = "Existing_RG1"
        elif "Onshore" in tech_csv:
            onoff_suf = "_ONS"
            tech = ""
            rg = "Existing_RG1"
    else:
        parts = tech_csv.split('_', 3)
        rg_dict = {"RGA": "RG1", "RGB": "RG2", "RGC": "RG3"}
        tech = parts[0] + "-HH" + parts[1]
        rg = rg_dict[parts[2]]
        if onoff == "Onshore":
            onoff_suf = "_VRE-ONS"
        elif onoff == "Offshore_floating":
            onoff_suf = "_VRE-OFF_floating"
        elif onoff == "Offshore_bottom_fixed":
            onoff_suf = "_VRE-OFF_bottom_fixed"

    if onoff == "Existing":
        df.columns = df.columns + onoff_suf + "_" + rg
    else:
        df.columns = df.columns + onoff_suf + "_" + tech + "_" + rg
    return df

def transform_wind_flh_to_balmorel_format(df_cf: pd.DataFrame, onoff: str) -> pd.Series:

    df_cf_melted = df_cf.reset_index().melt(id_vars='index', var_name='Column', value_name='Value')

    if onoff == "Offshore_bottom_fixed":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Offshore", "VRE-OFF_bottom_fixed")
    elif onoff == "Future_Offshore_floating":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Offshore", "OFF_VRE-OFF_floating")
    elif onoff == "Existing":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Existing", "Existing_RG1")

    elif onoff == "Future_Onshore":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Onshore", "VRE-ONS")

    df_cf_melted['Index_Column_Combination'] = df_cf_melted['index'] + '_' + df_cf_melted['Column']
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGA", "RG1")
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGB", "RG2")
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGC", "RG3")
    df_cf_melted=df_cf_melted.set_index("Index_Column_Combination")["Value"]

    return df_cf_melted


def format_solar_column_names_for_balmorel(df: pd.DataFrame, tech_csv: str, onoff: str) -> pd.DataFrame:
    if "RGA" in tech_csv:
        rg = "RG1"
    elif "RGB" in tech_csv:
        rg = "RG2"
    elif "RGC" in tech_csv:
        rg = "RG3"

    if onoff == "PV_Utility_scale_no_tracking":
        onoff_suf = "_VRE-PV_Utility_scale_no_tracking"
    elif onoff == "PV_Utility_scale_tracking":
        onoff_suf = "_VRE-PV_Utility_scale_tracking"
    elif onoff == "PV_Rooftop":
        onoff_suf = "_VRE-PV_Rooftop"

    df.columns = df.columns + onoff_suf + "_" + rg
    return df


def load_full_load_hours_data(folder: str, output_folder: str, scaled_raw_ts: str) -> pd.Series:
    if "Existing" in folder:
        df_cf = pd.read_excel(
            os.path.join(output_folder, folder, "stats", f"FLH_{scaled_raw_ts}_ts.xlsx"),
            index_col="Unnamed: 0",
            sheet_name=None,
        )
        df_cf = pd.concat(df_cf.values(), ignore_index=False)
        df_cf['Existing'] = df_cf['Offshore_2020'].combine_first(df_cf['Onshore_2020'])
        df_cf = df_cf[['Existing']]
    else:
        df_cf = pd.read_excel(
            os.path.join(output_folder, folder, "stats", f"FLH_{scaled_raw_ts}_ts.xlsx"),
            index_col="Unnamed: 0",
        )

    onoff, source = parse_technology_folder_name(folder)
    df_cf = transform_wind_flh_to_balmorel_format(df_cf, onoff)
    return df_cf


def combine_technology_timeseries_files(folder: str, output_folder: str, scaled_raw_ts: str) -> pd.DataFrame:
    tech_csvs = os.listdir(os.path.join(output_folder, folder, scaled_raw_ts))
    onoff, source = parse_technology_folder_name(folder)
    if not tech_csvs:
        raise EmptyMergeResultError(
            f"No time-series files found in '{os.path.join(output_folder, folder, scaled_raw_ts)}'."
        )

    dfs: list[pd.DataFrame] = []

    for filename in tech_csvs:
        df = pd.read_excel(
            os.path.join(output_folder, folder, scaled_raw_ts, filename), index_col="time"
        )

        if df.columns.empty:
            raise MissingRequiredColumnsError(
                f"No data columns found in '{filename}' under folder '{folder}'."
            )

        if source=="wind":
            df = format_wind_column_names_for_balmorel(df, filename, onoff)
        elif source == "solar":
            df = format_solar_column_names_for_balmorel(df, filename, onoff)

        dfs.append(df)

    combined_df = pd.concat(dfs, axis=1, join="inner")
    if combined_df.empty or combined_df.columns.empty:
        raise EmptyMergeResultError(
            "Combined technology time series is empty after merging on the time index for "
            f"folder '{folder}' ({scaled_raw_ts})."
        )

    return combined_df
def export_timeseries_to_balmorel_format(config_fn: str, start_date: str, output_folder: str) -> tuple[dict[str, dict[str, list[pd.DataFrame]]], dict[str, dict[str, list[pd.Series]]]]:
    """Main function to export time series data to Balmorel .inc format.
    
    Args:
        config_fn: Path to the configuration file specifying parameters for the export process.
        start_date: The starting date for the time series data to be exported.
        output_folder: The folder where the output .inc files will be saved.
    Returns:
        A tuple containing two dictionaries: (dfs_scaled, FLH_scaled). 
        - dfs_scaled is a dictionary of DataFrames for the scaled time series data, organized by source and type (scaled/raw).
        - FLH_scaled is a dictionary of Series for the full-load hours, organized by source and type (scaled/raw).
    Raises:
        EmptyMergeResultError: If any of the combined technology time series DataFrames are empty after merging.
        MissingRequiredColumnsError: If any of the required columns are missing in the input Excel files during the merging process.
    """
    # Load the configuration for the export process from the specified file.
    balmorel_config = ToBalmorelConfig.from_file(config_fn)

    # Create the necessary output directories for the Balmorel .inc files, organized by date and category (DA, CapDev).
    year_output_folder = os.path.join(output_folder, str(start_date))
    balmorel_output_root = os.path.join(year_output_folder, "to_balmorel")
    for subfolder_parts in (("DA", "scaled"), ("DA", "raw"), ("CapDev",)):
        create_directory_if_needed(os.path.join(balmorel_output_root, *subfolder_parts))

    # List the contents of the output folder to identify the technology folders for wind and solar, based on specified criteria in their names.
    year_folder_contents = os.listdir(year_output_folder)
    wind_criteria = {"Offshore", "Onshore", "Existing"}
    solar_criteria = {"PV"}

    technology_folders_by_source = {}
    technology_folders_by_source["wind"] = {
        folder_name for folder_name in year_folder_contents if any(criteria in folder_name for criteria in wind_criteria)
    }
    technology_folders_by_source["solar"] = {
        folder_name for folder_name in year_folder_contents if any(criteria in folder_name for criteria in solar_criteria)
    }

    exported_timeseries_by_source = {}
    exported_flh_by_source = {}
    # Loop through each energy source (wind and solar) and process the corresponding technology folders to combine their time series data, 
    # compute full-load hours, and export the results in Balmorel .inc format for both DA and CapDev resolutions.
    for source_name in technology_folders_by_source:
        exported_timeseries_by_source[source_name] = {}
        exported_flh_by_source[source_name] = {}

        if source_name == "wind":
            timeseries_inc_name = "WND_VAR_T"
            flh_inc_name = "WNDFLH"
        elif source_name == "solar":
            timeseries_inc_name = "SOLE_VAR_T"
            flh_inc_name = "SOLEFLH"

        for series_variant in ["scaled", "raw"]:
            exported_timeseries_by_source[source_name][series_variant] = []
            exported_flh_by_source[source_name][series_variant] = []
            # Load and combine the time series data for each technology folder corresponding to the current energy source (wind/solar) and type (scaled/raw),
            technology_dfs = []
            for technology_folder in technology_folders_by_source[source_name]:
                technology_dfs.append(
                    combine_technology_timeseries_files(technology_folder, year_output_folder, series_variant)
                )

            combined_timeseries_df = pd.concat(technology_dfs, axis=1)
            combined_flh_series = (combined_timeseries_df.mean().to_frame() * len(combined_timeseries_df))[0]
            # Create a time mapping DataFrame for Balmorel, which will be used to align the time series data with the expected time format in 
            # Balmorel. 
            time_mapping_df = create_balmorel_time_mapping()
            if len(combined_timeseries_df) > len(time_mapping_df):
                combined_timeseries_df = combined_timeseries_df[: len(time_mapping_df)]
            time_mapping_df.index = combined_timeseries_df.index

            combined_timeseries_df.index = time_mapping_df.DA_time
            combined_timeseries_df.rename_axis(None, axis="index", inplace=True)
            # For wind, add the existing RG2 and RG3 columns by copying the existing RG1 data, since Balmorel expects these to be present for
            # the existing technology.
            combined_timeseries_df = add_WND_VAR_T_Existing_RG2_RG3(combined_timeseries_df)

            # Create the .inc file for the time series data in the DA resolution, using the 
            # combined and formatted DataFrame of time series data for the current energy source and type (scaled/raw).
            da_output_folder = os.path.join(year_output_folder, "to_balmorel", "DA", series_variant)
            create_SSS_TTT_AAA_inc(combined_timeseries_df, timeseries_inc_name, da_output_folder)

            combined_flh_series.rename_axis(None, axis="index", inplace=True)
            combined_flh_series = add_FLH_existing_RG2_RG3(combined_flh_series)
            # Create the .inc file for the full-load hours in the DA resolution, using the combined and formatted Series of full-load hours 
            # for the current energy source and type (scaled/raw).
            create_AAA_inc(combined_flh_series, flh_inc_name, da_output_folder)
            # Compute the capacity development time series for the CapDev resolution, using the combined time series data and the time mapping DataFrame,
            capdev_timeseries_df = compute_capdev_timeseries(
                balmorel_config.capdev_timesteps_to_keep.as_legacy_dict(),
                combined_timeseries_df,
                time_mapping_df,
                source=source_name
            )
            capdev_flh_series = (capdev_timeseries_df.mean().to_frame() * len(combined_timeseries_df))[0]

            if series_variant == "scaled":
                capdev_output_folder = os.path.join(year_output_folder, "to_balmorel", "CapDev")
                create_SSS_TTT_AAA_inc(capdev_timeseries_df, timeseries_inc_name, capdev_output_folder)
                create_AAA_inc(capdev_flh_series, flh_inc_name, capdev_output_folder)

            exported_timeseries_by_source[source_name][series_variant].append(combined_timeseries_df)
            exported_flh_by_source[source_name][series_variant].append(combined_flh_series)

    time_mapping_df.to_csv(os.path.join(year_output_folder, "to_balmorel", "balmorel_time_translation.csv"))

    return exported_timeseries_by_source, exported_flh_by_source

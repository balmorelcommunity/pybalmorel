"""
Functions for reading CorRES VRE output files and converting them to
Balmorel inputs (xlsx and Balmorel .inc files).

Handles wind (onshore, offshore bottom-fixed, offshore floating, existing)
and solar (rooftop PV, utility-scale PV with/without tracking) technologies.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""


import os
import pandas as pd
from pathlib import Path
import fnmatch
from pprint import pformat
import logging

import numpy as np

from .auxiliary_functions import (
    create_directory_if_needed,
    filter_timeseries_by_dates,
    align_timeseries_to_first_monday,
    scale_timeseries_to_full_distribution,
)
from .config_models import WeatherYearConfig


def save_log(config: WeatherYearConfig, output_folder: str) -> None:
    """Save the configuration details to a log file in the output folder for traceability.
     Args:
        config: The WeatherYearConfig object containing the configuration details.
        output_folder: The folder where the log file will be saved.
    """
    log_filename = os.path.join(output_folder, 'logfile.log')
    logger = logging.getLogger()
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    logging.info("Config file content:")
    logging.info("\n%s", pformat(config))




def extract_technology_folders(path :str) -> list[str]:
    """Get technology folders from a CorRES results directory based on expected naming patterns.
     Args:
        path: The path to the CorRES results directory.
     Returns:
        A list of technology folder names.
    """
    contents = os.listdir(path)
    if "Future_Onshore" in path or "Future_Offshore" in path:
        folders = [item for item in contents
                   if os.path.isdir(os.path.join(path, item)) and "SP" in item and "RG" in item]
    elif "Existing" in path:
        folders = [item for item in contents
                   if os.path.isdir(os.path.join(path, item)) and ("Onshore" in item or "Offshore" in item)]
    elif "PV" in path:
        folders = [item for item in contents
                   if os.path.isdir(os.path.join(path, item)) and "PV" in item and "RG" in item]
    return folders


def generate_output_filename_for_technology(f_name: str, tech: str, run_folder: str) -> str:
    """Generate a standardized file name for output files based on technology and source type.
     Args:
        f_name: The type of file to generate the name for (e.g., "P" for power, "WS" for wind speed).
        tech: The technology name.
        run_folder: The folder where the run is located.
     Returns:
        The standardized file name.
    """

    if "Onshore_2020"== tech  :
         new_file_name={"P": "Onshore_Existing",
                "WS": "Wind_speed/Onshore_Existing_WindSpeed"}
    elif ("Offshore_2020"== tech):
        new_file_name={"P": "Offshore_Existing",
                "WS": "Wind_speed/Offshore_Existing_WindSpeed"}

    
    elif "PV" in  run_folder:
        new_file_name={"P": tech,
                "DNI": "DNI/" + tech + "_DNI"}
    
    elif "Future" in run_folder :
        new_file_name={"P": tech.replace("Onshore_","").replace("Offshore_",""),
                "WS": "Wind_speed/" + tech + "_WindSpeed"}
    
    return new_file_name[f_name]
def compute_capacity_factor_and_flh(df: pd.DataFrame, tech: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate Capacity Factor (CF) and Full Load Hours (FLH) for a given technology based on its time series data.
     Args:
        df: The DataFrame containing the time series data for the technology.
        tech: The technology name, used for labeling the output DataFrames.
     Returns:
        A tuple containing two DataFrames: CF (Capacity Factor) and FLH (Full Load Hours).
    """
    #tech_sub_name=tech.replace("Offshore_","").replace("Onshore_","").replace("PV_","")
    CF=df.mean().to_frame()
    CF.columns=[tech]
    FLH= CF * len(df)
    
    return CF,FLH


    
def process_timeseries_with_scaling(df: pd.DataFrame, start_date: str, end_date: str, source: str, fix_monday: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply necessary treatments to the time series data, including filtering by date range, fixing the first Monday if needed, and scaling the data to have the same mean as the full time series.
     Args:
        df: The original DataFrame containing the time series data.
        start_date: The start date for filtering the time series (in 'YYYY-MM-DD' format).
        end_date: The end date for filtering the time series (in 'YYYY-MM-DD' format).
        source: The source type (e.g., "wind" or "solar") to determine specific treatments.
        fix_monday: A boolean indicating whether to fix the first Monday in the time series if it is missing.
    Returns:
        A tuple containing three DataFrames: the original full time series, the cut time series based on the date range, and the scaled time series.
    """

    if source == "solar":
        df[df < 0] = 0

    # CorRES CSV indices are read as strings and must be normalized before year filtering.
    df.index = pd.to_datetime(df.index)
    
    df_cut=filter_timeseries_by_dates(df,start_date,end_date)
    if fix_monday:
        df_cut= align_timeseries_to_first_monday(df,df_cut,start_date)

    
    df_scaled=scale_timeseries_to_full_distribution(df,df_cut)
    
    

    
    return df, df_cut,df_scaled




def is_wind_tech_enabled(run_folder: str, tech: str, config: WeatherYearConfig) -> bool:
    """Determine whether a given wind technology should be read based on the configuration settings.
     Args:
        run_folder: The folder where the run is located, used to determine the source type (e.g., "Existing", "Future_Onshore", "Future_Offshore").
        tech: The technology name, used for matching against the configuration settings.
        config: The WeatherYearConfig object containing the configuration details, including which technologies and regions to keep.
    Returns:
        A boolean indicating whether the technology should be read (True) or skipped (False).
        """
    turbine_to_keep = [turbine.replace("-", "_").replace("HH", "") for turbine in config.turbine_to_keep]

    if Path(run_folder).name not in config.tech_to_keep:
        return False

    if "Future_Onshore" in run_folder or "Future_Offshore" in run_folder:
        found_turbine = next((t for t in turbine_to_keep if fnmatch.fnmatch(str(tech), f"*{t}*")), None)
        found_rg = next((rg for rg in config.rg_to_keep[Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
        return bool(found_turbine and found_rg)

    return True

def is_solar_tech_enabled(run_folder: str, tech: str, config: WeatherYearConfig) -> bool:
    """Determine whether a given solar technology should be read based on the configuration settings.
     Args:
        run_folder: The folder where the run is located, used to determine the source type (e.g., "PV").
        tech: The technology name, used for matching against the configuration settings.
        config: The WeatherYearConfig object containing the configuration details, including which technologies and regions to keep.
    Returns:
        A boolean indicating whether the technology should be read (True) or skipped (False).
    """
    found_rg = next((rg for rg in config.rg_to_keep[Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
    return Path(run_folder).name in config.tech_to_keep and bool(found_rg)


def export_timeseries_to_xlsx(config_fn, start_date, output_folder, end_date=False, fix_monday=True):
    create_directory_if_needed(output_folder)
    config = WeatherYearConfig.from_file(config_fn)

    save_log(config, output_folder)

    output_folder = os.path.join(output_folder, str(start_date))

    if not end_date:
        end_date = start_date

    for source in ["wind", "solar"]:
        for run_folder in config.corres_results[source]:
            folder_name = os.path.basename(Path(run_folder))

            if "Existing" in folder_name or "Future" in folder_name:
                files_names = ["P"]
            elif "CSP" in folder_name:
                files_names = ["CSP_with_storage_dispatched", "CSP_with_excess", "DNI"]
            elif "PV" in folder_name:
                files_names = ["P"]

            techs = extract_technology_folders(run_folder)

            full_ts_stats = {"CF": [], "FLH": []}
            raw_ts_stats = {"CF": [], "FLH": []}
            scaled_ts_stats = {"CF": [], "FLH": []}
            
            for tech in techs:
                for f_name in files_names:
                    if source == "wind" and not is_wind_tech_enabled(run_folder, tech, config):
                        continue
                    if source == "solar" and not is_solar_tech_enabled(run_folder, tech, config):
                        continue

                    destination_path = os.path.join(output_folder, folder_name)
                    create_directory_if_needed(destination_path)
                    create_directory_if_needed(os.path.join(destination_path, "raw"))
                    create_directory_if_needed(os.path.join(destination_path, "scaled"))
                    create_directory_if_needed(os.path.join(destination_path, "stats"))

                    df = pd.read_csv(
                        os.path.join(run_folder, tech, "Results", f_name + ".csv"),
                        index_col="time",
                    )

                    if "Onshore" in run_folder or "PV" in run_folder:
                        df = df[df.columns.intersection(config.regions_to_keep.onshore)]
                    elif "Offshore" in run_folder:
                        df = df[df.columns.intersection(config.regions_to_keep.offshore)]
                    elif "Existing" in run_folder:
                        df = df[df.columns.intersection(
                            config.regions_to_keep.onshore + config.regions_to_keep.offshore
                        )]

                    df, df_cut, df_scaled = process_timeseries_with_scaling(df, start_date, end_date, source, fix_monday)

                    file_base = generate_output_filename_for_technology(f_name, tech, folder_name)
                    df_cut.to_excel(os.path.join(destination_path, "raw", file_base + "_raw.xlsx"))
                    df_scaled.to_excel(os.path.join(destination_path, "scaled", file_base + "_scaled.xlsx"))

                    CF_full, FLH_full = compute_capacity_factor_and_flh(df, tech)
                    full_ts_stats["CF"].append(CF_full)
                    full_ts_stats["FLH"].append(FLH_full)

                    CF_raw, FLH_raw = compute_capacity_factor_and_flh(df_cut, tech)
                    raw_ts_stats["CF"].append(CF_raw)
                    raw_ts_stats["FLH"].append(FLH_raw)

                    CF_scaled, FLH_scaled = compute_capacity_factor_and_flh(df_scaled, tech)
                    scaled_ts_stats["CF"].append(CF_scaled)
                    scaled_ts_stats["FLH"].append(FLH_scaled)
            
                    stats_path = os.path.join(destination_path, "stats")
                    if "Existing" not in run_folder:
                        pd.concat(full_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_full_ts.xlsx"))
                        pd.concat(full_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_full_ts.xlsx"))
                        pd.concat(raw_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_raw_ts.xlsx"))
                        pd.concat(raw_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_raw_ts.xlsx"))
                        pd.concat(scaled_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_scaled_ts.xlsx"))
                        pd.concat(scaled_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_scaled_ts.xlsx"))
                    else:
                        def _write_per_sheet(df_combined, filename):
                            with pd.ExcelWriter(os.path.join(stats_path, filename), engine='xlsxwriter') as writer:
                                for col in df_combined.columns:
                                    df_combined[col].dropna().to_excel(writer, sheet_name=col, index=True)

                        _write_per_sheet(pd.concat(full_ts_stats["CF"], axis=1), "CF_full_ts.xlsx")
                        _write_per_sheet(pd.concat(full_ts_stats["FLH"], axis=1), "FLH_full_ts.xlsx")
                        _write_per_sheet(pd.concat(raw_ts_stats["CF"], axis=1), "CF_raw_ts.xlsx")
                        _write_per_sheet(pd.concat(raw_ts_stats["FLH"], axis=1), "FLH_raw_ts.xlsx")
                        _write_per_sheet(pd.concat(scaled_ts_stats["CF"], axis=1), "CF_scaled_ts.xlsx")
                        _write_per_sheet(pd.concat(scaled_ts_stats["FLH"], axis=1), "FLH_scaled_ts.xlsx")
                           

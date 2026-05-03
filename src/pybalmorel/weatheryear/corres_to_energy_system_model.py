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
    process_timeseries_with_scaling
)
from .config_models import WeatherYearConfig
from .exceptions import MissingRequiredColumnsError, EmptyMergeResultError


logger = logging.getLogger(__name__)


def save_log(config: WeatherYearConfig, output_folder: str) -> None:
    """Save the configuration details to a log file in the output folder for traceability.
     Args:
        config: The WeatherYearConfig object containing the configuration details.
        output_folder: The folder where the log file will be saved.
    """
    log_filename = os.path.join(output_folder, 'logfile.log')
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    config_logger = logging.getLogger(f"{__name__}.config")
    config_logger.setLevel(logging.INFO)
    config_logger.propagate = False
    config_logger.addHandler(file_handler)

    try:
        config_logger.info("Config file content:")
        config_logger.info("\n%s", pformat(config))
    finally:
        config_logger.removeHandler(file_handler)
        file_handler.close()


def _require_columns(df: pd.DataFrame, required_columns: set[str], context: str) -> None:
    """Ensure required columns exist in a DataFrame before downstream processing."""
    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise MissingRequiredColumnsError(
            f"Missing required columns {missing} in {context}. "
            f"Available columns: {list(df.columns)}"
        )


def _source_file_names(folder_name: str) -> list[str]:
    """Return input result file stems to read for one CorRES run folder."""
    if "Existing" in folder_name or "Future" in folder_name:
        return ["P"]
    if "CSP" in folder_name:
        return ["CSP_with_storage_dispatched", "CSP_with_excess", "DNI"]
    if "PV" in folder_name:
        return ["P"]
    return ["P"]


def _select_region_columns(
    df: pd.DataFrame,
    run_folder: str,
    config: WeatherYearConfig,
) -> pd.DataFrame:
    """Return a filtered dataframe containing only configured Balmorel regions."""
    if "Onshore" in run_folder or "PV" in run_folder:
        selected_regions = config.regions_to_keep.onshore
    elif "Offshore" in run_folder:
        selected_regions = config.regions_to_keep.offshore
    elif "Existing" in run_folder:
        selected_regions = config.regions_to_keep.onshore + config.regions_to_keep.offshore
    else:
        selected_regions = list(df.columns)
    return df[df.columns.intersection(selected_regions)]


def _write_processed_timeseries(
    df_cut: pd.DataFrame,
    df_scaled: pd.DataFrame,
    destination_path: str,
    file_base: str,
) -> None:
    """Write raw and scaled time series for one processed technology file."""
    df_cut.to_excel(os.path.join(destination_path, "raw", file_base + "_raw.xlsx"))
    df_scaled.to_excel(os.path.join(destination_path, "scaled", file_base + "_scaled.xlsx"))


def _write_stats_excel(
    stats_path: str,
    run_folder: str,
    full_ts_stats: dict[str, list[pd.DataFrame]],
    raw_ts_stats: dict[str, list[pd.DataFrame]],
    scaled_ts_stats: dict[str, list[pd.DataFrame]],
) -> None:
    """Persist CF/FLH stats with existing and future run-specific formatting."""

    def _write_per_sheet(df_combined: pd.DataFrame, filename: str) -> None:
        with pd.ExcelWriter(os.path.join(stats_path, filename), engine="xlsxwriter") as writer:
            for col in df_combined.columns:
                df_combined[col].dropna().to_excel(writer, sheet_name=col, index=True)

    if "Existing" not in run_folder:
        pd.concat(full_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_full_ts.xlsx"))
        pd.concat(full_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_full_ts.xlsx"))
        pd.concat(raw_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_raw_ts.xlsx"))
        pd.concat(raw_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_raw_ts.xlsx"))
        pd.concat(scaled_ts_stats["CF"], axis=1).to_excel(os.path.join(stats_path, "CF_scaled_ts.xlsx"))
        pd.concat(scaled_ts_stats["FLH"], axis=1).to_excel(os.path.join(stats_path, "FLH_scaled_ts.xlsx"))
        return

    _write_per_sheet(pd.concat(full_ts_stats["CF"], axis=1), "CF_full_ts.xlsx")
    _write_per_sheet(pd.concat(full_ts_stats["FLH"], axis=1), "FLH_full_ts.xlsx")
    _write_per_sheet(pd.concat(raw_ts_stats["CF"], axis=1), "CF_raw_ts.xlsx")
    _write_per_sheet(pd.concat(raw_ts_stats["FLH"], axis=1), "FLH_raw_ts.xlsx")
    _write_per_sheet(pd.concat(scaled_ts_stats["CF"], axis=1), "CF_scaled_ts.xlsx")
    _write_per_sheet(pd.concat(scaled_ts_stats["FLH"], axis=1), "FLH_scaled_ts.xlsx")




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
    else:
        folders = []
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


def export_timeseries_to_xlsx(
    config_fn: str,
    start_date: str,
    output_folder: str,
    end_date: str | bool = False,
    fix_monday: bool = True,
) -> None:
    """Main function to read CorRES output files, process the time series data, and export it to Excel files for use in Balmorel.
     Args:
        config_fn: The file path to the configuration file (e.g., YAML) containing settings for which technologies and regions to keep, as well as the paths to the CorRES results.
        start_date: The start date for filtering the time series (in 'YYYY-MM-DD' format).
        output_folder: The folder where the processed Excel files will be saved.
        end_date: The end date for filtering the time series (in 'YYYY-MM-DD' format). If False, no end date filtering is applied.
        fix_monday: A boolean indicating whether to fix the first Monday in the time series if it is missing. Defaults to True.
    Returns:
        None. The function saves the processed time series data to Excel files in the specified output folder.
     Raises:
        MissingRequiredColumnsError: If required columns are missing from the input CSV files.
        EmptyMergeResultError: If no region columns remain after filtering for the configured regions.
    """
    # Create the output directory if it doesn't exist
    create_directory_if_needed(output_folder)

    # Load the configuration from the specified file
    weather_config = WeatherYearConfig.from_file(config_fn)
    
    # Save the configuration to a log file in the output folder for traceability
    save_log(weather_config, output_folder)

    # Append the start date to the output folder path to create a subfolder for this specific weather year processing
    year_output_folder = os.path.join(output_folder, str(start_date))

    if not end_date:
        end_date = start_date
    
    # Iterate over the configured sources (wind and solar) and their corresponding run folders to process the time series data for each technology.
    for source_name in ["wind", "solar"]:
        for run_folder in weather_config.corres_results[source_name]:
            folder_name = os.path.basename(Path(run_folder))
            # Determine which input file names to read based on the folder name and source type (e.g., "P" for power, "WS" for wind speed, "DNI" for solar direct normal irradiance).
            input_file_names = _source_file_names(folder_name)
            # Extract the technology folders from the CorRES results directory based on expected naming patterns (e.g., "Onshore", "Offshore", "PV", "SP", "RG").
            technology_folders = extract_technology_folders(run_folder)

            full_ts_stats = {"CF": [], "FLH": []}
            raw_ts_stats = {"CF": [], "FLH": []}
            scaled_ts_stats = {"CF": [], "FLH": []}
            # Loop through each technology folder and input file name, applying the necessary filters based on the configuration settings for which technologies and regions to keep. Process the time series data, 
            # compute the capacity factor and full load hours, and save the results to Excel files in the appropriate subfolders (raw, scaled, stats) within the year-specific output folder.
            for technology_name in technology_folders:
                for input_file_stem in input_file_names:
                    if source_name == "wind" and not is_wind_tech_enabled(run_folder, technology_name, weather_config):
                        continue
                    if source_name == "solar" and not is_solar_tech_enabled(run_folder, technology_name, weather_config):
                        continue
                    
                    # Ensure output directories exist for this run folder.
                    destination_folder = os.path.join(year_output_folder, folder_name)
                    create_directory_if_needed(destination_folder)
                    for subfolder_name in ("raw", "scaled", "stats"):
                        create_directory_if_needed(os.path.join(destination_folder, subfolder_name))
                    
                    # Read the time series data from the corresponding CSV file for this technology and input type, ensuring that the required "time" column is present. Set the "time" column as the index of the DataFrame.
                    csv_path = os.path.join(run_folder, technology_name, "Results", input_file_stem + ".csv")
                    time_series_df = pd.read_csv(csv_path)
                    _require_columns(time_series_df, {"time"}, context=f"CSV '{csv_path}'")
                    time_series_df = time_series_df.set_index("time")

                    time_series_df = _select_region_columns(time_series_df, run_folder, weather_config)
                    if time_series_df.columns.empty:
                        raise EmptyMergeResultError(
                            "No region columns remain after filtering configured regions for "
                            f"technology '{technology_name}' in run folder '{run_folder}'."
                        )
                
                    full_series_df, raw_window_df, scaled_window_df = process_timeseries_with_scaling(
                        time_series_df,
                        start_date,
                        end_date,
                        source_name,
                        fix_monday,
                    )

                    output_file_base = generate_output_filename_for_technology(input_file_stem, technology_name, folder_name)
                    _write_processed_timeseries(raw_window_df, scaled_window_df, destination_folder, output_file_base)

                    full_cf_df, full_flh_df = compute_capacity_factor_and_flh(full_series_df, technology_name)
                    full_ts_stats["CF"].append(full_cf_df)
                    full_ts_stats["FLH"].append(full_flh_df)

                    raw_cf_df, raw_flh_df = compute_capacity_factor_and_flh(raw_window_df, technology_name)
                    raw_ts_stats["CF"].append(raw_cf_df)
                    raw_ts_stats["FLH"].append(raw_flh_df)

                    scaled_cf_df, scaled_flh_df = compute_capacity_factor_and_flh(scaled_window_df, technology_name)
                    scaled_ts_stats["CF"].append(scaled_cf_df)
                    scaled_ts_stats["FLH"].append(scaled_flh_df)
            
                    stats_folder = os.path.join(destination_folder, "stats")
                    _write_stats_excel(
                        stats_path=stats_folder,
                        run_folder=run_folder,
                        full_ts_stats=full_ts_stats,
                        raw_ts_stats=raw_ts_stats,
                        scaled_ts_stats=scaled_ts_stats,
                    )
                           

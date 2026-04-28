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
import numpy as np
from datetime import datetime, timedelta
import yaml
import fnmatch
from pprint import pformat
import logging

from .auxiliary_functions import (
    check_if_dir_exists,
    cut_timeseries,
    fix_first_monday,
    scale_data_to_same_mean_with_full_time_series,
)


def save_log(config, output_folder):
    """Set up file-only logging and write the active config to the log."""
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




def get_tech_folders(path):
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


def get_file_name(f_name,tech,run_folder):

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
def calculate_CF_FLH(df,tech):
    tech_sub_name=tech.replace("Offshore_","").replace("Onshore_","").replace("PV_","")
    CF=df.mean().to_frame()
    CF.columns=[tech]
    FLH= CF * len(df)
    
    return CF,FLH


    
def treat_timeseries(df,start_date,end_date,source,fix_monday):


    if source == "solar":
        df[df < 0] = 0

    # CorRES CSV indices are read as strings and must be normalized before year filtering.
    df.index = pd.to_datetime(df.index)
    
    df_cut=cut_timeseries(df,start_date,end_date)
    if fix_monday:
        df_cut= fix_first_monday(df,df_cut,start_date)

    
    df_scaled=scale_data_to_same_mean_with_full_time_series(df,df_cut)
    
    

    
    return df, df_cut,df_scaled




def check_wind_tech_to_read(run_folder, tech, config):
    turbine_to_keep = [turbine.replace("-", "_").replace("HH", "") for turbine in config["turbine_to_keep"]]

    if Path(run_folder).name not in config["tech_to_keep"]:
        return False

    if "Future_Onshore" in run_folder or "Future_Offshore" in run_folder:
        found_turbine = next((t for t in turbine_to_keep if fnmatch.fnmatch(str(tech), f"*{t}*")), None)
        found_rg = next((rg for rg in config["RGs_to_keep"][Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
        return bool(found_turbine and found_rg)

    return True

def check_solar_tech_to_read(run_folder, tech, config):
    found_rg = next((rg for rg in config["RGs_to_keep"][Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
    return Path(run_folder).name in config["tech_to_keep"] and bool(found_rg)


def get_energy_system_xlsx(config_fn, start_date, output_folder, end_date=False, fix_monday=True):
    check_if_dir_exists(output_folder)
    with open(config_fn) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    save_log(config, output_folder)

    output_folder = os.path.join(output_folder, str(start_date))

    if not end_date:
        end_date = start_date

    for source in ["wind", "solar"]:
        for run_folder in config["corres_results"][source]:
            folder_name = os.path.basename(Path(run_folder))

            if "Existing" in folder_name or "Future" in folder_name:
                files_names = ["P"]
            elif "CSP" in folder_name:
                files_names = ["CSP_with_storage_dispatched", "CSP_with_excess", "DNI"]
            elif "PV" in folder_name:
                files_names = ["P"]

            techs = get_tech_folders(run_folder)

            full_ts_stats = {"CF": [], "FLH": []}
            raw_ts_stats = {"CF": [], "FLH": []}
            scaled_ts_stats = {"CF": [], "FLH": []}
            
            for tech in techs:
                for f_name in files_names:
                    if source == "wind" and not check_wind_tech_to_read(run_folder, tech, config):
                        continue
                    if source == "solar" and not check_solar_tech_to_read(run_folder, tech, config):
                        continue

                    destination_path = os.path.join(output_folder, folder_name)
                    check_if_dir_exists(destination_path)
                    check_if_dir_exists(os.path.join(destination_path, "raw"))
                    check_if_dir_exists(os.path.join(destination_path, "scaled"))
                    check_if_dir_exists(os.path.join(destination_path, "stats"))

                    df = pd.read_csv(
                        os.path.join(run_folder, tech, "Results", f_name + ".csv"),
                        index_col="time",
                    )

                    if "Onshore" in run_folder or "PV" in run_folder:
                        df = df[df.columns.intersection(config["Regions_to_keep"]["onshore"])]
                    elif "Offshore" in run_folder:
                        df = df[df.columns.intersection(config["Regions_to_keep"]["offshore"])]
                    elif "Existing" in run_folder:
                        df = df[df.columns.intersection(
                            config["Regions_to_keep"]["onshore"] + config["Regions_to_keep"]["offshore"]
                        )]

                    df, df_cut, df_scaled = treat_timeseries(df, start_date, end_date, source, fix_monday)

                    file_base = get_file_name(f_name, tech, folder_name)
                    df_cut.to_excel(os.path.join(destination_path, "raw", file_base + "_raw.xlsx"))
                    df_scaled.to_excel(os.path.join(destination_path, "scaled", file_base + "_scaled.xlsx"))

                    CF_full, FLH_full = calculate_CF_FLH(df, tech)
                    full_ts_stats["CF"].append(CF_full)
                    full_ts_stats["FLH"].append(FLH_full)

                    CF_raw, FLH_raw = calculate_CF_FLH(df_cut, tech)
                    raw_ts_stats["CF"].append(CF_raw)
                    raw_ts_stats["FLH"].append(FLH_raw)

                    CF_scaled, FLH_scaled = calculate_CF_FLH(df_scaled, tech)
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
                           

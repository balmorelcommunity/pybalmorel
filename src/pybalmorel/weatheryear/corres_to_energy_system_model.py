"""
TITLE

Description


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

from .auxiliary_functions import check_if_dir_exists,scale_data_to_same_mean_with_full_time_series


def save_log(config, output_folder):
    log_filename = output_folder + '/logfile.log'

    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,  
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Remove the StreamHandler from the logger (which outputs to terminal)
    logging.getLogger().handlers.clear()

    # Add only file handler
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)

    # Now only logs to the file, not to the terminal
    logging.info("Config file content:")
    logging.info("\n%s", pformat(config))




def get_tech_folders(path):

    contents = os.listdir(path)
    if ("Future_Onshore" in path) |  ("Future_Offshore" in path):
        folders = [item for item in contents if ( os.path.isdir(os.path.join(path, item)) and ("SP" in item) and ("RG" in item))]
    elif ("Existing" in path): 
        folders = [item for item in contents if ( os.path.isdir(os.path.join(path, item)) and ( ("Onshore" in item) or ("Offshore" in item) ) )]
    elif ("PV" in path): 
        folders = [item for item in contents if ( os.path.isdir(os.path.join(path, item)) and ("PV" in item) and ("RG" in item))]
        
    
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


def fix_first_monday(df,df_cut,start_date):
    
    t = np.arange(datetime(int(start_date),1,1), datetime(int(start_date),12,31), timedelta(hours=1)).astype(datetime)
    
    first_monday = t[np.array([date.weekday() for date in t]) == 0][0]
    
    df_cut= df_cut.loc[df_cut.index>=first_monday]

    if len(df_cut)<8736:
        to_add=df.loc[  (df.index.year==(start_date) + 1) ][:8736 - len(df_cut)]
        df_cut=pd.concat([df_cut,to_add])

    return df_cut
    
def cut_timeseries(df,start_date,end_date):
  
   df.index = pd.to_datetime(df.index)
    
   mask=  (df.index.year >= start_date) & (df.index.year <= end_date)
   df = df.loc[mask]

   return df
    

def calculate_CF_FLH(df,tech):
    tech_sub_name=tech.replace("Offshore_","").replace("Onshore_","").replace("PV_","")
    CF=df.mean().to_frame()
    CF.columns=[tech]
    FLH= CF * len(df)
    
    return CF,FLH


    
def treat_timeseries(df,start_date,end_date,source,fix_monday):


    if source == "solar":
        df[df < 0] = 0
    
    df_cut=cut_timeseries(df,start_date,end_date)
    if fix_monday:
        df_cut= fix_first_monday(df,df_cut,start_date)

    
    df_scaled=scale_data_to_same_mean_with_full_time_series(df,df_cut)
    
    

    
    return df, df_cut,df_scaled




def check_wind_tech_to_read(run_folder,tech,config):

    turbine_to_keep = [turbine.replace("-", "_").replace("HH", "") for turbine in config["turbine_to_keep"] ]
    
    if Path(run_folder).name in config["tech_to_keep"]:

        if  ("Future_Onshore" in run_folder) |  ("Future_Offshore" in run_folder):
            found_turbine = next((turbine for turbine in turbine_to_keep if fnmatch.fnmatch(str(tech), f"*{turbine}*")), None)
            found_rg = next((rg for rg in config["RGs_to_keep"][Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
            
            if found_turbine and found_rg:
                return True
            else :
                return False
        else:
            return True
    else:
        return False

def check_solar_tech_to_read(run_folder,tech,config):
    
    found_rg = next((rg for rg in config["RGs_to_keep"][Path(run_folder).name] if fnmatch.fnmatch(str(tech), f"*{rg}*")), None)
    
    if (Path(run_folder).name in config["tech_to_keep"]) and found_rg:
         return True
    else: 
         return False


def get_energy_system_xlsx(config_fn,start_date,output_folder,end_date=False, fix_monday=True):
    #print("Extracting Corres results and create xlsx")
    check_if_dir_exists(output_folder)
    with open(config_fn) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
        
    save_log(config,output_folder)
    
    output_folder=output_folder + "/" + str(start_date)
    
    

    
    
    if not end_date: 
        end_date=start_date
    
    

    for source in ["wind","solar"]: 
        for run_folder in config["corres_results"][source]:
            
        
            if  ("Existing" in os.path.basename(Path(run_folder))) | ("Future" in os.path.basename(Path(run_folder))):
                    files_names=["P"]
            elif "CSP" in os.path.basename(Path(run_folder)):
                    files_names=["CSP_with_storage_dispatched","CSP_with_excess","DNI"]
            elif "PV" in os.path.basename(Path(run_folder)):
                    files_names=["P"]

            techs=get_tech_folders(run_folder)


            full_ts_stats={"CF":[], "FLH":[]}
            raw_ts_stats={"CF":[], "FLH":[]}
            scaled_ts_stats={"CF":[], "FLH":[]}
            
            for tech in techs:
                for f_name in files_names:
                    if (source=="wind") and not check_wind_tech_to_read(run_folder,tech,config):
                        continue
                    if (source=="solar") and not check_solar_tech_to_read(run_folder,tech,config):
                        continue
                    
                    destination_path= output_folder +"/"  +  os.path.basename(Path(run_folder))
                    check_if_dir_exists(destination_path)
                    check_if_dir_exists(destination_path + "/" + "raw")
                    check_if_dir_exists(destination_path + "/" + "scaled")
                    check_if_dir_exists(destination_path + "/" + "stats")
                    
                    df=pd.read_csv(run_folder + "/" + tech +  "/Results/" + f_name + ".csv", index_col= "time")

                    if ("Onshore" in run_folder) | ("PV" in run_folder):
                        df = df[df.columns.intersection(config["Regions_to_keep"]["onshore"])]
                    elif ("Offshore" in run_folder):
                        df = df[df.columns.intersection(config["Regions_to_keep"]["offshore"])]
                    elif ("Existing" in run_folder):
                        df = df[df.columns.intersection(config["Regions_to_keep"]["onshore"] + config["Regions_to_keep"]["offshore"])]
                    
                    df, df_cut,df_scaled=treat_timeseries(df,start_date,end_date,source,fix_monday)

        
                    df_cut.to_excel(destination_path  + "/raw/" +  get_file_name(f_name,tech,os.path.basename(Path(run_folder))) + "_raw.xlsx")
                    df_scaled.to_excel(destination_path  + "/scaled/" +  get_file_name(f_name,tech,os.path.basename(Path(run_folder))) + "_scaled.xlsx")
        
                    CF_full,FLH_full=calculate_CF_FLH(df,tech)
                    full_ts_stats["CF"].append(CF_full)
                    full_ts_stats["FLH"].append(FLH_full)
    
                    
                    CF_raw,FLH_raw=calculate_CF_FLH(df_cut,tech)
                    raw_ts_stats["CF"].append(CF_raw)
                    raw_ts_stats["FLH"].append(FLH_raw)
                    
                    CF_scaled,FLH_scaled=calculate_CF_FLH(df_scaled,tech)
                    scaled_ts_stats["CF"].append(CF_scaled)
                    scaled_ts_stats["FLH"].append(FLH_scaled)
            
                    if "Existing" not in run_folder:
                        pd.concat(full_ts_stats["CF"],axis=1).to_excel( destination_path  + "/stats/"  + "CF_full_ts.xlsx")
                        pd.concat(full_ts_stats["FLH"],axis=1).to_excel( destination_path  + "/stats/"  + "FLH_full_ts.xlsx")
        
                        pd.concat(raw_ts_stats["CF"],axis=1).to_excel( destination_path  + "/stats/"  + "CF_raw_ts.xlsx")
                        pd.concat(raw_ts_stats["FLH"],axis=1).to_excel( destination_path  + "/stats/"  + "FLH_raw_ts.xlsx")
        
                        pd.concat(scaled_ts_stats["CF"],axis=1).to_excel( destination_path  + "/stats/"  + "CF_scaled_ts.xlsx")
                        pd.concat(scaled_ts_stats["FLH"],axis=1).to_excel( destination_path  + "/stats/"  + "FLH_scaled_ts.xlsx")
                    else:
                        a=pd.concat(full_ts_stats["CF"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "CF_full_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in a.keys():
                                a[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
                                
                        b=pd.concat(full_ts_stats["FLH"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "FLH_full_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in b.keys():
                                b[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
        
                        c=pd.concat(raw_ts_stats["CF"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "CF_raw_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in c.keys():
                                c[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
                                
                        d=pd.concat(raw_ts_stats["FLH"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "FLH_raw_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in d.keys():
                                d[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
        
                        e=pd.concat(scaled_ts_stats["CF"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "CF_scaled_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in e.keys():
                                e[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
                                
                        f=pd.concat(scaled_ts_stats["FLH"],axis=1)
                        with pd.ExcelWriter(destination_path  + "/stats/"  + "FLH_scaled_ts.xlsx", engine='xlsxwriter') as writer:
                            for iter1 in f.keys():
                                f[iter1].dropna().to_excel(writer, sheet_name=iter1, index=True)
                           

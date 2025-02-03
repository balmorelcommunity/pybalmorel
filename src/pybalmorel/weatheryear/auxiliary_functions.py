"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""



from pathlib import Path
import pandas as pd
import numpy as np

def check_if_dir_exists(destination_path):
    Path(destination_path).mkdir(parents=True, exist_ok=True) 



def get_onoff_source_from_folder(folder):
    #folder_dictionary={"Future_Onshore":  }
    
    if "Future_Onshore" in folder:
        onoff="Onshore"
        source="wind"
    elif "Future_Offshore_floating" in folder:
        onoff="Offshore_floating"
        source="wind"
    elif "Future_Offshore_bottom_fixed" in folder:
         onoff="Offshore_bottom_fixed"
         source="wind"        
    elif "Existing_ERA5_GWA2" in folder:
        onoff="Existing"
        source="wind"
    elif "PV_Rooftop" in folder:
        onoff="PV_Rooftop"
        source="solar"
    elif "PV_Utility_scale_no_tracking" in folder:
        onoff="PV_Utility_scale_no_tracking"
        source="solar"
    elif "PV_Utility_scale_tracking" in folder:
        onoff="PV_Utility_scale_tracking"
        source="solar"

    return onoff, source 



def get_CapDev_timesteps(config):
    
    s_values = config["CapDev_timesteps_to_keep"]['S'].strip(':[]').split(',')
    timesteps = [f'{s}.{t}' for s in s_values for t in config["CapDev_timesteps_to_keep"]['T']]
    #df = pd.DataFrame({'timesteps': timesteps})
    
    return timesteps



def scale_data_to_same_mean_with_full_time_series(df,df_cut):
    def ecdf(data):
        """ Compute ECDF for a one-dimensional array of measurements. """
        x = np.sort(data)
        n = x.size
        y = np.arange(1, n+1) / n
        return x, y
    
    # Define a function to compute the inverse ECDF (quantile function)
    def inverse_ecdf(data, quantiles):
        """ Compute the inverse ECDF (quantile function) for given quantiles. """
        x, y = ecdf(data)
        return np.interp(quantiles, y, x)
    
    

    df_scaled=pd.DataFrame()
    #df_scaled.index=df_cut.index
    for iter1 in df.keys():
        # Compute ECDF and the corresponding values
        _, u_f = ecdf(df[iter1])
        u_f = np.interp(df[iter1], _, u_f)
        
        _, u_sel_orig = ecdf(df_cut[iter1])
        u_sel_orig = np.interp(df_cut[iter1], _, u_sel_orig)
        
        # Compute the inverse ECDF for the scaled selection
        #df_scaled[iter1] = inverse_ecdf(df[iter1], u_sel_orig)
        new_data = pd.DataFrame(inverse_ecdf(df[iter1], u_sel_orig), columns=[iter1])
        df_scaled = pd.concat([df_scaled, new_data], axis=1)
    df_scaled.index=df_cut.index
    
    return df_scaled

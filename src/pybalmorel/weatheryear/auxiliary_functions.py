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

    df_scaled=pd.DataFrame(0.0, index=df_cut.index, columns=df_cut.columns)
    for iter1 in df.keys():
        mask_zero_df = df[iter1] == 0
        mask_zero_df_cut = df_cut[iter1] == 0
        # Compute ECDF and the corresponding values
        _, u_f = ecdf(df[iter1].loc[~mask_zero_df])
        u_f = np.interp(df[iter1].loc[~mask_zero_df], _, u_f)
        
        _, u_sel_orig = ecdf(df_cut[iter1].loc[~mask_zero_df_cut])
        u_sel_orig = np.interp(df_cut[iter1].loc[~mask_zero_df_cut], _, u_sel_orig)
        
        # Compute the inverse ECDF for the scaled selection
        df_scaled.loc[~mask_zero_df_cut,iter1] = inverse_ecdf(df[iter1].loc[~mask_zero_df], u_sel_orig)
    
    return df_scaled

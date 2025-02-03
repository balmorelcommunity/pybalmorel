from pathlib import Path
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta


def check_if_dir_exists(destination_path):
    Path(destination_path).mkdir(parents=True, exist_ok=True) 


def fix_first_monday(df,df_cut,start_date):
    
    t = np.arange(datetime(int(start_date),1,1), datetime(int(start_date),12,31), timedelta(hours=1)).astype(datetime)
    
    first_monday = t[np.array([date.weekday() for date in t]) == 0][0]
    
    df_cut= df_cut.loc[df_cut.index>=first_monday]

    if len(df_cut)<8736:
        to_add=df.loc[  (df.index.year==(start_date) + 1) ][:8736 - len(df_cut)]
        df_cut=pd.concat([df_cut,to_add])
    if len(df_cut)>8736:
        df_cut=df_cut[:8736]    

    return df_cut
    
    
    
def cut_timeseries(df,start_date,end_date):
  
   #df.index = pd.to_datetime(df.index)
    
   mask=  (df.index.year >= start_date) & (df.index.year <= end_date)
   df = df.loc[mask]

   return df


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







def treat_timeseries(df,start_date,end_date,fix_monday):


    
    df_cut=cut_timeseries(df,start_date,end_date)
    if fix_monday:
        df_cut= fix_first_monday(df,df_cut,start_date)

    
    df_scaled=scale_data_to_same_mean_with_full_time_series(df,df_cut)
    
    

    
    return df, df_cut,df_scaled



def create_time_column():

    
    list_s = [f"S{str(i).zfill(2)}" for i in range(1, 53)]
    list_t = [f"T{str(i).zfill(3)}" for i in range(1, 169)]
    time_periods = [f"{s}.{t}" for s in list_s for t in list_t]
    df = pd.DataFrame(time_periods, columns=[ "CapDev_time"])
        
   
    list_s = [f"S{str(i).zfill(3)}" for i in range(1, 365)]
    list_t = [f"T{str(i).zfill(2)}" for i in range(1, 25)]
    time_periods = [f"{s}.{t}" for s in list_s for t in list_t]   

    df["DA_time"]=time_periods
    
    return df 



def convert_to_list_df_new(df,name,user_name):
    #df = pd.DataFrame(data, index=index)
    
    # Iterate through DataFrame and build the desired output
    output = []
    output_df=pd.DataFrame()

    for idx in df.index:
            sss, ttt = idx.split('.')
            for rrr in df.columns:
                value = df.loc[idx, rrr]
                output.append(f"{name}('{rrr}', '{user_name}', '{sss}', '{ttt}') = {value};")

    output_df[name]=output
    return output_df



def convert_to_list_df_annual_correction(df,name,user_name):
    # DH(YYY,'DK1_Large','RESH') = DH(YYY,'DK1_Large','RESH')*1.2

    output = []
    output_df=pd.DataFrame()
  
    for rrr in df.index:
        value = df.loc[rrr]
        output.append(f"{name}( YYY, '{rrr}', '{user_name}') = {name}( YYY, '{rrr}', '{user_name}')*{value};")

    output_df[name]=output
    return output_df





def convert_to_list_df(df,name,user_group):

    output = []
    output_df=pd.DataFrame()
    
    if  (name=="DE_VAR_T") | (name=="DH_VAR_T") :
        for idx in df.index:
            sss, ttt = idx.split('.')
            for rrr in df.columns:
                value = df.loc[idx, rrr]
                output.append(f"{name}('{rrr}', '{user_group}', '{sss}', '{ttt}') = {value};")

    output_df[name]=output
    return output_df




def create_list_inc(df,name,filename,output_folder):
    with open(output_folder + "/" + filename + ".inc", "w") as the_file:
            the_file.write("*File created from weatheryear module")
            the_file.write("\n")      
            for item in df[name]:
                the_file.write(item +"\n" )

                


def calc_CapDev_timeseries(config,combined_scaled_dfs,df_t):
    
    CapDev_timesteps=get_CapDev_timesteps(config)
    
    df_t_cut=df_t[df_t.CapDev_time.isin(CapDev_timesteps)]
    
    
    filtered_df1 = combined_scaled_dfs[combined_scaled_dfs.index.isin(df_t_cut.DA_time)]
    
    combined_scaled_dfs.index=df_t.index
    filtered_df1.index=df_t_cut.index
    
    df_scaled=scale_data_to_same_mean_with_full_time_series(combined_scaled_dfs,filtered_df1)
    
    df_scaled.index=df_t_cut.CapDev_time

    return df_scaled




"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""


import os
import pandas as pd
import yaml


from .to_inc import create_SSS_TTT_AAA_inc,create_AAA_inc
from .auxiliary_functions import check_if_dir_exists,get_onoff_source_from_folder,get_CapDev_timesteps,scale_data_to_same_mean_with_full_time_series


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

def fix_wind_column_names_to_balmorel(df,tech_csv,onoff):
    
    if onoff=="Existing":
        if "Offshore" in tech_csv:
                onoff_suf="_OFF"
                tech=""
                rg="Existing_RG1"
        elif "Onshore" in tech_csv:
                onoff_suf="_ONS"
                tech=""
                rg="Existing_RG1"

    else:
        parts = tech_csv.split('_', 3)
        rg_dict={"RGA":"RG1", "RGB":"RG2", "RGC":"RG3"}
        
        tech= parts[0] + "-HH" + parts[1]
        rg=rg_dict[ parts[2]]
        
        if onoff=="Onshore":
            onoff_suf="_VRE-ONS"
        elif onoff=="Offshore_floating":
            onoff_suf="_VRE-OFF_floating"
        elif onoff=="Offshore_bottom_fixed":
            onoff_suf="_VRE-OFF_bottom_fixed"

    if onoff=="Existing":
        df.columns= df.columns +  onoff_suf + "_" + rg 
    else:
        df.columns= df.columns +  onoff_suf + "_" + tech + "_"  + rg 
    
    return df

def fix_WFLH_areas(df_cf,onoff):
    

    df_cf_melted = df_cf.reset_index().melt(id_vars='index', var_name='Column', value_name='Value')
    
    

    if onoff=="Offshore_bottom_fixed":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Offshore", "VRE-OFF_bottom_fixed")
    
    elif onoff=="Future_Offshore_floating":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Offshore", "OFF_VRE-OFF_floating")
    
    elif onoff=="Existing":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Existing", "Existing_RG1")
        

    elif  onoff=="Future_Onshore":
        df_cf_melted['Column'] = df_cf_melted['Column'].str.replace("Onshore", "VRE-ONS")
   
    
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['index'] + '_' + df_cf_melted['Column']

    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGA", "RG1")
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGB", "RG2")
    df_cf_melted['Index_Column_Combination'] = df_cf_melted['Index_Column_Combination'].str.replace("RGC", "RG3")
    
    df_cf_melted=df_cf_melted.set_index("Index_Column_Combination")["Value"]

    
    
    return df_cf_melted

            
def fix_solar_column_names_to_balmorel(df,tech_csv,onoff):

    
    
    if "RGA" in tech_csv:
        rg= "RG1"
    elif "RGB" in tech_csv:
        rg= "RG2"
    elif "RGC" in tech_csv:
        rg= "RG3"    
    
    
   
    
    if onoff=="PV_Utility_scale_no_tracking":
            onoff_suf="_VRE-PV_Utility_scale_no_tracking"
    elif onoff=="PV_Utility_scale_tracking":
            onoff_suf="_VRE-PV_Utility_scale_tracking"
    elif onoff=="PV_Rooftop":
            onoff_suf="_VRE-PV_Rooftop"        
    
 
    df.columns= df.columns +  onoff_suf + "_"  + rg    
        
    

    return df

def get_FLH_for_balmorel(folder,output_folder,scaled_raw_ts):

    if "Existing" in folder:
        df_cf= pd.read_excel(output_folder + "/" + folder + "/stats/" + "FLH_" + scaled_raw_ts + "_ts.xlsx",index_col="Unnamed: 0",sheet_name=None)
        df_cf = pd.concat(df_cf.values(), ignore_index=False)
        df_cf['Existing'] = df_cf['Offshore_2020'].combine_first(df_cf['Onshore_2020'])
        df_cf=df_cf[['Existing']]
   
    else:
        df_cf= pd.read_excel(output_folder + "/" + folder + "/stats/" + "FLH_" + scaled_raw_ts + "_ts.xlsx",index_col="Unnamed: 0")

    onoff, source = get_onoff_source_from_folder(folder)

    #if source=="wind":
    df_cf=fix_WFLH_areas(df_cf,onoff)
        

    return df_cf
    
def combine_excel_for_balmorel(folder,output_folder,scaled_raw_ts):
    tech_csvs = os.listdir(output_folder + "/" + folder + "/" + scaled_raw_ts)

    
    onoff, source = get_onoff_source_from_folder(folder)
    

    combined_df = pd.DataFrame()
    
    
    
    
    for i,iter1 in enumerate(tech_csvs):
        
        df = pd.read_excel(output_folder + "/" + folder + "/" + scaled_raw_ts +"/" + iter1,index_col="time")
        
        if i==0:
            combined_df.index=df.index
  
        if source=="wind":
            df=fix_wind_column_names_to_balmorel(df,iter1,onoff)
            
            
        elif source=="solar":
            df=fix_solar_column_names_to_balmorel(df,iter1,onoff)
         
        combined_df = pd.merge(combined_df, df, left_index=True, right_index=True)
    
    return combined_df
     

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

def calc_CapDev_timeseries(config,combined_scaled_dfs,df_t):
    
    CapDev_timesteps=get_CapDev_timesteps(config)
    
    df_t_cut=df_t[df_t.CapDev_time.isin(CapDev_timesteps)]
    
    
    filtered_df1 = combined_scaled_dfs[combined_scaled_dfs.index.isin(df_t_cut.DA_time)]
    
    combined_scaled_dfs.index=df_t.index
    filtered_df1.index=df_t_cut.index
    
    df_scaled=scale_data_to_same_mean_with_full_time_series(combined_scaled_dfs,filtered_df1)
    
    df_scaled.index=df_t_cut.CapDev_time

    return df_scaled


def timeseries_to_balmorel(config_fn,start_date,output_folder):

        with open(config_fn) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)

    
        output_folder=output_folder + "/" + str(start_date)
        check_if_dir_exists(output_folder + "/to_balmorel/DA/scaled")
        check_if_dir_exists(output_folder + "/to_balmorel/DA/raw")
        check_if_dir_exists(output_folder + "/to_balmorel/CapDev")
        #check_if_dir_exists(output_folder + "/to_balmorel/CapDev/scaled")
        #check_if_dir_exists(output_folder + "/to_balmorel/CapDev/raw")
    
        contents = os.listdir(output_folder)
        wind_criteria = {'Offshore', 'Onshore',"Existing"}
        solar_criteria = {'PV'}
        
        
        techs=dict()
        techs["wind"] = {tech for tech in contents if any(criterion in tech for criterion in wind_criteria)}
        techs["solar"] = {tech for tech in contents if any(criterion in tech for criterion in solar_criteria)}
        
        
        dfs_scaled=dict()
        FLH_scaled=dict()
        
        for source in techs.keys():
            dfs_scaled[source]=dict()
            FLH_scaled[source]=dict()
                    
            
            if source == "wind":
                    ts_name="WND_VAR_T"
                    FLH_name="WNDFLH"

            elif source =="solar":
                ts_name="SOLE_VAR_T"
                FLH_name="SOLEFLH"
                    
            for scaled_raw_ts in ["scaled","raw"]:
                dfs_scaled[source][scaled_raw_ts]=[]
                FLH_scaled[source][scaled_raw_ts]=[]
                combined_scaled_dfs=pd.DataFrame()
                combined_scaled_FLH=pd.DataFrame()
                dfs=[]
                #FLH=[]
                for tech in techs[source]: 
                    dfs.append(combine_excel_for_balmorel(tech,output_folder,scaled_raw_ts))
                    #FLH.append(get_FLH_for_balmorel(tech,output_folder,scaled_raw_ts))
    
                combined_scaled_dfs=pd.concat(dfs,axis=1)
                #combined_scaled_FLH=pd.concat(FLH)
                combined_scaled_FLH=  ( (combined_scaled_dfs.mean().to_frame()) * len(combined_scaled_dfs))[0]
            
               
                df_t=create_time_column()
                if len(combined_scaled_dfs)>len(df_t):
                    combined_scaled_dfs=combined_scaled_dfs[:len(df_t)]
                df_t.index=combined_scaled_dfs.index
                
                
                combined_scaled_dfs.index=df_t.DA_time
                combined_scaled_dfs.rename_axis(None, axis='index', inplace=True)
                combined_scaled_dfs=add_WND_VAR_T_Existing_RG2_RG3(combined_scaled_dfs)
    
    
                create_SSS_TTT_AAA_inc(combined_scaled_dfs,ts_name,output_folder + "/to_balmorel/DA/" + scaled_raw_ts )
    
    
                combined_scaled_FLH.rename_axis(None, axis='index', inplace=True)
                combined_scaled_FLH=add_FLH_existing_RG2_RG3(combined_scaled_FLH)
    
                
                create_AAA_inc(combined_scaled_FLH,FLH_name,output_folder + "/to_balmorel/DA/" + scaled_raw_ts)

                df_CapDev_scaled=calc_CapDev_timeseries(config,combined_scaled_dfs,df_t)
                FLH_CapDev_scaled= ( (df_CapDev_scaled.mean().to_frame()) * len(combined_scaled_dfs))[0]

                if scaled_raw_ts=="scaled":
                    create_SSS_TTT_AAA_inc(df_CapDev_scaled,ts_name,output_folder + "/to_balmorel/CapDev/"  )
                    create_AAA_inc(FLH_CapDev_scaled,FLH_name,output_folder + "/to_balmorel/CapDev/" )

                
                    
                dfs_scaled[source][scaled_raw_ts].append(combined_scaled_dfs)
                FLH_scaled[source][scaled_raw_ts].append(combined_scaled_FLH)
        df_t.to_csv(output_folder + "/to_balmorel/balmorel_time_translation.csv")

        return dfs_scaled,FLH_scaled

        
            
    
        
        
            
    
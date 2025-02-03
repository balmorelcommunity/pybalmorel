"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""


import pandas as pd
import numpy as np

from .to_inc import create_GKFX_inc

def get_GKFX(RRRAAA_renewable_df,config,output_folder):

    RRRAAA_renewable_df[['Region', 'AreasRG']] = RRRAAA_renewable_df['RRRAAA_renewable'].str.split(pat='.', n=1, expand=True)

    RRRAAA_renewable_df[['Areas', 'RG']] = RRRAAA_renewable_df['AreasRG'].str.rsplit('_', n=1, expand=True)

    RRRAAA_renewable_df=RRRAAA_renewable_df[["Region","Areas","RG"]]

    existing_wind_cap=pd.read_excel(config["Existing_wind_cap"])

    wind_dfs=[]
    for iter1 in ["Onshore","Offshore"]:
        if iter1=="Onshore":
            cont="ONS_Existing"
            g_name="GNR_WT_WIND_ONS_Existing"
        elif iter1=="Offshore":
            cont="OFF_Existing"
            g_name="GNR_WT_WIND_OFF_Existing"
            
        RRRAAA_renewable_df_wind = RRRAAA_renewable_df[RRRAAA_renewable_df['Areas'].str.contains(cont, regex=True)]
        region_area_transl = RRRAAA_renewable_df_wind.drop_duplicates(subset=['Region', 'Areas'])
        if iter1 == "Offshore":
            #region_area_transl['Region'] = region_area_transl['Areas'].str.split('_').str[:2].str.join('_')
            region_area_transl.loc[:, 'Region'] = region_area_transl['Areas'].str.split('_').str[:2].str.join('_')

            
        df_merged = existing_wind_cap.merge(region_area_transl[['Region', 'Areas']], on='Region', how='left')
        df_merged = df_merged.dropna(subset=['Areas'])
        df_merged["AreaTehc"]=df_merged["Areas"] + "_" + df_merged["Technology"]

        for rg in["RG1","RG2","RG3"]:
            df_merged["Technology"]=df_merged["Technology"].replace(rg,g_name + "_" + rg)


        df_merged["AreaTehc"]=df_merged["AreaTehc"] + "." + df_merged["Technology"]
        df_merged=df_merged.set_index("AreaTehc")
        df_merged=df_merged.drop(["Region","Areas","Technology"],axis=1)
        df_merged = df_merged.replace(0, pd.NA).dropna(how='all')

        wind_dfs.append(df_merged)

    wind_dfs=pd.concat(wind_dfs)
    wind_dfs = wind_dfs[wind_dfs.index.notna()]

    existing_solar_cap=pd.read_excel(config["Existing_solar_cap"],sheet_name="Capacities_MW")
    year_columns=existing_solar_cap.columns[2:] 
    tech_split=pd.read_excel(config["Existing_solar_cap"],sheet_name="Tech_split",index_col="Region")
    tech_split=tech_split/100


    solar_dfs=[]
    for iter1 in tech_split.keys():
        if iter1=="PV_Rooftop":
            g_name= "GNR_PV-Rooftop_"
        elif iter1=="PV_Utility_scale_no_tracking":
            g_name= "GNR_PV-Utility_scale_no_tracking_"
        elif iter1=="PV_Utility_scale_tracking":
            g_name= "GNR_PV-Utility_scale_tracking_"
        
        df_merged = pd.merge(existing_solar_cap, tech_split[iter1], on='Region')
        df_merged["RG"]=df_merged["Technology"]
        df_merged["Technology"]= g_name + df_merged["Technology"] + "_Existing"
        df_merged[year_columns] = df_merged[year_columns].multiply(df_merged[iter1], axis=0)
        df_merged=df_merged.drop(iter1,axis=1)
        
        region_area_transl = RRRAAA_renewable_df[RRRAAA_renewable_df['Areas'].str.contains(iter1, regex=True)].drop_duplicates(subset=['Region', 'Areas'])
        df_merged = df_merged.merge(region_area_transl[['Region', 'Areas']], on='Region', how='left')
        
        solar_dfs.append(df_merged)

    df_solar=pd.concat(solar_dfs)
    df_solar["AreaTehc"]=df_solar["Areas"] + "_" + df_solar["RG"]
    df_solar["AreaTehc"]=df_solar["AreaTehc"] + "." + df_solar["Technology"]
    df_solar=df_solar.set_index("AreaTehc")
    df_solar=df_solar.drop(["Region","Areas","Technology","RG"],axis=1)
    df_solar = df_solar.replace(0, pd.NA).dropna(how='all')
    df_solar = df_solar[df_solar.index.notna()]

    gkfx=pd.concat([wind_dfs,df_solar])
    gkfx=gkfx.replace(np.nan,"")
    gkfx.index.name=""
    
    create_GKFX_inc(gkfx,"GKFX_renewable",output_folder + "/to_balmorel/")

    return gkfx
    
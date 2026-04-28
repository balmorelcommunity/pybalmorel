"""Functions to create the GKFX table and .inc file for existing renewable generators.

GKFX holds the exogenous capacity of wind and solar technologies in each area and year,
defined by the Balmorel reader file at Balmorelbb4_ReadData.inc line 256 as
'Capacity of exogenously given generation technologies (MW...'.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

import os

import numpy as np
import pandas as pd

from .to_inc import create_GKFX_inc

def get_GKFX(
    rrraaa_renewable_df: pd.DataFrame,
    config: dict,
    output_folder: str,
) -> pd.DataFrame:
    """Build GKFX table and write the corresponding .inc file for existing renewables.

    Args:
        rrraaa_renewable_df: DataFrame with 'RRRAAA_renewable' column naming generators.
        config: Configuration dict with keys 'Existing_wind_cap' and 'Existing_solar_cap'.
        output_folder: Root output directory; the .inc file is written to
            <output_folder>/to_balmorel/.

    Returns:
        GKFX DataFrame indexed by generator names.
    """
    rrraaa_renewable_df[['Region', 'AreasRG']] = rrraaa_renewable_df['RRRAAA_renewable'].str.split(
        pat='.', n=1, expand=True
    )
    rrraaa_renewable_df[['Areas', 'RG']] = rrraaa_renewable_df['AreasRG'].str.rsplit(
        '_', n=1, expand=True
    )
    rrraaa_renewable_df = rrraaa_renewable_df[["Region", "Areas", "RG"]]

    existing_wind_cap = pd.read_excel(config["Existing_wind_cap"])

    wind_dfs = []
    for wind_type in ["Onshore", "Offshore"]:
        if wind_type == "Onshore":
            cont = "ONS_Existing"
            g_name = "GNR_WT_WIND_ONS_Existing"
        elif wind_type == "Offshore":
            cont = "OFF_Existing"
            g_name = "GNR_WT_WIND_OFF_Existing"
            
        rrraaa_wind = rrraaa_renewable_df[rrraaa_renewable_df['Areas'].str.contains(cont, regex=True)]
        region_area_transl = rrraaa_wind.drop_duplicates(subset=['Region', 'Areas'])
        if wind_type == "Offshore":
            region_area_transl.loc[:, 'Region'] = (
                region_area_transl['Areas'].str.split('_').str[:2].str.join('_')
            )

            
        df_merged = existing_wind_cap.merge(
            region_area_transl[['Region', 'Areas']], on='Region', how='left'
        )
        df_merged = df_merged.dropna(subset=['Areas'])
        df_merged["AreaTech"] = df_merged["Areas"] + "_" + df_merged["Technology"]

        for rg in ["RG1", "RG2", "RG3"]:
            df_merged["Technology"] = df_merged["Technology"].replace(rg, g_name + "_" + rg)

        df_merged["AreaTech"] = df_merged["AreaTech"] + "." + df_merged["Technology"]
        df_merged = df_merged.set_index("AreaTech")
        df_merged = df_merged.drop(["Region", "Areas", "Technology"], axis=1)
        df_merged = df_merged.replace(0, pd.NA).dropna(how='all')
        wind_dfs.append(df_merged)

    wind_dfs = pd.concat(wind_dfs)
    wind_dfs = wind_dfs[wind_dfs.index.notna()]

    existing_solar_cap = pd.read_excel(config["Existing_solar_cap"], sheet_name="Capacities_MW")
    year_columns = existing_solar_cap.columns[2:]
    tech_split = pd.read_excel(
        config["Existing_solar_cap"], sheet_name="Tech_split", index_col="Region"
    )
    tech_split = tech_split / 100

    solar_dfs = []
    for solar_tech in tech_split.keys():
        if solar_tech == "PV_Rooftop":
            g_name = "GNR_PV-Rooftop_"
        elif solar_tech == "PV_Utility_scale_no_tracking":
            g_name = "GNR_PV-Utility_scale_no_tracking_"
        elif solar_tech == "PV_Utility_scale_tracking":
            g_name = "GNR_PV-Utility_scale_tracking_"
        
        df_merged = pd.merge(existing_solar_cap, tech_split[solar_tech], on='Region')
        df_merged["RG"] = df_merged["Technology"]
        df_merged["Technology"] = g_name + df_merged["Technology"] + "_Existing"
        df_merged[year_columns] = df_merged[year_columns].multiply(df_merged[solar_tech], axis=0)
        df_merged = df_merged.drop(solar_tech, axis=1)

        region_area_transl = rrraaa_renewable_df[
            rrraaa_renewable_df['Areas'].str.contains(solar_tech, regex=True)
        ].drop_duplicates(subset=['Region', 'Areas'])
        df_merged = df_merged.merge(
            region_area_transl[['Region', 'Areas']], on='Region', how='left'
        )
        
        solar_dfs.append(df_merged)

    df_solar = pd.concat(solar_dfs)
    df_solar["AreaTech"] = df_solar["Areas"] + "_" + df_solar["RG"]
    df_solar["AreaTech"] = df_solar["AreaTech"] + "." + df_solar["Technology"]
    df_solar = df_solar.set_index("AreaTech")
    df_solar = df_solar.drop(["Region", "Areas", "Technology", "RG"], axis=1)
    df_solar = df_solar.replace(0, pd.NA).dropna(how='all')
    df_solar = df_solar[df_solar.index.notna()]

    gkfx = pd.concat([wind_dfs, df_solar])
    gkfx = gkfx.replace(np.nan, "")
    gkfx.index.name = ""

    create_GKFX_inc(
        gkfx, "GKFX_renewable", os.path.join(output_folder, "to_balmorel")
    )

    return gkfx
    
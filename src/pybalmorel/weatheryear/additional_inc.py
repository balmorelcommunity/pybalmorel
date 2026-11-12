"""
Functions for generating additional Balmorel .inc files from CorRES VRE data.

Creates generator sets (GGG, AAA, RRRAAA), investment data (INVDATA, INVDATASET,
ALLOWEDINV, ANNUITYCG), potential tables (SUBTECHGROUPKPOT), capacity factors
(GKFX) and GDATA for renewable technologies.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

import numpy as np
import os 
import pandas as pd

from .auxiliary_functions import parse_technology_folder_name
from .config_models import AdditionalIncConfig
from .exceptions import MalformedTechnologyFolderError
from .to_inc import build_inc_file_list_type, create_Table_inc
from .get_GDATA_func import build_GDATA
from .get_GKFX_func import build_GKFX

# Investment years used in Balmorel generator set names
INVESTMENT_YEARS = ["_Y-2020", "_Y-2030", "_Y-2040", "_Y-2050"]

# Per-category name templates shared by build_GGG / build_INVDATASET / build_AAA
# for the "Future_*" wind and PV categories (the ones with a turbine/RG
# dimension). GGG_renewable, INVDATASET_renewable, and AAA_renewable are
# different Balmorel set domains and are meant to keep their own distinct
# spellings - but each spelling for a given category used to be hand-typed
# independently in each builder function, which already caused one real
# spelling divergence (see to_balmorel.py's format_wind_column_names_for_balmorel
# comment). Keeping each category's three templates together here means the
# (turbine, rg) identity feeding all three can't drift apart again (see ADR 0003).
# "Existing" wind/PV has no turbine dimension and is small/fixed, so it's left
# as plain literals in each builder rather than templated here.
_WIND_TEMPLATES = {
    "Future_Onshore": {
        "ggg": "GNR_WT-{tur}_ONS_{rg}{year}",
        "invdataset": "VRE-ONS_{tur}_{rg}",
        "aaa": "{region}_VRE-ONS_{tur}_{rg}",
    },
    "Future_Offshore_bottom_fixed": {
        "ggg": "GNR_WT-{tur}_OFF_bottom_fixed_{rg}{year}",
        "invdataset": "VRE-OFF_bottom_fixed_{tur}_{rg}",
        "aaa": "{region}_VRE-OFF_bottom_fixed_{tur}_{rg}",
    },
    "Future_Offshore_floating": {
        "ggg": "GNR_WT-{tur}_OFF_floating_{rg}{year}",
        "invdataset": "VRE-OFF_floating_{tur}_{rg}",
        "aaa": "{region}_VRE-OFF_floating_{tur}_{rg}",
    },
}

_SOLAR_TEMPLATES = {
    "PV_Rooftop": {
        "ggg": "GNR_PV-Rooftop_{rg}{year}",
        "ggg_existing": "GNR_PV-Rooftop_{rg}_Existing",
        "invdataset": "PV_Rooftop_{rg}",
        "aaa": "{region}_VRE-PV_Rooftop_{rg}",
    },
    "PV_Utility_scale_no_tracking": {
        "ggg": "GNR_PV-Utility_scale_no_tracking_{rg}{year}",
        "ggg_existing": "GNR_PV-Utility_scale_no_tracking_{rg}_Existing",
        "invdataset": "PV_Utility_scale_no_tracking_{rg}",
        "aaa": "{region}_VRE-PV_Utility_scale_no_tracking_{rg}",
    },
    "PV_Utility_scale_tracking": {
        "ggg": "GNR_PV-Utility_scale_tracking_{rg}{year}",
        "ggg_existing": "GNR_PV-Utility_scale_tracking_{rg}_Existing",
        "invdataset": "PV_Utility_scale_tracking_{rg}",
        "aaa": "{region}_VRE-PV_Utility_scale_tracking_{rg}",
    },
}


def _template_for(tech: str, templates: dict) -> dict:
    """Look up the (ggg, invdataset, aaa) name templates for a technology category."""
    for key, template in templates.items():
        if key in tech:
            return template
    raise KeyError(f"No naming template registered for technology: {tech}")


def _convert_corres_rg_to_balmorel(rg: str) -> str:
    """Translate CorRES resource-grade labels (RGA/B/C) to Balmorel labels (RG1/2/3)."""
    return rg.replace("RGA", "RG1").replace("RGB", "RG2").replace("RGC", "RG3")


def build_INVDATASET(
    config: AdditionalIncConfig,
    output_folder: str,
    techs: dict[str, list[str]],
    turbines: dict[str, list[str]],
) -> pd.DataFrame:
    INVDATASET_renewables=[]
    for tech in techs["wind"] :
                
        if "Existing" in tech:
            INVDATASET_renewables.append("OFF_Existing_RG1")
            INVDATASET_renewables.append("OFF_Existing_RG2")
            INVDATASET_renewables.append("OFF_Existing_RG3")
            INVDATASET_renewables.append("ONS_Existing_RG1")
            INVDATASET_renewables.append("ONS_Existing_RG2")
            INVDATASET_renewables.append("ONS_Existing_RG3")
                    #AAA_renwable.append(region + "_ONS_Exisiting")
                
        elif "Future_Onshore" in tech:
            template = _template_for(tech, _WIND_TEMPLATES)["invdataset"]
            for tur in turbines["onshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    INVDATASET_renewables.append(template.format(tur=tur, rg=rg))

        elif "Future_Offshore_bottom_fixed" in tech or "Future_Offshore_floating" in tech:
            template = _template_for(tech, _WIND_TEMPLATES)["invdataset"]
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    INVDATASET_renewables.append(template.format(tur=tur, rg=rg))

    for tech in techs["solar"] :
        template = _template_for(tech, _SOLAR_TEMPLATES)["invdataset"]
        for rg in config.rgs_for(tech):
            rg = _convert_corres_rg_to_balmorel(rg)
            INVDATASET_renewables.append(template.format(rg=rg))
    
    INVDATASET_renewables_df=pd.DataFrame()
    INVDATASET_renewables_df["INVDATASET_renewables"]=INVDATASET_renewables
    
    build_inc_file_list_type(INVDATASET_renewables_df,"INVDATASET_renewables",output_folder + "/to_balmorel")
    return INVDATASET_renewables_df


def build_INVDATA_renewable(
    INVDATASET_renewables_df: pd.DataFrame,
    AAA_renewable_df: pd.DataFrame,
    output_folder: str,
) -> pd.DataFrame:
    INVDATA=[]
    for iter1 in INVDATASET_renewables_df["INVDATASET_renewables"]:
            # build_AAA's templates always nest the INVDATASET_renewable string
            # directly inside the AAA_renewable name (region + "_" + this string
            # for wind, region + "_VRE-" + this string for solar - see ADR 0003),
            # so a plain literal containment check is exact; no extra
            # normalization of iter1 is needed (a prior "ONSVRE_"/"OFFSVRE_"
            # strip here was dead code - those substrings never occur).
            df=AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains(iter1, regex=False)]
            for area in df["AAA_renewable"]:
                INVDATA.append( "INVDATA('" + area + "','" + iter1 + "')=1 ;"   )
    
    INVDATA_df=pd.DataFrame()
    INVDATA_df["INVDATA_renewable"]=INVDATA
    
    build_inc_file_list_type(INVDATA_df,"INVDATA_renewable",output_folder + "/to_balmorel",equations=True)
    return INVDATA_df

def build_GGG(
    config: AdditionalIncConfig,
    output_folder: str,
    techs: dict[str, list[str]],
    turbines: dict[str, list[str]],
) -> pd.DataFrame:
    GGG_renewable=[]
    for tech in techs["wind"] :
        if "Existing" in tech:
            GGG_renewable.append( "GNR_WT_WIND_ONS_Existing_RG1")
            GGG_renewable.append("GNR_WT_WIND_ONS_Existing_RG2")
            GGG_renewable.append("GNR_WT_WIND_ONS_Existing_RG3")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG1")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG2")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG3")
        elif  "Future_Onshore" in tech:
            template = _template_for(tech, _WIND_TEMPLATES)["ggg"]
            for tur in turbines["onshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    for year in INVESTMENT_YEARS:
                        GGG_renewable.append(template.format(tur=tur, rg=rg, year=year))
        elif  "Future_Offshore_bottom_fixed" in tech or "Future_Offshore_floating" in tech:
            template = _template_for(tech, _WIND_TEMPLATES)["ggg"]
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    for year in INVESTMENT_YEARS:
                        GGG_renewable.append(template.format(tur=tur, rg=rg, year=year))

    for tech in techs["solar"] :
        templates = _template_for(tech, _SOLAR_TEMPLATES)
        for rg in config.rgs_for(tech):
            rg = _convert_corres_rg_to_balmorel(rg)
            for year in INVESTMENT_YEARS:
                GGG_renewable.append(templates["ggg"].format(rg=rg, year=year))
            GGG_renewable.append(templates["ggg_existing"].format(rg=rg))
    
    GGG_renewable_df=pd.DataFrame()
    GGG_renewable_df["GGG_renewable"]=GGG_renewable
    build_inc_file_list_type(GGG_renewable_df,"GGG_renewable",output_folder + "/to_balmorel")

    GGG_renewable_df=GGG_renewable_df.rename(columns={"GGG_renewable":"G_renewable"})
    build_inc_file_list_type(GGG_renewable_df,"G_renewable",output_folder + "/to_balmorel")
    return GGG_renewable_df



def build_ANNUITYCG(GDATA: pd.DataFrame, config: AdditionalIncConfig, output_folder: str) -> None:
    GDATA_future = GDATA.loc[GDATA["GDKVARIABL"]==1]
    annuity = (
                (1 - config.annuitycg_calculation.debt_share) * config.annuitycg_calculation.discount_rate
                + config.annuitycg_calculation.interest_rate * config.annuitycg_calculation.debt_share *
                (1 - (1 + config.annuitycg_calculation.discount_rate) ** (-GDATA_future['GDLIFETIME']))
                / (1 - (1 + config.annuitycg_calculation.interest_rate) ** (-GDATA_future['GDLIFETIME']))
            ) / (1 - (1 + config.annuitycg_calculation.discount_rate) ** (-GDATA_future['GDLIFETIME']))

    ANNUITYCG_list=[]
    for iter1 in annuity.index:
        ANNUITYCG_list.append("ANNUITYCG(CCC,'" + iter1 + "')=" + str(annuity.loc[iter1]) + ";")
            
    ANNUITYCG_df=pd.DataFrame()
    ANNUITYCG_df["ANNUITYCG_renewables"]=ANNUITYCG_list
    
    
    build_inc_file_list_type(ANNUITYCG_df,"ANNUITYCG_renewables",output_folder + "/to_balmorel",equations=True)



def build_AGKN(AAA: pd.DataFrame, GGG: pd.DataFrame, output_folder: str) -> None:

    AGKN=pd.DataFrame()
    agkn_list=[]
    
    AAA_ons_pv = AAA[AAA['AAA_renewable'].str.contains('ONS|PV', regex=True)]
    AAA_off = AAA[AAA['AAA_renewable'].str.contains('OFF', regex=True)]

        
    GGG_ons_pv = GGG[GGG['GGG_renewable'].str.contains('ONS|PV', regex=True)]
    GGG_off = GGG[GGG['GGG_renewable'].str.contains('OFF', regex=True)]

    for iter1 in AAA_ons_pv["AAA_renewable"].unique():
        for iter2 in GGG_ons_pv["GGG_renewable"]:
            agkn_list.append( "AGKN('" + iter1 + "','" + iter2 + "')=YES;"       )

    for iter1 in AAA_off["AAA_renewable"].unique():
        for iter2 in GGG_off["GGG_renewable"]:
            agkn_list.append( "AGKN('" + iter1 + "','" + iter2 + "')=YES;"       )
    
    AGKN["AGKN"]=agkn_list

    AGKN.to_csv( output_folder + "/to_balmorel/AGKN_renewables" + ".csv",index=False)


def build_AAA(
    config: AdditionalIncConfig,
    output_folder: str,
    techs: dict[str, list[str]],
    turbines: dict[str, list[str]],
) -> pd.DataFrame:
    AAA_renwable=[]
    for region in config.regions_to_keep.onshore:
       
        for tech in techs["wind"] :
            
            if "Existing" in tech:
                AAA_renwable.append(region + "_ONS_Existing_RG1")
                AAA_renwable.append(region + "_ONS_Existing_RG2")
                AAA_renwable.append(region + "_ONS_Existing_RG3")
                #AAA_renwable.append(region + "_ONS_Exisiting")
            
            elif "Future_Onshore" in tech:
                template = _template_for(tech, _WIND_TEMPLATES)["aaa"]
                for tur in turbines["onshore"]:
                    for rg in config.rgs_for(tech):
                        rg = _convert_corres_rg_to_balmorel(rg)
                        AAA_renwable.append(template.format(region=region, tur=tur, rg=rg))

        for tech in techs["solar"] :
            template = _template_for(tech, _SOLAR_TEMPLATES)["aaa"]
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                AAA_renwable.append(template.format(region=region, rg=rg))

    for region in config.regions_to_keep.offshore:
        for tech in techs["wind"] :

            if "Existing" in tech:
                AAA_renwable.append(region + "_OFF_Existing_RG1")
                AAA_renwable.append(region + "_OFF_Existing_RG2")
                AAA_renwable.append(region + "_OFF_Existing_RG3")

            
            elif "Future_Offshore_bottom_fixed" in tech or "Future_Offshore_floating" in tech:
                template = _template_for(tech, _WIND_TEMPLATES)["aaa"]
                for tur in turbines["offshore"]:
                    for rg in config.rgs_for(tech):
                        rg = _convert_corres_rg_to_balmorel(rg)
                        AAA_renwable.append(template.format(region=region, tur=tur, rg=rg))

    AAA_ren_df=pd.DataFrame()
    AAA_ren_df["AAA_renewable"]=AAA_renwable

    CCCRRRAAA_df=pd.DataFrame()
    CCCRRRAAA_df["CCCRRRAAA_renewable"]=AAA_renwable
    build_inc_file_list_type(AAA_ren_df,"AAA_renewable",output_folder + "/to_balmorel")
    build_inc_file_list_type(CCCRRRAAA_df,"CCCRRRAAA_renewable",output_folder + "/to_balmorel")
    return AAA_ren_df


def build_RRRAAA(
    AAA_renewable_df: pd.DataFrame,
    config: AdditionalIncConfig,
    output_folder: str,
) -> pd.DataFrame:
    RRRAAA_renewable_df=pd.DataFrame()
    RRRAAA_renewable_df_off=pd.DataFrame()
    areas=[]
    regions=[]
    for iter1 in config.regions_to_keep.offshore:
        
        areas=areas + list(AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]["AAA_renewable"].values[:])
        regions=regions + [iter1.replace("_OFF1","").replace("_OFF2","").replace("_OFF","")]*len(list(AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]["AAA_renewable"].values[:]))
    
    RRRAAA_renewable_df_off["RRR"]=regions
    RRRAAA_renewable_df_off["AAA"]=areas
    
    
    areas=[]
    regions=[]
    for iter1 in config.regions_to_keep.onshore:
        
        all_areas= AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]
        areas=areas + list(all_areas[~all_areas["AAA_renewable"].str.contains("OFF")]["AAA_renewable"].values[:])
        regions=regions + [iter1]*len(list(all_areas[~all_areas["AAA_renewable"].str.contains("OFF")]["AAA_renewable"].values[:]))
        
    RRRAAA_renewable_df["RRR"]=regions
    RRRAAA_renewable_df["AAA"]=areas
    
    RRRAAA_renewable_df=pd.concat([RRRAAA_renewable_df,RRRAAA_renewable_df_off])
    
    RRRAAA_renewable_df["RRRAAA_renewable"]=RRRAAA_renewable_df["RRR"] + "." + RRRAAA_renewable_df["AAA"]
    RRRAAA_renewable_df=RRRAAA_renewable_df.drop(["RRR","AAA"],axis=1)
    build_inc_file_list_type(RRRAAA_renewable_df,"RRRAAA_renewable",output_folder + "/to_balmorel")

    return RRRAAA_renewable_df
    
    
def build_ALLOWEDINV(
    AAA_renewable_df: pd.DataFrame,
    GGG_renewable_df: pd.DataFrame,
    INVDATASET_renewables_df: pd.DataFrame,
    turbines: dict[str, list[str]],
    techs: dict[str, list[str]],
    config: AdditionalIncConfig,
    output_folder: str,
) -> None:

    ALLOWEDINV_list=[]
    region=config.regions_to_keep.onshore[0]
    for tech in techs["wind"] :
        if "Existing" in tech:
            for rg in ["RG1","RG2","RG3"]:
                for onoff,area in [("GNR_WT_WIND_ONS_","ONS_Existing_"),("GNR_WT_WIND_OFF_","OFF_Existing_")]:
                    areas=AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains(area + rg, regex=True)]
                    area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                    ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(onoff + rg, regex=True)]
                    if len(ggg)>0:
                        str_to_add= area.values[0][0] + ".( \n"   
                        for iter1 in ggg['G_renewable']: 
                            str_to_add=str_to_add + iter1 + "\n "   
                        str_to_add = str_to_add  +") \n "
                        ALLOWEDINV_list.append( str_to_add)

                
                    
        elif "Future_Onshore" in tech:
            for tur in turbines["onshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( tur + "_" + rg, regex=True)] 
                    area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                    ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(tur + "_ONS_" + rg, regex=True)]
                    str_to_add= area.values[0][0] + ".( \n"   
                    for iter1 in ggg['G_renewable']: 
                        str_to_add=str_to_add + iter1 + "\n "   
                    str_to_add = str_to_add  +") \n "
                    ALLOWEDINV_list.append( str_to_add)
        elif "Future_Offshore_bottom_fixed" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    areas=AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains("_bottom_fixed_" + tur +"_" +  rg, regex=True)]
                    area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                    ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(tur + "_OFF_bottom_fixed_" + rg, regex=True)]
                    str_to_add= area.values[0][0] + ".( \n"   
                    for iter1 in ggg['G_renewable']: 
                        str_to_add=str_to_add + iter1 + "\n "   
                    str_to_add = str_to_add  +") \n "
                    ALLOWEDINV_list.append( str_to_add)
                    
        elif "Future_Offshore_floating" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    areas=AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains("_floating_" + tur +"_" +  rg, regex=True)]
                    area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                    ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(tur + "_OFF_floating_" + rg, regex=True)]
                    str_to_add= area.values[0][0] + ".( \n"   
                    for iter1 in ggg['G_renewable']: 
                        str_to_add=str_to_add + iter1 + "\n "   
                    str_to_add = str_to_add  +") \n "
                    ALLOWEDINV_list.append( str_to_add)
    
    for tech in techs["solar"] :  
    
        if "PV_Rooftop" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( "PV_Rooftop_" + rg, regex=True)] 
                area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains("PV-Rooftop_" + rg, regex=True)]
                str_to_add= area.values[0][0] + ".( \n"   
                for iter1 in ggg['G_renewable']: 
                    str_to_add=str_to_add + iter1 + "\n "   
                str_to_add = str_to_add  +") \n "
                ALLOWEDINV_list.append( str_to_add)
                    
        elif "PV_Utility_scale_no_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( "PV_Utility_scale_no_tracking_" + rg, regex=True)] 
                area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains("PV-Utility_scale_no_tracking_" + rg, regex=True)]
                str_to_add= area.values[0][0] + ".( \n"   
                for iter1 in ggg['G_renewable']: 
                    str_to_add=str_to_add + iter1 + "\n "   
                str_to_add = str_to_add  +") \n "
                ALLOWEDINV_list.append( str_to_add)
        
        elif "PV_Utility_scale_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( "PV_Utility_scale_tracking_" + rg, regex=True)] 
                area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains("PV-Utility_scale_tracking_" + rg, regex=True)]
                str_to_add= area.values[0][0] + ".( \n"   
                for iter1 in ggg['G_renewable']: 
                    str_to_add=str_to_add + iter1 + "\n "   
                str_to_add = str_to_add  +") \n "
                ALLOWEDINV_list.append( str_to_add)
    
    
    
    ALLOWEDINV_df=pd.DataFrame()
    ALLOWEDINV_df["ALLOWEDINV"]=ALLOWEDINV_list
        
    prefix = "SET ALLOWEDINV(AAA,GGG) "   
    with open(output_folder + "/to_balmorel/" + "ALLOWEDINV" + ".inc", "w") as the_file:
        the_file.write("*File created from weatheryear module")
        the_file.write("\n")
        
        the_file.write("$onMulti")
        the_file.write("\n")
        the_file.write(prefix )
        the_file.write("\n")
        the_file.write("/ ")
        the_file.write("\n")
    
        for item in ALLOWEDINV_df["ALLOWEDINV"]:
            the_file.write(item +"\n" )
        
        the_file.write("/ ;")
    
        for INVDATASET in INVDATASET_renewables_df["INVDATASET_renewables"]:
            areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( INVDATASET, regex=True)]
            if len(areas)>0:
                area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
            
                the_file.write("\n")
                the_file.write("\n")
                the_file.write("ALLOWEDINV(AAA,G)$((INVDATA(AAA,'" + INVDATASET + "')=1)  and ALLOWEDINV('" + area.values[0][0] + "',G))         = yes ; ")



def build_SUBTECHGROUPKPOT(
    RRRAAA_renewable_df: pd.DataFrame,
    config: AdditionalIncConfig,
    output_folder: str,
) -> None:

    dfs=[]
    for iter1 in ["Onshore","Solar","Offshore"]:
        dfs.append(pd.read_excel(config.vre_potentials, index_col="Region", sheet_name=iter1))
    
    SUBTECHGROUPKPOT=pd.concat(dfs,axis=1)
    
    SUBTECHGROUPKPOT.index.name = ""
    SUBTECHGROUPKPOT = SUBTECHGROUPKPOT.replace(np.nan, "")
    regions = RRRAAA_renewable_df["RRRAAA_renewable"].str.split(r"\.", n=1).str[0]
    SUBTECHGROUPKPOT = SUBTECHGROUPKPOT[SUBTECHGROUPKPOT.index.isin(regions)]
    
    create_Table_inc(SUBTECHGROUPKPOT, "SUBTECHGROUPKPOT", output_folder + "/to_balmorel/")
    
def build_DISCOST_H_renewable(AAA_renewable_df: pd.DataFrame, output_folder: str) -> None:
    DISCOST_H=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains('OFF_Existing', regex=True)]
    #DISCOST_H[""]=[2]*len(DISCOST_H)
    DISCOST_H = DISCOST_H.copy()
    DISCOST_H.loc[:, ""] = [2] * len(DISCOST_H)
    DISCOST_H=DISCOST_H.set_index("AAA_renewable")
    DISCOST_H.index.name=""
    create_Table_inc(DISCOST_H, "DISCOST_H_renewable", output_folder + "/to_balmorel/")


def create_additional_inc(
    config_fn: str,
    output_folder: str,
    start_date: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = AdditionalIncConfig.from_file(config_fn)

    output_folder = os.path.join(output_folder, str(start_date))
    
    

    
    contents = os.listdir(output_folder)
    wind_criteria = {'Offshore', 'Onshore',"Existing"}
    solar_criteria = {'PV'}

    def _select_techs(criteria: set[str]) -> list[str]:
        # Folders left over on disk from a previous run/config (e.g. a stale
        # PV_Rooftop directory) must not be processed just because they exist -
        # a known-but-currently-excluded category is dropped silently, but a
        # folder that looks like a VRE technology folder yet matches no known
        # technology pattern at all raises immediately instead (see ADR 0004).
        selected = set()
        for tech in contents:
            if not any(criterion in tech for criterion in criteria):
                continue
            try:
                parse_technology_folder_name(tech)
            except MalformedTechnologyFolderError:
                raise MalformedTechnologyFolderError(
                    f"'{tech}' looks like a VRE technology folder (matches {criteria}) "
                    "but matches no known technology pattern. This usually means CorRES "
                    "started producing a technology this pipeline doesn't know about yet."
                ) from None
            if tech in config.tech_to_keep:
                selected.add(tech)
        return sorted(selected)  # sorted so .inc files come out in the same order every run

    techs=dict()
    techs["wind"] = _select_techs(wind_criteria)
    techs["solar"] = _select_techs(solar_criteria)
    
    
    onshore_criteria = {'SP335-HH100', 'SP335-HH150','SP335-HH200','SP277-HH100',"SP277-HH150","SP277-HH200","SP199-HH100","SP199-HH150","SP199-HH200"}
    offshore_criteria = {'SP316-HH155','SP370-HH155'}
    turbines=dict()
    turbines["onshore"] = sorted({turb for turb in config.turbine_to_keep if any(criterion in turb for criterion in onshore_criteria)})
    turbines["offshore"] = sorted({turb for turb in config.turbine_to_keep if any(criterion in turb for criterion in offshore_criteria)})

    legacy_config = config.as_legacy_dict()

    AAA_renewable_df=build_AAA(config,output_folder,techs,turbines)
    RRRAAA_renewable_df=build_RRRAAA(AAA_renewable_df,config,output_folder)
    build_DISCOST_H_renewable(AAA_renewable_df,output_folder)
    GGG_renewable_df=build_GGG(config,output_folder,techs,turbines)
    GDATA=build_GDATA(GGG_renewable_df,turbines,techs,legacy_config,output_folder)
    INVDATASET_renewables_df=build_INVDATASET(config,output_folder,techs,turbines)
    INVDATA=build_INVDATA_renewable(INVDATASET_renewables_df,AAA_renewable_df,output_folder)
    build_ALLOWEDINV(AAA_renewable_df,GGG_renewable_df,INVDATASET_renewables_df,turbines,techs,config,output_folder)
    GKFX=build_GKFX(RRRAAA_renewable_df,legacy_config,output_folder)
    build_ANNUITYCG(GDATA,config,output_folder)
    build_SUBTECHGROUPKPOT(RRRAAA_renewable_df,config,output_folder)

    return AAA_renewable_df,RRRAAA_renewable_df,GKFX,GGG_renewable_df

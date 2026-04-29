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

from .config_models import AdditionalIncConfig
from .to_inc import build_inc_file_list_type,create_Table_inc
from .get_GDATA_func import build_GDATA
from .get_GKFX_func import build_GKFX

# Investment years used in Balmorel generator set names
INVESTMENT_YEARS = ["_Y-2020", "_Y-2030", "_Y-2040", "_Y-2050"]


def _convert_corres_rg_to_balmorel(rg: str) -> str:
    """Translate CorRES resource-grade labels (RGA/B/C) to Balmorel labels (RG1/2/3)."""
    return rg.replace("RGA", "RG1").replace("RGB", "RG2").replace("RGC", "RG3")


def build_INVDATASET(config: AdditionalIncConfig, output_folder, techs, turbines): 
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
            for tur in turbines["onshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    INVDATASET_renewables.append("VRE-ONS_" + tur + "_" + rg)
        
        elif "Future_Offshore_bottom_fixed" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    INVDATASET_renewables.append("VRE-OFF_bottom_fixed_" + tur + "_" + rg)
            
        elif "Future_Offshore_floating" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    INVDATASET_renewables.append("VRE-OFF_floating_" + tur + "_" + rg)
        
    for tech in techs["solar"] :
            
        if "PV_Rooftop" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                INVDATASET_renewables.append("PV_Rooftop_" + rg )
                
        elif "PV_Utility_scale_no_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                INVDATASET_renewables.append("PV_Utility_scale_no_tracking_" + rg )
        
        elif "PV_Utility_scale_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                INVDATASET_renewables.append("PV_Utility_scale_tracking_" + rg )   
    
    INVDATASET_renewables_df=pd.DataFrame()
    INVDATASET_renewables_df["INVDATASET_renewables"]=INVDATASET_renewables
    
    build_inc_file_list_type(INVDATASET_renewables_df,"INVDATASET_renewables",output_folder + "/to_balmorel")
    return INVDATASET_renewables_df


def build_INVDATA_renewable(INVDATASET_renewables_df,AAA_renewable_df,output_folder):
    INVDATA=[]
    for iter1 in INVDATASET_renewables_df["INVDATASET_renewables"]:
            if "SP" in iter1:
                check_str=iter1.replace("ONSVRE_","").replace("OFFSVRE_","")
            else:
                check_str=iter1
            
            df=AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains(check_str, regex=True)]
            for area in df["AAA_renewable"]:
                INVDATA.append( "INVDATA('" + area + "','" + iter1 + "')=1 ;"   )
    
    INVDATA_df=pd.DataFrame()
    INVDATA_df["INVDATA_renewable"]=INVDATA
    
    build_inc_file_list_type(INVDATA_df,"INVDATA_renewable",output_folder + "/to_balmorel",equations=True)
    return INVDATA_df

def build_GGG(config: AdditionalIncConfig, output_folder, techs, turbines):
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
            for tur in turbines["onshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    for year in INVESTMENT_YEARS:
                        GGG_renewable.append( "GNR_WT-" + tur + "_ONS_" + rg + year)
        elif  "Future_Offshore_bottom_fixed" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    for year in INVESTMENT_YEARS:
                        GGG_renewable.append( "GNR_WT-" + tur + "_OFF_bottom_fixed_" + rg + year)
    
        elif  "Future_Offshore_floating" in tech:
            for tur in turbines["offshore"]:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    for year in INVESTMENT_YEARS:
                        GGG_renewable.append( "GNR_WT-" + tur + "_OFF_floating_" + rg + year)
    
    for tech in techs["solar"] :
        
        
        if  "PV_Rooftop" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                for year in INVESTMENT_YEARS:
                    GGG_renewable.append( "GNR_PV-" + "Rooftop_" + rg + year)
                GGG_renewable.append( "GNR_PV-" + "Rooftop_" + rg + "_Existing")
        elif  "PV_Utility_scale_no_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                for year in INVESTMENT_YEARS:
                    GGG_renewable.append( "GNR_PV-" + "Utility_scale_no_tracking_" + rg + year)     
                GGG_renewable.append( "GNR_PV-" + "Utility_scale_no_tracking_" + rg + "_Existing")
                
        elif  "PV_Utility_scale_tracking" in tech:
            for rg in config.rgs_for(tech):
                rg = _convert_corres_rg_to_balmorel(rg)
                for year in INVESTMENT_YEARS:
                    GGG_renewable.append( "GNR_PV-" + "Utility_scale_tracking_" + rg + year)   
                GGG_renewable.append( "GNR_PV-" + "Utility_scale_tracking_" + rg + "_Existing")
    
    GGG_renewable_df=pd.DataFrame()
    GGG_renewable_df["GGG_renewable"]=GGG_renewable
    build_inc_file_list_type(GGG_renewable_df,"GGG_renewable",output_folder + "/to_balmorel")

    GGG_renewable_df=GGG_renewable_df.rename(columns={"GGG_renewable":"G_renewable"})
    build_inc_file_list_type(GGG_renewable_df,"G_renewable",output_folder + "/to_balmorel")
    return GGG_renewable_df



def build_ANNUITYCG(GDATA, config: AdditionalIncConfig, output_folder):
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



def build_AGKN(AAA,GGG,output_folder):

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


def build_AAA(config: AdditionalIncConfig, output_folder, techs, turbines):
    AAA_renwable=[]
    for region in config.regions_to_keep.onshore:
       
        for tech in techs["wind"] :
            
            if "Existing" in tech:
                AAA_renwable.append(region + "_ONS_Existing_RG1")
                AAA_renwable.append(region + "_ONS_Existing_RG2")
                AAA_renwable.append(region + "_ONS_Existing_RG3")
                #AAA_renwable.append(region + "_ONS_Exisiting")
            
            elif "Future_Onshore" in tech:
                for tur in turbines["onshore"]:
                    for rg in config.rgs_for(tech):
                        rg = _convert_corres_rg_to_balmorel(rg)
                        AAA_renwable.append(region + "_VRE-ONS_" + tur + "_" + rg)
    
        for tech in techs["solar"] :
                
            if "PV_Rooftop" in tech:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    AAA_renwable.append(region + "_VRE-PV_Rooftop_" + rg )
                    
            elif "PV_Utility_scale_no_tracking" in tech:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    AAA_renwable.append(region + "_VRE-PV_Utility_scale_no_tracking_" + rg )
            
            elif "PV_Utility_scale_tracking" in tech:
                for rg in config.rgs_for(tech):
                    rg = _convert_corres_rg_to_balmorel(rg)
                    AAA_renwable.append(region + "_VRE-PV_Utility_scale_tracking_" + rg )   

    for region in config.regions_to_keep.offshore:
        for tech in techs["wind"] :

            if "Existing" in tech:
                AAA_renwable.append(region + "_OFF_Existing_RG1")
                AAA_renwable.append(region + "_OFF_Existing_RG2")
                AAA_renwable.append(region + "_OFF_Existing_RG3")

            
            elif "Future_Offshore_bottom_fixed" in tech:
                for tur in turbines["offshore"]:
                    for rg in config.rgs_for(tech):
                        rg = _convert_corres_rg_to_balmorel(rg)
                        AAA_renwable.append(region + "_VRE-OFF_bottom_fixed_" + tur + "_" + rg)
        
            elif "Future_Offshore_floating" in tech:
                for tur in turbines["offshore"]:
                    for rg in config.rgs_for(tech):
                        rg = _convert_corres_rg_to_balmorel(rg)
                        AAA_renwable.append(region + "_VRE-OFF_floating_" + tur + "_" + rg)

    AAA_ren_df=pd.DataFrame()
    AAA_ren_df["AAA_renewable"]=AAA_renwable

    CCCRRRAAA_df=pd.DataFrame()
    CCCRRRAAA_df["CCCRRRAAA_renewable"]=AAA_renwable
    build_inc_file_list_type(AAA_ren_df,"AAA_renewable",output_folder + "/to_balmorel")
    build_inc_file_list_type(CCCRRRAAA_df,"CCCRRRAAA_renewable",output_folder + "/to_balmorel")
    return AAA_ren_df


def build_RRRAAA(AAA_renewable_df, config: AdditionalIncConfig, output_folder):
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
    
    
def build_ALLOWEDINV(AAA_renewable_df, GGG_renewable_df, INVDATASET_renewables_df, turbines, techs, config: AdditionalIncConfig, output_folder):

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



def build_SUBTECHGROUPKPOT(RRRAAA_renewable_df, config: AdditionalIncConfig, output_folder):

    dfs=[]
    for iter1 in ["Onshore","Solar","Offshore"]:
        dfs.append(pd.read_excel(config.vre_potentials, index_col="Region", sheet_name=iter1))
    
    SUBTECHGROUPKPOT=pd.concat(dfs,axis=1)
    
    SUBTECHGROUPKPOT.index.name=""
    SUBTECHGROUPKPOT=SUBTECHGROUPKPOT.replace(np.nan,"")
    SUBTECHGROUPKPOT = SUBTECHGROUPKPOT[SUBTECHGROUPKPOT.index.isin(RRRAAA_renewable_df['Region'])]
    
    create_Table_inc(SUBTECHGROUPKPOT,"SUBTECHGROUPKPOT",output_folder + "/to_balmorel/")
    
def build_DISCOST_H_renewable(AAA_renewable_df,output_folder):
    DISCOST_H=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains('OFF_Existing', regex=True)]
    #DISCOST_H[""]=[2]*len(DISCOST_H)
    DISCOST_H = DISCOST_H.copy()
    DISCOST_H.loc[:, ""] = [2] * len(DISCOST_H)
    DISCOST_H=DISCOST_H.set_index("AAA_renewable")
    DISCOST_H.index.name=""
    create_Table_inc(DISCOST_H,"DISCOST_H_renewable",output_folder + "/to_balmorel/")


def create_additional_inc(config_fn,output_folder,start_date):
    config = AdditionalIncConfig.from_file(config_fn)

    output_folder = os.path.join(output_folder, str(start_date))
    
    

    
    contents = os.listdir(output_folder)
    wind_criteria = {'Offshore', 'Onshore',"Existing"}
    solar_criteria = {'PV'}
    
    
    techs=dict()
    techs["wind"] = {tech for tech in contents if any(criterion in tech for criterion in wind_criteria)}
    techs["solar"] = {tech for tech in contents if any(criterion in tech for criterion in solar_criteria)}
    
    
    onshore_criteria = {'SP335-HH100', 'SP335-HH150','SP335-HH200','SP277-HH100',"SP277-HH150","SP277-HH200","SP199-HH100","SP199-HH150","SP199-HH200"}
    offshore_criteria = {'SP316-HH155','SP370-HH155'}
    turbines=dict()
    turbines["onshore"] = {turb for turb in config.turbine_to_keep if any(criterion in turb for criterion in onshore_criteria)}
    turbines["offshore"] = {turb for turb in config.turbine_to_keep if any(criterion in turb for criterion in offshore_criteria)}

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

"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

import numpy as np
import yaml
import os 
import pandas as pd

from .to_inc import create_list_inc,create_Table_inc
from .get_GDATA_func import get_GDATA
from .get_GKFX_func import get_GKFX

def get_INVDATASET(config,output_folder,techs,turbines): 
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
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    INVDATASET_renewables.append("VRE-ONS_" + tur + "_" + rg)
        
        elif "Future_Offshore_bottom_fixed" in tech:
            for tur in turbines["offshore"]:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    INVDATASET_renewables.append("VRE-OFF_bottom_fixed_" + tur + "_" + rg)
            
        elif "Future_Offshore_floating" in tech:
            for tur in turbines["offshore"]:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    INVDATASET_renewables.append("VRE-OFF_floating_" + tur + "_" + rg)
        
    for tech in techs["solar"] :
            
        if "PV_Rooftop" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                INVDATASET_renewables.append("PV_Rooftop_" + rg )
                
        elif "PV_Utility_scale_no_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                INVDATASET_renewables.append("PV_Utility_scale_no_tracking_" + rg )
        
        elif "PV_Utility_scale_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                INVDATASET_renewables.append("PV_Utility_scale_tracking_" + rg )   
    
    INVDATASET_renewables_df=pd.DataFrame()
    INVDATASET_renewables_df["INVDATASET_renewables"]=INVDATASET_renewables
    
    create_list_inc(INVDATASET_renewables_df,"INVDATASET_renewables",output_folder + "/to_balmorel")
    return INVDATASET_renewables_df


def get_INVDATA_renewable(INVDATASET_renewables_df,AAA_renewable_df,output_folder):
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
    
    create_list_inc(INVDATA_df,"INVDATA_renewable",output_folder + "/to_balmorel",equations=True)
    return INVDATA_df

def get_GGG(config,output_folder,techs,turbines):
    GGG_renewable=[]
    for tech in techs["wind"] :
        #for region in config["Regions_to_keep"]["onshore"]:
        if "Existing" in tech:
            GGG_renewable.append( "GNR_WT_WIND_ONS_Existing_RG1")
            GGG_renewable.append("GNR_WT_WIND_ONS_Existing_RG2")
            GGG_renewable.append("GNR_WT_WIND_ONS_Existing_RG3")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG1")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG2")
            GGG_renewable.append("GNR_WT_WIND_OFF_Existing_RG3")
        elif  "Future_Onshore" in tech:
            for tur in turbines["onshore"]:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                        GGG_renewable.append( "GNR_WT-" + tur + "_ONS_" + rg + year)
        elif  "Future_Offshore_bottom_fixed" in tech:
                for tur in turbines["offshore"]:
                    for rg in config["RGs_to_keep"][tech]:
                        rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                        for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                            GGG_renewable.append( "GNR_WT-" + tur + "_OFF_bottom_fixed_" + rg + year)
    
        elif  "Future_Offshore_floating" in tech:
                for tur in turbines["offshore"]:
                    for rg in config["RGs_to_keep"][tech]:
                        rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                        for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                            GGG_renewable.append( "GNR_WT-" + tur + "_OFF_floating_" + rg + year)
    
    for tech in techs["solar"] :
        
        
        if  "PV_Rooftop" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                    GGG_renewable.append( "GNR_PV-" + "Rooftop_" + rg + year)
                GGG_renewable.append( "GNR_PV-" + "Rooftop_" + rg + "_Existing")
        elif  "PV_Utility_scale_no_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                    GGG_renewable.append( "GNR_PV-" + "Utility_scale_no_tracking_" + rg + year)     
                GGG_renewable.append( "GNR_PV-" + "Utility_scale_no_tracking_" + rg + "_Existing")
                
        elif  "PV_Utility_scale_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                for year in ["_Y-2020", "_Y-2030","_Y-2040","_Y-2050"]:
                    GGG_renewable.append( "GNR_PV-" + "Utility_scale_tracking_" + rg + year)   
                GGG_renewable.append( "GNR_PV-" + "Utility_scale_tracking_" + rg + "_Existing")
    
    GGG_renewable_df=pd.DataFrame()
    GGG_renewable_df["GGG_renewable"]=GGG_renewable
    #GGG_renewable_df=GGG_renewable_df.set_index("GGG_renewable")
    #GGG_renewable_df.to_csv(output_folder + "/to_balmorel/GGG_renewable.csv")
    #create_list_inc(GGG_renewable_df,"GGG_renewable",output_folder + "/to_balmorel")
    create_list_inc(GGG_renewable_df,"GGG_renewable",output_folder + "/to_balmorel")

    GGG_renewable_df=GGG_renewable_df.rename(columns={"GGG_renewable":"G_renewable"})
    create_list_inc(GGG_renewable_df,"G_renewable",output_folder + "/to_balmorel")
    return GGG_renewable_df



def get_ANNUITYCG(GDATA,config,output_folder):
    GDATA_futrue= GDATA.loc[GDATA["GDKVARIABL"]==1]
    annuity = (
                (1 - config["ANNUITYCG_calculation"]["DEBT_SHARE"]) * config["ANNUITYCG_calculation"]["DISCOUNTRATE"] 
                + config["ANNUITYCG_calculation"]["INTEREST_RATE"] * config["ANNUITYCG_calculation"]["DEBT_SHARE"] * 
                (1 - (1 + config["ANNUITYCG_calculation"]["DISCOUNTRATE"] ) ** (-GDATA_futrue['GDLIFETIME'])) 
                / (1 - (1 + config["ANNUITYCG_calculation"]["INTEREST_RATE"] ) ** (-GDATA_futrue['GDLIFETIME']))
            ) / (1 - (1 + config["ANNUITYCG_calculation"]["DISCOUNTRATE"]) ** (-GDATA_futrue['GDLIFETIME']))

    ANNUITYCGG=[]
    for iter1 in annuity.index:
        ANNUITYCGG.append("ANNUITYCG(CCC,'" + iter1 + "')=" + str(annuity.loc[iter1]) + ";")
            
    ANNUITYCGG_df=pd.DataFrame()
    ANNUITYCGG_df["ANNUITYCG_renewables"]=ANNUITYCGG
    
    
    create_list_inc(ANNUITYCGG_df,"ANNUITYCG_renewables",output_folder + "/to_balmorel",equations=True)



def get_AGKN(AAA,GGG,output_folder):

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


def get_AAA(config,output_folder,techs,turbines):
    AAA_renwable=[]
    for region in config["Regions_to_keep"]["onshore"]:
       
        for tech in techs["wind"] :
            
            if "Existing" in tech:
                AAA_renwable.append(region + "_ONS_Existing_RG1")
                AAA_renwable.append(region + "_ONS_Existing_RG2")
                AAA_renwable.append(region + "_ONS_Existing_RG3")
                #AAA_renwable.append(region + "_ONS_Exisiting")
            
            elif "Future_Onshore" in tech:
                for tur in turbines["onshore"]:
                    for rg in config["RGs_to_keep"][tech]:
                        rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                        AAA_renwable.append(region + "_VRE-ONS_" + tur + "_" + rg)
    
        for tech in techs["solar"] :
                
            if "PV_Rooftop" in tech:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    AAA_renwable.append(region + "_VRE-PV_Rooftop_" + rg )
                    
            elif "PV_Utility_scale_no_tracking" in tech:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    AAA_renwable.append(region + "_VRE-PV_Utility_scale_no_tracking_" + rg )
            
            elif "PV_Utility_scale_tracking" in tech:
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    AAA_renwable.append(region + "_VRE-PV_Utility_scale_tracking_" + rg )   

    for region in config["Regions_to_keep"]["offshore"]:
        for tech in techs["wind"] :

            if "Existing" in tech:
                AAA_renwable.append(region + "_OFF_Existing_RG1")
                AAA_renwable.append(region + "_OFF_Existing_RG2")
                AAA_renwable.append(region + "_OFF_Existing_RG3")

            
            elif "Future_Offshore_bottom_fixed" in tech:
                    for tur in turbines["offshore"]:
                        for rg in config["RGs_to_keep"][tech]:
                            rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                            AAA_renwable.append(region + "_VRE-OFF_bottom_fixed_" + tur + "_" + rg)
        
            elif "Future_Offshore_floating" in tech:
                for tur in turbines["offshore"]:
                    for rg in config["RGs_to_keep"][tech]:
                        rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                        AAA_renwable.append(region + "_VRE-OFF_floating_" + tur + "_" + rg)

    AAA_ren_df=pd.DataFrame()
    AAA_ren_df["AAA_renewable"]=AAA_renwable

    CCCRRRAAA_df=pd.DataFrame()
    CCCRRRAAA_df["CCCRRRAAA_renewable"]=AAA_renwable
    #AAA_ren_df=AAA_ren_df.set_index("AAA_renewable")
    
    #create_list_inc(AAA_ren_df,"AAA_renewable",output_folder + "/to_balmorel")
    #AAA_ren_df.to_csv(output_folder + "/to_balmorel/AAA_renewable.csv")
    create_list_inc(AAA_ren_df,"AAA_renewable",output_folder + "/to_balmorel")
    create_list_inc(CCCRRRAAA_df,"CCCRRRAAA_renewable",output_folder + "/to_balmorel")
    return AAA_ren_df


def get_RRRAAA(AAA_renewable_df,config,output_folder):
    RRRAAA_renewable_df=pd.DataFrame()
    RRRAAA_renewable_df_off=pd.DataFrame()
    #RRR["RRR"]=config["Regions_to_keep"]["offshore"]
    areas=[]
    regions=[]
    for iter1 in config["Regions_to_keep"]["offshore"]:
        
        areas=areas + list(AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]["AAA_renewable"].values[:])
        regions=regions + [iter1.replace("_OFF1","").replace("_OFF2","").replace("_OFF","")]*len(list(AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]["AAA_renewable"].values[:]))
    
    RRRAAA_renewable_df_off["RRR"]=regions
    RRRAAA_renewable_df_off["AAA"]=areas
    
    
    areas=[]
    regions=[]
    for iter1 in config["Regions_to_keep"]["onshore"]:
        
        all_areas= AAA_renewable_df[AAA_renewable_df["AAA_renewable"].str.contains(iter1)]
        areas=areas + list(all_areas[~all_areas["AAA_renewable"].str.contains("OFF")]["AAA_renewable"].values[:])
        regions=regions + [iter1]*len(list(all_areas[~all_areas["AAA_renewable"].str.contains("OFF")]["AAA_renewable"].values[:]))
        
    RRRAAA_renewable_df["RRR"]=regions
    RRRAAA_renewable_df["AAA"]=areas
    
    RRRAAA_renewable_df=pd.concat([RRRAAA_renewable_df,RRRAAA_renewable_df_off])
    
    RRRAAA_renewable_df["RRRAAA_renewable"]=RRRAAA_renewable_df["RRR"] + "." + RRRAAA_renewable_df["AAA"]
    RRRAAA_renewable_df=RRRAAA_renewable_df.drop(["RRR","AAA"],axis=1)
    create_list_inc(RRRAAA_renewable_df,"RRRAAA_renewable",output_folder + "/to_balmorel")

    return RRRAAA_renewable_df
    
    
def get_ALLOWEDINV(AAA_renewable_df,GGG_renewable_df,INVDATASET_renewables_df,turbines,techs,config,output_folder):

    ALLOWEDINV_list=[]
    region=config["Regions_to_keep"]["onshore"][0]
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
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
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
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
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
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
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
                for rg in config["RGs_to_keep"][tech]:
                    rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                    areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( "PV_Rooftop_" + rg, regex=True)] 
                    area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                    ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains("PV-Rooftop_" + rg, regex=True)]
                    str_to_add= area.values[0][0] + ".( \n"   
                    for iter1 in ggg['G_renewable']: 
                        str_to_add=str_to_add + iter1 + "\n "   
                    str_to_add = str_to_add  +") \n "
                    ALLOWEDINV_list.append( str_to_add)
                    
        elif "PV_Utility_scale_no_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
                areas=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains( "PV_Utility_scale_no_tracking_" + rg, regex=True)] 
                area=areas[areas['AAA_renewable'].str.contains(region, regex=True)]
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains("PV-Utility_scale_no_tracking_" + rg, regex=True)]
                str_to_add= area.values[0][0] + ".( \n"   
                for iter1 in ggg['G_renewable']: 
                    str_to_add=str_to_add + iter1 + "\n "   
                str_to_add = str_to_add  +") \n "
                ALLOWEDINV_list.append( str_to_add)
        
        elif "PV_Utility_scale_tracking" in tech:
            for rg in config["RGs_to_keep"][tech]:
                rg=rg.replace("RGA","RG1").replace("RGB","RG2").replace("RGC","RG3")
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



def get_SUBTECHGROUPKPOT(RRRAAA_renewable_df,config,output_folder):

    dfs=[]
    for iter1 in ["Onshore","Solar","Offshore"]:
        dfs.append(pd.read_excel(config["VRE_potentials"],index_col="Region",sheet_name=iter1))
    
    SUBTECHGROUPKPOT=pd.concat(dfs,axis=1)
    
    SUBTECHGROUPKPOT.index.name=""
    SUBTECHGROUPKPOT=SUBTECHGROUPKPOT.replace(np.nan,"")
    SUBTECHGROUPKPOT = SUBTECHGROUPKPOT[SUBTECHGROUPKPOT.index.isin(RRRAAA_renewable_df['Region'])]
    
    create_Table_inc(SUBTECHGROUPKPOT,"SUBTECHGROUPKPOT",output_folder + "/to_balmorel/")
    
def get_DISCOST_H_renewable(AAA_renewable_df,output_folder):
    DISCOST_H=  AAA_renewable_df[AAA_renewable_df['AAA_renewable'].str.contains('OFF_Existing', regex=True)]
    #DISCOST_H[""]=[2]*len(DISCOST_H)
    DISCOST_H = DISCOST_H.copy()
    DISCOST_H.loc[:, ""] = [2] * len(DISCOST_H)
    DISCOST_H=DISCOST_H.set_index("AAA_renewable")
    DISCOST_H.index.name=""
    create_Table_inc(DISCOST_H,"DISCOST_H_renewable",output_folder + "/to_balmorel/")


def create_additional_inc(config_fn,output_folder,start_date):
    with open(config_fn) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)

    output_folder=output_folder+ "/" + str(start_date)
    
    

    
    contents = os.listdir(output_folder)
    wind_criteria = {'Offshore', 'Onshore',"Existing"}
    solar_criteria = {'PV'}
    
    
    techs=dict()
    techs["wind"] = {tech for tech in contents if any(criterion in tech for criterion in wind_criteria)}
    techs["solar"] = {tech for tech in contents if any(criterion in tech for criterion in solar_criteria)}
    
    
    onshore_criteria = {'SP335-HH100', 'SP335-HH150','SP335-HH200','SP277-HH100',"SP277-HH150","SP277-HH200","SP199-HH100","SP199-HH150","SP199-HH200"}
    offshore_criteria = {'SP316-HH155','SP370-HH155'}
    turbines=dict()
    turbines["onshore"] = {turb for turb in config["turbine_to_keep"] if any(criterion in turb for criterion in onshore_criteria)}
    turbines["offshore"] = {turb for turb in config["turbine_to_keep"] if any(criterion in turb for criterion in offshore_criteria)}

    AAA_renewable_df=get_AAA(config,output_folder,techs,turbines)
    RRRAAA_renewable_df=get_RRRAAA(AAA_renewable_df,config,output_folder)
    get_DISCOST_H_renewable(AAA_renewable_df,output_folder)
    GGG_renewable_df=get_GGG(config,output_folder,techs,turbines)
    GDATA=get_GDATA(GGG_renewable_df,turbines,techs,config,output_folder)
    INVDATASET_renewables_df=get_INVDATASET(config,output_folder,techs,turbines)
    INVDATA=get_INVDATA_renewable(INVDATASET_renewables_df,AAA_renewable_df,output_folder)
    get_ALLOWEDINV(AAA_renewable_df,GGG_renewable_df,INVDATASET_renewables_df,turbines,techs,config,output_folder)
    GKFX=get_GKFX(RRRAAA_renewable_df,config,output_folder)
    get_ANNUITYCG(GDATA,config,output_folder)
    get_SUBTECHGROUPKPOT(RRRAAA_renewable_df,config,output_folder)
    #get_AGKN(AAA_renewable_df,GGG_renewable_df,output_folder)

    return AAA_renewable_df,RRRAAA_renewable_df,GKFX,GGG_renewable_df

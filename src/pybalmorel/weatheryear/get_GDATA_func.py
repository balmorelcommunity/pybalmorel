"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""


import pandas as pd
import numpy as np

from .to_inc import create_GGG_GDATASET_inc


def add_unit_size_col(dfs,techs,turbines,config):
    # This function need to be better written 
    unit_size=pd.read_excel(config["VRE_tech_costs"],sheet_name="Standard_Unit_Size", index_col="Technologies")
    dfs = pd.concat([dfs, pd.DataFrame({'Unit_Size': [0.0] * len(dfs)})], axis=1)
    
    
    if "Existing_ERA5_GWA2" in techs["wind"]:
        for rg in ["RG1","RG2","RG3"]:
            mask_unit= (unit_size.index=="Onshore_wind_existing") & (unit_size.RGs==rg)
            existing_mask=   dfs["G_renewable"].str.contains("_ONS_Existing_" + rg, regex=True)
            dfs.loc[existing_mask,"Unit_Size"]= unit_size.loc[mask_unit,2020].values[0]
    
            mask_unit= (unit_size.index=="Offshore_wind_existing") & (unit_size.RGs==rg)
            existing_mask=   dfs["G_renewable"].str.contains("_OFF_Existing_" + rg, regex=True)
            dfs.loc[existing_mask,"Unit_Size"]= unit_size.loc[mask_unit,2020].values[0]
    
    if "Future_Offshore_bottom_fixed" in techs["wind"]:
        for rg in ["RG1","RG2","RG3"]:
            for year in [2020,2030,2040,2050]:
                 mask_unit= (unit_size.index.str.contains("bottom_fixed",regex=True) & (unit_size.RGs==rg))
                 df_mask=  dfs["G_renewable"].str.contains("OFF_bottom_fixed_" + rg + "_Y-"  + str(year), regex=True)
                 dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
    
    if "Future_Offshore_bottom_fixed" in techs["wind"]:
        for rg in ["RG1","RG2","RG3"]:
            for year in [2020,2030,2040,2050]:
                 mask_unit= (unit_size.index.str.contains("bottom_fixed",regex=True) & (unit_size.RGs==rg))
                 df_mask=  dfs["G_renewable"].str.contains("OFF_bottom_fixed_" + rg + "_Y-"  + str(year), regex=True)
                 dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
    
    
    if "Future_Onshore" in techs["wind"]:
        for turb in turbines["onshore"]:
            for rg in ["RG1","RG2","RG3"]:
                for year in [2020,2030,2040,2050]:
                     mask_unit= (unit_size.index.str.contains(turb,regex=True) & (unit_size.RGs==rg))
                     df_mask=  dfs["G_renewable"].str.contains(turb + "_ONS_" + rg + "_Y-" + str(year) , regex=True)
                     dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
    
    if "PV_Rooftop" in techs["solar"]:
        for rg in ["RG1","RG2","RG3"]:
            for year in [2020,2030,2040,2050]:
                mask_unit= (unit_size.index.str.contains("PV-Rooftop",regex=True) & (unit_size.RGs==rg))
                df_mask=  dfs["G_renewable"].str.contains("PV-Rooftop_" + rg + "_Y-" + str(year) , regex=True)
                dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
            df_mask=  dfs["G_renewable"].str.contains("PV-Rooftop_" + rg + "_Existing" , regex=True)
            dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,2020].values[0]
    
    if "PV_Utility_scale_no_tracking" in techs["solar"]:
        for rg in ["RG1","RG2","RG3"]:
            for year in [2020,2030,2040,2050]:
                mask_unit= (unit_size.index.str.contains("PV-Utility_scale_no_tracking",regex=True) & (unit_size.RGs==rg))
                df_mask=  dfs["G_renewable"].str.contains("PV-Utility_scale_no_tracking_" + rg + "_Y-" + str(year) , regex=True)
                dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
            df_mask=  dfs["G_renewable"].str.contains("PV-Utility_scale_no_tracking_" + rg + "_Existing" , regex=True)
            dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,2020].values[0]

    if "PV_Utility_scale_tracking" in techs["solar"]:
        for rg in ["RG1","RG2","RG3"]:
            for year in [2020,2030,2040,2050]:
                mask_unit= (unit_size.index.str.contains("PV-Utility_scale_tracking",regex=True) & (unit_size.RGs==rg))
                df_mask=  dfs["G_renewable"].str.contains("PV-Utility_scale_tracking_" + rg + "_Y-" + str(year) , regex=True)
                dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,year].values[0]
            df_mask=  dfs["G_renewable"].str.contains("PV-Utility_scale_tracking_" + rg + "_Existing" , regex=True)
            dfs.loc[df_mask,"Unit_Size"]= unit_size.loc[mask_unit,2020].values[0]
    return dfs



def get_GDATA(GGG_renewable_df,turbines,techs,config,output_folder):

    costs_dict=dict()
    for iter1 in ["Investment_cost","Annual_O&M","Variable_O&M"]:
        costs_dict[iter1]=pd.read_excel(config["VRE_tech_costs"],sheet_name=iter1, index_col="Technologies")


    dfs=[]
    for tech in techs["wind"] :
        if "Existing" in tech:
            for name1,name2 in [("GNR_WT_WIND_ONS_","Onshore_wind_existing"),("GNR_WT_WIND_OFF_","Offshore_wind_existing")]:
                
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(name1, regex=True)]
                inv_cost= costs_dict["Investment_cost"][costs_dict["Investment_cost"].index.str.contains(name2, regex=True)][2030].values[:]
                ann_OM= costs_dict["Annual_O&M"][costs_dict["Annual_O&M"].index.str.contains(name2, regex=True)][2030].values[:]
                var_OM= costs_dict["Variable_O&M"][costs_dict["Variable_O&M"].index.str.contains(name2, regex=True)][2030].values[:]
                
                inv_cost=  pd.DataFrame([inv_cost]*len(ggg), columns=['Investment_cost'])
                ann_OM=  pd.DataFrame([ann_OM]*len(ggg), columns=['Annual_O&M'])
                var_OM=  pd.DataFrame([var_OM]*len(ggg), columns=['Variable_O&M'])
                from_year=  pd.DataFrame([np.NaN]*len(ggg), columns=['from_year'])  
                life_time=  pd.DataFrame( [np.NaN]*len(ggg), columns=['life_time'])    
                last_year= pd.DataFrame([np.NaN ]*len(ggg), columns=['last_year'])  

                
                dfs.append(pd.concat([ggg.reset_index(drop=True),inv_cost,ann_OM,var_OM,from_year,life_time,last_year],ignore_index=False,axis=1))
                

        else:
            if "Future_Onshore" in tech:
                tur_onoff="onshore"
                ggg_name="_ONS_"
                cost_name=""
            elif "Future_Offshore_bottom_fixed" in tech:
                tur_onoff="offshore"
                ggg_name="_OFF_bottom_fixed_"
                cost_name="_bottom_fixed"
            elif "Future_Offshore_floating" in tech:
                tur_onoff="offshore"
                ggg_name="_OFF_floating_"
                cost_name="_floating"
            
            for tur in turbines[tur_onoff]:
                ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(tur + ggg_name, regex=True)]
                years = ggg['G_renewable'].str.split('Y-').str[-1].unique()
                for year in years:
                    ggg_y=ggg[ggg['G_renewable'].str.contains(year, regex=True)]
                    
                    inv_cost= costs_dict["Investment_cost"][costs_dict["Investment_cost"].index.str.contains(tur+ cost_name, regex=True)][int(year)].values[:]
                    ann_OM= costs_dict["Annual_O&M"][costs_dict["Annual_O&M"].index.str.contains(tur+ cost_name, regex=True)][int(year)].values[:]
                    var_OM= costs_dict["Variable_O&M"][costs_dict["Variable_O&M"].index.str.contains(tur+ cost_name, regex=True)][int(year)].values[:]
                    
                    inv_cost=  pd.DataFrame([inv_cost]*len(ggg_y), columns=['Investment_cost'])
                    ann_OM=  pd.DataFrame([ann_OM]*len(ggg_y), columns=['Annual_O&M'])
                    var_OM=  pd.DataFrame([var_OM]*len(ggg_y), columns=['Variable_O&M'])
                    from_year=  pd.DataFrame([year]*len(ggg_y), columns=['from_year'])  
                    life_time=  pd.DataFrame( [27 if year==2020 else 30]*len(ggg_y), columns=['life_time'])    
                    last_year= pd.DataFrame([int(year) + 9 ]*len(ggg_y), columns=['last_year'])  

                    dfs.append(pd.concat([ggg_y.reset_index(drop=True),inv_cost,ann_OM,var_OM,from_year,life_time,last_year],ignore_index=False,axis=1))
                

    for tech in techs["solar"] :  

        if "PV_Rooftop" in tech:
            ggg_name="PV-Rooftop_"
            cost_name="PV-Rooftop"
        elif "PV_Utility_scale_no_tracking" in tech:
            ggg_name="PV-Utility_scale_no_tracking_"
            cost_name="PV-Utility_scale_no_tracking"
        elif "PV_Utility_scale_tracking" in tech:
            ggg_name="PV-Utility_scale_tracking_"
            cost_name="PV-Utility_scale_tracking"

            
        ggg=GGG_renewable_df[GGG_renewable_df['G_renewable'].str.contains(ggg_name , regex=True)]
        years = ggg['G_renewable'].str.split('Y-').str[-1].unique()
        years = np.array([x for x in years if 'Existing' not in x])
        for year in years:
            ggg_y=ggg[ggg['G_renewable'].str.contains(year, regex=True)]

            if year=="2020":
                ggg_y=pd.concat([ggg_y,ggg[ggg['G_renewable'].str.contains("Existing", regex=True)]]) 
            
            inv_cost= costs_dict["Investment_cost"][costs_dict["Investment_cost"].index.str.contains(cost_name, regex=True)][int(year)].values[:]
            ann_OM= costs_dict["Annual_O&M"][costs_dict["Annual_O&M"].index.str.contains(cost_name, regex=True)][int(year)].values[:]
            var_OM= costs_dict["Variable_O&M"][costs_dict["Variable_O&M"].index.str.contains( cost_name, regex=True)][int(year)].values[:]
            
            inv_cost=  pd.DataFrame([inv_cost]*len(ggg_y), columns=['Investment_cost'])
            ann_OM=  pd.DataFrame([ann_OM]*len(ggg_y), columns=['Annual_O&M'])
            var_OM=  pd.DataFrame([var_OM]*len(ggg_y), columns=['Variable_O&M'])
            from_year=  pd.DataFrame([year]*len(ggg_y), columns=['from_year'])  
            life_time=  pd.DataFrame( [27 if year==2020 else 30]*len(ggg_y), columns=['life_time'])    
            last_year= pd.DataFrame([int(year) + 9 ]*len(ggg_y), columns=['last_year'])  

            df_toadd=pd.concat([ggg_y.reset_index(drop=True),inv_cost,ann_OM,var_OM,from_year,life_time,last_year],ignore_index=False,axis=1)
            df_toadd.loc[df_toadd['G_renewable'].str.contains('Existing'), ['from_year', 'life_time', 'last_year']] = np.nan
            dfs.append(df_toadd)
                    
    dfs=pd.concat(dfs)


    Fuel_efficiency=  pd.DataFrame([1]*len(dfs), columns=['Fuel_efficiency'])
    allowed_decomissione=pd.DataFrame([1]*len(dfs), columns=['allowed_decomissione'])

    dfs=pd.concat([dfs.reset_index(drop=True),Fuel_efficiency,allowed_decomissione,],axis=1)


    pv_mask= dfs["G_renewable"][dfs["G_renewable"].str.contains("PV", regex=True)]
    dfs.loc[pv_mask.index,"technology_group"]="SOLARPV"
    dfs.loc[pv_mask.index,"generation_type"]="GSOLE"
    dfs.loc[pv_mask.index,"fuel_type"]="SUN"
    #dfs.loc[pv_mask.index,"GDUCUNITSIZE"]=1


    wnd_mask= dfs["G_renewable"][dfs["G_renewable"].str.contains("_ONS_", regex=True)]
    dfs.loc[wnd_mask.index,"technology_group"]="WINDTURBINE_ONSHORE"
    dfs.loc[wnd_mask.index,"generation_type"]="GWND"
    dfs.loc[wnd_mask.index,"fuel_type"]="WIND"
    #dfs.loc[wnd_mask.index,"GDUCUNITSIZE"]=3.15

    wnd_mask= dfs["G_renewable"][dfs["G_renewable"].str.contains("_OFF_", regex=True)]
    dfs.loc[wnd_mask.index,"technology_group"]="WINDTURBINE_OFFSHORE"
    dfs.loc[wnd_mask.index,"generation_type"]="GWND"
    dfs.loc[wnd_mask.index,"fuel_type"]="WIND"
    #dfs.loc[wnd_mask.index,"GDUCUNITSIZE"]=20

    for rg in["RG1","RG2","RG3"]:
        on = dfs["G_renewable"][  (dfs["G_renewable"].str.contains(rg, regex=True)) &  ~( dfs["G_renewable"].str.contains("_OFF_", regex=True))]  
        dfs.loc[on.index,"subtechnology_group"]=rg
        off = dfs["G_renewable"][  (dfs["G_renewable"].str.contains(rg, regex=True)) &  ( dfs["G_renewable"].str.contains("_OFF_", regex=True))]  
        dfs.loc[off.index,"subtechnology_group"]=rg + "_OFF"

    existing_mask=dfs["Investment_cost"]==0
    dfs.loc[existing_mask,"variable_capacity"]=0
    dfs.loc[~existing_mask,"variable_capacity"]=1

    pv_existing_mask=   (dfs["G_renewable"].str.contains("PV", regex=True)) &  ( dfs["G_renewable"].str.contains("Existing", regex=True))
    dfs.loc[pv_existing_mask,"variable_capacity"]=0
    dfs.loc[pv_existing_mask,"Investment_cost"]=0


    dfs=add_unit_size_col(dfs,techs,turbines,config)
    

    dfs=dfs.rename(columns={
        "Investment_cost":"GDINVCOST0",
        "Annual_O&M": "GDOMFCOST0",
        "Variable_O&M": "GDOMVCOST0",
        "from_year": "GDFROMYEAR",
        "life_time": "GDLIFETIME",
        "last_year": "GDLASTYEAR",
        "Fuel_efficiency": "GDFE",
        "allowed_decomissione": "GDDECOM",
        "technology_group":"GDTECHGROUP",
        "generation_type":"GDTYPE",
        "fuel_type":"GDFUEL",
        "subtechnology_group":"GDSUBTECHGROUP",
        "variable_capacity":"GDKVARIABL",
        "Unit_Size": "GDUCUNITSIZE"
    })

    column_names_needed = [
        "GDTYPE", "GDFUEL", "GDCV", "GDCB", "GDFE", "GDCH4", "GDNOX", "GDDESO2", 
        "GDINVCOST0", "GDOMFCOST0", "GDOMVCOST0", "GDOMVCOSTIN", "GDFROMYEAR", "GDLIFETIME", 
        "GDKVARIABL", "GDLASTYEAR", "GDMOTHBALL", "GDSTOHLOAD", "GDSTOHUNLD", "GDCOMB", 
        "GDCOMBGUP", "GDCOMBGSHAREK1", "GDCOMBFUP", "GDCOMBFSHAREK1", "GDCOMBGSHARELO", 
        "GDCOMBGSHAREUP", "GDCOMBFSHARELO", "GDCOMBFSHAREUP", "GDCOMBSK", "GDCOMBSLO", 
        "GDCOMBSUP", "GDCOMBKRES", "GDCOMBFCAP", "GDLOADLOSS", "GDSTOLOSS", "GDUC", 
        "GDUCUNITSIZE", "GDUCGMIN", "GDUCUCOST", "GDUCCOST0", "GDUCF0", "GDUCDCOST", 
        "GDUCDTMIN", "GDUCUTMIN", "GDUCDURD", "GDUCDURU", "GDUCRAMPU", "GDUCRAMPD", 
        "GDBYPASSC", "GDTECHGROUP", "GDSUBTECHGROUP", "GDDECOM", "GDFOR", "GDPLANMAINT"
    ]

    for iter1 in column_names_needed:
        if iter1 not in dfs.columns:
            add=pd.DataFrame([np.nan]*len(dfs), columns=[iter1])
            dfs=pd.concat([dfs.reset_index(drop=True),add],axis=1)

    dfs=dfs.set_index("G_renewable")
    dfs=dfs[column_names_needed]
    dfs=dfs.fillna("")
    dfs.index.name=""

    create_GGG_GDATASET_inc(dfs,"GDATA_renewable",output_folder +"/to_balmorel")

    return dfs

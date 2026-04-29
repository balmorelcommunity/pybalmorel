"""
Functions to create the GDATA table and .inc file for renewable generators.

GDATA is a Balmorel parameter that holds generator attribute data, including
technology group, fuel type, investment costs, fixed and variable O&M costs,
lifetime, capacity variability flags, and unit commitment parameters.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

import os

import numpy as np
import pandas as pd

from .to_inc import create_GGG_GDATASET_inc

INVESTMENT_YEARS = [2020, 2030, 2040, 2050]
RG_GROUPS = ["RG1", "RG2", "RG3"]


def _build_cost_columns(
    costs_dict: dict, name: str, year: int, n_rows: int
) -> tuple:
    """Look up cost values for *name* and *year* and replicate them for *n_rows* generators.

    Args:
        costs_dict: dict of cost DataFrames keyed by 'Investment_cost', 'Annual_O&M',
            and 'Variable_O&M'.
        name: substring to match against the technology index.
        year: investment year column to read from each cost sheet.
        n_rows: number of generators to replicate costs for.

    Returns:
        Tuple of (inv_cost, ann_om, var_om) single-column DataFrames.
    """
    inv = costs_dict["Investment_cost"][
        costs_dict["Investment_cost"].index.str.contains(name, regex=True)
    ][year].values[:]
    ann = costs_dict["Annual_O&M"][
        costs_dict["Annual_O&M"].index.str.contains(name, regex=True)
    ][year].values[:]
    var = costs_dict["Variable_O&M"][
        costs_dict["Variable_O&M"].index.str.contains(name, regex=True)
    ][year].values[:]
    return (
        pd.DataFrame([inv] * n_rows, columns=["Investment_cost"]),
        pd.DataFrame([ann] * n_rows, columns=["Annual_O&M"]),
        pd.DataFrame([var] * n_rows, columns=["Variable_O&M"]),
    )


def add_unit_size_col(
    dfs: pd.DataFrame,
    techs: dict,
    turbines: dict,
    config: dict,
) -> pd.DataFrame:
    """Append a 'Unit_Size' column to *dfs* from the Standard_Unit_Size sheet.

    Args:
        dfs: generator DataFrame with a 'G_renewable' column.
        techs: dict with keys 'wind' and 'solar' listing active technology names.
        turbines: dict with keys 'onshore' and 'offshore' listing turbine names.
        config: workflow configuration dict; must contain 'VRE_tech_costs' path.

    Returns:
        *dfs* with an added 'Unit_Size' column.
    """
    unit_size = pd.read_excel(
        config["VRE_tech_costs"], sheet_name="Standard_Unit_Size", index_col="Technologies"
    )
    dfs = pd.concat([dfs, pd.DataFrame({"Unit_Size": [0.0] * len(dfs)})], axis=1)

    if "Existing_ERA5_GWA2" in techs["wind"]:
        for rg in RG_GROUPS:
            for prefix, label in [
                ("_ONS_Existing_", "Onshore_wind_existing"),
                ("_OFF_Existing_", "Offshore_wind_existing"),
            ]:
                mask_unit = (unit_size.index == label) & (unit_size.RGs == rg)
                gen_mask = dfs["G_renewable"].str.contains(prefix + rg, regex=True)
                dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, 2020].values[0]

    if "Future_Offshore_bottom_fixed" in techs["wind"]:
        for rg in RG_GROUPS:
            for year in INVESTMENT_YEARS:
                mask_unit = unit_size.index.str.contains("bottom_fixed", regex=True) & (
                    unit_size.RGs == rg
                )
                gen_mask = dfs["G_renewable"].str.contains(
                    "OFF_bottom_fixed_" + rg + "_Y-" + str(year), regex=True
                )
                dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, year].values[0]

    if "Future_Offshore_floating" in techs["wind"]:
        for rg in RG_GROUPS:
            for year in INVESTMENT_YEARS:
                mask_unit = unit_size.index.str.contains("floating", regex=True) & (
                    unit_size.RGs == rg
                )
                gen_mask = dfs["G_renewable"].str.contains(
                    "OFF_floating_" + rg + "_Y-" + str(year), regex=True
                )
                dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, year].values[0]

    if "Future_Onshore" in techs["wind"]:
        for turb in turbines["onshore"]:
            for rg in RG_GROUPS:
                for year in INVESTMENT_YEARS:
                    mask_unit = unit_size.index.str.contains(turb, regex=True) & (
                        unit_size.RGs == rg
                    )
                    gen_mask = dfs["G_renewable"].str.contains(
                        turb + "_ONS_" + rg + "_Y-" + str(year), regex=True
                    )
                    dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, year].values[0]

    for solar_tech, label in [
        ("PV_Rooftop", "PV-Rooftop"),
        ("PV_Utility_scale_no_tracking", "PV-Utility_scale_no_tracking"),
        ("PV_Utility_scale_tracking", "PV-Utility_scale_tracking"),
    ]:
        if solar_tech in techs["solar"]:
            for rg in RG_GROUPS:
                mask_unit = unit_size.index.str.contains(label, regex=True) & (
                    unit_size.RGs == rg
                )
                for year in INVESTMENT_YEARS:
                    gen_mask = dfs["G_renewable"].str.contains(
                        label + "_" + rg + "_Y-" + str(year), regex=True
                    )
                    dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, year].values[0]
                gen_mask = dfs["G_renewable"].str.contains(
                    label + "_" + rg + "_Existing", regex=True
                )
                dfs.loc[gen_mask, "Unit_Size"] = unit_size.loc[mask_unit, 2020].values[0]

    return dfs



def build_GDATA(
    GGG_renewable_df: pd.DataFrame,
    turbines: dict,
    techs: dict,
    config: dict,
    output_folder: str,
) -> pd.DataFrame:
    """Build GDATA table and write the corresponding .inc file for renewable generators.

    Reads investment cost, fixed O&M, and variable O&M from the VRE cost Excel workbook
    and assembles them with fuel type, technology group, lifetime, and capacity flags
    into a GDATA-formatted DataFrame, then writes a GDATA_renewable.inc file.

    Args:
        GGG_renewable_df: DataFrame with a 'G_renewable' column listing generator names.
        turbines: dict with keys 'onshore' and 'offshore' listing turbine names.
        techs: dict with keys 'wind' and 'solar' listing active technology names.
        config: workflow configuration dict; must contain 'VRE_tech_costs' path.
        output_folder: root output directory; the .inc file is written to
            <output_folder>/to_balmorel/.

    Returns:
        GDATA DataFrame indexed by generator name.
    """
    costs_dict = {}
    for cost_type in ["Investment_cost", "Annual_O&M", "Variable_O&M"]:
        costs_dict[cost_type] = pd.read_excel(
            config["VRE_tech_costs"], sheet_name=cost_type, index_col="Technologies"
        )

    dfs = []
    for tech in techs["wind"]:
        if "Existing" in tech:
            for name1, name2 in [
                ("GNR_WT_WIND_ONS_", "Onshore_wind_existing"),
                ("GNR_WT_WIND_OFF_", "Offshore_wind_existing"),
            ]:
                ggg = GGG_renewable_df[
                    GGG_renewable_df["G_renewable"].str.contains(name1, regex=True)
                ]
                inv_cost, ann_om, var_om = _build_cost_columns(costs_dict, name2, 2030, len(ggg))
                from_year = pd.DataFrame([np.nan] * len(ggg), columns=["from_year"])
                life_time = pd.DataFrame([np.nan] * len(ggg), columns=["life_time"])
                last_year = pd.DataFrame([np.nan] * len(ggg), columns=["last_year"])
                dfs.append(
                    pd.concat(
                        [ggg.reset_index(drop=True), inv_cost, ann_om, var_om,
                         from_year, life_time, last_year],
                        axis=1,
                    )
                )

        else:
            if "Future_Onshore" in tech:
                tur_onoff = "onshore"
                ggg_name = "_ONS_"
                cost_name = ""
            elif "Future_Offshore_bottom_fixed" in tech:
                tur_onoff = "offshore"
                ggg_name = "_OFF_bottom_fixed_"
                cost_name = "_bottom_fixed"
            elif "Future_Offshore_floating" in tech:
                tur_onoff = "offshore"
                ggg_name = "_OFF_floating_"
                cost_name = "_floating"

            for tur in turbines[tur_onoff]:
                ggg = GGG_renewable_df[
                    GGG_renewable_df["G_renewable"].str.contains(tur + ggg_name, regex=True)
                ]
                years = ggg["G_renewable"].str.split("Y-").str[-1].unique()
                for year in years:
                    ggg_y = ggg[ggg["G_renewable"].str.contains(year, regex=True)]
                    inv_cost, ann_om, var_om = _build_cost_columns(
                        costs_dict, tur + cost_name, int(year), len(ggg_y)
                    )
                    from_year = pd.DataFrame([year] * len(ggg_y), columns=["from_year"])
                    life_time = pd.DataFrame(
                        [27 if year == "2020" else 30] * len(ggg_y), columns=["life_time"]
                    )
                    last_year = pd.DataFrame(
                        [int(year) + 9] * len(ggg_y), columns=["last_year"]
                    )
                    dfs.append(
                        pd.concat(
                            [ggg_y.reset_index(drop=True), inv_cost, ann_om, var_om,
                             from_year, life_time, last_year],
                            axis=1,
                        )
                    )

    for tech in techs["solar"]:
        if "PV_Rooftop" in tech:
            ggg_name = "PV-Rooftop_"
            cost_name = "PV-Rooftop"
        elif "PV_Utility_scale_no_tracking" in tech:
            ggg_name = "PV-Utility_scale_no_tracking_"
            cost_name = "PV-Utility_scale_no_tracking"
        elif "PV_Utility_scale_tracking" in tech:
            ggg_name = "PV-Utility_scale_tracking_"
            cost_name = "PV-Utility_scale_tracking"

        ggg = GGG_renewable_df[
            GGG_renewable_df["G_renewable"].str.contains(ggg_name, regex=True)
        ]
        years = ggg["G_renewable"].str.split("Y-").str[-1].unique()
        years = np.array([y for y in years if "Existing" not in y])
        for year in years:
            ggg_y = ggg[ggg["G_renewable"].str.contains(year, regex=True)]
            if year == "2020":
                ggg_y = pd.concat(
                    [ggg_y, ggg[ggg["G_renewable"].str.contains("Existing", regex=True)]]
                )
            inv_cost, ann_om, var_om = _build_cost_columns(
                costs_dict, cost_name, int(year), len(ggg_y)
            )
            from_year = pd.DataFrame([year] * len(ggg_y), columns=["from_year"])
            life_time = pd.DataFrame(
                [27 if year == "2020" else 30] * len(ggg_y), columns=["life_time"]
            )
            last_year = pd.DataFrame([int(year) + 9] * len(ggg_y), columns=["last_year"])
            df_to_add = pd.concat(
                [ggg_y.reset_index(drop=True), inv_cost, ann_om, var_om,
                 from_year, life_time, last_year],
                axis=1,
            )
            df_to_add.loc[
                df_to_add["G_renewable"].str.contains("Existing"),
                ["from_year", "life_time", "last_year"],
            ] = np.nan
            dfs.append(df_to_add)

    dfs = pd.concat(dfs)

    fuel_efficiency = pd.DataFrame([1] * len(dfs), columns=["Fuel_efficiency"])
    allowed_decommission = pd.DataFrame([1] * len(dfs), columns=["allowed_decommission"])
    dfs = pd.concat(
        [dfs.reset_index(drop=True), fuel_efficiency, allowed_decommission], axis=1
    )

    pv_mask = dfs["G_renewable"][dfs["G_renewable"].str.contains("PV", regex=True)]
    dfs.loc[pv_mask.index, "technology_group"] = "SOLARPV"
    dfs.loc[pv_mask.index, "generation_type"] = "GSOLE"
    dfs.loc[pv_mask.index, "fuel_type"] = "SUN"

    wnd_mask = dfs["G_renewable"][dfs["G_renewable"].str.contains("_ONS_", regex=True)]
    dfs.loc[wnd_mask.index, "technology_group"] = "WINDTURBINE_ONSHORE"
    dfs.loc[wnd_mask.index, "generation_type"] = "GWND"
    dfs.loc[wnd_mask.index, "fuel_type"] = "WIND"

    wnd_mask = dfs["G_renewable"][dfs["G_renewable"].str.contains("_OFF_", regex=True)]
    dfs.loc[wnd_mask.index, "technology_group"] = "WINDTURBINE_OFFSHORE"
    dfs.loc[wnd_mask.index, "generation_type"] = "GWND"
    dfs.loc[wnd_mask.index, "fuel_type"] = "WIND"

    for rg in RG_GROUPS:
        on = dfs["G_renewable"][
            dfs["G_renewable"].str.contains(rg, regex=True)
            & ~dfs["G_renewable"].str.contains("_OFF_", regex=True)
        ]
        dfs.loc[on.index, "subtechnology_group"] = rg
        off = dfs["G_renewable"][
            dfs["G_renewable"].str.contains(rg, regex=True)
            & dfs["G_renewable"].str.contains("_OFF_", regex=True)
        ]
        dfs.loc[off.index, "subtechnology_group"] = rg + "_OFF"

    existing_mask = dfs["Investment_cost"] == 0
    dfs.loc[existing_mask, "variable_capacity"] = 0
    dfs.loc[~existing_mask, "variable_capacity"] = 1

    pv_existing_mask = (
        dfs["G_renewable"].str.contains("PV", regex=True)
        & dfs["G_renewable"].str.contains("Existing", regex=True)
    )
    dfs.loc[pv_existing_mask, "variable_capacity"] = 0
    dfs.loc[pv_existing_mask, "Investment_cost"] = 0

    dfs = add_unit_size_col(dfs, techs, turbines, config)

    dfs = dfs.rename(
        columns={
            "Investment_cost": "GDINVCOST0",
            "Annual_O&M": "GDOMFCOST0",
            "Variable_O&M": "GDOMVCOST0",
            "from_year": "GDFROMYEAR",
            "life_time": "GDLIFETIME",
            "last_year": "GDLASTYEAR",
            "Fuel_efficiency": "GDFE",
            "allowed_decommission": "GDDECOM",
            "technology_group": "GDTECHGROUP",
            "generation_type": "GDTYPE",
            "fuel_type": "GDFUEL",
            "subtechnology_group": "GDSUBTECHGROUP",
            "variable_capacity": "GDKVARIABL",
            "Unit_Size": "GDUCUNITSIZE",
        }
    )

    column_names_needed = [
        "GDTYPE", "GDFUEL", "GDCV", "GDCB", "GDFE", "GDCH4", "GDNOX", "GDDESO2",
        "GDINVCOST0", "GDOMFCOST0", "GDOMVCOST0", "GDOMVCOSTIN", "GDFROMYEAR", "GDLIFETIME",
        "GDKVARIABL", "GDLASTYEAR", "GDMOTHBALL", "GDSTOHLOAD", "GDSTOHUNLD", "GDCOMB",
        "GDCOMBGUP", "GDCOMBGSHAREK1", "GDCOMBFUP", "GDCOMBFSHAREK1", "GDCOMBGSHARELO",
        "GDCOMBGSHAREUP", "GDCOMBFSHARELO", "GDCOMBFSHAREUP", "GDCOMBSK", "GDCOMBSLO",
        "GDCOMBSUP", "GDCOMBKRES", "GDCOMBFCAP", "GDLOADLOSS", "GDSTOLOSS", "GDUC",
        "GDUCUNITSIZE", "GDUCGMIN", "GDUCUCOST", "GDUCCOST0", "GDUCF0", "GDUCDCOST",
        "GDUCDTMIN", "GDUCUTMIN", "GDUCDURD", "GDUCDURU", "GDUCRAMPU", "GDUCRAMPD",
        "GDBYPASSC", "GDTECHGROUP", "GDSUBTECHGROUP", "GDDECOM", "GDFOR", "GDPLANMAINT",
    ]

    for col in column_names_needed:
        if col not in dfs.columns:
            dfs = pd.concat(
                [dfs.reset_index(drop=True), pd.DataFrame([np.nan] * len(dfs), columns=[col])],
                axis=1,
            )

    dfs = dfs.set_index("G_renewable")
    dfs = dfs[column_names_needed]
    dfs = dfs.fillna("")
    dfs.index.name = ""

    create_GGG_GDATASET_inc(dfs, "GDATA_renewable", os.path.join(output_folder, "to_balmorel"))

    return dfs

"""
General Helper Functions

Created on 18/08/2023 by
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Union
from functools import wraps
from pybalmorel import MainResults
import shutil
import os
import time
import sys
import configparser
import click
from pathlib import Path

# %% ------------------------------- ###
###          1. Logging etc.        ###
### ------------------------------- ###


### 1.0 Logging error
def ErrorLog(succes, N_errors, error_log, error_message):
    """
    If a script had an error, log it

    Args:
        succes (CompletedProcess): The subprocess status
        N_errors (Integer): Amount of errors so far
        error_log (String): The error log to append
        error_message (String): The error message to append, if there's an error

    Returns:
        Nerrors: The amount of errors after subprocess
        error_log: The error log after subprocess
    """
    if succes.returncode != 0:
        N_errors += 1
        error_log = "\n".join([error_log, error_message])

    return N_errors, error_log


### 1.1 Log Process Time
def log_process_time(file_path, iteration, process_name, delta_time):
    if os.path.exists(file_path):
        with open(file_path, "a") as file:
            file.write("%d,%s,%d\n" % (iteration, process_name, delta_time))
    else:
        with open(file_path, "w") as file:
            file.write("Iteration,Process,Time\n")
            file.write("%d,%s,%d\n" % (iteration, process_name, delta_time))


def get_balmorel_time_and_hours(result: MainResults):
    """Get the temporal resolution using all_endofmodel.gdx

    Args:
        result (MainResults): _description_

    Returns:
        pd.MultiIndex, list: pandas index of Balmorel timeslices, list of corresponding hours in a year
    """

    # Get balmorel_index from electricity prices, which are defined for all hours since it's a dual variable
    elprices = result.get_result("EL_PRICE_YCRST")
    S, T = pd.Series(elprices["Season"].unique()), pd.Series(elprices["Time"].unique())
    balmorel_index = pd.MultiIndex.from_product(
        (list(S), list(T)), names=("Season", "Time")
    )

    # Convert to hours in a year
    weeks = S.str.lstrip("S").astype(int)
    hours = T.str.lstrip("T").astype(int)
    hour_index = [(week - 1) * 168 + hour - 1 for week in weeks for hour in hours]

    return balmorel_index, hour_index


S_list = ["S0%d" % i for i in range(1, 10)] + ["S%d" % i for i in range(10, 53)]
T_list = (
    ["T00%d" % i for i in range(1, 10)]
    + ["T0%d" % i for i in range(10, 100)]
    + ["T%d" % i for i in range(100, 169)]
)
ST_index = pd.MultiIndex.from_product((S_list, T_list))

# %% ------------------------------- ###
###           2. Dataframes         ###
### ------------------------------- ###


### 1.2 Create a filter for either all values or only the highest and lowest value in a column
def filter_low_max(df, col="none", plot_all=True):
    """_summary_

    Args:
        df (_type_): _description_
        col (_type_): _description_
        filter_type (bool, optional): _description_. Defaults to True.

    Returns:
        _type_: _description_
    """
    if plot_all:
        print("All values included")
        idx = df.iloc[:, 0] == df.iloc[:, 0]
    else:
        if col != "none":
            idx = (df[col] == df[col].max()) | (df[col] == df[col].min())
        else:
            print("Wrong column specified where max and min values should be filtered!")
    return idx


def store_capcred(CC, i, year, BalmArea, tech, tech_cap, val):
    """Takes the capacity credit dataframe and stores a new capacity credit for iteration i

    Args:
        CC (dataframe): Dataframe comprising all capacity credits
        i (int): The current iteration
        BalmArea (str): The Balmorel Region
        tech (str): The column (Technology or receiving region)
        tech_cap (float): The capacity of the technology or link
        val (float): Capacity credit (float between 0 and 1)

    Returns:
        _type_: _description_
    """
    # Save capacity credit
    if tech_cap > 1e-6:
        CC.loc[(i, year, BalmArea), tech] = val
    # If there is no capacity and it is the first iteration, select a capcred of 1
    elif (tech_cap < 1e-6) & (i == 0):
        CC.loc[(i, year, BalmArea), tech] = 1
    # Otherwise - capacity credit from last iteration will be used
    else:
        # print('using last iteration CC')
        CC.loc[(i, year, BalmArea), tech] = CC.loc[(i - 1, year, BalmArea), tech]

    return CC


# %% ------------------------------- ###
###            3. Analysis          ###
### ------------------------------- ###


def get_combined_obj_value(
    results: MainResults,
    capital_scenario_string: str = "capacity",
    operational_scenario_string: str = "dispatch",
    return_capex_opex_dfs: bool = False,
):
    df = results.get_result("OBJ_YCR")
    operational_costs = df.query(
        f'Scenario.str.contains("{operational_scenario_string}") and not (Category.str.contains("CAPITAL") or Category.str.contains("FIXED"))'
    )
    capital_costs = df.query(
        f'Scenario.str.contains("{capital_scenario_string}") and (Category.str.contains("CAPITAL") or Category.str.contains("FIXED"))'
    )
    obj_value = capital_costs.Value.sum() + operational_costs.Value.sum()

    if return_capex_opex_dfs:
        return obj_value, capital_costs, operational_costs
    else:
        return obj_value


# %% ------------------------------- ###
###        4. Antares Input         ###
### ------------------------------- ###


def set_cluster_attribute(
    name: str, attribute: str, value: any, node: str, cluster_type: str = "thermal"
):
    """Set the attribute of a

    Args:
        name (str): The name of the cluster element, i.e. the clusterfile section
        attribute (str): The attribute of the cluster element to set, i.e. the clusterfile option
        value (any): The value to set
        node (str): The node containing the cluster
        cluster_type (str, optional): The type of cluster, e.g. 'thermal', 'renewables'... Defaults to 'thermal'.
    """
    discharge_config = configparser.ConfigParser()
    discharge_config.read(
        "Antares/input/%s/clusters/%s/list.ini" % (cluster_type, node.lower())
    )
    discharge_config.set(name, attribute, str(value))
    with open(
        "Antares/input/%s/clusters/%s/list.ini" % (cluster_type, node.lower()), "w"
    ) as f:
        discharge_config.write(f)
    discharge_config.clear()


def create_transmission_input(
    wk_dir, ant_study, area_from, area_to, trans_cap, hurdle_costs
):
    area_from = area_from.lower()
    area_to = area_to.lower()
    try:
        f = open(
            wk_dir
            + ant_study
            + "/input/links/%s/%s_parameters.txt" % (area_from, area_to)
        )
        p = (
            wk_dir
            + ant_study
            + "/input/links/%s/%s_parameters.txt" % (area_from, area_to)
        )
        pcap_dir = (
            wk_dir
            + ant_study
            + "/input/links/%s/capacities/%s_direct.txt" % (area_from, area_to)
        )
        pcap_ind = (
            wk_dir
            + ant_study
            + "/input/links/%s/capacities/%s_indirect.txt" % (area_from, area_to)
        )
    except FileNotFoundError:
        f = open(
            wk_dir
            + ant_study
            + "/input/links/%s/%s_parameters.txt" % (area_to, area_from)
        )
        p = (
            wk_dir
            + ant_study
            + "/input/links/%s/%s_parameters.txt" % (area_to, area_from)
        )
        pcap_dir = (
            wk_dir
            + ant_study
            + "/input/links/%s/capacities/%s_direct.txt" % (area_to, area_from)
        )
        pcap_ind = (
            wk_dir
            + ant_study
            + "/input/links/%s/capacities/%s_indirect.txt" % (area_to, area_from)
        )

    # Write Parameters
    with open(p, "w") as f:
        for k in range(8760):
            f.write("%0.2f\t%0.2f\t0\t0\t0\t0\n" % (hurdle_costs, hurdle_costs))

    # Write Capacities
    if type(trans_cap) != list:
        with open(pcap_dir, "w") as f:
            for k in range(8760):
                f.write(str(int(trans_cap)) + "\n")
        with open(pcap_ind, "w") as f:
            for k in range(8760):
                f.write(str(int(trans_cap)) + "\n")
    else:
        with open(pcap_dir, "w") as f:
            for k in range(8760):
                f.write(str(int(trans_cap[0])) + "\n")
        with open(pcap_ind, "w") as f:
            for k in range(8760):
                f.write(str(int(trans_cap[1])) + "\n")


def log_time():
    string = time.strftime("[%Y-%m-%d %H:%M]:", tuple(time.localtime()))
    return string


def log(*message: str | list):
    print(log_time(), *message)


def get_marginal_costs(
    year,
    region,
    cap,
    idx_cap,
    fuel,
    GDATA,
    FPRICE,
    FDATA,
    EMI_POL,
    ANNUITYCG,
    include_capital_costs: bool = True,
):
    """Gets average marginal cost of generators in cap[idx_cap], provided VOM, fuel and emission policy data

    Args:
        year (str): Year in string
        cap (pd.DataFrame): All capacities
        idx_cap (pd.DataFrame): Index for capacities
        fuel (str): Fuel for generator
        GDATA (pd.DataFrame): Technology data
        FPRICE (pd.DataFrame): Fuel prices
        FDATA (pd.DataFrame): Fuel data
        EMI_POL (pd.DataFrame): Emission policy (if carbon tax)
        ANNUITYCG (pd.DataFrame): Annuity (if capital cost included)
        include_capital_costs (bool): Include CAPEX and Fixed O&M to marginal price?
    """
    ## Weighting capacities on highest data level (G)
    totalcap = cap.loc[idx_cap, "Value"].sum() * 1e3  # MW
    country = cap.loc[idx_cap, "C"].unique()[0]  # Should just be one country

    print(country)

    mc_cost_temp = 0
    for G in cap[idx_cap].G.unique():
        Gcap = cap.loc[idx_cap & (cap.G == G), "Value"].sum() * 1e3  # MW

        if Gcap < 1e-5:
            continue

        # VOM defined on output
        try:
            mc_cost_temp += GDATA.loc[(G, "GDOMVCOST0"), "Value"] * Gcap / totalcap
            # print('Added VOMO cost: ', mc_cost_temp)
        except KeyError:
            # print('No VOM-Out defined cost')
            pass

        # VOM defined on input
        try:
            # print('VOMI Cost: ', GDATA.loc[G, 'GDOMVCOSTIN'])
            mc_cost_temp += (
                GDATA.loc[(G, "GDOMVCOSTIN"), "Value"]
                / GDATA.loc[(G, "GDFE"), "Value"]
                * Gcap
                / totalcap
            )
            # print('Added VOMI cost: ', mc_cost_temp)
        except KeyError:
            # print('No VOM-In defined cost')
            pass

        # Fuel cost
        try:
            mc_cost_temp += (
                FPRICE.query("F == @fuel and A.str.contains(@region)")
                .loc[:, "Value"]
                .mean()
                * 3.6  # From €/GJ to €/MWh
                / GDATA.loc[(G, "GDFE"), "Value"]
                * Gcap
                / totalcap
            )  # Same prices everywhere as in DK
            # print('Added fuel cost: ', mc_cost_temp)
        except KeyError:
            log(f"No fuel cost for {region, G, fuel}")

        # Carbon cost
        try:
            country = cap[idx_cap].C.values[0]
            fuelemi = FDATA.loc[(fuel, "FDCO2"), "Value"] * 3.6 / 1000  # in t/MWh
            tax = EMI_POL.loc[
                (year, country, "ALL_SECTORS", "TAX_CO2"), "Value"
            ]  # €/tCO2
            mc_cost_temp += (
                tax * fuelemi / GDATA.loc[(G, "GDFE"), "Value"] * Gcap / totalcap
            )
            # print('Added CO2 cost: ', mc_cost_temp)
        except KeyError:
            pass

        if include_capital_costs:
            # The issue with this is that you don't know when the generators produce!
            # A lot of the capital costs could be allocated to a few hours, such as common ~3000 €/MWh prices in Balmorel investment opt results.
            # A flat / 8760 distribution is not realistic

            # CAPEX
            # Get endogenous share
            endo_share = (
                cap.query('Var == "ENDOGENOUS"')
                .loc[idx_cap & (cap.G == G), "Value"]
                .sum()
                * 1e3
                / Gcap
            )

            if endo_share < 1e-5:
                pass
            else:
                # print(f'Endogenous share for {G}: {endo_share*100} %')
                capex_cost = (
                    GDATA.loc[(G, "GDINVCOST0"), "Value"]
                    * 1e6
                    / 8760
                    * Gcap
                    * endo_share
                    * ANNUITYCG.loc[(country, G), "Value"]
                    / totalcap
                )
                # print('Added CAPEX part', capex_cost)
                mc_cost_temp += capex_cost

            # Fixed O&M
            try:
                fom_cost = (
                    GDATA.loc[(G, "GDOMFCOST0"), "Value"] * 1e3 / 8760 * Gcap / totalcap
                )
                # print('Added FOM part', fom_cost)
                mc_cost_temp += fom_cost
            except:
                # print('No fixed costs')
                pass

    return mc_cost_temp


def get_efficiency(cap: pd.DataFrame, idx_cap: pd.Index, GDATA: pd.DataFrame):
    """Gets average marginal cost of generators in cap[idx_cap], provided VOM, fuel and emission policy data

    Args:
        cap (_type_): _description_
        idx_cap (_type_): _description_
        GDATA (_type_): _description_
    """
    ## Weighting capacities on highest data level (G)
    totalcap = cap.loc[idx_cap, "Value"].sum() * 1e3  # MW

    eff_temp = 0
    for G in cap[idx_cap].G.unique():
        Gcap = cap.loc[idx_cap & (cap.G == G), "Value"].sum() * 1e3  # MW

        # Fuel cost
        try:
            eff_temp += (
                GDATA.loc[(G, "GDFE"), "Value"] * Gcap / totalcap
            )  # Same prices everywhere as in DK
            # print('Added fuel cost: ', mc_cost_temp)
        except:
            pass

    return eff_temp


def get_capex(
    cap: pd.DataFrame, idx_cap: pd.Index, GDATA: pd.DataFrame, ANNUITYCG: pd.DataFrame
):
    """Gets average marginal cost of generators in cap[idx_cap], provided VOM, fuel and emission policy data

    Args:
        cap (_type_): _description_
        idx_cap (_type_): _description_
        GDATA (_type_): _description_
    """

    capex_temp = 0
    for G in cap[idx_cap].G.unique():
        Gcap = cap.loc[idx_cap & (cap.G == G), "Value"].sum() * 1e3  # MW

        # Country
        country = cap.loc[idx_cap & (cap.G == G), "C"].unique()[
            0
        ]  # Will just be one country as region is filtered

        try:
            capex_temp += (
                GDATA.loc[(G, "GDINVCOST0"), "Value"]
                * ANNUITYCG.loc[(country, G), "Value"]
                * Gcap
                * 1e6
            )  # €
            # print('Added fuel cost: ', mc_cost_temp)
        except:
            pass

    return capex_temp


# ------------------- #
#       Outputs       #
# ------------------- #


def get_ptx_demand_timeseries(
    balmorel_scenario: str,
    antares_scenario: str,
    balmorel_scfolder: str,
    temporal: str = "weekly",
    mc_year: str = "mc-all",
    plot: bool = False,
    return_output_classes: bool = False,
    regions: list = ["ES", "FR", "DE"],
    commodities: list = ["HYDROGEN", "HEAT"],
    gams_system_directory: str = "/appl/gams/47.6.0",
):
    """
    Get electricity demands for power-to-heat and power-to-hydrogen across models

    Args:
       balmorel_scenario (str): The concrete Balmorel scenario to load.
       antares_scenario (str): The concrete Antares scenario to load.
       balmorel_scfolder (str): The scenario folder, where the Balmorel MainResults resides.
       temporal (str): The temporal granularity of the timeseries, weekly or hourly.
       mc_year (str): The monte-carlo year to read from Antares result.
       plot (bool): Plot the series or not

    Returns:
       (pd.DataFrame, pd.DataFrame) | (pd.DataFrame, pd.DataFrame, MainResults, AntaresOutput): Dataframes with Balmorel and Antares PtX electricity demands.
       possibly including Balmorel and Antares output classes.
    """

    # Get files
    balmorel_output = MainResults(
        f"MainResults_{balmorel_scenario}_Iter0.gdx",
        f"Balmorel/{balmorel_scfolder}/model",
        system_directory=gams_system_directory,
    )
    antares_output = AntaresOutput(antares_scenario)

    # Get Balmorel series
    df_balm = (
        balmorel_output.get_result("F_CONS_YCRAST")
        .query('Fuel == "ELECTRIC"')
        .query('Technology in ["ELECT-TO-HEAT", "ELECTROLYZER"]')
        .replace({"Technology": "ELECT-TO-HEAT"}, "HEAT")
        .replace({"Technology": "ELECTROLYZER"}, "HYDROGEN")
    )
    df_balm.Season = df_balm.Season.str.replace("S", "").astype(int)
    df_balm = df_balm.pivot_table(
        index=["Season", "Region", "Technology"]
        if temporal == "weekly"
        else ["Season", "Time", "Region", "Technology"],
        values="Value",
        aggfunc="sum",
    )
    df_ant = pd.DataFrame()
    for region in regions:
        for commodity in commodities:
            temp = antares_output.load_link_results(
                [region, f"{region}_{commodity}"], temporal=temporal, mc_year=mc_year
            )
            temp["Region"] = region
            temp["Commodity"] = commodity
            df_ant = pd.concat(
                (df_ant, temp[[temporal, "Region", "Commodity", "FLOW LIN."]]),
                ignore_index=True,
            )

    df_ant = df_ant.pivot_table(
        index=[temporal, "Region", "Commodity"], values="FLOW LIN.", aggfunc="sum"
    )

    if plot:
        for commodity in commodities:
            fig, axes = plt.subplots(3)

            for i, region in enumerate(regions):
                slices = (
                    (slice(None), slice(None), region, commodity)
                    if temporal == "hourly"
                    else (slice(None), region, commodity)
                )
                df_balm.loc[slices].plot(ax=axes[i], label="Balmorel")
                df_ant.loc[:, region, commodity].plot(ax=axes[i], label="Antares")
                axes[i].set_ylabel(region)
                axes[i].legend(("Balmorel", "Antares"))

            axes[0].set_title(commodity)

            plt.show()

    if not return_output_classes:
        return df_balm, df_ant
    else:
        return df_balm, df_ant, balmorel_output, antares_output


def get_antares_inadequacy(antares_result: str, regional_mapping: dict):
    AntOut = AntaresOutput(antares_result)

    data = []

    for region in regional_mapping.keys():
        # 1.4 Load Antares Results
        region_result = AntOut.load_area_results(region, temporal="annual")

        # Unsupplied Energy
        ENS = region_result.loc[0, "UNSP. ENRG"]
        # UNSENR_arr = AntOut.collect_mcyears('UNSP. ENRG', region).quantile(.5, axis=1)   # Hourly median unsupplied energy

        # Loss of load expectation
        LOLE = region_result.loc[0, "LOLD"]

        data.append([region, ENS, LOLE])

    df = pd.DataFrame(data, columns=["Region", "ENS", "LOLE"])

    return df


# %% ------------------------------- ###
###            5. Classes           ###
### ------------------------------- ###


class BC:
    """A class for handling the binding constraints of Antares"""

    def __init__(self, path_to_antares_study: str = "./Antares"):
        self.study_path = path_to_antares_study
        cf = configparser.ConfigParser()
        cf.read(
            os.path.join(
                self.study_path, "input/bindingconstraints/bindingconstraints.ini"
            )
        )

        bc_name_to_idx = {}
        section_names = []
        for section in cf.sections():
            name = cf.get(section, "name")
            # The operator is part of the filename in Antares 8.7
            operator = (
                cf.get(section, "operator")
                .replace("greater", "gt")
                .replace("less", "lt")
                .replace("equal", "eq")
            )
            name = name + "_" + operator

        self.sections = section_names
        self._bc_name_to_idx = bc_name_to_idx
        self._cf = cf

    def get(self, section: str, parameter: str):
        return self._cf.get(self._bc_name_to_idx[section], parameter)


class IncFile:
    """A useful class for creating .inc-files for GAMS models
    Args:
    prefix (str): The first part of the .inc file.
    body (str): The main part of the .inc file.
    suffix (str): The last part of the .inc file.
    name (str): The name of the .inc file.
    path (str): The path to save the file, defaults to 'Balmorel/base/data'.
    """

    def __init__(
        self, prefix="", body="", suffix="", name="name", path="Balmorel/base/data/"
    ):
        self.prefix = prefix
        self.body = body
        self.suffix = suffix
        self.name = name
        self.path = path

    def save(self):
        if self.path[-1] != "/":
            self.path += "/"
        if self.name[-4:] != ".inc":
            self.name += ".inc"

        with open(self.path + self.name, "w") as f:
            f.write(self.prefix)
            f.write(self.body)
            f.write(self.suffix)


def ReadIncFilePrefix(name, incfile_prefix_path, weather_year):
    if ("WND" in name) | ("SOLE" in name) | ("DE" in name) | ("WTR" in name):
        string = "* Weather year %d from Antares\n" % (weather_year + 1) + "".join(
            open(incfile_prefix_path + "/%s.inc" % name).readlines()
        )
    else:
        string = "".join(open(incfile_prefix_path + "/%s.inc" % name).readlines())

    return string


class AntaresOutput:
    """
    A class for handling Antares outputs, based on Antares 8.7

    Will assume that an Antares study exist in current directory
    and get the latest result by default.
    """

    def __init__(
        self,
        result_name: str = "latest",
        folder_name: str = "Antares",
        wk_dir: str = ".",
    ):
        result_folder = Path(folder_name).joinpath("output")

        # Find latest, if that was chosen (default)
        if result_name.lower() == "latest":
            results = [path for path in result_folder.iterdir() if "eco" in str(path)]
            most_recent = [result.stat().st_ctime for result in results]
            most_recent = most_recent.index(np.max(most_recent))
            self.path = results[most_recent]
        else:
            # Set path to result
            self.path = result_folder.joinpath(result_name)

        if self.path.exists():
            print(f"Found {self.path}")
            self.path = str(self.path)
        else:
            raise FileNotFoundError(f"Couldnt find {self.path}!")

        try:
            self.mc_years = os.listdir(os.path.join(self.path, "economy/mc-ind"))
            self.mc_years.sort()
            print(f"MC years: {self.mc_years}")
        except FileNotFoundError:
            self.mc_years = None

        self.name = result_name
        self.wk_dir = wk_dir

    # Function to load area results
    def load_area_results(
        self,
        node: str,
        result_type: str = "values",
        temporal: str = "hourly",
        mc_year: str = "mc-all",
    ):
        if mc_year == "mc-all":
            return pd.read_table(
                os.path.join(
                    self.path,
                    "economy/%s/areas/%s/%s-%s.txt"
                    % (
                        mc_year.lower(),
                        node.lower(),
                        result_type.lower(),
                        temporal.lower(),
                    ),
                ),
                skiprows=[0, 1, 2, 3, 5, 6],
            )
        else:
            mc_year = convert_int_to_mc_year(mc_year)
            return pd.read_table(
                os.path.join(
                    self.path,
                    "economy/mc-ind/%s/areas/%s/%s-%s.txt"
                    % (
                        mc_year.lower(),
                        node.lower(),
                        result_type.lower(),
                        temporal.lower(),
                    ),
                ),
                skiprows=[0, 1, 2, 3, 5, 6],
            )

    # Function to load column result from many areas
    def collect_result_areas(
        self,
        nodes: list,
        column: str,
        result_type: str = "values",
        temporal: str = "hourly",
        mc_year: str = "mc-all",
    ):
        res = pd.DataFrame(columns=nodes)
        for node in nodes:
            res[node] = self.load_area_results(node, result_type, temporal, mc_year)[
                column
            ]

        res.columns.name = column
        return res

    def load_link_results(
        self,
        nodes: list[str, str],
        result_type: str = "values",
        temporal: str = "hourly",
        mc_year: str = "mc-all",
    ):
        """
        Will load results from nodes[0] -> nodes[1]
        """
        if mc_year == "mc-all":
            return pd.read_table(
                os.path.join(
                    self.path,
                    "economy/%s/links/%s - %s/%s-%s.txt"
                    % (
                        mc_year.lower(),
                        nodes[0].lower(),
                        nodes[1].lower(),
                        result_type.lower(),
                        temporal.lower(),
                    ),
                ),
                skiprows=[0, 1, 2, 3, 5, 6],
            )
        else:
            mc_year = convert_int_to_mc_year(mc_year)
            return pd.read_table(
                os.path.join(
                    self.path,
                    "economy/mc-ind/%s/links/%s - %s/%s-%s.txt"
                    % (
                        mc_year.lower(),
                        nodes[0].lower(),
                        nodes[1].lower(),
                        result_type.lower(),
                        temporal.lower(),
                    ),
                ),
                skiprows=[0, 1, 2, 3, 5, 6],
            )

    # Function to load and calculate median results
    def collect_mcyears(
        self,
        column: str,
        node_or_nodes: Union[str, list],
        result_type: str = "values",
        temporal: str = "hourly",
    ):
        """
        If providing node_or_nodes is a string, it will be interpreted as an area result,
        while anything else is assumed link result
        """

        # Choose function
        if type(node_or_nodes) is str:
            func = self.load_area_results
        else:
            func = self.load_link_results

        if self.mc_years is not None:
            for mc_year in self.mc_years:
                # Create temporary variable at first mc_year
                if "temp" not in locals():
                    # Load
                    temp = func(node_or_nodes, result_type, temporal, mc_year)

                    # Only keep desired column
                    temp = pd.DataFrame(
                        data=temp[column].values, index=temp.index, columns=[mc_year]
                    )

                    # Convert name of column to mc_year name
                    temp.columns = [mc_year]

                # Append to temporary variable
                else:
                    temp[mc_year] = func(node_or_nodes, result_type, temporal, mc_year)[
                        column
                    ].values

            # Calculate quantile
            return temp

        else:
            # print('No mc-year results')
            return 0


class AntaresInput:
    """
    A class for handling Antares inputs, based on Antares 8.7
    """

    def __init__(self, folder_name: str = "Antares", wk_dir: str = "."):
        # Set path to result
        self.path = os.path.join(wk_dir, folder_name, "input")
        self.wk_dir = wk_dir

        # Thermal Cluster Data
        self.thermal_clusters = {}
        self.path_thermal_clusters = {}
        self.path_load = {}
        for area in os.listdir(os.path.join(self.path, "thermal/clusters")):
            self.path_thermal_clusters[area] = {}
            self.path_thermal_clusters[area]["ini"] = os.path.join(
                self.path, "thermal/clusters", area, "list.ini"
            )
            self.path_thermal_clusters[area]["series"] = os.path.join(
                self.path, "thermal/series", area
            )
            self.path_thermal_clusters[area]["prepro"] = os.path.join(
                self.path, "thermal/prepro", area
            )
            self.path_load[area] = os.path.join(
                self.path, "load/series", f"load_{area}.txt"
            )

            config = configparser.ConfigParser()
            config.read(self.path_thermal_clusters[area]["ini"])
            self.thermal_clusters[area] = config.sections()

    def thermal(self, area: str, series: bool = False, cluster_name: str = ""):
        area = area.lower()
        cluster_name = cluster_name.lower()
        if not (series):
            output = configparser.ConfigParser()
            output.read(self.path_thermal_clusters[area]["ini"])
        else:
            output = pd.read_table(
                os.path.join(
                    self.path_thermal_clusters[area]["series"],
                    cluster_name,
                    "series.txt",
                ),
                header=None,
            )

        return output

    def load(self, area: str):
        """Read the load timeseries of an area

        Args:
            area (str): _description_

        Returns:
            _type_: _description_
        """
        area = area.lower()
        output = pd.read_table(self.path_load[area], header=None)
        return output

    def create_thermal(
        self,
        area: str,
        cluster_name: str,
        fuel: str,
        enabled: bool = False,
        capacity: float = 0,
        marginal_cost: float = 0,
    ):
        """Creates a new cluster in area.
        Note that if a cluster already exists with this name,
        its data be overwritten.


        Args:
            area (str): _description_
            cluster_name (str): _description_
            fuel (str): _description_
            enabled (bool, optional): _description_. Defaults to False.
            capacity (float, optional): _description_. Defaults to 0.
            marginal_cost (float, optional): _description_. Defaults to 0.

        Returns:
            _type_: _description_
        """

        cluster_name = cluster_name.lower()
        area = area.lower()
        fuel = fuel.lower()

        # Create section in .ini file
        config = self.thermal(area, cluster_name=cluster_name)
        try:
            config.add_section(cluster_name)
        except configparser.DuplicateSectionError:
            config.remove_section(cluster_name)
            config.add_section(cluster_name)
            # print(f'{cluster_name} already existed in {area}, overwriting')

        config.set(cluster_name, "name", cluster_name)
        config.set(cluster_name, "group", fuel)
        config.set(cluster_name, "unitcount", "1")
        config.set(cluster_name, "co2", "0")
        config.set(cluster_name, "nh3", "0")
        config.set(cluster_name, "nmvoc", "0")
        config.set(cluster_name, "nox", "0")
        config.set(cluster_name, "op1", "0")
        config.set(cluster_name, "op2", "0")
        config.set(cluster_name, "op3", "0")
        config.set(cluster_name, "op4", "0")
        config.set(cluster_name, "op5", "0")
        config.set(cluster_name, "pm10", "0")
        config.set(cluster_name, "pm2_5", "0")
        config.set(cluster_name, "pm5", "0")
        config.set(cluster_name, "so2", "0")
        if enabled:
            config.set(cluster_name, "nominalcapacity", str(capacity))
            config.set(cluster_name, "marginal-cost", str(marginal_cost))
            config.set(cluster_name, "market-bid-cost", str(marginal_cost))
        else:
            config.set(cluster_name, "enabled", str(enabled).lower())

        with open(self.path_thermal_clusters[area]["ini"], "w") as f:
            config.write(f)

        # Create other files
        cluster_series_path = os.path.join(
            self.path_thermal_clusters[area]["series"], cluster_name
        )
        if not (os.path.exists(cluster_series_path.rstrip(cluster_name))):
            make_directory_if_not_exist(cluster_series_path.rstrip(cluster_name))
        make_directory_if_not_exist(cluster_series_path)

        with open(os.path.join(cluster_series_path, "CO2Cost.txt"), "w") as f:
            f.write("")
        with open(os.path.join(cluster_series_path, "fuelCost.txt"), "w") as f:
            f.write("")
        with open(os.path.join(cluster_series_path, "series.txt"), "w") as f:
            f.write("\n".join([str(capacity)] * 8760))
            f.write("\n")

        prepro_path = os.path.join(
            self.path_thermal_clusters[area]["prepro"], cluster_name
        )
        if not (os.path.exists(prepro_path.rstrip(cluster_name))):
            make_directory_if_not_exist(prepro_path.rstrip(cluster_name))
        make_directory_if_not_exist(prepro_path)
        with open(os.path.join(prepro_path, "data.txt"), "w") as f:
            f.write("\n".join(["1\t1\t0\t0\t0\t0"] * 365))
            f.write("\n")
        with open(os.path.join(prepro_path, "modulation.txt"), "w") as f:
            f.write("\n".join(["1\t1\t1\t0"] * 8760))
            f.write("\n")

        # Append to the class cluster list
        self.thermal_clusters[area].append(cluster_name)

        return config, cluster_series_path, prepro_path

    def purge_thermal_clusters(self, area: str):
        """Will delete all thermal cluster data within an area

        Args:
            area (str): _description_
        """
        area = area.lower()
        shutil.rmtree(self.path_thermal_clusters[area]["series"])
        shutil.rmtree(self.path_thermal_clusters[area]["prepro"])
        with open(self.path_thermal_clusters[area]["ini"], "w") as f:
            f.write("")

        self.thermal_clusters[area] = []


def make_directory_if_not_exist(path: str):
    if os.path.exists(path):
        pass
        # print(f'{path} already existed')
    else:
        os.mkdir(path)


def convert_int_to_mc_year(mc_year: int):
    # Make mc_year into correct format
    mc_year = "".join(["0" for i in range(5 - len(str(mc_year)))]) + str(mc_year)
    return mc_year


def write_8760_series(cluster_series_path: str, capacity: float | int):
    with open(os.path.join(cluster_series_path, "series.txt"), "w") as f:
        f.write("\n".join([str(capacity)] * 8760))
        f.write("\n")


# %% ------------------------------- ###
###          6. Utilities           ###
### ------------------------------- ###


def set_scenariobuilder_values(element: str, weather_years=35):
    """Build the chronological weather year scenarios for an element, so weather years don't mix

    Args:
        element (str): The name of the element, should include a '%d' for the weather year formatte
        weather_years (int, optional): The amount of weather years. Defaults to 35.
    """

    scenariobuilder = configparser.ConfigParser()
    scenariobuilder.read("Antares/settings/scenariobuilder.dat")

    for weather_year in range(weather_years):
        # print(f'formatting {element} to {element%weather_year} and value as {weather_year+1}')
        try:
            scenariobuilder.set(
                "default ruleset", element % weather_year, str(weather_year + 1)
            )
        except configparser.DuplicateOptionError:
            pass

    with open("Antares/settings/scenariobuilder.dat", "w") as f:
        scenariobuilder.write(f)


# By ChatGPT
def find_and_copy_files(source_folder, destination_folder, file_contains):
    # Create the destination folder if it doesn't exist
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Walk through the source folder and its subdirectories
    for foldername, subfolders, filenames in os.walk(source_folder):
        for filename in filenames:
            # Check if the file has the desired extension
            if file_contains in filename:
                source_path = os.path.join(foldername, filename)
                destination_path = os.path.join(destination_folder, filename)

                # Copy the file to the destination folder
                shutil.copy2(source_path, destination_path)
                print(f"Copied: {filename}")


def check_antares_compilation(wait_sec: int, max_waits: int, N_errors: int):
    """
    Peri-Processing usually takes around 100 s, while Antares compilation is around 60 s
    """
    i = 0
    compile_finished = False
    while not (compile_finished) and i < max_waits:
        # Check if Peri-Processing is being run
        periproc_finished = open(
            "Workflow/MetaResults/periprocessing_finished.txt", "r"
        )
        periproc_finished = periproc_finished.readline()
        periproc_finished = periproc_finished == "True"
        print("\nChecking if peri-processing has finished..", periproc_finished)
        # print(periproc_finished)

        # Check latest Antares log
        latest_ant_log = os.listdir("Antares/logs")
        latest_ant_log.sort()
        latest_ant_log = latest_ant_log[-1]

        print("Reading log:", latest_ant_log)

        log = open(os.path.join("Antares/logs", latest_ant_log), "r")

        # Convert to pandas series for finding text
        log = pd.Series(log.readlines())

        # Check if the simulation has compiled (i.e., started)
        compile_finished = len(log[log.str.find("Starting the simulation") != -1]) == 1
        # print(log[log.str.find('Starting the simulation') != -1].to_string())

        # Check both events
        compile_finished = compile_finished and periproc_finished

        # If it didn't compile, then wait
        if not (compile_finished):
            print(
                "Peri-processing is still running or Antares still compiling, waiting %0.2f min.."
                % (wait_sec / 60)
            )
            print(
                "Remember to check if last Antares run ever started - otherwise this might be stuck!"
            )
            sys.stdout.flush()

            time.sleep(wait_sec)
            i += 1

    if compile_finished and periproc_finished:
        print(
            "Peri-processing is not running and Antares finished compiling, starting peri-processing and Antares execution now!"
        )

        # Set periprocessing_finished to false (will be set to true after peri-processing finishes)
        with open("Workflow/MetaResults/periprocessing_finished.txt", "w") as f:
            f.write("False")
    else:
        print(
            "Waited for %0.2f min. and exiting now as this must be due to an error - or maybe last Antares run never started"
            % (i * wait_sec / 60)
        )
        N_errors += 1

    return compile_finished, N_errors


@click.pass_context
def data_context(ctx):
    # Create data filepaths
    ctx.obj["data_filepaths"] = {
        "offshore_wind": "Pre-Processing/Data/offshore_wind/offshore_wind_%d.csv",
        "onshore_wind": "Pre-Processing/Data/onshore_wind/onshore_wind_%d.csv",
        "solar_pv": "Pre-Processing/Data/solar_pv/solar_pv_%d.csv",
        "heat": "Pre-Processing/Data/heating_coeff/heating_coeff_%d.csv",
        "load": "Pre-Processing/Data/load_non_thermosensitive/load_non_thermosensitive.csv",
    }

    ctx.obj["data_value_column"] = {
        "offshore_wind": "offshore_wind",
        "onshore_wind": "onshore_wind",
        "solar_pv": "pv",
        "heat": "heating_coeff",
        "load": "non_thermosensitive",
    }

    return ctx


def load_OSMOSE_data(files: list, print_files_read: bool = False):
    """Load data from OSMOSE and do something with func(*args, **kwargs)"""

    def decorator(func):
        @wraps(func)
        def wrapper(ctx, *args, **kwargs):
            data_filepaths = ctx.obj["data_filepaths"]
            value_names = ctx.obj["data_value_column"]
            weather_years = ctx.obj["weather_years"]

            for data in files:
                # Load input data
                stoch_year_data = {}
                if data != "load":
                    for year in weather_years:
                        filename = data_filepaths[data] % year
                        if print_files_read:
                            print("Reading %s" % filename)
                        stoch_year_data[year] = pd.read_csv(filename).pivot_table(
                            index="time_id", columns="country", values=value_names[data]
                        )
                else:
                    stoch_year_data[0] = pd.read_csv(data_filepaths[data]).pivot_table(
                        index="time_id", columns="country", values=value_names[data]
                    )

                func(ctx, data, stoch_year_data, *args, **kwargs)

        return wrapper

    return decorator


if __name__ == "__main__":
    print("Test of loading binding constraint:")
    cf = BC()

    print(
        "Load fr_psp type and operator:",
        cf.get("fr_psp", "type"),
        cf.get("fr_psp", "operator"),
    )

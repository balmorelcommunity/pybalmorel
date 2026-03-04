"""
Created on 25.01.2024

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)

NOTE - Requires the time series aggregation module:
pip install tsam

Docs: https://tsam.readthedocs.io/en/latest/gettingStartedDoc.html
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pybalmorel import Balmorel, IncFile
from pybalmorel.utils import symbol_to_df
from pathlib import Path
import os

try:
    import tsam.timeseriesaggregation as tsam
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "You need to install the python package 'tsam' to do timeseries aggregation:\npip install tsam"
    )


### 3.1 LDC Curve and Plot Function
def doLDC(array, n_bins, plot=False, ax=None, **kwargs):
    """Make load duration curve from timeseries

    Args:
        array (array): A timeseries of load, wind-, solar profiles or other.
        n-bins (int): Amount of bins in histogram

    Returns:
        duration (array): ordered hours
        curve (array): frequency
    """
    # Extract profile
    data = np.histogram(array, bins=n_bins)
    duration = data[0][::-1]
    curve = data[1][:-1][::-1]

    if plot:
        # Normalisation
        n_hours = len(array)
        max_val = array.max()

        if ax == None:
            fig, ax = plt.subplots()
            ax.plot(
                np.cumsum(duration) / n_hours * 8736, curve / max_val * 100, **kwargs
            )
            return duration, curve, fig, ax
        else:
            ax.plot(
                np.cumsum(duration) / n_hours * 8736, curve / max_val * 100, **kwargs
            )
            return duration, curve

    else:
        return duration, curve


# TODO: Make a function that automatically lists symbols, checks for S or T in domains, and collects those
# TODO: Func for automatically list symbols
# TODO: Func for checking for SSS, TTT, S or T in domains
# TODO: Func for collecting
def collect_timeseries(
    scenario: str,
    balmorel_model_folder: str,
    gams_system_directory: str | None = None,
    weather_year: int = 2012,
    include_GMAXFS: bool = False,
    overwrite_input_data: bool = False,
):
    ### 1.0 Define used weather year (read .inc file description)

    ### 1.1 Read Profiles GDX
    m = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    if overwrite_input_data:
        print(
            f"Overwriting input data for scenario {scenario} in {balmorel_model_folder}"
        )
    m.load_incfiles(scenario, overwrite=overwrite_input_data)

    ### Get spatial resolution
    IA = list(symbol_to_df(m.input_data[scenario], "IA").AAA.unique())
    IR = list(symbol_to_df(m.input_data[scenario], "IR").RRR.unique())

    ### 1.2 Get S-T Timeseries
    # Wind
    df = (
        symbol_to_df(m.input_data[scenario], "WND_VAR_T", ["A", "S", "T", "Wind"])
        .query(f"A in {IA}")
        .pivot_table(index=["S", "T"], columns=["A"], values=["Wind"], fill_value=0)
    )

    # Solar
    df = df.join(
        symbol_to_df(m.input_data[scenario], "SOLE_VAR_T", ["A", "S", "T", "Solar"])
        .query(f"A in {IA}")
        .pivot_table(index=["S", "T"], columns=["A"], values=["Solar"], fill_value=0),
        how="outer",
    ).fillna(0)

    # El. Load
    df2 = symbol_to_df(
        m.input_data[scenario], "DE_VAR_T", ["R", "Type", "S", "T", "Load"]
    ).query(f"R in {IR}")
    # df2 = df2['Load'].pivot_table(index=['S', 'T'], columns=['R'], values=['RESE'], fill_value=0)
    users = df2.Type.unique()
    for user in users:
        temp = (
            df2.query("Type == @user")
            .rename(columns={"Load": "Load - %s" % user})
            .pivot_table(
                index=["S", "T"],
                columns=["R"],
                values=["Load - %s" % user],
                fill_value=0,
            )
        )
        df = df.join(temp, how="outer").fillna(0)

    # Heat Load
    df2 = symbol_to_df(
        m.input_data[scenario], "DH_VAR_T", ["A", "Type", "S", "T", "Heat"]
    ).query(f"A in {IA}")
    # df2 = df2['Load'].pivot_table(index=['S', 'T'], columns=['R'], values=['RESE'], fill_value=0)
    users = df2.Type.unique()
    for user in users:
        temp = (
            df2.query("Type == @user")
            .rename(columns={"Heat": "Heat - %s" % user})
            .pivot_table(
                index=["S", "T"],
                columns=["A"],
                values=["Heat - %s" % user],
                fill_value=0,
            )
        )
        df = df.join(temp, how="outer").fillna(0)

    # Run-of-River
    df = df.join(
        symbol_to_df(m.input_data[scenario], "WTRRRVAR_T", ["A", "S", "T", "RoR"])
        .query(f"A in {IA}")
        .pivot_table(index=["S", "T"], columns=["A"], values=["RoR"], fill_value=0),
        how="outer",
    ).fillna(0)

    # 1.2 Get S Timeseries

    ## Reservoir Inflows
    WTRRSVAR_S = symbol_to_df(
        m.input_data[scenario], "WTRRSVAR_S", ["A", "S", "Reservoir"]
    ).query(f"A in {IA}")
    # Set all T values to T001
    WTRRSVAR_S["T"] = "T001"  # Add T dimension
    df2 = WTRRSVAR_S.pivot_table(
        index=["S", "T"], columns=["A"], values=["Reservoir"]
    ).fillna(0)
    df = df.join(df2, how="outer")
    T = df.index.get_level_values(1).unique()
    for T0 in T[1:]:
        df.loc[(slice(None), T0), "Reservoir"] = df.loc[
            (slice(None), "T001"), "Reservoir"
        ].values

    ## HYPROFILS
    # HYPROFILS =

    ## Fuel Potential (at the moment irrelevant, as they are constant for all S)
    if include_GMAXFS:
        GMAXFS = symbol_to_df(
            m.input_data[scenario], "GMAXFS", ["Y", "CRA", "F", "S", "Potential"]
        ).query(f"CRA in {IA} or CRA in {IR}")
        GMAXFS["T"] = "T001"
        GMAXFS = GMAXFS[
            GMAXFS.Y == "2050"
        ]  # Filter year in biomass potential (most important to be strict in 2050)
        df2 = GMAXFS.pivot_table(
            index=["S", "T"], columns=["F", "CRA"], values=["Potential"]
        ).fillna(0)
        df.join(df2, how="outer")

    # # Extracting a value:
    # df.loc[('S01', 'T001'), ('Wind', 'AL00_A')]
    # # Extracting many values
    # df.loc[('S26', slice(None)), ('Solar', 'AL00_A')]

    ## Min/Max values
    HYRSDATA = symbol_to_df(
        m.input_data[scenario], "HYRSDATA", ["A", "HYRSDATASET", "S", "Hyrsdata"]
    ).query(f"A in {IA}")
    # Set all T values to T001
    HYRSDATA["T"] = "T001"  # Add T dimension
    df2 = (
        HYRSDATA.query('HYRSDATASET == "HYRSMAXVOL"')
        .rename(columns={"Hyrsdata": "Hyrsdata - HYRSMAXVOL"})
        .pivot_table(index=["S", "T"], columns=["A"], values=["Hyrsdata - HYRSMAXVOL"])
        .fillna(0)
    )
    df3 = (
        HYRSDATA.query('HYRSDATASET == "HYRSMINVOL"')
        .rename(columns={"Hyrsdata": "Hyrsdata - HYRSMINVOL"})
        .pivot_table(index=["S", "T"], columns=["A"], values=["Hyrsdata - HYRSMINVOL"])
        .fillna(0)
    )
    df = df.join(df2, how="outer")
    df = df.join(df3, how="outer")
    try:
        for T0 in T[1:]:
            df.loc[(slice(None), T0), "Hyrsdata - HYRSMINVOL"] = df.loc[
                (slice(None), "T001"), "Hyrsdata - HYRSMINVOL"
            ].values
    except:
        print("No HYRSMINVOL defined or all zero")
    try:
        for T0 in T[1:]:
            df.loc[(slice(None), T0), "Hyrsdata - HYRSMAXVOL"] = df.loc[
                (slice(None), "T001"), "Hyrsdata - HYRSMAXVOL"
            ].values
    except:
        print("No HYRSMAXVOL defined or unlimited (zero)")

    # Create index
    try:
        df.index = pd.date_range(
            "%d-01-01 00:00" % weather_year, "%d-12-30 23:00" % weather_year, freq="h"
        )  # 8760 h
    except ValueError:
        df.index = pd.date_range(
            "%d-01-01 00:00" % weather_year, "%d-12-29 23:00" % weather_year, freq="h"
        )  # 8736 h

    return m, df


def format_and_save_profiles(
    typPeriods, method, weather_year, Nperiods, db, balmorel_model_folder
):
    ### Create All S and T index
    S = np.array(
        ["S0%d" % i for i in range(1, 10)] + ["S%d" % i for i in range(10, 53)]
    )
    T = (
        ["T00%d" % i for i in range(1, 10)]
        + ["T0%d" % i for i in range(10, 100)]
        + ["T%d" % i for i in range(100, 169)]
    )

    # Make evenly distributed S and T for Balmorel input, based on Nperiods
    S = list(S[np.linspace(0, 51, Nperiods[0]).round().astype(int)])
    T = T[: Nperiods[1]]

    ### Scenario Name
    if method == "distributionAndMinMaxRepresentation":
        aggregation_scenario = "W%dT%d_%s_WY%d" % (
            Nperiods[0],
            Nperiods[1],
            "dist",
            weather_year,
        )
    else:
        aggregation_scenario = "W%dT%d_%s_WY%d" % (
            Nperiods[0],
            Nperiods[1],
            method[:4],
            weather_year,
        )

    try:
        os.mkdir("Balmorel/%s" % aggregation_scenario)
        os.mkdir("Balmorel/%s/data" % aggregation_scenario)
    except FileExistsError:
        pass

    # Formatting typical periods
    balmseries = typPeriods.copy()
    balmseries.index = pd.MultiIndex.from_product((S, T), names=["S", "T"])

    # TODO: Change this to any symbol with only s domain
    reservoir_series = balmseries.loc[(slice(None), "T001"), "Reservoir"]
    reservoir_series.index = reservoir_series.index.get_level_values(0)
    reservoir_series.index.name = ""

    hyrsdatasets = {
        dataset: balmseries.loc[(slice(None), "T001"), "Hyrsdata - %s" % dataset]
        for dataset in ["HYRSMAXVOL", "HYRSMINVOL"]
        if "Hyrsdata - %s" % dataset in balmseries.columns.get_level_values(0)
    }

    balmseries.index = (
        balmseries.index.get_level_values(0)
        + " . "
        + balmseries.index.get_level_values(1)
    )

    # Fix load and hydro data series
    loadseries = pd.DataFrame()
    for user in [
        col.replace("Load - ", "")
        for col in balmseries.columns.get_level_values(0).unique()
        if "Load" in col
    ]:
        temp = balmseries["Load - %s" % user]
        temp.index = user + " . " + temp.index
        loadseries = pd.concat((loadseries, temp)).fillna(0)

    heatseries = pd.DataFrame()
    for user in [
        col.replace("Heat - ", "")
        for col in balmseries.columns.get_level_values(0).unique()
        if "Heat" in col
    ]:
        temp = balmseries["Heat - %s" % user]
        temp.index = user + " . " + temp.index
        heatseries = pd.concat((heatseries, temp)).fillna(0)

    hyrsdataseries = pd.DataFrame()
    for dataset in [
        dataset
        for dataset in ["HYRSMAXVOL", "HYRSMINVOL"]
        if "Hyrsdata - %s" % dataset in balmseries.columns.get_level_values(0).unique()
    ]:
        temp = hyrsdatasets[dataset]
        temp.index = dataset + " . " + temp.index.get_level_values(0)
        temp.index.name = ""
        hyrsdataseries = pd.concat((hyrsdataseries, temp)).fillna(0)

    ### 4.3 Save Profiles
    incfiles = {
        "S": IncFile(
            name="S",
            path="Balmorel/%s/data/" % aggregation_scenario,
            prefix="SET S(SSS)  'Seasons in the simulation'\n/\n",
            body=", ".join(S),
            suffix="\n/;",
        ),
        "T": IncFile(
            name="T",
            path="Balmorel/%s/data/" % aggregation_scenario,
            prefix="SET T(TTT)  'Time periods within a season in the simulation'\n/\n",
            body=", ".join(T),
            suffix="\n/;",
        ),
    }

    path_to_data = f"{balmorel_model_folder}/{aggregation_scenario}/data/"
    for incfile in [
        "DE_VAR_T",
        "DH_VAR_T",
        "WND_VAR_T",
        "SOLE_VAR_T",
        "WTRRRVAR_T",
        "WTRRSVAR_S",
        "HYRSDATA",
    ]:
        incfiles[incfile] = IncFile(
            name=incfile,
            prefix=f"TABLE {incfile}({', '.join(db[incfile].domains_as_strings)}) '{db[incfile].text}'\n",
            path=path_to_data,
            suffix="\n;",
        )

        # Load specific formatting
        if "DE" in incfile or "DH" in incfile:
            symbol_prefix = incfile.split("_")[0]
            symbol_node_name = db[incfile].domains_as_strings[0]
            domains = ", ".join(db[incfile].domains_as_strings)
            temporary_symbol_name = symbol_prefix + "_VAR_T1"
            temporary_symbol_domains = (
                f"{symbol_prefix}USER, SSS, TTT, {symbol_node_name}"
            )
            incfiles[
                incfile
            ].prefix = f"TABLE {temporary_symbol_name}({temporary_symbol_domains}) '{db[incfile].text}'\n"
            incfiles[
                incfile
            ].suffix = f"\n;\n{symbol_prefix + '_VAR_T'}({domains}) = {temporary_symbol_name}({temporary_symbol_domains});\n"
            incfiles[
                incfile
            ].suffix += f"{temporary_symbol_name}({temporary_symbol_domains}) = 0;"

        # HYRSDATA specific formatting
        if incfile == "HYRSDATA":
            incfiles[
                incfile
            ].prefix = f"TABLE HYRSDATA1(HYRSDATASET, SSS, AAA) '{db[incfile].text}'\n"
            incfiles[
                incfile
            ].suffix = "\n;\nHYRSDATA(AAA, HYRSDATASET, SSS) = HYRSDATA1(HYRSDATASET, SSS, AAA);"
            incfiles[incfile].suffix += "\nHYRSDATA1(HYRSDATASET, SSS, AAA) = 0;"

    # Set bodies
    incfiles["DE_VAR_T"].body = loadseries.to_string()
    incfiles["DH_VAR_T"].body = heatseries.to_string()
    incfiles["WTRRRVAR_T"].body = balmseries["RoR"].T.to_string()
    incfiles["WTRRSVAR_S"].body = reservoir_series.T.to_string()
    incfiles["HYRSDATA"].body = hyrsdataseries.to_string()
    incfiles["WND_VAR_T"].body = balmseries["Wind"].T.to_string()
    incfiles["SOLE_VAR_T"].body = balmseries["Solar"].T.to_string()

    ## Save
    for key in incfiles.keys():
        incfiles[key].save()

    ## Make empty addon files
    for empty_file in ["INDIVUSERS_DH_VAR_T.inc", "INDUSTRY_DH_VAR_T.inc"]:
        Path(path_to_data).joinpath(empty_file).touch()


###        2. Main Function         ###
### ------------------------------- ###
### ------------------------------- ###


def temporal_aggregation(
    scenario: str = "base",
    typical_periods: int = 6,
    hours_per_period: int = 24,
    method: str = "dist",
    weather_year: int = 2000,
    balmorel_model_folder: str = ".",
    include_gmaxfs: bool = False,
    gams_system_directory: str | None = "/opt/gams/50.4",
    overwrite_input_data: bool = False,
):
    """_summary_

    Args:
        scenario (str): The scenario folder to aggregate.
        typical_periods (int): Amount of periods / seasons
        hours_per_period (int): Amount of hours / terms
        method (str, optional): Aggregation method. Defaults to 'distribution', options are: K-means, K-medoids, Distribution preserving (default) and random choice
        weather_year (int): The weather year the data belong to
        balmorel_model_folder (str, optional): The path to the Balmorel folder. Defaults to '.', i.e. in the working directory.
        include_gmaxfs (bool, optional): Include seasonal fuel availability variations. Defaults to False.
        gams_system_directory (str | None, optional): The GAMS system directory. Defaults to None, which should make the gams API find it itself if in path.
    """

    model, df = collect_timeseries(
        scenario,
        balmorel_model_folder,
        gams_system_directory,
        weather_year,
        include_gmaxfs,
        overwrite_input_data,
    )

    # Using a Random Choice
    if method == "random":
        # Make random time aggregation
        N_timeslices = typical_periods * hours_per_period
        N_hours = len(df)

        # Make choices
        agg_steps = []
        for i in range(N_timeslices):
            agg_steps.append(np.random.randint(N_hours))

        # Sort chronologically
        agg_steps.sort()

        format_and_save_profiles(
            df.iloc[agg_steps],
            "random",
            weather_year,
            (typical_periods, hours_per_period),
            model.input_data[scenario],
            balmorel_model_folder,
        )

        # Also save a small note with the chosen timesteps
        with open(
            "Balmorel/%s/picked_times.txt"
            % (
                "W%dT%d_rand_weather_year%d"
                % (typical_periods, hours_per_period, weather_year)
            ),
            "w",
        ) as f:
            f.write(pd.Series(df.iloc[agg_steps].index).to_string())

    # Using tsam
    elif method != "random":
        # Method
        if "medoid" in method:
            method = "medoidRepresentation"
        elif "mean" in method:
            method = "meanRepresentation"
        elif "dist" in method:
            method = "distributionAndMinMaxRepresentation"
        else:
            print(
                "Didnt recognise choice of method, going with distribution preserving method"
            )
            method = "distributionAndMinMaxRepresentation"

        ### Normalise (be careful here, if you actually need absolute numbers)
        # df = df.clip(1e-3) / df.max()

        ### 3.1 Create Aggregation Object
        aggregation = tsam.TimeSeriesAggregation(
            df,
            noTypicalPeriods=typical_periods,
            hoursPerPeriod=hours_per_period,
            segmentation=True,
            noSegments=hours_per_period,
            representationMethod=method,
            distributionPeriodWise=False,
            clusterMethod="hierarchical",
            # numericalTolerance=1e-13
        )

        typPeriods = aggregation.createTypicalPeriods()

        format_and_save_profiles(
            typPeriods,
            method,
            weather_year,
            (typical_periods, hours_per_period),
            model.input_data[scenario],
            balmorel_model_folder,
        )


if __name__ == "__main__":
    temporal_aggregation()

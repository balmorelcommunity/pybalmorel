"""
Created on 26.02.2026

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime
from .utils import prepare_incfile, symbol_to_df
import pickle as pkl
import pandas as pd
import tsam
from ripgrepy import Ripgrepy
from .formatting import SSS_TTT_index


class TimeAgg:
    def __init__(self, parent):
        self.parent = parent
        self.symbols = {}
        self.incfiles = {}
        self.incfiles_to_save = {}
        self.data = pd.DataFrame(index=SSS_TTT_index)

    def collect_and_standardise(
        self,
        scenario: str,
        symbols_to_aggregate: dict | str = "auto",
        incfile_symbol_relation: dict = {},
        overwrite: bool = False,
    ):

        # Collect .inc files
        self.parent.load_incfiles(scenario, overwrite=overwrite)

        # Check standardised time series data have already been collected, return if so and overwrite = False
        std_data_file = self.parent.path / scenario / "std_ts_data.pkl"
        symbols_file = self.parent.path / scenario / "symbols_to_agg.pkl"
        incfiles_file = self.parent.path / scenario / "incfile_symbol_relation.pkl"
        if (
            not overwrite
            and std_data_file.exists()
            and symbols_file.exists()
            and incfiles_file.exists()
        ):
            with open(std_data_file, "rb") as f:
                self.data = pkl.load(f)

            # Load old standardised input
            if symbols_to_aggregate == "auto":
                with open(symbols_file, "rb") as f:
                    self.symbols = pkl.load(f)
            # Manually defined, following a previous standardisation
            elif type(symbols_to_aggregate) is not str:
                self.symbols = symbols_to_aggregate

            # Load old relations
            if incfile_symbol_relation == {}:
                with open(incfiles_file, "rb") as f:
                    self.incfiles = pkl.load(f)
            # Manually defined, following a previous standardisation
            else:
                self.incfiles = incfile_symbol_relation

            return

        # Collect input - start checking if input is correct
        if type(symbols_to_aggregate) is dict and incfile_symbol_relation == {}:
            # Make sure input is correct for manual entry
            raise ValueError(
                "incfile_symbol_relation must be defined if writing symbols to aggregate manually!"
            )

        elif type(symbols_to_aggregate) is dict:
            # Check that incfiles were defined for each symbol
            for timeseries_type in ["SSS,TTT", "SSS", "TTT"]:
                for symbol in symbols_to_aggregate[timeseries_type]:
                    try:
                        incfile_symbol_relation[symbol]
                    except KeyError:
                        raise ValueError(f"Missing incfile for {symbol}!")

            # Correct input
            self.symbols = symbols_to_aggregate
            self.incfiles = incfile_symbol_relation

        elif (
            type(symbols_to_aggregate) is str and symbols_to_aggregate.lower() == "auto"
        ):
            # Automatically find time series symbols
            self.find_timeseries_input(scenario)

        elif (
            type(symbols_to_aggregate) is str and symbols_to_aggregate.lower() != "auto"
        ):
            # Check that some other string was not passed
            raise ValueError(
                r"Incorrect choice - did you mean symbols_to_aggregate = 'auto' ?"
            )

        else:
            raise ValueError("Incorrect input!")

        # Collect and standardise input
        for symbol_type in ["SSS,TTT", "SSS", "TTT"]:
            self.symbols_to_ignore = []
            for symbol in self.symbols[symbol_type]:
                self.standardise_timeseries(scenario, symbol)

            self.symbols[symbol_type] = [
                symbol
                for symbol in self.symbols[symbol_type]
                if symbol not in self.symbols_to_ignore
            ]

        # Save standardised input to a .pkl file
        with open(std_data_file, "wb") as f:
            pkl.dump(self.data, f)
        with open(symbols_file, "wb") as f:
            pkl.dump(self.symbols, f)
        with open(incfiles_file, "wb") as f:
            pkl.dump(self.incfiles, f)

    def get_weights(self, scenario: str):
        """Will calculate weights per region based on the sum of exogenous electricity, heat and hydrogen demand, and the total potential for technology investments"""

        # Collect data input for calculating weights
        Y = self.parent.get_input("Y").query(f'Scenario == "{scenario}"').YYY.unique()
        RRRAAA = (
            self.parent.get_input("RRRAAA")
            .query(f'Scenario=="{scenario}"')
            .pivot_table(index="AAA", values="RRR", aggfunc="max")
        )
        DE = (
            self.parent.get_input("DE")
            .query(f'Scenario=="{scenario}" and YYY in @Y')
            .pivot_table(index="RRR", values="Value", aggfunc="sum")
        )

        ## Get regions for later - assuming all regions have exogenous electricity demand
        DH = self.parent.get_input("DH").query(f'Scenario=="{scenario}" and YYY in @Y')
        DH["RRR"] = DH["AAA"].map(RRRAAA["RRR"])
        DH = DH.pivot_table(index="RRR", values="Value", aggfunc="sum")
        HYDROGEN_DH2 = self.parent.get_input("HYDROGEN_DH2").query(
            f'Scenario=="{scenario}" and YYY in @Y'
        )
        hydrogen_regions = [
            region
            for region in HYDROGEN_DH2["CCCRRRAAA"].unique()
            if region in DE.index
        ]
        HYDROGEN_DH2 = HYDROGEN_DH2.query("CCCRRRAAA in @hydrogen_regions").pivot_table(
            index="CCCRRRAAA", values="Value", aggfunc="sum"
        )
        HYDROGEN_DH2.index.name = "RRR"
        SUBTECHGROUPKPOT = self.parent.get_input("SUBTECHGROUPKPOT").query(
            f'Scenario=="{scenario}"'
        )
        subtech_regions = [
            region
            for region in SUBTECHGROUPKPOT["CCCRRRAAA"].unique()
            if region in DE.index
        ]
        SUBTECHGROUPKPOT = SUBTECHGROUPKPOT.query(
            "CCCRRRAAA in @subtech_regions"
        ).pivot_table(index="CCCRRRAAA", values="Value", aggfunc="sum")
        SUBTECHGROUPKPOT.index.name = "RRR"

        # Calculate weight per region
        weights_per_region  = (
            DE.add(DH, fill_value=0)
            .add(HYDROGEN_DH2, fill_value=0)
            .add(SUBTECHGROUPKPOT, fill_value=0)
        )
        weights_per_region = weights_per_region  / weights_per_region.max()
        
        # Assign weight per area
        weights_per_area = pd.DataFrame(index=RRRAAA.index, columns=['Value'], data=0.0)
        for area in weights_per_area.index:
            weights_per_area.loc[area, 'Value'] = weights_per_region.loc[RRRAAA.loc[area].values[0], 'Value']

        return weights_per_region, weights_per_area

    def find_timeseries_input(
        self,
        scenario: str,
        excluded_symbols: list = [
            "WEIGHT_S",
            "WEIGHT_T",
            "CHRONOHOUR",
            "SSIZE",
            "TWORKDAY",
            "TWEEKEND",
            "S",
            "T",
            "DE_VAR_T1",
            "DE_VAR_T1_INDIVHEATING",
            "DH_VAR_T1",
            "DH_VAR_T_IND",
            "DH_VAR_T_INDIVHEATING",
            "WND_VAR_T1",
            "SOLE_VAR_T1",
            "SOLH_VAR_T1",
            "X3FX_VAR_T1",
        ],
    ):
        """
        Locates the timeseries inputs of Balmorel by loading symbols from .inc
        files, filtering symbols with SSS or TTT domains, and filtering raw
        data input from processed by matching symbol names to the text of ALL
        .inc files in base/data and scenario/data. excluded_symbols can be used
        to exclude temporal resolution input meta data, such as CHRONOHOUR, S
        or T, or temporary profiles such as DE_VAR_T1.

        Args:
        scenario (str): scenario timeseries data input to find.
        excluded_symbols (list): symbols to exclude.

        Returns:
        str: description.
        """

        # Make sure scenario data has been loaded
        assert scenario in self.parent.input_data, (
            f"Input data not loaded for {scenario}!"
            f"Run 'Balmorel.load_incfiles({scenario})' before this command"
        )

        # Get a list of all symbols in this scenario
        db = self.parent.input_data[scenario]
        symbol_list = [
            symbol.name for symbol in db if symbol.name not in excluded_symbols
        ]

        # Categorise symbols
        timeseries_symbols = {"SSS,TTT": [], "SSS": [], "TTT": []}
        symbols_incfiles = {}
        for symbol in symbol_list:
            # Only look at symbols with domains (e.g.: not CCCRRRAAA)
            domains = [domain.name for domain in db[symbol].domains if domain != "*"]

            # Use ripgrep to search for symbol in .inc files
            incfiles_containing_symbol = search_in_incfiles(
                symbol, self.parent.path / scenario / "data"
            )

            # Try again in base/data, if symbol wasnt found in scenario/data
            if len(incfiles_containing_symbol) == 0:
                incfiles_containing_symbol = search_in_incfiles(
                    symbol, self.parent.path / "base/data"
                )

            # Only collect if symbol exists in an .inc file
            if len(incfiles_containing_symbol) > 0:
                if ("SSS" in domains or "S" in domains) and (
                    "TTT" in domains or "T" in domains
                ):
                    timeseries_symbols["SSS,TTT"].append(symbol)
                    symbols_incfiles[symbol] = incfiles_containing_symbol
                elif ("SSS" in domains or "S" in domains) and not (
                    "TTT" in domains or "T" in domains
                ):
                    timeseries_symbols["SSS"].append(symbol)
                    symbols_incfiles[symbol] = incfiles_containing_symbol
                elif ("TTT" in domains or "T" in domains) and not (
                    "SSS" in domains or "S" in domains
                ):
                    timeseries_symbols["TTT"].append(symbol)
                    symbols_incfiles[symbol] = incfiles_containing_symbol

        self.symbols = timeseries_symbols
        self.incfiles = symbols_incfiles

    def standardise_timeseries(self, scenario: str, symbol: str):
        """
        Collect and standardise timeseries

        NOTE: This depends on the balmorel_symbol_columns in pybalmorel/formatting.py!
                Otherwise, the following symbols will get KeyErrors in .pivot_table
                because of duplicate columns:
                XKRATE: Duplicate RRR's instead of IRRRE and IRRRI
        """

        # Get symbol
        db = self.parent.input_data[scenario]
        df = symbol_to_df(db, symbol)

        # Make sure it is not empty, remove if so
        if df.shape == (0, 0):
            self.symbols_to_ignore.append(symbol)
            print(f"Ignoring {symbol} in time aggregation since it was empty")
            return

        # Separate time domains from other domains
        domains = [
            domain
            for domain in df.columns
            if domain not in ["SSS", "S", "TTT", "T", "Value"]
        ]
        time_domains = [
            domain for domain in df.columns if domain in ["SSS", "S", "TTT", "T"]
        ]

        # Standardise
        df = df.pivot_table(
            index=time_domains, columns=domains, values="Value", fill_value=0
        )

        # Check if symbol has only constant values
        without_constants = df.loc[:, df.nunique() > 1]

        if len(without_constants.columns) == 0:
            self.symbols_to_ignore.append(symbol)
            print(
                f"Ignoring {symbol} in time aggregation since all time series were constant"
            )
            return

        # Flatten column to one string name
        if type(df.columns) is pd.MultiIndex:
            cols = [f"{symbol}|{'|'.join(col)}" for col in df.columns]
        else:
            cols = [f"{symbol}|{col}" for col in df.columns]
        df.columns = cols

        # Re-index to get full ST set for all (will duplicate S or T values to all T or S indices, respectively)
        if (
            "TTT" in time_domains
            and "SSS" not in time_domains
            and "S" not in time_domains
        ):
            df = df.reindex(SSS_TTT_index, level="TTT").fillna(0)
        elif (
            "T" in time_domains
            and "SSS" not in time_domains
            and "S" not in time_domains
        ):
            df.index.name = "TTT"
            df = df.reindex(SSS_TTT_index, level="TTT").fillna(0)
        elif (
            "SSS" in time_domains
            and "TTT" not in time_domains
            and "T" not in time_domains
        ):
            df = df.reindex(SSS_TTT_index, level="SSS").fillna(0)
        elif (
            "S" in time_domains
            and "TTT" not in time_domains
            and "T" not in time_domains
        ):
            df.index.name = "SSS"
            df = df.reindex(SSS_TTT_index, level="SSS").fillna(0)
        else:
            df.index.names = ["S", "T"]
            df = df.reindex(SSS_TTT_index).fillna(0)

        # Store time series data
        self.data = self.data.join(df, how="outer").fillna(0)

    def cluster(
        self,
        seasons: int = 6,
        terms: int = 24,
        method: str = "contiguous",
        representation: str = "distribution_minmax",
        weights_pr_region: pd.DataFrame = pd.DataFrame(),
        weights_pr_area: pd.DataFrame = pd.DataFrame()
    ):
        """Cluster collect input data

        Args:
            scenario (str): The scenario folder to aggregate.
            seasons (int): Amount of periods / seasons
            terms (int): Amount of hours / terms
            method (str, optional): Aggregation method. Defaults to 'contiguous', options are: averaging, kmeans, kmedoids, kmaxoids, hierarchical, contiguous (default) and random choice
            representation (str, optional): How to represent cluster centers. Options are: mean, medoid, maxoid, distribution, distribution_minmax (default), minmax_mean
        """

        # Using a Random Choice
        if method == "random":
            # # Make random time aggregation
            # N_timeslices = seasons * terms
            # N_hours = len(self.data)
            #
            # # Make choices
            # agg_steps = []
            # for i in range(N_timeslices):
            #     agg_steps.append(np.random.randint(N_hours))
            #
            # # Sort chronologically
            # agg_steps.sort()
            #
            # # Also save a small note with the chosen timesteps
            # with open(
            #     "Balmorel/%s/picked_times.txt"
            #     % (
            #         "W%dT%d_rand"
            #         % (seasons, terms)
            #     ),
            #     "w",
            # ) as f:
            #     f.write(pd.Series(self.data.iloc[agg_steps].index).to_string())
            raise NotImplementedError(
                "To be developed. The outcommented code in this function can be used to index the collected data and create new .inc files"
            )

        # Using tsam
        else:
            # Clip very small values (doesn't seem to be working?)
            df = self.data.clip(1e-5)

            # Assing weights 
            lowest_weight=float(weights_pr_region.Value.min())
            weights={}
            for timeseries in df.columns:
                area_sets=[area for area in timeseries.split('|') if area in weights_pr_area.index]
                region_sets=[region for region in timeseries.split('|') if region in weights_pr_region.index]
                if len(area_sets) > 0:
                    weights[timeseries] = float(weights_pr_area.loc[area_sets[0], 'Value'])
                else:
                    if len(region_sets) == 0:
                        print(f"Parameter {timeseries} did not contain any geography! Assigning lowest weight: {lowest_weight:0.6f}")
                        weights[timeseries] = lowest_weight
                    else:
                        weights[timeseries] = float(weights_pr_region.loc[region_sets[0], 'Value'])

            # Aggregate collected data
            cluster_config = tsam.ClusterConfig(method, representation, weights=weights)
            aggregation = tsam.aggregate(
                df,
                n_clusters=seasons,
                period_duration=terms,
                temporal_resolution=1,
                cluster=cluster_config,
            )

            # Make new Balmorel index
            data = aggregation.cluster_representatives
            data.index = pd.MultiIndex.from_product(
                [
                    [f"S{i:02.0f}" for i in range(1, seasons + 1)],
                    [f"T{i:03.0f}" for i in range(1, terms + 1)],
                ],
                names=["SSS", "TTT"],
            )

            # Store to self
            self.cluster_stats = aggregation
            self.agg_data = aggregation.cluster_representatives
            self.agg_resolution = {"S": seasons, "T": terms}
            self.method = method
            self.representation = representation

    def prepare_clustered_data(self, scenario: str, symbol_type: str):
        from . import IncFile  # deferred to avoid circular import with classes.py

        # Prepare placeholders
        incfiles = self.incfiles_to_save
        symbols = self.symbols
        incfile_relations = self.incfiles
        db = self.parent.input_data[scenario]

        # Prepare new, aggregated scenario and document
        self.new_scenario_path.mkdir(parents=True, exist_ok=True)
        with open(self.new_scenario_path / "../temporal_aggregation.md", "w") as f:
            f.write(
                f"Temporal aggregation made {datetime.now().strftime('%Y-%m-%d %T')}\n"
            )
            f.write(f"Method: {self.method}\n")
            f.write(f"Representation: {self.representation}\n")
            f.write(
                f"Aggregated resolution: {self.agg_resolution['S']} seasons and {self.agg_resolution['T']} terms\n"
            )

        # Loop through symbols
        for symbol in symbols[symbol_type]:
            # Collect metadata
            domains = db[symbol].domains_as_strings
            non_time_domains = [
                domain for domain in domains if domain not in ["SSS", "TTT", "Value"]
            ]
            explanatory_text = db[symbol].text

            # Collect aggregated data
            symbol_data_idx = self.agg_data.columns.str.contains(symbol)
            symbol_data = self.agg_data.loc[:, symbol_data_idx]

            # Un-standardise (prepare for Balmorel input)
            new_columns = symbol_data.columns.str.split("|", expand=True)
            symbol_data.columns = new_columns
            symbol_data.columns.names = ["symbol"] + non_time_domains

            # Take median of aggregated values if only T or S based symbol
            if symbol_type == "TTT":
                symbol_data = symbol_data.pivot_table(index="TTT", aggfunc="median")
            elif symbol_type == "SSS":
                symbol_data = symbol_data.pivot_table(index="SSS", aggfunc="median")

            # Get domain order correct
            for _ in range(len(non_time_domains)):
                symbol_data = symbol_data.stack()
            symbol_data = symbol_data.reset_index()

            domain_len = len(domains)
            symbol_data = symbol_data.pivot_table(
                index=domains[: domain_len - 1],
                columns=domains[domain_len - 1],
                values=symbol,
            )

            symbol_data.columns.name = ""
            symbol_data.index.name = ""
            symbol_data.index.names = [""] * symbol_data.index.nlevels
            if symbol_data.index.nlevels >= 2:
                symbol_data.index = [" . ".join(ind) for ind in symbol_data.index]

            # Loop through related .inc files
            if type(incfile_relations[symbol]) is str:
                iterable = [incfile_relations[symbol]]
            elif type(incfile_relations[symbol]) is list:
                iterable = incfile_relations[symbol]
            else:
                raise TypeError(
                    f"Wrong format of .inc-file-symbol relation dictionary entry for {symbol}!"
                )

            for incfile in iterable:
                # Prepare a new .inc file if it doesn't already exist
                if incfile not in incfiles.keys():
                    # Prepare filename, path, prefix and figure out if symbol == filename
                    filename, path, prefix, suffix, domains, filename_eq_symbol = (
                        prepare_incfile(incfile, symbol, domains, explanatory_text)
                    )
                    incfiles[incfile] = IncFile(
                        name=filename,
                        path=str(self.new_scenario_path),
                        body=symbol_data.to_string(),
                        prefix=prefix,
                        suffix=suffix,
                    )

                    # Store new attribute, relating to whether or not .inc filename equals symbol name
                    incfiles[incfile].sn_eq_ifn = filename_eq_symbol

                # Append to existing .inc file
                else:
                    filename, path, prefix, suffix, domains, filename_eq_symbol = (
                        prepare_incfile(incfile, symbol, domains, explanatory_text)
                    )
                    incfiles[incfile].body += "\n"
                    incfiles[incfile].body += "\n;\n" + prefix
                    incfiles[incfile].body += symbol_data.to_string()

            # Make first related .inc file the one to save data to, if no .inc file had a name equal to symbol name
            incfiles_to_save = [
                incfiles[prepared_incfile].sn_eq_ifn for prepared_incfile in iterable
            ]
            if sum(incfiles_to_save) == 0:
                incfiles[iterable[0]].sn_eq_ifn = True
            # Make sure that only one .inc file will be saved with the data
            elif sum(incfiles_to_save) > 1:
                raise ValueError(
                    f"More than one .inc file will contain data for symbol {symbol}, but only one should!"
                )

    def save_incfiles(self, scenario: str, excluded_incfiles: list = []):
        from . import IncFile  # deferred to avoid circular import with classes.py

        self.new_scenario_path = Path(
            self.parent.path
            / f"{scenario}_S{self.agg_resolution['S']}T{self.agg_resolution['T']}/data"
        )
        # Save .inc files
        for symbol_type in ["SSS,TTT", "SSS", "TTT"]:
            self.prepare_clustered_data(scenario, symbol_type)

        # TODO: Fix the fact that you are randomly saving EV leave profiles
        # to one of the .inc files, but balopt chooses a specific one,
        # which then might be empty in aggregated files
        # TODO: Split DR_DATAINPUT.inc into a time-dependant one and the
        # static input. Then excluded_incfiles can be an empty list as well
        # TODO: exclude DR_DATAINPUT and GDATA
        # TODO: INCLUDE HYRSDATA, but remember the relaxation line - put it somewhere else
        # TODO: Write "Always remember to check outputted .inc files in new scenario, to make sure important symbols are not left out" in docs as a general rule above the warning admonition

        # Save aggregated files
        incfiles = self.incfiles_to_save
        for incfile in incfiles:
            # Don't save excluded .inc files
            if incfiles[incfile].name in excluded_incfiles:
                continue

            # Only write data to one of the .inc files that symbols relate to
            if incfiles[incfile].sn_eq_ifn:
                incfiles[incfile].save()
            # Write the rest as empty files (typically addon files)
            else:
                # Empty file (addon files already included in previously written .inc file)
                with open(
                    incfiles[incfile].path + "/" + incfiles[incfile].name, "w"
                ) as f:
                    f.write("")

        # Finally save S and T
        bodies = {
            "S": ", ".join(
                [f"S{i:02.0f}" for i in range(1, self.agg_resolution["S"] + 1)]
            ),
            "T": ", ".join(
                [f"T{i:03.0f}" for i in range(1, self.agg_resolution["T"] + 1)]
            ),
        }
        for incfile in ["S", "T"]:
            f = IncFile(
                name=incfile,
                path=str(self.new_scenario_path),
                prefix=f"SET {incfile}({incfile * 3}) '{self.parent.input_data[scenario][incfile].text}'\n/\n",
                body=bodies[incfile],
                suffix="\n/;",
            ).save()

def search_in_incfiles(pattern: str, path: str | Path):
    """
    Use ripgrep to find a pattern (a string of text) in an .inc file

    Args:
       pattern (str): the string to find.
       path (str): the path to the .inc files, e.g. Balmorel/base/data.


    Returns:
       list: a list of .inc files that contain the pattern.

    """
    
    rg=Ripgrepy(pattern, str(path))
    incfiles_containing_pattern=(
        rg
        .glob('*.inc')
        .files_with_matches()
        .run()
        .as_string
        .split('\n')
        [:-1]
    )

    return incfiles_containing_pattern

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

        if ax is None:
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


def get_resolution(db):
    S = symbol_to_df(db, "S").SSS.to_list()
    T = symbol_to_df(db, "T").TTT.to_list()

    return pd.MultiIndex.from_product((S, T))


def compare_curves(scenario1: str, scenario2: str | None, overwrite: bool):
    """
    A draft function for comparing duration curves between a scenario and base at full resolution (by default)
    """

    # Get scenarios
    from . import Balmorel  # deferred to avoid circular import with classes.py
    m = Balmorel("Balmorel")
    m.load_incfiles(scenario1, overwrite=overwrite)
    res1 = get_resolution(m.input_data[scenario1])

    full_resolution = pd.MultiIndex.from_product(
        ([f"S{s:02.0f}" for s in range(1, 53)], [f"T{t:03.0f}" for t in range(1, 169)])
    )

    if scenario2 is None:
        scenario2 = "base"
        m.load_incfiles(scenario2, overwrite=overwrite)
        res2 = full_resolution
    else:
        m.load_incfiles(scenario2, overwrite=overwrite)
        res2 = get_resolution(m.input_data[scenario2])

    # Get temporal resolution choice
    for incfile in [
        "WND_VAR_T",
        "SOLE_VAR_T",
        "DH_VAR_T",
        "DE_VAR_T",
        "WTRRRVAR_T",
        "WTRRSVAR_S",
    ]:
        # Load
        df1 = symbol_to_df(m.input_data[scenario1], incfile)
        df2 = symbol_to_df(m.input_data[scenario2], incfile)

        # Get dimensions
        vars = [
            col for col in df1.columns if col not in ["SSS", "S", "TTT", "T", "Value"]
        ]
        temporal_dimension = [
            col for col in df1.columns if col in ["SSS", "S", "TTT", "T"]
        ]

        # Pivot
        df1 = (
            df1.pivot_table(index=temporal_dimension, columns=vars, values="Value")
            .reindex(full_resolution)
            .fillna(0)
            .loc[res1]
        )
        df2 = (
            df2.pivot_table(index=temporal_dimension, columns=vars, values="Value")
            .reindex(full_resolution)
            .fillna(0)
            .loc[res2]
        )
        print(df1)
        print(df2)

        # Plot all, 9 graphs max
        for batch in range(0, len(df1.columns), 9):
            # Get columns to plot
            columns = df1.columns[batch : batch + 9]

            # Prepare 9 plots
            fig, ax = plt.subplots(3, 3)

            # Iterate through the batch
            i = 0
            j = 0
            for col in columns:
                # Make duration curve
                if col != columns[-1]:
                    values1, bins1 = doLDC(
                        df1[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"color": "orange"},
                    )
                    values2, bins2 = doLDC(
                        df2[col].values, 100, plot=True, ax=ax[j][i], **{"color": "k"}
                    )
                else:
                    values1, bins1 = doLDC(
                        df1[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"label": scenario1, "color": "orange"},
                    )
                    values2, bins2 = doLDC(
                        df2[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"label": scenario2, "color": "k"},
                    )

                ax[j][i].set_title(col)

                i += 1
                if i == 3:
                    i = 0
                    j += 1

            # Save figure
            fig.legend(loc="upper center", ncol=2)
            fig.savefig(f"Balmorel/{scenario1}/{incfile}_col{batch}-{batch + 9}.png")

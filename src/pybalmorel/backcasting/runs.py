"""
Backcast runs: scenario names and their output folders

A scenario folder can hold several solved runs, each with its own
MainResults_<scenario-name>.gdx. `format` writes each run's output to
<scenario-folder>/backcastoutput/<scenario-name>/, while the files the
preparation commands write stay in backcastoutput/, since they describe
the scenario folder's input data.

Created on 17.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###          0. Settings            ###
### ------------------------------- ###

from pathlib import Path

# The Balmorel results `format` caches, and the comparison data it writes
BALMOREL_CACHE_FILES = (
    "balmorel_prices.csv",
    "balmorel_load.csv",
    "balmorel_generation.csv",
    "balmorel_flows.csv",
)
COMPARISON_FILES = (
    "loads.csv",
    "prices.csv",
    "generation.csv",
    "flows.csv",
    "load_components.csv",
)


#%% ------------------------------- ###
###        1. Run locations         ###
### ------------------------------- ###

def default_scenario_name(scenario_folder_path: str | Path, year: int) -> str:
    """The scenario name of a rolling-horizon Backcast of `year`, <folder>_R<year>.

    Args:
        scenario_folder_path (str | Path): The Balmorel scenario folder.
        year (int): The Backcast Year.

    Returns:
        str: E.g. 'backcast_R2023' for the folder 'backcast' and 2023.
    """
    return f"{Path(scenario_folder_path).resolve().name}_R{year}"


def run_output_path(scenario_folder_path: str | Path, scenario_name: str) -> Path:
    """The folder `format` writes one run's cache and comparison data to.

    Args:
        scenario_folder_path (str | Path): The Balmorel scenario folder.
        scenario_name (str): The run, as in MainResults_<scenario_name>.gdx.

    Returns:
        Path: <scenario_folder_path>/backcastoutput/<scenario_name>.
    """
    return Path(scenario_folder_path) / "backcastoutput" / scenario_name


def formatted_runs(scenario_folder_path: str | Path) -> list[str]:
    """The scenario names `format` has written output for in a scenario folder.

    Args:
        scenario_folder_path (str | Path): The Balmorel scenario folder.

    Returns:
        list[str]: Sorted names of the subfolders of backcastoutput/ that
            hold a file `format` writes.
    """
    output_path = Path(scenario_folder_path) / "backcastoutput"
    if not output_path.is_dir():
        return []
    return sorted(
        folder.name
        for folder in output_path.iterdir()
        if folder.is_dir()
        and any((folder / file).exists() for file in BALMOREL_CACHE_FILES + COMPARISON_FILES)
    )

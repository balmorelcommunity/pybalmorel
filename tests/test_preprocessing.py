"""
Pre-Processing Tools

Tests the pre-processing functions of pybalmorel

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel.classes import IncFile, Balmorel
import pandas as pd
import os


# %% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in the pyproject.toml file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)
local_balmorel_dir = os.environ.get("LOCAL_BALMOREL_DIR", None)
assert local_balmorel_dir is not None, (
    "Local Balmorel model not found. "
    "Set LOCAL_BALMOREL_DIR in the pyproject.toml file to point the Balmorel model you want to use for testing, e.g. the following if the model is one directory above this repository:\n"
    "  LOCAL_BALMOREL_DIR=../Balmorel"
)


### Create an .inc file
def test_IncFile():
    # Initiate .inc file class
    DE = IncFile(
        name="DE",
        prefix="TABLE   DE1(RRR,DEUSER,YYY)   'Annual electricity consumption (MWh)'\n",
        suffix="\n;\nDE(YYY,RRR,DEUSER) = DE1(RRR,DEUSER,YYY);",
        path="tests/output",
    )

    # Create annual electricity demand
    DE.body = pd.DataFrame(
        index=["DK1", "DK2"],
        columns=[2030, 2040, 2050],
        data=[[17e6, 20e6, 25e6], [14e6, 17e6, 20e6]],
    )

    # Fix the index format (in this case, append the DEUSER set to RRR)
    DE.body.index += " . RESE"

    # Save .inc file to path (will save as ./Balmorel/sc1/data/DE.inc)
    DE.save()

    assert "DE.inc" in os.listdir("tests/output")


def test_temporal_aggregation():

    if local_balmorel_dir is None:
        raise FileNotFoundError("No path to local Balmorel folder provided")

    m = Balmorel(local_balmorel_dir, gams_system_directory)

    m.temporal_aggregation(
        "base",
        8,
        24,
        symbols_to_aggregate={
            # 'SSS,TTT' : ['DE_VAR_T'],
            "SSS,TTT": [],
            "SSS": ["DR_RATE_S"],
            # 'SSS' : ['GKRATE'],
            "TTT": ["DR_RATE_T"],
        },
        incfile_symbol_relation={
            # 'DE_VAR_T' : ['../Balmorel/base/data/DE_VAR_T.inc','../Balmorel/base/data/INDIVUSERS_DE_VAR_T.inc'],
            "DR_RATE_S": "../Balmorel/base/data/DR_DATAINPUT.inc",
            "DR_RATE_T": "../Balmorel/base/data/DR_DATAINPUT.inc",
            "GKRATE": "../Balmorel/base/GKRATE.inc",
        },
        method="contiguous",
        overwrite=True,
    )

    m.temporal_aggregation("base", 8, 24, overwrite=True)

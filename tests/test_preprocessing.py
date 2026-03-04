"""
Pre-Processing Tools

Tests the pre-processing functions of pybalmorel

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from copy import Error
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


def test_find_timeseries():
    m = Balmorel(local_balmorel_dir, gams_system_directory)

    try:
        m.find_timeseries_input()
        raise Error(
            "An error should be returned, because .load_incfiles must be run first!"
        )
    except AssertionError:
        print(
            "find_timeseries returned an error if .load_incfiles hadnt been run as it is supposed to"
        )

    m.load_incfiles()
    ST_list, S_list, T_list = m.find_timeseries_input()

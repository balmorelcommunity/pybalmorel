"""
TITLE

Description

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel.utils import symbol_to_df
import pandas as pd
import gams
import os

#%% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in the pyproject.toml file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)


def test_symbol_to_df_mainresults():
    ws = gams.GamsWorkspace(system_directory=gams_system_directory)
    db = ws.add_database_from_gdx(os.path.abspath('examples/files/MainResults_Example1.gdx'))
    
    f = symbol_to_df(db, 'EL_PRICE_YCRST')
    assert type(f) == pd.DataFrame
    

# test_symbol_to_df_optiflow()

def test_symbol_to_df_all_endofmodel():
    ws = gams.GamsWorkspace(system_directory=gams_system_directory)
    db = ws.add_database_from_gdx(os.path.abspath('examples/files/all_endofmodel.gdx'))
    
    # A parameter
    f = symbol_to_df(db, 'DE')
    print(f)
    assert type(f) == pd.DataFrame
    
    # A set
    f = symbol_to_df(db, 'AAA')
    print(f)
    assert type(f) == pd.DataFrame
    
    

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

def test_symbol_to_df_mainresults():
    ws = gams.GamsWorkspace()
    db = ws.add_database_from_gdx(os.path.abspath('examples/files/MainResults_Example1.gdx'))
    
    f = symbol_to_df(db, 'EL_PRICE_YCRST')
    assert type(f) == pd.DataFrame
    

# test_symbol_to_df_optiflow()

def test_symbol_to_df_all_endofmodel():
    ws = gams.GamsWorkspace()
    db = ws.add_database_from_gdx(os.path.abspath('examples/files/all_endofmodel.gdx'))
    
    # A parameter
    f = symbol_to_df(db, 'DE')
    print(f)
    assert type(f) == pd.DataFrame
    
    # A set
    f = symbol_to_df(db, 'AAA')
    print(f)
    assert type(f) == pd.DataFrame
    
    

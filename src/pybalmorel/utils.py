"""
Functions
"""

import gams
import pandas as pd
from typing import Tuple
from pathlib import Path
from .formatting import balmorel_symbol_columns, optiflow_symbol_columns

preformatted_columns = {
    'balmorel' : balmorel_symbol_columns,
    'optiflow' : optiflow_symbol_columns
}

#%% ------------------------------- ###
###       1. GAMS Interface         ###
### ------------------------------- ###

### 1.1 Try to find 
def create_parameter_columns(df: pd.DataFrame,
                             db: gams.GamsDatabase,
                             symbol: str,
                             mainresult_symbol_columns: dict,
                             cols: list | None):
    if cols == None:
        try:
            df.columns = mainresult_symbol_columns[symbol] + ['Unit', 'Value']
        except (ValueError, KeyError):
            try:
                df.columns = mainresult_symbol_columns[symbol] + ['Value']
            except KeyError:
                # If no standard format exists, just use columns from GAMS
                df.columns = db[symbol].domains_as_strings + ['Value']
    else:
        df.columns = cols          
        
    return df

def create_variable_columns(df: pd.DataFrame,
                             db: gams.GamsDatabase,
                             symbol: str,
                             mainresult_symbol_columns: dict,
                             cols: list | None):
    if cols == None:
        try:
            df.columns = mainresult_symbol_columns[symbol] + ['Unit', 'Value', 'Marginal', 'Lower', 'Upper', 'Scale']
        except (ValueError, KeyError):
            try:
                df.columns = mainresult_symbol_columns[symbol] + ['Value', 'Marginal', 'Lower', 'Upper', 'Scale']
            except KeyError:
                # If no standard format exists, just use columns from GAMS
                df.columns = db[symbol].domains_as_strings + ['Value', 'Marginal', 'Lower', 'Upper', 'Scale']
    else:
        df.columns = cols          
        
    return df

def create_set_columns(df: pd.DataFrame,
                       db: gams.GamsDatabase,
                       symbol: str,
                       mainresult_symbol_columns: dict,
                       cols: list | None):
    if cols == None:
        try:
            df.columns = mainresult_symbol_columns[symbol]
        except (ValueError, KeyError):
            try:
                df.columns = mainresult_symbol_columns[symbol]
            except KeyError:
                # If no standard format exists, just use columns from GAMS
                df.columns = db[symbol].domains_as_strings
    else:
        df.columns = cols  
        
    return df

### 1.0 Converting a GDX file to a pandas dataframe
def symbol_to_df(db: gams.GamsDatabase, symbol: str, 
                 cols: list[str] | None = None, 
                 result_type: str = 'balmorel',
                 print_explanatory_text: bool = False):
    """
    Loads a symbol from a GDX database into a pandas dataframe

    Args:
        db (GamsDatabase): The loaded gdx file
        symbol (string): The desired symbol in the gdx file
        cols (list): Your defined columns, will otherwise first try to find pybalmorel default column formats for the symbol or the raw columns from the gdx  
        result_type (str): Is it a normal MainResults or a Optiflow Mainresults? Choose either 'balmorel' or 'optiflow'
        print_explanatory_text (bool): Print the text describing the symbol?
    """   
    if type(db[symbol]) == gams.GamsParameter:
        df = dict( (tuple(rec.keys), rec.value) for rec in db[symbol] )
        df = pd.DataFrame(df, index=['Value']).T.reset_index() # Convert to dataframe
        df = create_parameter_columns(df, db, symbol, preformatted_columns[result_type.lower()], cols)
    elif type(db[symbol]) == gams.GamsSet:
        df = pd.DataFrame([tuple(rec.keys)  for rec in db[symbol] ])
        df = create_set_columns(df, db, symbol, preformatted_columns[result_type.lower()], cols)
    elif type(db[symbol]) == gams.GamsVariable or type(db[symbol]) == gams.GamsEquation:
        df = dict( (tuple(rec.keys), rec.level) for rec in db[symbol] )
        df = pd.DataFrame(df, index=['Value', 'Marginal', 'Lower', 'Upper', 'Scale']).T.reset_index() # Convert to dataframe
        df = create_variable_columns(df, db, symbol, preformatted_columns[result_type.lower()], cols)
    else:
        raise TypeError('%s is not supported by symbol_to_df'%(str(type(db[symbol]))))
    
    if print_explanatory_text:
        print(db[symbol].text)
    
    return df 

def read_lines(name, file_path, make_space=True):
   
    if make_space:
        string = '\n' + ''.join(open(file_path + '/%s'%name).readlines()) + '\n'
    else:
        string = ''.join(open(file_path + '/%s'%name).readlines())
   
    return string

def read_all_incfiles(scenario: str = 'base',
                      balmorel_path: str | Path = '.'):
    """
    Will read all inc files into a string from the specified scenario. 
    Can be RAM intensive!

    Args:
       scenario (str): Balmorel scenario to read.
       balmorel_path (str): Path to Balmorel folder


    Returns:
       all_incfiles_string (str): A string of all inc file text.
    """
    
    balmorel_path = Path(balmorel_path)
    sc_incfiles = set(file.name for file in (balmorel_path / scenario / 'data').iterdir() if '.inc' in file.name)
    base_incfiles = set(file.name for file in (balmorel_path / 'base/data').iterdir() if '.inc' in file.name)
    all_incfiles = pd.Series(list(sc_incfiles | base_incfiles))

    # Get text from all incfiles 
    all_incfiles_string = ''
    for incfile in all_incfiles:
        try:
            with open(balmorel_path / scenario / 'data' / incfile, 'r', errors='ignore') as f:
                all_incfiles_string += f.read()
        except FileNotFoundError:
            with open(balmorel_path / 'base/data' / incfile, 'r', errors='ignore') as f:
                all_incfiles_string += f.read()

    return all_incfiles_string


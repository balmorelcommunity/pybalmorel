"""
Functions
"""

import gams
import pandas as pd
from typing import Tuple
from .formatting import balmorel_symbol_columns, optiflow_symbol_columns

#%% ------------------------------- ###
###       1. GAMS Interface         ###
### ------------------------------- ###

### 1.0 Converting a GDX file to a pandas dataframe
def symbol_to_df(db: gams.GamsDatabase, symbol: str, 
                 cols: Tuple[list, None] = None, 
                 parameter_or_set: str = 'parameter',
                 result_type: str = 'balmorel',
                 print_explanatory_text: bool = False):
    """
    Loads a symbol from a GDX database into a pandas dataframe

    Args:
        db (GamsDatabase): The loaded gdx file
        symbol (string): The desired symbol in the gdx file
        cols (list): Your defined columns, will otherwise first try to find pybalmorel default column formats for the symbol or the raw columns from the gdx  
        parameter_or_set (str): Is it a GAMS parameter or set? Choose either 'parameter' or 'set'
        result_type (str): Is it a normal MainResults or a Optiflow Mainresults? Choose either 'balmorel' or 'optiflow'
        print_explanatory_text (bool): Print the text describing the symbol?
    """   
    if parameter_or_set.lower() == 'parameter':
        df = dict( (tuple(rec.keys), rec.value) for rec in db[symbol] )
        df = pd.DataFrame(df, index=['Value']).T.reset_index() # Convert to dataframe
    elif parameter_or_set.lower() == 'set':
        df = pd.DataFrame([tuple(rec.keys)  for rec in db[symbol] ])
    else:
        print('Choose either parameter or set!')

    ## Format by result type
    result_type = result_type.lower()

    if result_type=='balmorel':
        mainresult_symbol_columns = balmorel_symbol_columns
    elif result_type=='optiflow':
        mainresult_symbol_columns = optiflow_symbol_columns

    #Name columns
    if cols == None and parameter_or_set.lower() == 'parameter':
        try:
            df.columns = mainresult_symbol_columns[symbol] + ['Unit', 'Value']
        except (ValueError, KeyError):
            try:
                df.columns = mainresult_symbol_columns[symbol] + ['Value']
            except KeyError:
                # If no standard format exists, just use columns from GAMS
                df.columns = db[symbol].domains_as_strings + ['Value']
    elif cols == None:
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
    
    if print_explanatory_text:
        print(db[symbol].text)
    
    return df 

def read_lines(name, file_path, make_space=True):
   
    if make_space:
        string = '\n' + ''.join(open(file_path + '/%s'%name).readlines()) + '\n'
    else:
        string = ''.join(open(file_path + '/%s'%name).readlines())
   
    return string


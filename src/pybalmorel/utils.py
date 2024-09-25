"""
Functions
"""

import gams
import pandas as pd
from .formatting import mainresult_symbol_columns

#%% ------------------------------- ###
###       1. GAMS Interface         ###
### ------------------------------- ###

### 1.0 Converting a GDX file to a pandas dataframe
def symbol_to_df(db: gams.GamsDatabase, symbol: str, 
                 cols: str = 'None', parameter_or_set: str = 'parameter'):
    """
    Loads a symbol from a GDX database into a pandas dataframe

    Args:
        db (GamsDatabase): The loaded gdx file
        symbol (string): The wanted symbol in the gdx file
        cols (list): The columns
        parameter_or_set (str): Choose either 'parameter' or 'set'
    """   
    if parameter_or_set == 'parameter':
        df = dict( (tuple(rec.keys), rec.value) for rec in db[symbol] )
        df = pd.DataFrame(df, index=['Value']).T.reset_index() # Convert to dataframe
    elif parameter_or_set == 'set':
        df = pd.DataFrame([tuple(rec.keys)  for rec in db[symbol] ])
    else:
        print('Choose either parameter or set!')

    if cols == 'None':
        try:
            df.columns = mainresult_symbol_columns[symbol] + ['Unit', 'Value']
        except KeyError:
            print('Standard column format not found for this symbol')
    elif type(cols) == list:
        df.columns = cols
    return df 

 
def read_lines(name, file_path, make_space=True):
   
    if make_space:
        string = '\n' + ''.join(open(file_path + '/%s'%name).readlines()) + '\n'
    else:
        string = ''.join(open(file_path + '/%s'%name).readlines())
   
    return string


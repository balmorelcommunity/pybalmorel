"""
Functions
"""

from typing import Union
import gams
import os
import pandas as pd
from .formatting import mainresults_symbol_columns

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
        df = dict( (tuple(rec.keys) ) for rec in db[symbol] )
        df = pd.DataFrame(dict( (tuple(rec.keys)) for rec in db[symbol] ), index=['Set']).T.reset_index()
    else:
        print('Choose either parameter or set!')

    if cols == 'None':
        try:
            df.columns = mainresults_symbol_columns[symbol] + ['Unit', 'Value']
        except KeyError:
            print('Standard column format not found for this symbol')
    elif type(cols) == list:
        df.columns = cols
    return df 

class IncFile:
    """A useful class for creating .inc-files for GAMS models
    Args:
    prefix (str): The first part of the .inc file.
    body (str): The main part of the .inc file.
    suffix (str): The last part of the .inc file.
    name (str): The name of the .inc file.
    path (str): The path to save the file, defaults to 'Balmorel/base/data'.
    """
    def __init__(self, prefix: str = '', body: str = '', 
                 suffix: str = '', name: str = 'name', 
                 path: str = 'Balmorel/base/data/'):
        self.prefix = prefix
        self.body = body
        self.suffix = suffix
        self.name = name
        self.path = path

    def body_concat(self, df: pd.DataFrame):
        """Concatenate a body temporarily being a dataframe to another dataframe
        """
        self.body = pd.concat((self.body, df)) # perhaps make a IncFile.body.concat function.. 

    def body_prepare(self, index: list, columns: list,
                    values: str = 'Value',
                    aggfunc: str ='sum',
                    fill_value: Union[str, int] = ''):
    
        # Pivot
        self.body = self.body.pivot_table(index=index, columns=columns, 
                            values=values, aggfunc=aggfunc,
                            fill_value=fill_value)
        
        # Check if there are multiple levels in index and 
        # concatenate with " . "
        if hasattr(self.body.index, 'levels'):
            new_ind = pd.Series(self.body.index.get_level_values(0))
            for level in range(1, len(self.body.index.levels)):
                new_ind += ' . ' + self.body.index.get_level_values(level) 

            self.body.index = new_ind
        
        # Check if there are multiple levels in columns and 
        # concatenate with " . "
        if hasattr(self.body.columns, 'levels'):
            new_ind = pd.Series(self.body.columns.get_level_values(0))
            for level in range(1, len(self.body.columns.levels)):
                new_ind += ' . ' + self.body.columns.get_level_values(level) 

            self.body.columns = new_ind
            
        # Delete names
        self.body.columns.name = ''
        self.body.index.name = ''


    def save(self):
        if self.name[-4:] != '.inc':
            self.name += '.inc'  
       
        with open(os.path.join(self.path, self.name), 'w') as f:
            f.write(self.prefix)
            if type(self.body) == str:
                f.write(self.body)
            elif type(self.body) == pd.DataFrame:
                f.write(self.body.to_string())
            else:
                print('Wrong format of %s.body!'%self.name)
                print('No body written')
            f.write(self.suffix)
 
 
def read_lines(name, file_path, make_space=True):
   
    if make_space:
        string = '\n' + ''.join(open(file_path + '/%s'%name).readlines()) + '\n'
    else:
        string = ''.join(open(file_path + '/%s'%name).readlines())
   
    return string


#%% ------------------------------- ###
###       2. Plotting Tools         ###
### ------------------------------- ###


# Implement the scripts from balmorel-postprocessing tool below (write functions)
# from plotting import MapsBalmorel, ProductionProfile, ProductionMap, LoadGDX
from .plotting.maps_balmorel import plot_map

from .plotting.interactive_barchart import MainResults


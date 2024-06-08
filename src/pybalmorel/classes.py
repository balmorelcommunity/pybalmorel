"""
Created on 08.06.2024

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import pandas as pd
from typing import Union
import os
import gams
import numpy as np
from .functions import symbol_to_df
from .plotting.interactive_barchart import bar_chart
from .plotting.production_profile import plot_profile

#%% ------------------------------- ###
###           1. Outputs            ###
### ------------------------------- ###

class MainResults:
    def __init__(self, files: Union[str, list, tuple], 
                 paths: Union[str, list, tuple] = '.', 
                 scenario_names: Union[str, list, tuple] = None):
        """
        Initialises the MainResults class and loads gdx result file(s)

        Args:
            files (str, list, tuple): Name(s) of the gdx result file(s)
            paths (str, list, tuple): Path(s) to the gdx result file(s), assumed in same path if only one path given, defaults to working directory
            scenario_names (str, list, tuple): Name of scenarios corresponding to each gdx file, defaults to ['SC1', 'SC2', ..., 'SCN'] if None given
        """

        if type(files) == str:
            # Change filenames to list if just one string
            files = [files]
            
        ## File paths
        if type(paths) == str:
            # Create identical paths if only one given
            paths = [paths]*len(files)
            
        elif ((type(paths) == list) or (type(paths) == tuple)) and (len(paths) == 1):
            paths = paths*len(files)
            
        elif len(files) != len(paths):
            # Raise error if not given same amount of paths and files     
            raise Exception("%d files, but %d paths given!\nProvide only one path or the same amount of paths as files"%(len(files), len(paths)))
        
        ## Scenario Names
        if scenario_names == None:
            # Try to make scenario names from filenames, if None given
            scenario_names = pd.Series(files).str.replace('MainResults_', '').str.replace('MainResults','').str.replace('.gdx', '')
            
            # Check if names are identical or empty
            if (len(scenario_names.unique()) != len(scenario_names)) or (np.all(scenario_names == '')):
                scenario_names = ['SC%d'%(i+1) for i in range(len(files))] # if so, just make generic names
            else:
                scenario_names = list(scenario_names)
                
        elif type(scenario_names) == str:
            scenario_names = [scenario_names]
            
        if len(files) != len(scenario_names):    
            # Raise error if not given same amount of scenario_names and files
            raise Exception("%d files, but %d scenario names given!\nProvide none or the same amount of scenario names as files"%(len(files), len(scenario_names)))
            
        ## Store MainResult databases
        self.sc = scenario_names
        self.db = {}
        ws = gams.GamsWorkspace()
        for i in range(len(files)):
            self.db[scenario_names[i]] = ws.add_database_from_gdx(os.path.join(os.path.abspath(paths[i]), files[i]))
     

    def get_result(self, symbol: str, cols: str = 'None'):
        # Placeholder
        df = pd.DataFrame()
        
        for SC in self.sc:
            # Get results from each scenario
            temp = symbol_to_df(self.db[SC], symbol, cols)
            temp['Scenario'] = SC 
            
            # Put scenario in first column
            temp = temp.loc[:, ['Scenario'] + list(temp.columns[:-1])]
            
            # Save
            df = pd.concat((df, temp), ignore_index=True)
            
        return df  
    
    ### Plotting Functions
    
    # Interactive Bar Chart
    def bar_chart(self):
        bar_chart(self)
        
    # Production Profile
    def plot_profile(self, scenario: str, year: int,
                     commodity: str, columns: str,
                     region: str, style: str = 'light'):
        plot_profile(self, scenario=scenario, year=year,
                     commodity=commodity, columns=columns,
                     region=region, style=style)

#%% ------------------------------- ###
###            2. Inputs            ###
### ------------------------------- ###

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
 

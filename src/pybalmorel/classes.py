"""
Created on 08.06.2024

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os
import sys
import shutil
import gams
import pandas as pd
import numpy as np
from typing import Union, Tuple
from functools import partial
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from .utils import symbol_to_df
from .interactive.interactive_functions import interactive_bar_chart
from .interactive.dashboard.eel_dashboard import interactive_geofilemaker
from .plotting.production_profile import plot_profile
from .plotting.maps_balmorel import plot_map

#%% ------------------------------- ###
###           1. Outputs            ###
### ------------------------------- ###

class MainResults:
    def __init__(self, files: Union[str, list, tuple], 
                 paths: Union[str, list, tuple] = '.', 
                 scenario_names: Union[str, list, tuple] = None,
                 system_directory: str = None):
        """
        Initialises the MainResults class and loads gdx result file(s)

        Args:
            files (str, list, tuple): Name(s) of the gdx result file(s)
            paths (str, list, tuple): Path(s) to the gdx result file(s), assumed in same path if only one path given, defaults to working directory
            scenario_names (str, list, tuple): Name of scenarios corresponding to each gdx file, defaults to ['SC1', 'SC2', ..., 'SCN'] if None given
            system_directory (str, optional): GAMS system directory. Is not used if not specified.
        """

        ## Loading scenarios
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
            
            # Rename MainResults with no suffix
            if np.any(scenario_names == ''):
                idx = list(scenario_names[scenario_names == ''].index)
                for ind in idx:
                    scenario_names[ind] = paths[ind].split('/model')[0].split(r'Balmorel')[1].replace('\\','')
                                
            # Check if some names are identical
            if len(scenario_names.unique()) != len(scenario_names):
                print('\n--------------WARNING!--------------\nIdentical scenario names detected, which will result in double counting when analysing')
                print('Scenarios: ', ', '.join(list(scenario_names)), '\n--------------WARNING!--------------\n')                

            scenario_names = list(scenario_names)

        elif type(scenario_names) == str:
            scenario_names = [scenario_names]
            
        if len(files) != len(scenario_names):    
            # Raise error if not given same amount of scenario_names and files
            raise Exception("%d files, but %d scenario names given!\nProvide none or the same amount of scenario names as files"%(len(files), len(scenario_names)))
            
        ## Store MainResult databases
        self.files = files
        self.paths = paths
        self.sc = scenario_names
        self.db = {}
            
        if system_directory != None:
            ws = gams.GamsWorkspace(system_directory=system_directory)
        else:
            ws = gams.GamsWorkspace()
            
        for i in range(len(files)):    
            print(os.path.join(os.path.abspath(paths[i]), files[i]))
            self.db[scenario_names[i]] = ws.add_database_from_gdx(os.path.join(os.path.abspath(paths[i]), files[i]))
     
    # Getting a certain result
    def get_result(self, symbol: str, cols: str = 'None') -> pd.DataFrame:
        """Get a certain result from the loaded gdx file(s) into a pandas DataFrame

        Args:
            symbol (str): The desired result, e.g. PRO_YCRAGF
            cols (str, optional): Specify custom columns. Defaults to pre-defined formats.

        Returns:
            pd.DataFrame: The output DataFrame
        """
        # Placeholder
        df = pd.DataFrame()
        
        for SC in self.sc:
            # Get results from each scenario
            try :
                temp = symbol_to_df(self.db[SC], symbol, cols)
                temp['Scenario'] = SC 
                # Put scenario in first column
                temp = temp.loc[:, ['Scenario'] + list(temp.columns[:-1])]
                # Save
                df = pd.concat((df, temp), ignore_index=True)
            
            except ValueError :
                print(f'{SC} doesn\'t have any value in the table {symbol}')
            
        return df  
    
    ## Plotting tools
    # Interactive bar chart plotting
    def interactive_bar_chart(self):
        """
        GUI for bar chart plotting
        """
        return  interactive_bar_chart(self)        
    
    # Plotting a production profile
    def plot_profile(self,
                     commodity: str,  
                     year: int, 
                     scenario: str = 0,
                     columns: str = 'Technology',
                     region: str = 'ALL',
                     style: str = 'light') -> Tuple[Figure, Axes]:
        """Plots the production profile of a commodity, in a year, for a certain scenario

        Args:
            commodity (str): The commodity (Electricity, Heat or Hydrogen)
            year (int): The model year to plot
            scenario (str, optional): Defaults to the first scenario in MainResults.
            columns (str, optional): Technology or Fuel as . Defaults to 'Technology'.
            region (str, optional): Which country, region or area to plot. Defaults to 'ALL'.
            style (str, optional): Plot style, light or dark. Defaults to 'light'.

        Returns:
            Figure, Axes: The figure and axes objects for further manipulations 
        """
        return plot_profile(self, commodity, year, scenario, columns, region, style)
        
    
    def plot_map(self, 
                scenario: str, 
                commodity: str, 
                year: int,
                path_to_geofile: str = None,  
                bypass_path: str = None, 
                geo_file_region_column: str = 'id', 
                style: str = 'light') -> Tuple[Figure, Axes]:
        """Plots the transmission capacities in a scenario, of a certain commodity

        Args:
            path_to_result (str): Path to the .gdx file
            scenario (str): The scenario name
            commodity (str): Electricity or hydrogen
            year (int): Model year 
            path_to_geofile (str, optional): The path to the fitting geofile. Defaults to '../geofiles/2024 BalmorelMap.geojson' in package directory.
            bypass_path (str, optional): Extra coordinates for transmission lines for beauty. Defaults to '../geofiles/bypass_lines' in package directory.
            geo_file_region_column (str, optional): The columns containing the region names of MainResults. Defaults to 'id'.
            style (str, optional): Plot style. Defaults to 'light'.

        Returns:
            Tuple[Figure, Axes]: The figure and axes objects of the plot
        """
        # Find path of scenario
        idx = np.array(self.sc) == scenario
        path = np.array(self.paths)[idx][0]
        files = np.array(self.files)[idx][0]
        path = os.path.join(path, files)
        
        return plot_map(path, scenario, commodity, 
                        year, path_to_geofile, bypass_path,
                        geo_file_region_column, style)
        
    # For wrapping functions, makes it possible to add imported functions in __init__ easily
    def _existing_func_wrapper(self, function, *args, **kwargs):
        return function(self, *args, **kwargs)     


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
 
class Balmorel:
    """A class that recognises the Balmorel folder structure, can be used to run scenarios or results

    Args:
        model_folder (str): The top level folder of Balmorel, where base and simex are located
    """

    def __init__(self, model_folder: str, gams_system_directory: str = None):
        
        # Get GAMS system directory (the default none will make GAMS find it by itself)
        self._gams_system_directory = gams_system_directory
        
        # Get full path
        self.path = os.path.abspath(model_folder)
        
        if not('base' in os.listdir(self.path)) or not('simex' in os.listdir(self.path)):
            raise Exception("Incorrect Balmorel folder, couldn't find base and/or simex in %s"%self.path)
        
        # Get scenario folders
        scenarios = [SC for SC in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, SC)) and SC != 'simex' and SC != '.git']
        
        # Check validity of scenario folders and make list of scenarios
        self.scenarios = []
        self.input_data = {}
        for SC in scenarios:
            if os.path.exists(os.path.join(self.path, SC, 'model/Balmorel.gms')) and \
                os.path.exists(os.path.join(self.path, SC, 'model/cplex.op4')):
                    self.scenarios.append(SC)
            else:
                print('Folder %s not added to scenario as the necessary %s/model/Balmorel.gms and/or %s/model/cplex.op4 did not exist'%tuple([SC]*3))

    def collect_results(self):
        
        files = []
        paths = []
        for SC in self.scenarios:
            path = os.path.join(self.path, '%s/model'%SC)
            mainresults_files = pd.Series(os.listdir(path))
            mainresults_files = mainresults_files[(mainresults_files.str.find('MainResults') != -1) & (mainresults_files.str.find('.gdx') != -1)]
            files += list(mainresults_files)
            paths += [path]*len(mainresults_files)

        self.results = MainResults(files=files ,paths=paths, system_directory=self._gams_system_directory)
            
    def run(self, scenario: str, cmd_line_options: dict = {}):
        
        # Working directory
        wk_dir = os.path.join(self.path, '%s/model'%scenario)
        
        # Add options
        ws = gams.GamsWorkspace(working_directory=wk_dir, system_directory=self._gams_system_directory)
        opt = ws.add_options()
        for key in cmd_line_options.keys():
            opt.defines[key] = cmd_line_options[key]
        
        # Run Balmorel
        try:
            job = ws.add_job_from_file(os.path.join(wk_dir, 'Balmorel'), job_name=scenario)
            job.run(opt)
        except gams.GamsExceptionExecution as e:
            exec_error = e
            print('Execution error! Check output, division by zero in OUTPUT_SUMMARY can happen and may not be a problem')
        
        # Check feasibility
        with open(os.path.join(wk_dir, '%s.lst'%scenario), 'r') as f:
            output = pd.Series(f.readlines())

        output = output[(output.str.find('LP status') != -1) | (output.str.find('MIP status') != -1)] # Find all status
        all_feasible = output[output.str.find('infeasible') != -1].empty # Check if none are infeasible
        if not(all_feasible):
            raise Exception('Model run infeasible!')
        
        # Raise error from before
        if 'exec_error' in locals():
            raise exec_error
        
        
    def load_incfiles(self, 
                      scenario: str = 'base', 
                      use_provided_read_files: bool = True,
                      read_file: str = 'Balmorel_ReadData',
                      overwrite: bool = False):
        """Will load .inc files from the specific scenario

        Args:
            scenario (str, optional): The scenario that you . Defaults to 'base'.
            use_provided_read_files (bool, optional): Use provided Balmorel_ReadData.gms and Balmorelbb4_ReadData.inc. Defaults to True.
            read_file (str, optional): The name of the read file to be executed. Defaults to Balmorel_ReadData
            overwrite (bool, optional): Will overwrite an existing %scenario%_input_data.gdx file from a previous .load_incfiles execution 
            
        Raises:
            KeyError: _description_
        """
        
        if not(scenario in self.scenarios):
            raise KeyError('%s scenario wasnt found.\nRun this Balmorel(...) class again if you just created the %s scenario.'%(scenario, scenario))
        
        
        # Path to the GAMS system directory
        model_folder = os.path.join(self.path, scenario, 'model')
        
        if os.path.exists(os.path.join(model_folder, '%s_input_data.gdx'%scenario)) and not(overwrite):
            ws = gams.GamsWorkspace()
            db = ws.add_database_from_gdx(os.path.join(model_folder, '%s_input_data.gdx'%scenario))
            self.input_data[scenario] = db
            
        else:
            # Are you using the provided 'ReadData'-Balmorel files or a custom one?
            use_provided_read_files = True
            if use_provided_read_files:
                pkgdir = sys.modules['pybalmorel'].__path__[0]
                # Copy Balmorel_ReadData and Balmorelbb4_ReadData 
                # into the model folder if there isn't one already
                for file in ['Balmorel_ReadData.gms', 'Balmorelbb4_ReadData.inc']:
                    if not(os.path.exists(os.path.join(model_folder, file))):
                        shutil.copyfile(os.path.join(pkgdir, file), os.path.join(model_folder, file))
                        print(os.path.join(model_folder, file))

            # Initialize GAMS Workspace
            ws = gams.GamsWorkspace(working_directory=model_folder)

            # Set options
            opt = ws.add_options()
            opt.gdx = '%s_input_data.gdx'%scenario # Setting the output gdx name (note, could be overwritten by the cmd line options, which is intended)        
            
            # Load the GAMS model
            model_db = ws.add_job_from_file(os.path.join(model_folder, read_file), job_name=scenario)

            # Run the GAMS file
            model_db.run(opt)

            # Store the database (will take some minutes)
            self.input_data[scenario] = model_db.get_out_db()
            
            
class GUI:
    def __init__(self) -> None:
        pass
    
    # Interactive bar chart plotting
    def bar_chart(self, MainResults_instance):
        """Interactive GUI to plot bar charts from MainResults

        Args:
            MainResults_instance (class): Loaded MainResults

        Returns:
            None: An interactive GUI is opened to plot bar charts 
        """                
        return  interactive_bar_chart(MainResults_instance)  
    
    def geofilemaker():
        """Opens a GUI to interactively generate necessary .inc files for Balmorel geography

        Returns:
            None: An interactive GUI to generate geographic .inc files
        """
        return interactive_geofilemaker()
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
from dataclasses import dataclass, field
from urllib.parse import urljoin
import requests
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
                 scenario_names: str | list | tuple | None = None,
                 system_directory: str | None = None,
                 result_type: str = 'balmorel'):
        """
        Initialises the MainResults class and loads gdx result file(s)

        Args:
            files (str, list, tuple): Name(s) of the gdx result file(s)
            paths (str, list, tuple): Path(s) to the gdx result file(s), assumed in same path if only one path given, defaults to working directory
            scenario_names (str, list, tuple): Name of scenarios corresponding to each gdx file, defaults to ['SC1', 'SC2', ..., 'SCN'] if None given
            system_directory (str, optional): GAMS system directory. Is not used if not specified.
            result_type (str, optional): Specifies the type of result to extract. Use 'optiflow' for OptiFlow results. If not specified, it defaults to extracting Balmorel GDX results.
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
        self.type = result_type
        self.db = {}
            
        if system_directory != None:
            ws = gams.GamsWorkspace(system_directory=system_directory)
            self._gams_system_directory = system_directory
        else:
            ws = gams.GamsWorkspace()
            
        for i in range(len(files)):    
            print('Loading', os.path.join(os.path.abspath(paths[i]), files[i]))
            try:
                self.db[scenario_names[i]] = ws.add_database_from_gdx(os.path.join(os.path.abspath(paths[i]), files[i]))
            except gams.control.workspace.GamsException as e:
                raise FileNotFoundError(f'\nCouldnt add file {files[i]}!\nBeware of æ,ø,å,ö,ü,ä or other non-english letters in the folders of your absolute path: {os.path.abspath(paths[i])}.\nThe GAMS API requires an absolute path with no non-english letters.')
     
    # Getting a certain result
    def get_result(self, symbol: str, cols: list | None = None) -> pd.DataFrame:
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
                temp = symbol_to_df(self.db[SC], symbol, cols, result_type=self.type)
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
    def interactive_bar_chart(self, plot_style: str = 'light'):
        """
        GUI for bar chart plotting
        """
        return  interactive_bar_chart(self, plot_style)        
    
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
                 year: int,
                 commodity: str | None = None,
                 lines: str | None = None, 
                 generation: str | None = None,
                 background : str | None = None,
                 save_fig: bool = False,
                 path_to_geofile: str | None = None,
                 geo_file_region_column: str = 'id',
                 **kwargs) -> Tuple[Figure, Axes]:
        """Plots the transmission capacities or flow in a scenario, of a certain commodity and the generation capacities or production of the regions.

        Args:
            path_to_result (str): Path to the .gdx file
            scenario (str): The scenario name       
            year (int): The year of the results
            commodity (str, optional): Commodity to be shown in the map. Choose from ['Electricity', 'Hydrogen'].
            lines (str, optional): Information plots with the lines. Choose from ['Capacity', 'FlowYear', 'FlowTime', 'UtilizationYear', 'UtilizationTime].
            generation (str, optional): Generation information plots on the countries. Choose from ['Capacity', 'Production', 'ProductionTime].
            background (str, optional): Background information to be shown on the map. Choose from ['H2 Storage', 'Elec Storage']. Defaults to 'None'.
            save_fig (bool, optional): Save the figure or not. Defaults to False.
            path_to_geofile (str, optional): Path to a personalized geofile. Defaults to None.
            geo_file_region_column (str, optional): Column name of the region names in the geofile. Defaults to 'id'.
            Structural additional options:
                **generation_commodity (str, optional): Commodity to be shown in the generation map, if not specified, same as line commodity. Defaults to commodity.
                **S (str, optional): Season for FlowTime or UtilizationTime. Will pick one random if not specified.
                **T (str, optional): Hour for FlowTime or UtilizationTime. Will pick one random if not specified.
                **exo_end (str, optional): Show only exogenous or endogenous capacities. Choose from ['Both', 'Endogenous', 'Exogenous']. Defaults to 'Both'.
                **generation_exclude_Import_Cap_H2 (bool, optional): Do not plot the capacities and production related to H2 Import (will be shown as line). Defaults to True.
                **generation_exclude_H2Storage (bool, optional): Do not plot capacity or production of the H2 storage. Defaults to True.
                **generation_exclude_ElectricStorage (bool, optional): Do not plot capacity or production of Electric storage. Defaults to True.
                **generation_exclude_Geothermal (bool, optional): Do not plot the production of Geothermal. Defaults to True.
                **coordinates_geofile_offset (float, optional): Geofile coordinates offset from the min and max of the geofile. Defaults to 0.5.
                **filename (str, optional): The name of the file to save, if save_fig = True. Defaults to .png if no extension is included.
            Visual additional options:
                **title_show (bool, optional): Show title or not. Defaults to True.
                **legend_show (bool, optional): Show legend_show or not. Defaults to True.
                **show_country_out (bool, optional): Show countries outside the model or not. Defaults to True.
                **choosen_map_coordinates (str, optional): Choose the map to be shown. Choose from ['EU', 'DK', 'Nordic']. Defaults to 'EU'.
                **map_coordinates (list, optional): Coordinates of the map if custom coordinates needed. Defaults to ''.
                Lines options :
                    **line_width_cat (str, optional): Way of determining lines width. Choose from ['log', 'linear', 'cluster']. Defaults to 'log'.
                    **line_show_min (int, optional): Minimum transmission capacity (GW) or flow (TWh) shown on map. Defaults to 0.
                    **line_width_min (float, optional): Minimum width of lines, used if cat is linear or log. Defaults to 0.5. Value in point.
                    **line_width_max (float, optional): Maximum width of lines, used if cat is linear or log. Defaults to 12. Value in point.
                    **line_cluster_values (list, optional): The capacity grouping necessary if cat is 'cluster'. Defaults values depends on commodity. Used for the legend if defined.
                    **line_cluster_widths (list, optional): The widths for the corresponding capacity group if cat is cluster (has to be same size as line_cluster_values). Used for the legend if defined. Values in point.
                    **line_legend_cluster_values (list, optional): The legend capacity grouping if a specific legend is needed. Is handled automatically if not defined. Not used if cat is 'cluster'.
                    **line_opacity (float, optional): Opacity of lines. Defaults to 1.
                    **line_label_show (bool, optional): Showing or not the value of the lines. Defaults to False.
                    **line_label_min (int, optional): Minimum transmission capacity (GW) or flow (TWh) shown on map in text. Defaults to 0.
                    **line_label_decimals (int, optional): Number of decimals shown for line capacities. Defaults to 1.
                    **line_label_fontsize (int, optional): Font size of transmission line labels. Defaults to 10.
                    **line_flow_show (bool, optional): Showing or not the arrows on the lines. Defaults to True.
                Generation options :
                    **generation_show_min (float, optional): Minimum generation capacity (GW) or production (TWh) shown on map. Defaults to 0.001.
                    **generation_display_type (str, optional): Type of display on regions. Choose from ['Pie']. Defaults to 'Pie'.
                    **generation_var (str, optional): Variable to be shown in the pie chart. Choose from ['TECH_TYPE', 'FFF']. Defaults to 'TECH_TYPE'.
                    **pie_radius_cat (str, optional): Way of determining pie size. Choose from ['log', 'linear', 'cluster']. Defaults to 'log'.
                    **pie_show_min (int, optional): Minimum transmission capacity (GW) or flow (TWh) shown on map. Defaults to 0. Value in data unit.
                    **pie_radius_min (float, optional): Minimum width of lines, used if cat is linear or log. Defaults to 0.2. Value in data unit.
                    **pie_radius_max (float, optional): Maximum width of lines, used if cat is linear or log. Defaults to 1.4. Value in data unit.
                    **pie_cluster_values (list, optional) = The capacity groupings necessary if cat is 'cluster'. Defaults values depends on commodity. Used for the legend if defined.
                    **pie_cluster_radius (list, optional) = The radius for the corresponding capacity group if cat is cluster (has to be same size as pie_cluster_values). Used for the legend if defined. Values in data unit.
                    **pie_legend_cluster_radius (list, optional) = The legend capacity grouping if a specific legend is needed. Is handled automatically if not defined. Not used if cat is 'cluster'. 
                Background options :
                    **background_name (str, optional): Personalized name of the background (mostly useful for Custom).
                    **background_unit (str, optional): Personalized unit of the background (mostly useful for Custom).
                    **background_scale (list, optional) : Scale used for the background coloring. Defaults to (0, Max value found in results).
                    **background_scale_tick (int, optional) : A tick every x units in the background legend. Defaults to 2.
                    **background_label_show (bool, optional): Showing or not the background label on the countries. Defaults to False.
                    **background_label_fontsize (int, optional): Font size of the background labels. Defaults to 10.
            Colors additional options:
                **background_color (str, optional): Background color of the map. Defaults to 'white'.
                **regions_ext_color (str, optional): Color of regions outside the model. Defaults to '#d3d3d3'.
                **regions_model_color (str, optional): Color of regions inside the model. Defaults to 'linen'.
                **line_color (str, optional): Color of lines network. Defaults to 'green' for electricity and '#13EAC9' for hydrogen.
                **line_label_color (str, optional): Color of line labels. Defaults to 'black'.
                **generation_tech_color (dict, optional): Dictionnary of colors for each technology. Defaults to colors for electricity and hydrogen.
                **generation_fuel_color (dict, optional): Dictionnary of colors for each fuel. Defaults to colors for electricity and hydrogen.
                **background_colormap (str, optional): Personalized background colormap on the countries.
                **background_label_color (str, optional): Color of the background labels. Defaults to 'black'.
            Geography additional options:
                **coordinates_RRR_path = Path to the csv file containing the coordinates of the regions centers.
                **bypass_path = Path to the csv file containing the coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions.
                **hydrogen_third_nations_path = Path to the csv file containing the coordinates of h2 import lines from third nations.
                **countries_color_path = Path to the csv file containing the personnalized colors of the countries
                **countries_background_path = Path to the csv file containing the personnalized background of the countries

        Returns:
            Tuple[Figure, Axes]: The figure and axes objects of the plot
        """
        # Find path of scenario
        idx = np.array(self.sc) == scenario
        path = np.array(self.paths)[idx][0]
        files = np.array(self.files)[idx][0]
        path = os.path.join(path, files)
        
        if hasattr(self, "_gams_system_directory"):
            return plot_map(path, scenario, year, commodity, lines, generation, background, save_fig, path_to_geofile, geo_file_region_column, 
                            system_directory=self._gams_system_directory, **kwargs)
        else:
            return plot_map(path, scenario, year, commodity, lines, generation, background, save_fig, path_to_geofile, geo_file_region_column, **kwargs)
        
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

    def locate_results(self):
        """
        Locates results, which is faster than collecting them if you just want an overview
        """
                
        self.files = []
        self.paths = []
        self.scenario_names = []
        self.scfolder_to_scname = {}
        self.scname_to_scfolder = {}
        for SC in self.scenarios:
            path = os.path.join(self.path, '%s/model'%SC)
            mainresults_files = pd.Series(os.listdir(path))
            mainresults_files = mainresults_files[(mainresults_files.str.find('MainResults') != -1) & (mainresults_files.str.find('.gdx') != -1)]
            self.files += list(mainresults_files)
            self.paths += [path]*len(mainresults_files)
            if len(mainresults_files) == 1:
                self.scenario_names += [SC]
                self.scfolder_to_scname[SC] = [SC]
                self.scname_to_scfolder[SC] = SC
            else:
                mainresults_files = (
                    mainresults_files
                    .str.replace('MainResults_', '')
                    .str.replace('.gdx', '')
                )
                self.scenario_names += list(mainresults_files)
                self.scfolder_to_scname[SC] = list(mainresults_files)
                
                for scenario_name in mainresults_files:
                    self.scname_to_scfolder[scenario_name] = SC 

    def collect_results(self):
        """
        Collects results
        """

        self.locate_results()

        self.results = MainResults(files=self.files, paths=self.paths, scenario_names=self.scenario_names, system_directory=self._gams_system_directory)
            
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
            ws = gams.GamsWorkspace(system_directory=self._gams_system_directory)
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
            ws = gams.GamsWorkspace(working_directory=model_folder, system_directory=self._gams_system_directory)

            # Set options
            opt = ws.add_options()
            opt.gdx = '%s_input_data.gdx'%scenario # Setting the output gdx name (note, could be overwritten by the cmd line options, which is intended)        
            
            # Load the GAMS model
            model_db = ws.add_job_from_file(os.path.join(model_folder, read_file), job_name=scenario)

            # Run the GAMS file
            model_db.run(opt)

            # Store the database (will take some minutes)
            self.input_data[scenario] = model_db.get_out_db()
            
@dataclass
class TechData:
    files: dict = field(default_factory=lambda: {
        "el_and_dh" :   "technology_data_for_el_and_dh.xlsx",
        "indi_heat" :   "technology_data_heating_installations.xlsx",
        "ren_fuels" :   "data_sheets_for_renewable_fuels.xlsx",
        "storage"   :   "technology_datasheet_for_energy_storage.xlsx",
        "ccts"      :   "technology_data_for_carbon_capture_transport_storage.xlsx",
        "indu_heat" :   "technology_data_for_industrial_process_heat_0.xlsx",
        "trans"     :   "energy_transport_datasheet.xlsx"                              
    })
    path: str = r"C:\Users\mathi\gitRepos\balmorel-preprocessing\RawDataProcessing\Data\Technology Data" # Change this later
    
    def load(self, file: str):
        f = pd.read_excel(os.path.join(self.path, self.files[file]),
                          sheet_name='alldata_flat')
        return f

    # Function to download a file from a URL and save it to a specified folder
    def download_file(self, url, save_folder, filename=None):
        """
        Downloads a file from a given URL and saves it to a specified folder.
        Args:
            url (str): The URL of the file to download.
            save_folder (str): The folder where the file should be saved.
            filename (str, optional): The name to save the file as. If not provided, the filename is extracted from the URL.
        Returns:
            str: The full path to the saved file.
        Raises:
            requests.exceptions.RequestException: If the download fails.
        Notes:
            - The function ensures that the save folder exists.
            - The file is downloaded in chunks to handle large files efficiently.
        chunk_size:
            The size of each chunk of data to be written to the file. In this case, it is set to 8192 bytes (8 KB).
        """
        # Make sure the save folder exists
        os.makedirs(save_folder, exist_ok=True)

        # If no filename is provided, extract the filename from the URL
        if filename is None:
            filename = url.split("/")[-1]
        
        # Full path to save the file
        save_path = os.path.join(save_folder, filename)

        # Download the file with streaming to handle large files
        with requests.get(url, stream=True) as response:
            response.raise_for_status()  # Raise an error if the download fails
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        
        print(f"Downloaded file to: {save_path}")
        return save_path

    def download_catalogue(self, 
                           file: str,
                           save_to_folder: str = '.',
                           domain: str = "https://ens.dk/sites/ens.dk/files/Analyser/"):
        """Downloads technology catalogue from DEA website

        Args:
            file (str): _description_
            save_to_folder (str, optional): _description_. Defaults to '.'.
            domain (_type_, optional): _description_. Defaults to "https://ens.dk/sites/ens.dk/files/Analyser/".
        """
        try:
            # You probably used the short name used in this class
            filename = self.files[file]
        except KeyError:
            # ..in case you wrote the full name of the file
            filename = file
            
        if not(filename in os.listdir(save_to_folder)):
            self.download_file(urljoin(domain, filename), save_to_folder)
        else:
            print('\nThe file:\t\t%s\nalready exists in:\t%s'%(self.files[file], save_to_folder))

    def download_all_catalogues(self,
                                save_to_folder: str = '.'):
        for file in self.files.keys():
            self.download_catalogue(file, save_to_folder)
        

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
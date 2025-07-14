###!/usr/bin/env Balmorel
"""
This script has many options for designing maps of 
Balmorel results

It depends on a geofile, that should contain the exact name
of the region names in Balmorel - otherwise, results from
regions that are NOT in the geofile will not be shown! 
"""
#%% ----------------------------- ###
###       0. Script Settings      ###
### ----------------------------- ###

from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, ArrowStyle, Circle
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import pandas as pd
import numpy as np
import os
import glob
from gams import GamsWorkspace
from typing import Tuple
import geopandas as gpd
import cartopy.crs as ccrs


def plot_map(path_to_result: str, 
             scenario: str, 
             year: int,
             commodity: str | None = None,
             lines: str | None = None, 
             generation: str | None = None,
             background : str | None = None,
             save_fig: bool = False,
             path_to_geofile: str | None = None,
             geo_file_region_column: str = 'id',
             system_directory: str | None = None,
             **kwargs) -> Tuple[Figure, Axes] | None:
    
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
        system_directory (str, optional): GAMS system directory. Default does NOT WORK! Need to make some if statements so it's not specified if not specified
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
                **line_value_max (float, optional): Maximum value of lines, used if cat is linear or log to set the value corresponding to the maximum width.
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
                **pie_radius_min (float, optional): Minimum radius of pie, used if cat is linear or log. Defaults to 0.2. Value in data unit.
                **pie_radius_max (float, optional): Maximum radius of pie, used if cat is linear or log. Defaults to 1.4. Value in data unit.
                **pie_cluster_values (list, optional) = The capacity groupings necessary if cat is 'cluster'. Defaults values depends on commodity. Used for the legend if defined.
                **pie_cluster_radius (list, optional) = The radius for the corresponding capacity group if cat is cluster (has to be same size as pie_cluster_values). Used for the legend if defined. Values in data unit.
                **pie_value_max (float, optional): Maximum value of pie, used if cat is linear or log to set the value corresponding to the maximum radius.
                **pie_legend_cluster_values (list, optional) = The legend capacity grouping if a specific legend is needed. Is handled automatically if not defined. Not used if cat is 'cluster'. 
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
    
    # Set the pybalmorel working directory
    wk_dir = os.path.dirname(__file__)      

    ### 0.0 Find the MainResults file
    iter = '0'
    found_scenario = False
    
    path_to_result = path_to_result.lstrip(' ').rstrip(' ')
    if 'MainResults' in path_to_result:
        if os.path.exists(path_to_result):
            found_scenario = True
            print('Found MainResults in %s'%(path_to_result))
            
    elif path_to_result[-4:] == r'\...':
        path_to_result = path_to_result[:-4]
        for subdir in pd.Series(os.listdir(path_to_result.rstrip(r'\...'))):  
            subpath = os.path.join(path_to_result, subdir, 'model')
            if os.path.isdir(subpath):
                if os.path.exists(subpath + '/MainResults_%s_Iter%s.gdx'%(scenario, iter)): 
                    path_to_result = subpath
                    print('Found %s_Iter%s in %s'%(scenario, iter, path_to_result))
                    scenario = scenario + '_Iter%s'%iter
                    found_scenario = True
                    break
                    
                elif os.path.exists(subpath + '/MainResults_%s.gdx'%scenario):
                    path_to_result = subpath
                    print('Found %s in %s'%(scenario, path_to_result))
                    found_scenario = True
                    break
    else:
        if os.path.exists(path_to_result + '/MainResults_%s_Iter%s.gdx'%(scenario, iter)): 
            print('Found %s_Iter%s in %s'%(scenario, iter, path_to_result))
            scenario = scenario + '_Iter%s'%iter
            found_scenario = True
            
        elif os.path.exists(path_to_result + '/MainResults_%s.gdx'%scenario):
            print('Found %s in %s'%(scenario, path_to_result))
            found_scenario = True
    
    if found_scenario:

        ### ----------------------------- ###
        ###        1. Preparations        ###
        ### ----------------------------- ###


        ### 1.1 Set Options
        
        ### Structural options
        if commodity != None:
            commodity = commodity.lower().capitalize()
        if commodity not in [None, 'Electricity', 'Hydrogen']: # Check that it's a possible type of commodity
            raise ValueError('commodity must be either "Electricity" or "Hydrogen"')
        if lines not in [None, 'Capacity', 'FlowYear', 'FlowTime', 'UtilizationYear', 'UtilizationTime']: # Check that it's a possible type of lines display
            raise ValueError('lines must be either "Capacity", "FlowYear", "FlowTime", "UtilizationYear or "UtilizationTime"')
        if lines != None and commodity == None :
            raise ValueError('You must specify a commodity if you want to plot the lines')
        generation_commodity = kwargs.get('generation_commodity', commodity) # Commodity to be shown in the generation map, if not specified, same as line commodity
        if generation_commodity not in ['Electricity', 'Hydrogen']:
            print(f'generation_commodity must be either "Electricity" or "Hydrogen", set to {commodity}')
            generation_commodity = commodity
        if generation not in [None, 'Capacity', 'Production', 'ProductionTime']: # Check that it's a possible type of generation display
            raise ValueError('generation must be either "Capacity", "Production", or ProductionTime')
        if generation != None and commodity == None :
            raise ValueError('You must specify a commodity if you want to plot the generation')
        if lines in ['FlowTime', 'UtilizationTime']: # Check if there is a specified season and hour for flow maps
            S = kwargs.get('S', '')
            T = kwargs.get('T', '')
        exo_end = kwargs.get('exo_end', 'Both') # Options for showing only exogenous or endogenous capacities
        if exo_end not in ['Both', 'Endogenous', 'Exogenous']:
            print('exo_end must be either "Both", "Endogenous" or "Exogenous", set to "Both"')
            exo_end = 'Both'
        generation_exclude_Import_Cap_H2 = kwargs.get('generation_exclude_Import_Cap_H2',True) #take out the capacities because of the IMPORT_H2 from oher countries
        generation_exclude_H2Storage = kwargs.get('generation_exclude_H2Storage', True)  #do not plot the capacities of the H2 storage
        generation_exclude_ElectricStorage = kwargs.get('generation_exclude_ElectricStorage', True)  #do not plot the production of Electric storag, only works with Show pie production
        generation_exclude_Geothermal = kwargs.get('generation_exclude_Geothermal', True) #do not plot the production of Geothermal, only works with Show pie production -> Do we have ?
        background_dict = {'H2 Storage': {'type': 'simpletransfo','var': 'G_STO_YCRAF', 'filters': [('COMMODITY','HYDROGEN')], 'transformation': [1/1000], 'colormap': 'Blues', 'unit': 'TWh', 'basescale': '0max'},
                           'Elec Storage': {'type': 'simpletransfo', 'var': 'G_STO_YCRAF', 'filters': [('COMMODITY','ELECTRICITY')], 'transformation': [1/1000], 'colormap': 'Oranges', 'unit': 'TWh', 'basescale': '0max'},
                           'Elec Price': {'type': 'simpletransfo', 'var': ['EL_PRICE_YCR', 'EL_PRICE_YCRST'], 'colormap': 'RdYlGn_r', 'unit': 'Money/MWh', 'basescale': 'minmax'},
                           'H2 Net Export' : {'type': 'netexport', 'var': 'XH2_FLOW_YCR', 'colormap' : 'RdYlGn', 'unit': 'TWh', 'basescale': '0max'},
                           'Elec Net Export' : {'type': 'netexport', 'var': 'X_FLOW_YCR',  'colormap' : 'RdYlGn', 'unit': 'TWh', 'basescale': '0max'}} # Dictionary of background options
        if background not in background_dict.keys() and background != None : # Check that it's a possible type of background
            print('background set to None')
            background = None
        selected_background = background_dict[background].copy() if background != None else None
        # If the user wants personalized background with csv input
        countries_background_path = kwargs.get('countries_background_path', '')
        if countries_background_path != '' :
            background_dict['Custom'] = {'type': 'simpletransfo', 'colormap': 'Spectral_r', 'unit': 'Custom', 'basescale': 'minmax'}
            background = 'Custom'
            selected_background = background_dict[background].copy()
            df_background = pd.read_csv(os.path.abspath(os.path.join(wk_dir, countries_background_path)))
        
        # Special case of geofile input
        if path_to_geofile != None:
            abspath_to_geofile = os.path.abspath(os.path.join(wk_dir, path_to_geofile))
            geo_file = gpd.read_file(abspath_to_geofile)
            minx, miny, maxx, maxy = geo_file.total_bounds
            coordinates_geofile_offset = kwargs.get('coordinates_geofile_offset', 0.5) # Geofile coordinates offset from the min and max of the geofile
            coordinates_geofile = [(minx-coordinates_geofile_offset, maxx+coordinates_geofile_offset), (miny-coordinates_geofile_offset, maxy+coordinates_geofile_offset)]
            # Warning message about the coordinates and the size of the object on the map
            print("WARNING : You have selected a geofile as an input for the map. The coordinates of the map will be set to the coordinates of the geofile with an offset.\n\
            If you want to modify the size of the offset, please use the option 'coordinates_geofile_offset', the default value is 0.5. \n\
            The size of the object on the map may be affected because default value have been selected. The most critical being the pie charts size parameters. \n\
            Please modify them to your convenience with 'pie_radius_min', 'pie_radius_max', 'pie_cluster_groups', and 'pie_cluster_radius' \n\
            If you wish to modify the line size parameters please use : 'line_width_min', 'line_width_max', 'line_cluster_groups', and 'line_cluster_widths'.")
        
        ### Visual options
        title_show = kwargs.get('title_show', True) # Showing or not the title
        legend_show = kwargs.get('legend_show', True) # Showing or not the legend
        show_country_out = kwargs.get('show_country_out', True) # Showing or not the countries outside the model
        dict_map_coordinates = {'EU': [(-11,36),(33,72)], 'DK': [(7.5,13.5),(54.5,58)]} # Dictionary of coordinates for different maps
        choosen_map_coordinates = kwargs.get('choosen_map_coordinates', 'EU') # Choose the map to be shown
        map_coordinates = kwargs.get('map_coordinates', '') # Coordinates of the map
        if path_to_geofile != None and map_coordinates == '':
            dict_map_coordinates['Geofile'] = coordinates_geofile
            choosen_map_coordinates = 'Geofile'
        elif map_coordinates != '' : 
            dict_map_coordinates['Custom'] = map_coordinates
            choosen_map_coordinates = 'Custom'
            print("WARNING : You have selected custom coordinates for the map. The coordinates of the map will be set to the choosen custom coordinates.\n\
            The size of the object on the map may be affected because default value have been selected. The most critical being the pie charts size parameters. \n\
            Please modify them to your convenience with 'pie_radius_min', 'pie_radius_max', 'pie_cluster_groups', and 'pie_cluster_radius' \n\
            If you wish to modify the line size parameters please use : 'line_width_min', 'line_width_max', 'line_cluster_groups', and 'line_cluster_widths'.")
        # lines options
        line_width_cat = kwargs.get('line_width_cat', 'log') # Choose the way of determining lines width, log, linear or cluster
        if line_width_cat not in ['linear', 'log', 'cluster']: # Check that it's a possible category of line thickness
            print('line_thick_cat must be either "linear", "log" or "cluster", set to "log"')
            line_width_cat = 'log'
        line_show_min = kwargs.get('line_show_min', 0) # Minimum transmission capacity (GW) or flow (TWh) shown on map
        line_width_min = kwargs.get('line_width_min', 0.5) # Minimum width of lines, used if cat is linear or log
        line_width_max = kwargs.get('line_width_max', 12) # Maximum width of lines, used if cat is linear or log
        line_cluster_values = kwargs.get('line_cluster_values', []) # Values of the clusters for the clustering category
        line_cluster_widths = kwargs.get('line_cluster_widths', []) # Widths of the clusters for the clustering category
        if len(line_cluster_values) != len(line_cluster_widths): # Raise error if the cluster values and widths are not of same length
            raise ValueError('line_cluster_values and line_cluster_widths must be of same length')
        if line_width_cat == 'cluster' and line_cluster_values == []: # If the user did not input the cluster values, notify it
            raise ValueError('You have selected the cluster category for the line width, but you have not specified the cluster values.')
        line_legend_values = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200]
        line_value_max = kwargs.get('line_value_max', None) # Maximum value of lines, used if cat is linear or log to set the value corresponding to the maximum width
        line_legend_cluster_values = kwargs.get('line_legend_cluster_values', []) # Values of the clusters in the legend
        line_opacity = kwargs.get('line_opacity', 1) # Opacity of lines
        line_label_show = kwargs.get('line_label_show', False)  # Showing or not the value of the lines
        line_label_min = kwargs.get('line_label_min', 0) #Minimum transmission capacity (GW) or flow (TWh) shown on map in text
        line_label_decimals = kwargs.get('line_label_decimals', 1) #Number of decimals shown for line labels
        line_label_fontsize = kwargs.get('line_font_size', 10) #Font size of transmission line labels
        line_flow_show = kwargs.get('line_flow_show', True) # Showing or not the arrows on the lines
        # generation options
        generation_show_min = kwargs.get('generation_show_min', 0.001) # Minimum generation capacity (GW) or production (TWh) shown on map
        generation_display_type = kwargs.get('generation_display_type', 'Pie') 
        if generation_display_type not in ['Pie']:
            print('generation_display_type must be either "Pie", set to "Pie"')
            generation_display_type = 'Pie'
        generation_var = kwargs.get('generation_var', 'TECH_TYPE') # Variable to be shown in the pie chart
        if generation_var not in ['TECH_TYPE', 'FFF']:
            print('generation_var must be either "TECH_TYPE" or "FFF", set to "TECH_TYPE"')
            generation_var = 'TECH_TYPE'
        if generation_display_type == 'Pie' and generation != None:
            pie_radius_cat = kwargs.get('pie_radius_cat', 'log') # 'linear' = Capacities are scaled linearly, 'cluster' = capacities are clustered in groups
            if pie_radius_cat not in ['linear', 'log', 'cluster']: # Check that it's a possible category of line thickness
                print('pie_radius_cat must be either "linear", "log" or "cluster", set to "log"')
                pie_radius_cat = 'log'
            pie_show_min = kwargs.get('pie_show_min', 0) # Minimum transmission capacity (GW) or flow (TWh) shown on map
            pie_radius_dict = {'EU': {'pie_radius_min' : 0.2, 'pie_radius_max' : 1.4, 'pie_cluster_radius' : [0.2, 0.6, 1, 1.3]}, 
                               'DK': {'pie_radius_min' : 0.05, 'pie_radius_max' : 0.5, 'pie_cluster_radius' : [0.05, 0.1, 0.25, 0.5]}}
            if choosen_map_coordinates not in ["EU", "DK"]:
                pie_radius_dict[choosen_map_coordinates] = {'pie_radius_min' : 0.1, 'pie_radius_max' : 0.5, 'pie_cluster_radius' : [0.1, 0.2, 0.3, 0.5]}
            pie_radius_min = kwargs.get('pie_radius_min', pie_radius_dict[choosen_map_coordinates]['pie_radius_min']) # Minimum width of lines, used if cat is linear or log
            pie_radius_max = kwargs.get('pie_radius_max', pie_radius_dict[choosen_map_coordinates]['pie_radius_max']) # Maximum width of lines, used if cat is linear or log
            pie_cluster_values = kwargs.get('pie_cluster_values', []) # Values of the clusters for the clustering category
            pie_cluster_radius = kwargs.get('pie_cluster_radius', []) # Radius of the clusters for the clustering category
            if len(pie_cluster_values) != len(pie_cluster_radius):
                raise ValueError('pie_cluster_values and pie_cluster_radius must be of same length')
            if pie_radius_cat == 'cluster' and pie_cluster_values == []: # If the user did not input the cluster values, notify it
                raise ValueError('You have selected the cluster category for the pie radius, but you have not specified the cluster values.')
            pie_legend_values = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400, 450, 500, 600, 750, 1000]
            pie_value_max = kwargs.get('pie_value_max', None) # Maximum value of pie, used if cat is linear or log to set the value corresponding to the maximum radius
            pie_legend_cluster_values = kwargs.get('pie_legend_cluster_values', []) # Values of the clusters in the legend
        # background options
        if background != None:
            background_name = kwargs.get('background_name', '') # Name of the background (mostly useful for Custom)
            background = background_name if background_name != '' else background
            background_unit = kwargs.get('background_unit', '') # Unit of the background (mostly useful for Custom)
            selected_background['unit'] = background_unit if background_unit != '' else selected_background['unit']
        else : 
            background_name = None
        background_scale = kwargs.get('background_scale', [0, 0]) # Scale used for the background coloring
        background_scale_tick = kwargs.get('background_scale_tick', 2) # A tick every x units in the background legend
        background_label_show = kwargs.get('background_label_show', False) # Showing or not the background label on the countries
        background_label_fontsize = kwargs.get('background_label_fontsize', 10) # Font size of the background labels

        # Colors options
        # Map colors options 
        background_color = kwargs.get('background_color', 'white') #Background color of the map
        regions_ext_color = kwargs.get('regions_ext_color', '#d3d3d3') #Color of regions outside the model
        regions_model_color = kwargs.get('regions_model_color', 'linen') #Color of regions inside the model
        # If the person wants personnalized colors on countries
        countries_colors_path = kwargs.get('countries_colors_path', '') 
        if countries_colors_path != '' :
            df_countries_colors = pd.read_csv(os.path.abspath(os.path.join(wk_dir, countries_colors_path)))
        # Line colors options
        if commodity == 'Electricity':
            line_color = kwargs.get('line_color', 'green') # Color of electrical network
        elif commodity == 'Hydrogen':
            line_color = kwargs.get('line_color', '#13EAC9') # Color of hydrogen network
        line_label_color = kwargs.get('line_label_color', 'black') #Color of line labels
        # generation colors options
        generation_tech_color = {
        'HYDRO-RESERVOIRS': '#33b1ff',
        'HYDRO-RUN-OF-RIVER': '#4589ff',
        'HYDRO' : '#33b1ff',
        'WIND-ONSHORE': '#006460',
        'BOILERS': '#8B008B',
        'ELECT-TO-HEAT': '#FFA500',
        'INTERSEASONAL-HEAT-STORAGE': '#FFD700',
        'CHP-BACK-PRESSURE': '#E5D8D8',
        'SMR-CCS': '#00BFFF',
        'SMR': '#d1b9b9',
        'INTRASEASONAL-HEAT-STORAGE': '#00FFFF',
        'CONDENSING': '#8a3ffc',
        'SOLAR-HEATING': '#FF69B4',
        'CHP-EXTRACTION': '#ff7eb6',
        'SOLAR-PV': '#d2a106',
        'WIND-OFFSHORE': '#08bdba',
        'INTRASEASONAL-ELECT-STORAGE': '#ba4e00',
        'ELECTROLYZER': '#ADD8E6', #7FBF7F
        'H2-STORAGE': '#FFC0CB',
        'FUELCELL': '#d4bbff',
        'CHP' : '#E5D8D8'
        }
        generation_fuel_color = {
        'HYDRO': '#08bdba',
        'WIND-ONSHORE': '#5e45ff',
        'WIND-OFFSHORE': '#4589ff',
        'BIOGAS': '#23932d',
        'COAL': '#595959',
        'ELECTRIC': '#BA000F',
        'OIL': '#7b4c42',
        'MUNIWASTE': '#757501',
        'BIOMASS': '#006460',
        'HEAT': '#a5e982',
        'NATGAS': '#850017',
        'NATGAS-CCS':'#d35050',
        'OTHER': '#f7f7f7',
        'SOLAR': '#fad254',
        'NUCLEAR': '#cd6f00',
        'LIGNITE': '#2b1d1d',
        'HYDROGEN': '#dbdcec',
        }
        # Background color options
        if background != None:
            background_colormap = kwargs.get('background_colormap', '') # Background colormap on the countries
            selected_background['colormap'] = background_colormap if background_colormap != '' else selected_background['colormap']
        background_label_color = kwargs.get('background_label_color', 'black') # Color of the background labels
            
        # Options to modify later
        market = 'Investment' #Choose from ['Balancing', 'DayAhead', 'FullYear', 'Investment'] -> Figure out why different market ?
        YEAR = '' #Add year to read file name (e.g. '2025', '2035', 'full') -> 
        SUBSET = '' #Add subset to read file name (e.g. 'full')


        ### 1.2 Read gdx functions
        
        # Read gdx files
        def read_paramenter_from_gdx(ws,gdx_name,parameter_name,**read_options):
            for item in read_options.items():
                if item[0]=="field":
                            field=item[1]
                            
            db = ws.add_database_from_gdx(gdx_name)
            
            if "field" in locals() : # Check what is this ??
                if field=="Level":
                    par=dict( (tuple(rec.keys), rec.level) for rec in db[parameter_name] )
                elif field=="Marginal":
                    par=dict( (tuple(rec.keys), rec.marginal) for rec in db[parameter_name] )
                elif field=="Lower":
                    par=dict( (tuple(rec.keys), rec.lower) for rec in db[parameter_name] )
                elif field=="Upper":
                        par=dict( (tuple(rec.keys), rec.lower) for rec in db[parameter_name] )
                elif field=="Scale":
                            par=dict( (tuple(rec.keys), rec.lower) for rec in db[parameter_name] )
                elif field=="Value":
                            par=dict( (tuple(rec.keys), rec.value) for rec in db[parameter_name] )
            else:
                if "Parameter" in str(type(db[parameter_name])):
                    par=dict( (tuple(rec.keys), rec.value) for rec in db[parameter_name] )
                elif "Variable" in str(type(db[parameter_name])):
                    par=dict( (tuple(rec.keys), rec.level) for rec in db[parameter_name] )
                elif "Set" in str(type(db[parameter_name])):
                    par=dict( (tuple(rec.keys), rec.text) for rec in db[parameter_name] )
                elif "Equation" in str(type(db[parameter_name])):
                    par=dict( (tuple(rec.keys), rec.level) for rec in db[parameter_name] )
                    
            return par, db[parameter_name].get_domains_as_strings()
        

        # Extract data from gdx files
        def dataframe_from_gdx(gdx_name,parameter_name,system_directory,**read_options):
            
            if system_directory != None:
                ws = GamsWorkspace(os.getcwd(), system_directory=system_directory)
            else:
                ws = GamsWorkspace(os.getcwd())

            var, cols= read_paramenter_from_gdx(ws,gdx_name,parameter_name,**read_options)
            if "custom_domains" in read_options :
                cols= read_options["custom_domains"]
            
            unzip_var= list(zip(*var))
            
            new_dict=dict()
            i=0
            for col in cols:
                new_dict[col]= list(unzip_var[i])
                i=i+1
            
            if "field" in read_options :
                field= read_options.get("field")
                new_dict[field]=[]
                new_dict[field]=list(var.values())
            else:
                new_dict["Value"]=list(var.values())
                
            df=pd.DataFrame.from_dict(new_dict)

            return df


        ### 1.3 Read geographic files
        
        # If the user did not input a personalized geofile, use the default one
        if path_to_geofile == None:
            # Path to csv coordinates files
            coordinates_RRR_path = kwargs.get('coordinates_RRR_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/coordinates_RRR.csv'))) # Coordinates of regions centers
            
            # Load coordinates csv files
            df_unique = pd.read_csv(coordinates_RRR_path)
            df_region = df_unique.loc[df_unique['Type'] == 'region', ]

            # List of regions names in and out of the model
            r_in = list(df_unique.loc[(df_unique['Display'] == 1) & (df_unique['Type'] == 'region'), 'RRR'])
            r_out = list(df_unique.loc[(df_unique['Display'] == 0) & (df_unique['Type'] == 'region'), 'RRR'])

            # Define dictionnaries for paths to regions geojson files
            layers_in = {region: '' for region in r_in}
            layers_out = {region: '' for region in r_out}

            # Fill dictionnaries with layer paths for each region; if both a shapefile and geojson file are available for one region, the geojson file is used. 
            for region in r_in:
                layers_in[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/geojson_files/'+ region + '.geojson')))
            for region in r_out:
                layers_out[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/geojson_files/'+ region + '.geojson')))
                    
            #Remove brackets from file paths
            for region in layers_in:
                layers_in[region] = str(layers_in[region])[2:-2] 
            for region in layers_out:
                layers_out[region] = str(layers_out[region])[2:-2]
        else :
            abspath_to_geofile = os.path.abspath(os.path.join(wk_dir, path_to_geofile))
            geo_file = gpd.read_file(abspath_to_geofile)
            r_in = list(geo_file[geo_file_region_column].unique())
            r_out = []
            
        # Load bypass, hydrogen import coordinates and countries colors files
        bypass_path = kwargs.get('bypass_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/bypass_lines.csv'))) # Coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions
        hydrogen_third_nations_path = kwargs.get('hydrogen_third_nations_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/hydrogen_third_nations.csv'))) # Coordinates of h2 import lines from third nations
        df_bypass = pd.read_csv(bypass_path) 
        if commodity == 'Hydrogen':
            df_hydrogen_lines_outside = pd.read_csv(hydrogen_third_nations_path) 

        ### 1.4 Read run-specific files
        ## 1.4.1 Function: reading gdx-files -> Don't understand the interest of creating those columns

        def df_creation(gdx_file, varname, system_directory):
            df = pd.DataFrame()
            if '_' in gdx_file: # if yes: extract scenario name from gdx filename
                scen = scenario
                # year = year
                subset = SUBSET
                market = 'Invest'
            else:
                # if no: use nan instead
                scen = ''
                subset = SUBSET
                market = ''

            # create empty temporary dataframe and load the gdx data into it
            temp = pd.DataFrame()
            # temp = gdxpds.to_dataframe(gdx_file, varname, gams_dir=gams_dir,
            #                        old_interface=False)
            
            temp=dataframe_from_gdx(gdx_file,varname, system_directory)

            # add a scenario column with the scenario name of the current iteration
            temp['Scenario'] = scen
            temp['Market']  = market
            temp['run'] = scen + '_' + str(year) + '_' + subset

            # rearrange the columns' order
            cols = list(temp.columns)
            cols = [cols[-1]] + cols[:-1]
            temp = temp[cols]

            # concatenate the temporary dataframe to the preceeding data
            df = pd.concat([df, temp], sort=False)
            return df


        ## 1.4.2 - Define var_list
        
        var_list = []
        if commodity == 'Electricity':
            if lines == 'Capacity' : 
                var_list = var_list + ['X_CAP_YCR']
            elif lines == 'FlowYear' :
                var_list = var_list + ['X_FLOW_YCR']
            elif lines == 'FlowTime' :
                var_list = var_list + ['X_FLOW_YCRST']
            elif lines == 'UtilizationYear':
                var_list = var_list + ['X_CAP_YCR', 'X_FLOW_YCR']
            elif lines == 'UtilizationTime':
                var_list = var_list + ['X_CAP_YCR', 'X_FLOW_YCRST']
        if commodity == 'Hydrogen':
            if lines == 'Capacity' : 
                var_list = var_list + ['XH2_CAP_YCR']
            elif lines == 'FlowYear' :
                var_list = var_list + ['XH2_FLOW_YCR']
            elif lines == 'UtilizationYear' :
                var_list = var_list + ['XH2_CAP_YCR', 'XH2_FLOW_YCR']
            if lines == 'FlowTime' : 
                var_list = var_list + ['XH2_FLOW_YCRST']
            if lines == 'UtilizationTime': 
                var_list = var_list + ['XH2_CAP_YCR', 'XH2_FLOW_YCRST']
        var_list = var_list + ['G_CAP_YCRAF', 'PRO_YCRAGF']
        if generation != None:
            if generation.lower() == 'productiontime':
                var_list += ['PRO_YCRAGFST']
        if background not in [None, 'Custom', background_name]:
            if type(selected_background['var']) == list :
                if lines in ['FlowTime', 'UtilizationTime'] or generation == 'ProductionTime' :
                    background_var = selected_background['var'][1]
                    var_list = var_list + [background_var]
                else :
                    background_var = selected_background['var'][0]
                    var_list = var_list + [background_var]
            else :
                background_var = selected_background['var']
                var_list = var_list + [background_var]


        ## 1.4.3 - Use function to read inputs
        
        # Retrieve path to gdx file
        if ('MainResults' in path_to_result) or ('.gdx' in path_to_result): # Not sure of the interest of all of this
            gdx_file =  glob.glob(path_to_result)
        elif (YEAR == '') & (SUBSET == ''):
            gdx_file =  glob.glob(path_to_result + '\\MainResults_' + scenario + '.gdx')
        else:
            gdx_file =  glob.glob('./input/results/'+ market + '\\MainResults_' + scenario + '_'  + YEAR + '_' + SUBSET + '.gdx')
        gdx_file = gdx_file[0]
        
        # Dictionnary to store all dataframes for each variable in var_list
        all_df = {varname: df for varname, df in zip(var_list,var_list)}
        
        # Extract the dataframe from the result and keep them in the dictionnary
        for varname, df in zip(var_list, var_list):
            all_df[varname] = df_creation(gdx_file, varname, system_directory)
        
        # Transmission lines data
        if commodity == 'Electricity':
            if lines == 'Capacity' :
                df_line = all_df['X_CAP_YCR']
            elif lines == 'FlowYear' :
                df_line = all_df['X_FLOW_YCR']
            elif lines == 'FlowTime' :
                df_line = all_df['X_FLOW_YCRST']
            elif lines == 'UtilizationYear' :
                df_cap = all_df['X_CAP_YCR']
                df_line = all_df['X_FLOW_YCR']
            elif lines == 'UtilizationTime':
                df_cap = all_df['X_CAP_YCR']
                df_line = all_df['X_FLOW_YCRST']
        elif commodity == 'Hydrogen':
            if lines == 'Capacity' :
                df_line = all_df['XH2_CAP_YCR']
            elif lines == 'FlowYear' :
                df_line = all_df['XH2_FLOW_YCR']
            elif lines == 'FlowTime' :
                df_line = all_df['XH2_FLOW_YCRST']
            elif lines == 'UtilizationYear' :
                df_cap = all_df['XH2_CAP_YCR']
                df_line = all_df['XH2_FLOW_YCR']
            elif lines == 'UtilizationTime':
                df_cap = all_df['XH2_CAP_YCR']
                df_line = all_df['XH2_FLOW_YCRST']
                
        # Generation data
        if generation == 'Capacity':
            df_generation = all_df['G_CAP_YCRAF']
        elif generation == 'Production':
            df_generation = all_df['PRO_YCRAGF']
        elif generation == 'ProductionTime':
            df_generation = all_df['PRO_YCRAGFST']
        if generation != None:
            if generation_commodity == 'Electricity':
                df_generation = df_generation[df_generation['COMMODITY'] == 'ELECTRICITY']
            elif generation_commodity == 'Hydrogen':
                df_generation = df_generation[df_generation['COMMODITY'] == 'HYDROGEN']
            
        # Background data
        if background not in [None, 'Custom', background_name]:
            df_background = all_df[background_var]
                
        ## 1.4.4 - Select relevant dataframe and rename columns
        column_dict = {'Val':'Value', 'Y':'Year', 'C':'Country'}
        if lines != None:
            df_line = df_line.rename(columns = column_dict)
        if lines in ['UtilizationYear', 'UtilizationTime'] :
            df_cap = df_cap.rename(columns = column_dict)
        if generation != None:
            df_generation = df_generation.rename(columns = column_dict)
        if selected_background != None:
            df_background = df_background.rename(columns = column_dict)
            
        # 1.4.5 Check if there is some H2 import
        if all_df['G_CAP_YCRAF']['FFF'].str.contains('IMPORT_H2').any():
            H2_import = True
        else :
            H2_import = False
            

        ### ----------------------------- ###
        ###        2. Processing          ###
        ### ----------------------------- ###

        ## 2.1 Replace "EPS" with 0

        if lines != None:
            df_line.Value=df_line.Value.replace('Eps', 0)
            df_line.Value=pd.to_numeric(df_line.Value)
        if generation != None:
            df_generation.Value=df_generation.Value.replace('Eps', 0)
            df_generation.Value=pd.to_numeric(df_generation.Value)
        if background not in [None, 'Custom', background_name]:
            df_background.Value=df_background.Value.replace('Eps', 0)
            df_background.Value=pd.to_numeric(df_background.Value)


        ### 2.2 Filter dataframes for relevant data
        
        # Filter the year
        if lines != None :
            df_line['Year'] = df_line['Year'].astype(int)
            df_line = df_line.loc[df_line['Year'] == year].reset_index(drop = True)
        if lines in ['UtilizationYear', 'UtilizationTime']:
            df_cap['Year'] = df_cap['Year'].astype(int)
            df_cap = df_cap.loc[df_cap['Year'] == year].reset_index(drop = True)
        if generation != None:
            df_generation['Year'] = df_generation['Year'].astype(int)
            df_generation = df_generation.loc[df_generation['Year'] == year].reset_index(drop = True)
        if background not in [None, 'Custom', background_name]:
            df_background['Year'] = df_background['Year'].astype(int)
            df_background = df_background.loc[df_background['Year'] == year].reset_index(drop = True)
        
        # Exogenous and endogenous capacities
        if lines == 'Capacity' :
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_line.columns),np.where((df_line.columns == 'VARIABLE_CATEGORY') | (df_line.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
                df_line = pd.DataFrame(df_line.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
            elif exo_end == 'Endogenous' :
                df_line = df_line.loc[df_line['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_line = df_line.loc[df_line['VARIABLE_CATEGORY'] == 'EXOGENOUS']
        elif lines in ['UtilizationYear','UtilizationTime'] :
            col_keep = list(np.delete(np.array(df_cap.columns),np.where((df_cap.columns == 'VARIABLE_CATEGORY') | (df_cap.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
            df_cap = pd.DataFrame(df_cap.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
        if generation == 'Capacity':
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_generation.columns),np.where((df_generation.columns == 'VARIABLE_CATEGORY') | (df_generation.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
                df_generation = pd.DataFrame(df_generation.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
            elif exo_end == 'Endogenous' :
                df_generation = df_generation.loc[df_generation['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_generation = df_generation.loc[df_generation['VARIABLE_CATEGORY'] == 'EXOGENOUS']
        if background not in [None, 'Custom', background_name]:
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_background.columns),np.where((df_background.columns == 'VARIABLE_CATEGORY') | (df_background.columns == 'Value')) ))
                df_background = pd.DataFrame(df_background.groupby(col_keep)['Value'].sum().reset_index() )
            elif exo_end == 'Endogenous' :
                df_background = df_background.loc[df_background['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_background = df_background.loc[df_background['VARIABLE_CATEGORY'] == 'EXOGENOUS']
                
        # Time and season filtering if needed
        if lines == 'FlowTime' or lines == 'UtilizationTime':
            # If season and time step are not specified, take the first one
            if S == '' :
                S = df_line['SSS'].iloc[0]
            if T == '' :
                T = df_line['TTT'].iloc[0]
            df_line = df_line.loc[df_line['SSS'] == S]
            df_line = df_line.loc[df_line['TTT'] == T]
            #Convert flow from MWh to GWh
            df_line['Value'] = df_line['Value'] / 1000
            df_line["UNITS"] = "GWh"
            df_line = df_line.reset_index(drop = True)
            if len(df_line) == 0:
                raise ValueError('No data for the selected season and time step')
        if generation == 'ProductionTime':
            # If season and time step are not specified, take the first one
            if S == '' :
                S = df_generation['SSS'].iloc[0]
            if T == '' :
                T = df_generation['TTT'].iloc[0]
            df_generation = df_generation.loc[df_generation['SSS'] == S]
            df_generation = df_generation.loc[df_generation['TTT'] == T]
            #Convert flow from MWh to GWh
            df_generation['Value'] = df_generation['Value'] / 1000
            df_generation["UNITS"] = "GWh"
            df_generation = df_generation.reset_index(drop = True)
            if len(df_generation) == 0:
                raise ValueError('No data for the selected season and time step')
        if background not in [None, 'Custom', background_name]:
            if type(selected_background['var']) == list :
                if lines in ['FlowTime', 'UtilizationTime'] or generation == 'ProductionTime' :
                    if S == '' :
                        S = df_background['SSS'].iloc[0]
                    if T == '' :
                        T = df_background['TTT'].iloc[0]
                    df_background = df_background.loc[df_background['SSS'] == S]
                    df_background = df_background.loc[df_background['TTT'] == T]
                    if len(df_background) == 0:
                        raise ValueError('No data for the selected season and time step')
            
        
        ### 2.3 Calculate the utilization of the lines
        
        if lines == 'UtilizationTime':
            df_line = pd.merge(df_line, df_cap[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
            df_line.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
            df_line['Congestion'] = df_line['Value'] / df_line['Capacity'] * 100
            df_line['Value'] = df_line['Congestion']
        elif lines == 'UtilizationYear':
            df_line = pd.merge(df_line, df_cap[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
            df_line.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
            df_line['Congestion'] = df_line['Value'] / (df_line['Capacity']*8760/1000) * 100
            df_line['Value'] = df_line['Congestion']

        
        ### 2.4 Add coordinates to line dataframes
        
        if lines != None :
            if path_to_geofile == None : # If the user hasn't define a personalized geofile
                for i,row in df_line.iterrows():
                        for j in range(0,len(df_unique)):
                            if df_line.loc[i,'IRRRE'] == df_unique.loc[j, 'RRR']:
                                df_line.loc[i,'LatExp'] = df_unique.loc[j, 'Lat']
                                df_line.loc[i,'LonExp'] = df_unique.loc[j, 'Lon']
                            if df_line.loc[i,'IRRRI'] == df_unique.loc[j, 'RRR']:
                                df_line.loc[i,'LatImp'] = df_unique.loc[j, 'Lat']
                                df_line.loc[i,'LonImp'] = df_unique.loc[j, 'Lon']
            else :
                for i,row in df_line.iterrows():
                    for j in range(0,len(geo_file)):
                        if df_line.loc[i,'IRRRE'] == geo_file.loc[j, geo_file_region_column]:  
                            df_line.loc[i,'LatExp'] = geo_file.loc[j].geometry.centroid.y       
                            df_line.loc[i,'LonExp'] = geo_file.loc[j].geometry.centroid.x       
                        if df_line.loc[i,'IRRRI'] == geo_file.loc[j, geo_file_region_column]:  
                            df_line.loc[i,'LatImp'] = geo_file.loc[j].geometry.centroid.y       
                            df_line.loc[i,'LonImp'] = geo_file.loc[j].geometry.centroid.x
                # If a line doesn't have coordinates because the countries are not in the personalized geofile, delete it and add a comment
                df_line_copy = df_line.copy()
                for i,row in df_line.iterrows():
                    if pd.isnull(df_line.loc[i,'LatExp']) or pd.isnull(df_line.loc[i,'LatImp']):
                        df_line_copy = df_line_copy.drop(i)
                        print('Line between ' + df_line.loc[i,'IRRRE'] + ' and ' + df_line.loc[i,'IRRRI'] + ' has been deleted because of missing coordinates in the geofile')
                df_line = df_line_copy
        
        ### 2.5 One direction capacity  lines
        
        # When capacity is not the same in both directions, display the max :
        if lines == 'Capacity' :
            df_line_new = pd.DataFrame(columns = df_line.columns) # Create new dataframe to store the balanced values
            indexes = [] # Keep indexes of the lines that are deleted at the end
            for i,row in df_line.iterrows():
                for k,row in df_line.iterrows():
                    if (df_line.loc[k,'IRRRE'] == df_line.loc[i,'IRRRI']) & (df_line.loc[k,'IRRRI'] == df_line.loc[i,'IRRRE']) :
                        if (df_line.loc[k,'Value'] >= df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[k]]], ignore_index=True)
                        elif (df_line.loc[k,'Value'] < df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[i]]], ignore_index=True)
                        indexes.append(i)
                        indexes.append(k)
            # Delete indexes row from original dataframe
            df_line = df_line.drop(indexes)
            # Update the original dataframe
            df_line = pd.concat([df_line, df_line_new], ignore_index=True)
        # When FlowYear or UtilizationYear is selected, do the balance between the two directions
        if lines in ['FlowYear','UtilizationYear'] :
            df_line_new = pd.DataFrame(columns = df_line.columns) # Create new dataframe to store the balanced values
            indexes = [] # Keep indexes of the lines that have been balanced
            for i,row in df_line.iterrows():
                for k,row in df_line.iterrows():
                    if (df_line.loc[k,'IRRRE'] == df_line.loc[i,'IRRRI']) & (df_line.loc[k,'IRRRI'] == df_line.loc[i,'IRRRE']):
                        if (df_line.loc[k,'Value'] >= df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[k]]], ignore_index=True)
                            if lines == 'FlowYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[k,'Value'] - df_line.loc[i,'Value'] # Add the difference to the new dataframe
                            elif lines == 'UtilizationYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[k,'Value'] + df_line.loc[i,'Value'] # Add the line utilization to the new dataframe
                        elif (df_line.loc[k,'Value'] < df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[i]]], ignore_index=True)
                            if lines == 'FlowYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[i,'Value'] - df_line.loc[k,'Value'] # Add the difference to the new dataframe
                            elif lines == 'UtilizationYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[i,'Value'] + df_line.loc[k,'Value']
                        indexes.append(i)
                        indexes.append(k)
            # Delete indexes row from original dataframe
            df_line = df_line.drop(indexes)
            # Update the original dataframe
            df_line = pd.concat([df_line, df_line_new], ignore_index=True)
            
            
        ### 2.6 Add bypass coordinates for indirect lines
        
        if lines in ['Capacity','FlowYear']:
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'UNITS', 'Value']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        elif lines == 'FlowTime':
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Value']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        elif lines == 'UtilizationTime':
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'UNITS', 'Value', 'Capacity']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        elif lines == 'UtilizationTime':
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Value', 'Capacity']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        #Replace existing row by 2 bypass 
        if lines != None:
            keys = list(df_bypass.columns.values)[0:2]
            i1 = df_line.set_index(keys).index
            i2 = df_bypass.set_index(keys).index
            df_line = df_line[~i1.isin(i2)] #Delete existing rows that need bypass
            df_line = df_line._append(df_bypass, ignore_index = True, sort = True) #Append bypass rows


        ### 2.7 Define line centers
        
        #Define centre of each transmission line
        if lines != None:
            df_line['LatMid'] = (df_line['LatImp'] + df_line['LatExp']) /2
            df_line['LonMid'] = (df_line['LonImp'] + df_line['LonExp']) /2                                      
        
        
        ### 2.8 Process the generation data
        
        if generation != None:
            # Make the pie charts based on technologies
            if generation_var == 'TECH_TYPE':
            # Create horizontal table with sectors as columns
                display_column = 'TECH_TYPE'
                #Distinguish if has CCS or not for hydrogen
                G_to_tech_type = {
                'GNR_STEAM-REFORMING_E-70_Y-2020': 'SMR',
                'GNR_STEAM-REFORMING-CCS_E-70_Y-2020': 'SMR-CCS'
                }
                df_generation['TECH_TYPE'] = df_generation['G'].map(G_to_tech_type).fillna(df_generation['TECH_TYPE'])

            # Make pie charts based on Fuels
            if generation_var == 'FFF':
                display_column = 'FFF'
                #If you map fuels to change the fuel type.     
                # Define the dictionary to map old fuel names to new ones
                
                #First split wind to wind on and wind off based on the tech_type
                # create a dictionary to map the values of TECH_TYPE to the corresponding FFF names
                tech_type_to_fff = {"WIND-ON": "WIND-ON", "WIND-OFF": "WIND-OFF"}
                # use the map function to replace the values of FFF based on the values of TECH_TYPE
                df_generation['FFF'] = df_generation['TECH_TYPE'].map(tech_type_to_fff).fillna(df_generation['FFF'])
                # create a dictionary to map the values of FFF to the corresponding fuel types
                fff_to_fuel = {
                'BIOOIL': 'OIL', 
                'LIGHTOIL': 'OIL', 
                'OIL': 'OIL', 
                'FUELOIL': 'OIL',
                'SHALE' : 'OIL',
                'WOODCHIPS': 'BIOMASS', 
                'WOODPELLETS': 'BIOMASS', 
                'WOODWASTE': 'BIOMASS', 
                'WOOD': 'BIOMASS',
                'STRAW': 'BIOMASS',
                'RETORTGAS':'NATGAS',
                'OTHERGAS': 'NATGAS',
                'DUMMY': 'NATGAS',
                'PEAT' : 'NATGAS',
                'WASTEHEAT' :'HEAT',
                'LNG' :'NATGAS',
                'SUN':'SOLAR',
                'WATER':'HYDRO'
                
                }
                # use the map function to replace the values of FFF based on the values of the dictionary
                df_generation['FFF'] = df_generation['FFF'].map(fff_to_fuel).fillna(df_generation['FFF'])
                
                G_to_FFF = {
                'GNR_BO_NGASCCS_E-105_MS-5-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_BO_NGASCCS_E-106_MS-5-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_BO_NGASCCS_E-106_MS-5-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_BO_NGASCCS_E-106_MS-5-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_BP_E-51_SS-10-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_BP_E-53_SS-10-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_BP_E-54_SS-10-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_BP_E-55_SS-10-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-51_SS-10-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-53_SS-10-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-54_SS-10-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-55_SS-10-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-59_LS-100-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-61_LS-100-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-62_LS-100-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_CND_E-63_LS-100-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_EXT_E-59_LS-100-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_EXT_E-61_LS-100-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_EXT_E-62_LS-100-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_CC_NGASCCS_EXT_E-63_LS-100-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_BP_E-47_Y-2020':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_BP_E-48_Y-2030':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_BP_E-49_Y-2040':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_BP_E-50_Y-2050':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_CND_E-47_Y-2020':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_CND_E-48_Y-2030':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_CND_E-49_Y-2040':'NATGAS-CCS',                   
                'GNR_ENG_NGASCCS_CND_E-50_Y-2050':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-37_SS-5-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-39_SS-5-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-40_SS-5-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-40_SS-5-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-42_LS-40-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-43_LS-40-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-44_LS-40-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_BP_E-44_LS-40-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-37_SS-5-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-39_SS-5-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-40_SS-5-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-40_SS-5-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-42_LS-40-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-43_LS-40-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-44_LS-40-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_GT_NGASCCS_CND_E-44_LS-40-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_IND-DF_NGASCCS_E-100_MS-3-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_IND-BO_NGASCCS_E-93_MS-20-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_IND-BO_NGASCCS_E-94_MS-20-MW_Y-2030':'NATGAS-CCS',                   
                'GNR_IND-BO_NGASCCS_E-95_MS-20-MW_Y-2040':'NATGAS-CCS',                   
                'GNR_IND-BO_NGASCCS_E-96_MS-20-MW_Y-2050':'NATGAS-CCS',                   
                'GNR_ST_NGASCCS_CND_E-47_LS-400-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_ST_NGASCCS_EXT_E-47_LS-400-MW_Y-2020':'NATGAS-CCS',                   
                'GNR_ST_NGASCCS_BP_E-7_MS-15-MW_Y-2020':'NATGAS-CCS' 
                }
                df_generation['FFF'] = df_generation['G'].map(G_to_FFF).fillna(df_generation['FFF'])   

            if generation_exclude_H2Storage:
                df_generation = df_generation[df_generation['TECH_TYPE'] != 'H2-STORAGE']
            
            if generation_exclude_Import_Cap_H2:
                df_generation = df_generation[df_generation['FFF'] != 'IMPORT_H2']

            if generation_exclude_ElectricStorage:
                df_generation = df_generation[df_generation['TECH_TYPE'] != 'INTRASEASONAL-ELECT-STORAGE']
                df_generation = df_generation[df_generation['TECH_TYPE'] != 'INTERSEASONAL-ELECT-STORAGE']
            
            # if generation_exclude_Geothermal: # Do we have geothermia inside the model ?
            #     df_generation_capacity = df_generation_capacity[df_generation_capacity['FFF'] != 'HEAT']   
            
            # Rename values of onshore and offshore wind
            df_generation[display_column] = df_generation[display_column].replace({'WIND-ON': 'WIND-ONSHORE', 'WIND-OFF': 'WIND-OFFSHORE'})
            # Rename and merge HYDRO-RESERVOIRS and HYDRO-RUN-OF-RIVER together
            df_generation[display_column] = df_generation[display_column].replace({'HYDRO-RESERVOIRS': 'HYDRO', 'HYDRO-RUN-OF-RIVER': 'HYDRO'})
            # Rename and merge CHP-BACK-PRESSURE and CHP-EXTRACTION together
            df_generation[display_column] = df_generation[display_column].replace({'CHP-BACK-PRESSURE': 'CHP', 'CHP-EXTRACTION': 'CHP'})
            

            # Get the name for the legend
            if generation_var == 'TECH_TYPE':
                df_tech_names = df_generation['TECH_TYPE'].unique()
                df_tech_names_sorted = np.sort(df_tech_names)
                df_tech_names = df_tech_names_sorted
            if generation_var == 'FFF':   
                df_tech_names = df_generation['FFF'].unique()
                df_tech_names_sorted = np.sort(df_tech_names)
                df_tech_names = df_tech_names_sorted
            
            # Sum values per regions and tech/fuel type
            df_generation = pd.DataFrame(df_generation.groupby(['RRR', display_column])['Value'].sum().reset_index())

            # Merge the data frame to get the coordinates
            df_slack_generation = df_generation
            if path_to_geofile == None : # If the user hasn't define a personalized geofile
                df_slack_generation = pd.merge(df_slack_generation, df_region[['Lat', 'Lon', 'RRR']], on = ['RRR'], how = 'right')
            else :
                for i,row in df_slack_generation.iterrows():
                    for j in range(0,len(geo_file)):
                        if df_slack_generation.loc[i,'RRR'] ==  geo_file.loc[j, geo_file_region_column]:  
                            df_slack_generation.loc[i,'Lat'] = geo_file.loc[j].geometry.centroid.y       
                            df_slack_generation.loc[i,'Lon'] = geo_file.loc[j].geometry.centroid.x       
                # If capacities don't have coordinates because the countries are not in the personalized geofile, delete them and add a comment
                df_slack_generation_copy = df_slack_generation.copy()
                for i,row in df_slack_generation.iterrows():
                    if pd.isnull(df_slack_generation.loc[i,'Lat']):
                        df_slack_generation_copy = df_slack_generation_copy.drop(i)
                        print('Capacity in ' + df_slack_generation.loc[i,'RRR'] + ' has been deleted because of missing coordinates in the geofile')
                df_slack_generation = df_slack_generation_copy

            # If they are some nan countries with no tech group filter outcome of merge
            df_slack_generation = df_slack_generation.dropna(subset=[display_column])

            #Keep the names of the regions
            RRRs = df_slack_generation['RRR'].unique()

            # Some times some capacities are close to zero but with a negative make them o
            df_slack_generation.loc[(df_slack_generation['Value'] < 0) & (df_slack_generation['Value'] > -0.0001), 'Value'] = 0
            
            # We want to get rid of very small values so that legend is not too big
            df_slack_generation = df_slack_generation.loc[df_slack_generation['Value'] > generation_show_min]
            
            # Take out the existing Tech/Fuel types for the legend
            if generation_var == 'TECH_TYPE':
                generation_existing_var = df_slack_generation['TECH_TYPE'].unique() 
            elif generation_var == 'FFF':
                generation_existing_var = df_slack_generation['FFF'].unique()
            
            # Only select Denmark data if coordinates of Denmark are selected
            if choosen_map_coordinates == 'DK' :
                df_slack_generation = df_slack_generation.loc[df_slack_generation['RRR'].str.contains('DK')]
        
        ### 2.9 Process the background data
        
        if background not in [None, 'Custom', background_name]:
            # Simple Transfo case
            if selected_background['type'] == 'simpletransfo' :
                try :
                    # Filter the data
                    filters = selected_background['filters']
                    for i in range(len(filters)):
                        df_background = df_background.loc[df_background[filters[i][0]] == filters[i][1]].reset_index(drop = True)
                except :
                    pass
                try :
                    # Apply the transformation
                    transformation = selected_background['transformation']
                    for i in range(len(transformation)):
                        df_background["Value"] = df_background["Value"]*transformation[i]
                except :
                    pass
                # Group by region RRR
                df_background = pd.DataFrame(df_background.groupby(['RRR'])['Value'].sum().reset_index())
            # Net export case
            elif selected_background['type'] == 'netexport' :
                # Create a list with all unique elements in df_background["IRRE"] or df_background["IRRI"]
                unique_RRR = list(set(df_background["IRRRE"]).union(set(df_background["IRRRI"])))
                df_background_netexport = pd.DataFrame(columns=['RRR', 'Value'])
                for rrr in unique_RRR:
                    export_value = df_background[df_background['IRRRE'] == rrr]['Value'].sum()
                    import_value = df_background[df_background['IRRRI'] == rrr]['Value'].sum()
                    net_export = export_value - import_value
                    df_background_netexport = pd.concat([df_background_netexport, pd.DataFrame([{'RRR': rrr, 'Value': net_export}])], ignore_index=True)
                df_background = df_background_netexport.copy()
              
        if background != None :  
            # Merge the data frame to get the coordinates for each region
            if path_to_geofile == None : # If the user hasn't define a personalized geofile
                df_background = pd.merge(df_background, df_region[['Lat', 'Lon', 'RRR']], on = ['RRR'], how = 'inner')
            else :
                for i,row in df_background.iterrows():
                    for j in range(0,len(geo_file)):
                        if df_background.loc[i,'RRR'] ==  geo_file.loc[j, geo_file_region_column]:  
                            df_background.loc[i,'Lat'] = geo_file.loc[j].geometry.centroid.y       
                            df_background.loc[i,'Lon'] = geo_file.loc[j].geometry.centroid.x       
                # If capacities don't have coordinates because the countries are not in the personalized geofile, delete them and add a comment
                df_background_copy = df_background.copy()
                for i,row in df_background.iterrows():
                    if pd.isnull(df_background.loc[i,'Lat']):
                        df_background_copy = df_background_copy.drop(i)
                        print('Background in ' + df_background.loc[i,'RRR'] + ' has been deleted because of missing coordinates in the geofile')
                df_background = df_background_copy
            # Get the regions having data
            background_RRR = df_background['RRR'].unique()
            # Deal with the scale of the background
            if background_scale == [0,0]:
                if selected_background['basescale'] in ['0max', 'minmax']:
                    background_scale[1] = df_background['Value'].max()
                if selected_background['basescale'] == 'minmax' :
                    background_scale[0] = df_background['Value'].min()
                if selected_background['type'] == 'netexport' :
                    if -df_background['Value'].max() < df_background['Value'].min() :
                        background_scale[0] = -df_background['Value'].max()
                    else :
                        background_scale[0] = df_background['Value'].min()
                        background_scale[1] = -df_background['Value'].min()
            
            
        ### 2.10 Verify which country was defined as in but does not have any data
        # Please note that the user is free to define something as out of the model and still has data for it
        
        if lines != None or generation != None:
            check = []
            if lines != None:
                check = check + [df_line['IRRRE'].unique(), df_line['IRRRI'].unique()]
            if generation != None:
                check = check + [df_generation['RRR'].unique()]
            r_in_copy = r_in.copy()
            r_out_copy = r_out.copy()
            if path_to_geofile == None:
                layers_in_copy = layers_in.copy()
                layers_out_copy = layers_out.copy()
                for region in r_in : 
                    if not any(region in sublist for sublist in check):
                        r_in_copy.remove(region)
                        layers_in_copy.pop(region)
                        r_out_copy.append(region)
                        layers_out_copy[region] = layers_in[region]
                layers_in = layers_in_copy
                layers_out = layers_out_copy
            else :
                for region in r_in :
                    if not any(region in sublist for sublist in check):
                        r_out_copy.append(region)
                        r_in_copy.remove(region)
            r_in = r_in_copy
            r_out = r_out_copy


        ### ----------------------------- ###
        ###          3. Plotting          ###
        ### ----------------------------- ###

        ### 3.1 Create the map with the countries and regions
        
        projection = ccrs.EqualEarth()
        
        # Get the coordinates of the graph
        xlim = dict_map_coordinates[choosen_map_coordinates][0]
        ylim = dict_map_coordinates[choosen_map_coordinates][1]

        # Calculate the aspect ratio based on the limits and set the figure size based on the aspect ratio
        aspect_ratio = (xlim[1] - xlim[0]) / (ylim[1] - ylim[0])
        fig_width = 12  # Adjust as needed
        fig_height = fig_width / aspect_ratio

        fig, ax = plt.subplots(figsize=(fig_width+10, fig_height), subplot_kw={"projection": projection}, dpi=100, facecolor=background_color)

        if path_to_geofile == None : # If the user hasn't define a personalized geofile
            for R in layers_in:
                # Get the color of the country based on the background choice if it exists
                if background != None: 
                    value = df_background.loc[df_background['RRR'] == R, 'Value'].values
                    if len(value) != 0 :
                        face_color = plt.cm.get_cmap(selected_background['colormap'])((value[0] - background_scale[0]) / (background_scale[1] - background_scale[0]))
                    else :
                        if countries_background_path == '' :
                            value = np.append(value, 0)
                            face_color = plt.cm.get_cmap(selected_background['colormap'])((value[0] - background_scale[0]) / (background_scale[1] - background_scale[0]))
                        else :
                            face_color = regions_model_color
                else : 
                    face_color = regions_model_color
                # Get the personalized color of the country if defined
                if countries_colors_path != '':
                    country_color = df_countries_colors.loc[df_countries_colors['RRR'] == R, 'color'].values
                    if len(country_color) > 0:
                        face_color = country_color[0]
                # Get the geo file and plot it
                geo = gpd.read_file(layers_in[R])
                geo_artist = ax.add_geometries(geo.geometry, crs = projection,
                                                facecolor=[face_color], edgecolor='#46585d',
                                                linewidth=.2)
                geo_artist.set_zorder(1)
                
            for R in layers_out:
                face_color = regions_ext_color
                # Get the personalized color of the country if defined
                if countries_colors_path != '':
                    country_color = df_countries_colors.loc[df_countries_colors['RRR'] == R, 'color'].values
                    if len(country_color) > 0:
                        face_color = country_color[0]
                if show_country_out or face_color != regions_ext_color:
                    geo = gpd.read_file(layers_out[R])
                    geo_artist = ax.add_geometries(geo.geometry, crs = projection,
                                                facecolor=[face_color], edgecolor='#46585d',
                                                linewidth=.2)
                    geo_artist.set_zorder(1)
        else :
            for R in r_out :
                face_color = regions_ext_color
                # Get the personalized color of the country if defined
                if countries_colors_path != '':
                    country_color = df_countries_colors.loc[df_countries_colors['RRR'] == R, 'color'].values
                    if len(country_color) > 0:
                        face_color = country_color[0]
                if show_country_out or face_color != regions_ext_color:
                    geo_file = geo_file[geo_file.geometry.notnull()]
                    # Print one time all countries as outside countries to make sure to have everything defined plotted
                    geo_artist = ax.add_geometries(geo_file.geometry, crs=projection,
                                                    facecolor=[regions_ext_color], edgecolor='#46585d',
                                                    linewidth=.2)
                    geo_artist.set_zorder(1)
            # Print this time all countries in the model with right color if needed
            for R in r_in:
                if background != None: 
                    value = df_background.loc[df_background['RRR'] == R, 'Value'].values
                    if len(value) != 0 :
                        face_color = plt.cm.get_cmap(selected_background['colormap'])((value[0] - background_scale[0]) / (background_scale[1] - background_scale[0]))
                    else :
                        if countries_background_path == '' :
                            value = np.append(value, 0)
                            face_color = plt.cm.get_cmap(selected_background['colormap'])((value[0] - background_scale[0]) / (background_scale[1] - background_scale[0]))
                        else :
                            face_color = regions_model_color
                else : 
                    face_color = regions_model_color
                # Get the personalized color of the country if defined
                if countries_colors_path != '':
                    country_color = df_countries_colors.loc[df_countries_colors['RRR'] == R, 'color'].values
                    if len(country_color) > 0:
                        face_color = country_color[0]
                try :
                    geo_file = geo_file[geo_file.geometry.notnull()]
                    geometry = [geo_file[geo_file[geo_file_region_column] == R].geometry.iloc[0]]
                    geo_artist = ax.add_geometries(geometry, crs=projection,
                                facecolor=[face_color], edgecolor='#46585d',
                                linewidth=.2)
                    geo_artist.set_zorder(1)
                except :
                    print("It seems like the region " + R + " id is not defined correctly in the geofile")
                    
        # Add labels to countries   
        if background != None:
            if background_label_show :
                for r in background_RRR: # Find idx of the region
                    Lon = df_background.loc[df_background['RRR']==r, 'Lon'].mean()
                    Lat = df_background.loc[df_background['RRR']==r, 'Lat'].mean()
                    if (xlim[0] <= Lon <= xlim[1]) & (ylim[0] <= Lat <= ylim[1]) :
                        label = "{:.{}f}".format(df_background.loc[df_background['RRR']==r,'Value'].mean(), 0)
                        plt.annotate(label, # this is the value which we want to label (text)
                                     (Lon,Lat), # x and y is the points location where we have to label
                                     textcoords="offset points",
                                     xytext=(0,-4), # this for the distance between the points and the text label
                                     ha='center',
                                     fontsize = background_label_fontsize,
                                     color = background_label_color,
                                     zorder=1)


        ### 3.2 Tools for line width and pie radius interpolation
        
        def linear_interpolation(value, max_value, length_max, length_min):
            length_constant = max_value/length_max
            length = value/length_constant
            if length < length_min:
                length = length_min
            return length
        
        def log_interpolation(value, max_value, length_max, length_min):
            normalized_value = (value-0)/(max_value-0)
            log_scaled = np.log1p(normalized_value) / np.log1p(1)
            length = length_min + log_scaled * (length_max - length_min)
            return length
        
        # A function for finding the nearest value in an array, useful for clustering
        def find_nearest(array, value):
            array = np.asarray(array)
            idx = (np.abs(array - value)).argmin()
            return array[idx], idx

        ### 3.3 Adding transmission lines
        
        if lines != None :
            # Check if there is some h2 import in the 
            if H2_import:
                if commodity == 'Hydrogen':
                    lines_H2_Thirdnations =[]
                    for i, row in df_hydrogen_lines_outside.iterrows():
                        y1 = df_hydrogen_lines_outside.loc[i,'LatExp']
                        x1 =  df_hydrogen_lines_outside.loc[i,'LonExp']
                        y2 = df_hydrogen_lines_outside.loc[i,'LatImp']
                        x2 = df_hydrogen_lines_outside.loc[i,'LonImp']
                        
                        l, = ax.plot([x1,x2], [y1,y2], color = 'orange', linestyle=(0, (1, 1)), solid_capstyle='round', solid_joinstyle='round', 
                                    linewidth = 3, zorder=1)
                        #save line information
                        lines_H2_Thirdnations.append(l)
            
            #Plot tran lines either for H2 or Electricity, options such as linear plot or cluster are available look the begining            
            save_lines = []
            if lines in ['UtilizationYear','UtilizationTime']:
                line_max_value = df_line['Capacity'].max() # Find maximum value useful for linear and logarithmic scale
            else :
                line_max_value = df_line['Value'].max() # Find maximum value useful for linear and logarithmic scale
            if line_value_max != None:
                line_max_value = line_value_max
            for i,row in df_line.iterrows(): 
                y1 = df_line.loc[i,'LatExp']
                x1 =  df_line.loc[i,'LonExp']
                y2 = df_line.loc[i,'LatImp']
                x2 = df_line.loc[i,'LonImp']
                if lines in  ['UtilizationYear','UtilizationTime']:
                    cap = df_line.loc[i,'Capacity']
                else :
                    cap = df_line.loc[i,'Value']
                    
                # Condition on coordinates
                if ((xlim[0] <= x1 <= xlim[1]) & (ylim[0] <= y1 <= ylim[1])) or ((xlim[0] <= x2 <= xlim[1]) & (ylim[0] <= y2 <= ylim[1])) :
                    if not(np.isnan(cap)) : # Print an error message, if capacity is a NaN value
                        if cap >= line_show_min : # Only plot if big enough
                            if line_width_cat == 'cluster':
                                nearest, idx = find_nearest(line_cluster_values, cap) 
                                width = line_cluster_widths[idx]
                            elif line_width_cat == 'linear':
                                width = linear_interpolation(cap, line_max_value, line_width_max, line_width_min)
                            elif line_width_cat == 'log':
                                width = log_interpolation(cap, line_max_value, line_width_max, line_width_min)
                                
                            # Colors if Congestion is plotted
                            if lines in ['UtilizationYear','UtilizationTime']:
                                colormap = plt.cm.Reds
                                line_final_color = colormap(df_line.loc[i,'Value']/100)
                            else :
                                line_final_color = line_color

                            # Plot the lines
                            l, = ax.plot([x1,x2], [y1,y2], color = line_final_color, linewidth = width, solid_capstyle='round', solid_joinstyle='round', zorder=1, alpha=line_opacity)
                            save_lines.append(l)
                            
                            # Plot the arrows on the flow
                            if line_flow_show :
                                if lines in ["FlowTime", "FlowYear", "UtilizationYear", "UtilizationTime"]:
                                    if df_line.loc[i,'Value'] >= line_show_min:
                                        #Choose arrow style
                                        style = ArrowStyle('Fancy', head_length=4, head_width=4, tail_width=0.1)
                                        # Draw arrow
                                        arrow = FancyArrowPatch(posA=(x1+0.5*(x2-x1),y1+0.5*(y2-y1)), posB=(x1+0.501*(x2-x1),y1+0.501*(y2-y1)), arrowstyle=style, color='black')
                                        ax.add_patch(arrow)
                    
                    else:
                        pass
                        # print("There's a NaN value in line\nIRRRE %s\nIRRRI %s"%(df_line.loc[i, 'IRRRE'], df_line.loc[i, 'IRRRI']))
                        
                    # Add labels to lines   
                    if line_label_show & (xlim[0] <= df_line.loc[i,'LonMid'] <= xlim[1]) & (ylim[0] <= df_line.loc[i,'LatMid'] <= ylim[1]) :
                        if df_line.loc[i,'Value'] >= line_label_min and df_line.loc[i,'Value'] >= line_show_min:
                                if lines in ['UtilizationYear','UtilizationTime']:
                                    label = "{:.{}f}%".format(df_line.loc[i,'Value'], 0)
                                else :
                                    label = "{:.{}f}".format(df_line.loc[i,'Value'], line_label_decimals)
                                plt.annotate(label, # this is the value which we want to label (text)
                                (df_line.loc[i,'LonMid'],df_line.loc[i,'LatMid']), # x and y is the points location where we have to label
                                textcoords="offset points",
                                xytext=(0,-4), # this for the distance between the points
                                # and the text label
                                ha='center',
                                fontsize = line_label_fontsize,
                                color = line_label_color,
                                )
                        
        
        ### 3.4 Adding Generation
        
        if generation != None:
            pies = []
            
            # Calculate the sum of the values by region and find the maximum value
            df_slack_generation_sum = pd.DataFrame(df_slack_generation.groupby(['RRR'])['Value'].sum().reset_index())
            pie_max_value = df_slack_generation_sum['Value'].max()
            if pie_value_max != None:
                pie_max_value = pie_value_max
            
            for r in RRRs: # Find idx of the region
                idx = df_slack_generation['RRR'] == r
                Lat = df_slack_generation.loc[idx, 'Lat'].mean()
                Lon = df_slack_generation.loc[idx, 'Lon'].mean()
                
                # Condition on coordinates
                if (xlim[0] <= Lon <= xlim[1]) & (ylim[0] <= Lat <= ylim[1]) :
                    CAPSUM = df_slack_generation.loc[idx, 'Value'].sum() # Sum of capacities in the region for clustering
                    if CAPSUM > pie_show_min: # Only plot if big enough
                        if pie_radius_cat == 'cluster':
                            nearest, id = find_nearest(pie_cluster_values, CAPSUM) 
                            radius = pie_cluster_radius[id]
                        elif pie_radius_cat == 'linear':
                            radius = linear_interpolation(CAPSUM, pie_max_value, pie_radius_max, pie_radius_min)
                        elif pie_radius_cat == 'log':
                            radius = log_interpolation(CAPSUM, pie_max_value, pie_radius_max, pie_radius_min)

                        if generation_var == 'TECH_TYPE':
                            colors_df = [generation_tech_color.get(tech, 'gray') for tech in df_slack_generation['TECH_TYPE'][idx]]
                        if generation_var == 'FFF':
                            colors_df = [generation_fuel_color.get(tech, 'gray') for tech in df_slack_generation['FFF'][idx]]
                        p = ax.pie(df_slack_generation['Value'][idx].values,
                                center=(Lon, Lat), radius=radius,
                                # If he does not find a match will return gray in the pie
                                colors = colors_df) 
                        # Save pie information
                        pies.append(p)
                    
        ### 3.5 Adding legend
        
        # Unit of the legend
        if lines in ['Capacity','UtilizationYear','UtilizationTime']:
            line_unit = 'GW'
        elif lines == 'FlowYear':
            line_unit = 'TWh'
        elif lines == 'FlowTime':
            line_unit = 'GWh'
            
        if generation == 'Capacity':
            generation_unit = 'GW'
        elif generation == 'Production' :
            generation_unit = 'TWh' 
        elif generation == 'ProductionTime':
            generation_unit = 'GWh'
        
        if legend_show and choosen_map_coordinates == 'EU' :         
            
            ### 3.5.1 Legend with pies
            
            if generation != None:
                ### Pie legend
                
                scatter_handles = []
                legend_labels = []
                if pie_legend_cluster_values == [] and pie_radius_cat != 'cluster' : # If the user has not input any legend values
                    # If they do not exist, create the legend clusters
                    pie_legend_cluster_values = []
                    pie_legend_clusters_radius = []
                    # Stop the loop if idx is already at 0
                    stop_loop = False
                    for i in range(4):
                        if i == 0 : # On the first round, find the nearest value to the maximum
                            pie_legend_value, pie_legend_idx = find_nearest(pie_legend_values, pie_max_value)
                        else:
                            if pie_legend_idx != 0 :
                                pie_legend_value, pie_legend_idx = find_nearest(pie_legend_values, pie_legend_value/2)
                            else :
                                stop_loop = True
                        if stop_loop == False :
                            # Find the correct width for the line
                            if pie_radius_cat == 'linear':
                                pie_legend_radius = linear_interpolation(pie_legend_value, pie_max_value, pie_radius_max, pie_radius_min)
                            elif pie_radius_cat == 'log':
                                pie_legend_radius = log_interpolation(pie_legend_value, pie_max_value, pie_radius_max, pie_radius_min)
                            # Append the values to the lists
                            pie_legend_cluster_values = [pie_legend_value] + pie_legend_cluster_values
                            pie_legend_clusters_radius = [pie_legend_radius] + pie_legend_clusters_radius
                            # The patch
                            scatter = ax.scatter([], [], s=((pie_legend_radius * ax.get_window_extent().width / (xlim[1] - xlim[0])) * 72 / fig.dpi) ** 2, facecolor='grey', edgecolor='grey')
                            scatter_handles = [scatter] + scatter_handles
                            # The text
                            legend_labels = ['{} {}'.format(pie_legend_value, generation_unit)] + legend_labels
                    # Add the legend
                    if len(pie_legend_clusters_radius) > 1:
                        first_legend = ax.legend(scatter_handles, legend_labels, scatterpoints=1, loc='upper left', ncol=4, fontsize=12, frameon=False, bbox_to_anchor=(0, 0.99))
                        ax.add_artist(first_legend)  
                elif pie_radius_cat == 'cluster' : # If the user has choosen the clustering, we are using that for the legend
                    for i in range(len(pie_cluster_values)) :
                        pie_legend_value = pie_cluster_values[i]
                        pie_legend_radius = pie_cluster_radius[i]
                        scatter = ax.scatter([], [], s=((pie_legend_radius * ax.get_window_extent().width / (xlim[1] - xlim[0])) * 72 / fig.dpi) ** 2, facecolor='grey', edgecolor='grey')
                        scatter_handles.append(scatter)
                        legend_labels.append('{} {}'.format(pie_legend_value, generation_unit))
                    first_legend = ax.legend(scatter_handles, legend_labels, scatterpoints=1, loc='upper left', ncol=4, fontsize=12, frameon=False, bbox_to_anchor=(0, 0.99))
                    ax.add_artist(first_legend)   
                else : # If the user has input some legend values
                    pie_legend_clusters_radius = []
                    for i in range(len(pie_legend_cluster_values)) :
                        pie_legend_value = pie_legend_cluster_values[i]
                        # Find the correct width for the line
                        if pie_radius_cat == 'linear':
                            pie_legend_radius = linear_interpolation(pie_legend_value, pie_max_value, pie_radius_max, pie_radius_min)
                        elif pie_radius_cat == 'log':
                            pie_legend_radius = log_interpolation(pie_legend_value, pie_max_value, pie_radius_max, pie_radius_min)
                        pie_legend_clusters_radius = [pie_legend_radius] + pie_legend_clusters_radius
                        scatter = ax.scatter([], [], s=((pie_legend_radius * ax.get_window_extent().width / (xlim[1] - xlim[0])) * 72 / fig.dpi) ** 2, facecolor='grey', edgecolor='grey')
                        scatter_handles.append(scatter)
                        legend_labels.append('{} {}'.format(pie_legend_value, generation_unit))
                    first_legend = ax.legend(scatter_handles, legend_labels, scatterpoints=1, loc='upper left', ncol=4, fontsize=12, frameon=False, bbox_to_anchor=(0, 0.99))
                    ax.add_artist(first_legend)   

                ### Tech legend
                # Get the bounding box of the first legend
                bbox_first_legend = first_legend.get_window_extent().transformed(ax.transAxes.inverted())
                
                # Tech of fuel legend
                # The characteristics of legend depend on the commodity and the variable
                if generation_var == 'TECH_TYPE':
                    dict_generation_color = generation_tech_color
                    ncol = 2
                elif generation_var == 'FFF':
                    dict_generation_color = generation_fuel_color
                    ncol = 3
                            
                # Calculate the position for the second legend based on the bounding box of the first one
                pos_tech = (bbox_first_legend.x0, bbox_first_legend.y0 - 0.01)  # Adjust the vertical position as needed
            
                # Plot the legend for technologies
                patches = [mpatches.Patch(color=dict_generation_color[tech], label=tech) for tech in generation_existing_var]
                second_legend = ax.legend(handles=patches, loc='upper left', ncol = ncol, frameon=False,
                                        mode='expnad', bbox_to_anchor=pos_tech)    
                ax.add_artist(second_legend)
            
            
            ### 3.5.2 Legend with lines
            
            if lines != None:
                # Get the bounding box of the first legend
                try :
                    bbox_second_legend = second_legend.get_window_extent().transformed(ax.transAxes.inverted())
                    pos_line = (bbox_second_legend.x0, bbox_second_legend.y0)  # Adjust the vertical position as needed
                except :
                    pos_line = (0, 1)
                    
                if commodity == 'Electricity':
                    subs = 'el'
                elif commodity == 'Hydrogen':
                    subs = 'H2'
                    
                # Create lines for legend
                lines_legend = []
                string = []
                if line_legend_cluster_values == [] and line_width_cat != 'cluster' : # If the user has not input any legend values
                    # If they do not exist, create the legend clusters
                    line_legend_cluster_values = []
                    line_legend_clusters_width = []
                    # Stop the loop if idx is already at 0
                    stop_loop = False
                    for i in range(4):
                        if i == 0 : # On the first round, find the nearest value to the maximum
                            line_legend_value, line_legend_idx = find_nearest(line_legend_values, line_max_value)
                        else:
                            if line_legend_idx != 0 :
                                line_legend_value, line_legend_idx = find_nearest(line_legend_values, line_legend_value/2)
                            else :
                                stop_loop = True
                        if stop_loop == False :
                            # Find the correct width for the line
                            if line_width_cat == 'linear':
                                line_legend_width = linear_interpolation(line_legend_value, line_max_value, line_width_max, line_width_min)
                            elif line_width_cat == 'log':
                                line_legend_width = log_interpolation(line_legend_value, line_max_value, line_width_max, line_width_min)
                            # Append the values to the lists
                            line_legend_cluster_values = [line_legend_value] + line_legend_cluster_values
                            line_legend_clusters_width = [line_legend_width] + line_legend_clusters_width
                            # The patch
                            lines_legend = [Line2D([0], [0], linewidth=line_legend_width, color=line_color)] + lines_legend
                            # The text
                            ave = line_legend_value
                            string = ['%d %s$_\mathrm{%s}$'%(int(ave), line_unit, subs)] + string
                    # Add the legend
                    ax.legend(lines_legend, string, frameon=False, loc='upper left', bbox_to_anchor=pos_line)
                elif line_width_cat == 'cluster' : # If the user has choosen the clustering, we are using that for the legend
                    for i in range(len(line_cluster_values)) :
                        line_legend_value = line_cluster_values[i]
                        line_legend_width = line_cluster_widths[i]
                        lines_legend.append(Line2D([0], [0], linewidth=line_legend_width, color=line_color))
                        string.append('%d %s$_\mathrm{%s}$'%(int(line_legend_value), line_unit, subs))
                    ax.legend(lines_legend, string, frameon=False, loc='upper left', bbox_to_anchor=pos_line)
                else : # If the user has input some legend values
                    line_legend_clusters_width = []
                    for i in range(len(line_legend_cluster_values)) :
                        line_legend_value = line_legend_cluster_values[i]
                        # Find the correct width for the line
                        if line_width_cat == 'linear':
                            line_legend_width = linear_interpolation(line_legend_value, line_max_value, line_width_max, line_width_min)
                        elif line_width_cat == 'log':
                            line_legend_width = log_interpolation(line_legend_value, line_max_value, line_width_max, line_width_min)
                        line_legend_clusters_width = [line_legend_width] + line_legend_clusters_width
                        lines_legend.append(Line2D([0], [0], linewidth=line_legend_width, color=line_color))
                        string.append('%d %s$_\mathrm{%s}$'%(int(line_legend_cluster_values[i]), line_unit, subs))
                    ax.legend(lines_legend, string, frameon=False, loc='upper left', bbox_to_anchor=pos_line)
            
        ### 3.6 Limits of graph
        
        # Set limit always after pies because it brakes the graph
        ax.set_xlim(xlim[0],xlim[1])      
        ax.set_ylim(ylim[0],ylim[1])
            
            
        ### 3.5.3 Utilization legend
        
        if lines in ['UtilizationYear','UtilizationTime']:
            # Create the inset for the color bar
            # Create a new axes for the color bar
            bbox_ax = ax.get_tightbbox()
            bbox_fig = fig.transFigure.inverted().transform(bbox_ax)
            cbar_ax1 = fig.add_axes([bbox_fig[1,0]+0.005, bbox_fig[0,1]+0.01, 0.015, bbox_fig[1,1]-bbox_fig[0,1]-0.02])  # [left, bottom, width, height]
            # Normalize and create a color bar
            norm = mcolors.Normalize(vmin=0, vmax=100)
            cbar1 = fig.colorbar(cm.ScalarMappable(norm=norm, cmap="Reds"), cax=cbar_ax1)
            cbar1.set_label("Line Utilization [%]") # Add label
              
                
        ### 3.5.3 Background label and legend
        
        if background != None:
            # Ticks label
            bg_lower = np.ceil(background_scale[0] / background_scale_tick) * background_scale_tick
            bg_upper = np.floor(background_scale[1] / background_scale_tick) * background_scale_tick 
            ticks = list(np.arange(bg_lower, bg_upper+background_scale_tick, background_scale_tick))
            # Create a new axes for the color bar
            bbox_ax = ax.get_tightbbox()
            bbox_fig = fig.transFigure.inverted().transform(bbox_ax)
            cbar_ax2 = fig.add_axes([bbox_fig[0,0]-0.02, bbox_fig[0,1]+0.01, 0.015, bbox_fig[1,1]-bbox_fig[0,1]-0.02])  # [left, bottom, width, height]
            # Normalize and create a color bar
            norm = mcolors.Normalize(vmin=background_scale[0], vmax=background_scale[1])
            cbar2 = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=selected_background['colormap']), cax=cbar_ax2)
            cbar2.ax.yaxis.set_label_position('left')
            cbar2.ax.yaxis.set_ticks_position('left')
            cbar2.ax.yaxis.set_ticks(ticks)
            cbar2.set_label(f"{background} [{selected_background['unit']}]") # Add label
            
        # Black lining around the graph
        ax.plot([xlim[0],xlim[1]], [ylim[0],ylim[0]], color = 'black', linewidth = 2, zorder=1)
        ax.plot([xlim[0],xlim[1]], [ylim[1],ylim[1]], color = 'black', linewidth = 1, zorder=1)
        ax.plot([xlim[0],xlim[0]], [ylim[0],ylim[1]], color = 'black', linewidth = 1, zorder=1)
        ax.plot([xlim[1],xlim[1]], [ylim[0],ylim[1]], color = 'black', linewidth = 2, zorder=1)


        ### 3.7 Graph title
        
        if title_show :
            title_list = []
            # Add scenario name
            title_list.append(scenario)
            # Add year
            title_list.append(str(year))
            # Add season and time step if needed
            if lines in ['FlowTime', 'UtilizationTime'] or generation == 'ProductionTime':
                title_list.append(S)
                title_list.append(T)
            # Add lines information
            if lines != None :
                lines_title = commodity
                if lines == 'Capacity':
                    lines_title += ' Transmission Capacity' + f' [{line_unit}]'
                elif lines == 'FlowYear':
                    lines_title += ' Transmission Flow' + f' [{line_unit}]'
                elif lines == 'FlowTime':
                    lines_title += ' Transmission Flow' + f' [{line_unit}]'
                elif lines == 'UtilizationYear':
                    lines_title += ' Line Utilization'
                elif lines == 'UtilizationTime':
                    lines_title += ' Line Utilization'
                title_list.append(lines_title)
            
            if generation != None:
                generation_title = generation_commodity
                if generation == 'Capacity':
                    generation_title += ' Generation Capacity' + f' [{generation_unit}]'
                elif generation == 'Production':
                    generation_title += ' Generation Production' + f' [{generation_unit}]'
                elif generation == 'ProductionTime':
                    generation_title += ' Generation Production' + f' [{generation_unit}]'
                title_list.append(generation_title)
                
            ax.set_title(' - '.join(title_list))
            
            
        ### 3.8 Save the figure
        
        # Output the figure in pdf
        if save_fig and kwargs.get('filename') == None:
            output_dir = os.path.join(os.getcwd(), 'output')
            os.makedirs(output_dir, exist_ok=True)
            fig.savefig(os.path.join(output_dir, f'{commodity}_{lines}_{generation_commodity}_{generation}.pdf'), bbox_inches='tight')
        elif save_fig and kwargs.get('filename') != None:
            output_dir = os.path.join(os.getcwd(), 'output')
            os.makedirs(output_dir, exist_ok=True)
            fig.savefig(os.path.join(output_dir, kwargs.get('filename')), bbox_inches='tight')
        
        return fig, ax
            
    else:
        print("\nDidn't find a scenario in the paths given")
      
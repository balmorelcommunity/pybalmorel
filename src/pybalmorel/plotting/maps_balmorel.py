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

try:
    import cartopy.crs as ccrs
    cartopy_installed = True
except ModuleNotFoundError:
    cartopy_installed = False


def plot_map(path_to_result: str, 
             SCENARIO: str, 
             year: int,
             commodity: str,
             lines: str = 'Capacity', 
             gnr: str = 'Capacity',
             bg: str = 'None',
             legend: bool = True,
             system_directory: str = None,
             **kwargs) -> Tuple[Figure, Axes]:
    
    """Plots the transmission capacities or flow in a scenario, of a certain commodity and the generation capacities or production of the regions.

    Args:
        path_to_result (str): Path to the .gdx file
        SCENARIO (str): The scenario name       
        year (int): Model year 
        commodity (str): Electricity or Hydrogen
        lines (str, optional): Information plots with the lines. Choose from ['Capacity', 'FlowYear', 'FlowTime']. Defaults to 'Capacity'.
        gnr (str, optional): Information plots on the countries. Choose from ['Capacity', 'Production']. Defaults to 'Capacity'.
        legend (bool, optional): Show legend or not. Defaults to True.
        system_directory (str, optional): GAMS system directory. Default does NOT WORK! Need to make some if statements so it's not specified if not specified
        Structural additional options:
            **S (str, optional): Season for FlowTime. Will pick one random if not specified.
            **T (str, optional): Hour for FlowTime. Will pick one random if not specified.
            **exo_end (str, optional): Show only exogenous or endogenous capacities. Choose from ['Both', 'Endogenous', 'Exogenous']. Defaults to 'Both'.
            **gnr_exclude_Import_Cap_H2 (bool, optional): Do not plot the capacities and production related to H2 Import (will be shown as line). Defaults to True.
            **gnr_exclude_H2Storage (bool, optional): Do not plot the capacities of the H2 storage. Defaults to True.
            **gnr_exclude_ElectricStorage (bool, optional): Do not plot the production of Electric storage. Defaults to True.
            **gnr_exclude_Geothermal (bool, optional): Do not plot the production of Geothermal. Defaults to True.
        Visual additional options:
            Lines options :
                **line_width_cat (str, optional): Way of determining lines width. Choose from ['linear', 'cluster']. Defaults to 'cluster'.
                **line_width_constant (int, optional): Constant related to thickness of lines if cat is 'linear'. Defaults values depends on commodity.
                **line_cluster_groups (list, optional): The capacity groupings if cat is 'cluster'. Defaults values depends on commodity.
                **line_cluster_widths (list, optional): The widths for the corresponding capacity group (has to be same size as cluster_groups). Defaults values depends on commodity.
                **line_label_show (bool, optional): Showing or not the value of the lines. Defaults to False.
                **line_label_min (int, optional): Minimum transmission capacity (GW) or flow (TWh) shown on map in text. Defaults to 0.
                **line_label_decimals (int, optional): Number of decimals shown for line capacities. Defaults to 1.
                **line_label_fontsize (int, optional): Font size of transmission line labels. Defaults to 10.
            Gnr options :
                **gnr_show (bool, optional): Showing or not the gnr capacities or production. Defaults to True.
                **gnr_commodity (str, optional): Commodity to be shown in the gnr map, if not specified, same as line commodity. Defaults to commodity.
                **gnr_display_type (str, optional): Type of display on regions. Choose from ['Pie']. Defaults to 'Pie'.
                **gnr_var (str, optional): Variable to be shown in the pie chart. Choose from ['TECH_TYPE', 'FFF']. Defaults to 'TECH_TYPE'.
                **pie_cat (str, optional): Way of determining pie size. Choose from ['linear', 'cluster']. Defaults to 'cluster'.
                **pie_width_constant (float, optional): Constant factored on sum of generation capacities, if linear cluster choosen. Defaults to 0.03.
                **pie_cluster_groups = The capacity groupings if cat is 'cluster'. Defaults values depends on commodity.
                **pie_cluster_radius = The radius for the corresponding capacity group (has to be same size as pie_cluster_groups). Defaults values depends on commodity.
                **pie_legend_cluster_groups = The capacity groupings for the legend if cat is 'cluster'. Defaults values depends on commodity.
                **pie_legend_cluster_radius = The radius for the corresponding capacity group for the legend (has to be same size as pie_legend_cluster_groups). Defaults values depends on commodity.
        Colors additional options:
            **background_color (str, optional): Background color of the map. Defaults to 'white'.
            **regions_ext_color (str, optional): Color of regions outside the model. Defaults to '#d3d3d3'.
            **regions_model_color (str, optional): Color of regions inside the model. Defaults to 'linen'.
            **line_color (str, optional): Color of lines network. Defaults to 'green' for electricity and '#13EAC9' for hydrogen.
            **line_label_color (str, optional): Color of line labels. Defaults to 'black'.
            **gnr_tech_color (dict, optional): Dictionnary of colors for each technology. Defaults to colors for electricity and hydrogen.
            **gnr_fuel_color (dict, optional): Dictionnary of colors for each fuel. Defaults to colors for electricity and hydrogen.
        Geography additional options:
            **coordinates_RRR_path = Path to the csv file containing the coordinates of the regions centers.
            **bypass_path = Path to the csv file containing the coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions.
            **hydrogen_third_nations_path = Path to the csv file containing the coordinates of h2 import lines from third nations.

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
                if os.path.exists(subpath + '/MainResults_%s_Iter%s.gdx'%(SCENARIO, iter)): 
                    path_to_result = subpath
                    print('Found %s_Iter%s in %s'%(SCENARIO, iter, path_to_result))
                    SCENARIO = SCENARIO + '_Iter%s'%iter
                    found_scenario = True
                    break
                    
                elif os.path.exists(subpath + '/MainResults_%s.gdx'%SCENARIO):
                    path_to_result = subpath
                    print('Found %s in %s'%(SCENARIO, path_to_result))
                    found_scenario = True
                    break
    else:
        if os.path.exists(path_to_result + '/MainResults_%s_Iter%s.gdx'%(SCENARIO, iter)): 
            print('Found %s_Iter%s in %s'%(SCENARIO, iter, path_to_result))
            SCENARIO = SCENARIO + '_Iter%s'%iter
            found_scenario = True
            
        elif os.path.exists(path_to_result + '/MainResults_%s.gdx'%SCENARIO):
            print('Found %s in %s'%(SCENARIO, path_to_result))
            found_scenario = True
    
    if found_scenario:

        ### ----------------------------- ###
        ###        1. Preparations        ###
        ### ----------------------------- ###


        ### 1.1 Set Options
        
        # Structural options
        commodity = commodity.capitalize()
        if commodity not in ['Electricity', 'Hydrogen']: # Check that it's a possible type of commodity
            raise ValueError('commodity must be either "Electricity" or "Hydrogen"')
        if lines not in ['Capacity', 'FlowYear', 'FlowTime', 'CongestionFlowYear', 'CongestionFlowTime']: # Check that it's a possible type of lines display
            raise ValueError('lines must be either "Capacity", "FlowYear", "FlowTime", "CongestionFlowYear or "CongestionFlowTime"')
        if gnr not in ['Capacity', 'Production']: # Check that it's a possible type of gnr display
            raise ValueError('gnr must be either "Capacity" or "Production"')
        if lines in ['FlowTime', 'CongestionFlowTime']: # Check if there is a specified season and hour for flow maps
            S = kwargs.get('S', '')
            T = kwargs.get('T', '')
        exo_end = kwargs.get('exo_end', 'Both') # Options for showing only exogenous or endogenous capacities
        if exo_end not in ['Both', 'Endogenous', 'Exogenous']:
            print('exo_end must be either "Both", "Endogenous" or "Exogenous", set to "Both"')
            exo_end = 'Both'
        gnr_exclude_Import_Cap_H2 = kwargs.get('gnr_exclude_Import_Cap_H2',True) #take out the capacities because of the IMPORT_H2 from oher countreis
        gnr_exclude_H2Storage = kwargs.get('gnr_exclude_H2Storage', True)  #do not plot the capacities of the H2 storage
        gnr_exclude_ElectricStorage = kwargs.get('gnr_exclude_ElectricStorage', True)  #do not plot the production of Electric storag, only works with Show pie production
        gnr_exclude_Geothermal = kwargs.get('gnr_exclude_Geothermal', True) #do not plot the production of Geothermal, only works with Show pie production -> Do we have ?
        
        background_dict = {'H2 Storage': {'var': 'G_STO_YCRAF', 'filters': [('COMMODITY','HYDROGEN')], 'transformation': [1/1000], 'colormap': (plt.cm.Blues,'Blues'), 'unit': 'TWh'},
                           'Elec Storage': {'var': 'G_STO_YCRAF', 'filters': [('COMMODITY','ELECTRICITY')], 'transformation': [1/1000], 'colormap': (plt.cm.Oranges,'Oranges'), 'unit': 'TWh'}}
        if bg not in background_dict.keys() : # Check that it's a possible type of background
            print('bg set to "None"')
            bg = 'None' 
        selected_bg = background_dict[bg].copy() if bg != 'None' else None
        
        # Visual options
        show_country_out = kwargs.get('show_country_out', True) # Showing or not the countries outside the model
        dict_map_coordinates = {'EU': [(-11,36),(33,72)], 'DK': [(7.5,13.5),(54.5,58)], 'Nordic': [(4.8,17),(50.5,70)]} # Dictionary of coordinates for different maps
        choosen_map_coordinates = kwargs.get('choosen_map_coordinates', 'EU') # Choose the map to be shown
        map_coordinates = kwargs.get('map_coordinates', '') # Coordinates of the map
        if map_coordinates != '' :
            dict_map_coordinates['Custom'] = map_coordinates
            choosen_map_coordinates = 'Custom'
        line_width_cat = kwargs.get('line_width_cat', 'log') # 'linear' = Capacities are scaled linearly, 'cluster' = capacities are clustered in groups
        if line_width_cat not in ['linear', 'log', 'cluster']: # Check that it's a possible category of line thickness
            print('line_thick_cat must be either "linear", "log" or "cluster", set to "log"')
            line_width_cat = 'log'
        line_show_min = kwargs.get('line_show_min', 0) # Minimum transmission capacity (GW) or flow (TWh) shown on map
        line_width_min = kwargs.get('line_width_min', 0.5) # Minimum width of lines, used if cat is linear or log
        line_width_max = kwargs.get('line_width_max', 12) # Maximum width of lines, used if cat is linear or log
        if lines == "FlowYear" : 
            line_cluster_groups = kwargs.get('line_cluster_groups', [10, 30, 60, 100]) # The capacity groupings if cat is 'cluster'
        else :
            if commodity == 'Electricity' :
                line_cluster_groups = kwargs.get('line_cluster_groups', [5, 15, 30, 60]) # The capacity groupings if cat is 'cluster'
            elif commodity == 'Hydrogen':
                line_cluster_groups = kwargs.get('line_cluster_groups', [5, 10, 20, 30]) # The capacity groupings if cat is 'cluster'
        line_cluster_widths = kwargs.get('line_cluster_widths', [1, 5, 8, 12]) # The widths for the corresponding capacity group used if cat is 'cluster'
        if len(line_cluster_groups) != len(line_cluster_widths): # Raise error if the cluster groups and widths are not of same length
            raise ValueError('line_cluster_groups and line_cluster_widths must be of same length')
        line_opacity = kwargs.get('line_opacity', 1) # Opacity of lines
        line_label_show = kwargs.get('line_label_show', False)  # Showing or not the value of the lines
        line_label_min = kwargs.get('line_label_min', 0) #Minimum transmission capacity (GW) or flow (TWh) shown on map in text
        line_label_decimals = kwargs.get('line_label_decimals', 1) #Number of decimals shown for line capacities
        line_label_fontsize = kwargs.get('line_font_size', 10) #Font size of transmission line labels
        line_flow_show = kwargs.get('line_flow_show', True) # Showing or not the arrows on the lines
        # gnr options
        gnr_show = kwargs.get('gnr_show', True) # Showing or not the gnr capacities or production
        gnr_show_min = kwargs.get('gnr_show_min', 0.001) # Minimum generation capacity (GW) or production (TWh) shown on map
        gnr_commodity = kwargs.get('gnr_commodity', commodity) # Commodity to be shown in the gnr map, if not specified, same as line commodity
        if gnr_commodity not in ['Electricity', 'Hydrogen']:
            print(f'gnr_commodity must be either "Electricity" or "Hydrogen", set to {commodity}')
            gnr_commodity = commodity
        gnr_display_type = kwargs.get('gnr_display_type', 'Pie') 
        if gnr_display_type not in ['Pie']:
            print('gnr_display_type must be either "Pie", set to "Pie"')
            gnr_display_type = 'Pie'
        gnr_var = kwargs.get('gnr_var', 'TECH_TYPE') # Variable to be shown in the pie chart
        if gnr_var not in ['TECH_TYPE', 'FFF']:
            print('gnr_var must be either "TECH_TYPE" or "FFF", set to "TECH_TYPE"')
            gnr_var = 'TECH_TYPE'
        if gnr_display_type == 'Pie':
            pie_radius_cat = kwargs.get('pie_radius_cat', 'log') # 'linear' = Capacities are scaled linearly, 'cluster' = capacities are clustered in groups
            if pie_radius_cat not in ['linear', 'log', 'cluster']: # Check that it's a possible category of line thickness
                print('pie_radius_cat must be either "linear", "log" or "cluster", set to "log"')
                pie_radius_cat = 'log'
            pie_show_min = kwargs.get('pie_show_min', 0) # Minimum transmission capacity (GW) or flow (TWh) shown on map
            pie_radius_dict = {'EU': {'pie_radius_min' : 0.2, 'pie_radius_max' : 1.4, 'pie_cluster_radius' : [0.2, 0.6, 1, 1.3], 
                                      'pie_cluster_groups' : {'Production' : {'Electricity' : [20,50,200,400], 'Hydrogen' : [10,50,100,250]}, 
                                                              'Capacity' : {'Electricity' : [10,50,200,400], 'Hydrogen' : [1,10,30,60]}}}, 
                               'DK': {'pie_radius_min' : 0.05, 'pie_radius_max' : 0.5, 'pie_cluster_radius' : [0.05, 0.1, 0.25, 0.5], 
                                      'pie_cluster_groups' : {'Production' : {'Electricity' : [10,25,50,100], 'Hydrogen' : [0.5,1,2,50]}, 
                                                              'Capacity' : {'Electricity' : [5,10,25,50], 'Hydrogen' : [0.1,0.2,0.5,1]}}}}
            pie_radius_min = kwargs.get('pie_radius_min', pie_radius_dict[choosen_map_coordinates]['pie_radius_min']) # Minimum width of lines, used if cat is linear or log
            pie_radius_max = kwargs.get('pie_radius_max', pie_radius_dict[choosen_map_coordinates]['pie_radius_max']) # Maximum width of lines, used if cat is linear or log
            pie_cluster_groups = kwargs.get('pie_cluster_groups', pie_radius_dict[choosen_map_coordinates]['pie_cluster_groups'][gnr][commodity]) # The capacity groupings if cat is 'cluster'
            pie_cluster_radius = kwargs.get('pie_cluster_radius', pie_radius_dict[choosen_map_coordinates]['pie_cluster_radius'])
            if len(pie_cluster_groups) != len(pie_cluster_radius):
                raise ValueError('pie_cluster_groups and pie_cluster_radius must be of same length')

        # Colors options
        # Map colors options 
        background_color = kwargs.get('background_color', 'white') #Background color of the map
        regions_ext_color = kwargs.get('regions_ext_color', '#d3d3d3') #Color of regions outside the model
        regions_model_color = kwargs.get('regions_model_color', 'linen') #Color of regions inside the model
        # Line colors options
        if commodity == 'Electricity':
            line_color = kwargs.get('line_color', 'green') # Color of electrical network
        elif commodity == 'Hydrogen':
            line_color = kwargs.get('line_color', '#13EAC9') # Color of hydrogen network
        line_label_color = kwargs.get('line_label_color', 'black') #Color of line labels
        # gnr colors options
        gnr_tech_color = {
        'HYDRO-RESERVOIRS': '#33b1ff',
        'HYDRO-RUN-OF-RIVER': '#4589ff',
        'WIND-ON': '#006460',
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
        'WIND-OFF': '#08bdba',
        'INTRASEASONAL-ELECT-STORAGE': '#ba4e00',
        'ELECTROLYZER': '#ADD8E6',
        'H2-STORAGE': '#FFC0CB',
        'FUELCELL': '#d4bbff'
        }

        '''
        gnr_fuel_color = {
        'HYDRO': '#4589ff',
        'WIND-ON': '#006460',
        'WIND-OFF': '#08bdba',
        'BIOGAS': '#d1b9b9',
        'COAL': '#7f7f7f',
        'ELECTRIC': '#BA000F',
        'OIL': '#8c564b',
        'MUNIWASTE': '#FFC0CB',
        'BIOMASS': '#ff7eb6',
        'HEAT': '#a5e982',
        'NATGAS': '#cd6f00',
        'NATGAS-CCS':'#388d3a',
        'OTHER': '#ffbb78',
        'SOLAR': '#fad254',
        'NUCLEAR': '#8a3ffc',
        'LIGNITE': '#2b1d1d',
        'HYDROGEN': '#f4eeff',
        }
        '''

        gnr_fuel_color = {
        'HYDRO': '#08bdba',
        'WIND-ON': '#5e45ff',
        'WIND-OFF': '#4589ff',
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
        
    

        # Not relevant or not sure what they do ?
        filetype_input = 'gdx' #Choose input file type: 'gdx' or 'csv'  -> I think not relevant because we are using gdx files
        market = 'Investment' #Choose from ['Balancing', 'DayAhead', 'FullYear', 'Investment'] -> Figure out why different market ?
        YEAR = '' #Add year to read file name (e.g. '2025', '2035', 'full') -> 
        SUBSET = '' #Add subset to read file name (e.g. 'full')
        # Alternative geofile (off, at the moment)
        AltGeo = 'Balmorel'  
        # AltGeo = 'MUNI' # The other type of polygons, if traditional Balmorel regions areas not used
        # AltGeoCol = 'NUTS_ID' # Column to search in file of other type of polygon
        AltGeoCol = 'GID_2'
        # AltGeoPath = r'C:\Users\mberos\OneDrive - Danmarks Tekniske Universitet\Dokumenter\Balmorel\base\auxils\create_BalmorelInput\Data\Shapefiles\NUTS_RG_01M_2021_4326\NUTS_RG_01M_2021_4326.shp' # Path to other type of polygons
        AltGeoPath = r'geojson'
        # hubs
        hub_display = False
        hub_size = 100.6
        hub_decimals = 10 #Number of decimals shown for hub capacities
        background_hubsize = True #Displaying the true size of the hub as a circle on the map.
        hub_area = 100.8 #MW / km^2, background hub size on map. 
        hub_area_opacity = 10.7 #Opacity of background hub size. 
        font_hub = 12 #Font size of hub labels
        hub_color = 'lightblue'
        hub_background_color = 'lightblue'
        hub_text = 'black'
        
        # Not implemented but could be nice
        font_region = 10 #Font size of region labels
        region_text = 'black'  


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
        
        # Delete later when the geography question is solved
        # if path_to_geofile == None:
        #     path_to_geofile = os.path.abspath(os.path.join(wk_dir, '../geofiles/2024 BalmorelMap.geojson'))
        # geo_file = gpd.read_file(path_to_geofile) # For another map that includes all EU
        # project_dir = './Input' # For csv reading
        
        # Path to csv coordinates files
        coordinates_RRR_path = kwargs.get('coordinates_RRR_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/coordinates_RRR.csv'))) # Coordinates of regions centers
        bypass_path = kwargs.get('bypass_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/bypass_lines.csv'))) # Coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions
        hydrogen_third_nations_path = kwargs.get('hydrogen_third_nations_path', os.path.abspath(os.path.join(wk_dir, '../geofiles/hydrogen_third_nations.csv'))) # Coordinates of h2 import lines from third nations
        
        # Load coordinates csv files
        df_unique = pd.read_csv(coordinates_RRR_path)
        df_region = df_unique.loc[df_unique['Type'] == 'region', ]
        df_bypass = pd.read_csv(bypass_path) 
        if commodity == 'Hydrogen':
            df_hydrogen_lines_outside = pd.read_csv(hydrogen_third_nations_path) 

        # List of regions names in and out of the model
        r_in = list(df_unique.loc[(df_unique['Display'] == 1) & (df_unique['Type'] == 'region'), 'RRR'])
        r_out = list(df_unique.loc[(df_unique['Display'] == 0) & (df_unique['Type'] == 'region'), 'RRR'])

        # Define dictionnaries for paths to regions geojson files
        layers_in = {region: '' for region in r_in}
        layers_out = {region: '' for region in r_out}

        # Fill dictionnaries with layer paths for each region; if both a shapefile and geojson file are available for one region, the geojson file is used. 
        for region in r_in:
            layers_in[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/geojson_files/'+ region + '.geojson')))
            if bool(layers_in[region]) == False:
                layers_in[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/shapefiles/'+ region + '.shp')))
        for region in r_out:
            layers_out[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/geojson_files/'+ region + '.geojson')))
            if bool(layers_out[region]) == False:
                layers_out[region] = glob.glob(os.path.abspath(os.path.join(wk_dir, '../geofiles/shapefiles/'+ region + '.shp')))
                
        #Remove brackets from file paths
        for region in layers_in:
            layers_in[region] = str(layers_in[region])[2:-2] 
        for region in layers_out:
            layers_out[region] = str(layers_out[region])[2:-2]

        #Convert shapefiles to geojson files  
        for region in layers_out:
            if layers_out[region][-4:] == '.shp':
                gpd.read_file(layers_out[region]).to_file(os.path.abspath(os.path.join(wk_dir, '../geofiles/geojson_files/'+ region + '.geojson')), driver='GeoJSON')
                layers_out[region] = layers_out[region].replace('shapefiles', 'geojson_files').replace('.shp', '.geojson')


        ### 1.4 Read run-specific files

        ## 1.4.0 If commodity == 'Other': define variables or file names -> Change this so that it's having the name of the commodity in the var_list, do later
        # if commodity == 'Other':
        #     if filetype_input == 'gdx':
        #         var_list = ['G_CAP_YCRAF', 'XH2_CAP_YCR', 'XH2_FLOW_YCRST', 'PRO_YCRAGFST'] #Fill in variables to read, e.g. ['G_CAP_YCRAF', 'X{commodity}_CAP_YCR', 'X{commodity}_FLOW_YCRST', 'PRO_YCRAGST']
        #     if filetype_input == 'csv':
        #         flow_file = 'FlowH2Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv' #Fill in flow file name if applicable, e.g. 'Flow{commodity}Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        #         transcap_file = 'CapacityH2Transmission_' + SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv' #Fill in transmission capacity file name, e.g. 'Capacity{commodity}Transmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv' 

        ## 1.4.1 Function: reading gdx-files -> Don't understand the interest of creating those columns

        def df_creation(gdx_file, varname, system_directory):
            df = pd.DataFrame()
            if '_' in gdx_file:
                    # if yes: extract scenario name from gdx filename
                # print(gdx_file)
                scenario = SCENARIO
                # year = year
                subset = SUBSET
                market = 'Invest'
            else:
                # if no: use nan instead
                scenario = ''
                subset = SUBSET
                market = ''

            # create empty temporary dataframe and load the gdx data into it
            temp = pd.DataFrame()
            # temp = gdxpds.to_dataframe(gdx_file, varname, gams_dir=gams_dir,
            #                        old_interface=False)
            
            temp=dataframe_from_gdx(gdx_file,varname, system_directory)

            # add a scenario column with the scenario name of the current iteration
            temp['Scenario'] = scenario
            temp['Market']  = market
            temp['run'] = scenario + '_' + str(year) + '_' + subset

            # rearrange the columns' order
            cols = list(temp.columns)
            cols = [cols[-1]] + cols[:-1]
            temp = temp[cols]

            # concatenate the temporary dataframe to the preceeding data
            df = pd.concat([df, temp], sort=False)
            return df


        ## 1.4.2 - Define var_list
        
        var_list = []
        var_list = var_list + ['G_CAP_YCRAF', 'PRO_YCRAGF']
        if commodity == 'Electricity':
            if lines == 'Capacity' : 
                var_list = var_list + ['X_CAP_YCR']
            elif lines == 'FlowYear' :
                var_list = var_list + ['X_FLOW_YCR']
            elif lines == 'FlowTime' :
                var_list = var_list + ['X_FLOW_YCRST']
            elif lines == 'CongestionFlowYear':
                var_list = var_list + ['X_CAP_YCR', 'X_FLOW_YCR']
            elif lines == 'CongestionFlowTime':
                var_list = var_list + ['X_CAP_YCR', 'X_FLOW_YCRST']
            # if hub_display == True: -> Do we keep hubs ?
            #     var_list = var_list + ['PRO_YCRAGFST']
        if commodity == 'Hydrogen':
            if lines == 'Capacity' : 
                var_list = var_list + ['XH2_CAP_YCR']
            elif lines == 'FlowYear' :
                var_list = var_list + ['XH2_FLOW_YCR']
            elif lines == 'CongestionFlowYear' :
                var_list = var_list + ['XH2_CAP_YCR', 'XH2_FLOW_YCR']
            if lines == 'FlowTime' : 
                var_list = var_list + ['XH2_FLOW_YCRST']
            if lines == 'CongestionFlowTime': 
                var_list = var_list + ['XH2_CAP_YCR', 'XH2_FLOW_YCRST']
            # if hub_display == True: -> Do we keep hubs ?
            #     var_list = var_list + ['PRO_YCRAGFST']
        if selected_bg != None:
            var_list = var_list + [selected_bg['var']]


        ## 1.4.3 - Use function to read inputs
        
        # Retrieve path to gdx file
        if ('MainResults' in path_to_result) or ('.gdx' in path_to_result): # Not sure of the interest of all of this
            gdx_file =  glob.glob(path_to_result)
        elif (YEAR == '') & (SUBSET == ''):
            gdx_file =  glob.glob(path_to_result + '\\MainResults_' + SCENARIO + '.gdx')
        else:
            gdx_file =  glob.glob('./input/results/'+ market + '\\MainResults_' + SCENARIO + '_'  + YEAR + '_' + SUBSET + '.gdx')
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
            elif lines == 'CongestionFlowYear' :
                df_cap = all_df['X_CAP_YCR']
                df_line = all_df['X_FLOW_YCR']
            elif lines == 'CongestionFlowTime':
                df_cap = all_df['X_CAP_YCR']
                df_line = all_df['X_FLOW_YCRST']
        elif commodity == 'Hydrogen':
            if lines == 'Capacity' :
                df_line = all_df['XH2_CAP_YCR']
            elif lines == 'FlowYear' :
                df_line = all_df['XH2_FLOW_YCR']
            elif lines == 'FlowTime' :
                df_line = all_df['XH2_FLOW_YCRST']
            elif lines == 'CongestionFlowYear' :
                df_cap = all_df['XH2_CAP_YCR']
                df_line = all_df['XH2_FLOW_YCR']
            elif lines == 'CongestionFlowTime':
                df_cap = all_df['XH2_CAP_YCR']
                df_line = all_df['XH2_FLOW_YCRST']
            # elif lines == 'FlowTime' : # Not flow time for hydrogen ???
            #     df_line = all_df['XH2_FLOW_YCRST']
                
        # Generation data
        if gnr == 'Capacity':
            df_gnr = all_df['G_CAP_YCRAF']
        elif gnr == 'Production':
            df_gnr = all_df['PRO_YCRAGF']
        if gnr_commodity == 'Electricity':
            df_gnr = df_gnr[df_gnr['COMMODITY'] == 'ELECTRICITY']
        elif gnr_commodity == 'Hydrogen':
            df_gnr = df_gnr[df_gnr['COMMODITY'] == 'HYDROGEN']
            
        # Background data
        if selected_bg != None:
            df_bg = all_df[selected_bg['var']]
                
        ## 1.4.4 - Select relevant dataframe and rename columns
        column_dict = {'Val':'Value', 'Y':'Year', 'C':'Country'}
        df_line = df_line.rename(columns = column_dict)
        df_gnr = df_gnr.rename(columns = column_dict)
        if lines in ['CongestionFlowYear', 'CongestionFlowTime'] :
            df_cap = df_cap.rename(columns = column_dict)
        if selected_bg != None:
            df_bg = df_bg.rename(columns = column_dict)
        # if hub_display == True: # Do we keep hubs ?
        #     df_capgen = df_capgen.rename(columns = column_dict)
        #     if lines == 'Flow' or lines == 'CongestionFlow': 
        #             df_hubprod = df_hubprod.rename(columns = column_dict)
        

        ## 1.4.4 - Hub data -> Do we keep hubs ?
        # if filetype_input == 'gdx' and hub_display == True:
        #     hub_windgen = (pd.read_csv('./Input/geo_files/hub_technologies.csv', sep = ',', quotechar = '"').hub_name) 
        #     df_capgen = all_df['G_CAP_YCRAF']
        #     if lines == 'Flow' or lines == 'CongestionFlow':
        #         df_hubprod = all_df['PRO_YCRAGFST']
        #         df_hubprod['Y'] = df_hubprod['Y'].astype(int)
        #         df_hubprod = df_hubprod.loc[(df_hubprod['G'].isin(hub_windgen)) & (df_hubprod['TECH_TYPE'] == 'WIND-OFF') & (df_hubprod['Y']==year) & (df_hubprod['SSS'] == S) & (df_hubprod['TTT']==T), ]


        ## 1.4B1 - Read CSV files -> Are we really gonna use csv files ???
        # map_name = 'Transmission' + commodity + '_' + lines + '_' + str(year) + '_Map.html'
        # if filetype_input == 'csv':
        #     generation_file = 'CapacityGeneration_'+  SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        #     if commodity == 'Electricity':
        #         flow_file = 'FlowElectricityHourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        #         transcap_file = 'CapacityElectricityTransmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv'
        #     if commodity == 'Hydrogen':
        #         flow_file = 'FlowH2Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        #         transcap_file = 'CapacityH2Transmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv'
            
        #     #Transmission capacity data
        #     df_capacity = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(transcap_file), sep = ',', quotechar = '"') 
        #     #Transmission flow data
        #     if lines == 'Flow' or lines == 'CongestionFlow':
        #         df_flow = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(flow_file), sep = ',', quotechar = '"')

        #     if hub_display == True:
        #         prod_file = 'ProductionHourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        #         hub_windgen = (pd.read_csv('./Input/geo_files/hub_technologies.csv', sep = ',', quotechar = '"').hub_name) 
        #         #Generation capacity data
        #         df_capgen = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(generation_file), sep = ',', quotechar = '"') 
        #         if lines == 'Flow' or lines == 'CongestionFlow':
        #         #Hub production data
        #             df_hubprod = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(prod_file), sep = ',', quotechar = '"') 
        #             df_hubprod = df_hubprod.loc[(df_hubprod['G'].isin(hub_windgen)) & (df_hubprod['TECH_TYPE'] == 'WIND-OFF') & (df_hubprod['Y']==year) & (df_hubprod['SSS'] == S) & (df_hubprod['TTT']==T), ]


        ### ----------------------------- ###
        ###        2. Processing          ###
        ### ----------------------------- ###

        ## 2.1 Replace "EPS" with 0

        df_line.Value=df_line.Value.replace('Eps', 0)
        df_line.Value=pd.to_numeric(df_line.Value)
        df_gnr.Value=df_gnr.Value.replace('Eps', 0)
        df_gnr.Value=pd.to_numeric(df_gnr.Value)
        if selected_bg != None:
            df_bg.Value=df_bg.Value.replace('Eps', 0)
            df_bg.Value=pd.to_numeric(df_bg.Value)
        # if hub_display == True: # Do we keep hubs ?
        #     df_capgen.Value=df_capgen.Value.replace('Eps', 0)
        #     df_capgen.Value=pd.to_numeric(df_capgen.Value)
        #     if lines == 'Flow' or lines == 'CongestionFlow':
        #         df_hubprod.Value=df_hubprod.Value.replace('Eps', 0)
        #         df_hubprod.Value=pd.to_numeric(df_hubprod.Value)


        ### 2.2 Filter dataframes for relevant data
        
        # Filter the year
        df_line['Year'] = df_line['Year'].astype(int)
        df_line = df_line.loc[df_line['Year'] == year].reset_index(drop = True)
        df_gnr['Year'] = df_gnr['Year'].astype(int)
        df_gnr = df_gnr.loc[df_gnr['Year'] == year].reset_index(drop = True)
        if lines in ['CongestionFlowYear', 'CongestionFlowTime']:
            df_cap['Year'] = df_cap['Year'].astype(int)
            df_cap = df_cap.loc[df_cap['Year'] == year].reset_index(drop = True)
        if selected_bg != None:
            df_bg['Year'] = df_bg['Year'].astype(int)
            df_bg = df_bg.loc[df_bg['Year'] == year].reset_index(drop = True)
        
        # Exogenous and endogenous capacities
        if lines == 'Capacity' :
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_line.columns),np.where((df_line.columns == 'VARIABLE_CATEGORY') | (df_line.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
                df_line = pd.DataFrame(df_line.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
            elif exo_end == 'Endogenous' :
                df_line = df_line.loc[df_line['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_line = df_line.loc[df_line['VARIABLE_CATEGORY'] == 'EXOGENOUS']
        elif lines in ['CongestionFlowYear','CongestionFlowTime'] :
            col_keep = list(np.delete(np.array(df_cap.columns),np.where((df_cap.columns == 'VARIABLE_CATEGORY') | (df_cap.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
            df_cap = pd.DataFrame(df_cap.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
        if gnr == 'Capacity':
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_gnr.columns),np.where((df_gnr.columns == 'VARIABLE_CATEGORY') | (df_gnr.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
                df_gnr = pd.DataFrame(df_gnr.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
            elif exo_end == 'Endogenous' :
                df_gnr = df_gnr.loc[df_gnr['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_gnr = df_gnr.loc[df_gnr['VARIABLE_CATEGORY'] == 'EXOGENOUS']
        if selected_bg != None:
            if exo_end == 'Both' :
                col_keep = list(np.delete(np.array(df_bg.columns),np.where((df_bg.columns == 'VARIABLE_CATEGORY') | (df_bg.columns == 'Value')) ))
                df_bg = pd.DataFrame(df_bg.groupby(col_keep)['Value'].sum().reset_index() )
            elif exo_end == 'Endogenous' :
                df_bg = df_bg.loc[df_bg['VARIABLE_CATEGORY'] == 'ENDOGENOUS']
            elif exo_end == 'Exogenous' :
                df_bg = df_bg.loc[df_bg['VARIABLE_CATEGORY'] == 'EXOGENOUS']
                
        # Time and season for FlowTime
        if lines == 'FlowTime' or lines == 'CongestionFlowTime':
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
            
        
        ### 2.3 Calculate the congestion of the lines
        
        if lines == 'CongestionFlowTime':
            df_line = pd.merge(df_line, df_cap[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
            df_line.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
            df_line['Congestion'] = df_line['Value'] / df_line['Capacity'] * 100
            df_line['Value'] = df_line['Congestion']
        elif lines == 'CongestionFlowYear':
            df_line = pd.merge(df_line, df_cap[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
            df_line.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
            df_line['Congestion'] = df_line['Value'] / (df_line['Capacity']*8760/1000) * 100
            df_line['Value'] = df_line['Congestion']

        
        ### 2.4 Add coordinates to line dataframes
        
        for i,row in df_line.iterrows():
                for j in range(0,len(df_unique)):
                    if df_line.loc[i,'IRRRE'] == df_unique.loc[j, 'RRR']:
                        df_line.loc[i,'LatExp'] = df_unique.loc[j, 'Lat']
                        df_line.loc[i,'LonExp'] = df_unique.loc[j, 'Lon']
                    if df_line.loc[i,'IRRRI'] == df_unique.loc[j, 'RRR']:
                        df_line.loc[i,'LatImp'] = df_unique.loc[j, 'Lat']
                        df_line.loc[i,'LonImp'] = df_unique.loc[j, 'Lon']
                      
        
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
        # When FlowYear or CongestionFlowYear is selected, do the balance between the two directions
        if lines in ['FlowYear','CongestionFlowYear'] :
            df_line_new = pd.DataFrame(columns = df_line.columns) # Create new dataframe to store the balanced values
            indexes = [] # Keep indexes of the lines that have been balanced
            for i,row in df_line.iterrows():
                for k,row in df_line.iterrows():
                    if (df_line.loc[k,'IRRRE'] == df_line.loc[i,'IRRRI']) & (df_line.loc[k,'IRRRI'] == df_line.loc[i,'IRRRE']):
                        if (df_line.loc[k,'Value'] >= df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[k]]], ignore_index=True)
                            if lines == 'FlowYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[k,'Value'] - df_line.loc[i,'Value'] # Add the difference to the new dataframe
                            elif lines == 'CongestionFlowYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[k,'Value'] + df_line.loc[i,'Value'] # Add the line utilization to the new dataframe
                        elif (df_line.loc[k,'Value'] < df_line.loc[i,'Value']) & (i not in indexes) & (k not in indexes):
                            df_line_new = pd.concat([df_line_new, df_line.loc[[i]]], ignore_index=True)
                            if lines == 'FlowYear':
                                df_line_new.loc[len(df_line_new)-1,'Value'] = df_line.loc[i,'Value'] - df_line.loc[k,'Value'] # Add the difference to the new dataframe
                            elif lines == 'CongestionFlowYear':
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
        elif lines == 'CongestionFlowTime':
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'UNITS', 'Value', 'Capacity']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        elif lines == 'CongestionFlowTime':
            df_bypass = pd.merge(df_bypass, df_line[['Year', 'Country', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Value', 'Capacity']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
        #Replace existing row by 2 bypass rows
        keys = list(df_bypass.columns.values)[0:2]
        i1 = df_line.set_index(keys).index
        i2 = df_bypass.set_index(keys).index
        df_line = df_line[~i1.isin(i2)] #Delete existing rows that need bypass
        df_line = df_line._append(df_bypass, ignore_index = True, sort = True) #Append bypass rows


        ### 2.7 Define line centers
        
        #Define centre of each transmission line
        df_line['LatMid'] = (df_line['LatImp'] + df_line['LatExp']) /2
        df_line['LonMid'] = (df_line['LonImp'] + df_line['LonExp']) /2
        
        
        ### 2.9 Process the gnr data
        
        # Make the pie charts based on technologies
        if gnr_var == 'TECH_TYPE':
        # Create horizontal table with sectors as columns
            display_column = 'TECH_TYPE'
            #Distinguish if has CCS or not for hydrogen
            G_to_tech_type = {
            'GNR_STEAM-REFORMING_E-70_Y-2020': 'SMR',
            'GNR_STEAM-REFORMING-CCS_E-70_Y-2020': 'SMR-CCS'
            }
            df_gnr['TECH_TYPE'] = df_gnr['G'].map(G_to_tech_type).fillna(df_gnr['TECH_TYPE'])

        # Make pie charts based on Fuels
        if gnr_var == 'FFF':
            display_column = 'FFF'
            #If you map fuels to change the fuel type.     
            # Define the dictionary to map old fuel names to new ones
            
            #First split wind to wind on and wind off based on the tech_type
            # create a dictionary to map the values of TECH_TYPE to the corresponding FFF names
            tech_type_to_fff = {"WIND-ON": "WIND-ON", "WIND-OFF": "WIND-OFF"}
            # use the map function to replace the values of FFF based on the values of TECH_TYPE
            df_gnr['FFF'] = df_gnr['TECH_TYPE'].map(tech_type_to_fff).fillna(df_gnr['FFF'])
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
            df_gnr['FFF'] = df_gnr['FFF'].map(fff_to_fuel).fillna(df_gnr['FFF'])
            
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
            df_gnr['FFF'] = df_gnr['G'].map(G_to_FFF).fillna(df_gnr['FFF'])   

        if gnr_exclude_H2Storage:
            df_gnr = df_gnr[df_gnr['TECH_TYPE'] != 'H2-STORAGE']

        # Check if there is some H2 import
        if df_gnr['FFF'].str.contains('IMPORT_H2').any():
            H2_import = True
        else :
            H2_import = False
        
        if gnr_exclude_Import_Cap_H2:
            df_gnr = df_gnr[df_gnr['FFF'] != 'IMPORT_H2']

        if gnr_exclude_ElectricStorage:
            df_gnr = df_gnr[df_gnr['TECH_TYPE'] != 'INTRASEASONAL-ELECT-STORAGE']
            df_gnr = df_gnr[df_gnr['TECH_TYPE'] != 'INTERSEASONAL-ELECT-STORAGE']
        
        # if gnr_exclude_Geothermal: # Do we have geothermia inside the model ?
        #     df_gnr_capacity = df_gnr_capacity[df_gnr_capacity['FFF'] != 'HEAT']   

        # Get the name for the legend
        if gnr_var == 'TECH_TYPE':
            df_tech_names = df_gnr['TECH_TYPE'].unique()
            df_tech_names_sorted = np.sort(df_tech_names)
            df_tech_names = df_tech_names_sorted
        if gnr_var == 'FFF':   
            df_tech_names = df_gnr['FFF'].unique()
            df_tech_names_sorted = np.sort(df_tech_names)
            df_tech_names = df_tech_names_sorted
        
        # Sum values per regions and tech/fuel type
        df_gnr = pd.DataFrame(df_gnr.groupby(['RRR', display_column])['Value'].sum().reset_index())

        # Merge the data frame to get the coordinates
        df_slack_gnr = df_gnr
        df_slack_gnr = pd.merge(df_slack_gnr, df_region[['Lat', 'Lon', 'RRR']], on = ['RRR'], how = 'right')

        # If they are some nan countries with no tech group filter outcome of merge
        df_slack_gnr = df_slack_gnr.dropna(subset=[display_column])

        #Keep the names of the regions
        RRRs = df_slack_gnr['RRR'].unique()

        # Some times some capacities are close to zero but with a negative make them o
        df_slack_gnr.loc[(df_slack_gnr['Value'] < 0) & (df_slack_gnr['Value'] > -0.0001), 'Value'] = 0
        
        # We want to get rid of very small values so that legend is not too big
        df_slack_gnr = df_slack_gnr.loc[df_slack_gnr['Value'] > gnr_show_min]
        
        # Take out the existing Tech/Fuel types for the legend
        if gnr_var == 'TECH_TYPE':
            gnr_existing_var = df_slack_gnr['TECH_TYPE'].unique() 
        elif gnr_var == 'FFF':
            gnr_existing_var = df_slack_gnr['FFF'].unique()
        
        # Only select Denmark data if coordinates of Denmark are selected
        if choosen_map_coordinates == 'DK' :
            df_slack_gnr = df_slack_gnr.loc[df_slack_gnr['RRR'].str.contains('DK')]
        
        ### 2.10 Process the background data
        
        if selected_bg != None:
            # Filter the data
            filters = selected_bg['filters']
            for i in range(len(filters)):
                df_bg = df_bg.loc[df_bg[filters[i][0]] == filters[i][1]].reset_index(drop = True)
            # Apply the transformation
            transformation = selected_bg['transformation']
            for i in range(len(transformation)):
                df_bg["Value"] = df_bg["Value"]*transformation[i]
            # Group by region RRR
            df_bg = pd.DataFrame(df_bg.groupby(['RRR'])['Value'].sum().reset_index())
            # Find the maximum over the region RRR
            bg_max = df_bg['Value'].max()

        ### 2.3 Group hub data -> Do we really use hub ?
        #Generation Capacities
        # if hub_display == True:
        #     df_capgen['Year'] = df_capgen['Year'].astype(int)
        #     # df_capgen = df_capgen.merge(df_unique, on = 'RRR', how = 'left', left_index = True).reset_index(drop = True) #Add coordinates of each region
        #     #poly
        #     df_capgen = df_capgen.merge(geo_file, on = geo_file_region_column, how = 'left' ).reset_index(drop = True) #Add coordinates of each region
        #     df_capgen = df_capgen.loc[df_capgen['Year'] == year] #Keep only data from year of interest
        #     df_hubcap = df_capgen.loc[df_capgen['G'].isin(hub_windgen),] #Keep only hub data 
        #     df_hubcap_agg = pd.DataFrame(df_hubcap.groupby(['Year', 'Country', 'RRR', 'Lat', 'Lon'])['Value'].sum().reset_index()) #Sum all capacities (of different wind turbines) at each location
        #     df_hubcap_agg['Radius'] = np.sqrt(df_hubcap_agg['Value'] * 1000 / hub_area / np.pi) # Create column of hub radius (in kilometres)

        #     if lines == 'Flow' or lines == 'CongestionFlow':
        #         #Merge all relevant hub info into one dataframe
        #         df_hubprod = pd.DataFrame(df_hubprod.groupby(['Year', 'Country', 'RRR'])['Value'].sum().reset_index()) #Sum all production (of different wind turbines) at each location
        #         df_hubprod.Value = df_hubprod.Value/1000
        #         df_hubprod.rename(columns = {'Value': 'prod_GWh'}, inplace = True)
        #         df_hub = pd.merge(df_hubcap_agg, df_hubprod[['RRR', 'prod_GWh']], on = 'RRR', how = 'left', left_index = True).reset_index(drop = True) 
        #         #Display a zero instead of NaN values (i.e. if there is no production in that hour, so df_hubprod row does not exist)
        #         df_hub.loc[df_hub.prod_GWh.isna() == True, 'prod_GWh'] = 0
        #     else: 
        #         df_hub = df_hubcap_agg.copy()
                


        ### 2.4 Prepare capacity dataframe -> Still useful ???
        # if AltGeo == 'NORD': # ???
        #     df_capacity.IRRRE = df_capacity.IRRRE.str.replace('_','')
        #     df_capacity.IRRRI = df_capacity.IRRRI.str.replace('_','')
        
        # # Check alternative regions in missing lat/lon -> Do we keep this ??
        # # idx = (df_capacity.loc[:,'LatExp'].isna()) | (df_capacity.loc[:,'LatImp'].isna())
        # if AltGeo != 'Balmorel': # For what ???
        #     for i,row in df_capacity.iterrows():
        #         for j in range(0,len(df_altreg)):
        #             if df_capacity.loc[i,'IRRRE'] == df_altreg.loc[j, AltGeoCol]:
        #                 df_capacity.loc[i,'LatExp'] = df_altreg.loc[j].geometry.centroid.y
        #                 df_capacity.loc[i,'LonExp'] = df_altreg.loc[j].geometry.centroid.x
        #             if df_capacity.loc[i,'IRRRI'] == df_altreg.loc[j, AltGeoCol]:
        #                 df_capacity.loc[i,'LatImp'] = df_altreg.loc[j].geometry.centroid.y
        #                 df_capacity.loc[i,'LonImp'] = df_altreg.loc[j].geometry.centroid.x


        # ### 2.6 Calculate Congestion -> Do later
        # if lines == 'CongestionFlow': #Skip this cell in case lines != 'CongestionFlow'
        #     df_flow = pd.merge(df_flow, df_capacity[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
        #     df_flow.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
        #     df_flow['Congestion'] = df_flow['Value'] / df_flow['Capacity'] * 100

        #     #Create color codes for congestion of lines
        #     df_flow['color'] = pd.cut(df_flow['Congestion'], bins = flowline_breaks, labels = flowline_color )


        ### ----------------------------- ###
        ###          3. Plotting          ###
        ### ----------------------------- ###

        ### 3.1 Create the map with the countries and regions
        
        if cartopy_installed:
            
            projection = ccrs.EqualEarth()
            
            # Get the coordinates of the graph
            xlim = dict_map_coordinates[choosen_map_coordinates][0]
            ylim = dict_map_coordinates[choosen_map_coordinates][1]

            # Calculate the aspect ratio based on the limits and set the figure size based on the aspect ratio
            aspect_ratio = (xlim[1] - xlim[0]) / (ylim[1] - ylim[0])
            fig_width = 12  # Adjust as needed
            fig_height = fig_width / aspect_ratio

            fig, ax = plt.subplots(figsize=(fig_width+10, fig_height), subplot_kw={"projection": projection}, dpi=100, facecolor=background_color)

            for R in layers_in:
                # Get the color of the country based on the background choice 
                if selected_bg != None: 
                    value = df_bg.loc[df_bg['RRR'] == R, 'Value'].values
                    if len(value) == 0 :
                        value = np.append(value, 0)
                    face_color = selected_bg['colormap'][0](value[0] / bg_max)
                else : 
                    face_color = regions_model_color
                # Get the geo file and plot it
                geo = gpd.read_file(layers_in[R])
                geo_artist = ax.add_geometries(geo.geometry, crs = projection,
                                               facecolor=[face_color], edgecolor='#46585d',
                                               linewidth=.2)
                geo_artist.set_zorder(1)
                
            if show_country_out :
                for R in layers_out:
                    geo = gpd.read_file(layers_out[R])
                    geo_artist = ax.add_geometries(geo.geometry, crs = projection,
                                                facecolor=[regions_ext_color], edgecolor='#46585d',
                                                linewidth=.2)
                    geo_artist.set_zorder(1)

        # else: # Should we keep the additional geography ???
        #     fig, ax = plt.subplots(figsize=(12, 12), dpi=100,
        #                         facecolor=background_color)
            
        #     # Adding shapefiles
        #     geo_file.plot(ax=ax, facecolor=[.6, .6, .6], edgecolor='grey', linewidth=.2)

        # ax.set_facecolor(background_color)


        ### 3.2 Adding transmission lines
        
        # A function for finding the nearest value in an array, useful for clustering
        def find_nearest(array, value):
            array = np.asarray(array)
            idx = (np.abs(array - value)).argmin()
            return array[idx]

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
        if lines in ['CongestionFlowYear','CongestionFlowTime']:
            line_max_value = df_line['Capacity'].max() # Find maximum value useful for linear and logarithmic scale
        else :
            line_max_value = df_line['Value'].max() # Find maximum value useful for linear and logarithmic scale
        line_width_constant = line_max_value/line_width_max
        for i,row in df_line.iterrows(): 
            y1 = df_line.loc[i,'LatExp']
            x1 =  df_line.loc[i,'LonExp']
            y2 = df_line.loc[i,'LatImp']
            x2 = df_line.loc[i,'LonImp']
            if lines in  ['CongestionFlowYear','CongestionFlowTime']:
                cap = df_line.loc[i,'Capacity']
            else :
                cap = df_line.loc[i,'Value']
                
            # Condition on coordinates
            if ((xlim[0] <= x1 <= xlim[1]) & (ylim[0] <= y1 <= ylim[1])) or ((xlim[0] <= x2 <= xlim[1]) & (ylim[0] <= y2 <= ylim[1])) :
                if not(np.isnan(cap)) : # Print an error message, if capacity is a NaN value
                    if cap >= line_show_min : # Only plot if big enough
                        if line_width_cat == 'cluster':
                            nearest = find_nearest(line_cluster_groups, cap) 
                            width = np.array(line_cluster_widths)[line_cluster_groups == nearest]
                        elif line_width_cat == 'linear':
                            width = cap/line_width_constant
                            if width < line_width_min:
                                width = line_width_min
                        elif line_width_cat == 'log':
                            normalized_cap = (cap-0)/(line_max_value-0)
                            log_scaled = np.log1p(normalized_cap) / np.log1p(1)
                            width = line_width_min + log_scaled * (line_width_max - line_width_min)
                            
                        # Colors if Congestion is plotted
                        if lines in ['CongestionFlowYear','CongestionFlowTime']:
                            colormap = plt.cm.Reds
                            line_final_color = colormap(df_line.loc[i,'Value']/100)
                        else :
                            line_final_color = line_color

                        # Plot the lines
                        l, = ax.plot([x1,x2], [y1,y2], color = line_final_color, linewidth = width, solid_capstyle='round', solid_joinstyle='round', zorder=1, alpha=line_opacity)
                        save_lines.append(l)
                        
                        # Plot the arrows on the flow
                        if line_flow_show :
                            if lines in ["FlowTime", "FlowYear", "CongestionFlowYear", "CongestionFlowTime"]:
                                if df_line.loc[i,'Value'] >= line_show_min:
                                    #Choose arrow style
                                    style = ArrowStyle('Fancy', head_length=4, head_width=4, tail_width=0.1)
                                    # Draw arrow
                                    arrow = FancyArrowPatch(posA=(x1+0.5*(x2-x1),y1+0.5*(y2-y1)), posB=(x1+0.501*(x2-x1),y1+0.501*(y2-y1)), arrowstyle=style, color='black')
                                    ax.add_patch(arrow)
                
                else:
                    pass
                    print("There's a NaN value in line\nIRRRE %s\nIRRRI %s"%(df_line.loc[i, 'IRRRE'], df_line.loc[i, 'IRRRI']))
                    
                # Add labels to lines   
                if line_label_show & (xlim[0] <= df_line.loc[i,'LonMid'] <= xlim[1]) & (ylim[0] <= df_line.loc[i,'LatMid'] <= ylim[1]) :
                    if df_line.loc[i,'Value'] >= line_label_min and df_line.loc[i,'Value'] >= line_show_min:
                            if lines in ['CongestionFlowYear','CongestionFlowTime']:
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
                        
        
        ### 3.4 Adding Pies
        
        if gnr_show:
            pies = []
            
            # Calculate the sum of the values by region and find the maximum value
            df_slack_gnr_sum = pd.DataFrame(df_slack_gnr.groupby(['RRR'])['Value'].sum().reset_index())
            pie_max_value = df_slack_gnr_sum['Value'].max()
            pie_radius_constant = pie_max_value/pie_radius_max
            
            for r in RRRs: # Find idx of the region
                idx = df_slack_gnr['RRR'] == r
                Lat = df_slack_gnr.loc[idx, 'Lat'].mean()
                Lon = df_slack_gnr.loc[idx, 'Lon'].mean()
                
                # Condition on coordinates
                if (xlim[0] <= Lon <= xlim[1]) & (ylim[0] <= Lat <= ylim[1]) :
                    CAPSUM = df_slack_gnr.loc[idx, 'Value'].sum() # Sum of capacities in the region for clustering
                    if CAPSUM > pie_show_min: # Only plot if big enough
                        if pie_radius_cat == 'cluster':
                            nearest = find_nearest(pie_cluster_groups, CAPSUM) 
                            radius = np.array(pie_cluster_radius)[pie_cluster_groups == nearest]
                            radius = radius[0]
                        elif pie_radius_cat == 'linear':
                            radius = CAPSUM/pie_radius_constant
                            if radius < pie_radius_min :
                                radius = pie_radius_min
                        elif pie_radius_cat == 'log':
                            normalized_cap = (CAPSUM-0)/(pie_max_value-0)
                            log_scaled = np.log1p(normalized_cap) / np.log1p(1)
                            radius = pie_radius_min + log_scaled * (pie_radius_max - pie_radius_min)

                        if gnr_var == 'TECH_TYPE':
                            colors_df = [gnr_tech_color.get(tech, 'gray') for tech in df_slack_gnr['TECH_TYPE'][idx]]
                        if gnr_var == 'FFF':
                            colors_df = [gnr_fuel_color.get(tech, 'gray') for tech in df_slack_gnr['FFF'][idx]]
                        p = ax.pie(df_slack_gnr['Value'][idx].values,
                                center=(Lon, Lat), radius=radius,
                                # If he does not find a match will return gray in the pie
                                colors = colors_df) 
                        # Save pie information
                        pies.append(p)
                    
        ### 3.5 Adding legend
        
        # Unit of the legend
        if lines in ['Capacity','CongestionFlowYear','CongestionFlowTime']:
            line_unit = 'GW'
        elif lines == 'FlowYear':
            line_unit = 'TWh'
        elif lines == 'FlowTime':
            line_unit = 'GWh'
        
        if legend and choosen_map_coordinates == 'EU' :         
            
            ### 3.5.1 Legend with pies
            
            if gnr_show:
                # Pie legend
                scatter_handles = []
                # To plot radius with scatter, we need to convert the radius to pixels and then to point
                for i in range(len(pie_cluster_groups)):
                    scatter = ax.scatter([], [], s=((pie_cluster_radius[i] * ax.get_window_extent().width / (xlim[1] - xlim[0])) * 72 / fig.dpi) ** 2, facecolor='grey', edgecolor='grey')
                    scatter_handles.append(scatter)

                if gnr == 'Capacity':
                    legend_labels = ['{} GW'.format(pie_cluster_groups[i]) for i in range(len(pie_cluster_groups))]
                elif gnr == 'Production':
                    legend_labels = ['{} TWh'.format(pie_cluster_groups[i]) for i in range(len(pie_cluster_groups))]
                
                # Legend with pies
                first_legend = ax.legend(scatter_handles, legend_labels, 
                                        scatterpoints=1,
                                        loc='upper left',
                                        ncol=4,
                                        fontsize=12,
                                        frameon=False, bbox_to_anchor=(0, 0.99))
                ax.add_artist(first_legend)  

                # Get the bounding box of the first legend
                bbox_first_legend = first_legend.get_window_extent().transformed(ax.transAxes.inverted())
                
                # Tech of fuel legend
                # The characteristics of legend depend on the commodity and the variable
                if gnr_var == 'TECH_TYPE':
                    dict_gnr_color = gnr_tech_color
                    ncol = 2
                elif gnr_var == 'FFF':
                    dict_gnr_color = gnr_fuel_color
                    ncol = 3
                            
                # Calculate the position for the second legend based on the bounding box of the first one
                pos_tech = (bbox_first_legend.x0, bbox_first_legend.y0 - 0.01)  # Adjust the vertical position as needed
            
                # Plot the legend for technologies
                patches = [mpatches.Patch(color=dict_gnr_color[tech], label=tech) for tech in gnr_existing_var]
                second_legend = ax.legend(handles=patches, loc='upper left', ncol = ncol, frameon=False,
                                        mode='expnad', bbox_to_anchor=pos_tech)    
                ax.add_artist(second_legend)
            
            
            ### 3.5.2 Legend with lines
            
            # Get the bounding box of the first legend
            bbox_second_legend = second_legend.get_window_extent().transformed(ax.transAxes.inverted())
            pos_line = (bbox_second_legend.x0, bbox_second_legend.y0 - 0.0)  # Adjust the vertical position as needed
                
            if commodity == 'Electricity':
                subs = 'el'
            elif commodity == 'Hydrogen':
                subs = 'H2'
            # Create lines for legend
            lines_legend = []
            string = []
            for i in range(len(line_cluster_groups)):
                # Modify line_cluster_widths for linear and log scale
                if line_width_cat == 'linear':
                    line_cluster_widths[i] = line_cluster_groups[i]/line_width_constant
                    if line_cluster_widths[i] < line_width_min:
                                line_cluster_widths[i] = line_width_min
                elif line_width_cat == 'log':
                    normalized_cap = (line_cluster_groups[i]-0)/(line_max_value-0)
                    log_scaled = np.log1p(normalized_cap) / np.log1p(1)
                    width = line_width_min + log_scaled * (line_width_max - line_width_min)
                    line_cluster_widths[i] = width
                # The patch
                lines_legend.append(Line2D([0], [0], linewidth=line_cluster_widths[i],
                                    color=line_color))
                # The text
                ave = line_cluster_groups[i]
                string.append('%0.1f %s$_\mathrm{%s}$'%(ave, line_unit, subs))
            ax.legend(lines_legend, string, frameon=False, loc='upper left', bbox_to_anchor=pos_line)
                        
            # if commodity == 'Hydrogen':
            #     subs = 'H2'
            #     # Create lines for legend
            #     lines_legend = []
            #     string = []
            #     for i in range(len(line_cluster_groups)):
            #         # The patch
            #         lines_legend.append(Line2D([0], [0], linewidth=line_cluster_widths[i],
            #                             color=line_color))
            #         # The text
            #         if i == 0:
            #             ave = line_cluster_groups[i]
            #             string.append('%0.1f %s$_\mathrm{%s}$'%(ave, line_unit, subs))
            #         elif i == len(line_cluster_groups)-1:
            #             ave = line_cluster_groups[i]
            #             string.append('%0.1f %s$_\mathrm{%s}$'%(ave, line_unit, subs))
            #         else:
            #             ave0 = line_cluster_groups[i]
            #             string.append('%0.1f %s$_\mathrm{%s}$'%(ave0, line_unit, subs))
                
            #     ax.legend(lines_legend, string,frameon=False, loc='upper left', bbox_to_anchor=(0, 0.85))    
                
            
            ### 3.5.3 Congestion legend
            
            if lines in ['CongestionFlowYear','CongestionFlowTime']:
                # Create the inset for the color bar
                cbar_ax = inset_axes(
                    ax,
                    width="3%",  # Width of the color bar
                    height="80%",  # Height of the color bar
                    loc="center right",  # Position the color bar on the right
                    borderpad=-3,  # Padding between the axis and color bar
                )
                # Normalize and create a color bar
                norm = mcolors.Normalize(vmin=0, vmax=100)
                cbar = fig.colorbar(cm.ScalarMappable(norm=norm, cmap="Reds"), cax=cbar_ax)
                if lines == 'CongestionFlowYear':
                    cbar.set_label("Line Utilization [%]") # Add label
                elif lines == 'CongestionFlowTime':
                    cbar.set_label("Line Congestion [%]")  # Add label
                    
            ### 3.5.3 Background legend
            
            if selected_bg != None:
                # Ticks label
                bg_upper = int(np.ceil(bg_max))  # Round up 
                ticks = list(range(0,bg_upper,2))
                # Create the inset for the color bar
                cbar_ax = inset_axes(
                    ax,
                    width="3%",  # Width of the color bar
                    height="80%",  # Height of the color bar
                    loc="center left",  # Position the color bar on the right
                    borderpad=-3,  # Padding between the axis and color bar
                )
                # Normalize and create a color bar
                norm = mcolors.Normalize(vmin=0, vmax=bg_max)
                cbar = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=selected_bg['colormap'][1]), cax=cbar_ax)
                cbar.ax.yaxis.set_label_position('left')
                cbar.ax.yaxis.set_ticks_position('left')
                cbar.ax.yaxis.set_ticks(ticks)
                cbar.set_label(f"{bg} [{selected_bg['unit']}]") # Add label
        
        
        ### 3.6 Limits of graph
        
        # Set limit always after pies because it brakes the graph
        ax.set_xlim(xlim[0],xlim[1])      
        ax.set_ylim(ylim[0],ylim[1])
        ax.set_aspect('equal', anchor='E')  # Ensure the aspect ratio is equal
            
        # Black lining around the graph
        ax.plot([xlim[0],xlim[1]], [ylim[0],ylim[0]], color = 'black', linewidth = 2, zorder=1)
        ax.plot([xlim[0],xlim[1]], [ylim[1],ylim[1]], color = 'black', linewidth = 1, zorder=1)
        ax.plot([xlim[0],xlim[0]], [ylim[0],ylim[1]], color = 'black', linewidth = 1, zorder=1)
        ax.plot([xlim[1],xlim[1]], [ylim[0],ylim[1]], color = 'black', linewidth = 2, zorder=1)


        ### 3.7 Graph title

        if lines == 'Capacity':
            ax.set_title(' - '.join((SCENARIO, str(year), commodity + ' Transmission Capacity' + f' [{line_unit}]')))
        elif lines == 'FlowYear':
            ax.set_title(' - '.join((SCENARIO, str(year), commodity + ' Transmission Flow' + f' [{line_unit}]')))
        elif lines == 'FlowTime':
            ax.set_title(' - '.join((SCENARIO, str(year), S, T, commodity + ' Transmission Flow' + f' [{line_unit}]')))
        elif lines == 'CongestionFlowYear':
            ax.set_title(' - '.join((SCENARIO, str(year), commodity + ' Line Utilization')))
        elif lines == 'CongestionFlowTime':
            ax.set_title(' - '.join((SCENARIO, str(year), S, T, commodity + ' Line Congestion')))
        
        
        
        # ### 3.3 Adding HUB Capacities -> Should we keep this ???
        # if hub_display:
        #     idx = df_hubcap_agg['Year'] == year
        #     temp = df_hubcap_agg[idx]
        #     for i,row in temp.iterrows():
                
        #         markersize = row['Value']
                
        #         ax.plot(row['Lon'], row['Lat'], 'o', color=[.8, .8, 1], 
        #                 markersize=markersize, zorder=-1)
        
        ##% 3.4 Save map
        # plt.savefig("network_MUNI_2DE_NoS_MoreFLH_noBio_LSNOstevns.svg", bbox_inches="tight", transparent=True)
        # plt.savefig("Output/balmorelmap.png", bbox_inches="tight", transparent=True)
        # plt.savefig("Output/balmorelmap.pdf", bbox_inches="tight", transparent=True)

        # print('\nSuccesful execution of MapsBalmorel.py')
        
        plt.show()
        
        return fig, ax
            
    else:
        print("\nDidn't find a scenario in the paths given")
      
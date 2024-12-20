# In[ ]:

#!/usr/bin/env Balmorel
import math
import geopandas as gpd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
# import xarray as xr
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from matplotlib.patches import ArrowStyle
import matplotlib.patches as mpatches
from matplotlib.legend_handler import HandlerPatch
from sklearn.cluster import KMeans
#from matplotlib.colors import to_rgb


from pathlib import Path
import sys
import os
import glob

#choose correct version of Gams
sys.path.append(r'C:\GAMS\36\apifiles\Python\api_38')
sys.path.append(r'C:\GAMS\36\apifiles\Python\gams')

from gams import GamsWorkspace

# # 1 Preparations

# ### 1.1 Set Options

# In[ ]:

### Set options here.
#Structural options     
filetype_input = 'gdx' #Choose input file type: 'gdx' or 'csv' 
gams_dir = 'C:/GAMS/39' #Only required if filetype_input == 'gdx'
market = 'Investment' #Choose from ['Balancing', 'DayAhead', 'FullYear', 'Investment']
COMMODITY = 'H2' #Choose from: ['Electricity', 'H2', 'Other']. Add to csv-files name (only relevant if filetype_input == 'csv'). If 'Other': go to cell 1.4.0.
SCENARIO = 'DemandShift60%_GH2E_new' #Add scenario to read file name
Import_Hydrogen = True #if the addone for import is on then use this option
YEAR = 'all' #Add year to read file name (e.g. '2025', '2035', 'full')
SUBSET = 'all' #Add subset to read file name (e.g. 'full')
year = 2050 #Year to be displayed
LINES = 'Capacity' #Choose from: ['Capacity', 'Flow', 'CongestionFlow']. For 'CongestionFlow', exo_end automatically switches to 'Total'.
exo_end = 'Total' # Choose from ['Endogenous', 'Exogenous', 'Total']. For 'CongestionFlow', exo_end automatically switches to 'Total'.
S = 'S02' #Season 
T = 'T073' #Hour 

   
# hubs
hub_display = True
hub_size = 100.6
hub_decimals = 10 #Number of decimals shown for hub capacities
background_hubsize = True #Displaying the true size of the hub as a circle on the map.
hub_area = 100.8 #MW / km^2, background hub size on map. 
hub_area_opacity = 10.7 #Opacity of background hub size. 


#Visual options transmission lines hydrogen or electricity
label_min = 0.01 #Minimum transmission capacity (GW) shown on map in text
font_line = 12 #Font size of transmission line labels
font_hub = 12 #Font size of hub labels
font_region = 10 #Font size of region labels
line_decimals = 1 #Number of decimals shown for line capacities
line_width_constant = 3 #Constant related to thickness of lines: the higher the number, the narrower the lines will be
flowline_breaks = [0, 40, 94.999, 100] #Breaks for different congestion categories
legend_values = ['Fully congested', '40-95% congested', '< 50% congested'] #Values displayed in legend
cat = 'linear' # 'linear' = Capacities are scaled linearly, 'cluster' = capacities are clustered in groups, small cluster c!
show_flow_arrows = 'NO' #'YES' or 'NO', net flow arrow, fix the arrows can be quite big
show_label = 'NO'   # 'YES' or 'NO'

if COMMODITY == 'Electricity' :
    cluster_groups = [1, 5, 10, 15] # The capacity groupings if cat is 'cluster'
    cluster_widths = [1, 5, 10, 15] # The widths for the corresponding capacity group (has to be same size as cluster_groups)  
elif COMMODITY == 'H2':
    cluster_groups = [1, 5, 10, 20] # The capacity groupings if cat is 'cluster'
    cluster_widths = [1, 4, 8, 16] # The widths for the corresponding capacity group (has to be same size as cluster_groups)  
        

#Scale up the width in case of linear the legend
if cat == 'linear':
    cluster_widths = [(1/line_width_constant) * i for i in cluster_widths]
    

#Pie Options
GNR_Show = True #map capacities or production in a pie chart
Show_pie = 'capacity' #You can choose 'production' (GWh) or 'capacity' (GW)
cat_pie = 'cluster' # 'linear' = Capacities are scaled linearly, 'cluster' = capacities are clustered in groups, small cluster c!
pie_width_constant = 0.04 # constant factored on sum of generation capacities, if linear cluster choosen
exclude_Import_Cap_H2 = True #take out the capacities because of the IMPORT_H2 from oher countreis
exclude_H2Storage = True  #do not plot the capacities of the H2 storage
exclude_ElectricStorage = True  #do not plot the production of Electric storag, only works with Show pie production
exclude_Geothermal = True #do not plot the production of Geothermal, only works with Show pie production
plot_category = 'TECH_TYPE' #use 'FFF' or 'TECH_TYPE'
#make clusters for pies
if Show_pie == 'production':
    if COMMODITY == 'Electricity' :
        cluster_groups_pie = [10,  15,    20,   30,  40,   50,  75,   100, 125, 150, 175,  200, 225,  250, 300, 350,  400, 450, 500, 550, 600, 650, 700,  750,  800,  850,900,  950] #TWh
        cluster_radius_pie = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4,  0.45, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.20,  1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9,  2,  2.1, 2.2,  2.3,  2.4]
    elif COMMODITY == 'H2':
        cluster_groups_pie = [10,   20,  50,  75,   100, 150, 175, 200,  250, 300,  400, 500, 650, 800, 950] #TWh
        cluster_radius_pie = [0.1, 0.1, 0.2, 0.3,  0.4, 0.5, 0.6, 0.7,  1.0, 1.3,  1.6, 1.9, 2.1, 2.4, 2.7]
        
if Show_pie == 'capacity':
    if COMMODITY == 'Electricity' :
        cluster_groups_pie = [2,    5,   10,  20,   30,  40,  50,  80,   100, 200,  300, 400, 450, 500] #GW
        cluster_radius_pie = [0.08, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.8,  1.0, 1.3,  1.5, 1.6, 1.8, 2.0]
    elif COMMODITY == 'H2':
        cluster_groups_pie = [0.5,  1,   2,   3.5, 4.5,  6,   7.5,  10, 12.5, 15,  17.5,   20, 22.5,  25, 27.5,  30,  35,  40,  45,  50, 55,  60,   65,  70, 80, 90, 100, 110] #GW
        cluster_radius_pie = [0.1, 0.15, 0.2, 0.3, 0.35, 0.4, 0.5,  0.6, 0.65, 0.7, 0.75,  0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2, 2.2, 2.4,2.6]     
    
    
    
"""
    elif COMMODITY == 'H2':
        cluster_groups_pie = [0.5,  1,   2,   3.5,  5, 6,  7.5,  10,   15,   20,   30,  40,   50,  60, 70, 80, 90,  100] #GW
        cluster_radius_pie = [0.1, 0.15, 0.2, 0.3,  0.4, 0.45, 0.5,  0.6,  0.7,  0.8,  1.1,   1.4,  1.5, 1.7, 1,8, 1.9, 2, 2.1] 
    
    
    
#Expirimental  so to make the clustering linear or log yet it provides a false pictures.   
    elif COMMODITY == 'H2':
        start = 1   # Starting value
        end = 110     # Ending value
        step = 2    # Step size
        cluster_groups_pie = []
        # Use a loop to generate the array
        for i in range(int((end-start)/step)+1):
            value = start + i * step
            cluster_groups_pie.append(value)

#Scale all the arrays to create the 
scale_factor = 0.025
#for linear scalling
radii = [r*scale_factor for r in cluster_groups_pie]  
#for log scaling of radius for pie chart
#radii = [ math.log10(r) for r in cluster_groups_pie]  
cluster_radius_pie = radii
"""

#colors
background_color = 'white'
regions_ext_color = 'lightgrey'
regions_model_color = 'grey'
region_text = 'black'
capline_color = 'orange' #you can use orange or others green
flowline_color = ['#3D9200', '#feb24c','#960028']
line_text = 'black'
hub_color = 'lightblue'
hub_background_color = 'lightblue'
hub_text = 'black'
#net_colour = 'green' # Colour of network

#colour for network
if COMMODITY == 'Electricity' :
    net_colour = '#8fbc8f'
elif COMMODITY == 'H2' : 
    net_colour = '#13EAC9'

# ### 1.2 Import Packages

# In[ ]:


# from pathlib import Path
import sys
from IPython.display import HTML, display


sys.path.append(r'C:\GAMS\36\apifiles\Python\api_38')
sys.path.append(r'C:\GAMS\36\apifiles\Python\gams')

# from gams import GamsWorkspace


display(HTML(data="""
<style>
    div#notebook-container    { width: 95%; }
    div#menubar-container     { width: 65%; }
    div#maintoolbar-container { width: 99%; }
</style>
"""))



# In[ ]:


def read_paramenter_from_gdx(ws,gdx_name,parameter_name,**read_options):
     
     for item in read_options.items():
         if item[0]=="field":
                     field=item[1]

     
     db = ws.add_database_from_gdx(gdx_name)
     
     if "field" in locals() :
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
             
     return par , db[parameter_name].get_domains_as_strings()
 


def dataframe_from_gdx(gdx_name,parameter_name,**read_options):
     
     ws = GamsWorkspace(os.getcwd(),)


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



# In[ ]:
# ### 1.3 Read geographic files

project_dir = Path('.\input')

#Load coordinates files 
df_unique = pd.read_csv(project_dir/'geo_files/coordinates_RRR.csv')
df_region = df_unique.loc[df_unique['Type'] == 'region', ]
df_bypass = pd.read_csv(project_dir/'geo_files/bypass_lines.csv') # coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions

#if import hydrogen is activate
if Import_Hydrogen:
    if COMMODITY == 'H2':
        df_hydrogen_lines_outside = pd.read_csv(project_dir/'geo_files/hydrogen_third_nations.csv') # coordinates of 'hooks' in indirect lines, to avoid going trespassing third regions

    

#Define names of geojson and shapefile layers
r_in = list(df_unique.loc[(df_unique['Display'] == 1) & (df_unique['Type'] == 'region'), 'RRR'])
r_out = list(df_unique.loc[(df_unique['Display'] == 0) & (df_unique['Type'] == 'region'), 'RRR'])

layers_in = {region: '' for region in r_in}
layers_out = {region: '' for region in r_out}

#Create dictionaries with layer names for each region; if both a shapefile and geojson file are available for one region, the geojson file is used. 
for region in r_in:
    layers_in[region] = glob.glob(f'{project_dir}/geo_files/geojson_files/'+ region + '.geojson')
    if bool(layers_in[region]) == False:
        layers_in[region] = glob.glob(f'{project_dir}/geo_files/shapefiles/'+ region + '.shp')
for region in r_out:
    layers_out[region] = glob.glob(f'{project_dir}/geo_files/geojson_files/'+ region + '.geojson')
    if bool(layers_out[region]) == False:
        layers_out[region] = glob.glob(f'{project_dir}/geo_files/shapefiles/'+ region + '.shp')

for region in layers_in:
    layers_in[region] = str(layers_in[region])[2:-2] #Remove brackets from file names
for region in layers_out:
    layers_out[region] = str(layers_out[region])[2:-2] #Remove brackets from file names

    
#Convert shapefiles to geojson files  
for region in layers_out:
    if layers_out[region][-4:] == '.shp':
        gpd.read_file(layers_out[region]).to_file(f'{project_dir}/geo_files/geojson_files/'+ region + '.geojson', driver='GeoJSON')
        layers_out[region] = layers_out[region].replace('shapefiles', 'geojson_files').replace('.shp', '.geojson')


# # 1.4 Read run-specific files

# ##### 1.4.0 If COMMODITY == 'Other': define variables or file names

# In[ ]:


if COMMODITY == 'Other':
    if filetype_input == 'gdx':
        var_list = ['G_CAP_YCRAF', 'XH2_CAP_YCR', 'XH2_FLOW_YCRST', 'PRO_YCRAGFST'] #Fill in variables to read, e.g. ['G_CAP_YCRAF', 'X{COMMODITY}_CAP_YCR', 'X{COMMODITY}_FLOW_YCRST', 'PRO_YCRAGST']
    if filetype_input == 'csv':
        flow_file = 'FlowH2Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv' #Fill in flow file name if applicable, e.g. 'Flow{COMMODITY}Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        transcap_file = 'CapacityH2Transmission_' + SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv' #Fill in transmission capacity file name, e.g. 'Capacity{COMMODITY}Transmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv' 


# ### 1.4A - GDX Inputs

# ##### 1.4A.1 Function: reading gdx-files

# In[ ]:


if filetype_input == 'gdx':
    def df_creation(gdx_file, varname):
        df = pd.DataFrame()
        if '_' in gdx_file:
                # if yes: extract scenario name from gdx filename
            scenario = gdx_file.split('_', 3)[-3]
            year = gdx_file.split('_', 3)[-2]
            subset = gdx_file.split('_', 3)[-1][:-4]
            market = gdx_file.split('\\', 1)[0].split('/',3)[-1]
        else:
               # if no: use nan instead
            scenario = 'nan'

        # create empty temporary dataframe and load the gdx data into it
        temp = pd.DataFrame()
        # temp = gdxpds.to_dataframe(gdx_file, varname, gams_dir=gams_dir,
        #                        old_interface=False)
        
        temp=dataframe_from_gdx(gdx_file,varname)

        # add a scenario column with the scenario name of the current iteration
        temp['Scenario'] = scenario
        temp['Market']  = market
        temp['run'] = scenario + '_' + year + '_' + subset

        # rearrange the columns' order
        cols = list(temp.columns)
        cols = [cols[-1]] + cols[:-1]
        temp = temp[cols]

        # concatenate the temporary dataframe to the preceeding data
        df = pd.concat([df, temp], sort=False)
        return df


# ##### 1.4A.2 - Define var_list

# In[ ]:


if filetype_input == 'gdx':
    if COMMODITY == 'Electricity':
        var_list = []
        if LINES == 'Capacity' or LINES == 'CongestionFlow' or LINES == 'Flow': 
            var_list = var_list + ['G_CAP_YCRAF', 'X_CAP_YCR', 'X_FLOW_YCR','PRO_YCRAGF']
        if LINES == 'Flow' or LINES == 'CongestionFlow':
            var_list = var_list + ['X_FLOW_YCRST']
        if hub_display == True:
            var_list = var_list + ['PRO_YCRAGFST']
    if COMMODITY == 'H2':
        var_list = []
        if LINES == 'Capacity' or LINES == 'CongestionFlow' or LINES == 'Flow': 
            var_list = var_list + ['G_CAP_YCRAF', 'XH2_CAP_YCR','XH2_FLOW_YCR','PRO_YCRAGF']
        if LINES == 'Flow' or LINES == 'CongestionFlow':
            var_list = var_list + ['XH2_FLOW_YCRST']
        if hub_display == True:
            var_list = var_list + ['PRO_YCRAGFST']


# ##### 1.4A.3 - Use function to read inputs

# In[ ]:


if filetype_input == 'gdx':
    runs = list()
    gdx_file_list = list()

    # directory to the input gdx file(s)
    #gdx_file_list = gdx_file_list + glob.glob('./input/results/'+ market + '/*.gdx')
    
    gdx_file =  glob.glob('./input/results/'+ market + '\\MainResults_' + SCENARIO + '_'  + YEAR + '_' + SUBSET + '.gdx')
    gdx_file = gdx_file[0]

    all_df = {varname: df for varname, df in zip(var_list,var_list)}


    for varname, df in zip(var_list, var_list):
        all_df[varname] = df_creation(gdx_file, varname)
        if all_df[varname]['run'][0] not in runs:
            runs.append(all_df[varname]['run'][0])

    #run_dict = dict(zip(gdx_file_list, runs) )
    #all_df = dict((run_dict[key], value) for (key, value) in all_df.items())
    
    #Transmission capacity data
    if LINES == 'Capacity' or LINES == 'CongestionFlow'  or LINES == 'Flow':
        if COMMODITY == 'Electricity':
            df_capacity = all_df['X_CAP_YCR']
            df_flow = all_df['X_FLOW_YCR']
            if Show_pie == 'capacity':
                df_GNR_capacity = all_df['G_CAP_YCRAF']
                df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['COMMODITY'] == 'ELECTRICITY']
            else:
                df_GNR_capacity = all_df['PRO_YCRAGF']
                df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['COMMODITY'] == 'ELECTRICITY']

        if COMMODITY == 'H2':
            df_capacity = all_df['XH2_CAP_YCR']
            df_flow = all_df['XH2_FLOW_YCR']
            if Show_pie == 'capacity':
                df_GNR_capacity = all_df['G_CAP_YCRAF']
                df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['COMMODITY'] == 'HYDROGEN']
            else:
                df_GNR_capacity = all_df['PRO_YCRAGF']
                df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['COMMODITY'] == 'HYDROGEN']
        if COMMODITY == 'Other':
            df_capacity = all_df[var_list[1]]

    #Transmission flow data
    if LINES == 'Flow' or LINES == 'CongestionFlow' : 
        if COMMODITY == 'Electricity':
            df_flow = all_df['X_FLOW_YCRST']
        if COMMODITY == 'H2':
            df_flow = all_df['XH2_FLOW_YCRST']
    if COMMODITY == 'Other':
        if LINES == 'Flow':
            df_flow = all_df[var_list[1]]
        if LINES == 'CongestionFlow':
            df_flow = all_df[var_list[2]]


# ##### 1.4A.4 - Hub data

# In[ ]:


if filetype_input == 'gdx' and hub_display == True:
    hub_windgen = (pd.read_csv(project_dir/'geo_files/hub_technologies.csv', sep = ',', quotechar = '"').hub_name) 
    df_capgen = all_df['G_CAP_YCRAF']
    if LINES == 'Flow' or LINES == 'CongestionFlow':
        df_hubprod = all_df['PRO_YCRAGFST']
        df_hubprod['Y'] = df_hubprod['Y'].astype(int)
        df_hubprod = df_hubprod.loc[(df_hubprod['G'].isin(hub_windgen)) & (df_hubprod['TECH_TYPE'] == 'WIND-OFF') &                                     (df_hubprod['Y']==year) & (df_hubprod['SSS'] == S) & (df_hubprod['TTT']==T), ]


# ### 1.4B1 - Read CSV files

# In[ ]:


map_name = 'Transmission' + COMMODITY + '_' + LINES + '_' + str(year) + '_Map.html'
if filetype_input == 'csv':
    generation_file = 'CapacityGeneration_'+  SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
    if COMMODITY == 'Electricity':
        flow_file = 'FlowElectricityHourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        transcap_file = 'CapacityElectricityTransmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv'
    if COMMODITY == 'H2':
        flow_file = 'FlowH2Hourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        transcap_file = 'CapacityH2Transmission_'+ SCENARIO + '_' + YEAR + '_'+ SUBSET + '.csv'
     
    #Transmission capacity data
    df_capacity = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(transcap_file), sep = ',', quotechar = '"') 
    #Transmission flow data
    if LINES == 'Flow' or LINES == 'CongestionFlow':
        df_flow = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(flow_file), sep = ',', quotechar = '"')

    if hub_display == True:
        prod_file = 'ProductionHourly_'+ SCENARIO + '_' + YEAR + '_' + SUBSET + '.csv'
        hub_windgen = (pd.read_csv(project_dir/'geo_files/hub_technologies.csv', sep = ',', quotechar = '"').hub_name) 
        #Generation capacity data
        df_capgen = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(generation_file), sep = ',', quotechar = '"') 
        if LINES == 'Flow' or LINES == 'CongestionFlow':
        #Hub production data
            df_hubprod = pd.read_csv(str(project_dir) + '/results/' + str(market) + '/' + str(prod_file), sep = ',', quotechar = '"') 
            df_hubprod = df_hubprod.loc[(df_hubprod['G'].isin(hub_windgen)) & (df_hubprod['TECH_TYPE'] == 'WIND-OFF') &                                         (df_hubprod['Y']==year) & (df_hubprod['SSS'] == S) & (df_hubprod['TTT']==T), ]


# ### 1.4B2 - Calibrate column names

# In[ ]:


column_dict = {'Val':'Value', 'Y':'Year', 'C':'Country'}
if LINES == 'Capacity' or LINES == 'CongestionFlow':
    df_capacity = df_capacity.rename(columns = column_dict)
    df_flow = df_flow.rename(columns = column_dict)
if LINES == 'Flow' or LINES == 'CongestionFlow':
    df_flow = df_flow.rename(columns = column_dict)
if hub_display == True:
    df_capgen = df_capgen.rename(columns = column_dict)
    if LINES == 'Flow' or LINES == 'CongestionFlow': 
            df_hubprod = df_hubprod.rename(columns = column_dict)


    
# # 2 Processing of dataframes

# ### 2.1 Replace "EPS" with 0

# In[ ]:


#Replace possible "Eps" with 0
df_capacity.Value=df_capacity.Value.replace('Eps', 0)
df_capacity.Value=pd.to_numeric(df_capacity.Value)
df_flow.Value=df_flow.Value.replace('Eps', 0)
df_flow.Value=pd.to_numeric(df_flow.Value)
if LINES == 'Flow' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Capacity'
    df_flow.Value=df_flow.Value.replace('Eps', 0)
    df_flow.Value=pd.to_numeric(df_flow.Value)
if hub_display == True:
    df_capgen.Value=df_capgen.Value.replace('Eps', 0)
    df_capgen.Value=pd.to_numeric(df_capgen.Value)
    if LINES == 'Flow' or LINES == 'CongestionFlow':
        df_hubprod.Value=df_hubprod.Value.replace('Eps', 0)
        df_hubprod.Value=pd.to_numeric(df_hubprod.Value)


# In[ ]: 
### 2.2 Add Coordinates + Select Time + Convert Units


#Flows
if LINES == 'Flow' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Capacity'
    df_flow['Year'] = df_flow['Year'].astype(int)
    #Keep only data from moment of interest
    df_flow = df_flow.loc[df_flow['Year'] == year] 
    df_flow = df_flow.loc[df_flow['SSS'] == S,]
    df_flow = df_flow.loc[df_flow['TTT'] == T, ]
    for i,row in df_flow.iterrows():
        for j in range(0,len(df_unique)):
            if df_flow.loc[i,'IRRRE'] == df_unique.loc[j, 'RRR']:
                df_flow.loc[i,'LatExp'] = df_unique.loc[j, 'Lat']
                df_flow.loc[i,'LonExp'] = df_unique.loc[j, 'Lon']
            if df_flow.loc[i,'IRRRI'] == df_unique.loc[j, 'RRR']:
                df_flow.loc[i,'LatImp'] = df_unique.loc[j, 'Lat']
                df_flow.loc[i,'LonImp'] = df_unique.loc[j, 'Lon']

    #Convert flow from MWh to GWh
    df_flow['Value'] = df_flow['Value'] / 1000
    df_flow = df_flow.reset_index(drop = True)
    if len(df_flow) == 0:
        print("Error: Timestep not in data; check year, S and T.")
        sys.exit()


# In[ ]:
# ### 2.3 Group hub data



#Generation Capacities
if hub_display == True:
    df_capgen['Year'] = df_capgen['Year'].astype(int)
    # df_capgen = df_capgen.merge(df_unique, on = 'RRR', how = 'left', left_index = True).reset_index(drop = True) #Add coordinates of each region
    #poly
    df_capgen = df_capgen.merge(df_unique, on = 'RRR', how = 'left' ).reset_index(drop = True) #Add coordinates of each region
    df_capgen = df_capgen.loc[df_capgen['Year'] == year] #Keep only data from year of interest
    df_hubcap = df_capgen.loc[df_capgen['G'].isin(hub_windgen),] #Keep only hub data 
    df_hubcap_agg = pd.DataFrame(df_hubcap.groupby(['Year', 'Country', 'RRR', 'Lat', 'Lon'])['Value'].sum().reset_index()) #Sum all capacities (of different wind turbines) at each location
    df_hubcap_agg['Radius'] = np.sqrt(df_hubcap_agg['Value'] * 1000 / hub_area / np.pi) # Create column of hub radius (in kilometres)

    if LINES == 'Flow' or LINES == 'CongestionFlow':
        #Merge all relevant hub info into one dataframe
        df_hubprod = pd.DataFrame(df_hubprod.groupby(['Year', 'Country', 'RRR'])['Value'].sum().reset_index()) #Sum all production (of different wind turbines) at each location
        df_hubprod.Value = df_hubprod.Value/1000
        df_hubprod.rename(columns = {'Value': 'prod_GWh'}, inplace = True)
        df_hub = pd.merge(df_hubcap_agg, df_hubprod[['RRR', 'prod_GWh']], on = 'RRR', how = 'left', left_index = True).reset_index(drop = True) 
        #Display a zero instead of NaN values (i.e. if there is no production in that hour, so df_hubprod row does not exist)
        df_hub.loc[df_hub.prod_GWh.isna() == True, 'prod_GWh'] = 0
    else: 
        df_hub = df_hubcap_agg.copy()
        


# In[ ]:
# ### 2.4 Prepare capacity dataframe



#Transmission Capacities
if LINES == 'Capacity' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Flow'
    df_capacity['Year'] = df_capacity['Year'].astype(int)
    df_flow['Year'] = df_flow['Year'].astype(int)
    df_capacity = df_capacity.loc[df_capacity['Year'] == year, ].reset_index(drop = True) #Keep only data from year of interest
    df_flow = df_flow.loc[df_flow['Year'] == year, ].reset_index(drop = True) #Keep only data from year of interest
    if exo_end == 'Total' or LINES == 'CongestionFlow':
        col_keep = list(np.delete(np.array(df_capacity.columns),np.where((df_capacity.columns == 'VARIABLE_CATEGORY') |                                     (df_capacity.columns == 'Value')) )) #Create list with all columns except 'Variable_Category' and 'Value'
        df_capacity = pd.DataFrame(df_capacity.groupby(col_keep)['Value'].sum().reset_index() )#Sum exogenous and endogenous capacity for each region
    if exo_end == 'Endogenous' and LINES != 'CongestionFlow':
        df_capacity = df_capacity.loc[df_capacity['VARIABLE_CATEGORY'] == 'ENDOGENOUS', ]
    if exo_end == 'Exogenous' and LINES != 'CongestionFlow':
        df_capacity = df_capacity.loc[df_capacity['VARIABLE_CATEGORY'] == 'EXOGENOUS', ]

    for i,row in df_capacity.iterrows():
        for j in range(0,len(df_unique)):
            if df_capacity.loc[i,'IRRRE'] == df_unique.loc[j, 'RRR']:
                df_capacity.loc[i,'LatExp'] = df_unique.loc[j, 'Lat']
                df_flow.loc[i,'LatExp'] = df_unique.loc[j, 'Lat']
                df_capacity.loc[i,'LonExp'] = df_unique.loc[j, 'Lon']
                df_flow.loc[i,'LonExp'] = df_unique.loc[j, 'Lon']
            if df_capacity.loc[i,'IRRRI'] == df_unique.loc[j, 'RRR']:
                df_capacity.loc[i,'LatImp'] = df_unique.loc[j, 'Lat']
                df_flow.loc[i,'LatImp'] = df_unique.loc[j, 'Lat']
                df_capacity.loc[i,'LonImp'] = df_unique.loc[j, 'Lon']
                df_flow.loc[i,'LonImp'] = df_unique.loc[j, 'Lon']
    if len(df_capacity) == 0:
        print("Error: No capacity found. Check year and exo_end.")
        sys.exit()
        
# In[ ]:
# ### Include the flow information to the capacity data frame, by mergine the flow 

df_try_cap = df_capacity
df_try_flow = df_flow

column_dict = {'Value' : 'Flow'}
#change the colloumn name save flow
df_try_flow = df_flow.rename(columns = column_dict)

#merged the two data frames
merged_df = pd.merge(df_try_cap, df_try_flow[['Flow','IRRRE', 'IRRRI',]], on=['IRRRE', 'IRRRI'], 
                     how='left')
#replace the Nan with zeros meaning there was not flow from some regions to regions should be EPS
merged_df['Flow'] = merged_df['Flow'].fillna(0)


#save the merged_df with a slack
df_tot = merged_df

#create a new coloumn with the groups of flows
df_tot['edge'] = merged_df[['IRRRE', 'IRRRI']].apply(lambda x: ','.join(sorted(x)), axis=1)
#for every group find the max
df_edge_group = df_tot.groupby(by='edge')['Flow'].max()
#keep that in a dictionary
max_flow_dict = df_edge_group.to_dict()

#function checks if the dictionary data correspond with the every row flow
def check_max_flow(edge, flow):
    max_flow = max_flow_dict.get(edge, None)
    if max_flow is None:
        return 'NA'
    if flow == max_flow:
        return 'True'
    else:
        return 'False'

merged_df['Max_flow'] = merged_df.apply(lambda x: check_max_flow(x['edge'], x['Flow']), axis=1)
              
  
#pass it back to the df_capacity frame to continue
df_capacity = merged_df


# In[ ]:
# ### 2.5 Add bypass coordinates for indirect lines



if LINES == 'Capacity':
    df_bypass = pd.merge(df_bypass, df_capacity[['Year', 'Country', 'IRRRE', 'IRRRI', 'UNITS', 'Value','Flow','Max_flow']], on = ['IRRRE', 'IRRRI'], how = 'left')
    #Replace existing row by 2 bypass rows
    keys = list(df_bypass.columns.values)[0:2]
    i1 = df_capacity.set_index(keys).index
    i2 = df_bypass.set_index(keys).index
    df_capacity = df_capacity[~i1.isin(i2)] #Delete existing rows that need bypass
    df_capacity = df_capacity.append(df_bypass, ignore_index = True, sort = True) #Append bypass rows
    
if LINES == 'Flow' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Capacity'
    df_bypass = pd.merge(df_bypass, df_flow[['Year', 'Country', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Value']], on = ['IRRRE', 'IRRRI'], how = 'left').dropna()
    #Replace existing row by 2 bypass rows
    keys = list(df_bypass.columns.values)[0:2]
    i1 = df_flow.set_index(keys).index
    i2 = df_bypass.set_index(keys).index
    df_flow = df_flow[~i1.isin(i2)]#Delete existing rows that need bypass
    df_flow = df_flow.append(df_bypass, ignore_index = True, sort = True)#Append bypass rows


# In[ ]:
# ### 2.6 Calculate Congestion



if LINES == 'CongestionFlow': #Skip this cell in case LINES != 'CongestionFlow'
    df_flow = pd.merge(df_flow, df_capacity[['Year', 'Country', 'IRRRE', 'IRRRI', 'Value']], on = ['Year', 'Country', 'IRRRE', 'IRRRI'], how = 'left')
    df_flow.rename(columns={'Value_x': 'Value', 'Value_y' : 'Capacity'}, inplace = True)
    df_flow['Congestion'] = df_flow['Value'] / df_flow['Capacity'] * 100

    #Create color codes for congestion of lines
    df_flow['color'] = pd.cut(df_flow['Congestion'], bins = flowline_breaks, labels = flowline_color )



# In[ ]:
# ### 2.7 One direction capacity  lines
#this code does not work btw IK you change the matrix inside the second loop?


#When capacity is not the same in both directions, display one:
for i,row in df_capacity.iterrows():
    for k,row in df_capacity.iterrows():
        if (df_capacity.loc[k,'IRRRE'] == df_capacity.loc[i,'IRRRI']) & (df_capacity.loc[k,'IRRRI'] == df_capacity.loc[i,'IRRRE']) & (df_capacity.loc[k,'Value'] != df_capacity.loc[i,'Value']):
            df_capacity.loc[i,'Value'] = df_capacity.loc[k,'Value']


# In[ ]:
# ###  2.8 Define line centers



#Define centre of each transmission line
if LINES == 'Flow' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Capacity'
    df_flow['LatMid'] = (df_flow['LatImp'] + df_flow['LatExp']) /2
    df_flow['LonMid'] = (df_flow['LonImp'] + df_flow['LonExp']) /2
if LINES == 'Capacity' or LINES == 'CongestionFlow': #Skip this cell in case LINES == 'Flow'
    df_capacity['LatMid'] = (df_capacity['LatImp'] + df_capacity['LatExp']) /2
    df_capacity['LonMid'] = (df_capacity['LonImp'] + df_capacity['LonExp']) /2


# In[ ]:
# ###  create some lines to indicate hydrogen from thrid countries. 

#df_hydrogen_lines_outside

# In[]
#process the capacities to be able to be plotted
#mike the pie charts based on technologies
if plot_category == 'TECH_TYPE':
# Create horizontal table with sectors as columns
    display_column = 'TECH_TYPE'
    #Distinguish if has CCS or not for hydrogen
    G_to_tech_type = {
    'GNR_STEAM-REFORMING_E-70_Y-2020': 'SMR',
    'GNR_STEAM-REFORMING-CCS_E-70_Y-2020': 'SMR-CCS'
    }
    df_GNR_capacity['TECH_TYPE'] = df_GNR_capacity['G'].map(G_to_tech_type).fillna(df_GNR_capacity['TECH_TYPE'])
 
 
    
    
#Keep the year and scenario
#make pie charts based on FUEls
if plot_category == 'FFF':
    display_column = 'FFF'
    #If you map fuels to change the fuel type.     
    # Define the dictionary to map old fuel names to new ones
    
    #First split wind to wind on and wind off based on the tech_type
    # create a dictionary to map the values of TECH_TYPE to the corresponding FFF names
    tech_type_to_fff = {"WIND-ON": "WIND-ON", "WIND-OFF": "WIND-OFF"}
    # use the map function to replace the values of FFF based on the values of TECH_TYPE
    df_GNR_capacity['FFF'] = df_GNR_capacity['TECH_TYPE'].map(tech_type_to_fff).fillna(df_GNR_capacity['FFF'])
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
    df_GNR_capacity['FFF'] = df_GNR_capacity['FFF'].map(fff_to_fuel).fillna(df_GNR_capacity['FFF'])
    
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
    df_GNR_capacity['FFF'] = df_GNR_capacity['G'].map(G_to_FFF).fillna(df_GNR_capacity['FFF'])   

if exclude_H2Storage:
    df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['TECH_TYPE'] != 'H2-STORAGE']
    
#df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['TECH_TYPE'] != 'H2-STORAGE']

if exclude_Import_Cap_H2:
    df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['FFF'] != 'IMPORT_H2']

#if you plot production do not show production from storages
if Show_pie == 'production':
    if exclude_ElectricStorage:
        df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['FFF'] != 'ELECTRIC']
    
    if exclude_Geothermal:
        df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['FFF'] != 'HEAT']    

#Load coloours for techs
#upgraded palette
if plot_category == 'TECH_TYPE':
    df_color_tech = {
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
if plot_category == 'FFF':
    df_color_tech = {
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

if plot_category == 'FFF':
    df_color_tech = {
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


#get the names
if plot_category == 'TECH_TYPE':
    df_tech_names = df_GNR_capacity['TECH_TYPE'].unique()
    df_tech_names_sorted = np.sort(df_tech_names)
    df_tech_names = df_tech_names_sorted

if plot_category == 'FFF':   
    df_tech_names = df_GNR_capacity['FFF'].unique()
    df_tech_names_sorted = np.sort(df_tech_names)
    df_tech_names = df_tech_names_sorted

#Keep the year and other info    
df_GNR_capacity.loc[:, 'Y'] = df_GNR_capacity['Y'].astype(int)
df_GNR_capacity = df_GNR_capacity[df_GNR_capacity['Y'] == year]


#sum values
df_GNR_capacity = pd.DataFrame(df_GNR_capacity.groupby(['RRR', display_column])['Value'].sum().reset_index())

df_slack_GNR = df_GNR_capacity
#Merge the data frame to get the coordinates
df_slack_GNR = pd.merge(df_slack_GNR, df_region[['Lat', 'Lon', 'RRR']], on = ['RRR'], how = 'right')

#if they are some nan countries with no tech group filter outcome of merge
if plot_category == 'TECH_TYPE':
    df_slack_GNR = df_slack_GNR.dropna(subset=['TECH_TYPE'])

if plot_category == 'FFF':
    df_slack_GNR = df_slack_GNR.dropna(subset=['FFF'])

#Keep the names of the regions
RRRs = df_slack_GNR['RRR'].unique()



#some times some capacities are close to zero but with a negative make them o
df_slack_GNR.loc[(df_slack_GNR['Value'] < 0) & (df_slack_GNR['Value'] > -0.0001), 'Value'] = 0


#slack1_1 = df_slack_GNR
#slack1_2 = df_capacity

#slack2_1 = df_slack_GNR
#slack2_2 = df_capacity

#slack1_1['Value']= slack1_1['Value'] - slack2_1['Value']
#slack1_1['Value']= slack1_2['Value'] - slack2_2['Value']

#df_slack_GNR = slack1_1
#df_capacity = slack2_2
# In[]
### 3.1 Plotting the regions
projection = ccrs.EqualEarth()

fig, ax = plt.subplots(figsize=(12, 12), subplot_kw={"projection": projection}, dpi=100)

for R in layers_in:
    geo = gpd.read_file(layers_in[R])
    ax.add_geometries(geo.geometry, crs = projection,
                  facecolor=['linen'], edgecolor='#46585d',
                  linewidth=.2)



for R in layers_out:
    geo = gpd.read_file(layers_out[R])
    ax.add_geometries(geo.geometry, crs = projection,
                  facecolor=['#d3d3d3'], edgecolor='#46585d',
                  linewidth=.2)
'''
# Set limit always after pies because it brakes the graph
ax.set_xlim(-11,29)      
ax.set_ylim(33,72)
'''


### 3.2 Adding transmission lines
# A function for finding the nearest value in an array
def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]






 
    
#%%
#Plot tran lines either for H2 or Electricity, options such as linear plot or cluster are available look the begging

#if import hydrogen is activate make lines to third nations
if Import_Hydrogen:
    if COMMODITY == 'H2':
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
    
#%%
#Plot tran lines either for H2 or Electricity, options such as linear plot or cluster are available look the begging            
lines = []
for i,row in df_capacity.iterrows(): 
    y1 = df_capacity.loc[i,'LatExp']
    x1 =  df_capacity.loc[i,'LonExp']
    y2 = df_capacity.loc[i,'LatImp']
    x2 = df_capacity.loc[i,'LonImp']
    cap = df_capacity.loc[i,'Value']
    #slope of line 
    m = (y2-y1)/(x2-x1)
    
    if cat == 'cluster':
        nearest = find_nearest(cluster_groups, cap) 
        width = np.array(cluster_widths)[cluster_groups == nearest]
    else:
        width = cap/line_width_constant
        if width < cluster_widths[0]:
            width = cluster_widths[0]


    # Print an error message, if capacity is a NaN value
    #Plot the lines
    if not(np.isnan(cap)):
        #plt plot line
        l, = ax.plot([x1,x2], [y1,y2], color = net_colour, solid_capstyle='round', solid_joinstyle='round', 
                     linewidth = width, zorder=1)
        #save line information
        lines.append(l)
        
        #plt arrows for the direction of flow  if its yes as option and plot only the net direction True/False
        if show_flow_arrows == 'YES':
            if df_capacity.loc[i,'Value'] >= label_min:
                if df_capacity.loc[i,'Max_flow'] == 'True':
                    #be carefull width is a array that why access the element
                    if cat == 'cluster':
                        head_length = 1.25*width[0]/10
                        head_width = 0.75*width[0]/10 
                    else:
                        head_length = 1.25*width/10
                        head_width = 0.75*width/10
                    #Choose arrow style
                    arrow = "-|>"
                    joinstyle = 'round'
                    style = ''.join([arrow,',head_length =',str(head_length),',head_width =',str(head_width)])
                    #plot the arrow
                    ax.annotate("", xytext=((x1+x2)/2,(y1+y2)/2),xy=((x1+x2)/2+0.01*(x2-x1),(y1+y2)/2+0.01*(y2-y1)), 
                                arrowprops=dict(arrowstyle= style,color= net_colour,joinstyle ='round'))

                #arrow = FancyArrowPatch((x1+x2)/2,(y1+y2)/2,(x1+x2)/2+0.001*(x2-x1),(y1+y2)/2+0.001*(y2-y1),
                #                       arrowstyle="->", color=net_colour)
                #ax.add_patch(arrow)
            
    else:
        print("There's a NaN value in line\nIRRRE %s\nIRRRI %s"%(df_capacity.loc[i, 'IRRRE'], df_capacity.loc[i, 'IRRRI']))

    # Add labels to  if its activated 
    
    if show_label == 'YES':
        if df_capacity.loc[i,'Value'] >= label_min:
            label = "{:.1f}".format(df_capacity.loc[i,'Value'])
            plt.annotate(label, # this is the value which we want to label (text)
            (df_capacity.loc[i,'LonMid'],df_capacity.loc[i,'LatMid']), # x and y is the points location where we have to label
            textcoords="offset points",
            xytext=(0,-4), # this for the distance between the points
            # and the text label
             ha='center',
             )
            #,arrowprops=dict(arrowstyle="->", color='green'))

#%
### 3.3 Adding HUB Capacities
if hub_display:
    idx = df_hubcap_agg['Year'] == year
    temp = df_hubcap_agg[idx]
    for i,row in temp.iterrows():
        
        markersize = row['Value']
        
        ax.plot(row['Lon'], row['Lat'], 'o', color=[.8, .8, 1], 
                markersize=markersize, zorder=-1)
               

#colours


#Pie charts
if GNR_Show:
    pies = []
    for r in RRRs:
        idx = df_slack_GNR['RRR'] == r
        # fig, ax = plt.subplots(1, facecolor='none')
        Lat = df_slack_GNR.loc[idx, 'Lat'].mean()
        Lon = df_slack_GNR.loc[idx, 'Lon'].mean()
        CAPSUM = df_slack_GNR.loc[idx, 'Value'].sum()
        if cat_pie == 'cluster':
            nearest = find_nearest(cluster_groups_pie, CAPSUM) 
            width = np.array(cluster_radius_pie)[cluster_groups_pie == nearest]
            radius = width[0]
        else:
            width = CAPSUM*pie_width_constant
            radius = width
        if CAPSUM != 0:
            if plot_category == 'TECH_TYPE':
                colors_df = [df_color_tech.get(tech, 'gray') for tech in df_slack_GNR['TECH_TYPE'][idx]]
            if plot_category == 'FFF':
                colors_df = [df_color_tech.get(tech, 'gray') for tech in df_slack_GNR['FFF'][idx]]
            p = ax.pie(df_slack_GNR['Value'][idx].values,
                       center=(Lon, Lat), radius=radius,
                       #If he does not find a match will return gray in the pie
                       colors = colors_df ) 
            #save pie information
            pies.append(p)
            
    scatter_handles = []
    #keep only some of classes for the legend, legend based on scatter
    slack_length = len(cluster_groups_pie)-1
    if COMMODITY == 'Electricity' :
        cluster_groups_pie = [cluster_groups_pie[i] for i in [0, 7, 14, (slack_length-7)]]
        cluster_radius_pie = [cluster_radius_pie[i] for i in [0, 7, 14, (slack_length-7)]]
    
    if COMMODITY == 'H2' :
        cluster_groups_pie = [cluster_groups_pie[i] for i in [1, 7, 15, (slack_length-6)]]
        cluster_radius_pie = [cluster_radius_pie[i] for i in [1, 7, 15, (slack_length-6)]]
        
    #can be tricky to plot radius with scatter because, s is in points, and needs to cover the area 1/72 inc
    for i in range(len(cluster_groups_pie)):
        scatter = ax.scatter([], [], s=1200*((cluster_radius_pie[i]*72/fig.dpi)**2), facecolor='grey', edgecolor='grey')
        scatter_handles.append(scatter)

    if Show_pie == 'capacity':
        legend_labels = ['{} GW'.format(cluster_groups_pie[i]) for i in range(len(cluster_groups_pie))]
    else:
        legend_labels = ['{} TWh'.format(cluster_groups_pie[i]) for i in range(len(cluster_groups_pie))]

    #fig, ax = plt.subplots()

    first_legend = ax.legend(scatter_handles, legend_labels,
               scatterpoints=1,
               loc='upper left',
               ncol=4,
               fontsize=14,
               frameon=False,
               bbox_to_anchor=(0, 1))

    ax.add_artist(first_legend)    
         
    # Set limit always after pies because it brakes the graph
    ax.set_xlim(-11,35)      
    ax.set_ylim(34,72)
    
    #the position of legends because with Electricity more technologies emerging
    if COMMODITY == 'H2':
        pos_tech = (0,0.86)
    elif COMMODITY == "Electricity":
        if plot_category == 'TECH_TYPE':
            pos_tech = (0, 0.77)   
        else:
            pos_tech = (0,0.78)
          

    #legend for technologies
    #typical python concept
    patches = [mpatches.Patch(color=df_color_tech[tech], label=tech) for tech in df_tech_names]
    #to make circle in the legend
    # = [mpatches.Circle((0, 0), radius=5, facecolor=df_color_tech[tech], edgecolor='none') for tech in df_tech_names]
    second_legend = ax.legend(handles=patches, loc='lower left', ncol = 3,frameon=False,
                              mode='expnad',bbox_to_anchor=pos_tech)    
    ax.add_artist(second_legend) 
    
#
### 3.3 Making a legend for trans lines H2 or electricity
if COMMODITY == 'Electricity':
    subs = 'el'
    if cat == 'cluster' or cat == 'linear':
        # Create lines for legend
        lines = []
        string = []
        for i in range(len(cluster_groups)):
            # The patch
            lines.append(Line2D([0], [0], linewidth=cluster_widths[i],
                                color=net_colour))
            # The text
            if i == 0:
                ave = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave, subs))
            elif i == len(cluster_groups)-1:
                ave = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave, subs))
            else:
                ave0 = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave0, subs))
        if plot_category == 'TECH_TYPE':
            ax.legend(lines, string,frameon=False, loc='upper left', bbox_to_anchor=(0, 0.77))
        else:
            ax.legend(lines, string,frameon=False, loc='upper left', bbox_to_anchor=(0, 0.78))
            




if COMMODITY == 'H2':
    subs = 'H2'
    if cat == 'cluster' or cat == 'linear':
        # Create lines for legend
        lines = []
        string = []
        for i in range(len(cluster_groups)):
            # The patch
            lines.append(Line2D([0], [0], linewidth=cluster_widths[i],
                                color=net_colour))
            # The text
            if i == 0:
                ave = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave, subs))
            elif i == len(cluster_groups)-1:
                ave = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave, subs))
            else:
                ave0 = cluster_groups[i]
                string.append('%0.1f GW$_\mathrm{%s}$'%(ave0, subs))
        
        ax.legend(lines, string,frameon=False, loc='upper left', bbox_to_anchor=(0, 0.85))    
    

#remove border
plt.box(False)

### 3.3 Save map
# Make Transmission_Map output folder
if not os.path.isdir('output/Transmission_Map/' + LINES + '/' + SCENARIO + '/' + market):
    os.makedirs('output/Transmission_Map/' + LINES + '/' + SCENARIO + '/' + market)


output_dir = 'output/Transmission_Map/' + LINES + '/' + SCENARIO + '/' + market

plt.savefig(output_dir + '/' +  map_name + '.png', dpi=300, bbox_inches='tight')
    

#Saw plot
plt.show()



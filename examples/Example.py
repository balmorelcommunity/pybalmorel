"""
Created on 04.06.2024

This script serve as an example on how to use the package, and as a test in developing it

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

### 0.1 Use development scripts or the package installed from pip
use_development = True
import pandas as pd
if use_development:
    import sys
    sys.path.append('../')
    from src.pybalmorel import MainResults, Balmorel
else:
    from pybalmorel import IncFile, MainResults


#%% ------------------------------- ###
###        1. Pre-Processing        ###
### ------------------------------- ###

### Create an .inc file

# Initiate .inc file class
DE = IncFile(name='DE',
            prefix="TABLE   DE1(RRR,DEUSER,YYY)   'Annual electricity consumption (MWh)'\n",
            suffix="\n;\nDE(YYY,RRR,DEUSER) = DE1(RRR,DEUSER,YYY);",
            path='files')


# Create annual electricity demand 
DE.body = pd.DataFrame(index=['DK1', 'DK2'], columns=[2030, 2040, 2050],
                       data=[[17e6, 20e6, 25e6],
                            [14e6, 17e6, 20e6]])

# Fix the index format (in this case, append the DEUSER set to RRR)
DE.body.index += ' . RESE'

# Save .inc file to path (will save as ./Balmorel/sc1/data/DE.inc)
DE.save()

#%% ------------------------------- ###
###          2. Run Balmorel        ###
### ------------------------------- ###

# Initiate Model Class
model = Balmorel('path/to/model/folder')
print(model.scenarios) # Print recognised scenarios

# Run Model
model.run('base', {'some_cmd_line_option' : 'arg'})

# Collect MainResults into model.results
model.collect_results()
model.results.get_result('OBJ_YCR') # Get objective function

#%% ------------------------------- ###
###       3. Post-Processing        ###
### ------------------------------- ###

### 3.1 Interactive bar chart tool
res = MainResults(['MainResults_Example1.gdx',
                   'MainResults_Example2.gdx'], 
                  'files',
                  scenario_names=['SC1', 'SC2'])
res.interactive_bar_chart()

### 3.2 Plotting maps
res.plot_map('SC2', 'Electricity', 2050)

### 3.3 Plot profiles
res.plot_profile('Hydrogen', 2050, 'SC2')
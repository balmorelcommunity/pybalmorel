"""
Created on 04.06.2024

This script serve as an example on how to use the package, and as a test in developing it

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import sys
sys.path.append('../')
from src.pybalmorel import MainResults
from src.pybalmorel.functions import plot_map

#%% ------------------------------- ###
###        1. Plotting Tools        ###
### ------------------------------- ###

### 1.1 Interactive bar chart tool
res = MainResults('MainResults_ScenarioName.gdx', 'Files')
res.interactive_bar_chart()


### 1.2 Plotting maps
plot_map('files', 'files/2024 BalmorelMap.geojson', 'ScenarioName',
         2050, 'Electricity', 'files/bypass_lines.csv')


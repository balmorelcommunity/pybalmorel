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
if use_development:
    import sys
    sys.path.append('../')
    from src.pybalmorel import MainResults, Balmorel
else:
    from pybalmorel import IncFile, MainResults


#%% ------------------------------- ###
###        1. Plotting Tools        ###
### ------------------------------- ###

### 1.1 Interactive bar chart tool
# res = MainResults(['MainResults_Example1.gdx',
#                    'MainResults_Example2.gdx'], 
#                   'files',
#                   scenario_names=['SC1', 'SC2'])
# res.interactive_bar_chart()


### 1.2 Plotting maps
# res.plot_map('SC2', 'Electricity', 2050)

### 1.3 Plot profiles
# res.plot_profile('Hydrogen', 2050, 'SC2')

#%% ------------------------------- ###
###          2. Run Balmorel        ###
### ------------------------------- ###

b = Balmorel(r'C:\Users\mathi\gitRepos\Balmorel')

# print(b.scenarios)
b.collect_results()
# print(b.results.sc)

print(b.results.get_result('OBJ_YCR').Scenario.unique())
"""
TITLE

Description

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel import MainResults
import os


#%% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###

def test_MainResults():
    # GAMS system directory - If not in path define here!
    gams_system_directory = None
    
    # Loading one scenario
    res = MainResults(files='MainResults_Example1.gdx', paths='examples/files', system_directory=gams_system_directory)

    df = res.get_result('PRO_YCRAGF')
    
    assert list(df.columns) == ['Scenario', 'Year', 'Country', 'Region', 'Area', 'Generation', 'Fuel', 'Commodity', 'Technology', 'Unit', 'Value']
    
    # Loading several scenarios, with automatic naming
    res = MainResults(files=['MainResults_Example1.gdx', 'MainResults_Example2.gdx'], paths='examples/files', system_directory=gams_system_directory)

    df = res.get_result('G_CAP_YCRAF')
    assert list(df.Scenario.unique()) == ['Example1', 'Example2']
    
    # Loading several scenarios, and naming them
    res = MainResults(files=['MainResults_Example1.gdx', 'MainResults_Example2.gdx'], paths='examples/files', scenario_names=['SC1', 'SC2'], system_directory=gams_system_directory)

    df = res.get_result('G_CAP_YCRAF')
    assert list(df.Scenario.unique()) == ['SC1', 'SC2']
    
    # GUI
    res.interactive_bar_chart()
    
    # Test profiles
    fig, ax = res.plot_profile(scenario='SC1', year=2050, commodity='Electricity', columns='Technology',
                 region='DK2')
    fig.savefig('tests/output/electricity_profile.png')
    fig, ax = res.plot_profile(scenario='SC1', year=2050, commodity='Hydrogen', columns='Technology',
                 region='DK1')
    fig.savefig('tests/output/hydrogen_profile.png')
    fig, ax = res.plot_profile(scenario='SC2', year=2050, commodity='Heat', columns='Technology',
                 region='DK1')
    fig.savefig('tests/output/heat_profile.png')
    assert 'electricity_profile.png' in os.listdir('tests/output') and 'heat_profile.png' in os.listdir('tests/output') and 'hydrogen_profile.png' in os.listdir('tests/output')
    
    # Test map
    fig, ax = res.plot_map('SC2', 2050, 'elecTriciTY')
    fig.savefig('tests/output/electricity_map.png') 
    fig, ax = res.plot_map('SC2', 2050, 'HYDROGEN') 
    fig.savefig('tests/output/hydrogen_map.png') 
    assert 'electricity_map.png' in os.listdir('tests/output') and 'hydrogen_map.png' in os.listdir('tests/output')
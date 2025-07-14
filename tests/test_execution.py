"""
TITLE

Description

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel import Balmorel


#%% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###

def test_Balmorel():
    model = Balmorel('examples/Balmorel')
    print(model) # Print recognised scenarios
    scenarios = model.scenarios
    scenarios.sort()
    
    assert scenarios == ['base', 'valid_scenario']
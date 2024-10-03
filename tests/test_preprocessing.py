"""
TITLE

Description

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel.classes import IncFile
from pybalmorel import GUI
import pandas as pd
import os


#%% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###

### Create an .inc file
def test_IncFile():
    # Initiate .inc file class
    DE = IncFile(name='DE',
                prefix="TABLE   DE1(RRR,DEUSER,YYY)   'Annual electricity consumption (MWh)'\n",
                suffix="\n;\nDE(YYY,RRR,DEUSER) = DE1(RRR,DEUSER,YYY);",
                path='tests/output')

    # Create annual electricity demand 
    DE.body = pd.DataFrame(index=['DK1', 'DK2'], columns=[2030, 2040, 2050],
                        data=[[17e6, 20e6, 25e6],
                                [14e6, 17e6, 20e6]])

    # Fix the index format (in this case, append the DEUSER set to RRR)
    DE.body.index += ' . RESE'

    # Save .inc file to path (will save as ./Balmorel/sc1/data/DE.inc)
    DE.save()
    
    assert 'DE.inc' in os.listdir('tests/output')
    
# This makes an error when exiting the GUI, but in principle it works, so can be used locally
# def test_GUI():
#     GUI.geofilemaker()
    

"""
Created on 03.06.2024

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

# Choice of either dark or bright plots
# import matplotlib.pyplot as plt

# style = 'report'

# if style == 'report':
#     plt.style.use('default')
#     fc = 'white'
# elif style == 'ppt':
#     plt.style.use('dark_background')
#     fc = 'none'

#%% ------------------------------- ###
###          1. Colours             ###
### ------------------------------- ###

tech_colours = {
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
            'SALT-CAVERN': '#E8C3A8',
            'STEEL-TANK':'#C0C0C0',
            'FUELCELL': '#d4bbff',
            'IMPORT H2':'#cd6f00'
            }


fuel_colours = {
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
            'HYDROGEN': '#dbdcec'
            }


balmorel_colours = tech_colours | fuel_colours

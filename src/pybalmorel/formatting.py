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

#%% ------------------------------- ###
###            2. Other             ###
### ------------------------------- ###

mainresults_symbol_columns = {'F_CONS_YCRA': ['Year','Country','Region','Area','Generation','Fuel','Technology'],
                             'F_CONS_YCRAST': ['Year','Country','Region','Area','Generation','Fuel','Season','Time','Technology'],
                             'G_CAP_YCRAF': ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                             'G_STO_YCRAF': ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                             'H2_DEMAND_YCR': ['Year','Country','Region','Category'],
                             'H2_DEMAND_YCRST': ['Year','Country','Region','Season','Time','Category'],
                             'H2_PRICE_YCR': ['Year','Country','Region','Category'],
                             'H2_DEMAND_YCRST': ['Year','Country','Region','Season','Time','Category'],
                             'H_BALANCE_YCRAST': ['Year','Country','Region','Area','Technology','Season','Time'],
                             'H_DEMAND_YCRA': ['Year','Country','Region','Area','Category'],
                             'H_DEMAND_YCRAST': ['Year','Country','Region','Area','Season','Time','Category'],
                             'H_PRICE_YCRA': ['Year','Country','Region','Area','Category'],
                             'H_PRICE_YCRAST': ['Year','Country','Region','Area','Season','Time'],
                             'OBJ_YCR': ['Year','Country','Region','Category'],
                             'PRO_YCRAGF': ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology'],
                             'PRO_YCRAGFST': ['Year','Country','Region','Area','Generation','Fuel','Season','Time','Commodity','Technology'],
                             'X_CAP_YCR': ['Year','Country','From','To','Category'],
                             'X_FLOW_YCR': ['Year','Country','From','To'],
                             'X_FLOW_YCRST': ['Year','Country','From','To','Season','Time'],
                             'XH2_CAP_YCR': ['Year','Country','From','To','Category'],
                             'XH2_FLOW_YCR': ['Year','Country','From','To'],
                             'XH2_FLOW_YCRST': ['Year','Country','From','To','Season','Time'],
                             'XH_CAP_YCA': ['Year','Country','From','To','Category'],
                             'XH_FLOW_YCA': ['Year','Country','From','To'],
                             'XH_FLOW_YCAST': ['Year','Country','From','To','Season','Time']}
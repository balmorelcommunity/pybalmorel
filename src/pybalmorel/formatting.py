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
            'BOILERS': '#8B008B',
            'ELECT-TO-HEAT': '#FFA500',
            'INTERSEASONAL-HEAT-STORAGE': '#FFD700',
            'CHP-BACK-PRESSURE': '#E5D8D8',
            'STEAMREFORMING': '#00BFFF',
            'SMR-CCS': '#00BFFF',
            'SMR': '#d1b9b9',
            'INTRASEASONAL-HEAT-STORAGE': '#00FFFF',
            'CONDENSING': '#8a3ffc',
            'SOLAR-HEATING': '#FF69B4',
            'CHP-EXTRACTION': '#ff7eb6',
            'SOLAR-PV': '#d2a106',
            'WIND-ON': '#006460',
            'WIND-OFF': '#08bdba',
            'INTRASEASONAL-ELECT-STORAGE': '#ba4e00',
            'H2-STORAGE': '#E8C3A8',
            'ELECTROLYZER': '#ADD8E6',
            'SALT-CAVERN': '#E8C3A8',
            'STEEL-TANK':'#C0C0C0',
            'FUELCELL': '#d4bbff',
            'IMPORT H2':'#cd6f00'
            }


fuel_colours = {
            'HYDRO': '#08bdba',
            # 'WIND-ON': '#5e45ff',
            # 'WIND-OFF': '#4589ff',
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

            'IMPORT': '#96b9fc',
            'LIGHTOIL': '#666666',
            'FUELOIL': '#666666',
            'WATER': '#3f2500',
            'WIND': '#53f385',
            'SUN': '#ffff00',
            'WOODCHIPS': '#e94343',
            'WOODPELLETS': '#d73c3c',
            'PEAT': '#cccccc',
            'STRAW': '#f18787',
            'WASTEHEAT': '#ff0000'
            }


balmorel_colours = tech_colours | fuel_colours

mberos_colours = {
        'IMPORT' : [150/255, 185/255, 252/255],
        'BIOGAS' : [128/255, 159/255, 121/255],
        'CONDENSING' : [0.2, 0.2, 0.2],
        'NATGAS' : [0.2, 0.2, 0.2],
        'COAL' : [0, 0, 0],
        'LIGHTOIL' : [0.4, 0.4, 0.4],
        'FUELOIL' : [.4, .4, .4],
        'WATER' : [63/255, 37/255, 1],
        'HYDRO-RESERVOIRS' : [63/255, 37/255, 1],
        'HYDRO-RUN-OF-RIVER' : [63/255*0.8, 37/255*0.8, 1*0.8],
        'WIND' : [83/255, 243/255, 133/255],
        'WIND-ON' : [83/255, 243/255, 133/255],
        'WIND-OFF' : [83/255*0.8, 243/255*0.8, 133/255*0.8],
        'SUN' : [255/255, 254/255, 0],
        'SOLAR-PV' : [255/255, 254/255, 0],
        'MUNIWASTE' : [150/255, 150/255, 150/255],
        'WOODCHIPS' : [233/255, 67/255, 67/255],
        'WOODPELLETS' : [215/255, 60/255, 60/255],
        'STRAW' : [241/255, 135/255, 135/255],
        'PEAT' : [.8, .8, .8],
        'ELECTRIC' : [252/255, 1, 137/255],
        'HYDROGEN' : [137/255, 224/255, 1],
        'NUCLEAR' : [204/255, 0, 204/255],
        'WASTEHEAT' : [1,0,0]
        }

#%% ------------------------------- ###
###            2. Other             ###
### ------------------------------- ###

#Balmorel
balmorel_symbol_columns = {'F_CONS_YCRA':     ['Year','Country','Region','Area','Generation','Fuel','Technology'],
                           'F_CONS_YCRAST':   ['Year','Country','Region','Area','Generation','Fuel','Season','Time','Technology'],
                           'G_CAP_YCRAF':     ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                           'EL_DEMAND_YCR':   ['Year','Country','Region','Category'],
                           'EL_DEMAND_YCRST': ['Year','Country','Region','Season','Time','Category'],
                           'EL_PRICE_YCR':    ['Year','Country','Region'],
                           'EL_PRICE_YCRST':  ['Year','Country','Region','Season','Time'],
                           'G_STO_YCRAF':     ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                           'EL_BALANCE_YCRST':['Year','Country','Region','Technology','Season','Time'],
                           'H2_DEMAND_YCR':   ['Year','Country','Region','Category'],
                           'H2_DEMAND_YCRST': ['Year','Country','Region','Season','Time','Category'],
                           'H2_PRICE_YCR':    ['Year','Country','Region','Category'],
                           'H2_DEMAND_YCRST': ['Year','Country','Region','Season','Time','Category'],
                           'H_BALANCE_YCRAST':['Year','Country','Region','Area','Technology','Season','Time'],
                           'H_DEMAND_YCRA':   ['Year','Country','Region','Area','Category'],
                           'H_DEMAND_YCRAST': ['Year','Country','Region','Area','Season','Time','Category'],
                           'H_PRICE_YCRA':    ['Year','Country','Region','Area','Category'],
                           'H_PRICE_YCRAST':  ['Year','Country','Region','Area','Season','Time'],
                           'OBJ_YCR':         ['Year','Country','Region','Category'],
                           'PRO_YCRAGF':      ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology'],
                           'PRO_YCRAGFST':    ['Year','Country','Region','Area','Generation','Fuel','Season','Time','Commodity','Technology'],
                           'X_CAP_YCR':       ['Year','Country','From','To','Category'],
                           'X_FLOW_YCR':      ['Year','Country','From','To'],
                           'X_FLOW_YCRST':    ['Year','Country','From','To','Season','Time'],
                           'XH2_CAP_YCR':     ['Year','Country','From','To','Category'],
                           'XH2_FLOW_YCR':    ['Year','Country','From','To'],
                           'XH2_FLOW_YCRST':  ['Year','Country','From','To','Season','Time'],
                           'XH_CAP_YCA':      ['Year','Country','From','To','Category'],
                           'XH_FLOW_YCA':     ['Year','Country','From','To'],
                           'XH_FLOW_YCAST':   ['Year','Country','From','To','Season','Time']
}


balmorel_mainresults_symbol_columns = {'F_CONS_YCRA':    ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Technology'],
                           'F_CONS_YCRAST':   ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Season','Time','Technology'],
                           'G_CAP_YCRAF':     ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                           'G_STO_YCRAF':     ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Commodity','Technology','Category'],
                           'EL_DEMAND_YCR':   ['Scenario', 'Year','Country','Region','Category'],
                           'EL_DEMAND_YCRST': ['Scenario', 'Year','Country','Region','Season','Time','Category'],
                           'EL_PRICE_YCR':    ['Scenario', 'Year','Country','Region'],
                           'EL_PRICE_YCRST':  ['Scenario', 'Year','Country','Region','Season','Time'],
                           'EL_BALANCE_YCRST':['Scenario', 'Year','Country','Region','Technology','Season','Time'],
                           'H2_DEMAND_YCR':   ['Scenario', 'Year','Country','Region','Category'],
                           'H2_DEMAND_YCRST': ['Scenario', 'Year','Country','Region','Season','Time','Category'],
                           'H2_PRICE_YCR':    ['Scenario', 'Year','Country','Region','Category'],
                           'H2_DEMAND_YCRST': ['Scenario', 'Year','Country','Region','Season','Time','Category'],
                           'H_BALANCE_YCRAST':['Scenario', 'Year','Country','Region','Area','Technology','Season','Time'],
                           'H_DEMAND_YCRA':   ['Scenario', 'Year','Country','Region','Area','Category'],
                           'H_DEMAND_YCRAST': ['Scenario', 'Year','Country','Region','Area','Season','Time','Category'],
                           'H_PRICE_YCRA':    ['Scenario', 'Year','Country','Region','Area','Category'],
                           'H_PRICE_YCRAST':  ['Scenario', 'Year','Country','Region','Area','Season','Time'],
                           'OBJ_YCR':         ['Scenario', 'Year','Country','Region','Category'],
                           'PRO_YCRAGF':      ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Commodity','Technology'],
                           'PRO_YCRAGFST':    ['Scenario', 'Year','Country','Region','Area','Generation','Fuel','Season','Time','Commodity','Technology'],
                           'X_CAP_YCR':       ['Scenario', 'Year','Country','From','To','Category'],
                           'X_FLOW_YCR':      ['Scenario', 'Year','Country','From','To'],
                           'X_FLOW_YCRST':    ['Scenario', 'Year','Country','From','To','Season','Time'],
                           'XH2_CAP_YCR':     ['Scenario', 'Year','Country','From','To','Category'],
                           'XH2_FLOW_YCR':    ['Scenario', 'Year','Country','From','To'],
                           'XH2_FLOW_YCRST':  ['Scenario', 'Year','Country','From','To','Season','Time'],
                           'XH_CAP_YCA':      ['Scenario', 'Year','Country','From','To','Category'],
                           'XH_FLOW_YCA':     ['Scenario', 'Year','Country','From','To'],
                           'XH_FLOW_YCAST':   ['Scenario', 'Year','Country','From','To','Season','Time']
}

#Optiflow
optiflow_symbol_columns = {'ECO_INDIC':             ['Year','Indicator'],
                           'ECO_PROC_YCRAP':        ['Year','Country','Region','Area','Process','Cost'],
                           'EMI_PROC':              ['Year','Country','Region','Area','Process','Flow'],
                           'EMI_YCRAG':             ['Year','Country','Region','Area','Generation','Fuel','Technology'],
                           'OBJ_YCR':               ['Year','Country','Region','Category'],
                           'PRO_YCRAGF':            ['Year','Country','Region','Area','Generation','Fuel','Commodity','Technology'],
                           'PRO_YCRAGFST':          ['Year','Country','Region','Area','Generation','Fuel','Season','Time','Commodity','Technology'],
                           'RE_fuel_Price':         ['Year','Country','Process','Flow'],
                           'VFLOW_Opti_A':          ['Year','Country','From','To','Flow'],
                           'VFLOW_Opti_C':          ['Year','Country','From','To','Flow'],
                           'VFLOWBUFFER_Opti_C':    ['Year','Buffer','Process','Flow'],
                           'VFLOTCCU_A':            ['Year','Area','Source','Flow'],
                           'VFLOTCCU_C':            ['Year','Country','Source','Flow'],
                           'VFLOWSOURCE_Opti_A':    ['Year','Area','Source','Flow'],
                           'VFLOWSOURCE_Opti_C':    ['Year','Country','Source','Flow'],
                           'VFLOWSTORAGE_Opti_A':   ['Year','Area','Process','Flow'],
                           'VFLOWSTORAGE_Opti_C':   ['Year','Country','Process','Flow'],
                           'VFLOWTRANS_Opti_A':     ['Year','From','To','Process','Flow'],
                           'VFLOWTRANS_Opti_C':     ['Year','From','To','Process','Flow']
}

optiflow_mainresults_symbol_columns = {'ECO_INDIC': ['Scenario','Year','Indicator'],
                           'ECO_PROC_YCRAP':        ['Scenario','Year','Country','Region','Area','Process','Cost'],
                           'EMI_PROC':              ['Scenario','Year','Country','Region','Area','Process','Flow'],
                           'EMI_YCRAG':             ['Scenario','Year','Country','Region','Area','Generation','Fuel','Technology'],
                           'OBJ_YCR':               ['Scenario','Year','Country','Region','Category'],
                           'PRO_YCRAGF':            ['Scenario','Year','Country','Region','Area','Generation','Fuel','Commodity','Technology'],
                           'PRO_YCRAGFST':          ['Scenario','Year','Country','Region','Area','Generation','Fuel','Season','Time','Commodity','Technology'],
                           'RE_fuel_Price':         ['Scenario','Year','Country','Process','Flow'],
                           'VFLOW_Opti_A':          ['Scenario','Year','Country','From','To','Flow'],
                           'VFLOW_Opti_C':          ['Scenario','Year','Country','From','To','Flow'],
                           'VFLOWBUFFER_Opti_C':    ['Scenario','Year','Buffer','Process','Flow'],
                           'VFLOTCCU_A':            ['Scenario','Year','Area','Source','Flow'],
                           'VFLOTCCU_C':            ['Scenario','Year','Country','Source','Flow'],
                           'VFLOWSOURCE_Opti_A':    ['Scenario','Year','Area','Source','Flow'],
                           'VFLOWSOURCE_Opti_C':    ['Scenario','Year','Country','Source','Flow'],
                           'VFLOWSTORAGE_Opti_A':   ['Scenario','Year','Area','Process','Flow'],
                           'VFLOWSTORAGE_Opti_C':   ['Scenario','Year','Country','Process','Flow'],
                           'VFLOWTRANS_Opti_A':     ['Scenario','Year','From','To','Process','Flow'],
                           'VFLOWTRANS_Opti_C':     ['Scenario','Year','From','To','Process','Flow']
}




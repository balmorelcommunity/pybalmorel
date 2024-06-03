# -*- coding: utf-8 -*-
"""
Created on 28.05.2022

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ----------------------------- ###
###       0. Script Settings      ###
### ----------------------------- ###

import traceback

try:
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import sys
    import gams
    import os
    from Functions import symbol_to_df
    
    ### 0.0 Load Arguments
    if len(sys.argv) > 2:
        paths = (r'%s'%sys.argv[1]).split(',')
        SC     = sys.argv[2]
        iter   = sys.argv[3]
        reg     = sys.argv[4].upper()
        Y       = sys.argv[5]
        com     = sys.argv[6].upper()
        typ     = sys.argv[7] # Should be a column, e.g. TECH_TYPE, RRR, AAA, G
        style   = sys.argv[8].lower()
        
    ### 0.1 If no arguments, then you are probably running this script stand-alone
    else:
        import os
        print('-------------------------------\n'+'           TEST MODE           \n'+'-------------------------------\n')
        os.chdir(__file__.replace(r'\Scripts\ProductionProfile.py', ''))
        paths = r'C:\Users\mathi\gitRepos\spatial-aggregation\muni+nord\model'.split(',')
        SC = 'Muni+NordBefore'
        iter = '0'
        reg = 'All'.upper()
        com = 'HEAT'
        Y = '2050'
        typ = 'TECH_TYPE' # Should be a column, e.g. TECH_TYPE, RRR, AAA, G
        style = 'dark'

    # Find the MainResults file
    found_scenario = False
    for wk_dir in paths: 
        wk_dir = wk_dir.lstrip(' ').rstrip(' ')
        if wk_dir[-4:] == '\...':
            wk_dir = wk_dir[:-4]
            for subdir in pd.Series(os.listdir(wk_dir.rstrip('\...'))):  
                subpath = os.path.join(wk_dir, subdir, 'model')
                if os.path.isdir(subpath):
                    if os.path.exists(subpath + '/MainResults_%s_Iter%s.gdx'%(SC, iter)): 
                        wk_dir = subpath
                        print('Found %s_Iter%s in %s'%(SC, iter, wk_dir))
                        SC = SC + '_Iter%s'%iter
                        found_scenario = True
                        break
                        
                    elif os.path.exists(subpath + '/MainResults_%s.gdx'%SC):
                        wk_dir = subpath
                        print('Found %s in %s'%(SC, wk_dir))
                        found_scenario = True     
                        break
                    
        else:
            if os.path.exists(wk_dir + '/MainResults_%s_Iter%s.gdx'%(SC, iter)): 
                print('Found %s_Iter%s in %s'%(SC, iter, wk_dir))
                SC = SC + '_Iter%s'%iter
                found_scenario = True
                
            elif os.path.exists(wk_dir + '/MainResults_%s.gdx'%SC):
                print('Found %s in %s'%(SC, wk_dir))
                found_scenario = True
                
        if found_scenario:
            break

    if found_scenario:
        ### 0.2 Set plot style
        if style == 'light':
            plt.style.use('default')
            fc = 'white'
            demcolor = 'k'
        elif style == 'dark':
            plt.style.use('dark_background')
            fc = 'none'
            demcolor = 'w'
                
            
        ### ----------------------------- ###
        ###        1. Read Files          ###
        ### ----------------------------- ###

        ### Technical
        delim = ','

        ### Try to load the non-iteration scenario suffix first
        ws = gams.GamsWorkspace()
        try:
            db = ws.add_database_from_gdx(wk_dir + '/MainResults_%s.gdx'%SC)
        except gams.GamsException:
            SC = SC + '_Iter%s'%iter  
            db = ws.add_database_from_gdx(wk_dir + '/MainResults_%s.gdx'%SC)

        fProd = symbol_to_df(db, "PRO_YCRAGFST", cols=['Y', 'C', 'RRR', 'AAA', 'G', 'FFF', 'SSS', 'TTT', 'COMMODITY', 'TECH_TYPE', 'UNITS', 'Val'])
        
        if com == 'ELECTRICITY':
            fPrice  = symbol_to_df(db, "EL_PRICE_YCRST", cols=['Y', 'C', 'RRR', 'SSS', 'TTT', 'UNITS', 'Val']) 
            fDem  = symbol_to_df(db, "EL_DEMAND_YCRST", cols=['Y', 'C', 'RRR', 'SSS', 'TTT', 'VARIABLE_CATEGORY', 'UNIT', 'Val'])  
        elif com == 'HYDROGEN':
            fPrice  = symbol_to_df(db, "H2_PRICE_YCRST", cols=['Y', 'C', 'RRR', 'SSS', 'TTT', 'UNITS', 'Val']) 
            fDem  = symbol_to_df(db, "H2_DEMAND_YCRST", cols=['Y', 'C', 'RRR', 'SSS', 'TTT', 'VARIABLE_CATEGORY', 'UNIT', 'Val'])  
        elif com == 'HEAT':
            fPrice  = symbol_to_df(db, "H_PRICE_YCRAST", cols=['Y', 'C', 'RRR', 'AAA', 'SSS', 'TTT', 'UNITS', 'Val']) 
            fDem  = symbol_to_df(db, "H_DEMAND_YCRAST", cols=['Y', 'C', 'RRR', 'AAA', 'SSS', 'TTT', 'VARIABLE_CATEGORY', 'UNIT', 'Val'])  

        ### ----------------------------- ###
        ###           Parameters          ###
        ### ----------------------------- ###

        # Choices
        if reg in fProd.C.unique():
            CorRorA = 'C' # Region or country level?
            country = reg 
            # Load transmission
            if com == 'ELECTRICITY':
                fFlow = symbol_to_df(db, "X_FLOW_YCRST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            elif com == 'HYDROGEN':
                fFlow = symbol_to_df(db, "XH2_FLOW_YCRST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            elif com == 'HEAT':
                fFlow = symbol_to_df(db, "XH_FLOW_YCAST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            else:
                pass
        elif reg in fProd.RRR.unique():
            CorRorA = 'R'
            # Load transmission
            if com == 'ELECTRICITY':
                fFlow = symbol_to_df(db, "X_FLOW_YCRST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            elif com == 'HYDROGEN':
                fFlow = symbol_to_df(db, "XH2_FLOW_YCRST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            elif com == 'HEAT':
                fFlow = symbol_to_df(db, "XH_FLOW_YCAST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            else:
                pass   
        elif reg in fProd.AAA.unique():
            CorRorA = 'A'
            fFlow = symbol_to_df(db, "XH_FLOW_YCAST", cols=['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
        elif reg == 'ALL':
            CorRorA = 'All'
            
        # Check if flow is empty
        if (reg != 'ALL'):
            if (len(fFlow) == 0):
                fFlow = pd.DataFrame(columns = ['Y', 'C', 'IRRRE', 'IRRRI', 'SSS', 'TTT', 'UNITS', 'Val'])
            
        resfactor = 1 # Factor on flows, to get yearly results 
        price_agg_func = np.average # function for aggregation of regions - average or max ?
        bypass_eps = 'Y' # Bypass EPS values in electricity prices? This could be fair, if you have regions with very small electricity demand, making EPS electricity prices (not wrong)


        ### Colours
        c = {'IMPORT' : [150/255, 185/255, 252/255],
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
            'WASTEHEAT' : [1,0,0]}


        ### ----------------------------- ###
        ###              Sort             ###
        ### ----------------------------- ###

        
        # Production
        if CorRorA == 'R':
            idx = fProd['RRR'] == reg
        elif CorRorA == 'C':
            idx = fProd['C'] == country
        elif CorRorA == 'A':
            idx = fProd['AAA'] == reg
        elif CorRorA == 'All':
            idx = fProd['C'] == fProd['C']
        idx = idx & (fProd['COMMODITY'] == com)
        idx = idx & (fProd['Y'] == Y)

        # Make temporal index
        t_index = pd.MultiIndex.from_product((fProd.SSS.unique(), fProd.TTT.unique()), names=['SSS', 'TTT'])
        df_placeholder = pd.DataFrame(index=t_index)

        # Create production dataframe
        fPr = fProd[idx].pivot_table(values='Val', index=['SSS', 'TTT'], columns=[typ],aggfunc=sum)
        fPr = df_placeholder.join(fPr, how='left')
        fPr.fillna(0, inplace=True)
        
        ### Import / Export
        # First aggregate regions in country, if country
        if CorRorA == 'C':
            for reg0 in [reg0 for reg0 in fFlow.loc[fFlow.C == reg, 'IRRRE'].unique()]:
                fFlow['IRRRE'] = fFlow['IRRRE'].str.replace(reg0, country) 
                fFlow['IRRRI'] = fFlow['IRRRI'].str.replace(reg0, country) 
            # Delete internal flows
            fFlow = fFlow[~((fFlow.IRRRE == reg) & (fFlow.IRRRI == reg))]

        # Get year
        print('Note that the following flows have not been scaled to fit annual flows\n')
        try:
            idx = fFlow['Y'] == Y

            idx1 = fFlow['IRRRE'] == reg
            idx2 = fFlow['IRRRI'] == reg
            
            fFlE = fFlow[idx & idx1].pivot_table(values='Val', index=['SSS', 'TTT'], aggfunc=sum)    
            fFlI = fFlow[idx & idx2].pivot_table(values='Val', index=['SSS', 'TTT'], aggfunc=sum)
            
            # Make sure no values are missing
            fFlE = df_placeholder.join(fFlE, how='left')
            fFlE.fillna(0, inplace=True)
        
            fFlI = df_placeholder.join(fFlI, how='left')
            fFlI.fillna(0, inplace=True)
        
            print('\n' + reg + ' Main Export-To Regions: [TWh]')
            print(fFlow[idx & idx1].pivot_table(values='Val', index=['IRRRI'], aggfunc=sum)/1e6*resfactor  )
            print('\n')

            print(reg + ' Main Import-From Regions: [TWh]')
            print(fFlow[idx & idx2].pivot_table(values='Val', index=['IRRRE'], aggfunc=sum)/1e6*resfactor  )
            print('\n')
            no_trans_data = False
        except (KeyError, NameError):
            no_trans_data = True
            print('No transmission data')


        ### Electricity Demand and price
        if CorRorA == 'C':
            fP = fPrice.groupby(['Y', 'C', 'SSS', 'TTT'], as_index=False)
            fP = fP.aggregate({'Val' : price_agg_func}) # For aggregation of electricity price, max or average? (maybe max if nodal representation of a market?)
            fP = fP[fP.C == country]    
            
            fD = fDem.groupby(['Y', 'C', 'VARIABLE_CATEGORY', 'SSS', 'TTT'], as_index=False)
            fD = fD.aggregate({'Val' : np.sum}) 
            dems = fD[(fD['Y']==Y) & (fD['C'] == country)]
            fD = fDem[fDem.C == country] 
        elif CorRorA == 'R':
            dems = fDem[(fDem['Y']==Y) & (fDem['RRR'] == reg)]
            fP = fPrice[fPrice['RRR'] == reg]    
            fD = fDem[fDem['RRR'] == reg] 
        elif CorRorA == 'A':
            dems = fDem[(fDem['Y']==Y) & (fDem['AAA'] == reg)]
            fP = fPrice[fPrice['AAA'] == reg]    
            fD = fDem[fDem['AAA'] == reg] 
        elif CorRorA == 'All':
            fP = fPrice.groupby(['Y', 'C', 'SSS', 'TTT'], as_index=False)
            fP = fP.aggregate({'Val' : price_agg_func}) # For aggregation of electricity price, max or average? (maybe max if nodal representation of a market?)        
            fD = fDem.groupby(['Y', 'C', 'VARIABLE_CATEGORY', 'SSS', 'TTT'], as_index=False)
            fD = fD.aggregate({'Val' : np.sum}) 
            dems = fD[(fD['Y']==Y)]

        print('Electricity Demand: [TWh]')
        for cat in np.unique(dems['VARIABLE_CATEGORY']):
            print(cat, ' = ', round(dems[dems['VARIABLE_CATEGORY'] == cat]['Val'].sum()/1e6*resfactor,2))

        # Subtract import from export
        f = pd.DataFrame({'IMPORT' : np.zeros(len(fPr))}, index=fPr.index)
        if not(no_trans_data):
            # f = f + fFlI - fFlE
            f_temp = pd.DataFrame([], index=fPr.index)
            try:
                f_temp['IMPORT'] = fFlI
                f_temp['EXPORT'] = -fFlE
                f_temp[np.isnan(f_temp)] = 0
            except ValueError:
                # If no connections to this region
                pass
            
            # f[np.isnan(f)] = 0
            # f.columns = ['IMPORT']
            f = pd.DataFrame([], index=fPr.index)
            f['IMPORT'] = f_temp.sum(axis=1)
            
            f[fPr.columns] = fPr
                    
        else:
            f = pd.DataFrame([], index=fPr.index)
            f[fPr.columns] = fPr
                
        # Price
        if bypass_eps.lower() == 'y':
            idx = fP.Val == 'Eps'
            fP.loc[idx, 'Val'] = 0 # If you chose to bypass eps values in el-price, it's probably because the actual prices are very small
            fP.Val = fP.Val.astype(float)
            
        idx = fP['Y'] == Y
        fP = fP[idx].pivot_table(values='Val', index=['SSS', 'TTT'], aggfunc=price_agg_func)

        # Make sure no values are missing
        fP = df_placeholder.join(fP, how='left')
        fP.fillna(0, inplace=True)
        
        # Demand
        idx = fD['Y'] == Y 
        fD = fD[idx].pivot_table(values='Val', index=['SSS', 'TTT'], aggfunc=sum)
        
        # Make sure no values are missing
        fD = df_placeholder.join(fD, how='left')
        fD.fillna(0, inplace=True)
        
        # x-axis
        xticks = fD.index.sort_values()
        fD = fD.loc[xticks]
        x = np.arange(0, len(fD), 1)

        # H2 Production
        # idx = (fH2['Year'] == Y) & (fH2['Reg'] == reg) & (fH2['SC'] == SC)
        # H2 = fH2.loc[idx, 'Power [GWH2]']
        # if len(H2) == 0:
        #     H2 = np.zeros(len(x))

        ### Graph
        fig, ax = plt.subplots(figsize=(9,3), facecolor=fc)
        temp = np.zeros(len(fD))
        ps = []
        for col in f:
            try:
                ps.append(ax.fill_between(x, temp, temp+f.loc[xticks, col].values/1e3, label=col, facecolor=np.array(c[col]).round(2)))
            except KeyError:
                print('No defined colour for %s'%col)
                ps.append(ax.fill_between(x, temp, temp+f.loc[xticks, col].values/1e3, label=col))
            temp = temp + f.loc[xticks, col].values/1e3       

        # p0, = ax.plot(x, H2, color=[76/255,128/255, 204/255])
        p1, = ax.plot(x, fD.values[:,0]/1e3, color=demcolor)
        ax2 = ax.twinx()
        try:
            p2, = ax2.plot(x, fP.values, 'r--', linewidth=1)
        except TypeError:
            print('\nThere could be "EPS" values in electricity prices - cannot plot')

        ax.set_facecolor(fc)
        names = pd.Series(f.columns).str.lower().str.capitalize()
        # names = list(names) + ['H$_2$ Production [GW$_\mathrm{H_2}$]', 'Demand', 'Price'] # With H2 production
        names = list(names) + ['Demand', 'Price'] # Without H2 production

        # ax.legend(ps+[p0, p1, p2], names, # With H2 production
        ax.legend(ps+[p1, p2], names, # Without H2 production
                loc='center', bbox_to_anchor=(.5, 1.28), ncol=5)
        ax.set_title(SC + ' - ' + com + ' - ' + reg + ' - ' + str(Y))
        ax.set_ylabel('Power [GW]')
        xlabel = xticks.get_level_values(1).unique().to_list()
        # if len(xlabel) > 14: 
        #     xlabel = [', '.join(xlabel[i*14:(i+1)*14]) + '\n' for i in range(round(len(xlabel) / 14))]
        #     ax.set_xlabel('Terms: ' + ''.join(xlabel))
        # else:
        #     ax.set_xlabel('Terms: ' + ', '.join(xlabel))
        
        # xticks = np.hstack(np.arange(0, 673, 168)) # For 4 representative weeks
        # ax.set_xticks(xticks+12.5)
        # ax.set_xticklabels((xticks/24).astype(int)) # old
        # ax.set_xticklabels(['S02', 'S08', 'S15', 'S21', 'S28', 'S34', 'S41', 'S47']) # For 4 representative weeks
        if (CorRorA == 'R') | (CorRorA == 'A'):
            ax2.set_ylabel('Price [€ / MWh]')
        else:
            ax2.set_ylabel('Average Price [€ / MWh]')
        # ax2.set_ylim([0, 300])
        # ax.set_xlim([2*168, 3*168])
        # ax.set_xlim([0, 4*168])
        N_S = len(xticks.get_level_values(0).unique()) 
        N_T = len(xticks.get_level_values(1).unique())
        tick_step = N_T
        ax.set_xlim([min(x), max(x)])
        ax.set_xticks(x[::tick_step])
        ax.set_xticklabels(xticks.get_level_values(0)[::tick_step], rotation=90)
        # ax.set_xlim([x[N_T*13], x[N_T*14]])
        #ax.set_ylim([0, 16])

        # fig.savefig(SC+'_'+str(Y)+'_'+reg+'ElGraph.pdf', bbox_inches='tight',
        #             transparent=True)
        # ax.set_xlim([200, 250])

        # ax.set_ylim(-15000, 5000)
        fig.savefig('Output/productionprofile.png', bbox_inches='tight', transparent=True)

        print('\nSuccesful execution of ProductionProfile.py')
        with open('Output/Log.txt', 'w') as f:
            f.write('No errors\nFound scenario in %s'%wk_dir)
    
    else:
        print("\nDidn't find a scenario in the paths given")
        with open('Output/Log.txt', 'w') as f:
            f.write('Nothing loaded! Check path and MainResults files.')
        
except Exception as e:
    message = traceback.format_exc()
    
    print('\nAn error occurred - check the Python environment')
    with open('Output/Log.txt', 'w') as f:
        f.write('Something went wrong. Make sure you typed an existing scenario, iteration, symbol, region, year, legend type and/or plot style.')
        f.write('\n\n' + message)
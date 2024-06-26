"""
Created on 11.11.2023

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###
import traceback

try:
    
    import gams
    import sys
    import os
    import pandas as pd
    from Functions import symbol_to_df, convert_to_list

    ### 0.0 Load Arguments
    if len(sys.argv) > 2:
        paths    = (r'%s'%sys.argv[1]).split(',')
        SCs     = convert_to_list(sys.argv[2])
        iters   = convert_to_list(sys.argv[3])
        symbols = convert_to_list(sys.argv[4])
        print(sys.argv)
        
    ### 0.1 If no arguments, then you are probably running this script stand-alone
    else:
        import os
        print('-------------------------------\n'+'           TEST MODE           \n'+'-------------------------------\n')
        os.chdir(__file__.replace(r'\Scripts\LoadGDX.py', ''))
        paths = r'C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\base\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W5T8\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W5T21\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W10T24\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W20T24\model'.split(',')
        # paths = convert_to_list('C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\base\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W5T8\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W5T21\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W10T24\model, C:\Users\mberos\gitRepos\balmorel-antares\Balmorel\W20T24\model')
        SCs = ['All']
        iters = [0]
        symbols = ['EL_PRICE_YCR']

    if SCs[0].lower() == 'all':
        # Find all MainResults in the first path
        SClist = pd.Series(os.listdir(paths[0]))
        SClist = SClist[SClist.str.find('MainResults_') != -1]
        SClist = SClist.str.split('_Iter', expand=True)[0]
        SClist = SClist.str.replace('MainResults_', '').str.replace('.gdx', '')
        SCs = list(SClist.unique())
    
    ### ------------------------------- ###
    ###         1. Open GDX File        ###
    ### ------------------------------- ###

    ### 1.1 Load DataFrames
    ws = gams.GamsWorkspace()
    dfs = {symbol : pd.DataFrame({}) for symbol in symbols}
    warning_message = ''

    for SC in SCs:
        if len(iters) >= 1:
            for itr in iters:                
                SC_FULL = SC + '_Iter%s'%itr
                print('\nTrying to load MainResults_%s.gdx from path..'%(SC_FULL))
                for path in paths:
                    path = path.lstrip(' ').rstrip(' ')
                    if path[-4:] == '\...':
                        path = path.replace('\...', '')
                        for subdir in os.listdir(path):  
                            subpath = os.path.join(path, subdir, 'model')
                            if os.path.exists(subpath + "/MainResults_%s.gdx"%SC_FULL):
                                print(subpath)
                                try:
                                    db = ws.add_database_from_gdx(subpath.lstrip(' ').rstrip(' ') + "/MainResults_%s.gdx"%SC_FULL)
                                
                                    for symbol in symbols:
                                        try:
                                            temp = symbol_to_df(db, symbol)
                                            temp['SC'] = SC
                                            temp['Iteration'] = itr
                                            dfs[symbol] = pd.concat((dfs[symbol], temp))
                                            print("Loaded %s"%(symbol))
                                        except:
                                            print("Couldn't load %s"%symbol)
                                except gams.GamsException:
                                    print("It doesn't exist, not loaded")
                                
                    else:
                        try:
                            print(path)
                            db = ws.add_database_from_gdx(path.lstrip(' ').rstrip(' ') + "/MainResults_%s.gdx"%SC_FULL)
                        
                            for symbol in symbols:
                                try:
                                    temp = symbol_to_df(db, symbol)
                                    temp['SC'] = SC
                                    temp['Iteration'] = itr
                                    dfs[symbol] = pd.concat((dfs[symbol], temp))
                                    print("Loaded %s"%(symbol))
                                except:
                                    print("Couldn't load %s"%symbol)
                        except gams.GamsException:
                            print("It doesn't exist, not loaded")
        try:
            print('\nTrying to load MainResults_%s.gdx from path..'%SC)
            for path in paths:
                
                path = path.lstrip(' ').rstrip(' ')
                if path[-4:] == '\...':
                        path = path[:-4]
                        for subdir in pd.Series(os.listdir(path)):  
                            subpath = os.path.join(path, subdir, 'model')
                            if os.path.exists(subpath + "/MainResults_%s.gdx"%SC):
                                print(subpath)
                                db = ws.add_database_from_gdx(path.lstrip(' ').rstrip(' ') + "/MainResults_%s.gdx"%SC)
                else:
                    print(path)
                    db = ws.add_database_from_gdx(path.lstrip(' ').rstrip(' ') + "/MainResults_%s.gdx"%SC)
          
            
                for symbol in symbols:
                    try:
                        temp = symbol_to_df(db, symbol)
                        temp['SC'] = SC
                        temp['Iteration'] = -1
                        dfs[symbol] = pd.concat((dfs[symbol], temp)) 
                        print("Loaded %s"%(symbol))
                    except:
                        print("Couldn't load %s"%symbol)
        except gams.GamsException:
            print("It doesn't exist, not loaded") 
            
    all_empty = 0
    for symbol in symbols:
        dfs[symbol].to_csv('Output/%s.csv'%symbol, index=None)
        if len(dfs[symbol]) == 0:
            all_empty += 1
    

    ### 1.2 Saves the dataframes as efficient pickle files that can be read in a python script 
    # import pickle
    # with open('Output/df.pkl', 'wb') as f:
    #     pickle.dump(dfs, f)

    ### 1.3 Opening a pickle file
    # with open('df.pkl', 'rb') as f:
    #     dfs = pickle.load(f)
    
    with open('Output/Log.txt', 'w') as f:
        if len(warning_message) == 0:
            f.write('No errors')
            print('\nSuccesful execution of LoadGDX.py')
        elif all_empty == len(symbols):
            f.write('Nothing loaded! Check path and MainResults files.')
            print('Nothing loaded! Check path and MainResults files.')
        else:
            f.write(warning_message)
            print(warning_message)

except Exception as e:
    message = traceback.format_exc()
    
    print('\nAn error occurred - check the Python environment')
    with open('Output/Log.txt', 'w') as f:
        f.write('Something went wrong. Make sure you typed an existing scenario, iteration, symbol, region, year, legend type and/or plot style.')
        f.write('\n\n' + message)
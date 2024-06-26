"""
Created on 11.04.2024

@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import geopandas as gpd
import gams
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import cmcrameri
from PIL import Image
from ..utils import symbol_to_df

style = 'report'

if style == 'report':
    plt.style.use('default')
    fc = 'white'
elif style == 'ppt':
    plt.style.use('dark_background')
    fc = 'none'

#%% ------------------------------- ###
###        1. 
### ------------------------------- ###


### 1.1 Parameters
os.chdir(__file__.replace(r'\Scripts\ProductionMap.py', ''))

paths = r'C:\Users\mberos\gitRepos\Balmorel\base\model'
SC = 'DK_BZ'
# geofile = 'BalmorelMap+DKMUNI.gpkg'
geofile = '2024 BalmorelMapDK_.geojson'
gfidx = 'id' # index with region names

### 1.2 Load Files
# Balmorel Results
ws = gams.GamsWorkspace()
db = ws.add_database_from_gdx(os.path.join(paths, 'MainResults_%s.gdx'%SC))
pro = symbol_to_df(db, 'PRO_YCRAGFST', ['Y', 'C', 'R', 'A', 'G', 'F', 
                                        'S', 'T', 'Commodity', 'Tech', 'Unit', 'Val'])

# Geofile
gf = gpd.read_file('Input/%s'%geofile)
gf = gf[gf.NAME_0 == 'Denmark']
gf.index = gf[gfidx]

#%%
temp = pro[pro.F == 'WIND'].pivot_table(index=['R'], columns=['S', 'T'], 
                                        values='Val')

maxprod = temp.max().max()
delta_t = 120
images = []
print('Plotting...')
for S in temp.columns.get_level_values(0).unique():
    for T in temp.columns.get_level_values(1).unique():
        print(S, T) 
        fig, ax = plt.subplots()
        try:
            gf0 = gf.join(temp[S][T]).fillna(0).copy()
        except KeyError:
            # If no value
            gf0 = gf.copy()
            gf0[T] = 0 
        gf0.plot(column = T, ax=ax, cmap=cmcrameri.cm.cmaps['vik'], label='Data',
                legend=True, vmin=0, vmax=maxprod)
        
        # cbar = plt.colorbar()
        # ax.colorbar()
        ax.axis('off')

        # Store for .gif
        fig.canvas.draw()  # Draw the figure
        image = Image.frombytes('RGB', fig.canvas.get_width_height(), 
                                fig.canvas.tostring_rgb())
        images.append(image)
        plt.close(fig)


print('Saving gif...')
# Save gif
images[0].save('%s_windpro.gif'%SC, save_all=True, append_images=images[1:], 
            duration=delta_t, loop=0)
Convenient python functions for pre- or post-processing the GAMS framework Balmorel 

Check out Test.ipynb in https://github.com/Mathias157/pybalmorel/tree/master/tests for examples on how to use. 

A few examples are provided on processing outputs and inputs below.

## Outputs
### Example of plotting MainResults
```
from pybalmorel import MainResults

### 1.0 Loading MainResults in different ways
# Using MainResults files in the same path, with different suffixes
res = MainResults(files=['MainResults_Example1.gdx', 
                         'MainResults_Example2.gdx'], 
                  paths='Files')
# Using the Balmorel scenario folder structure, with optional scenario_names (otherwise, different scenarios by default get these generic names: SC1, SC2, ..., SCN)
res = MainResults(files=['MainResults.gdx', 
                         'MainResults.gdx'], 
                  paths=['Balmorel/Example1/model',
                         'Balmorel/Example2/model'],
                  scenario_names=['Example1', 'Example2'])

### 1.1 Getting a specific result
df = res.get_result('G_CAP_YCRAF')

### 1.2 Plotting maps
fig, ax = res.plot_map(scenario='SC1', commodity='Electricity', year=2050)

### 1.3 Plotting production profiles
fig, ax = res.plot_profile(scenario='SC2', year=2050, commodity='Heat', columns='Technology', region='all')

### 1.4 Interactive bar chart tool
res.interactive_bar_chart()
```

Results can be loaded into a pandas DataFrame from a .gdx file using gams and symbol_to_df:
```
import gams
import os
from pybalmorel.functions import symbol_to_df
import pandas as pd


# Load .gdx file
ws = gams.GamsWorkspace()
db = ws.add_database_from_gdx(os.path.abspath('Balmorel/base/model/MainResults_ScenarioName.gdx'))

# Load the annual production into a pandas DataFrame
pro = symbol_to_df(db, 'PRO_YCRAGF', cols=['Y', 'C', 'R', 'A', 'G', 'F', 
                                           'Commodity', 'Tech', 'Unit', 'Value'])
```


## Inputs
### Example of creating an .inc file
```
from pybalmorel import IncFile
import pandas as pd


# Initiate .inc file class
DE = IncFile(name='DE',
            prefix="TABLE   DE1(RRR,DEUSER,YYY)   'Annual electricity consumption (MWh)'\n",
            suffix="\n;\nDE(YYY,RRR,DEUSER) = DE1(RRR,DEUSER,YYY);",
            path='Balmorel/sc1/data')


# Create annual electricity demand 
DE.body = pd.DataFrame(index=['DK1', 'DK2'], columns=[2030, 2040, 2050],
                       data=[[17e6, 20e6, 25e6],
                            [14e6, 17e6, 20e6]])

# Fix the index format (in this case, append the DEUSER set to RRR)
DE.body.index += ' . RESE'

# Save .inc file to path (will save as ./Balmorel/sc1/data/DE.inc)
DE.save()
```

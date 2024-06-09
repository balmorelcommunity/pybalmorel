Convenient python functions for pre- or post-processing the GAMS framework Balmorel 

Check out Test.ipynb in https://github.com/Mathias157/pybalmorel/tree/master/tests for examples on how to use. 

A few examples are provided on processing outputs and inputs below.

## Outputs
### Example of plotting MainResults
```
from pybalmorel.functions import plot_map
from pybalmorel import MainResults

### 1.1 Interactive bar chart tool
res = MainResults('MainResults_ScenarioName.gdx', 'Files')
res.interactive_bar_chart()

### 1.2 Plotting maps
plot_map('files', 'files/2024 BalmorelMap.geojson', 'ScenarioName',
         2050, 'Electricity', 'files/bypass_lines.csv')
```

Results can be loaded into a pandas DataFrame from a .gdx file using gams and symbol_to_df:
```
import gams
import os
from pybalmorel.functions import symbol_to_df
import pandas as pd


# Load .gdx file
ws = gams.GamsWorkspace()
db = ws.add_database_from_gdx(os.path.abspath('Balmorel/base/model/MainResults_Base.gdx'))

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

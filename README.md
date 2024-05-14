Convenient python functions for pre- or post-processing the GAMS framework Balmorel 

### Example of creating an .inc file
```
from pybalmorel.functions import IncFile
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

# Fix the index format (in this case, adding the DEUSER set)
DE.body.index = DE.body.index + ' . RESE'

# Save .inc file to path (will save as ./Balmorel/sc1/data/DE.inc)
DE.save()
```

### Example of loading results from a .gdx file
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

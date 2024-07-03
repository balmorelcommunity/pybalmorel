# pybalmorel
Convenient python functions for pre- or post-processing the GAMS framework Balmorel 

## Examples
The following notebooks provide examples on how to use pybalmorel for pre-processing, post-processing and for executing Balmorel scenarios:
- [Pre-Processing](examples/PreProcessing.ipynb)
- [Execution](examples/Execution.ipynb)
- [Post-Processing](examples/PostProcessing.ipynb)

A few examples of processing outputs and inputs are also provided below.

## Outputs
### Example of using MainResults
```
from pybalmorel import MainResults

### 1.0 Loading MainResults in different ways
# Using MainResults files in the same path, with different suffixes
res = MainResults(files=['MainResults_Scenario1.gdx', 
                         'MainResults_Scenario2.gdx'], 
                  paths='Files')
# Using the Balmorel scenario folder structure, with optional scenario_names (otherwise, different scenarios by default get these generic names: SC1, SC2, ..., SCN)
res = MainResults(files=['MainResults.gdx', 
                         'MainResults.gdx'], 
                  paths=['Balmorel/Scenario1/model',
                         'Balmorel/Scenario2/model'],
                  scenario_names=['Scenario1', 'Scenario2'])

### 1.1 Getting a specific result
df = res.get_result('G_CAP_YCRAF')

### 1.2 Plotting maps
fig, ax = res.plot_map(scenario='Scenario1', commodity='Electricity', year=2050)

### 1.3 Plotting production profiles
fig, ax = res.plot_profile(scenario='Scenario2', year=2050, commodity='Heat', columns='Technology', region='all')

### 1.4 Interactive bar chart tool
res.interactive_bar_chart()
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
            path='Balmorel/Scenario1/data')


# Create annual electricity demand 
DE.body = pd.DataFrame(index=['DK1', 'DK2'], columns=[2030, 2040, 2050],
                       data=[[17e6, 20e6, 25e6],
                            [14e6, 17e6, 20e6]])

# Fix the index format (in this case, append the DEUSER set to RRR)
DE.body.index += ' . RESE'

# Save .inc file to path (will save as ./Balmorel/Scenario1/data/DE.inc)
DE.save()
```

# Overview

There are several functions to plot energy balances, transmission capacity maps and a ipywidget to interactively plot bar charts, check out [this notebook](https://github.com/Mathias157/pybalmorel/blob/master/examples/PostProcessing.ipynb).

The example below uses the Balmorel class to load results.

## Interactively Plotting All Results
```python
from pybalmorel import Balmorel

# Load Balmorel
model = Balmorel('path/to/Balmorel')

# Collect results
model.collect_results()

# Plot bar charts with an interactive GUI 
model.results.interactive_bar_chart()
```

## Transmission Maps and Energy Balances

Using the collected results below, the examples below illustrate how to plot figures of transmission capacities and save them. 

```python
# Plot electricity transmission capacities in the first scenario, year 2050
model.results.plot_map(model.results.sc[0], 2050, 'electricity', lines='Capacity')

# Plot total heat energy balance in the second scenario, year 2050
model.results.plot_profile('heat', 2050, model.results.sc[1])
```

`plot_profile` plots the whole year in one figure. To split the year into several figures, e.g. one per week, use `plot_profiles`, which returns lists of figures and axes:

```python
# One figure per 168 time slices (a week of hourly data)
figs, axes = model.results.plot_profiles('electricity', 2050, model.results.sc[0], chunk_size=168)
figs[0].savefig('electricity_week1.png')
```

Both functions also take `columns` ('Technology' or 'Fuel'), `region` (a country, region or area, defaults to 'ALL') and `style` ('light' or 'dark').

There are many more features, read more about the map plotting tool here [here](map_plotting.md).


## Getting Specific Results
The `model.results` is actually a `MainResults` class. The example below illustrates how to get specific results using that class.

```python
from pybalmorel import MainResults

mainresults_files = ['MainResults_SC1.gdx', 'MainResults_SC2.gdx']
paths = ['path/to/folder/with/SC1', 'path/to/folder/with/SC2']
results = MainResults(mainresults_files, paths=paths)
```

If the files are in the same folder, you just need to input a single path to the paths argument. The class will name the scenarios 'SC1' and 'SC2' by default and store them in a list in `results.sc`, but you can also provide your own names with the scenario_names argument.

Results are retrieved with `get_result`, which returns a DataFrame with the results of all scenarios and a 'Scenario' column:

```python
# Electricity production by technology in all scenarios
production = results.get_result('PRO_YCRAGF')
production.query("Commodity == 'ELECTRICITY'").pivot_table(
    index='Scenario', columns='Technology', values='Value', aggfunc='sum'
)
```

Column names are predefined for the standard Balmorel outputs. For other symbols, provide your own with the `cols` argument, e.g. `results.get_result('MY_SYMBOL', cols=['Year', 'Region'])`. If GAMS can't find your installation by itself, pass `system_directory='/opt/gams/53'` when creating `MainResults`.

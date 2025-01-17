# Post-Processing

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
model.results.plot_map(model.results.sc[0], 'electricity', 2050)

# Plot total heat energy balance in the second scenario, year 2050
model.results.plot_profile('heat', 2050, model.results.sc[1])
```

For more information about the map plotting please look here :

```{toctree}
:maxdepth: 1
:hidden:

postprocessing_map.md
```

## Getting Specific Results
The `model.results` is actually a `MainResults` class. The example below illustrates how to get specific results using that class.

```python
from pybalmorel import MainResults

mainresults_files = ['MainResults_SC1.gdx', 'MainResults_SC2.gdx']
paths = ['path/to/folder/with/SC1', 'path/to/folder/with/SC2']
results = MainResults(mainresults_files, paths=paths)
```

If the files are in the same folder, you just need to input a single path to the paths argument. The class will name the scenarios 'SC1' and 'SC2' by default and store them in a list in `results.sc`, but you can also provide your own names with the scenario_names argument.
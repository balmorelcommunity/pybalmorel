# Execution

The 'Balmorel' class can also be used to run Balmorel scenarios. Check out [this notebook](https://github.com/Mathias157/pybalmorel/blob/master/examples/Execution.ipynb) or the examples below.

```python
from pybalmorel import Balmorel

# Find Balmorel model
model = Balmorel('path/to/Balmorel')

# Run base scenario
model.run('base')

# Collect MainResults into model.results
model.collect_results()
model.results.get_result('OBJ_YCR') # Get objective function
```

## Finding the Model

`Balmorel` recognises the folder structure of a Balmorel model: the folder must contain `base`, and every other folder (except `simex`) with a `model/Balmorel.gms` and a `model/cplex.op4` or `model/cplex.op2` file is added as a scenario. Folders that don't qualify are reported. The scenarios found are listed in `model.scenarios`.

If GAMS can't find your installation by itself, pass its system directory:

```python
model = Balmorel('path/to/Balmorel', gams_system_directory='/opt/gams/53')
```

## Command Line Options

`run` takes GAMS double-dash parameters as a dictionary. Each key-value pair is passed as `--key=value`, which the model can read as `%key%`:

```python
# Equivalent to: gams Balmorel.gms --my_switch=yes
model.run('base', cmd_line_options={'my_switch': 'yes'})
```

If the run fails during execution, a message is printed and the error is raised after the listing file has been checked. If any solve in the listing file is infeasible, an exception is raised.

## Locating Results

`collect_results` loads all MainResults .gdx files from the scenarios' `model` folders into a [MainResults](postprocessing/overview.md#getting-specific-results) object at `model.results`. If you only want an overview of which results exist, `locate_results` is faster, as it does not load the files:

```python
model.locate_results()
print(model.scenario_names)  # Scenario names
print(model.files)           # MainResults files
print(model.paths)           # Folders of the files
```

A scenario folder with a single MainResults file is named after the folder. If a folder holds several MainResults files, e.g. `MainResults_SC1.gdx` and `MainResults_SC2.gdx`, the scenarios are named after the suffixes (`SC1`, `SC2`). Pass `suffix_naming_only=True` to `locate_results` or `collect_results` to always name scenarios after the suffix. The mappings between scenario folders and names are stored in `model.scfolder_to_scname` and `model.scname_to_scfolder`.

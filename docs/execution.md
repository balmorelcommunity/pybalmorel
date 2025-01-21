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
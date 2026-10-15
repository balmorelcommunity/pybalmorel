#!/usr/bin/env bash

# Remember to do this command locally:
# git update-index --chmod=+x tests/online_tests.sh

set -e

python -m pytest tests/test_preprocessing.py -k "not test_temporal_aggregation"
python -m pytest tests/test_execution.py
python -m pytest tests/test_weatheryear_naming_and_filtering.py
python -m pytest tests/test_weatheryear_config.py
python -m pytest tests/test_weatheryear_scenario_data.py
python -m pytest tests/test_backcasting.py

echo -e
echo "NOTE:"
echo "Only tests that do not require a GAMS installation can be performed online."
echo "Make sure to test functions requiring the gamsapi locally"
echo -e
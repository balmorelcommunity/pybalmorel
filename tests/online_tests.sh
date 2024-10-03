#!/usr/bin/env bash

# Remember to do this command locally:
# git update-index --chmod=+x tests/online_tests.sh

python -m pytest tests/test_preprocessing.py
python -m pytest tests/test_execution.py

echo -e
echo "NOTE:"
echo "Only tests that do not require a GAMS installation can be performed online."
echo "Make sure to test functions requiring the gamsapi locally"
echo -e
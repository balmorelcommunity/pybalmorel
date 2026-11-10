"""
Execution Tools

This script tests the execution functions from pybalmorel, currently only implemented
testing the scenario structure of Balmorel as including the entire model is heavy.

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import shutil
from pathlib import Path

from pybalmorel import Balmorel


# %% ------------------------------- ###
###             1. Utils            ###
### ------------------------------- ###


def test_Balmorel():
    model = Balmorel("examples/Balmorel")
    print(model)  # Print recognised scenarios
    scenarios = model.scenarios
    scenarios.sort()

    assert scenarios == ["base", "valid_scenario"]


def test_Balmorel_legacy_top_level_simex(tmp_path: Path, capsys) -> None:
    """Balmorel versions before balmorelcommunity/Balmorel#57 have simex in the top folder"""
    model_folder = tmp_path / "Balmorel"
    shutil.copytree("examples/Balmorel", model_folder)
    (model_folder / "simex").mkdir()

    model = Balmorel(model_folder)

    assert sorted(model.scenarios) == ["base", "valid_scenario"]
    assert str(model_folder / "simex") not in capsys.readouterr().out


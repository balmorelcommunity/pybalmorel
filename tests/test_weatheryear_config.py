"""
Weather-Year Config Tests

Tests CapDev_timesteps_to_keep parsing, which must accept 'S' as a list of
representative season codes (same shape as 'T'), matching the documented
config format.

Created on 17.08.2026
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import pytest

from pybalmorel import WEATHERYEAR
from pybalmorel.weatheryear.auxiliary_functions import build_capdev_timesteps_list
from pybalmorel.weatheryear.config_models import (
    CapDevTimestepsConfig,
    ConfigValidationError,
)

# %% ------------------------------- ###
###   1. CapDevTimestepsConfig       ###
### ------------------------------- ###


def test_capdev_timesteps_config_from_raw_accepts_list_of_seasons():
    config = CapDevTimestepsConfig.from_raw(
        {"S": ["S02", "S08"], "T": ["T073", "T076"]}
    )
    assert config.s == ["S02", "S08"]
    assert config.t == ["T073", "T076"]


def test_capdev_timesteps_config_from_raw_rejects_string_seasons():
    with pytest.raises(ConfigValidationError):
        CapDevTimestepsConfig.from_raw({"S": "S02,S08", "T": ["T073"]})


def test_capdev_timesteps_config_as_legacy_dict_round_trips_lists():
    config = CapDevTimestepsConfig.from_raw({"S": ["S02", "S08"], "T": ["T073"]})
    assert config.as_legacy_dict() == {
        "CapDev_timesteps_to_keep": {"S": ["S02", "S08"], "T": ["T073"]}
    }


# %% ------------------------------- ###
###   2. build_capdev_timesteps_list ###
### ------------------------------- ###


def test_build_capdev_timesteps_list_cross_product():
    config = {"CapDev_timesteps_to_keep": {"S": ["S02", "S08"], "T": ["T073", "T076"]}}
    assert build_capdev_timesteps_list(config) == [
        "S02.T073",
        "S02.T076",
        "S08.T073",
        "S08.T076",
    ]


# %% ------------------------------- ###
###   3. WEATHERYEAR year validation ###
### ------------------------------- ###


def test_WEATHERYEAR_rejects_year_outside_corres_range():
    with pytest.raises(ValueError):
        WEATHERYEAR(year=2024, config_fn="examples/files/mutli_year_config.yml", output_folder="results/")


def test_WEATHERYEAR_accepts_year_inside_corres_range():
    mly = WEATHERYEAR(year=2021, config_fn="examples/files/mutli_year_config.yml", output_folder="results/")
    assert mly.year == 2021

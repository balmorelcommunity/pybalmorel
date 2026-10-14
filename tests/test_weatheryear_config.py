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

import pandas as pd
import pytest

from pybalmorel import WEATHERYEAR
from pybalmorel.weatheryear.auxiliary_functions import (
    build_capdev_timesteps_list,
    process_timeseries_with_scaling,
)
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


def _hourly_profile(first_year: int, last_year: int) -> pd.DataFrame:
    index = pd.date_range(f"{first_year}-01-01", f"{last_year}-12-31 23:00", freq="h")
    return pd.DataFrame({"DK1": 0.5}, index=index.astype(str))


def test_process_timeseries_rejects_year_outside_input_range():
    with pytest.raises(ValueError, match="covers 2020-2021"):
        process_timeseries_with_scaling(
            _hourly_profile(2020, 2021), 2024, 2024, "wind", fix_monday=True
        )


def test_process_timeseries_rejects_input_ending_before_52_weeks():
    profile = _hourly_profile(2023, 2023).iloc[:-23]
    with pytest.raises(ValueError, match="only 8713 are available"):
        process_timeseries_with_scaling(profile, 2023, 2023, "hydro", fix_monday=True)


def test_process_timeseries_accepts_year_inside_input_range():
    _, df_cut, _ = process_timeseries_with_scaling(
        _hourly_profile(2020, 2022), 2021, 2021, "wind", fix_monday=True
    )
    assert len(df_cut) == 8736
    assert df_cut.index[0] == pd.Timestamp("2021-01-04")


def test_WEATHERYEAR_accepts_year_inside_corres_range():
    mly = WEATHERYEAR(year=2021, config_fn="examples/files/mutli_year_config.yml", output_folder="results/")
    assert mly.year == 2021

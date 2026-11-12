"""
Weather-Year Demand Plausibility Tests

Tests the plausibility check on the weather-year electricity demand profiles
(see CONTEXT.md, Demand Profile Fallback) on small synthetic profiles. GAMS-free.

Created on 26.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import numpy as np
import pandas as pd
import pytest

from pybalmorel.weatheryear.demand2btc import (
    demand_plausibility_failures,
    drop_implausible_demand,
)

# %% ------------------------------- ###
###        1. Plausibility          ###
### ------------------------------- ###


def _profiles(n_hours: int = 168) -> pd.DataFrame:
    hours = np.arange(n_hours)
    return pd.DataFrame(
        {
            "DK1": 3000 + 500 * np.sin(hours / 24 * 2 * np.pi),
            "FR": 50000 + 8000 * np.sin(hours / 24 * 2 * np.pi + 1),
            "PT": 6000 + 1500 * np.cos(hours / 24 * 2 * np.pi),
        },
        index=pd.date_range("2023-01-02", periods=n_hours, freq="h"),
    )


def test_plausible_profiles_pass():
    assert demand_plausibility_failures(_profiles()) == {}


def test_non_positive_values_fail():
    df = _profiles()
    df.iloc[10, 0] = -1e13

    failures = demand_plausibility_failures(df)

    assert set(failures) == {"DK1"}
    assert "1 hours at or below 0" in failures["DK1"]


def test_a_peak_far_above_the_median_fails():
    df = _profiles()
    df.iloc[20, 1] = 22.5 * df["FR"].median()

    failures = demand_plausibility_failures(df)

    assert set(failures) == {"FR"}
    assert failures["FR"].startswith("a peak of 22.")
    assert "times its median at 2023-01-02 20:00:00" in failures["FR"]


def test_identical_profiles_fail_for_every_copy():
    df = _profiles()
    df["DK2"] = df["DK1"]

    failures = demand_plausibility_failures(df)

    assert set(failures) == {"DK1", "DK2"}
    assert failures["DK2"] == "its profile is identical to DK1"


def test_failing_regions_are_left_out_so_they_keep_base(capsys):
    raw, scaled = _profiles(), _profiles()
    raw.iloc[0, 0] = 0
    # Corrupt years in the full series reach the scaled profile of a clean year
    scaled.iloc[0, 2] = -6.7e5

    raw, scaled = drop_implausible_demand(raw, scaled, 2023)

    assert list(raw.columns) == ["FR"]
    assert list(scaled.columns) == ["FR"]
    output = capsys.readouterr().out
    assert "DK1's 2023 electricity demand profile fails the plausibility check (1 hours at or below 0" in output
    assert "PT's 2023 electricity demand profile fails the plausibility check (in its scaled profile: 1 hours" in output


def test_every_region_failing_raises():
    df = -_profiles()

    with pytest.raises(Exception, match="Every region's 2023 electricity demand profile fails"):
        drop_implausible_demand(df, df.copy(), 2023)

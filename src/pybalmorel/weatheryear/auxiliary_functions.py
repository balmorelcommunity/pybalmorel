"""
Auxiliary helpers for the weather-year preprocessing to Balmorel conversion.

This module provides utility functions for path creation, technology/source parsing,
CapDev timestep generation, and ECDF-based scaling of reduced time-series subsets.

@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .exceptions import MalformedTechnologyFolderError


def create_directory_if_needed(destination_path: str) -> None:
    """Create directory tree if it does not exist."""
    Path(destination_path).mkdir(parents=True, exist_ok=True)


def align_timeseries_to_first_monday(df: pd.DataFrame, df_cut: pd.DataFrame, start_date: int) -> pd.DataFrame:
    """Align the first timestep to Monday and ensure 8736 hourly steps."""
    t = np.arange(
        datetime(int(start_date), 1, 1),
        datetime(int(start_date), 12, 31),
        timedelta(hours=1),
    ).astype(datetime)
    first_monday = t[np.array([date.weekday() for date in t]) == 0][0]

    df_cut = df_cut.loc[df_cut.index >= first_monday]

    if len(df_cut) < 8736:
        to_add = df.loc[df.index.year == (start_date + 1)][: 8736 - len(df_cut)]
        df_cut = pd.concat([df_cut, to_add])
    if len(df_cut) > 8736:
        df_cut = df_cut[:8736]

    return df_cut


def filter_timeseries_by_dates(df: pd.DataFrame, start_date: int, end_date: int) -> pd.DataFrame:
    """Cut a datetime-indexed DataFrame to a year range [start_date, end_date]."""
    mask = (df.index.year >= start_date) & (df.index.year <= end_date)
    return df.loc[mask]


def parse_technology_folder_name(folder: str) -> tuple[str, str]:
    """Infer technology variant and source type from a folder name.

    Args:
        folder: Folder name such as 'Future_Onshore' or 'PV_Rooftop'.

    Returns:
        Tuple of (onoff, source) used by downstream formatting logic.

    Raises:
        MalformedTechnologyFolderError: If no known folder pattern is found.
    """
    folder_map = [
        ("Future_Onshore", ("Onshore", "wind")),
        ("Future_Offshore_floating", ("Offshore_floating", "wind")),
        ("Future_Offshore_bottom_fixed", ("Offshore_bottom_fixed", "wind")),
        ("Existing_ERA5_GWA2", ("Existing", "wind")),
        ("PV_Rooftop", ("PV_Rooftop", "solar")),
        ("PV_Utility_scale_no_tracking", ("PV_Utility_scale_no_tracking", "solar")),
        ("PV_Utility_scale_tracking", ("PV_Utility_scale_tracking", "solar")),
    ]

    for pattern, result in folder_map:
        if pattern in folder:
            return result

    raise MalformedTechnologyFolderError(
        f"Unknown technology folder format: '{folder}'. "
        "Expected one of: Future_Onshore, Future_Offshore_floating, "
        "Future_Offshore_bottom_fixed, Existing_ERA5_GWA2, PV_Rooftop, "
        "PV_Utility_scale_no_tracking, PV_Utility_scale_tracking."
    )


def build_capdev_timesteps_list(config: dict[str, Any]) -> list[str]:
    """Build CapDev timesteps from config values.

    Args:
        config: Configuration dictionary containing 'CapDev_timesteps_to_keep'.

    Returns:
        List of 'Sxxx.Txx' timestep strings to keep for CapDev processing.
    """
    s_values = [
        s.strip() for s in config["CapDev_timesteps_to_keep"]["S"].strip(":[]").split(",")
    ]
    return [f"{s}.{t}" for s in s_values for t in config["CapDev_timesteps_to_keep"]["T"]]


def create_balmorel_time_mapping() -> pd.DataFrame:
    """Create a DataFrame mapping CapDev and DA timesteps to Balmorel time identifiers.
    Args:
        None
    Returns:
        DataFrame with columns 'CapDev_time' and 'DA_time'.
    """
    list_s = [f"S{str(i).zfill(2)}" for i in range(1, 53)]
    list_t = [f"T{str(i).zfill(3)}" for i in range(1, 169)]
    capdev_periods = [f"{s}.{t}" for s in list_s for t in list_t]
    df = pd.DataFrame(capdev_periods, columns=["CapDev_time"])

    list_s = [f"S{str(i).zfill(3)}" for i in range(1, 365)]
    list_t = [f"T{str(i).zfill(2)}" for i in range(1, 25)]
    da_periods = [f"{s}.{t}" for s in list_s for t in list_t]
    df["DA_time"] = da_periods

    return df


def _calculate_ecdf(data: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Compute empirical CDF arrays (x, y) for a one-dimensional sample."""
    x = np.sort(data)
    n = x.size
    y = np.arange(1, n + 1) / n
    return x, y


def _compute_inverse_quantile(data: pd.Series, quantiles: np.ndarray) -> np.ndarray:
    """Map quantiles to values using empirical inverse CDF interpolation."""
    x, y = _calculate_ecdf(data)
    return np.interp(quantiles, y, x)


def scale_timeseries_to_full_distribution(
    df: pd.DataFrame,
    df_cut: pd.DataFrame,
    source: str,
) -> pd.DataFrame:
    """Scale reduced time series using the distribution of the full series.

    For each column, non-zero entries in df_cut are mapped through quantiles from
    df_cut and then projected onto the empirical inverse CDF of df.

    Args:
        df: Full-resolution DataFrame.
        df_cut: Reduced-resolution DataFrame to be scaled.
        source: The source type (e.g., "wind" or "solar") to determine specific scaling logic.
    Returns:
        Scaled DataFrame with the same shape and index/columns as df_cut.
    """
    df_scaled = pd.DataFrame(0.0, index=df_cut.index, columns=df_cut.columns)

    for column_name in df.columns:
        mask_zero_df = df[column_name] == 0
        mask_zero_df_cut = df_cut[column_name] == 0

        if source == "solar":
            x_cut, u_cut = _calculate_ecdf(df_cut[column_name].loc[~mask_zero_df_cut])
            u_sel_orig = np.interp(df_cut[column_name].loc[~mask_zero_df_cut], x_cut, u_cut)
            
            df_scaled.loc[~mask_zero_df_cut, column_name] = _compute_inverse_quantile(
            df[column_name].loc[~mask_zero_df], u_sel_orig
        )
        else:
            x_cut, u_cut = _calculate_ecdf(df_cut[column_name])
            u_sel_orig = np.interp(df_cut[column_name], x_cut, u_cut)
            df_scaled[column_name] = _compute_inverse_quantile(df[column_name], u_sel_orig)

    return df_scaled

def process_timeseries_with_scaling(df: pd.DataFrame, start_date: str, end_date: str, source: str, fix_monday: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply necessary treatments to the time series data, including filtering by date range, fixing the first Monday if needed, and scaling the data to have the same mean as the full time series.
     Args:
        df: The original DataFrame containing the time series data.
        start_date: The start date for filtering the time series (in 'YYYY-MM-DD' format).
        end_date: The end date for filtering the time series (in 'YYYY-MM-DD' format).
        source: The source type (e.g., "wind" or "solar") to determine specific treatments.
        fix_monday: A boolean indicating whether to fix the first Monday in the time series if it is missing.
    Returns:
        A tuple containing three DataFrames: the original full time series, the cut time series based on the date range, and the scaled time series.
    """

    if source == "solar":
        df[df < 0] = 0

    # CorRES CSV indices are read as strings and must be normalized before year filtering.
    df.index = pd.to_datetime(df.index)
    
    df_cut=filter_timeseries_by_dates(df,start_date,end_date)
    if fix_monday:
        df_cut= align_timeseries_to_first_monday(df,df_cut,start_date)

    
    df_scaled=scale_timeseries_to_full_distribution(df,df_cut,source)
    
    

    
    return df, df_cut,df_scaled

def compute_capdev_timeseries(
    config: dict[str, Any],
    combined_scaled_dfs: pd.DataFrame,
    df_t: pd.DataFrame,
    source: str,
) -> pd.DataFrame:
    """Convert DA-scaled series to CapDev timeseries using configured timesteps.
    Args:
        config: Configuration dictionary containing 'CapDev_timesteps_to_keep'.
        combined_scaled_dfs: DataFrame of DA-scaled time series.
        df_t: DataFrame mapping CapDev and DA timesteps.
        source: The source type (e.g., "wind" or "solar","demand") to determine specific scaling logic.
    Returns:
        df_scaled:DataFrame of CapDev-scaled time series with index as CapDev_time.
    """
    capdev_timesteps = build_capdev_timesteps_list(config)
    df_t_cut = df_t[df_t.CapDev_time.isin(capdev_timesteps)]
    filtered_df = combined_scaled_dfs[combined_scaled_dfs.index.isin(df_t_cut.DA_time)]

    combined_scaled_copy = combined_scaled_dfs.copy()
    filtered_copy = filtered_df.copy()
    combined_scaled_copy.index = df_t.index
    filtered_copy.index = df_t_cut.index

    df_scaled=scale_timeseries_to_full_distribution(combined_scaled_copy,filtered_copy, source)
    #df_scaled = scaler(combined_scaled_copy, filtered_copy)
    df_scaled.index = df_t_cut.CapDev_time
    return df_scaled

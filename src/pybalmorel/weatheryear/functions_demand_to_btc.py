"""Helper functions for converting demand time series to Balmorel format."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def check_if_dir_exists(destination_path: str) -> None:
    """Create directory tree if it does not already exist."""
    Path(destination_path).mkdir(parents=True, exist_ok=True) 


def fix_first_monday(df: pd.DataFrame, df_cut: pd.DataFrame, start_date: int) -> pd.DataFrame:
    """Align the first timestep to Monday and ensure 8736 hourly steps.

    Args:
        df: Full input time series.
        df_cut: Year-filtered time series.
        start_date: Year as integer.

    Returns:
        Adjusted DataFrame starting from first Monday with 8736 records.
    """
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
    
    
    
def cut_timeseries(df: pd.DataFrame, start_date: int, end_date: int) -> pd.DataFrame:
    """Cut a datetime-indexed DataFrame to a year range [start_date, end_date]."""
    mask = (df.index.year >= start_date) & (df.index.year <= end_date)
    return df.loc[mask]


def get_CapDev_timesteps(config: dict[str, Any]) -> list[str]:
    """Build list of CapDev timesteps from config."""
    s_values = [
        s.strip() for s in config["CapDev_timesteps_to_keep"]["S"].strip(":[]" ).split(",")
    ]
    return [f"{s}.{t}" for s in s_values for t in config["CapDev_timesteps_to_keep"]["T"]]



def _ecdf(data: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Compute empirical CDF arrays (x, y) for one-dimensional data."""
    x = np.sort(data)
    n = x.size
    y = np.arange(1, n + 1) / n
    return x, y


def _inverse_ecdf(data: pd.Series, quantiles: np.ndarray) -> np.ndarray:
    """Compute inverse ECDF (quantile mapping) via interpolation."""
    x, y = _ecdf(data)
    return np.interp(quantiles, y, x)


def scale_data_to_same_mean_with_full_time_series(
    df: pd.DataFrame,
    df_cut: pd.DataFrame,
) -> pd.DataFrame:
    """Scale cut series by matching quantiles to the full-series distribution."""
    df_scaled = pd.DataFrame()
    for column_name in df.columns:
        x_cut, u_cut = _ecdf(df_cut[column_name])
        u_sel_orig = np.interp(df_cut[column_name], x_cut, u_cut)
        new_data = pd.DataFrame(
            _inverse_ecdf(df[column_name], u_sel_orig), columns=[column_name]
        )
        df_scaled = pd.concat([df_scaled, new_data], axis=1)

    df_scaled.index = df_cut.index
    return df_scaled







def treat_timeseries(
    df: pd.DataFrame,
    start_date: int,
    end_date: int,
    fix_monday: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Cut, optionally Monday-align, and scale a time series."""
    df_cut = cut_timeseries(df, start_date, end_date)
    if fix_monday:
        df_cut = fix_first_monday(df, df_cut, start_date)

    df_scaled = scale_data_to_same_mean_with_full_time_series(df, df_cut)
    return df, df_cut, df_scaled



def create_time_column() -> pd.DataFrame:
    """Create DA and CapDev time translation columns used by Balmorel."""
    list_s = [f"S{str(i).zfill(2)}" for i in range(1, 53)]
    list_t = [f"T{str(i).zfill(3)}" for i in range(1, 169)]
    capdev_periods = [f"{s}.{t}" for s in list_s for t in list_t]
    df = pd.DataFrame(capdev_periods, columns=["CapDev_time"])

    list_s = [f"S{str(i).zfill(3)}" for i in range(1, 365)]
    list_t = [f"T{str(i).zfill(2)}" for i in range(1, 25)]
    da_periods = [f"{s}.{t}" for s in list_s for t in list_t]
    df["DA_time"] = da_periods

    return df 



def convert_to_list_df_new(df: pd.DataFrame, name: str, user_name: str) -> pd.DataFrame:
    """Convert time-series DataFrame to Balmorel assignment lines."""
    output = []
    output_df = pd.DataFrame()

    for idx in df.index:
        sss, ttt = idx.split(".")
        for rrr in df.columns:
            value = df.loc[idx, rrr]
            output.append(f"{name}('{rrr}', '{user_name}', '{sss}', '{ttt}') = {value};")

    output_df[name] = output
    return output_df



def convert_to_list_df_annual_correction(df: pd.Series, name: str, user_name: str) -> pd.DataFrame:
    """Convert annual correction factors to Balmorel assignment lines."""
    output = []
    output_df = pd.DataFrame()

    for rrr in df.index:
        value = df.loc[rrr]
        output.append(
            f"{name}( YYY, '{rrr}', '{user_name}') = {name}( YYY, '{rrr}', '{user_name}')*{value};"
        )

    output_df[name] = output
    return output_df





def convert_to_list_df(df: pd.DataFrame, name: str, user_group: str) -> pd.DataFrame:
    """Legacy wrapper for converting DE_VAR_T and DH_VAR_T tables to line format."""
    output = []
    output_df = pd.DataFrame()

    if (name == "DE_VAR_T") or (name == "DH_VAR_T"):
        for idx in df.index:
            sss, ttt = idx.split(".")
            for rrr in df.columns:
                value = df.loc[idx, rrr]
                output.append(f"{name}('{rrr}', '{user_group}', '{sss}', '{ttt}') = {value};")

    output_df[name] = output
    return output_df




def create_list_inc(df: pd.DataFrame, name: str, filename: str, output_folder: str) -> None:
    """Write Balmorel assignment lines to a .inc file."""
    with open(os.path.join(output_folder, f"{filename}.inc"), "w") as the_file:
        the_file.write("*File created from weatheryear module")
        the_file.write("\n")
        for item in df[name]:
            the_file.write(item + "\n")

                


def calc_CapDev_timeseries(
    config: dict[str, Any],
    combined_scaled_dfs: pd.DataFrame,
    df_t: pd.DataFrame,
) -> pd.DataFrame:
    """Convert DA-scaled series to CapDev timeseries using configured timesteps."""
    capdev_timesteps = get_CapDev_timesteps(config)
    df_t_cut = df_t[df_t.CapDev_time.isin(capdev_timesteps)]

    filtered_df = combined_scaled_dfs[combined_scaled_dfs.index.isin(df_t_cut.DA_time)]
    combined_scaled_dfs.index = df_t.index
    filtered_df.index = df_t_cut.index

    df_scaled = scale_data_to_same_mean_with_full_time_series(combined_scaled_dfs, filtered_df)
    df_scaled.index = df_t_cut.CapDev_time

    return df_scaled




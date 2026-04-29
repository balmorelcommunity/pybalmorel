"""Helper functions for converting demand time series to Balmorel format."""

import os

import numpy as np
import pandas as pd

from .auxiliary_functions import (
    compute_capdev_timeseries,
    create_directory_if_needed,
    create_balmorel_time_mapping,
    filter_timeseries_by_dates,
    align_timeseries_to_first_monday,
    build_capdev_timesteps_list,
)



def _calculate_ecdf(data: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Compute empirical CDF arrays (x, y) for one-dimensional data."""
    x = np.sort(data)
    n = x.size
    y = np.arange(1, n + 1) / n
    return x, y


def _compute_inverse_quantile(data: pd.Series, quantiles: np.ndarray) -> np.ndarray:
    """Compute inverse ECDF (quantile mapping) via interpolation."""
    x, y = _calculate_ecdf(data)
    return np.interp(quantiles, y, x)


def scale_timeseries_to_full_distribution(
    df: pd.DataFrame,
    df_cut: pd.DataFrame,
) -> pd.DataFrame:
    """Scale cut series by matching quantiles to the full-series distribution."""
    df_scaled = pd.DataFrame()
    for column_name in df.columns:
        x_cut, u_cut = _calculate_ecdf(df_cut[column_name])
        u_sel_orig = np.interp(df_cut[column_name], x_cut, u_cut)
        new_data = pd.DataFrame(
            _compute_inverse_quantile(df[column_name], u_sel_orig), columns=[column_name]
        )
        df_scaled = pd.concat([df_scaled, new_data], axis=1)

    df_scaled.index = df_cut.index
    return df_scaled


def process_timeseries_with_scaling(
    df: pd.DataFrame,
    start_date: int,
    end_date: int,
    fix_monday: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Cut, optionally Monday-align, and scale a time series."""
    df_cut = filter_timeseries_by_dates(df, start_date, end_date)
    if fix_monday:
        df_cut = align_timeseries_to_first_monday(df, df_cut, start_date)

    df_scaled = scale_timeseries_to_full_distribution(df, df_cut)
    return df, df_cut, df_scaled



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




def build_inc_file_list_type(df: pd.DataFrame, name: str, filename: str, output_folder: str) -> None:
    """Write Balmorel assignment lines to a .inc file."""
    with open(os.path.join(output_folder, f"{filename}.inc"), "w") as the_file:
        the_file.write("*File created from weatheryear module")
        the_file.write("\n")
        for item in df[name]:
            the_file.write(item + "\n")

                




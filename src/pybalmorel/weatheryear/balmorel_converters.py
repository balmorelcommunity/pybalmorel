"""Unified converters for Balmorel time-series and factor assignment lines.

This module provides consolidated conversion functions used by demand2btc.py
and hydro_to_btc.py to transform DataFrames into Balmorel GAMS assignment
strings and handle raw/scaled CSV output.
"""

import os

import pandas as pd

from .auxiliary_functions import create_directory_if_needed


def apply_balmorel_da_time_index(df: pd.DataFrame, time_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a time series with Balmorel DA index applied.

    Args:
        df: DataFrame with original time index.
        time_df: DataFrame with Balmorel DA time index (must contain 'DA_time' column).

    Returns:
        A DataFrame with the Balmorel DA time index applied.
    """
    indexed_df = df.copy()
    indexed_df.index = time_df["DA_time"]
    return indexed_df


def to_balmorel_timeseries_assignment_lines(
    df: pd.DataFrame, symbol: str, user_name: str | None = None
) -> pd.DataFrame:
    """Convert time-series DataFrame to Balmorel assignment lines.

    Handles multi-dimensional (region, season, time) indexing by parsing the
    DataFrame index as "season.time" strings.

    Args:
        df: Time-series DataFrame indexed by "season.time" (e.g., "S01.T001"),
            with region/area names as columns.
        symbol: Balmorel symbol name (e.g., 'DE_VAR_T', 'RE_CAP_DISP').
        user_name: Optional user group name for demand symbols (e.g., 'RESE', 'RESIDENTIAL').
                   If None, omits the user dimension from the assignment.

    Returns:
        DataFrame with a single column (symbol) containing GAMS assignment strings.
    """
    output = []

    for idx in df.index:
        sss, ttt = idx.split(".")
        for region in df.columns:
            value = df.loc[idx, region]
            if user_name:
                assignment = f"{symbol}('{region}', '{user_name}', '{sss}', '{ttt}') = {value};"
            else:
                assignment = f"{symbol}('{region}', '{sss}', '{ttt}') = {value};"
            output.append(assignment)

    return pd.DataFrame({symbol: output})


def to_balmorel_factor_assignment_lines(
    series: pd.Series, symbol: str, user_name: str | None = None
) -> pd.DataFrame:
    """Convert scalar/annual factor Series to Balmorel assignment lines.

    Used for annual correction factors and FLH factors indexed by region/area.

    Args:
        series: Series indexed by region/area names, values are scalar factors.
        symbol: Balmorel symbol name (e.g., 'DH', 'RES_FLH').
        user_name: Optional user group name for demand symbols.
                   If None, generates region-only assignments.

    Returns:
        DataFrame with a single column (symbol) containing GAMS assignment strings.
    """
    output = []

    for region in series.index:
        value = series.loc[region]
        if user_name:
            # Annual correction format: multiply existing value
            assignment = f"{symbol}( YYY, '{region}', '{user_name}') = {symbol}( YYY, '{region}', '{user_name}')*{value};"
        else:
            # FLH factor format: direct assignment
            assignment = f"{symbol}('{region}') = {value};"
        output.append(assignment)

    return pd.DataFrame({symbol: output})


def to_balmorel_technology_factor_assignment_lines(
    series: pd.Series, symbol: str, technology_name: str
) -> pd.DataFrame:
    """Convert annual technology factors to Balmorel assignment lines.

    Used for factors indexed by region/area that modify a region-technology
    parameter, such as COP adjustments.

    Args:
        series: Series indexed by region/area names, values are scalar factors.
        symbol: Balmorel symbol name (e.g., 'COP').
        technology_name: Technology identifier used as second symbol dimension.

    Returns:
        DataFrame with a single column (symbol) containing GAMS assignment strings.
    """
    output = []

    for region in series.index:
        value = series.loc[region]
        assignment = (
            f"{symbol}('{region}', '{technology_name}') = "
            f"{symbol}('{region}', '{technology_name}')*{value};"
        )
        output.append(assignment)

    return pd.DataFrame({symbol: output})


def prepare_balmorel_output_dirs(
    year_output_folder: str,
) -> tuple[str, str, str, str, str]:
    """Create and return the standard Balmorel output directories for one weather year.

    All five subdirectories are created under ``<year_output_folder>/to_balmorel/``.

    Args:
        year_output_folder: Root output folder for the year (e.g., ``output/2012``).

    Returns:
        Tuple of
        ``(dispatch_raw_folder, dispatch_scaled_folder,
        capdev_scaled_long_term_folder, capdev_scaled_full_year_folder,
        capdev_raw_folder)``.
    """
    to_balmorel = os.path.join(year_output_folder, "to_balmorel")
    dispatch_raw = os.path.join(to_balmorel, "HourlyDispatch", "raw")
    dispatch_scaled = os.path.join(to_balmorel, "HourlyDispatch", "scaled_long_term")
    capdev_scaled_long_term = os.path.join(to_balmorel, "CapDev", "scaled_long_term")
    capdev_scaled_full_year = os.path.join(to_balmorel, "CapDev", "scaled_full_year")
    capdev_raw = os.path.join(to_balmorel, "CapDev", "raw")

    for folder in (
        year_output_folder,
        dispatch_raw,
        dispatch_scaled,
        capdev_scaled_long_term,
        capdev_scaled_full_year,
        capdev_raw,
    ):
        create_directory_if_needed(folder)

    return dispatch_raw, dispatch_scaled, capdev_scaled_long_term, capdev_scaled_full_year, capdev_raw


def write_raw_and_scaled_csv(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    output_folder: str,
    subfolder_name: str,
    csv_name: str,
    include_flh_sum: bool = False,
) -> None:
    """Persist raw and scaled time-series CSV outputs.

    Optionally writes FLH (Full Load Hours) sum files for hydro inflow data.

    Args:
        df_raw: DataFrame with raw hourly time series.
        df_scaled: DataFrame with scaled hourly time series.
        output_folder: Root output folder for the year.
        subfolder_name: Name of the subfolder (e.g., 'classic_elec', 'res_inflow').
        csv_name: Name of the CSV file to save.
        include_flh_sum: If True, also write sum aggregates as '_FLH.csv' files (for hydro).
    """
    raw_folder = os.path.join(output_folder, subfolder_name, "raw")
    scaled_folder = os.path.join(output_folder, subfolder_name, "scaled")

    create_directory_if_needed(raw_folder)
    create_directory_if_needed(scaled_folder)

    df_raw.to_csv(os.path.join(raw_folder, csv_name))
    df_scaled.to_csv(os.path.join(scaled_folder, csv_name))

    if include_flh_sum:
        csv_stem = os.path.splitext(csv_name)[0]
        df_raw.sum().to_csv(os.path.join(raw_folder, f"{csv_stem}_FLH.csv"))
        df_scaled.sum().to_csv(os.path.join(scaled_folder, f"{csv_stem}_FLH.csv"))

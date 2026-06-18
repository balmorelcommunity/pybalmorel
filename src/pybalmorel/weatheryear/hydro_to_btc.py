"""Create Balmorel hydro .inc files from hydro-model CSV outputs.

This module converts reservoir and run-of-river inflow time series into
HourlyDispatch and CapDev formats and writes annual/long-term FLH-factor
.inc files used by Balmorel.
"""

import os

import pandas as pd

from .auxiliary_functions import (
    compute_capdev_timeseries,
    create_balmorel_time_mapping,
    create_directory_if_needed,
    process_timeseries_with_scaling,
)
from .balmorel_converters import (
    apply_balmorel_da_time_index,
    prepare_balmorel_output_dirs,
    to_balmorel_timeseries_assignment_lines,
    to_balmorel_factor_assignment_lines,
    write_raw_and_scaled_csv,
)
from .config_models import HydroModuleConfig
from .to_inc import build_inc_file_list_type





def _write_hydro_timeseries_inc_files(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    symbol: str,
    csv_name: str,
    hd_raw_folder: str,
    hd_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
    config: HydroModuleConfig,
    time_df: pd.DataFrame,
) -> None:
    """Write HourlyDispatch and CapDev hydro .inc files for one hydro symbol."""
    dispatch_cases = [
        (df_raw, hd_raw_folder),
        (df_scaled, hd_scaled_folder),
    ]
    for src_df, output_folder in dispatch_cases:
        df = to_balmorel_timeseries_assignment_lines(src_df, symbol)
        build_inc_file_list_type(df, symbol, output_folder, filename=f"{symbol}_WY")
        src_df.to_csv(os.path.join(output_folder, csv_name))

    capdev_cases = [
        (df_scaled, True, capdev_scaled_long_term_folder),
        (df_raw, True, capdev_scaled_full_year_folder),
        (df_raw, False, capdev_raw_folder),
    ]
    capdev_timesteps = config.capdev_timesteps_to_keep.as_legacy_dict()
    for src_df, scale, output_folder in capdev_cases:
        capdev_df = compute_capdev_timeseries(
            capdev_timesteps,
            src_df,
            time_df,
            source="hydro",
            scale=scale,
        )
        df = to_balmorel_timeseries_assignment_lines(capdev_df, symbol)
        build_inc_file_list_type(df, symbol, output_folder, filename=f"{symbol}_WY")
        capdev_df.to_csv(os.path.join(output_folder, csv_name))


def _process_hydro_inflow_series(
    df_inflow: pd.DataFrame,
    year: int,
    symbol: str,
    csv_name: str,
    subfolder_name: str,
    year_output_folder: str,
    hd_raw_folder: str,
    hd_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
    config: HydroModuleConfig,
) -> None:
    """Process one hydro inflow series and write corresponding Balmorel files."""
    _, df_cut, df_scaled = process_timeseries_with_scaling(
        df_inflow,
        year,
        year,
        source="hydro",
        fix_monday=True,
    )
    write_raw_and_scaled_csv(
        df_raw=df_cut,
        df_scaled=df_scaled,
        output_folder=year_output_folder,
        subfolder_name=subfolder_name,
        csv_name=csv_name,
        include_flh_sum=True,
    )

    time_df = create_balmorel_time_mapping()
    df_cut = apply_balmorel_da_time_index(df_cut, time_df)
    df_scaled = apply_balmorel_da_time_index(df_scaled, time_df)

    _write_hydro_timeseries_inc_files(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol=symbol,
        csv_name=csv_name,
        hd_raw_folder=hd_raw_folder,
        hd_scaled_folder=hd_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
        time_df=time_df,
    )


def _write_flh_inc_files(
    yearly_flh_series: pd.Series,
    long_term_flh_series: pd.Series,
    symbol: str,
    csv_name: str,
    hd_raw_folder: str,
    hd_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
) -> None:
    """Write annual and long-term hydro FLH-factor .inc and CSV outputs."""
    df = to_balmorel_factor_assignment_lines(yearly_flh_series, symbol)

    build_inc_file_list_type(df, symbol, capdev_scaled_full_year_folder, filename=f"{symbol}_WY")
    build_inc_file_list_type(df, symbol, capdev_raw_folder, filename=f"{symbol}_WY")
    build_inc_file_list_type(df, symbol, hd_raw_folder, filename=f"{symbol}_WY")

    yearly_flh_series.to_csv(os.path.join(capdev_scaled_full_year_folder, csv_name))
    yearly_flh_series.to_csv(os.path.join(capdev_raw_folder, csv_name))
    yearly_flh_series.to_csv(os.path.join(hd_raw_folder, csv_name))

    df = to_balmorel_factor_assignment_lines(long_term_flh_series, symbol)
    build_inc_file_list_type(df, symbol, capdev_scaled_long_term_folder, filename=f"{symbol}_WY")
    build_inc_file_list_type(df, symbol, hd_scaled_folder, filename=f"{symbol}_WY")

    long_term_flh_series.to_csv(os.path.join(capdev_scaled_long_term_folder, csv_name))
    long_term_flh_series.to_csv(os.path.join(hd_scaled_folder, csv_name))




def create_hydro_inc(config_fn: str, year: int, output_folder: str) -> None:
    """Create hydro-related Balmorel .inc files for one weather year.

    Args:
        config_fn: Path to YAML config file.
        year: Weather year to process.
        output_folder: Root output directory.
    """
    config = HydroModuleConfig.from_file(config_fn)
    csv_folder = config.hydro_model_results

    df_inflow_res = pd.read_csv(
        os.path.join(csv_folder, "res_inflow.csv"), index_col=0, parse_dates=True
    )
    df_inflow_ror = pd.read_csv(
        os.path.join(csv_folder, "ror_inflow.csv"), index_col=0, parse_dates=True
    )
    df_res_flh_factors = pd.read_csv(
        os.path.join(csv_folder, "res_inflow_flh_fac.csv"), index_col=0, parse_dates=True
    )
    df_ror_flh_factors = pd.read_csv(
        os.path.join(csv_folder, "ror_inflow_flh_fac.csv"), index_col=0, parse_dates=True
    )

    year_output_folder = os.path.join(output_folder, str(year))
    (
        hd_raw_folder,
        hd_scaled_folder,
        capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder,
        capdev_raw_folder,
    ) = prepare_balmorel_output_dirs(year_output_folder)

    # Reservoir inflow (WTRRSVAR_S)
    _process_hydro_inflow_series(
        df_inflow=df_inflow_res,
        year=year,
        symbol="WTRRSVAR_S",
        csv_name="res_inflow.csv",
        subfolder_name="res_inflow",
        year_output_folder=year_output_folder,
        hd_raw_folder=hd_raw_folder,
        hd_scaled_folder=hd_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
    )

    # Run-of-river inflow (WTRRRVAR_T)
    _process_hydro_inflow_series(
        df_inflow=df_inflow_ror,
        year=year,
        symbol="WTRRRVAR_T",
        csv_name="ror_inflow.csv",
        subfolder_name="ror_inflow",
        year_output_folder=year_output_folder,
        hd_raw_folder=hd_raw_folder,
        hd_scaled_folder=hd_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
    )

    # FLH factors
    res_flh_year = df_res_flh_factors.loc[str(year)].iloc[0]
    res_flh_long_term = df_res_flh_factors.mean()
    _write_flh_inc_files(
        yearly_flh_series=res_flh_year,
        long_term_flh_series=res_flh_long_term,
        symbol="WTRRSFLH",
        csv_name="res_inflow_flh.csv",
        hd_raw_folder=hd_raw_folder,
        hd_scaled_folder=hd_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
    )

    ror_flh_year = df_ror_flh_factors.loc[str(year)].iloc[0]
    ror_flh_long_term = df_ror_flh_factors.mean()
    _write_flh_inc_files(
        yearly_flh_series=ror_flh_year,
        long_term_flh_series=ror_flh_long_term,
        symbol="WTRRRFLH",
        csv_name="ror_inflow_flh.csv",
        hd_raw_folder=hd_raw_folder,
        hd_scaled_folder=hd_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
    )

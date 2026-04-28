"""Create Balmorel demand .inc files from demand-model CSV outputs.

This module converts electricity and heat demand time series into Balmorel DA and
CapDev formats and writes annual correction-factor .inc files for DH users.
"""

import os
from typing import Any

import pandas as pd
import yaml

from .functions_demand_to_btc import (
    check_if_dir_exists,
    convert_to_list_df_annual_correction,
    convert_to_list_df_new,
    create_list_inc,
    create_time_column,
    get_CapDev_timesteps,
    scale_data_to_same_mean_with_full_time_series,
    treat_timeseries,
)


def _build_capdev_scaled(df_scaled: pd.DataFrame, time_df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Create CapDev-resolution scaled series from DA-resolution scaled series."""
    capdev_timesteps = get_CapDev_timesteps(config)
    df_t_cut = time_df[time_df.CapDev_time.isin(capdev_timesteps)]
    filtered_df = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev = scale_data_to_same_mean_with_full_time_series(df_scaled, filtered_df)
    df_scaled_capdev.index = df_t_cut.CapDev_time
    return df_scaled_capdev


def _write_var_t_inc(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    symbol: str,
    user_name: str,
    filename: str,
    da_raw_folder: str,
    da_scaled_folder: str,
    capdev_folder: str,
    config: dict[str, Any],
    time_df: pd.DataFrame,
) -> None:
    """Write DA raw/scaled and CapDev .inc files for one demand user group."""
    df = convert_to_list_df_new(df_raw, symbol, user_name)
    create_list_inc(df, symbol, filename, da_raw_folder)

    df = convert_to_list_df_new(df_scaled, symbol, user_name)
    create_list_inc(df, symbol, filename, da_scaled_folder)

    df_scaled_capdev = _build_capdev_scaled(df_scaled, time_df, config)
    df = convert_to_list_df_new(df_scaled_capdev, symbol, user_name)
    create_list_inc(df, symbol, filename, capdev_folder)


def _prepare_common_output_dirs(year_output_folder: str) -> tuple[str, str, str]:
    """Create and return common Balmorel output directories for one weather year."""
    da_raw_folder = os.path.join(year_output_folder, "to_balmorel", "DA", "raw")
    da_scaled_folder = os.path.join(year_output_folder, "to_balmorel", "DA", "scaled")
    capdev_folder = os.path.join(year_output_folder, "to_balmorel", "CapDev")

    check_if_dir_exists(year_output_folder)
    check_if_dir_exists(da_raw_folder)
    check_if_dir_exists(da_scaled_folder)
    check_if_dir_exists(capdev_folder)
    return da_raw_folder, da_scaled_folder, capdev_folder


def create_demand_inc(config_fn: str, year: int, output_folder: str) -> None:
    """Create demand-related Balmorel .inc files for one weather year.

    Args:
        config_fn: Path to YAML config file.
        year: Weather year to process.
        output_folder: Root output directory.
    """
    with open(config_fn) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    spaceheat_to_hotwater_ratio = config["spaceHeat_to_hotWater_ratio"]
    ann_corr_fac_ref_year = int(config["ann_corr_fac_ref_year"])
    csv_folder = config["demand_model_results"]

    df_classic = pd.read_csv(
        os.path.join(csv_folder, "classic_demand.csv"), index_col=0, parse_dates=True
    )
    df_space_heat_profile = pd.read_csv(
        os.path.join(csv_folder, "heat_profile_indiv_user.csv"), index_col=0, parse_dates=True
    )
    df_resh_heat_profile = pd.read_csv(
        os.path.join(csv_folder, "heat_profile_resh.csv"), index_col=0, parse_dates=True
    )
    df_resh_hotwater_profile = pd.read_csv(
        os.path.join(csv_folder, "hotWater_profile_resh.csv"), index_col=0
    )
    df_heat_corr_factors_indiv_user = pd.read_csv(
        os.path.join(csv_folder, "heat_yearly_corr_factors_indiv_user.csv"), index_col=0
    )
    df_heat_corr_factors_resh = pd.read_csv(
        os.path.join(csv_folder, "heat_yearly_corr_factors_resh.csv"), index_col=0
    )

    year_output_folder = os.path.join(output_folder, str(year))
    da_raw_folder, da_scaled_folder, capdev_folder = _prepare_common_output_dirs(year_output_folder)

    # Electricity demand
    _, df_cut, df_scaled = treat_timeseries(df_classic, year, year, fix_monday=True)

    classic_elec_raw_folder = os.path.join(year_output_folder, "classic_elec", "raw")
    classic_elec_scaled_folder = os.path.join(year_output_folder, "classic_elec", "scaled")
    check_if_dir_exists(classic_elec_raw_folder)
    check_if_dir_exists(classic_elec_scaled_folder)
    df_cut.to_csv(os.path.join(classic_elec_raw_folder, "classic_elec.csv"))
    df_scaled.to_csv(os.path.join(classic_elec_scaled_folder, "classic_elec.csv"))

    time_df = create_time_column()
    df_cut.index = time_df["DA_time"]
    df_scaled.index = time_df["DA_time"]

    _write_var_t_inc(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DE_VAR_T",
        user_name="RESE",
        filename="DE_VAR_T_RESE",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_folder=capdev_folder,
        config=config,
        time_df=time_df,
    )
    _write_var_t_inc(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DE_VAR_T",
        user_name="OTHER",
        filename="DE_VAR_T_OTHER",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_folder=capdev_folder,
        config=config,
        time_df=time_df,
    )

    # Heat demand: individual users
    _, df_cut, df_scaled = treat_timeseries(df_space_heat_profile, year, year, fix_monday=True)

    indiv_raw_folder = os.path.join(year_output_folder, "heat_profile_indiv_user", "raw")
    indiv_scaled_folder = os.path.join(year_output_folder, "heat_profile_indiv_user", "scaled")
    check_if_dir_exists(indiv_raw_folder)
    check_if_dir_exists(indiv_scaled_folder)
    df_cut.to_csv(os.path.join(indiv_raw_folder, "heat_profile_indiv_user.csv"))
    df_scaled.to_csv(os.path.join(indiv_scaled_folder, "heat_profile_indiv_user.csv"))

    time_df = create_time_column()
    df_cut.index = time_df["DA_time"]
    df_scaled.index = time_df["DA_time"]

    _write_var_t_inc(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DH_VAR_T",
        user_name="RESIDENTIAL",
        filename="DH_VAR_T_RESIDENTIAL",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_folder=capdev_folder,
        config=config,
        time_df=time_df,
    )
    _write_var_t_inc(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DH_VAR_T",
        user_name="TERTIARY",
        filename="DH_VAR_T_TERTIARY",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_folder=capdev_folder,
        config=config,
        time_df=time_df,
    )

    # Heat demand: RESH (space heat blended with hot-water profile)
    _, df_cut, df_scaled = treat_timeseries(df_resh_heat_profile, year, year, fix_monday=True)

    resh_raw_folder = os.path.join(year_output_folder, "heat_profile_resh", "raw")
    resh_scaled_folder = os.path.join(year_output_folder, "heat_profile_resh", "scaled")
    check_if_dir_exists(resh_raw_folder)
    check_if_dir_exists(resh_scaled_folder)

    time_df = create_time_column()
    df_cut.index = time_df["DA_time"]
    df_scaled.index = time_df["DA_time"]
    df_resh_hotwater_profile.index = time_df["DA_time"]

    df_cut = (
        df_cut * spaceheat_to_hotwater_ratio
        + df_resh_hotwater_profile * (1 - spaceheat_to_hotwater_ratio)
    )
    df_scaled = (
        df_scaled * spaceheat_to_hotwater_ratio
        + df_resh_hotwater_profile * (1 - spaceheat_to_hotwater_ratio)
    )

    _write_var_t_inc(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DH_VAR_T",
        user_name="RESH",
        filename="DH_VAR_T_RESH",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_folder=capdev_folder,
        config=config,
        time_df=time_df,
    )

    # Annual DH correction factors
    to_balmorel_folder = os.path.join(year_output_folder, "to_balmorel")
    df_heat_corr_factor_year = (
        df_heat_corr_factors_indiv_user.loc[year]
        / df_heat_corr_factors_indiv_user.loc[ann_corr_fac_ref_year]
    )
    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year, "DH", "RESIDENTIAL")
    create_list_inc(df, "DH", "DH_RESIDENTIAL", to_balmorel_folder)

    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year, "DH", "TERTIARY")
    create_list_inc(df, "DH", "DH_TERTIARY", to_balmorel_folder)

    df_heat_corr_factor_year = (
        df_heat_corr_factors_resh.loc[year]
        / df_heat_corr_factors_resh.loc[ann_corr_fac_ref_year]
    )
    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year, "DH", "RESH")
    create_list_inc(df, "DH", "DH_RESH", to_balmorel_folder)
    df_heat_corr_factor_year = df_heat_corr_factors_resh.loc[year]/df_heat_corr_factors_resh.loc[ann_corr_fac_ref_year]

    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year,'DH','RESH')
    create_list_inc(df,'DH','DH_RESH',output_folder+'/'+str(year)+'/to_balmorel/')











































"""Create Balmorel demand .inc files from demand-model CSV outputs.

This module converts electricity and heat demand time series into Balmorel DA and
CapDev formats and writes annual correction-factor .inc files for DH users.
"""

import os

import pandas as pd

from .auxiliary_functions import compute_capdev_timeseries
from .config_models import DemandModuleConfig
from .functions_demand_to_btc import (
    create_directory_if_needed,
    convert_to_list_df_annual_correction,
    convert_to_list_df_new,
    build_inc_file_list_type,
    create_balmorel_time_mapping,
    scale_timeseries_to_full_distribution,
    process_timeseries_with_scaling,
)


def _write_demand_timeseries_inc_files(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    symbol: str,
    user_name: str,
    filename: str,
    da_raw_folder: str,
    da_scaled_folder: str,
    capdev_folder: str,
    config: DemandModuleConfig,
    time_df: pd.DataFrame,
) -> None:
    """Write DA raw/scaled and CapDev .inc files for one demand user group."""
    df = convert_to_list_df_new(df_raw, symbol, user_name)
    build_inc_file_list_type(df, symbol, filename, da_raw_folder)

    df = convert_to_list_df_new(df_scaled, symbol, user_name)
    build_inc_file_list_type(df, symbol, filename, da_scaled_folder)

    df_scaled_capdev = compute_capdev_timeseries(
        config.capdev_timesteps_to_keep.as_legacy_dict(),
        df_scaled,
        time_df,
        scaler=scale_timeseries_to_full_distribution,
    )
    df = convert_to_list_df_new(df_scaled_capdev, symbol, user_name)
    build_inc_file_list_type(df, symbol, filename, capdev_folder)


def _prepare_common_output_dirs(year_output_folder: str) -> tuple[str, str, str]:
    """Create and return common Balmorel output directories for one weather year."""
    da_raw_folder = os.path.join(year_output_folder, "to_balmorel", "DA", "raw")
    da_scaled_folder = os.path.join(year_output_folder, "to_balmorel", "DA", "scaled")
    capdev_folder = os.path.join(year_output_folder, "to_balmorel", "CapDev")

    create_directory_if_needed(year_output_folder)
    create_directory_if_needed(da_raw_folder)
    create_directory_if_needed(da_scaled_folder)
    create_directory_if_needed(capdev_folder)
    return da_raw_folder, da_scaled_folder, capdev_folder


def generate_demand_balmorel_inc_files(config_fn: str, year: int, output_folder: str) -> None:
    """Create demand-related Balmorel .inc files for one weather year.

    Args:
        config_fn: Path to YAML config file.
        year: Weather year to process.
        output_folder: Root output directory.
    """
    config = DemandModuleConfig.from_file(config_fn)

    spaceheat_to_hotwater_ratio = config.spaceheat_to_hotwater_ratio
    ann_corr_fac_ref_year = config.ann_corr_fac_ref_year
    csv_folder = config.demand_model_results

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
    _, df_cut, df_scaled = process_timeseries_with_scaling(df_classic, year, year, fix_monday=True)

    classic_elec_raw_folder = os.path.join(year_output_folder, "classic_elec", "raw")
    classic_elec_scaled_folder = os.path.join(year_output_folder, "classic_elec", "scaled")
    create_directory_if_needed(classic_elec_raw_folder)
    create_directory_if_needed(classic_elec_scaled_folder)
    df_cut.to_csv(os.path.join(classic_elec_raw_folder, "classic_elec.csv"))
    df_scaled.to_csv(os.path.join(classic_elec_scaled_folder, "classic_elec.csv"))

    time_df = create_balmorel_time_mapping()
    df_cut.index = time_df["DA_time"]
    df_scaled.index = time_df["DA_time"]

    _write_demand_timeseries_inc_files(
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
    _write_demand_timeseries_inc_files(
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
    _, df_cut, df_scaled = process_timeseries_with_scaling(df_space_heat_profile, year, year, fix_monday=True)

    indiv_raw_folder = os.path.join(year_output_folder, "heat_profile_indiv_user", "raw")
    indiv_scaled_folder = os.path.join(year_output_folder, "heat_profile_indiv_user", "scaled")
    create_directory_if_needed(indiv_raw_folder)
    create_directory_if_needed(indiv_scaled_folder)
    df_cut.to_csv(os.path.join(indiv_raw_folder, "heat_profile_indiv_user.csv"))
    df_scaled.to_csv(os.path.join(indiv_scaled_folder, "heat_profile_indiv_user.csv"))

    time_df = create_balmorel_time_mapping()
    df_cut.index = time_df["DA_time"]
    df_scaled.index = time_df["DA_time"]

    _write_demand_timeseries_inc_files(
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
    _write_demand_timeseries_inc_files(
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
    _, df_cut, df_scaled = process_timeseries_with_scaling(df_resh_heat_profile, year, year, fix_monday=True)

    resh_raw_folder = os.path.join(year_output_folder, "heat_profile_resh", "raw")
    resh_scaled_folder = os.path.join(year_output_folder, "heat_profile_resh", "scaled")
    create_directory_if_needed(resh_raw_folder)
    create_directory_if_needed(resh_scaled_folder)

    time_df = create_balmorel_time_mapping()
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

    _write_demand_timeseries_inc_files(
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
    build_inc_file_list_type(df, "DH", "DH_RESIDENTIAL", to_balmorel_folder)

    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year, "DH", "TERTIARY")
    build_inc_file_list_type(df, "DH", "DH_TERTIARY", to_balmorel_folder)

    df_heat_corr_factor_year = (
        df_heat_corr_factors_resh.loc[year]
        / df_heat_corr_factors_resh.loc[ann_corr_fac_ref_year]
    )
    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year, "DH", "RESH")
    build_inc_file_list_type(df, "DH", "DH_RESH", to_balmorel_folder)











































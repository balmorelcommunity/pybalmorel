"""Create Balmorel demand .inc files from demand-model CSV outputs.

This module converts electricity and heat demand time series into Balmorel DA and
CapDev formats and writes annual correction-factor .inc files for DH users.
"""

import os

import pandas as pd

from .auxiliary_functions import (
    compute_capdev_timeseries,
    create_directory_if_needed,
    create_balmorel_time_mapping,
    process_timeseries_with_scaling,
    scale_timeseries_to_full_distribution
)
from .balmorel_converters import (
    apply_balmorel_da_time_index,
    prepare_balmorel_output_dirs,
    to_balmorel_timeseries_assignment_lines,
    to_balmorel_factor_assignment_lines,
    write_raw_and_scaled_csv,
)
from .config_models import DemandModuleConfig
from .to_inc import build_inc_file_list_type


def _load_individual_heat_profiles(csv_folder: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load individual-user heat profiles for residential and tertiary demand."""
    combined_path = os.path.join(csv_folder, "heat_profile_indiv_user.csv")
    if os.path.exists(combined_path):
        combined = pd.read_csv(combined_path, index_col=0, parse_dates=True)
        return combined.copy(), combined.copy()

    residential_path = os.path.join(csv_folder, "heat_profile_indiv_user_residential.csv")
    tertiary_path = os.path.join(csv_folder, "heat_profile_indiv_user_tertiary.csv")
    return (
        pd.read_csv(residential_path, index_col=0, parse_dates=True),
        pd.read_csv(tertiary_path, index_col=0, parse_dates=True),
    )


def _load_individual_heat_correction_factors(csv_folder: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load annual correction factors for residential and tertiary individual users."""
    combined_path = os.path.join(csv_folder, "heat_yearly_corr_factors_indiv_user.csv")
    if os.path.exists(combined_path):
        combined = pd.read_csv(combined_path, index_col=0)
        return combined.copy(), combined.copy()

    residential_path = os.path.join(csv_folder, "heat_yearly_corr_factors_indiv_user_residential.csv")
    tertiary_path = os.path.join(csv_folder, "heat_yearly_corr_factors_indiv_user_tertiary.csv")
    return (
        pd.read_csv(residential_path, index_col=0),
        pd.read_csv(tertiary_path, index_col=0),
    )


def _process_individual_heat_user(
    df_space_heat_profile: pd.DataFrame,
    year: int,
    user_name: str,
    subfolder_name: str,
    filename: str,
    year_output_folder: str,
    da_raw_folder: str,
    da_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
    config: DemandModuleConfig,
) -> None:
    """Process one individual-user heat profile and export Balmorel files."""
    _, df_cut, df_scaled = process_timeseries_with_scaling(
        df_space_heat_profile,
        year,
        year,
        "demand",
        fix_monday=True,
    )

    write_raw_and_scaled_csv(
        df_raw=df_cut,
        df_scaled=df_scaled,
        output_folder=year_output_folder,
        subfolder_name=subfolder_name,
        csv_name=f"{subfolder_name}.csv",
    )

    time_df = create_balmorel_time_mapping()
    df_cut = apply_balmorel_da_time_index(df_cut, time_df)
    df_scaled = apply_balmorel_da_time_index(df_scaled, time_df)

    _write_demand_timeseries_inc_files(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DH_VAR_T",
        user_name=user_name,
        filename=filename,
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
        time_df=time_df,
    )





def _blend_space_heat_and_hotwater(
    space_heat_df: pd.DataFrame,
    hotwater_df: pd.DataFrame,
    spaceheat_to_hotwater_ratio: float,
) -> pd.DataFrame:
    """Blend space-heat and hot-water profiles using a fixed annual ratio.
    Args:
        space_heat_df: DataFrame with space-heat time series.
        hotwater_df: DataFrame with hot-water time series.
        spaceheat_to_hotwater_ratio: The ratio of space heat to hot water.
    Returns:
        A DataFrame with the blended time series."""
    return (
        space_heat_df * spaceheat_to_hotwater_ratio
        + hotwater_df * (1 - spaceheat_to_hotwater_ratio)
    )


def _annual_correction_factor_for_year(
    correction_factors_df: pd.DataFrame,
    year: int,
    reference_year: int,
) -> pd.Series:
    """Compute annual correction factor for one year relative to a reference year.
    Args:
        correction_factors_df: DataFrame with annual correction factors indexed by year.
        year: The year for which to compute the correction factor.
        reference_year: The reference year for comparison.
    Returns:
        A Series containing the correction factors for the specified year.
    """
    return correction_factors_df.loc[year] / correction_factors_df.loc[reference_year]





def _write_demand_timeseries_inc_files(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    symbol: str,
    user_name: str,
    filename: str,
    da_raw_folder: str,
    da_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
    config: DemandModuleConfig,
    time_df: pd.DataFrame,
) -> None:
    """Write DA raw/scaled and CapDev .inc files for one demand user group.
    Args:
        df_raw: DataFrame with raw hourly time series.
        df_scaled: DataFrame with scaled hourly time series.
        symbol: Symbol for the demand user group.
        user_name: Name of the demand user group.
        filename: Name of the .inc file to save.
        da_raw_folder: Path to the folder for raw DA files.
        da_scaled_folder: Path to the folder for scaled DA files.
        capdev_scaled_long_term_folder: Path to the scaled long-term CapDev folder.
        capdev_scaled_full_year_folder: Path to the scaled full-year CapDev folder.
        capdev_raw_folder: Path to the raw CapDev folder.
        config: Configuration object for the demand module.
        time_df: DataFrame with Balmorel DA time index.
    """
    df = to_balmorel_timeseries_assignment_lines(df_raw, symbol, user_name)
    build_inc_file_list_type(df, symbol, da_raw_folder, filename=filename)

    df = to_balmorel_timeseries_assignment_lines(df_scaled, symbol, user_name)
    build_inc_file_list_type(df, symbol, da_scaled_folder, filename=filename)

    capdev_cases = [
        (df_scaled, True,  capdev_scaled_long_term_folder),
        (df_raw,    True,  capdev_scaled_full_year_folder),
        (df_raw,    False, capdev_raw_folder),
    ]
    capdev_config = config.capdev_timesteps_to_keep.as_legacy_dict()
    for src_df, scale, output_folder in capdev_cases:
        capdev_df = compute_capdev_timeseries(capdev_config, src_df, time_df, source="demand", scale=scale)
        df = to_balmorel_timeseries_assignment_lines(capdev_df, symbol, user_name)
        build_inc_file_list_type(df, symbol, output_folder, filename=filename)



def generate_demand_balmorel_inc_files(config_fn: str, year: int, output_folder: str) -> None:
    """Create demand-related Balmorel .inc files for one weather year.
    Args:
        config_fn: Path to YAML config file.
        year: Weather year to process.
        output_folder: Root output directory.
    """
    # Load configuration and input CSVs
    config = DemandModuleConfig.from_file(config_fn)

    spaceheat_to_hotwater_ratio = config.spaceheat_to_hotwater_ratio
    ann_corr_fac_ref_year = config.ann_corr_fac_ref_year
    csv_folder = config.demand_model_results

    df_classic = pd.read_csv(
        os.path.join(csv_folder, "classic_demand.csv"), index_col=0, parse_dates=True
    )
    df_space_heat_profile_residential, df_space_heat_profile_tertiary = _load_individual_heat_profiles(csv_folder)
    df_resh_heat_profile = pd.read_csv(
        os.path.join(csv_folder, "heat_profile_resh.csv"), index_col=0, parse_dates=True
    )
    df_resh_hotwater_profile = pd.read_csv(
        os.path.join(csv_folder, "hotwater_profile_resh.csv"), index_col=0
    )
    (
        df_heat_corr_factors_indiv_user_residential,
        df_heat_corr_factors_indiv_user_tertiary,
    ) = _load_individual_heat_correction_factors(csv_folder)
    df_heat_corr_factors_resh = pd.read_csv(
        os.path.join(csv_folder, "heat_yearly_corr_factors_resh.csv"), index_col=0
    )
    
    year_output_folder = os.path.join(output_folder, str(year))
    (
        da_raw_folder,
        da_scaled_folder,
        capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder,
        capdev_raw_folder,
    ) = prepare_balmorel_output_dirs(year_output_folder)

    # Electricity demand: individual users
    _, df_cut, df_scaled = process_timeseries_with_scaling(df_classic, year, year, "demand", fix_monday=True)

    write_raw_and_scaled_csv(
        df_raw=df_cut,
        df_scaled=df_scaled,
        output_folder=year_output_folder,
        subfolder_name="classic_elec",
        csv_name="classic_elec.csv",
    )

    time_df = create_balmorel_time_mapping()
    df_cut = apply_balmorel_da_time_index(df_cut, time_df)
    df_scaled = apply_balmorel_da_time_index(df_scaled, time_df)

    _write_demand_timeseries_inc_files(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DE_VAR_T",
        user_name="RESE",
        filename="DE_VAR_T_RESE",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
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
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
        time_df=time_df,
    )

    # Heat demand: individual users
    _process_individual_heat_user(
        df_space_heat_profile=df_space_heat_profile_residential,
        year=year,
        user_name="RESIDENTIAL",
        subfolder_name="heat_profile_indiv_user_residential",
        filename="DH_VAR_T_RESIDENTIAL",
        year_output_folder=year_output_folder,
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
    )
    _process_individual_heat_user(
        df_space_heat_profile=df_space_heat_profile_tertiary,
        year=year,
        user_name="TERTIARY",
        subfolder_name="heat_profile_indiv_user_tertiary",
        filename="DH_VAR_T_TERTIARY",
        year_output_folder=year_output_folder,
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
    )

    # Heat demand: RESH (space heat blended with hot-water profile)
    _, df_cut, df_scaled = process_timeseries_with_scaling(df_resh_heat_profile, year, year, "demand", fix_monday=True)

    resh_raw_folder = os.path.join(year_output_folder, "heat_profile_resh", "raw")
    resh_scaled_folder = os.path.join(year_output_folder, "heat_profile_resh", "scaled")
    create_directory_if_needed(resh_raw_folder)
    create_directory_if_needed(resh_scaled_folder)

    time_df = create_balmorel_time_mapping()
    df_cut = apply_balmorel_da_time_index(df_cut, time_df)
    df_scaled = apply_balmorel_da_time_index(df_scaled, time_df)
    df_resh_hotwater_profile = apply_balmorel_da_time_index(df_resh_hotwater_profile, time_df)

    df_cut = _blend_space_heat_and_hotwater(
        space_heat_df=df_cut,
        hotwater_df=df_resh_hotwater_profile,
        spaceheat_to_hotwater_ratio=spaceheat_to_hotwater_ratio,
    )
    df_scaled = _blend_space_heat_and_hotwater(
        space_heat_df=df_scaled,
        hotwater_df=df_resh_hotwater_profile,
        spaceheat_to_hotwater_ratio=spaceheat_to_hotwater_ratio,
    )

    write_raw_and_scaled_csv(
        df_raw=df_cut,
        df_scaled=df_scaled,
        output_folder=year_output_folder,
        subfolder_name="heat_profile_resh",
        csv_name="heat_profile_resh.csv",
    )

    _write_demand_timeseries_inc_files(
        df_raw=df_cut,
        df_scaled=df_scaled,
        symbol="DH_VAR_T",
        user_name="RESH",
        filename="DH_VAR_T_RESH",
        da_raw_folder=da_raw_folder,
        da_scaled_folder=da_scaled_folder,
        capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
        capdev_raw_folder=capdev_raw_folder,
        config=config,
        time_df=time_df,
    )

    # Annual DH correction factors
    to_balmorel_folder = os.path.join(year_output_folder, "to_balmorel")
    df_heat_corr_factor_year = _annual_correction_factor_for_year(
        correction_factors_df=df_heat_corr_factors_indiv_user_residential,
        year=year,
        reference_year=ann_corr_fac_ref_year,
    )
    df = to_balmorel_factor_assignment_lines(df_heat_corr_factor_year, "DH", "RESIDENTIAL")
    build_inc_file_list_type(df, "DH", to_balmorel_folder, filename="DH_RESIDENTIAL")

    df_heat_corr_factor_year = _annual_correction_factor_for_year(
        correction_factors_df=df_heat_corr_factors_indiv_user_tertiary,
        year=year,
        reference_year=ann_corr_fac_ref_year,
    )
    df = to_balmorel_factor_assignment_lines(df_heat_corr_factor_year, "DH", "TERTIARY")
    build_inc_file_list_type(df, "DH", to_balmorel_folder, filename="DH_TERTIARY")

    df_heat_corr_factor_year = _annual_correction_factor_for_year(
        correction_factors_df=df_heat_corr_factors_resh,
        year=year,
        reference_year=ann_corr_fac_ref_year,
    )
    df = to_balmorel_factor_assignment_lines(df_heat_corr_factor_year, "DH", "RESH")
    build_inc_file_list_type(df, "DH", to_balmorel_folder, filename="DH_RESH")

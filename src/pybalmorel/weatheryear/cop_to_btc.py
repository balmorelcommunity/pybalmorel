"""Create Balmorel COP .inc files from COP-model CSV outputs.

This module converts COP time series into HourlyDispatch and CapDev formats,
and writes annual COP factor .inc files for non-ground heat-pump technologies.
"""

import os

import pandas as pd

from .auxiliary_functions import (
    compute_capdev_timeseries,
    create_balmorel_time_mapping,
    process_timeseries_with_scaling,
)
from .balmorel_converters import (
    apply_balmorel_da_time_index,
    prepare_balmorel_output_dirs,
    to_balmorel_technology_factor_assignment_lines,
    to_balmorel_timeseries_assignment_lines,
    write_raw_and_scaled_csv,
)
from .config_models import CopModuleConfig
from .to_inc import build_inc_file_list_type


_COP_TYPES: dict[str, str] = {
    "air_air": "GNR_HP_ELEC_AIR-AIR_COP-490_SS-3-KW_Y-2020",
    "air_water": "GNR_HP_ELEC_AIR-WTR_COP-310_LS_Y-2020",
    "ground_water": "GNR_HP_ELEC_GROUND-WTR_COP-360_LS-4-MW_Y-2020",
}


def _write_cop_timeseries_inc_files(
    df_raw: pd.DataFrame,
    df_scaled: pd.DataFrame,
    cop_type: str,
    technology_name: str,
    hd_raw_folder: str,
    hd_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
    config: CopModuleConfig,
    time_df: pd.DataFrame,
) -> None:
    """Write HourlyDispatch and CapDev COP .inc files for one COP type."""
    filename = f"SEASONALCOP_COP_VAR_T_WY_{cop_type}"

    dispatch_cases = [
        (df_raw, hd_raw_folder),
        (df_scaled, hd_scaled_folder),
    ]
    for src_df, output_folder in dispatch_cases:
        df = to_balmorel_timeseries_assignment_lines(
            src_df, "COP_VAR_T", technology_name
        )
        build_inc_file_list_type(df, "COP_VAR_T", output_folder, filename=filename)
        src_df.to_csv(os.path.join(output_folder, f"cop_{cop_type}.csv"))

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
            source="demand",
            scale=scale,
        )
        df = to_balmorel_timeseries_assignment_lines(
            capdev_df, "COP_VAR_T", technology_name
        )
        build_inc_file_list_type(df, "COP_VAR_T", output_folder, filename=filename)
        capdev_df.to_csv(os.path.join(output_folder, f"cop_{cop_type}.csv"))


def _write_cop_factor_inc_files(
    correction_factors_df: pd.DataFrame,
    year: int,
    cop_type: str,
    technology_name: str,
    hd_raw_folder: str,
    hd_scaled_folder: str,
    capdev_scaled_long_term_folder: str,
    capdev_scaled_full_year_folder: str,
    capdev_raw_folder: str,
) -> None:
    """Write annual and long-term COP correction-factor .inc files."""
    filename = f"COP_WY_{cop_type}"

    yearly_factor = (
        correction_factors_df.loc[str(year)].iloc[0] / correction_factors_df.mean()
    )
    df = to_balmorel_technology_factor_assignment_lines(
        yearly_factor, "COP", technology_name
    )

    build_inc_file_list_type(
        df, "COP", capdev_scaled_full_year_folder, filename=filename
    )
    build_inc_file_list_type(df, "COP", capdev_raw_folder, filename=filename)
    build_inc_file_list_type(df, "COP", hd_raw_folder, filename=filename)

    yearly_factor.to_csv(
        os.path.join(capdev_scaled_full_year_folder, f"cop_fac_{cop_type}.csv")
    )
    yearly_factor.to_csv(os.path.join(capdev_raw_folder, f"cop_fac_{cop_type}.csv"))
    yearly_factor.to_csv(os.path.join(hd_raw_folder, f"cop_fac_{cop_type}.csv"))

    long_term_factor = (
        correction_factors_df.loc[str(year)].iloc[0]
        / correction_factors_df.loc[str(year)].iloc[0]
    )
    df = to_balmorel_technology_factor_assignment_lines(
        long_term_factor, "COP", technology_name
    )

    build_inc_file_list_type(
        df, "COP", capdev_scaled_long_term_folder, filename=filename
    )
    build_inc_file_list_type(df, "COP", hd_scaled_folder, filename=filename)

    long_term_factor.to_csv(
        os.path.join(capdev_scaled_long_term_folder, f"cop_fac_{cop_type}.csv")
    )
    long_term_factor.to_csv(os.path.join(hd_scaled_folder, f"cop_fac_{cop_type}.csv"))


def create_cop_inc(config_fn: str, year: int, output_folder: str) -> None:
    """Create COP-related Balmorel .inc files for one weather year.

    Args:
        config_fn: Path to YAML config file.
        year: Weather year to process.
        output_folder: Root output directory.
    """
    config = CopModuleConfig.from_file(config_fn)
    csv_folder = config.cop_model_results

    year_output_folder = os.path.join(output_folder, str(year))
    (
        hd_raw_folder,
        hd_scaled_folder,
        capdev_scaled_long_term_folder,
        capdev_scaled_full_year_folder,
        capdev_raw_folder,
    ) = prepare_balmorel_output_dirs(year_output_folder)

    for cop_type, technology_name in _COP_TYPES.items():
        if cop_type == "ground_water":
            # TODO: Make some rough assumption to produce this otherwise manual fix
            # Ground-source heat pump COP doesn't vary by weather year: Balmorel already
            # carries a fixed per-area annual-average value in base/data/SEASONALCOP_COP.inc.
            continue

        profile_path = os.path.join(csv_folder, f"cop_{cop_type}_profile.csv")
        df_cop_ts = pd.read_csv(profile_path, index_col=0, parse_dates=True)

        _, df_cut, df_scaled = process_timeseries_with_scaling(
            df_cop_ts,
            year,
            year,
            source="demand",
            fix_monday=True,
        )

        write_raw_and_scaled_csv(
            df_raw=df_cut,
            df_scaled=df_scaled,
            output_folder=year_output_folder,
            subfolder_name=f"cop_{cop_type}",
            csv_name="cop.csv",
        )

        time_df = create_balmorel_time_mapping()
        df_cut = apply_balmorel_da_time_index(df_cut, time_df)
        df_scaled = apply_balmorel_da_time_index(df_scaled, time_df)

        _write_cop_timeseries_inc_files(
            df_raw=df_cut,
            df_scaled=df_scaled,
            cop_type=cop_type,
            technology_name=technology_name,
            hd_raw_folder=hd_raw_folder,
            hd_scaled_folder=hd_scaled_folder,
            capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
            capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
            capdev_raw_folder=capdev_raw_folder,
            config=config,
            time_df=time_df,
        )

        factors_path = os.path.join(csv_folder, f"cop_{cop_type}_corr_factors.csv")
        df_cop_factors = pd.read_csv(factors_path, index_col=0, parse_dates=True)

        _write_cop_factor_inc_files(
            correction_factors_df=df_cop_factors,
            year=year,
            cop_type=cop_type,
            technology_name=technology_name,
            hd_raw_folder=hd_raw_folder,
            hd_scaled_folder=hd_scaled_folder,
            capdev_scaled_long_term_folder=capdev_scaled_long_term_folder,
            capdev_scaled_full_year_folder=capdev_scaled_full_year_folder,
            capdev_raw_folder=capdev_raw_folder,
        )

"""
VRE Level

Scale the weather year's wind and solar full-load hours per canonical region
and kind (solar, onshore, offshore) so that the output Balmorel can produce in
the Backcast Year equals ENTSO-E's reported output (see CONTEXT.md and ADR
0012). The hourly profiles and the spread between a region's areas stay as
the weather year wrote them. Writes WNDFLH_ENTSOE.inc and SOLEFLH_ENTSOE.inc
and appends their $include to the scenario's WNDFLH.inc and SOLEFLH.inc.

Created on 28.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
from pathlib import Path
from warnings import warn

import numpy as np
import pandas as pd

from ..classes import IncFile
from .calendar import SEASONS, backcast_hours
from .flows import canonical_region
from .thermal import load_scenario_input, technology_fuels

# Factors outside these bounds point at a capacity or reporting gap, not at the full-load hours
FACTOR_BOUNDS = (0.6, 1.5)

# ENTSO-E production type of each kind
KIND_PRODUCTION_TYPES = {"Solar": "Solar", "Onshore": "Wind Onshore", "Offshore": "Wind Offshore"}

# Kind of one factor over onshore and offshore, where ENTSO-E reports no offshore
WIND = "Wind"

# Full-load-hour symbol of each kind
KIND_SYMBOLS = {"Solar": "SOLEFLH", "Onshore": "WNDFLH", "Offshore": "WNDFLH", WIND: "WNDFLH"}

# Offshore areas, as weatheryear.additional_inc.build_AAA names them: existing farms
# '<offshore region>_OFF_Existing_RG<n>' and new ones '<offshore region>_VRE-OFF_...'
OFFSHORE_AREA = re.compile(r"_OFF_Existing_RG\d+$|_VRE-OFF_")

# ------------------------------- #
#        1. Observed output       #
# ------------------------------- #


def observed_vre(generation: dict[str, pd.DataFrame], year: int) -> pd.DataFrame:
    """ENTSO-E's solar, onshore and offshore output per canonical region over the Backcast Calendar.

    Args:
        generation (dict[str, pd.DataFrame]): Hourly ENTSO-E output (MW) per
            canonical region, one column per production type.
        year (int): The Backcast Year.

    Returns:
        pd.DataFrame: Index canonical region, columns 'Solar', 'Onshore' and
            'Offshore' (TWh). A kind the region doesn't report is NaN.
    """
    hours = backcast_hours(year)
    observed = {
        region: {
            kind: df.reindex(hours)[production_type].sum(min_count=1) / 1e6
            if production_type in df.columns
            else np.nan
            for kind, production_type in KIND_PRODUCTION_TYPES.items()
        }
        for region, df in generation.items()
    }

    return pd.DataFrame.from_dict(observed, orient="index", columns=list(KIND_PRODUCTION_TYPES))


# ------------------------------- #
#     2. Balmorel's VRE output    #
# ------------------------------- #


def flh_areas(wndflh: pd.DataFrame, soleflh: pd.DataFrame, rrraaa: pd.DataFrame) -> pd.DataFrame:
    """Every area with wind or solar full-load hours, with its canonical region and kind.

    Args:
        wndflh (pd.DataFrame): WNDFLH from get_input, ending in (AAA, Value).
        soleflh (pd.DataFrame): SOLEFLH from get_input, ending in (AAA, Value).
        rrraaa (pd.DataFrame): RRRAAA from get_input, ending in (RRR, AAA).

    Returns:
        pd.DataFrame: Columns 'Area', 'Symbol', 'Region', 'Kind' and 'FLH'.
    """
    rrraaa = rrraaa.iloc[:, -2:].set_axis(["BalmorelRegion", "Area"], axis=1)
    areas = pd.concat(
        [
            flh.iloc[:, -2:].set_axis(["Area", "FLH"], axis=1).assign(Symbol=symbol)
            for symbol, flh in (("WNDFLH", wndflh), ("SOLEFLH", soleflh))
        ],
        ignore_index=True,
    )
    areas["FLH"] = areas["FLH"].astype(float)
    areas = areas.merge(rrraaa, on="Area", how="left")
    areas["Region"] = areas["BalmorelRegion"].map(canonical_region, na_action="ignore")
    areas["Kind"] = np.where(
        areas["Symbol"] == "SOLEFLH",
        "Solar",
        np.where(areas["Area"].str.contains(OFFSHORE_AREA), "Offshore", "Onshore"),
    )

    return areas[["Area", "Symbol", "Region", "Kind", "FLH"]]


def available_vre(
    gkfx: pd.DataFrame,
    gdata: pd.DataFrame,
    rrraaa: pd.DataFrame,
    wndflh: pd.DataFrame,
    soleflh: pd.DataFrame,
    gkrate: pd.DataFrame,
    names: dict[float, str],
    year: int,
) -> pd.DataFrame:
    """Balmorel's wind and solar PV capacity of `year` per area and technology, with its available output.

    Wind is every technology with fuel WIND; solar PV every technology of
    type GSOLE with fuel SUN, so solar heat isn't counted. Available output is
    GKFX x FLH x the mean weekly GKRATE (1 where unset). An area with GKFX
    and no full-load hours warns and counts for nothing.

    Args:
        gkfx (pd.DataFrame): GKFX from get_input, ending in (Y, AAA, G, Value).
        gdata (pd.DataFrame): GDATA from get_input, ending in (G, GDATASET, Value).
        rrraaa (pd.DataFrame): RRRAAA from get_input, ending in (RRR, AAA).
        wndflh (pd.DataFrame): WNDFLH from get_input, ending in (AAA, Value).
        soleflh (pd.DataFrame): SOLEFLH from get_input, ending in (AAA, Value).
        gkrate (pd.DataFrame): GKRATE from get_input, ending in (AAA, G, SSS, Value).
        names (dict[float, str]): Output of thermal.acronym_names.
        year (int): The Backcast Year, the Y of GKFX.

    Returns:
        pd.DataFrame: Columns 'Area', 'Technology', 'Region', 'Kind',
            'Capacity' (MW), 'FLH', 'Rating' and 'Available' (TWh).
    """
    gkfx = gkfx.iloc[:, -4:].set_axis(["Year", "Area", "Technology", "Capacity"], axis=1)
    gkfx = gkfx[(gkfx["Year"].astype(str) == str(year)) & (gkfx["Capacity"].astype(float) > 0)]
    fuels = technology_fuels(gdata, names)
    wind = fuels.index[fuels["Fuel"] == "WIND"]
    solar = fuels.index[(fuels["Fuel"] == "SUN") & (fuels["Type"] == "GSOLE")]
    capacity = gkfx[gkfx["Technology"].isin(wind.union(solar))].copy()
    capacity["Capacity"] = capacity["Capacity"].astype(float)
    capacity["Symbol"] = np.where(capacity["Technology"].isin(solar), "SOLEFLH", "WNDFLH")

    rrraaa = rrraaa.iloc[:, -2:].set_axis(["BalmorelRegion", "Area"], axis=1)
    capacity = capacity.merge(rrraaa, on="Area", how="left")
    capacity["Region"] = capacity["BalmorelRegion"].map(canonical_region, na_action="ignore")
    capacity["Kind"] = np.where(
        capacity["Symbol"] == "SOLEFLH",
        "Solar",
        np.where(capacity["Area"].str.contains(OFFSHORE_AREA), "Offshore", "Onshore"),
    )
    areas = flh_areas(wndflh, soleflh, rrraaa)
    capacity = capacity.merge(areas[["Area", "Symbol", "FLH"]], on=["Area", "Symbol"], how="left")

    gkrate = gkrate.iloc[:, -4:].set_axis(["Area", "Technology", "Season", "Rating"], axis=1)
    weekly = (
        gkrate[gkrate["Season"].isin(SEASONS)]
        .pivot_table(index=["Area", "Technology"], columns="Season", values="Rating", aggfunc="first")
        .reindex(columns=SEASONS)
        .astype(float)
        .fillna(1.0)
    )
    rating = weekly.mean(axis=1).rename("Rating")
    capacity = capacity.merge(rating, left_on=["Area", "Technology"], right_index=True, how="left")
    capacity["Rating"] = capacity["Rating"].fillna(1.0)

    missing = capacity[capacity["FLH"].fillna(0) <= 0]
    for row in missing.groupby(["Area", "Symbol"])["Capacity"].sum().reset_index().itertuples():
        warn(
            f"{row.Area} has {row.Capacity:.0f} MW of GKFX but no {row.Symbol}, so it produces "
            "nothing and counts for nothing in the VRE level."
        )
    capacity["FLH"] = capacity["FLH"].fillna(0.0)
    capacity["Available"] = capacity["Capacity"] * capacity["FLH"] * capacity["Rating"] / 1e6

    return capacity[["Area", "Technology", "Region", "Kind", "Capacity", "FLH", "Rating", "Available"]]


# ------------------------------- #
#           3. Factors            #
# ------------------------------- #


def vre_factors(
    available: pd.DataFrame,
    observed: pd.DataFrame,
    bounds: tuple[float, float] = FACTOR_BOUNDS,
) -> pd.DataFrame:
    """The factor per canonical region and kind that makes Balmorel's available output ENTSO-E's.

    Where ENTSO-E reports no offshore output for a region with Balmorel
    offshore capacity, onshore and offshore share one factor (kind 'Wind'),
    since ENTSO-E books small offshore farms as onshore. A factor outside
    `bounds`, or of a region without ENTSO-E generation data, is not written
    and warns.

    Args:
        available (pd.DataFrame): Output of available_vre.
        observed (pd.DataFrame): Output of observed_vre.
        bounds (tuple[float, float], optional): Lowest and highest factor
            written. Defaults to FACTOR_BOUNDS.

    Returns:
        pd.DataFrame: Columns 'Region', 'Kind', 'GKFX' (MW), 'AvailableTWh',
            'ObservedTWh', 'Factor' and 'Written', one row per region and
            kind with Balmorel capacity.
    """
    available = available.dropna(subset=["Region"]).copy()
    offshore_regions = set(available.loc[available["Kind"] == "Offshore", "Region"])
    no_entsoe_offshore = {
        region
        for region in offshore_regions
        if region in observed.index and not observed.loc[region, "Offshore"] > 0
    }
    wind = available["Region"].isin(no_entsoe_offshore) & available["Kind"].isin(["Onshore", "Offshore"])
    available["FactorKind"] = available["Kind"].where(~wind, WIND)

    factors = (
        available.groupby(["Region", "FactorKind"])
        .agg(GKFX=("Capacity", "sum"), AvailableTWh=("Available", "sum"))
        .rename_axis(["Region", "Kind"])
        .reset_index()
    )
    observed_twh = observed.fillna(0.0).assign(**{WIND: lambda df: df["Onshore"] + df["Offshore"]})
    factors["ObservedTWh"] = [
        observed_twh.loc[row.Region, row.Kind] if row.Region in observed_twh.index else np.nan
        for row in factors.itertuples()
    ]
    with np.errstate(divide="ignore", invalid="ignore"):
        factors["Factor"] = factors["ObservedTWh"] / factors["AvailableTWh"]
    factors["Written"] = factors["Factor"].between(*bounds)

    for row in factors[~factors["Written"]].itertuples():
        if np.isnan(row.ObservedTWh):
            warn(
                f"{row.Region} has {row.GKFX:.0f} MW of {row.Kind.lower()} GKFX but no ENTSO-E "
                "generation file, so it keeps the weather year's full-load hours."
            )
        else:
            warn(
                f"{row.Region} {row.Kind.lower()}: factor {row.Factor:.2f} ({row.ObservedTWh:.2f} TWh "
                f"observed against {row.AvailableTWh:.2f} TWh available on {row.GKFX:.0f} MW of GKFX) "
                f"is outside {bounds[0]}-{bounds[1]}, so it keeps the weather year's full-load hours. "
                "That gap is a capacity or reporting problem, not a full-load-hour one."
            )

    return factors


def scaled_flh(areas: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """The scaled full-load hours of every area of a region and kind with a written factor.

    Args:
        areas (pd.DataFrame): Output of flh_areas.
        factors (pd.DataFrame): Output of vre_factors.

    Returns:
        pd.DataFrame: Columns 'Area', 'Symbol', 'Region', 'Kind', 'FLH',
            'Factor' and 'NewFLH'.
    """
    written = factors[factors["Written"]]
    wind_regions = set(written.loc[written["Kind"] == WIND, "Region"])
    areas = areas[areas["FLH"] > 0].copy()
    areas["FactorKind"] = areas["Kind"].where(
        ~(areas["Region"].isin(wind_regions) & areas["Kind"].isin(["Onshore", "Offshore"])), WIND
    )
    scaled = areas.merge(
        written[["Region", "Kind", "Factor"]].rename(columns={"Kind": "FactorKind"}),
        on=["Region", "FactorKind"],
    )
    scaled["NewFLH"] = scaled["FLH"] * scaled["Factor"]

    return scaled[["Area", "Symbol", "Region", "Kind", "FLH", "Factor", "NewFLH"]]


# ------------------------------- #
#           4. Output             #
# ------------------------------- #


def write_flh_override(
    scaled: pd.DataFrame,
    factors: pd.DataFrame,
    symbol: str,
    year: int,
    scenario_data_path: str | Path,
) -> IncFile:
    """Write <symbol>_ENTSOE.inc with the scaled full-load hours of one symbol.

    The file is written even without lines, since the scenario's include
    falls back to base's file where it is missing. The header lists the
    observed output each region and kind is scaled to, not the factor, so a
    rerun on the scaled input data writes the same file.

    Args:
        scaled (pd.DataFrame): Output of scaled_flh.
        factors (pd.DataFrame): Output of vre_factors.
        symbol (str): 'WNDFLH' or 'SOLEFLH'.
        year (int): The Backcast Year.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    kind_name = "Wind" if symbol == "WNDFLH" else "Solar"
    targets = factors[factors["Written"] & (factors["Kind"].map(KIND_SYMBOLS) == symbol)]
    lines = [
        f"{symbol}('{row.Area}')={row.NewFLH:.1f};\n"
        for row in scaled[scaled["Symbol"] == symbol].sort_values("Area").itertuples()
    ]

    inc_file = IncFile(
        prefix=(
            f"* {kind_name} full-load hours scaled to ENTSO-E {year} output per country "
            "(see CONTEXT.md) - generated, do not hand-edit\n"
            + "".join(
                f"* {row.Region} {row.Kind.lower()}: {row.ObservedTWh:.2f} TWh\n"
                for row in targets.sort_values(["Region", "Kind"]).itertuples()
            )
        ),
        body="".join(lines),
        suffix="",
        name=f"{symbol}_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def append_flh_include(flh_inc_path: str | Path, symbol: str) -> None:
    """Idempotently append the scenario-fallback $include of <symbol>_ENTSOE.inc (see ADR 0006).

    A scenario without its own <symbol>.inc gets one that loads base's first.

    Args:
        flh_inc_path (str | Path): Path to the scenario's WNDFLH.inc or SOLEFLH.inc.
        symbol (str): 'WNDFLH' or 'SOLEFLH'.
    """
    flh_inc_path = Path(flh_inc_path)
    if not flh_inc_path.exists():
        flh_inc_path.write_text(f"$include '../../base/data/{symbol}.inc';\n")

    content = flh_inc_path.read_text()
    if f"{symbol}_ENTSOE.inc" in content:
        return

    include_block = (
        "\n"
        f"$if     EXIST '../data/{symbol}_ENTSOE.inc' $INCLUDE         '../data/{symbol}_ENTSOE.inc';\n"
        f"$if not EXIST '../data/{symbol}_ENTSOE.inc' $INCLUDE '../../base/data/{symbol}_ENTSOE.inc';\n"
    )
    with open(flh_inc_path, "a") as f:
        f.write(("" if content.endswith("\n") else "\n") + include_block)
    print(f"Added the $include of {symbol}_ENTSOE.inc to {flh_inc_path}")


def generate_vre_flh(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    generation: dict[str, pd.DataFrame],
    bounds: tuple[float, float] = FACTOR_BOUNDS,
    gams_system_directory: str | None = None,
    reload_input: bool = False,
) -> list[IncFile]:
    """Write WNDFLH_ENTSOE.inc, SOLEFLH_ENTSOE.inc and backcastoutput/vre_flh.csv for a scenario.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to write the overrides for.
        year (int): The Backcast Year.
        generation (dict[str, pd.DataFrame]): Hourly ENTSO-E output per
            canonical region and production type.
        bounds (tuple[float, float], optional): Lowest and highest factor
            written. Defaults to FACTOR_BOUNDS.
        gams_system_directory (str | None, optional): GAMS system directory.
        reload_input (bool, optional): Run ReadData again instead of reusing
            the cached input GDX. Defaults to False.

    Returns:
        list[IncFile]: The saved WNDFLH and SOLEFLH IncFile instances.
    """
    model, names = load_scenario_input(
        balmorel_model_folder,
        scenario,
        gams_system_directory,
        reload_input,
        ignore=tuple(f"{symbol}{suffix}.inc" for symbol in ("WNDFLH", "SOLEFLH") for suffix in ("", "_ENTSOE")),
    )
    inputs = {
        symbol: model.get_input(symbol)
        for symbol in ("GKFX", "GDATA", "RRRAAA", "WNDFLH", "SOLEFLH", "GKRATE")
    }
    available = available_vre(
        inputs["GKFX"],
        inputs["GDATA"],
        inputs["RRRAAA"],
        inputs["WNDFLH"],
        inputs["SOLEFLH"],
        inputs["GKRATE"],
        names,
        year,
    )
    factors = vre_factors(available, observed_vre(generation, year), bounds)
    scaled = scaled_flh(flh_areas(inputs["WNDFLH"], inputs["SOLEFLH"], inputs["RRRAAA"]), factors)

    output_path = Path(balmorel_model_folder) / scenario / "backcastoutput"
    output_path.mkdir(exist_ok=True)
    factors.to_csv(output_path / "vre_flh.csv", index=False)
    written = factors[factors["Written"]]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(factors.set_index(["Region", "Kind"]).round(3))
    print(
        f"Available output of the {len(written)} region-kinds written goes from "
        f"{written['AvailableTWh'].sum():.1f} TWh to the observed {written['ObservedTWh'].sum():.1f} TWh"
    )

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    inc_files = []
    for symbol in ("WNDFLH", "SOLEFLH"):
        inc_files.append(write_flh_override(scaled, factors, symbol, year, scenario_data_path))
        append_flh_include(scenario_data_path / f"{symbol}.inc", symbol)
    print(
        "The weather year overwrites WNDFLH.inc and SOLEFLH.inc, so rerun vre-flh after every "
        "weather-year run. Rerunning is safe: the factors are recomputed against the input data."
    )

    return inc_files

"""
Flows

Analyse transmission flows in ENTSO-E data

Created on 09.07.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from warnings import warn
from itertools import product
from ..entsoe import (
    bidding_zone_translation,
    entsoe_subzones,
    fetch_annual_transmission_data,
    region_to_entsoe_code,
)
from ..classes import Balmorel, IncFile

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

path = Path("tests/output")


def get_data(year, from_to_list, path: Path | str = path):
    path = Path(path)
    df = pd.DataFrame()
    for region_from, region_to in from_to_list:
        temp = pd.read_csv(
            path.joinpath(f"{year}_{region_from}-{region_to}_crossborder_flows.csv")
        )
        temp.columns = ["Time", f"{region_from}-{region_to}"]
        temp.Time = pd.to_datetime(temp.Time, utc=True).dt.tz_convert(
            "Europe/Copenhagen",
        )
        temp = temp.set_index("Time").resample("1h").aggregate("mean").reset_index()

        if len(df) == 0:
            df = temp
        else:
            df = df.merge(temp, on="Time")

    return df


def capacity_max(df: pd.DataFrame) -> pd.DataFrame:
    """Annual maximum hourly flow per border ('Observed Max Flow', see CONTEXT.md)"""
    return df.set_index("Time").resample("1YE").aggregate("max")


def observed_max_flow(
    year: int, region_from: str, region_to: str, path: Path | str
) -> float | None:
    """The Observed Max Flow for one border, one direction, one year.

    Args:
        year (int): The year to read.
        region_from (str): ENTSO-E zone code/name flow originates from.
        region_to (str): ENTSO-E zone code/name flow arrives at.
        path (Path | str): Folder containing the fetched crossborder_flows csv's.

    Returns:
        float | None: The observed max flow in MW, or None if the csv wasn't fetched.
    """
    path = Path(path)
    csv_path = path / f"{year}_{region_from}-{region_to}_crossborder_flows.csv"
    if not csv_path.exists():
        return None

    df = get_data(year, [[region_from, region_to]], path=path)
    return df[f"{region_from}-{region_to}"].max()


# ------------------------------- #
#   2. XKFX overrides (backcast)  #
# ------------------------------- #


def get_current_borders(
    balmorel_model_folder: str | Path,
    scenario: str,
    gams_system_directory: str | None = None,
) -> pd.DataFrame:
    """The non-zero XKFX borders currently defined for a Balmorel scenario.

    Reads XKFX through GAMS (via Balmorel.load_incfiles/.get_input) rather than
    parsing XKFX.inc, since it is a hand-formatted GAMS TABLE not safe to parse
    with a text-based parser (see docs/adr/0002).

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to read XKFX from.
        gams_system_directory (str | None, optional): GAMS system directory.

    Returns:
        pd.DataFrame: Columns 'RegionFrom', 'RegionTo' for every non-zero border.
    """
    m = Balmorel(balmorel_model_folder, gams_system_directory=gams_system_directory)
    m.load_incfiles(scenario)
    xkfx = m.get_input("XKFX")

    value_col = xkfx.columns[-1]
    region_from_col, region_to_col = xkfx.columns[-3], xkfx.columns[-2]

    xkfx = xkfx[xkfx[value_col].astype(float) != 0]
    borders = xkfx[[region_from_col, region_to_col]].drop_duplicates()
    borders.columns = ["RegionFrom", "RegionTo"]

    return borders.reset_index(drop=True)


def compute_entsoe_transmission_overrides(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    api_key: str,
    gams_system_directory: str | None = None,
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Compute Observed Max Flow XKFX overrides for a Balmorel scenario's borders.

    Borders are read from the scenario's current XKFX (see get_current_borders).
    Internal links that ENTSO-E can't distinguish (both sides sharing a canonical
    name, e.g. DE4-N <-> DE4-W) are left out untouched, per docs/adr/0002. Where
    several ENTSO-E zones collapse to one Balmorel region, their observed flows
    are summed; where several Balmorel regions collapse to one ENTSO-E zone, the
    observed flow is split evenly across them.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to read/derive borders for.
        year (int): The backcast target year.
        entsoe_data_path (str | Path): Folder to fetch/read ENTSO-E csv's from.
        api_key (str): ENTSO-E transparency platform API key.
        gams_system_directory (str | None, optional): GAMS system directory.

    Returns:
        tuple[pd.DataFrame, list[tuple[str, str]]]: Overrides (Year, RegionFrom,
            RegionTo, Value) and the ENTSO-E zone pairs that could not be fetched.
    """
    borders = get_current_borders(
        balmorel_model_folder, scenario, gams_system_directory
    )

    borders["CanonicalFrom"] = borders.RegionFrom.map(
        lambda r: bidding_zone_translation.get(r, r)
    )
    borders["CanonicalTo"] = borders.RegionTo.map(
        lambda r: bidding_zone_translation.get(r, r)
    )

    # Drop internal links ENTSO-E can't distinguish (e.g. DE4-N <-> DE4-W)
    borders = borders[borders.CanonicalFrom != borders.CanonicalTo]

    canonical_pairs = borders[["CanonicalFrom", "CanonicalTo"]].drop_duplicates()
    fetch_pairs = []
    for canon_from, canon_to in canonical_pairs.itertuples(index=False):
        from_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_from)]
        to_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_to)]
        fetch_pairs += list(product(from_codes, to_codes))
    fetch_pairs = list(dict.fromkeys(fetch_pairs))  # de-duplicate, keep order

    entsoe_data_path = Path(entsoe_data_path)
    entsoe_data_path.mkdir(parents=True, exist_ok=True)
    fetch_annual_transmission_data(
        "crossborder_flows", fetch_pairs, year, str(entsoe_data_path), api_key
    )

    failed_pairs = []
    results = []
    for (canon_from, canon_to), group in borders.groupby(
        ["CanonicalFrom", "CanonicalTo"]
    ):
        from_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_from)]
        to_codes = [region_to_entsoe_code(sz) for sz in entsoe_subzones(canon_to)]

        total = 0.0
        any_succeeded = False
        for region_from, region_to in product(from_codes, to_codes):
            value = observed_max_flow(year, region_from, region_to, entsoe_data_path)
            if value is None:
                failed_pairs.append((region_from, region_to))
            else:
                total += value
                any_succeeded = True

        if not any_succeeded:
            continue

        split_factor = len(group)
        value_per_border = total / split_factor
        for row in group.itertuples():
            results.append(
                {
                    "Year": year,
                    "RegionFrom": row.RegionFrom,
                    "RegionTo": row.RegionTo,
                    "Value": value_per_border,
                }
            )

    return pd.DataFrame(results), list(dict.fromkeys(failed_pairs))


def write_xkfx_override(
    overrides: pd.DataFrame, scenario_data_path: str | Path
) -> IncFile:
    """Write XKFX_ENTSOE.inc with the ENTSO-E-derived transmission overrides.

    Args:
        overrides (pd.DataFrame): Output of compute_entsoe_transmission_overrides.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    body = "".join(
        f"XKFX('{int(row.Year)}','{row.RegionFrom}','{row.RegionTo}')={row.Value:.1f};\n"
        for row in overrides.itertuples()
    )

    inc_file = IncFile(
        prefix=(
            "* Transmission capacities derived from ENTSO-E Observed Max Flow\n"
            "* (see CONTEXT.md and docs/adr/0001, 0002) - generated, do not hand-edit\n"
        ),
        body=body,
        suffix="",
        name="XKFX_ENTSOE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def append_xkfx_include(xkfx_inc_path: str | Path) -> None:
    """Idempotently append the scenario-fallback $include for XKFX_ENTSOE.inc.

    Args:
        xkfx_inc_path (str | Path): Path to the scenario's XKFX.inc.
    """
    xkfx_inc_path = Path(xkfx_inc_path)
    content = xkfx_inc_path.read_text()

    if "XKFX_ENTSOE.inc" in content:
        return

    include_block = (
        "\n"
        "$if     EXIST '../data/XKFX_ENTSOE.inc' $INCLUDE         '../data/XKFX_ENTSOE.inc';\n"
        "$if not EXIST '../data/XKFX_ENTSOE.inc' $INCLUDE '../../base/data/XKFX_ENTSOE.inc';\n"
    )

    with open(xkfx_inc_path, "a") as f:
        f.write(include_block)


def generate_transmission_max_flow_overrides(
    balmorel_model_folder: str | Path,
    scenario: str,
    year: int,
    entsoe_data_path: str | Path,
    api_key: str,
    gams_system_directory: str | None = None,
) -> None:
    """Fetch ENTSO-E flows and write the XKFX_ENTSOE.inc backcast overrides.

    Args:
        balmorel_model_folder (str | Path): Top-level Balmorel folder (contains 'base').
        scenario (str): The scenario to generate overrides for.
        year (int): The backcast target year.
        entsoe_data_path (str | Path): Folder to fetch/read ENTSO-E csv's from.
        api_key (str): ENTSO-E transparency platform API key.
        gams_system_directory (str | None, optional): GAMS system directory.
    """
    overrides, failed_pairs = compute_entsoe_transmission_overrides(
        balmorel_model_folder,
        scenario,
        year,
        entsoe_data_path,
        api_key,
        gams_system_directory,
    )

    if failed_pairs:
        warn(
            f"Could not fetch ENTSO-E data for {len(failed_pairs)} zone pair(s): "
            f"{failed_pairs}. These were left out of XKFX_ENTSOE.inc - fix the "
            "zone-code mapping or proceed with the borders that were available."
        )

    scenario_data_path = Path(balmorel_model_folder) / scenario / "data"
    write_xkfx_override(overrides, scenario_data_path)
    append_xkfx_include(scenario_data_path / "XKFX.inc")


# ------------------------------- #
#            3. Main              #
# ------------------------------- #


def main():
    df = pd.DataFrame()
    for year in [2024]:
        temp = get_data(year, [["FR", "ES"], ["ES", "FR"]])

        if len(df) == 0:
            df = temp
        else:
            df = pd.concat((df, temp))

    annual = (
        df.set_index("Time")
        .resample("1YE")
        .aggregate(lambda x: np.round(np.sum(x) / 1e6))
    )
    print(annual)

    print(capacity_max(df))


if __name__ == "__main__":
    main()

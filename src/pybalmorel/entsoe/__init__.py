"""
ENTSO-E API

Generic client for fetching data from the ENTSO-E transparency platform,
including the zone-code vocabulary bridging ENTSO-E bidding zones and
Balmorel regions (see CONTEXT.md). Independent of Balmorel backcasting -
see pybalmorel.backcasting for that.

TODO: consider a standalone CLI here (e.g. `python -m pybalmorel.entsoe`)
for downloading raw ENTSO-E data scoped to Balmorel bidding zones, separate
from the backcasting validation workflow.

Created on 18.06.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
import pandas as pd
import requests
from pathlib import Path
from entsoe.entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from entsoe.mappings import NEIGHBOURS, lookup_area
from getpass import getpass
from decouple import config, UndefinedValueError

bidding_zone_codes = {
    "IT-NORD": "10Y1001A1001A73I",
    "IT-CNOR": "10Y1001A1001A70O",
    "IT-CSUD": "10Y1001A1001A71M",
    "IT-SUD": "10Y1001A1001A788",
    "IT-Calabria": "10Y1001C--00096J",
    "IT-Sicily": "10Y1001A1001A75E",
    "IT-Sardinia": "10Y1001A1001A74G",
    "NO1": "10YNO-1--------2",
    "NO2": "10YNO-2--------T",
    "NO3": "10YNO-3--------J",
    "NO4": "10YNO-4--------9",
    "NO5": "10Y1001A1001A48H",
    "SE1": "10Y1001A1001A44P",
    "SE2": "10Y1001A1001A45N",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
    "BA": "10YBA-JPCC-----D",
}

# Note: No data for CY or TR in 2024
bidding_zones = [
    "IE_SEM",
    "10YGB----------A",
    "PT",
    "ES",
    "FR",
    "BE",
    "NL",
    "DE_LU",
    "10YDK-1--------W",
    "10YDK-2--------M",
    "10YNO-1--------2",
    "10YNO-2--------T",
    "10YNO-3--------J",
    "10YNO-4--------9",
    "10Y1001A1001A48H",
    "10Y1001A1001A44P",
    "10Y1001A1001A47J",
    "10Y1001A1001A45N",
    "10Y1001A1001A46L",
    "FI",
    "EE",
    "LV",
    "LT",
    "PL",
    "CZ",
    "SK",
    "HU",
    "RO",
    "BG",
    "GR",
    "AL",
    "MK",
    "XK",
    "ME",
    "RS",
    "10YBA-JPCC-----D",
    "HR",
    "SI",
    "AT",
    "CH",
    "10Y1001A1001A73I",
    "10Y1001A1001A70O",
    "10Y1001A1001A71M",
    "10Y1001A1001A788",
    "10Y1001C--00096J",
    "10Y1001A1001A75E",
    "10Y1001A1001A74G",
]

# Balmorel region name -> canonical name shared with an ENTSO-E zone,
# for regions where Balmorel's resolution differs from ENTSO-E's
# (finer Balmorel regions collapsing to one ENTSO-E zone, or a spelling difference).
bidding_zone_translation = {
    "IT-NORD": "IT",
    "IT-CNOR": "IT",
    "IT-CSUD": "IT",
    "IT-SUD": "IT",
    "IT-Calabria": "IT",
    "IT-Sicily": "IT",
    "IT-Sardinia": "IT",
    "DE4-E": "DE",
    "DE4-N": "DE",
    "DE4-S": "DE",
    "DE4-W": "DE",
    "FIN": "FI",
}

# Balmorel region/ENTSO-E zone names known to have no ENTSO-E-native query code
# equal to their canonical name (see bidding_zone_translation above)
_extra_entsoe_codes = {
    "DE": "DE_LU",
    "IE": "IE_SEM",
    "UK": "10YGB----------A",
    "DK1": "10YDK-1--------W",
    "DK2": "10YDK-2--------M",
}

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def region_to_entsoe_code(canonical_region: str) -> str:
    """Map a canonical region name to the code entsoe-py expects for querying it."""
    if canonical_region in bidding_zone_codes:
        return bidding_zone_codes[canonical_region]
    return _extra_entsoe_codes.get(canonical_region, canonical_region)


_code_to_region = {
    **{code: region for region, code in bidding_zone_codes.items()},
    **{code: region for region, code in _extra_entsoe_codes.items()},
}


def entsoe_code_to_region(code: str) -> str:
    """Map an ENTSO-E query code back to its region name.

    Inverse of region_to_entsoe_code. Falls back to the code itself if unmapped.
    """
    return _code_to_region.get(code, code)


def zone_eic_code(zone: str) -> str:
    """The EIC code of any ENTSO-E zone identifier.

    Accepts a Balmorel/canonical region name ('DK1', 'UK'), an entsoe-py area
    name ('DK_1', 'GB') or an EIC code ('10YDK-1--------W'), so files fetched
    under different spellings of the same zone can be recognised as one.

    Args:
        zone (str): The zone identifier.

    Returns:
        str: The EIC code, or the query code itself if entsoe-py doesn't know it.
    """
    query_code = region_to_entsoe_code(zone)
    try:
        return lookup_area(query_code).code
    except ValueError:
        return query_code


def zone_to_region(zone: str) -> str:
    """The region name of any ENTSO-E zone identifier (before canonical translation).

    Like entsoe_code_to_region, but also understands entsoe-py area names
    ('DK_1' -> 'DK1', 'IT_NORD' -> 'IT-NORD', 'GB' -> 'UK') and EIC codes not in
    bidding_zone_codes.

    Args:
        zone (str): The zone identifier.

    Returns:
        str: The region name, falling back to the entsoe-py area name or `zone` itself.
    """
    if zone in _code_to_region:
        return _code_to_region[zone]
    try:
        area = lookup_area(zone)
    except ValueError:
        return zone
    for key in (area.code, area.name):
        if key in _code_to_region:
            return _code_to_region[key]
    return area.name


# One zone token in a '<year>_<from>-<to>_<query>.csv' file name: a
# 16-character EIC code (which itself contains '-') or an area name like
# 'FR', 'DE_LU' or 'DK_1'
_zone_token = r"(10Y[0-9A-Z-]{13}|[A-Z]{2}(?:_[A-Z0-9]+)*)"


def parse_transmission_filename(
    file_name: str, year: int, entsoe_query: str = "crossborder_flows"
) -> tuple[str, str] | None:
    """The (from, to) zones of a '<year>_<from>-<to>_<entsoe_query>.csv' file.

    Args:
        file_name (str): The file name, without folder.
        year (int): The year the file must be for.
        entsoe_query (str, optional): The query in the file name. Defaults to 'crossborder_flows'.

    Returns:
        tuple[str, str] | None: The zones as spelled in the name, or None if it doesn't match.
    """
    match = re.fullmatch(
        rf"{year}_{_zone_token}-{_zone_token}_{re.escape(entsoe_query)}\.csv", file_name
    )
    return (match.group(1), match.group(2)) if match else None


def transmission_files(
    path: str | Path, year: int, entsoe_query: str = "crossborder_flows"
) -> dict[tuple[str, str], Path]:
    """The fetched transmission files in `path`, one per directed pair of EIC codes.

    A pair fetched under several spellings (e.g. 'DK_1-DE_LU' and
    '10YDK-1--------W-DE_LU') appears once, so it is never read twice.

    Args:
        path (str | Path): Folder with the fetched csv's.
        year (int): The year to look for.
        entsoe_query (str, optional): The query in the file names. Defaults to 'crossborder_flows'.

    Returns:
        dict[tuple[str, str], Path]: {(from EIC code, to EIC code): file}.
    """
    files = {}
    for csv_path in sorted(Path(path).glob(f"{year}_*_{entsoe_query}.csv")):
        zones = parse_transmission_filename(csv_path.name, year, entsoe_query)
        if zones is None:
            continue
        files.setdefault(tuple(zone_eic_code(zone) for zone in zones), csv_path)
    return files


def find_transmission_file(
    path: str | Path,
    year: int,
    zone_from: str,
    zone_to: str,
    entsoe_query: str = "crossborder_flows",
) -> Path | None:
    """The fetched file for one directed pair, whichever spelling it was saved under.

    Args:
        path (str | Path): Folder with the fetched csv's.
        year (int): The year to look for.
        zone_from (str): Zone the flow originates from, in any spelling.
        zone_to (str): Zone the flow arrives at, in any spelling.
        entsoe_query (str, optional): The query in the file name. Defaults to 'crossborder_flows'.

    Returns:
        Path | None: The file, or None if the pair hasn't been fetched.
    """
    exact = Path(path) / f"{year}_{zone_from}-{zone_to}_{entsoe_query}.csv"
    if exact.exists():
        return exact
    return transmission_files(path, year, entsoe_query).get(
        (zone_eic_code(zone_from), zone_eic_code(zone_to))
    )


def entsoe_subzones(canonical_region: str) -> list[str]:
    """The ENTSO-E bidding zones that collapse to `canonical_region`.

    Returns multiple zones only when ENTSO-E's resolution is finer than Balmorel's
    for this region (e.g. 'IT' -> the 7 Italian bidding zones). Otherwise returns
    a single-item list of the canonical name itself.
    """
    subzones = [
        raw
        for raw, canon in bidding_zone_translation.items()
        if canon == canonical_region and raw in bidding_zone_codes
    ]
    return subzones if subzones else [canonical_region]


def date_format(date):
    if type(date) is not pd.Timestamp:
        proper_date = pd.Timestamp(date, tz="Europe/Brussels")
    else:
        proper_date = date
    return proper_date


def get_full_year(year: int):

    start_date = pd.Timestamp(f"{year}0101", tz="Europe/Brussels")
    end_date = pd.Timestamp(f"{year + 1}0101", tz="Europe/Brussels")

    return start_date, end_date


def get_api_key():
    try:
        api_key = config("ENTSOE_API_KEY")
    except UndefinedValueError:
        print(
            "Couldn't find ENTSOE_API_KEY in environment variables, define it in an .env file in project root to avoid being prompted every time."
        )
        api_key = getpass("API key for ENTSO-E transparency platform: ")

    return api_key


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def fetch_annual_data(entsoe_query, year, bidding_zones, path, api_key):
    client = EntsoePandasClient(api_key=api_key)
    start_date, end_date = get_full_year(year)
    p = Path(path)
    for bidding_zone in bidding_zones:
        try:
            if not p.joinpath(f"{year}_{bidding_zone}_{entsoe_query}.csv").exists():
                df = getattr(client, f"query_{entsoe_query}")(
                    bidding_zone,
                    start=start_date,  # pyright: ignore
                    end=end_date,  # pyright: ignore
                )

                df.to_csv(p.joinpath(f"{year}_{bidding_zone}_{entsoe_query}.csv"))
        except ValueError as e:
            print(f"Couldn't fetch bidding zone {bidding_zone}")
            print(e)
        except NoMatchingDataError as e:
            print(f"Couldn't find any data for bidding zone {bidding_zone}")
            print(e)


def no_data_file(path: str | Path, year: int, entsoe_query: str) -> Path:
    """The file remembering pairs ENTSO-E has no data for, so reruns skip them.

    Delete it to query those pairs again.
    """
    return Path(path) / f"{year}_{entsoe_query}_nodata.txt"


def read_no_data_pairs(
    path: str | Path, year: int, entsoe_query: str = "crossborder_flows"
) -> set[tuple[str, str]]:
    """The (from EIC code, to EIC code) pairs ENTSO-E previously had no data for."""
    f = no_data_file(path, year, entsoe_query)
    if not f.exists():
        return set()
    return {
        tuple(line.split("\t"))  # pyright: ignore
        for line in f.read_text().splitlines()
        if line.count("\t") == 1
    }


def fetch_annual_transmission_data(
    entsoe_query, from_to_list, year, path, api_key, timeout: int = 120
):
    client = EntsoePandasClient(api_key=api_key, timeout=timeout)
    start_date, end_date = get_full_year(year)
    p = Path(path)
    # Pairs already fetched under any spelling of their zones are skipped,
    # as are pairs ENTSO-E had no data for on an earlier run
    fetched = set(transmission_files(p, year, entsoe_query))
    no_data = read_no_data_pairs(p, year, entsoe_query)
    for region_from, region_to in from_to_list:
        eic_pair = (zone_eic_code(region_from), zone_eic_code(region_to))
        if eic_pair in fetched or eic_pair in no_data:
            continue
        try:
            df = getattr(client, f"query_{entsoe_query}")(
                region_from,
                region_to,
                start=start_date,  # pyright: ignore
                end=end_date,  # pyright: ignore
            )

            df.to_csv(
                p.joinpath(f"{year}_{region_from}-{region_to}_{entsoe_query}.csv")
            )
        except ValueError as e:
            print(f"Couldn't fetch link {region_from}-{region_to}")
            print(e)
        except NoMatchingDataError:
            print(f"Couldn't find any data for link {region_from}-{region_to}")
            with open(no_data_file(p, year, entsoe_query), "a") as f:
                f.write("\t".join(eic_pair) + "\n")
        except requests.exceptions.RequestException as e:
            # Timeouts, dropped connections and server errors (e.g. 527)
            # shouldn't stop the loop - rerun to retry
            print(f"Request failed for link {region_from}-{region_to}, rerun to retry")
            print(e)


if __name__ == "__main__":
    # Example use of functions
    api_key = get_api_key()
    # fetch_annual_data("load", 2024, bidding_zones, ".", api_key)
    # fetch_annual_data("day_ahead_prices", 2024, bidding_zones, ".", api_key)
    # Only query pairs of neighbouring zones, both within bidding_zones.
    # Both directions are added, since NEIGHBOURS isn't symmetric (e.g. no AL key),
    # and XK is missing from NEIGHBOURS entirely so its borders are added manually.
    # GR-IT_SUD (GRITA) and ME-IT_CSUD (MONITA) are also missing from NEIGHBOURS
    zone_names = {lookup_area(bidding_zone).name for bidding_zone in bidding_zones}
    neighbours = {
        **NEIGHBOURS,
        "XK": ["AL", "ME", "MK", "RS"],
        "GR": NEIGHBOURS["GR"] + ["IT_SUD"],
        "ME": NEIGHBOURS["ME"] + ["IT_CSUD"],
    }
    # Saved under the same zone spelling transmission-max-flow uses
    query_code = lambda name: region_to_entsoe_code(zone_to_region(name))
    neighbour_pairs = sorted(
        {
            (query_code(pair_from), query_code(pair_to))
            for zone_from in zone_names
            for zone_to in neighbours.get(zone_from, [])
            if zone_to in zone_names
            for pair_from, pair_to in [(zone_from, zone_to), (zone_to, zone_from)]
        }
    )
    for year in [2023]:
        fetch_annual_transmission_data(
            "crossborder_flows",
            neighbour_pairs,
            year,
            "tests/output",
            api_key,
        )

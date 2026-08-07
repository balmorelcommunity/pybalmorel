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

import pandas as pd
from pathlib import Path
from entsoe.entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
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
    "10Y1001A1001A47J",
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
            "Couldn't find ENSTOE_API_KEY in environment variables, define it in an .env file in project root to avoid being prompted every time."
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


def fetch_annual_transmission_data(entsoe_query, from_to_list, year, path, api_key):
    client = EntsoePandasClient(api_key=api_key)
    start_date, end_date = get_full_year(year)
    p = Path(path)
    for region_from, region_to in from_to_list:
        try:
            if not p.joinpath(
                f"{year}_{region_from}-{region_to}_{entsoe_query}.csv"
            ).exists():
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
        except NoMatchingDataError as e:
            print(f"Couldn't find any data for link {region_from}-{region_to}")
            print(e)


if __name__ == "__main__":
    # Example use of functions
    api_key = get_api_key()
    # fetch_annual_data("load", 2024, bidding_zones, ".", api_key)
    # fetch_annual_data("day_ahead_prices", 2024, bidding_zones, ".", api_key)
    for year in [2020, 2021, 2022, 2023, 2024, 2025]:
        fetch_annual_transmission_data(
            "crossborder_flows",
            [["ES", "FR"], ["FR", "ES"]],
            year,
            "tests/output",
            api_key,
        )

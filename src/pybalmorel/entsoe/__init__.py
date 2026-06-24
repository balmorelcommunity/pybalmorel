"""
ENTOS-E API

For backcast validation of Balmorel

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

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


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


def fetch_annual_data(
    entsoe_query,
    year,
    path,
):
    api_key = get_api_key()
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


if __name__ == "__main__":
    fetch_annual_data("load", 2024, "tests/output")
    fetch_annual_data("day_ahead_prices", 2024, "tests/output")

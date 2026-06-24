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
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from getpass import getpass

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def fetch_day_ahead_prices(api_key, start_date, end_date, bidding_zone):
    """Fetch day-ahead electricity prices for a specified bidding zone.

    Args:
        api_key (str): API key for the ENTSO-E Transparency Platform.
        start_date (str): Start date in the format 'YYYYMMDD'.
        end_date (str): End date in the format 'YYYYMMDD'.
        bidding_zone (str): Bidding zone code (e.g., '10YNO-1--------J').

    Returns:
        pd.DataFrame: DataFrame containing the day-ahead prices.
    """
    client = EntsoePandasClient(api_key=api_key)
    start_date = date_format(start_date)
    end_date = date_format(end_date)
    prices = client.query_day_ahead_prices(
        bidding_zone,
        start=start_date,  # pyright: ignore
        end=end_date,  # pyright: ignore
    )
    return prices


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


# ------------------------------- #
#            2. Main              #
# ------------------------------- #

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


def get_dayahead_prices(year: int, path: str):
    api_key = getpass("API key for ENTSO-E transparency platform: ")

    for bidding_zone in bidding_zones:
        p = Path(path)
        start_date, end_date = get_full_year(year)
        try:
            if not p.joinpath(f"{year}_{bidding_zone}_dayaheadprices.csv").exists():
                prices_df = fetch_day_ahead_prices(
                    api_key, start_date, end_date, bidding_zone
                )
                prices_df.to_csv(
                    p.joinpath(f"{year}_{bidding_zone}_dayaheadprices.csv")
                )
        except ValueError as e:
            print(f"Couldn't fetch bidding zone {bidding_zone}")
            print(e)
        except NoMatchingDataError as e:
            print(f"Couldn't find any data for bidding zone {bidding_zone}")
            print(e)


if __name__ == "__main__":
    get_dayahead_prices(2024, "tests/output")

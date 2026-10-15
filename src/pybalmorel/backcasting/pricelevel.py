"""
Price Level

Convert nominal historical prices into the backcast Price Year (€2016, see
CONTEXT.md and docs/adr/0009): deflate with the euro-area HICP and convert USD
with the Eurostat annual-average exchange rate.

The tables are bundled rather than fetched, so backcast inputs are
reproducible offline. Extend them once a year from:
- HICP: Eurostat prc_hicp_aind, geo=EA (changing composition), coicop=CP00,
  unit=INX_A_AVG (annual average index, 2015=100)
- EUR/USD: Eurostat ert_bil_eur_a, currency=USD, statinfo=AVG (USD per EUR)

Created on 15.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import pandas as pd

PRICE_YEAR = 2016

# Retrieved from Eurostat on 15.10.2026 (prc_hicp_aind updated 06.02.2026)
hicp_euro_area = {
    2012: 98.05,
    2013: 99.38,
    2014: 99.81,
    2015: 100.00,
    2016: 100.23,
    2017: 101.78,
    2018: 103.56,
    2019: 104.80,
    2020: 105.06,
    2021: 107.78,
    2022: 116.82,
    2023: 123.15,
    2024: 126.07,
    2025: 128.75,
}

# Retrieved from Eurostat on 15.10.2026 (ert_bil_eur_a updated 08.07.2026)
usd_per_eur = {
    2012: 1.2848,
    2013: 1.3281,
    2014: 1.3285,
    2015: 1.1095,
    2016: 1.1069,
    2017: 1.1297,
    2018: 1.1810,
    2019: 1.1195,
    2020: 1.1422,
    2021: 1.1827,
    2022: 1.0530,
    2023: 1.0813,
    2024: 1.0824,
    2025: 1.1300,
}

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def _lookup(table: dict[int, float], year: int, table_name: str) -> float:
    if year not in table:
        raise Exception(
            f"No {table_name} value for {year} - extend the table in "
            f"pybalmorel/backcasting/pricelevel.py (covers {min(table)}-{max(table)})."
        )
    return table[year]


def deflator(year: int, price_year: int = PRICE_YEAR) -> float:
    """Factor converting nominal euros of `year` into euros of `price_year`.

    Args:
        year (int): The year the nominal price was observed in.
        price_year (int, optional): Target currency year. Defaults to PRICE_YEAR (2016).

    Returns:
        float: Multiply a nominal `year` price by this to get a `price_year` price.
    """
    return _lookup(hicp_euro_area, price_year, "HICP") / _lookup(
        hicp_euro_area, year, "HICP"
    )


def eur_per_usd(year: int) -> float:
    """Annual-average EUR per USD for `year` (nominal, before deflation).

    Args:
        year (int): The year of the exchange rate.

    Returns:
        float: Multiply a USD price by this to get a nominal EUR price.
    """
    return 1 / _lookup(usd_per_eur, year, "EUR/USD")


def to_price_year(
    nominal: float | pd.Series | pd.DataFrame,
    year: int,
    currency: str = "EUR",
    price_year: int = PRICE_YEAR,
) -> float | pd.Series | pd.DataFrame:
    """Convert a nominal price (scalar or pandas object) into `price_year` euros.

    Args:
        nominal (float | pd.Series | pd.DataFrame): Nominal price(s) observed in `year`.
        year (int): The year the price(s) were observed in.
        currency (str, optional): 'EUR' or 'USD'. Defaults to 'EUR'.
        price_year (int, optional): Target currency year. Defaults to PRICE_YEAR (2016).

    Returns:
        float | pd.Series | pd.DataFrame: The price(s) in `price_year` euros.
    """
    if currency == "USD":
        nominal = nominal * eur_per_usd(year)
    elif currency != "EUR":
        raise Exception(f"Unsupported currency '{currency}' - use 'EUR' or 'USD'.")

    return nominal * deflator(year, price_year)

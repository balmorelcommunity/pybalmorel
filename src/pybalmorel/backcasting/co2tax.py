"""
CO2 Tax

Convert EEX EUA primary-auction results (Balmorel's
backcast/historicalprices/) into Balmorel's season/term-resolved
TAX_CO2_ST(YYY,CCCRRRAAA,SSS,TTT) input (see the Balmorel repo's
docs/adr/0002-co2-tax-season-term-resolution.md).

Every country gets the EUA price unless overridden (e.g. the UK's own
carbon price, or 0 for countries without one). Prices are expressed in the
backcast Price Year (see pricelevel.py) and mapped onto the UTC Backcast
Calendar (see calendar.py).

Created on 15.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from pathlib import Path

import pandas as pd

from ..classes import IncFile
from .calendar import daily_to_backcast_grid
from .pricelevel import PRICE_YEAR, to_price_year
from .scenariochecks import check_balopt_option

# Balmorel CCC members - overrides naming anything else are rejected
balmorel_countries = [
    "NORWAY", "DENMARK", "FINLAND", "GERMANY", "NETHERLANDS", "SWEDEN",
    "UNITED_KINGDOM", "ESTONIA", "LATVIA", "LITHUANIA", "POLAND", "BELGIUM",
    "FRANCE", "ITALY", "SWITZERLAND", "AUSTRIA", "CZECH_REPUBLIC", "SPAIN",
    "PORTUGAL", "SLOVAKIA", "HUNGARY", "SLOVENIA", "CROATIA", "ROMANIA",
    "BULGARIA", "GREECE", "IRELAND", "LUXEMBOURG", "ALBANIA", "MONTENEGRO",
    "NORTH_MACEDONIA", "BOSNIA_AND_HERZEGOVINA", "SERBIA", "TURKEY", "MALTA",
    "CYPRUS",
]  # fmt: skip

# ------------------------------- #
#          1. Loading             #
# ------------------------------- #


def find_eex_auction_file(historicalprices_path: str | Path, year: int) -> Path:
    """Find the EEX primary-auction report for `year` under historicalprices_path.

    Args:
        historicalprices_path (str | Path): Folder searched recursively.
        year (int): The Backcast Year.

    Returns:
        Path: The .xlsx/.xls report.
    """
    matches = sorted(
        Path(historicalprices_path).rglob(
            f"emission-spot-primary-market-auction-report-{year}-data.xls*"
        )
    )
    if not matches:
        raise FileNotFoundError(
            f"No 'emission-spot-primary-market-auction-report-{year}-data.xlsx' "
            f"under {historicalprices_path} - download it from "
            "https://www.eex.com/en/market-data/market-data-hub/environmentals/eex-eua-primary-auction-spot-download"
        )
    return matches[0]


def load_eex_auction_prices(xlsx_path: str | Path) -> pd.Series:
    """Load daily EUA primary-auction clearing prices in nominal EUR/tCO2.

    Only successful auctions are used. Days with several auctions (e.g. the
    EU, DE and PL auctions) get the mean of their clearing prices.

    Args:
        xlsx_path (str | Path): An EEX 'emission-spot-primary-market-auction-report'
            file (header in the sixth row, columns 'Date', 'Status' and
            'Auction Price €/tCO2').

    Returns:
        pd.Series: Daily nominal price in EUR/tCO2, indexed by calendar date.
    """
    df = pd.read_excel(xlsx_path, header=5)
    price_col = next(col for col in df.columns if str(col).startswith("Auction Price"))

    df = df[df["Status"].astype(str).str.lower() == "successful"]
    dates = pd.to_datetime(df["Date"]).dt.normalize()
    prices = pd.to_numeric(df[price_col], errors="coerce")

    return prices.groupby(dates).mean().dropna().sort_index()


# ------------------------------- #
#   2. TAX_CO2_ST.inc (backcast)  #
# ------------------------------- #


def parse_co2_overrides(overrides: list[str] | tuple[str, ...]) -> dict[str, float]:
    """Parse 'COUNTRY=VALUE' strings into {CCC name: nominal EUR/tCO2}.

    Args:
        overrides (list[str] | tuple[str, ...]): e.g. ['UNITED_KINGDOM=85', 'SERBIA=0'].

    Returns:
        dict[str, float]: Validated overrides.
    """
    parsed = {}
    for override in overrides:
        country, separator, value = override.partition("=")
        country = country.strip().upper()
        if not separator:
            raise Exception(f"CO2 override '{override}' is not of the form COUNTRY=VALUE")
        if country not in balmorel_countries:
            raise Exception(
                f"Unknown country '{country}' in CO2 override - use a Balmorel "
                f"CCC name, one of: {', '.join(balmorel_countries)}"
            )
        try:
            parsed[country] = float(value)
        except ValueError:
            raise Exception(f"CO2 override '{override}' has a non-numeric value")
    return parsed


def write_co2_tax_override(
    eua_grid: pd.DataFrame,
    year: int,
    scenario_data_path: str | Path,
    overrides: dict[str, float] | None = None,
) -> IncFile:
    """Write TAX_CO2_ST.inc with the (S,T)-resolved EUA price for every country.

    Args:
        eua_grid (pd.DataFrame): (S,T) grid of the EUA price in Price Year EUR/tCO2.
        year (int): The Backcast Year.
        scenario_data_path (str | Path): The scenario's 'data' folder.
        overrides (dict[str, float] | None, optional): {CCC name: flat price in
            Price Year EUR/tCO2} replacing the EUA price. Defaults to None.

    Returns:
        IncFile: The saved IncFile instance.
    """
    body = (
        f"TABLE TAX_CO2_ST_EUA(SSS,TTT) 'EUA primary-auction price, backcast {year} (EUR{PRICE_YEAR}/tCO2)'\n"
        + eua_grid.to_string()
        + "\n;\n\n"
        + f"TAX_CO2_ST('{year}',C,SSS,TTT) = TAX_CO2_ST_EUA(SSS,TTT);\n"
        + "".join(
            f"TAX_CO2_ST('{year}','{country}',SSS,TTT) = {value:.4f};\n"
            for country, value in (overrides or {}).items()
        )
    )

    inc_file = IncFile(
        prefix=(
            "* Historical (S,T)-resolved CO2 tax from EEX EUA primary auctions\n"
            "* (see docs/adr/0002-co2-tax-season-term-resolution.md) - generated, do not hand-edit\n\n"
        ),
        body=body,
        suffix="",
        name="TAX_CO2_ST",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def generate_co2_tax_override(
    historicalprices_path: str | Path,
    year: int,
    balmorel_scenario_path: str | Path,
    overrides: dict[str, float] | None = None,
) -> None:
    """Convert the EEX auction report for `year` into the scenario's TAX_CO2_ST.inc.

    Warns (without changing anything) if the scenario's balopt.opt doesn't set
    TAX_CO2_DOL=YYY_CCC_SSS_TTT, in which case Balmorel ignores TAX_CO2_ST.

    Args:
        historicalprices_path (str | Path): Path to backcast/historicalprices/.
        year (int): The Backcast Year.
        balmorel_scenario_path (str | Path): The scenario folder (e.g. .../backcast).
        overrides (dict[str, float] | None, optional): {CCC name: flat nominal
            EUR/tCO2 in `year`} replacing the EUA price. Defaults to None.
    """
    eua_prices = load_eex_auction_prices(
        find_eex_auction_file(historicalprices_path, year)
    )
    eua_grid = to_price_year(daily_to_backcast_grid(eua_prices, year), year)
    overrides_price_year = {
        country: to_price_year(value, year) for country, value in (overrides or {}).items()
    }

    write_co2_tax_override(
        eua_grid, year, Path(balmorel_scenario_path) / "data", overrides_price_year
    )

    check_balopt_option(balmorel_scenario_path, "TAX_CO2_DOL", "YYY_CCC_SSS_TTT")

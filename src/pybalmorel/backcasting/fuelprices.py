"""
Fuel Prices

Convert collected historical fuel price series (Balmorel's
backcast/historicalprices/) into Balmorel's season/term-resolved
FUELPRICE(YYY,AAA,FFF,SSS,TTT) input (see the Balmorel repo's
docs/adr/0001-fuelprice-season-term-resolution.md).

Only NATGAS and COAL are converted here - CO2 belongs to EMI_POL, not
FUELPRICE, and oil is not covered yet.

Created on 13.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from pathlib import Path

import pandas as pd

from ..classes import IncFile

# ------------------------------- #
#          1. Loading             #
# ------------------------------- #

GAS_MWH_TO_GJ = 3.6  # 1 MWh = 3.6 GJ
COAL_LHV_GJ_PER_TONNE = 30.2  # bituminous coal, engineeringtoolbox.com


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Strip thousands separators/quotes from a numeric-looking string column."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "").str.replace('"', ""), errors="coerce"
    )


def load_ttf_gas_prices(csv_path: str | Path, year: int) -> pd.Series:
    """Load daily TTF natural gas prices, converted to Money/GJ.

    Args:
        csv_path (str | Path): Path to the Yahoo Finance TTF=F export
            (columns include 'Date' with no year, e.g. 'Dec 30', and 'Adj Close'
            in EUR/MWh).
        year (int): Calendar year the file covers, used to complete 'Date'.

    Returns:
        pd.Series: Daily price in Money/GJ, indexed by calendar date.
    """
    # Volume has unquoted thousands separators (e.g. "1,119"), so a plain
    # pd.read_csv mis-tokenizes those rows - split each line to the header's
    # field count instead, lumping any extra commas into the unused last field.
    lines = [line for line in Path(csv_path).read_text().splitlines() if line.strip()]
    header = lines[0].split(",")
    rows = [line.split(",", maxsplit=len(header) - 1) for line in lines[1:]]
    df = pd.DataFrame(rows, columns=header)

    dates = pd.to_datetime(df["Date"] + f" {year}", format="%b %d %Y")
    prices_per_mwh = _clean_numeric(df["Adj Close"])
    series = pd.Series((prices_per_mwh / GAS_MWH_TO_GJ).to_numpy(), index=dates)
    return series.dropna().sort_index()


def load_rotterdam_coal_prices(
    csv_path: str | Path,
    eur_per_usd: float,
    lhv_gj_per_tonne: float = COAL_LHV_GJ_PER_TONNE,
) -> pd.Series:
    """Load daily Rotterdam coal futures prices, converted to Money/GJ.

    Args:
        csv_path (str | Path): Path to the investing.com Rotterdam Coal Futures
            export (columns include 'Date' as MM/DD/YYYY and 'Price' in USD/t).
        eur_per_usd (float): EUR/USD exchange rate to apply - the source data is
            quoted in USD, while Balmorel's FUELPRICE convention is Money/GJ in
            the model's own currency (EUR). No default is provided; pick a rate
            deliberately rather than have one silently baked in.
        lhv_gj_per_tonne (float, optional): Lower heating value used to convert
            USD/t to USD/GJ. Defaults to 30.2 (bituminous coal).

    Returns:
        pd.Series: Daily price in Money/GJ, indexed by calendar date.
    """
    df = pd.read_csv(csv_path)
    dates = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    prices_per_tonne_usd = _clean_numeric(df["Price"])
    prices_per_gj = prices_per_tonne_usd * eur_per_usd / lhv_gj_per_tonne
    series = pd.Series(prices_per_gj.to_numpy(), index=dates)
    return series.dropna().sort_index()


# ------------------------------- #
#      2. Calendar -> (S,T)       #
# ------------------------------- #


def daily_prices_to_st_grid(prices: pd.Series, year: int) -> pd.DataFrame:
    """Map a daily price series onto Balmorel's S01-S52 x T001-T168 backcast grid.

    Missing calendar days (weekends/holidays with no trading data) carry the
    last available price forward (or backward, for gaps before the first
    observation). Uses the same first-Monday-to-last-Sunday 52-week window as
    pybalmorel.backcasting.__main__.format_balmorel_df, so the resulting
    (Season,Time) grid lines up with ENTSO-E-derived backcast data.

    Args:
        prices (pd.Series): Daily prices indexed by calendar date.
        year (int): The backcast year.

    Returns:
        pd.DataFrame: Index 'S01'..'S52', columns 'T001'..'T168'.
    """
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index).normalize()
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()

    hourly_index = pd.date_range(
        f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz="Europe/Copenhagen"
    )
    daily_lookup = prices.reindex(hourly_index.tz_localize(None).normalize())
    daily_lookup = daily_lookup.ffill().bfill()
    daily_lookup.index = hourly_index

    iso = hourly_index.isocalendar().reset_index(drop=True)
    first_monday_hour = iso.query("day == 1").index[0]
    last_sunday_hour = iso.query("day == 7").index[-1]

    values = daily_lookup.to_numpy()[first_monday_hour : last_sunday_hour + 1]
    if len(values) != 52 * 168:
        raise ValueError(
            f"Expected {52 * 168} hours in the first-Monday-to-last-Sunday window "
            f"for {year}, got {len(values)}."
        )

    return pd.DataFrame(
        values.reshape(52, 168),
        index=[f"S{s:02d}" for s in range(1, 53)],
        columns=[f"T{t:03d}" for t in range(1, 169)],
    )


# ------------------------------- #
#  3. FUELPRICE.inc (backcast)    #
# ------------------------------- #


def write_fuelprice_override(
    fuel_grids: dict[str, pd.DataFrame],
    year: int,
    scenario_data_path: str | Path,
) -> IncFile:
    """Write FUELPRICE.inc with (S,T)-resolved historical fuel prices.

    Written as scenario-local 'data/FUELPRICE.inc', which bb4datainc.inc reads
    ahead of base/data/FUELPRICE.inc (and that fallback's own separate
    FUELPRICE_%SCNAME%.inc indirection) - see docs/adr/0001 in the Balmorel
    repo. Requires FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT to be set in the
    scenario's balopt.opt (not done here), and FUELPRICE_CONSTANT.inc (see
    write_fuelprice_constant_override) to list every other fuel, or the model
    densely populates IFUELPRICE for every fuel in FFF.

    Args:
        fuel_grids (dict[str, pd.DataFrame]): {FFF fuel name: (S,T) grid},
            e.g. {'NATGAS': ..., 'COAL': ...} as returned by daily_prices_to_st_grid.
        year (int): The backcast year these prices apply to.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    body_parts = []
    assignments = []
    for fuel, grid in fuel_grids.items():
        table_name = f"FUELPRICE_ST_{fuel}"
        body_parts.append(
            f"TABLE {table_name}(SSS,TTT) 'Historical {fuel} price, backcast {year} (Money/GJ)'\n"
        )
        body_parts.append(grid.to_string())
        body_parts.append("\n;\n\n")
        assignments.append(
            f"FUELPRICE('{year}',AAA,'{fuel}',SSS,TTT) = {table_name}(SSS,TTT);\n"
        )

    inc_file = IncFile(
        prefix=(
            "* Historical (S,T)-resolved fuel prices from backcast/historicalprices\n"
            "* (see docs/adr/0001-fuelprice-season-term-resolution.md) - generated, do not hand-edit\n\n"
        ),
        body="".join(body_parts) + "".join(assignments),
        suffix="",
        name="FUELPRICE",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def write_fuelprice_constant_override(
    resolved_fuels: list[str], scenario_data_path: str | Path
) -> IncFile:
    """Write FUELPRICE_CONSTANT.inc flagging every fuel except resolved_fuels as annual-only.

    Keeps IFUELPRICE's dense (S,T) broadcast limited to the fuels that actually
    have historical daily data - required for FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT
    to be affordable (see docs/adr/0001, 'FUELPRICE_CONSTANT' section).

    Args:
        resolved_fuels (list[str]): FFF fuel names with real (S,T) data, e.g.
            ['NATGAS', 'COAL'] - excluded from the constant set.
        scenario_data_path (str | Path): The scenario's 'data' folder.

    Returns:
        IncFile: The saved IncFile instance.
    """
    body = "FUELPRICE_CONSTANT(FFF) = YES;\n" + "".join(
        f"FUELPRICE_CONSTANT('{fuel}') = NO;\n" for fuel in resolved_fuels
    )

    inc_file = IncFile(
        prefix=(
            "* Fuels with historical (S,T)-resolved prices are excluded here so\n"
            "* IFUELPRICE is only densely populated for them - generated, do not hand-edit\n\n"
        ),
        body=body,
        suffix="",
        name="FUELPRICE_CONSTANT",
        path=str(scenario_data_path),
    )
    inc_file.save()

    return inc_file


def generate_fuelprice_overrides(
    historicalprices_path: str | Path,
    year: int,
    eur_per_usd: float,
    balmorel_scenario_path: str | Path,
) -> None:
    """Convert backcast/historicalprices/ into FUELPRICE.inc + FUELPRICE_CONSTANT.inc.

    Only NATGAS and COAL get real (S,T)-resolved prices - CO2 belongs to
    EMI_POL, not FUELPRICE, and oil is not covered yet. Every other fuel is
    flagged constant (see docs/adr/0001 in the Balmorel repo).

    Note: requires 'FUELPRICE_DOL=YYY_AAA_FFF_SSS_TTT' to be set in the
    scenario's balopt.opt - currently NOT set for backcast/model/balopt.opt
    (open issue 4 in the ADR). Also note base/data/HYDROGEN_FUELPRICE.inc
    currently hardcodes its own flat 2024 COAL/NATGAS prices into
    FUELPRICE_HYDROGEN, which overrides IFUELPRICE unconditionally whenever
    it is nonzero - those lines need removing, or this override is silently
    ignored for COAL/NATGAS.

    Args:
        historicalprices_path (str | Path): Path to backcast/historicalprices/.
        year (int): The backcast year.
        eur_per_usd (float): EUR/USD exchange rate for the (USD-quoted) coal price.
        balmorel_scenario_path (str | Path): The scenario folder (e.g. .../backcast).
    """
    historicalprices_path = Path(historicalprices_path)

    gas_prices = load_ttf_gas_prices(
        historicalprices_path / f"natural_gas_TTF_{year}.csv", year
    )
    coal_prices = load_rotterdam_coal_prices(
        historicalprices_path / "Rotterdam Coal Futures Historical Data.csv",
        eur_per_usd,
    )

    fuel_grids = {
        "NATGAS": daily_prices_to_st_grid(gas_prices, year),
        "COAL": daily_prices_to_st_grid(coal_prices, year),
    }

    scenario_data_path = Path(balmorel_scenario_path) / "data"
    write_fuelprice_override(fuel_grids, year, scenario_data_path)
    write_fuelprice_constant_override(list(fuel_grids), scenario_data_path)

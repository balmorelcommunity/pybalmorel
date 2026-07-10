"""
Conversion rates and Inflation

Download and get conversion rates and inflation correction

Created on 10.07.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

from pathlib import Path
import pandas as pd

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def get_conversion_rate(path: str, filename: str = "estat_tec00033.tsv"):
    """Get conversion rates from other currencies to Euro"""
    file = Path(path).joinpath(filename)
    if not file.exists():
        raise FileNotFoundError(
            f"Can't find {file}! Make sure you have downloaded and uncompressed it to the path provided.\nDownload from:\nhttps://ec.europa.eu/eurostat/web/products-datasets/-/TEC00033"
        )
    df = pd.read_csv(file, sep="\t")

    index_col = df.pop(r"freq,statinfo,unit,currency\TIME_PERIOD").str.split(
        ",", expand=True
    )
    index_col.columns = ["freq", "statinfo", "unit", "currency"]
    df.columns = df.columns.str.replace(" ", "").astype(int)

    df = df.merge(index_col, left_index=True, right_index=True)

    return df


def get_harmonised_price_index(
    path: str,
    filename: str = "estat_prc_hicp_aind$defaultview_filtered.tsv",
    index_choice: str = "CP00",
):
    """Get the harmonised index for consumer prices (HICP)"""
    file = Path(path).joinpath(filename)
    if not file.exists():
        raise FileNotFoundError(
            f"Can't find {file}! Make sure you have downloaded and uncompressed it to the path provided.\nDownload from:\nhttps://ec.europa.eu/eurostat/databrowser/product/page/PRC_HICP_AIND"
        )
    df = pd.read_csv(file, sep="\t")

    index_col = df.pop(r"freq,unit,coicop,geo\TIME_PERIOD").str.split(",", expand=True)
    index_col.columns = ["freq", "unit", "coicop", "geo"]

    # Convert value-containing dataframe to integer columns and float values
    df.columns = df.columns.str.replace(" ", "").astype(int)
    df = (
        df.replace(": ", 0)
        .replace(": @C", 0)
        .replace(to_replace=r"(\d+\.?\d*)\s*d", value=r"\1", regex=True)
        .astype(float)
    )

    df = df.merge(index_col, left_index=True, right_index=True)

    # Get index choice (default: 'all-items HICP', CP00)
    df = df.query(f'coicop == "{index_choice}"')

    # Get average annual index
    df = df.query('unit == "INX_A_AVG"')

    return df


def inflation_correction(
    value: float,
    year_to: int,
    year_from: int,
    inflation_table: pd.DataFrame,
    region: str = "EU",
):

    inflation_table = inflation_table.query(f'geo == "{region}"')

    from_index = inflation_table[year_from]
    to_index = inflation_table[year_to]

    corrected_value = value * to_index / from_index

    if corrected_value.shape[0] > 1:
        raise ValueError("More price indices were found for the input parameters!")

    return float(corrected_value.iloc[0])


def euro_conversion_rate(
    year: int,
    currency: str,
    currency_table: pd.DataFrame,
):

    df = currency_table.query(f'currency == "{currency}"')

    if df[year].shape[0] > 1:
        raise ValueError("More conversion rates were found for the input parameters!")

    return float(df[year].iloc[0])


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():

    pass


if __name__ == "__main__":
    currency_table = get_conversion_rate("tests/output")
    hicp = get_harmonised_price_index("tests/output")
    converted_value = inflation_correction(10, 2016, 2024, hicp)
    print(f"10 € converted from €2024 to €2016:\n{converted_value}")
    in_usd = converted_value * euro_conversion_rate(2016, "USD", currency_table)
    print(f"Then, convert this to USD2016:\n{in_usd}")

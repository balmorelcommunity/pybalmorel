"""
Average Prices

Get average prices for static Balmorel backcasting input
Data input:
- Natural gas, scraped from: https://finance.yahoo.com/quote/TTF%3DF/history/  Unit is in € / MWh
- CO2: https://www.eex.com/en/market-data/market-data-hub/environmentals/eex-eua-primary-auction-spot-download Unit in €/tCO2
- Oil weekly: https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fenergy.ec.europa.eu%2Fdocument%2Fdownload%2F906e60ca-8b6a-44e7-8589-652854d2fd3f_en%3Ffilename%3DWeekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx&wdOrigin=BROWSELINK  Unit in €/t
- Coal: https://www.investing.com/commodities/rotterdam-coal-futures Unit in €/t

Lower heating values from https://www.engineeringtoolbox.com/fuels-higher-calorific-values-d_169.html#gsc.tab=0
- Heavy fuel oil 39 MJ/kg = 39 GJ/t
- Anthracite coal 32.6 MJ/kg = 32.6 GJ/t
- Bituminous coal 30.2 MJ/kg = 30.2 GJ/t

Bituminous coal is the most abundant form of coal, according to this source:
https://swannscoalsupplies.co.uk/blogs/news/what-are-the-four-different-types-of-coal

Created on 09.07.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import click
import pandas as pd

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def load_row(file_path: str, row: int, sheet_name: str, header: int | list):
    # Load the Excel file, specifying the sheet and using the first row as header
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=header)

    # Extract the 1077th row (index 1076 due to zero-based indexing)
    row = df.iloc[row - 4]

    # Convert to numeric, coercing errors (non-numeric values) to NaN
    numeric_row = pd.to_numeric(row, errors="coerce")

    # Drop NaN values (non-numeric)
    numeric_row = numeric_row.dropna()  # pyright: ignore

    # Make dataframe
    df = pd.DataFrame(numeric_row).reset_index()

    return df


def format_oil_price_parameters(parameters: pd.Series):
    parameters = (
        parameters.str.replace("price_wo_tax_", "")
        .str.replace("fuel_oil_1", "FUELOIL1")
        .str.replace("fuel_oil_2", "FUELOIL2")
        .str.replace("heating_oil", "HEATINGOIL")
        .str.replace("exchange_rate", "EXCHANGERATE")
        .str.split("_", expand=True)
    )
    return parameters[0], parameters[1]


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.group()
def main():
    """Average price CLI: get average prices for oil, gas, coal."""
    pass


@click.command()
def fueloil(filepath: str = "Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"):
    """Calculate average heavy fuel oil prices (€/GJ) from the oil bulletin excel."""
    try:
        result = load_row(
            filepath,
            1077,
            "Prices wo taxes",
            [0, 2],
        )
        result.columns = ["Parameter", "Unit", "Value"]
        region, parameter = format_oil_price_parameters(result.Parameter)
        result.Parameter = parameter
        result["Region"] = region
        result = result.query(
            'Parameter == "FUELOIL1" or Parameter == "FUELOIL2"'
        ).pivot_table(index="Region", values="Value", aggfunc="mean")
        # Convert to €/GJ
        result = result / 39  # 39 GJ/t for heavy fuel oil
        # Convert to €2016 (not implemented, kept for ref)
        print("Average heavy fuel oil prices (€/GJ):")
        print(result.to_string(float_format=lambda x: f"{x:.2f}", index=True))
    except Exception as e:
        print(f"Error processing fueloil: {e}")


@click.command()
def naturalgas(filepath: str = "natural_gas_TTF_2024.csv"):
    """Calculate average TTF natural gas price (€/MWh) from CSV."""
    try:
        # pandas >=1.3: on_bad_lines='skip', <1.3: error_bad_lines=False
        try:
            df = pd.read_csv(
                filepath,
                on_bad_lines="skip",
            )
        except TypeError:
            df = pd.read_csv(
                filepath,
                error_bad_lines=False,
            )

        def clean(x):
            try:
                # Remove all thousand separators if present
                return float(str(x).replace(",", ""))
            except:
                return None

        avg_price = df["Adj Close"].apply(clean).dropna().mean()
        print(f"TTF Natural Gas 2024 average price (€/MWh): {avg_price:.2f}")
    except Exception as e:
        print(f"Error processing naturalgas: {e}")


@click.command()
def coal(filepath: str = "Rotterdam Coal Futures Historical Data.csv"):
    """Calculate average Rotterdam coal price (€/t and €/GJ) from CSV."""
    try:
        df = pd.read_csv(filepath)

        def clean(x):
            try:
                return float(str(x).replace(",", "").replace('"', ""))
            except:
                return None

        avg_price_ton = df["Price"].apply(clean).dropna().mean()
        avg_price_gj = avg_price_ton / 30.2 if avg_price_ton is not None else None
        print(f"Rotterdam Coal Futures average price (USD/t): {avg_price_ton:.2f}")
        print(f"Rotterdam Coal Futures average price (USD/GJ): {avg_price_gj:.2f}")
    except Exception as e:
        print(f"Error processing coal: {e}")


main.add_command(naturalgas)
main.add_command(coal)
main.add_command(fueloil)

if __name__ == "__main__":
    main()

"""Helper functions for converting demand time series to Balmorel format."""
import pandas as pd


def convert_to_list_df_new(df: pd.DataFrame, name: str, user_name: str) -> pd.DataFrame:
    """Convert time-series DataFrame to Balmorel assignment lines."""
    output = []
    output_df = pd.DataFrame()

    for idx in df.index:
        sss, ttt = idx.split(".")
        for rrr in df.columns:
            value = df.loc[idx, rrr]
            output.append(f"{name}('{rrr}', '{user_name}', '{sss}', '{ttt}') = {value};")

    output_df[name] = output
    return output_df



def convert_to_list_df_annual_correction(df: pd.Series, name: str, user_name: str) -> pd.DataFrame:
    """Convert annual correction factors to Balmorel assignment lines."""
    output = []
    output_df = pd.DataFrame()

    for rrr in df.index:
        value = df.loc[rrr]
        output.append(
            f"{name}( YYY, '{rrr}', '{user_name}') = {name}( YYY, '{rrr}', '{user_name}')*{value};"
        )

    output_df[name] = output
    return output_df








                




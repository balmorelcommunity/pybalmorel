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
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def get_conversion_rate(path: str, filename: str = "estat_tec00033.tsv"):
    file = Path(path).joinpath(filename)
    if not file.exists():
        raise FileNotFoundError(
            f"Can't find {file}! Make sure you have downloaded and uncompressed it to the path provided.\nDownload from:\nhttps://ec.europa.eu/eurostat/web/products-datasets/-/TEC00033"
        )
    df = pd.read_csv(file, sep="\t")
    print(df)


def get_harmonised_price_index(
    path: str, filename: str = "estat_prc_hicp_aind$defaultview_filtered.tsv"
):
    file = Path(path).joinpath(filename)
    if not file.exists():
        raise FileNotFoundError(
            f"Can't find {file}! Make sure you have downloaded and uncompressed it to the path provided.\nDownload from:\nhttps://ec.europa.eu/eurostat/databrowser/product/page/PRC_HICP_AIND"
        )
    df = pd.read_csv(file, sep="\t")
    print(df)


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():

    pass


if __name__ == "__main__":
    get_conversion_rate("tests/output")
    get_harmonised_price_index("tests/output")

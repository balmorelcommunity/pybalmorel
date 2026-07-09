"""
Flows

Analyse transmission flows in ENTSO-E data

Created on 09.07.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import click
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from . import bidding_zone_codes, bidding_zones

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #

path = Path("tests/output")


def get_data(year, from_to_list):
    df = pd.DataFrame()
    for region_from, region_to in from_to_list:
        temp = pd.read_csv(
            path.joinpath(f"{year}_{region_from}-{region_to}_crossborder_flows.csv")
        )
        temp.columns = ["Time", f"{region_from}-{region_to}"]
        temp.Time = pd.to_datetime(temp.Time, utc=True).dt.tz_convert(
            "Europe/Copenhagen",
        )
        temp = temp.set_index("Time").resample("1h").aggregate("mean").reset_index()

        if len(df) == 0:
            df = temp
        else:
            df = df.merge(temp, on="Time")

    return df


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


def main():
    df = pd.DataFrame()
    for year in [2020, 2021, 2022, 2023, 2024, 2025]:
        temp = get_data(year, [["FR", "ES"], ["ES", "FR"]])

        if len(df) == 0:
            df = temp
        else:
            df = pd.concat((df, temp))

    annual = (
        df.set_index("Time")
        .resample("1YE")
        .aggregate(lambda x: np.round(np.sum(x) / 1e6))
    )
    print(annual)

    capacity_max = df.set_index("Time").resample("1YE").aggregate("max")
    print(capacity_max)


if __name__ == "__main__":
    main()

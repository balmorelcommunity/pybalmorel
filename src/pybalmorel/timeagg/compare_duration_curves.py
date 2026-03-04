"""
TITLE

DESCRIPTION

Created on 05.09.2025
@author: Mathias Berg Rosendal
         PhD Student at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from GeneralHelperFunctions import doLDC
from pybalmorel import Balmorel
from pybalmorel.utils import symbol_to_df
import click

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def get_resolution(db):

    S = symbol_to_df(db, "S").SSS.to_list()
    T = symbol_to_df(db, "T").TTT.to_list()

    return pd.MultiIndex.from_product((S, T))


# ------------------------------- #
#            2. Main              #
# ------------------------------- #


@click.command()
@click.argument("scenario1")
@click.argument("scenario2", required=False, default=None)
@click.option(
    "--overwrite",
    required=False,
    default=False,
    help="Load input files again? Defaults to False, use True if you changed data",
)
def main(scenario1: str, scenario2: str | None, overwrite: bool):
    """
    Compare duration curves between a scenario and base at full resolution (by default)
    """

    # Get scenarios
    m = Balmorel("Balmorel")
    m.load_incfiles(scenario1, overwrite=overwrite)
    res1 = get_resolution(m.input_data[scenario1])

    full_resolution = pd.MultiIndex.from_product(
        ([f"S{s:02.0f}" for s in range(1, 53)], [f"T{t:03.0f}" for t in range(1, 169)])
    )

    if scenario2 is None:
        scenario2 = "base"
        m.load_incfiles(scenario2, overwrite=overwrite)
        res2 = full_resolution
    else:
        m.load_incfiles(scenario2, overwrite=overwrite)
        res2 = get_resolution(m.input_data[scenario2])

    # Get temporal resolution choice
    for incfile in [
        "WND_VAR_T",
        "SOLE_VAR_T",
        "DH_VAR_T",
        "DE_VAR_T",
        "WTRRRVAR_T",
        "WTRRSVAR_S",
    ]:
        # Load
        df1 = symbol_to_df(m.input_data[scenario1], incfile)
        df2 = symbol_to_df(m.input_data[scenario2], incfile)

        # Get dimensions
        vars = [
            col for col in df1.columns if col not in ["SSS", "S", "TTT", "T", "Value"]
        ]
        temporal_dimension = [
            col for col in df1.columns if col in ["SSS", "S", "TTT", "T"]
        ]

        # Pivot
        df1 = (
            df1.pivot_table(index=temporal_dimension, columns=vars, values="Value")
            .reindex(full_resolution)
            .fillna(0)
            .loc[res1]
        )
        df2 = (
            df2.pivot_table(index=temporal_dimension, columns=vars, values="Value")
            .reindex(full_resolution)
            .fillna(0)
            .loc[res2]
        )
        print(df1)
        print(df2)

        # Plot all, 9 graphs max
        for batch in range(0, len(df1.columns), 9):
            # Get columns to plot
            columns = df1.columns[batch : batch + 9]

            # Prepare 9 plots
            fig, ax = plt.subplots(3, 3)

            # Iterate through the batch
            i = 0
            j = 0
            for col in columns:
                # Make duration curve
                if col != columns[-1]:
                    values1, bins1 = doLDC(
                        df1[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"color": "orange"},
                    )
                    values2, bins2 = doLDC(
                        df2[col].values, 100, plot=True, ax=ax[j][i], **{"color": "k"}
                    )
                else:
                    values1, bins1 = doLDC(
                        df1[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"label": scenario1, "color": "orange"},
                    )
                    values2, bins2 = doLDC(
                        df2[col].values,
                        100,
                        plot=True,
                        ax=ax[j][i],
                        **{"label": scenario2, "color": "k"},
                    )

                ax[j][i].set_title(col)

                i += 1
                if i == 3:
                    i = 0
                    j += 1

            # Save figure
            fig.legend(loc="upper center", ncol=2)
            fig.savefig(f"Balmorel/{scenario1}/{incfile}_col{batch}-{batch + 9}.png")


if __name__ == "__main__":
    main()

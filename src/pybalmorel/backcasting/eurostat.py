"""
Eurostat Energy Balances

Fetch the Eurostat statistics the Demand Level needs from the public
dissemination API (no key): final electricity consumption and electric
boilers and heat pumps in district heating (nrg_bal_c), and households'
electricity for space and water heating (nrg_d_hhq). Responses are JSON-stat
and cached as <eurostat-data-path>/<year>_<dataset>.json, so a dataset is
only fetched once per year.

Created on 28.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import json
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests

EUROSTAT_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Energy balance codes per dataset: final consumption, then the electricity used for heat
FINAL_CONSUMPTION = "FC_E"
HEATING_BALANCES = {
    "nrg_d_hhq": ("FC_OTH_HH_E_SH", "FC_OTH_HH_E_WH"),
    "nrg_bal_c": ("TI_EHG_EB", "TI_EHG_EDHP"),
}
DATASET_BALANCES = {
    "nrg_bal_c": (FINAL_CONSUMPTION, *HEATING_BALANCES["nrg_bal_c"]),
    "nrg_d_hhq": HEATING_BALANCES["nrg_d_hhq"],
}

# Eurostat geo codes that differ from Balmorel's country codes
GEO_TRANSLATION = {"EL": "GR"}

# ------------------------------- #
#          1. JSON-stat           #
# ------------------------------- #


def decode_jsonstat(response: dict) -> pd.DataFrame:
    """Decode a JSON-stat 2.0 dataset into one row per cell with a value.

    Eurostat's 'value' is sparse: a dict from the flat, row-major index over
    the dimensions in 'id' to the value. Cells without a value are left out.

    Args:
        response (dict): The parsed JSON-stat response.

    Returns:
        pd.DataFrame: One column per dimension (holding its category codes)
            and 'Value'.
    """
    dimensions, sizes = response["id"], response["size"]
    codes = []
    for dimension in dimensions:
        index = response["dimension"][dimension]["category"]["index"]
        if isinstance(index, list):
            index = {code: position for position, code in enumerate(index)}
        codes.append(np.array(sorted(index, key=lambda code: index[code]), dtype=object))

    values = response.get("value", {})
    if isinstance(values, list):
        values = {position: value for position, value in enumerate(values) if value is not None}
    flat = np.array([int(position) for position in values], dtype=int)
    positions = np.unravel_index(flat, sizes) if len(flat) else [np.array([], dtype=int)] * len(sizes)

    decoded = pd.DataFrame(
        {dimension: codes[i][positions[i]] for i, dimension in enumerate(dimensions)}
    )
    decoded["Value"] = np.array(list(values.values()), dtype=float)

    return decoded


# ------------------------------- #
#           2. Fetching           #
# ------------------------------- #


def eurostat_url(dataset: str, year: int) -> str:
    """The dissemination API URL of a dataset's electricity balances in GWh for `year`.

    Args:
        dataset (str): 'nrg_bal_c' or 'nrg_d_hhq'.
        year (int): The Backcast Year.

    Returns:
        str: The URL.
    """
    query = {
        "format": "JSON",
        "lang": "EN",
        "siec": "E7000",
        "unit": "GWH",
        "time": str(year),
        "nrg_bal": list(DATASET_BALANCES[dataset]),
    }
    return f"{EUROSTAT_API}/{dataset}?{urlencode(query, doseq=True)}"


def download_json(url: str) -> dict:
    """GET a JSON response.

    Args:
        url (str): The URL.

    Returns:
        dict: The parsed response.
    """
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise Exception(f"Eurostat returned {response.status_code} for {url}: {response.text[:500]}")
    return response.json()


def fetch_eurostat(dataset: str, year: int, eurostat_data_path: str | Path) -> pd.DataFrame:
    """A dataset's electricity balances for `year`, from the cache or else the dissemination API.

    Args:
        dataset (str): 'nrg_bal_c' or 'nrg_d_hhq'.
        year (int): The Backcast Year.
        eurostat_data_path (str | Path): The cache folder.

    Returns:
        pd.DataFrame: Columns 'Country' (Balmorel's code, e.g. 'GR' for
            Eurostat's 'EL'), 'Balance' and 'GWh'.
    """
    cache = Path(eurostat_data_path) / f"{year}_{dataset}.json"
    if cache.exists():
        response = json.loads(cache.read_text())
    else:
        url = eurostat_url(dataset, year)
        print(f"Fetching {dataset} for {year} from Eurostat")
        response = download_json(url)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(response))

    decoded = decode_jsonstat(response)
    decoded = decoded[decoded["nrg_bal"].isin(DATASET_BALANCES[dataset])]
    if "time" in decoded.columns:
        decoded = decoded[decoded["time"].astype(str) == str(year)]

    return pd.DataFrame(
        {
            "Country": decoded["geo"].replace(GEO_TRANSLATION).to_numpy(),
            "Balance": decoded["nrg_bal"].to_numpy(),
            "GWh": decoded["Value"].to_numpy(),
        }
    )


def electricity_balances(year: int, eurostat_data_path: str | Path) -> pd.DataFrame:
    """Final electricity consumption and the four electricity-for-heat balances per country.

    Args:
        year (int): The Backcast Year.
        eurostat_data_path (str | Path): The cache folder.

    Returns:
        pd.DataFrame: Index country, one column per balance code (GWh). A
            value Eurostat doesn't report is NaN.
    """
    balances = pd.concat([fetch_eurostat(dataset, year, eurostat_data_path) for dataset in DATASET_BALANCES])
    columns = [balance for codes in DATASET_BALANCES.values() for balance in codes]

    return balances.pivot_table(index="Country", columns="Balance", values="GWh", aggfunc="first").reindex(
        columns=columns
    )

# Economics Utilities: Currency and Inflation Adjustment

This module provides tools for working with currency conversion rates and inflation correction based on official Eurostat data. It enables converting values between currencies and years, applying harmonised price indices (HICP) for consumer prices, and integrates easily with energy system modeling workflows.

## Overview

The utilities in `src/pybalmorel/economics/prices.py` support:

- Loading currency-to-euro conversion rates from Eurostat datasets
- Loading harmonised price indices (HICP) for inflation adjustments
- Correcting values for inflation between two years for a selected region
- Converting values between Euros and other currencies using official exchange rates

Eurostat official data are required, and must be downloaded separately (links below).

## Data Sources

- **Currency Conversion Rates**: [TEC00033](https://ec.europa.eu/eurostat/web/products-datasets/-/TEC00033)
- **Harmonised Index of Consumer Prices (HICP)**: [PRC_HICP_AIND](https://ec.europa.eu/eurostat/databrowser/product/page/PRC_HICP_AIND)

Download, extract, and place the data files in your working directory or as specified by function arguments.

## Functions

### `get_conversion_rate(path, filename="estat_tec00033.tsv")`
**Returns:** DataFrame of conversion rates from currencies to Euro.

| Argument  | Type   | Description                                    |
|-----------|--------|------------------------------------------------|
| path      | str    | Directory with Eurostat currency data          |
| filename  | str    | Name of Eurostat file (default: estat_tec00033.tsv) |

Raises FileNotFoundError if file missing.

### `get_harmonised_price_index(path, filename="estat_prc_hicp_aind$defaultview_filtered.tsv", index_choice="CP00")`
**Returns:** DataFrame of harmonised annual price indices.

| Argument     | Type   | Description                                                      |
|-------------|--------|------------------------------------------------------------------|
| path        | str    | Directory with Eurostat HICP data                                 |
| filename    | str    | Name of Eurostat file (default: estat_prc_hicp_aind$defaultview_filtered.tsv) |
| index_choice| str    | HICP index code, default 'CP00' (all-items HICP)                 |

### `inflation_correction(value, year_to, year_from, inflation_table, region="EU")`
**Returns:** `float` with the value inflation-corrected from year_from to year_to.

| Argument        | Type        | Description                                               |
|----------------|-------------|-----------------------------------------------------------|
| value          | float       | Base value to correct                                     |
| year_to        | int         | Target year                                               |
| year_from      | int         | Source (base) year                                        |
| inflation_table| pd.DataFrame| DataFrame (see above) of HICP indices used for correction |
| region         | str         | Code (e.g. "EU"), default "EU"                           |

Raises ValueError if more than one matching price index is found.

### `euro_conversion_rate(year, currency, currency_table)`
**Returns:** `float` for the conversion rate (currency/Euro) in a specific year.

| Argument      | Type        | Description                                     |
|-------------- |------------|-------------------------------------------------|
| year          | int        | Year to lookup                                  |
| currency      | str        | Currency code, e.g. 'USD', 'DKK'                |
| currency_table| pd.DataFrame| Table of conversion rates (from get_conversion_rate) |

Raises ValueError if more than one matching rate is found.

## Example Usage

```python
from pybalmorel.economics.prices import (
    get_conversion_rate, get_harmonised_price_index, inflation_correction, euro_conversion_rate
)

currency_table = get_conversion_rate("tests/output")
hicp = get_harmonised_price_index("tests/output")
converted_value = inflation_correction(10, 2016, 2024, hicp)
print(f"10 € converted from €2024 to €2016: {converted_value}")
in_usd = converted_value * euro_conversion_rate(2016, "USD", currency_table)
print(f"Then, convert this to USD2016: {in_usd}")
```

See [Eurostat TEC00033](https://ec.europa.eu/eurostat/web/products-datasets/-/TEC00033) and [Eurostat PRC_HICP_AIND](https://ec.europa.eu/eurostat/databrowser/product/page/PRC_HICP_AIND) for data files and descriptions.

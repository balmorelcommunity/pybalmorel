# Economic Adjustments: Currency & Inflation Tools

This page covers utilities for currency conversion and inflation correction in pre-processing, from `pybalmorel.economics.prices`.

These tools use official Eurostat data sources to:

- Load annual currency-to-euro conversion rates
- Load harmonised consumer price indices (HICP)
- Correct values for inflation between years/regions
- Convert Euros to/from other currencies for modeling

## Data Sources

- [TEC00033] Eurostat Currency Conversion Rates: https://ec.europa.eu/eurostat/web/products-datasets/-/TEC00033
- [PRC_HICP_AIND] Harmonised Index of Consumer Prices: https://ec.europa.eu/eurostat/databrowser/product/page/PRC_HICP_AIND

### Requirements
- Download/untar files from official Eurostat links.
- Place in a directory and provide path to all loader functions.

---

## API Overview

### `get_conversion_rate(path, filename="estat_tec00033.tsv")`
Loads exchange rates (currency→EUR, annual).
- path: str — Directory with Eurostat file
- filename: str — e.g. 'estat_tec00033.tsv'
- Returns: DataFrame (currencies/rates by year)

### `get_harmonised_price_index(path, filename="estat_prc_hicp_aind$defaultview_filtered.tsv", index_choice="CP00")`
Loads HICP for consumer price inflation (all-items default).
- path: str — Directory with Eurostat file
- filename: str — e.g. 'estat_prc_hicp_aind$defaultview_filtered.tsv'
- index_choice: str — HICP code, default 'CP00'
- Returns: DataFrame (annual indices)

### `inflation_correction(value, year_to, year_from, inflation_table, region="EU")`
Inflation-correct value from `year_from` → `year_to` using regional index.
- value: float — Initial value
- year_to: int
- year_from: int
- inflation_table: pd.DataFrame — HICP (from above)
- region: str — HICP region, default 'EU'
- Returns: float — Corrected value

### `euro_conversion_rate(year, currency, currency_table)`
Get currency/Euro rate for year/currency combo.
- year: int
- currency: str — e.g. 'USD', 'DKK'
- currency_table: DataFrame — as from get_conversion_rate
- Returns: float rate

---

## Example

```python
from pybalmorel.economics.prices import (
    get_conversion_rate, get_harmonised_price_index,
    inflation_correction, euro_conversion_rate
)

currency_table = get_conversion_rate("tests/output")
hicp = get_harmonised_price_index("tests/output")
converted_value = inflation_correction(10, 2016, 2024, hicp)
print(f"10 € converted from €2024 to €2016: {converted_value}")
in_usd = converted_value * euro_conversion_rate(2016, "USD", currency_table)
print(f"Then, convert this to USD2016: {in_usd}")
```

Official Eurostat links above describe file formats and variables in detail.
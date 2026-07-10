"""
ENTSO-E Data Preprocessing Module
================================

This module provides functionality for fetching, processing, and validating
historical electricity market data from the ENTSO-E Transparency Platform
for use in Balmorel model backcasting and validation.

Module Structure
---------------

The module consists of two main components:

1. **Data Fetching** (`__init__.py`)
   - Fetches raw data from ENTSO-E API
   - Handles authentication and API key management
   - Supports annual data downloads for:
     - Load data
     - Day-ahead prices
     - Generation data
     - Cross-border flows

2. **Data Processing & Validation** (`__main__.py`)
   - Loads and formats ENTSO-E CSV data
   - Aligns Balmorel model results with ENTSO-E data
   - Provides statistical analysis and visualization
   - Supports backcast validation workflows

Key Features
------------

- **Bidding Zone Mapping**: Comprehensive mapping between ENTSO-E bidding zones
  and Balmorel model regions (see `bidding_zone_codes` and `bidding_zone_translation`)

- **Technology Categorization**: Standardized mapping of generation technologies
  between ENTSO-E and Balmorel (see `balmorel_to_category` and `entsoe_to_category`)

- **Temporal Alignment**: Conversion between Balmorel's seasonal time slices
  and ENTSO-E's hourly data

- **Data Aggregation**: Spatial aggregation of sub-regions (e.g., DE4 zones → DE,
  IT-* zones → IT)

- **Visualization**: Built-in plotting functions for:
  - Generation mix comparison
  - Price duration curves
  - Regional comparisons

Usage
-----

The module provides a CLI interface with three main commands:

```bash
# Fetch and format data for validation
python -m pybalmorel.entsoe format \
    <balmorel-scenario> \
    <balmorel-scenario-path> \
    <entsoe-data-path> \
    <year>

# Generate statistics
python -m pybalmorel.entsoe statistics <balmorel-scenario-path>

# Generate plots
python -m pybalmorel.entsoe generation <balmorel-scenario-path>
python -m pybalmorel.entsoe prices <balmorel-scenario-path>
```

Configuration
-------------

- **API Key**: Set `ENTSOE_API_KEY` in `.env` file or provide when prompted
- **GAMS Path**: Set `GAMS_SYSTEM_DIR` in `.env` for Balmorel result processing
- **Output**: Processed data cached in `<scenario-path>/backcastoutput/`

Data Flow
---------

1. Raw ENTSO-E data fetched via API and saved as CSV
2. Balmorel model results extracted from GDX files
3. Both datasets formatted to common temporal and regional structure
4. Datasets aligned and joined for comparison
5. Statistics calculated and visualizations generated

Limitations
------------

- No data available for Cyprus (CY) or Turkey (TR) in ENTSO-E
- Some bidding zones may lack complete data coverage
- Cross-border flow data requires explicit region pairs
"""

"""
Hydro Reference

Observed long-term Natural-Inflow Hydro per country, the reference for the
plausibility check and the Hydro Inflow Fallback of Absolute Hydro FLH (see
CONTEXT.md and docs/adr/0011). Bundled, like the deflator table of ADR 0009,
so a weather-year run needs no download.

Mean annual gross generation 2013-2022 (the ten years before the newest
weather year in the 2023 inputs, never the Backcast Year itself), TWh/yr, to 0.1 GWh.

Sources, retrieved 2026-10-22:
- Eurostat nrg_bal_c, nrg_bal=PPRD, siec=RA100, unit=GWH (primary production
  of hydro). Pumped-storage output, including the pumped part of mixed plants,
  is booked separately under RA130 (Energy Balance Guide), so RA100 is
  natural inflow only. nrg_bal_peh has no RA110/RA120 split; its GEP RA100
  equals PPRD RA100 except for UK and UA, where it includes pumped output.
  Eurostat 'EL' is 'GR' here. UK covers 2013-2019, UA 2013-2020 and BA
  2014-2022; every other country 2013-2022.
- CH (not in Eurostat): Swiss Federal Office of Energy, electricity balance
  (opendata ogd32), run-of-river + storage generation minus 0.73 x storage
  pump consumption - Eurostat's default for pumped output when it isn't
  measured. Calendar years.

Created on 22.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""

hydro_natural_inflow_twh = {
    "AL": 6.4666, "AT": 39.2284, "BA": 5.4909, "BE": 0.318, "BG": 4.0519,
    "CH": 35.66, "CY": 0.0, "CZ": 2.059, "DE": 19.5683, "DK": 0.0164,
    "EE": 0.025, "ES": 29.5594, "FI": 14.4463, "FR": 59.1657, "GE": 9.1683,
    "GR": 4.9274, "HR": 6.7955, "HU": 0.2303, "IE": 0.7451, "IS": 13.5477,
    "IT": 45.1929, "LT": 0.4251, "LU": 0.0989, "LV": 2.6276, "MD": 0.0506,
    "ME": 1.7262, "MK": 1.4693, "MT": 0.0, "NL": 0.0811, "NO": 136.4363,
    "PL": 2.1507, "PT": 11.1317, "RO": 16.293, "RS": 10.0122, "SE": 67.1323,
    "SI": 4.4879, "SK": 4.2005, "TR": 64.2245, "UA": 8.599, "UK": 5.6453,
    "XK": 0.2164,
}

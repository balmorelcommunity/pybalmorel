"""
Backcasting

Validate simulated Balmorel behaviour against historical ENTSO-E data:
load/price/generation/flow comparison, the Observed Flow Limit XKFX overrides,
and historical fuel prices and CO2 tax on the UTC Backcast Calendar
(see CONTEXT.md and docs/adr/0005-0010). Depends on pybalmorel.entsoe
for raw data access; pybalmorel.entsoe never depends on this package.

Created on 07.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""

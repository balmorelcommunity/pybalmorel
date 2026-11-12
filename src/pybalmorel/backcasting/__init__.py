"""
Backcasting

Validate simulated Balmorel behaviour against historical ENTSO-E data:
load/price/generation/flow comparison, and the Calibration Inputs of a
Backcast on the UTC Backcast Calendar: the Observed Flow Limit XKFX
overrides, nuclear and thermal availability, the must-run floor, the VRE
level, the demand profiles and level (with Eurostat heating), and
historical fuel prices and CO2 tax (see CONTEXT.md and docs/adr/0005-0012).
Depends on pybalmorel.entsoe for raw data access; pybalmorel.entsoe never
depends on this package.

Created on 07.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""

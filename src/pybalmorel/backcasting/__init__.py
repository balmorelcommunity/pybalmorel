"""
Backcasting

Validate simulated Balmorel behaviour against historical ENTSO-E data:
load/price/generation comparison and the Observed Max Flow XKFX overrides
(see CONTEXT.md and docs/adr/0001, 0002, 0003). Depends on pybalmorel.entsoe
for raw data access; pybalmorel.entsoe never depends on this package.

Created on 07.08.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""

# pybalmorel

A Python toolkit for pre-processing, running, and post-processing the Balmorel energy system model. Includes a backcasting toolbox that validates simulated Balmorel behaviour against historical ENTSO-E data.

## Language

### Backcasting

**Observed Max Flow**:
The maximum hourly cross-border electricity flow recorded by ENTSO-E on a given directed border-pair within a year. Used as an exogenous transmission constraint in backcasting runs, standing in for whatever combination of technical, market, maintenance, and social/political constraints actually limited flow that year.
_Avoid_: Capacity, Transmission Capacity, NTC

**Transmission Capacity (NTC)**:
The grid operator's rated/commercial cross-border transfer capability, independent of whether it was ever fully utilised. Deliberately *not* used for backcasting — Observed Max Flow is used instead, since backcasting aims to reproduce what actually happened in a given historical year, not what was technically possible.
_Avoid_: Capacity (when ambiguous with Observed Max Flow)

**Canonical Region Name**:
A shared identifier used to bridge a Balmorel region and an ENTSO-E bidding zone when the two disagree on spelling or resolution (e.g. Balmorel's `DE4-E`/`DE4-N`/`DE4-S`/`DE4-W` and ENTSO-E's `IT-NORD`, `IT-CNOR`, etc. all canonicalize to `DE`/`IT`). Defined by `bidding_zone_translation`; a name absent from it is already canonical.

**ENTSO-E Zone Code**:
The raw identifier the ENTSO-E transparency platform API expects for a query (e.g. `10YNO-1--------2`, `DE_LU`) — one layer downstream of a Canonical Region Name, which a code can share (`FR`) or differ from entirely.
_Avoid_: Region, Zone (when ambiguous with Canonical Region Name)

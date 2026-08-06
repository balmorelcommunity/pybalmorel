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

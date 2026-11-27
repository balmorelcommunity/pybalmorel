# Optional Input Data splits exogenous demand by Demand User, matched strictly to the results

Balmorel's results sum exogenous demand over its Demand Users (`EXOGENOUS`
in `EL_DEMAND_YCR` and `H_DEMAND_YCRA`). The IAMC conversion needs those
users to report demand by Final Energy Sector, e.g.
`Final Energy|Residential|Electricity`, which the NMSF Template asks for.
Only the Input Data of a run gives them: add-ons change `DE` and `DH` before
the model uses them, so the `.inc` files don't.

So `to_iamc` and `sankey_flows` take an optional `input_data`: the path to
a compiled `<scenario>_input_data.gdx`, or a dict of paths per Balmorel
scenario. The Reader takes only `DE` and `DH` from it; everything else
still comes from the results (ADR 0016). Exogenous electricity in a region
and year is split by `DEUSER` only where the users add up to the results'
`EXOGENOUS` within 0.1%. Each individual area's On-Site Fuel Use, On-Site
Use electricity, Heat Exchange in and demand-side emissions are split
between `Residential` and `Commercial` by its `DHUSER` shares, under the
same check. Where a figure fails the check, only its total is reported,
and a Conversion Note names the regions. Rows in the 'demand_users' rule
table give each user its Final Energy Sector. The default rows assume DTU's
Balmorel data.

The check lets one file serve several Balmorel scenarios without silently
giving a scenario the split of another. In 2024_kountouris, one
`base_input_data.gdx` matches all three scenarios exactly.

## Considered options

- **Scale the users' shares to the results' total, without the check.** It
  splits everywhere, but a file from another scenario or an older data set
  would give the wrong sector split with nothing to show it.
- **Read the `.inc` files, or run GAMS to compile them.** The `.inc` files
  miss what the add-ons change, e.g. the industry add-on moving electric
  process heat out of `PII`. Running GAMS needs a licence and the whole
  model at conversion time.
- **Balmorel reports demand by user in its results.** This is proposed
  upstream (exogenous demand by `DEUSER` and `DHUSER` in MainResults). It
  is the better source, and the only one that can give heat by user when
  INDIVUSERS' group shift is on. Results already produced, such as
  2024_kountouris', won't have it.
- **Report individual areas as `Residential and Commercial` only.** It is
  simpler, but the NMSF Template has no such variable, so a submission
  would carry no residential or commercial final energy or demand-side
  emissions. `Residential and Commercial` is reported anyway, as the sum
  of the two. In the common definitions it is their sibling, not their
  parent.

## Consequences

- Without `input_data` the conversion works as before. Exogenous
  electricity goes to `Final Energy|Electricity` only, and individual areas
  to `Residential and Commercial`.
- A Demand User without a rule row counts in `Final Energy|Electricity`
  only, and a Conversion Note gives its amount. Sector totals are reported
  even so, and each note says how much exogenous electricity no sector got.
- With DTU's data, `Commercial` is small and `Other Sector` large: services'
  own electricity is in `OTHER`. The rows' notes say so.
- Where INDIVUSERS' group shift is on, it moves heat demand between a
  region's individual areas. An area's users then rarely add up to the
  results' total, and the area stays under `Residential and Commercial`.
  2024_kountouris runs with the shift off.

# Take the Demand Level net of the model's own electric heating, iterated over runs

Balmorel adds electric heating (`ENDOGENOUS_ELECT2HEAT`, E2H) and
transmission losses on top of the exogenous demand `DE`. ENTSO-E's load
contains both. So the Demand Level has to leave out the heating Balmorel
adds back, with the same scope, or every country's load gap carries the
difference into generation, prices and flows.

The first Demand Level, variant (a′), left out Eurostat's electricity for
heating, H: household space and water heating, plus electric boilers and
heat pumps in district heating. Balmorel's E2H covers more: industrial
process heat, services heating, and individual users. In `backcast_R2023`
of 2026-11-04, solved with (a′), Balmorel's load matched ENTSO-E's at
system level (2,694.7 against 2,699.6 TWh), but the country gaps summed to
175 TWh in absolute terms, nearly all of it E2H − H: IT +50.6 TWh (E2H − H
+45.5), FR −25.5 (−24.7), NO −13.5 (−13.6). The system match itself hid
offsetting errors (LU left out of the Balmorel side, `DE` 0.27% low).
(a′) also counted transmission losses twice, about 20 TWh in that run,
and the distribution losses Balmorel books on wind and solar output,
about 7 TWh.

The Demand Level of canonical region k is now

    X_k = (L_k − T_k − E_k − O_k)(1 − d_k)

with L_k ENTSO-E's load, d_k the distribution loss, and T_k, E_k and O_k
the previous backcast run's transmission losses, electricity for heat, and
distribution losses on anything but exogenous demand (on its electric
heating, and the 1–2% of wind and solar output Balmorel books as
distribution loss), summed over k's Balmorel regions and scaled from the
calendar's 8736 hours to Balmorel's 8760. Balmorel's load as `format`
compares it, `EXO + E2H + DIST_LOSSES + TRANS_LOSSES`, then equals L_k
exactly, as long as E2H and the losses stay as they were.

They don't, because E2H responds to prices: lower `DE` gives lower prices
and more electric heating, roughly −0.3 TWh of E2H per TWh of `DE` in
Europe (−0.06 in IT to −0.59 in ES, from two runs that differed in more
than `DE`). The level is therefore a fixed-point iteration over runs,
`X_{n+1} = (L − T_n − E_n − O_n)(1 − d)`, which converges for any slope between
−1 and 0, with the error shrinking by about that factor each run.
`demand-level --heat model` is the default. Each run prints the previous
run's residual, X less that run's exogenous load, summed over Europe and
summed in absolute terms over countries. The user decides when to stop:
nothing caps the number of runs, and about 10 TWh summed over countries is
the guidance, since other errors remain. The first run of a new Backcast
Year has no previous run, so it takes `--heat eurostat`, which is (a′).

## Considered options

- **Keep (a′).** It needs no previous run, and its system total was close.
  Rejected: the scope difference E2H − H lands in each country's load, so
  a supply-side comparison per country inherits it (IT's generation and
  imports are compared against 50 TWh of demand that ENTSO-E never saw).
- **Fix the scope of E2H in base data**, so that Balmorel's electric
  heating matches Eurostat's scope and (a′) becomes exact. Rejected for
  now: it changes base data that other scenarios use (backcast corrections
  stay in override files, ADR 0006), Eurostat has no split of electric
  heating in services and industry to match, and transmission losses would
  still be in the gap.
- **An enforced stop rule or a relaxation factor** (`X_new = ωX + (1−ω)X_prev`).
  Not built: with a slope near −0.3 plain iteration converges in two or
  three runs, and the user prefers to judge the residual. Relaxation can be
  added if a country oscillates.

## Consequences

- A country's total load is a Calibration Input at every level, the
  system's and each country's, up to the last residual. The evidence on
  demand is E2H against H per country (`E2H_minus_H_TWh` in
  `demand_level.csv`), read knowing the scopes differ. IT's E2H barely
  responds to prices, so its excess is structural (capacity or heat-demand
  allocation), and C moves it out of IT's load rather than fixing it.
- A backcast takes several runs, each a full-year hourly run (the check
  rejects a sampled run), and `format` must run on each before the next
  `demand-level`. The level depends on the previous run, so a change to
  any other input (capacities, fuel prices) moves the fixed point and
  needs another iteration or two.
- The previous run must have solved with the scenario's current
  `DE_ENTSOE.inc`. The command warns where its exogenous load is more than
  1% off that file's level, and warns if the INDUSTRY or INDIVUSERS
  wrappers that re-apply the level are missing.
- A country without Eurostat balances (CH) gets a level under C, since
  only ENTSO-E load and the previous run are needed; its coverage check is
  skipped and noted.
- The hourly shape stays ENTSO-E's total load profile, which includes
  electric heating. Subtracting the previous run's hourly heating from the
  profile as well is deferred.

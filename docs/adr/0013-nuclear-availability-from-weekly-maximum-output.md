# Rate nuclear per week from its highest observed output

In Balmorel's base data, nuclear has a flat rating of
1 − GDPLANMAINT/8760 = 0.9425 all year. In the 2023 backcast that let France
produce about 505 TWh against 319 TWh observed, because the year's long
outages are not in the base data. Nuclear runs whenever it is available, so
its output is set by availability, not by dispatch. We therefore treat it
as a Calibration Input, like the Observed Flow Limit (ADR 0010) and, later,
the VRE Level (ADR 0012).

The **Nuclear Availability** of a country in one week of the Backcast
Calendar is its highest hourly nuclear output that week, as reported by
ENTSO-E, divided by its nuclear `GKFX` in the Backcast Year and clipped at
1. `nuclear-availability` writes it as weekly `GKRATE` overrides to
`GKRATE_ENTSOE.inc`. The scenario's `GKRATE.inc` includes that file after
the base ratings, which is the override-file pattern of ADR 0006. Every
nuclear technology in a country gets the same rating, because ENTSO-E
reports nuclear output per bidding zone, not per unit. The week's highest
output is a lower bound on what could run, for the same reason as the
observed flow in ADR 0005: the fleet produced that much in at least one
hour. A week is long enough to contain an outage and short enough to place
it in the year. It is also Balmorel's season, so the ratings fit
`GKRATE(AAA,GGG,SSS)`.

The weeks after a country's last week with data are rated zero. ENTSO-E
stops reporting a fleet that has closed instead of reporting zeros, as for
Germany after 15 April 2023. A data feed that just stops looks the same, so
the command warns loudly. Any other week without data keeps the base
rating. A zero is written as `eps`, because Balmorel reads a literal 0 as
full capacity.

## Considered options

- Balmorel's own maintenance scheduling (`PLANNED_MAINTENANCE`): rejected.
  It places a generic amount of maintenance where it costs least, not when
  the outages of the Backcast Year happened. With the weekly ratings, it
  would also come on top of outages that the ratings already contain, so it
  is off in the backcast.
- The week's mean output: rejected. It fixes the week's energy to the
  observed energy, and Balmorel could only reach it by running flat out in
  every hour. That removes the load following the fleet actually did
  within the week.
- An annual energy limit (`GMAXF`): rejected. It says nothing about when
  the outages happened, so Balmorel would put its own outages in the
  cheapest hours.
- ENTSO-E outage reports, as ADR 0014 uses for thermal capacity: not
  needed. Nuclear output is not a Validation Metric, so nothing argues
  against using observed output, and that output was already being
  downloaded for the validation.

## Consequences

- Each country's annual nuclear output is fixed by a Calibration Input, so
  it is not evidence in Backcast Validation. How the fleet's output varies
  within each week still is.
- Because the rating comes from the week's highest hour, Balmorel can match
  the observed output in every hour of the week. The exception is a rating
  clipped at 1: ENTSO-E reports Romania's Cernavoda at up to 1,453 MW
  against 1,300 MW of `GKFX`, which is a reporting difference.
- A `GKFX` that is too high is offset by a lower rating. A `GKFX` that is
  too low can't be corrected by the rating, because ratings are clipped at
  1. Units that ran in the Backcast Year but are missing from base `GKFX`
  must therefore be added to the scenario's `GKFX`. For 2023 these are
  Isar 2, Neckarwestheim 2, Emsland and Olkiluoto 3.
- A country without ENTSO-E nuclear output keeps the base rating. In 2023
  that is the UK.
- The scenario needs `GKRATE_DOL` set to `AAA_GGG_SSS`, and
  `PLANNED_MAINTENANCE` off.

# Rate thermal capacity from installed capacity and outages, not observed output

Base `GKFX` overstates the fossil fleet of the Backcast Year, and all of it
is available all year. In the 2023 backcast, Germany had 48.0 GW of hard
coal and lignite against an observed maximum of 31.9 GW. Too much cheap
capacity flattens the top of the merit order, and the backcast's thermal
output was too high.

The **Thermal Availability** of a fuel group in a country and week is
k(1 − u):

- k is ENTSO-E's installed capacity of the group divided by its `GKFX`,
  capped at 1.
- u is the energy that ENTSO-E reports as out of service that week, divided
  by the installed capacity × 168 h. It counts planned and forced outages,
  takes the latest revision of each event, and drops cancelled and
  withdrawn events.

`thermal-availability` writes it as weekly `GKRATE` overrides to
`GKRATE_THERMAL_ENTSOE.inc`, which the scenario includes after the nuclear
ratings. The groups are coal (hard coal and lignite), gas, oil, oil shale
and peat, biomass, and waste. Technologies are assigned to a group by their
`GDFUEL`. Hard coal and lignite are one group because Balmorel labels the
lignite fleets of e.g. BG, RO, CZ, HU and SK as `COAL`, which ENTSO-E reports
as lignite; separate groups rated them by the country's small hard coal
fleet (2026-11-12).
An electricity-producing fuel that belongs to no group stops the command,
so a new fuel can't silently keep full availability. Every technology of a
group in a country gets the same rating.

Nuclear takes its availability from observed output (ADR 0013), and thermal
capacity deliberately doesn't. The fossil mix, meaning how much each group
produces and when, is a Validation Metric. A ceiling taken from observed
output, such as the week's highest hour, would fix the top of that mix by
construction. Installed capacity and outage reports describe what could
have run, independently of what the market chose to run.

## Considered options

- Nuclear's method, the week's highest observed output per group: rejected
  for the reason above.
- Correcting `GKFX` to ENTSO-E's installed capacity: rejected. ENTSO-E
  reports per bidding zone and production type, but `GKFX` is per area and
  technology, so the correction would need a split that no data provides. A
  rating scales every technology of the group in a country by the same
  factor, and it leaves the base data alone (ADR 0006).

## Consequences

- Outages are averaged over the week, but output peaks within it. A unit
  that was out for half the week counts as half a unit for the whole week,
  so the rated capacity can be below the week's observed peak. With the
  2023 reports, DE lignite is rated below its observed weekly peak in 9
  weeks, by up to 1.2 GW, and Balmorel can't reproduce those peak hours.
  Nuclear's weekly maximum has no such gap.
- k is a ratio of totals, so it derates the whole group rather than the
  units that actually closed. Where ENTSO-E covers less than Balmorel does,
  typically small CHP and industrial plants, k is too low: ES waste gets
  0.10 and PL biomass 0.19. Those plants also produce heat, so the derating
  reaches the heat balance as well.
- Where ENTSO-E reports more installed capacity than `GKFX`, as for DE gas
  (33.1 against 24.8 GW), k is 1. The rating never adds capacity.
- A group without ENTSO-E installed capacity keeps its base `GKRATE`. A
  country without outage reports only gets k. The command warns in both
  cases.
- The Must-run Floor is capped at `GKFX` × `GKRATE` (Balmorel ADR 0005), so
  the thermal ratings must be written before the floor.
- Thermal output stays a Validation Metric. The ratings come from different
  ENTSO-E datasets than the output being validated, so an error in either
  one shows up as a validation gap rather than being fitted away.

# Scale weather-year VRE full-load hours to the backcast year's observed output

The weather-year full-load hours for wind and solar describe CorRES's
technology, not the fleet that stood in the backcast year: DE PV 1,272 h
against about 885 h delivered on Balmorel's capacity in 2023. We scale them
per country and kind (solar, onshore, offshore) so that the output Balmorel
can produce equals ENTSO-E's reported output, and keep the weather year's
hourly profiles and the spread between areas.

Unlike hydro (ADR 0011, where the backcast year's generation is never the
reference), wind and solar output is not dispatched: apart from curtailment
it is the resource, the same argument that made observed nuclear output an
availability input. So a country's annual wind and solar output becomes a
Calibration Input and stops being evidence in Backcast Validation. The
hourly timing still comes from the weather year and remains a check.

## Considered options

- Correct `GKFX` to ENTSO-E's installed capacity and keep CorRES's
  full-load hours: rejected as the main fix. DE PV's 1,272 h is too high
  on any capacity Germany had in 2023. Used instead for the countries whose
  factor falls outside the bounds, which are capacity or reporting gaps.
- Set full-load hours per country to observed output ÷ `GKFX` directly:
  rejected, since it erases the difference between a country's areas
  (DE4-S onshore 2,856 h against DE4-N 2,444 h).

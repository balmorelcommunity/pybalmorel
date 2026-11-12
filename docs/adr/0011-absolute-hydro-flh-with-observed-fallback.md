# Take the hydro inflow level from CorRES, with an observed long-term fallback

The weatheryear module wrote hydro full-load hours as a factor on Balmorel's
base FLH: that year's CorRES inflow over its long-term mean. The year's
variation came from CorRES, the level from Balmorel's base data, which is
placeholder data (reservoir FLH "set equal to ROR"). In the 2023 backcast that
put Austria at 59 TWh against ~41 observed and Italy at 70 against ~40-45.

In absolute mode, the FLH is CorRES's inflow energy for the year divided by
the Balmorel capacity of that hydro type in the area. Run-of-river energy
above the area's run-of-river capacity in an hour moves to its reservoir,
because CorRES and Balmorel split an area's hydro differently and Balmorel
would otherwise spill it.

CorRES's inflow is wrong in several countries (identical reservoir and
run-of-river series, sub-areas carrying the national series, Switzerland at
under half its observed output). For a country that fails a plausibility
check, the level comes from observed long-term natural-inflow hydro (Eurostat,
bundled as in ADR 0009) and CorRES still gives the year's variation. We never
use the backcast year's own observed generation: hydro output is a validation
metric, and calibrating its level to the same year would make that comparison
meaningless. Countries that CorRES covers only partly or not at all get
the same fallback (Turkey alone would otherwise keep 94.5 TWh of placeholder
inflow against 64 TWh observed); without CorRES data the year's variation is
lost and the level is the long-term one. The fallback is temporary, until
CorRES releases corrected and complete series.

Relative mode stays the default, so weather-year runs outside the backcast
are unchanged.

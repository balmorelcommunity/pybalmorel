# Cap backcast transmission at a percentile of observed flow, not its maximum

ADR 0005 chose observed flow over NTC as the backcast transmission constraint
and took the yearly maximum hourly flow. That reasoning stands, but the
maximum turned out to be a single extreme hour on many borders: in 2023,
FR→IT reached 9,841.5 MW in one hour (2023-06-12 08:00 UTC), with only 8
hours above 4,500 MW. Balmorel moves power at no cost up to its limit, so a
limit set by one hour is used in many, and the 2023 backcast had flows
either at the limit or at zero.

The **Observed Flow Limit** is the 99th percentile of the hourly flow in one
direction, over the hours with flow in that direction, on the series summed
over every ENTSO-E zone pair of the canonical border. It replaces "max" in
ADR 0005 for both the `XKFX_ENTSOE.inc` overrides and the validation's
`Limit`. We take the percentile over flowing hours because over all hours a
rarely used direction is cut to near zero (SE3→SE2 would close entirely).
We sum hour by hour before taking the percentile, because adding per-file
maxima from different hours overstates a border made of several zone pairs.
The percentile is a CLI option (`--percentile`, default 99); 100 gives back
the maximum of the summed series.

We accept that Balmorel will still use a border either fully or not at all,
since it has no flow-dependent cost. Flows remain a validation metric
compared by energy and by the share of hours at the limit, not something
the inputs are tuned to match.

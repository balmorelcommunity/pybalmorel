# Rate transmission weekly from outage reports, not observed flows

A Backcast's transmission capacity is the Observed Flow Limit: the p99 of a
direction's hourly flows over the Backcast Year (ADRs 0005 and 0010), and
available every hour. A cable that was out for a month, or a border derated
for maintenance, still carries its full limit in Balmorel, so the backcast
can trade across borders that were closed or cut.

The **Transmission Availability** of a direction in a week is the mean over
the week's minutes of min(remaining, limit) / limit:

- remaining is the capacity ENTSO-E's transmission outage reports (A78,
  Transparency Platform 10.1.A planned and 10.1.B forced) leave in service
  in that direction. Reports hold at minute resolution. Overlapping reports
  take the lowest capacity. A border of several ENTSO-E zone pairs sums
  the pairs, a pair without a report at that time counting its largest
  reported capacity. A minute without any report counts as the full limit.
- limit is the direction's Observed Flow Limit, the `XKFX` summed over the
  border's Balmorel lines.

Only the latest revision of each report counts, cancelled reports are
dropped (the API already leaves out withdrawn ones), and exact duplicates
count once. Planned and forced outages both count.

Reports on "Operational Security" assets are dropped too. Svenska kraftnät
and Fingrid file year-long limits on the Swedish and Finnish borders as
planned maintenance of an "AC Link" with that name (e.g. "Operational
Security SE3": FI→SE3 at 0–800 MW of an 857 MW limit for all of 2023). Only
the name tells them from an outage. A TSO limiting a border to protect its
own grid is the internal-congestion cut this rating is not meant to
describe, and a prospective scenario would not model it as an outage. With
them, FI→SE3 would be rated 0.40 on average instead of 0.75, and SE2→SE3
0.84 instead of 0.89.

`transmission-availability` writes the ratings as weekly `XKRATE` overrides
to `XKRATE_ENTSOE.inc`. The Balmorel backcast's `XKRATE.inc` resets every
open line to 1 and then includes the file. A rating of 0 is written as
`eps`, since Balmorel reads an `XKRATE` of 0 as 1. Every Balmorel line
between the two zones gets the same rating. No Balmorel code changes:
backcast scenarios already read `XKRATE` per line and season.

## Weekly, not hourly

The reports have minute resolution, so an hourly rating was possible. It is
averaged to weeks because weekly outages are easier to model for a
prospective 2050 study than a specific outage in certain hours. A future
scenario can be given a weekly outage rate for a border; it cannot be given
the hours a specific cable will trip. Calibrating the backcast on the same
kind of input a prospective run can have keeps the two comparable. The price
is that an outage of a few hours derates the whole week a little instead of
closing those hours.

## Only reports that describe the whole border

The reports are not uniform. On HVDC links and the Nordic, DK/NO–DE and
Iberian borders they give the capacity left on the whole border. Elsewhere
they give the capacity left on a single line or circuit, where 0 means one
circuit out, not the border closed (FR–UK, IE–UK, CH–DE, the Balkans). On
Core's flow-based borders they are regional or empty, since the capacity
between Core zones comes from the flow-based parameters. Some TSOs also file
internal-grid events on a border pair.

A direction is therefore rated only if all three hold:

1. Its largest reported capacity is at least half its Observed Flow Limit
   (`--min-reported-share 0.5`). Below that, the reports describe a line,
   not the border.
2. Its border is not between two Core flow-based countries (AT, BE, CZ, DE,
   FR, HR, HU, NL, PL, RO, SI, SK in 2023).
3. Observed flow exceeded the reported capacity, by more than 10 MW or 2% of
   the largest report, in less than a fifth of the hours with a report
   (`--max-exceeded-share 0.2`). Flow above a border's reported capacity
   for that often means the reports don't describe the border's capacity.

Every other direction is rated 1 and keeps its Observed Flow Limit all
year.

The third test uses observed flows, a Validation Metric
([`CONTEXT.md`](../../CONTEXT.md)). It is kept because it is weak: it is a
yes/no decision per direction for the whole year, it can only remove a
rating, never set or raise one, and the ratings themselves come only from
the reports. A border whose flows are badly simulated is not fitted by it.

## Own client for the reports

entsoe-py 0.8.1's `query_unavailability_transmission` returns only the
first 200 reports of a query: it pages by period, not by the API's offset.
A border can have far more in a year (DE_LU→NO2: 1,699 in 2023; 25
directions had more than 200). It also drops each report's asset name and
type, which tell a border report from a line report. `pybalmorel.entsoe`
therefore has its own A78 client (`entsoe/outages.py`, ADR 0007) that pages
by offset up to the API's limit and keeps the assets. It downloads the
Backcast Calendar's 52 weeks, not the calendar year (ADR 0008).

## Considered options

- **Hourly ratings** from the same reports: rejected for the reason above.
- **The week's highest observed flow** per direction, as nuclear takes its
  availability from observed output (ADR 0013): rejected. Flows are the
  Validation Metric this rating is meant to improve, so a ceiling from them
  would fix the top of the flows by construction.
- **Offered NTC** or other hourly operational series: rejected. They are
  observed hour by hour, which a prospective scenario can't be given, and a
  TSO's offered capacity also cuts for internal congestion, which is a
  market outcome, not an outage.
- **Rating every direction with reports**: rejected. Single-line reports
  would close whole borders whenever one circuit is out (FR–UK reports
  0 MW for single circuits), and Core reports would rate borders whose
  capacity is set by the flow-based domain.
- **Reconstructing the border from asset-level reports**, i.e. the nominal
  capacity of each line less the out ones: rejected. The reports give only
  the remaining capacity, not the nominal capacity of the asset, so the
  line's share of the border is unknown.
- **Weekly energy limits** (the sum of a week's flow no higher than a
  share of the limit × 168 h): kept as the fallback, if the backcast still
  overestimates cross-border flows with the ratings. It needs a new
  Balmorel equation.

## Consequences

In 2023, 158 of 190 directed pairs of zones have reports (13,991 events at
their latest revision: 12,477 planned, 1,514 forced). Of the 179 directions
with an Observed Flow Limit, 69 are rated, with 94 of the 243 GW of limits.
Their limit-weighted mean rating is 0.875, so on average 11.8 GW is out,
4.9% of all limits. The deepest ratings are ES→PT 0.65 and PT→ES 0.72,
AT→IT 0.63, DE→DK2 0.67, IT→FR 0.69, NO3→NO5 0.74, FI→SE3 0.75, DK1→DE 0.75
and NO2→DE 0.76. 38 weekly ratings are 0.

- 110 directions keep a rating of 1. Their flows are limited only by the
  annual Observed Flow Limit, and the README of the Balmorel backcast lists
  them under Known limitations: 44 without reports (55.5 GW, mostly Core
  borders that report nothing, the Balkans and TR, DK1↔UK, IT↔MT, and the
  reverse of four rated Nordic directions), 33 with single-line reports
  (31.5 GW: the Balkans, IT's borders with GR, ME and SI, CH's borders
  with DE, FR and IT, FR→UK, BE→UK, UK→IE, NO1↔NO3, NO2→NO5), 20 Core
  flow-based (38.6 GW), and 13 whose flows exceeded the reports too often
  (23.3 GW, e.g. NO5→NO2 76%, FR→IT 57%, DK2→DE 56%).
- The Core borders are not rated at all, so central Europe's flows keep
  their annual limit; the flow-based domain is outside Balmorel's NTC
  model in any case.
- The tests are per direction, so the two directions of a border can differ:
  UK→FR is rated (0.81), FR→UK is not (its largest report is 49% of the
  limit).
- ES↔PT reports cover 8,677 of the 8,736 hours. They name internal
  Portuguese lines (Pegões–Sines, Palmela–Pegões) whose maintenance cuts
  the border, so the Iberian rating is close to a capacity schedule, and
  ES→PT flow exceeded it in 18% of the outage hours, just under the
  threshold.
- A minute without a report counts as the full limit, so the rating can
  only lower the Observed Flow Limit, never raise it.
- The rating is shared by all Balmorel lines between two zones, as the
  reports are per border, not per line.
- The rating is an average, so a week with a two-day outage gets about
  0.7 on every hour of the week. Balmorel can then trade 70% across a
  border that was closed for two days, and less than the limit in the
  other five.
- Cross-border flows stay a Validation Metric. The ratings come from a
  different ENTSO-E dataset than the flows being validated, so an error in
  either one shows up as a validation gap rather than being fitted away.

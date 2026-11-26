# The Sankey classifies MainResults with the IAMC Mapping Rules

A Sankey drawn from MainResults is meant to be compared with one drawn from
the IAMC data that `to_iamc` makes from the same results. For the two to
share node names (Sources, commodities, Final Energy Sectors), Balmorel's
fuels, heat areas, demand categories and OptiFlow flows must be classified
in IAMC terms. The Sankey therefore reads MainResults through the IAMC
Reader and classifies with the same Mapping Rules, Fuel Categories, 'areas',
'demand_categories' tables and OptiFlow Mapping as `to_iamc`, taking the
same overrides. It does its own counting.

The comparison thus tests how `to_iamc` counts (the Output-Share Split,
Heat Exchange, On-Site Use and On-Site Fuel Use, Net Exports, Direct
Equivalent), never how it classifies: a fuel in the wrong Fuel Category, or
an area of the wrong kind, is equally wrong on both sides and the two
Sankeys agree.

## Considered options

- **A mapping table of the Sankey's own**, from Balmorel names to node
  names. It would also catch classification errors, but it would be a
  second copy of the same classification that drifts from the rule tables,
  and every study's overrides would have to be made twice.

## Consequences

- To check classification, read the rule tables and the warnings about
  what went to Other; the Sankey comparison won't show it.
- The Reader gains a Balmorel region column, so that a Sankey can cover
  chosen regions or areas; `to_iamc` still sums per country.

# IAMC currency: deflate in euros, then exchange at the target year's rate

Balmorel's money is EUR_2016. The common definitions report prices in USD_2010. When `to_iamc` gets no `currency` worth, it converts with pybalmorel's own price-level tables (`backcasting/pricelevel.py`, ADR 0009):

1. Bring EUR_2016 to the target year with the euro-area HICP.
2. For USD, exchange at that year's mean EUR/USD rate.

One EUR_2016 is then worth 93.14 / 100.23 × 1.3257 = **1.2319 USD_2010**. We extended the tables back to 2010 for this.

We chose this method for three reasons:

- **Euro inflation for euro costs.** Balmorel's costs are European, so euro inflation is what changed them. Exchanging once, in the year the IAMC unit names, keeps US inflation out of them.
- **The usual convention.** It is how the World Bank builds its constant-USD series: the constant local-currency series is converted at the base year's market rate. AMPERE, an earlier IAMC model-comparison project, also asked for base-year market rates.
- **One source.** It uses the same method and tables as the backcast prices. Every year has one source, bundled and traceable.

## Considered options

- **The IAMC's `iam_units` package** (pyam's `convert_unit`) has no EUR_2016. It has EUR only for 2000, 2005, 2010, 2020 and 2024, using the World Bank euro-area deflator. It links EUR and USD only after `configure_currency("EXC", <year>)`, with one exchange-rate year of 2005, 2010, 2015, 2020 or 2024.
  - With the 2010 rate and EUR_2016 interpolated in its deflator, it gives 1.2205. That is the same method, with the GDP deflator in place of the HICP.
  - We would have had to define EUR_2016 by hand and add a dependency, for a result within 1% of ours.
- **Exchange at the 2016 rate, then deflate with US inflation to 2010** gives 1.0067, 18% less. The gap is the real change in EUR/USD from 2010 to 2016 (1.3257 → 1.1069). This route applies US inflation to European costs. Using `iam_units` with the 2020 rate gives almost the same, 1.0119.
- **Purchasing power parity** was rejected: prices of traded energy are compared at market rates.

## Consequences

The choice of exchange-rate year moves every reported price and cost by up to about 20%, so other teams' numbers may differ for this reason alone.

A Conversion Note in each scenario gives the worth used and how it was found. A study that must match another convention passes `currency={"USD_2010": <worth>}`, which beats the tables, with no code change.

Eurostat's own site no longer gives HICP years before 2016. The 2010 and 2011 values come from the DBnomics mirror of the same Eurostat series; its 2015 and 2016 values equal those already in the tables.

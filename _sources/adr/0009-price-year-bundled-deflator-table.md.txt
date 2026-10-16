# Bundle the Price Year deflator and exchange-rate tables instead of fetching or passing them

Backcast prices (gas, coal, CO2) are observed in nominal currency of the Backcast Year, and coal is quoted in USD. Balmorel's inputs are in €2016 (the **Price Year**, see `CONTEXT.md`). Every series is converted in one place, `pybalmorel.backcasting.pricelevel`: USD to EUR at the Eurostat annual-average rate for the Backcast Year (`ert_bil_eur_a`), then deflated with the annual-average euro-area HICP (`prc_hicp_aind`, geo `EA`, `CP00`).

We bundle both annual tables as plain dicts in that module, with the source dataset codes and retrieval date next to them. We rejected fetching from the Eurostat API at runtime, because a backcast input would then depend on the network and on Eurostat revisions made after the run, and GAMS-free CI tests would need network access. We rejected letting the user supply the rate (the earlier `--eur-per-usd` flag, now removed) or a CSV, because two runs could then silently use different conversions for the same year, and a run's prices could no longer be traced to a source.

The base year is a module constant (`PRICE_YEAR = 2016`) that each function accepts as an override, so a model rebased to another currency year doesn't need a code change. Annual rather than daily rates are used: the daily variation of EUR/USD within a year is small next to the variation of the fuel prices themselves, and annual figures match how the rest of Balmorel's data is deflated.

The tables need extending once a year. A Backcast Year missing from them raises an error rather than falling back to the nearest year.

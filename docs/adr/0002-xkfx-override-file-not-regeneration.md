# Generate XKFX overrides as a separate, non-destructive include file rather than regenerating XKFX.inc

The backcast pipeline only computes Observed Max Flow ([[0001]]) for borders with a clean 1:1 (or aggregatable) mapping between a Balmorel region and an ENTSO-E bidding zone, for a single target year. Every other entry in `XKFX.inc` — inter-`DE4-*` internal links, and any border ENTSO-E has no usable data for — must keep its current value untouched.

Rather than parsing and regenerating the entire `XKFX.inc` (its existing symmetric base `TABLE` plus hand-tuned asymmetric overrides), the pipeline writes a separate `XKFX_ENTSOE.inc` containing only `XKFX('<year>','A','B')=value;` assignment lines for the borders it computed — the same style already used for the hand-written NO1/NO2/NO5 corrections. This file is pulled in via Balmorel's standard scenario-fallback `$INCLUDE` pattern (checking `<scenario>/data/` first, falling back to `base/data/`) appended at the end of the base `XKFX.inc`. Because GAMS assignments execute in file order, anything the override file doesn't mention is left exactly as the base table set it — the script cannot corrupt or silently drop a link it doesn't understand, which a full-file regeneration could.

Two aggregation rules apply when writing the override file, needed because Balmorel and ENTSO-E don't always share the same regional resolution:

- **Many ENTSO-E zones → one Balmorel region** (e.g. Italian sub-zones → `IT`): sum the observed flows.
- **One ENTSO-E zone → many Balmorel regions** (e.g. `DE_LU` → `DE4-S`/`DE4-W`): split the observed flow evenly across the matching Balmorel sub-links.

The set of borders to fetch ENTSO-E data for is derived from the non-zero entries already present in the target `XKFX.inc`, translated to ENTSO-E zone codes and de-duplicated, rather than a hand-maintained list — this keeps the fetch scope automatically in sync with whatever interconnections the Balmorel model actually defines, and pairs that translate to the same zone on both sides (the internal `DE4-*` links) are naturally excluded. `fetch_annual_transmission_data` already skips a pair if its CSV was already downloaded. Any pair that still fails to fetch is surfaced as a warning at the end of the run, rather than silently dropped, so the user can decide whether to fix a zone-code mapping or proceed with the borders that were available.

Cleaning up `XKFX.inc`'s ad-hoc hand-formatting is a separate, later concern and out of scope for this pipeline.

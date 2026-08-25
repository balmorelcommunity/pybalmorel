---
status: accepted
---

# Vectorize symbol_to_df via gams.transfer instead of per-record iteration

`symbol_to_df` built DataFrames by iterating GDX records one at a time in pure Python (`for rec in db[symbol]`), which dominates runtime on high-cardinality symbols (e.g. `PRO_YCRAGFST`, millions of records for a full scenario). We replaced the internal extraction with `gams.transfer.Container(system_directory=db.workspace.system_directory).read(db, symbols=[symbol]).records`, which accepts the existing classic `gams.GamsDatabase` object directly, so the function's signature and output shape are unchanged. `gamsapi[transfer]` was already a pinned dependency, so this introduced no new dependency. Measured ~62x speedup on an 81K-record symbol with identical row order to the old loop.

## Considered options

- **Hybrid: keep the old loop for small symbols, vectorize only above a record-count threshold.** Rejected — the vectorized path's fixed per-call overhead (~0.26ms) is noise against real run times even for the smallest symbols in this codebase's actual call patterns (dozens to low hundreds of calls per run), so a second code path would add maintenance cost for no practical benefit.
- **Keep the old loop as a fallback behind a flag.** Rejected — there's no realistic scenario where `gams.transfer` works but the classic API path is needed instead; a flag with no real fallback case is dead weight.
- **Include the `element_text` column that `gams.transfer` returns for Sets.** Rejected for this change — it would widen the output shape for every Set-returning call site (`create_set_columns` does a hard positional column-count overwrite, so this isn't additive-safe without further changes). Left as a separate, deliberately-scoped follow-up feature if wanted later.

## Consequences

- Domain columns come back from `gams.transfer` as `category` dtype; we cast them to `object` to preserve the exact dtype contract of the old implementation, since downstream code merges/concatenates `symbol_to_df` output across scenarios.
- The classic API is still used for the pre-existing zero-records short-circuit and the `type(db[symbol])`-based dispatch; only record extraction moved to `gams.transfer`.

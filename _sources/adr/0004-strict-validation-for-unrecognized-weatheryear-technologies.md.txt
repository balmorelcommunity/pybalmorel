# Fail loudly on unrecognized technologies; keep silently dropping known-excluded ones

`tech_to_keep`/`turbine_to_keep` are meant to silently exclude known-but-unwanted technologies from Balmorel's inputs. But `to_balmorel.py`'s two `os.listdir()`-based scans in `export_timeseries_to_balmorel_format` never checked either list — any technology folder or file present on disk, including stale output left over from a prior run under a different `config/weatheryear.yml`, silently became part of the model's Balmorel inputs regardless of the current config.

We decided the fix distinguishes two failure categories: a technology present but excluded by config keeps being silently dropped — that's the whole point of `tech_to_keep`/`turbine_to_keep` — but a technology that doesn't match *any* recognized category at all now raises immediately instead of passing through unfiltered, since that indicates either a real upstream data change (e.g. CorRES shipping a new turbine class) or leftover cruft the keep-lists were never told to consider.

## Considered options

- **Log a warning instead of raising.** Rejected — a warning is exactly the kind of signal that already failed to prevent this bug from going unnoticed in a Snakemake-driven pipeline nobody watches interactively.

## Consequences

- `data/weatheryear_raw/<year>/` in the consuming GREAT repo is still deliberately never auto-cleaned between runs (see that repo's ADR 0014) — this fix doesn't change that retention policy, it only ensures stale or unexpected folders are correctly excluded (or flagged) rather than silently reprocessed regardless of the current config.

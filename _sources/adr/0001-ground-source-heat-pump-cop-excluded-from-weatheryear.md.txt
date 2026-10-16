# Ground-source heat pump COP is excluded from the weatheryear pipeline

`create_cop_inc()` in `weatheryear/cop_to_btc.py` iterates `_COP_TYPES` (`air_air`, `air_water`, `ground_water`), but no COP model ever produces `cop_ground_water_profile.csv`, and the code has no config-driven opt-out for it (unlike `tech_to_keep`/`PV_to_keep` for VRE). We decided to skip `ground_water` unconditionally in this loop rather than synthesize a per-weather-year `.inc` file for it.

Ground-source COP doesn't vary meaningfully by weather year the way air-source COP does — ground temperature is stable year-round, unlike ambient air. `Balmorel/base/data/SEASONALCOP_COP.inc` already carries a fixed, per-area annual-average COP for `GNR_HP_ELEC_GROUND-WTR_...` (and propagates it to future technology vintages via a `GDATA(...,'GDFE')` ratio), so the model already has a working default independent of this pipeline.

**Considered but rejected**: synthesizing a constant-value `.inc` file per weather year from `SEASONALCOP_COP.inc`, to keep output shape consistent with `air_air`/`air_water`. Rejected because it would require mapping GAMS `AAA` area codes to this pipeline's region columns, and duplicates a value Balmorel already applies by default — added complexity for no modeling benefit.

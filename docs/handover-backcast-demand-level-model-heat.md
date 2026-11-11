# Handover: demand level net of the model's own electric heating

From the Balmorel `backcast` branch (2023 backcast, 2026-11-03). This
follows `handover-backcast-demand-level.md` (variant (a′), implemented as
`demand-level`). It changes which heating the level leaves out: the
electricity the previous backcast run used for heat, instead of Eurostat's
figure. It also fixes an 8760/8736-hour mismatch, and adds an optional
hourly refinement to `demand-profile`.

> **Status (2026-11-10): implemented** as `demand-level --heat model`
> (the default), with `--heat eurostat` for the first run of a new year.
> See ADR 0015 and `docs/preprocessing/preparing_backcast.md`. Differences
> from this spec: CH is written (coverage unchecked), the residual is
> reported but no stop rule is enforced, the summary's `BaseTWh` is
> `InputTWh`, and step 2 (the hourly refinement) is deferred. On
> 2026-11-11 the formula below was corrected to
> `X_k = (L_k − T_k − E_k − O_k)(1 − d_k)`: Balmorel's `DIST_LOSSES` also
> holds losses on its electric heating and on wind and solar output
> (`DISLOSS_E_AG`, 6.7 TWh in the compared countries), which this spec
> missed, so the residual disagreed with the load comparison by 7.3 TWh.
>
> **Earlier status: not built.** This file was never committed, and
> it was restored from the 2026-11-03 session. The tables below come
> from `backcast_R2023` of 2026-10-29, which was solved before the
> wrappers. `backcast_R2023` of 2026-11-04 was solved with the wrappers
> and the current (a′) `DE_ENTSOE.inc`, so it can serve as iteration 0.
> In it, Balmorel's load is 2,694.7 TWh against ENTSO-E's 2,699.6. The
> per-country gaps add up to 175 TWh in absolute terms, nearly all of it
> E2H − H: IT +50.6 (E2H − H +45.5), FR −25.5 (−24.7), NO −13.5 (−13.6),
> and CH −11.6, which is on its base level. All runs before the
> thermal-outage fix of 2026-11-09 must be rerun anyway; that rerun can
> be iteration 0.

## What happened

`backcast_R2023` (solved 2026-10-29) was the first run with `DE_ENTSOE.inc`.
Balmorel's load came out 369 TWh below ENTSO-E's (2,276 against 2,645 TWh).
The worst countries were FR −77, DE −49, IT −43 and ES −39. Generation was
correspondingly low.

**Cause: the heating was subtracted twice.** `backcast/data/DE.inc` applies
`DE_ENTSOE.inc` while `DE` is read. `bb4datainc.inc` then runs the
`deadditions` hook:

- `INDUSTRY_DE.inc` subtracts `DE1_IND` from `PII`.
- `INDIVUSERS_DE.inc` subtracts `DE1_INDIVHEATING` from `RESE` and `OTHER`.

Each clamps at 0. In the `DE_ENTSOE` regions that removed another 509 TWh
(175 + 334) from a level that was already net of Eurostat heating (238
TWh). A minimal GAMS script (`DE.inc` plus the two hooks) reproduces the
solved `EXOGENOUS` × 8760/8736 to 0.0 TWh in all 47 regions. So
`DE_ENTSOE.inc` and `DE_VAR_T_ENTSOE.inc` themselves load correctly. The
clamps had also zeroed `RESE` in IT, ES, PT, FIN and EE, and `PII` in DK1,
DK2, LV and LT. Those zeros were carried into `DE_ENTSOE.inc`, because
`demand-level` splits users by the post-addon `DE` shares in the input GDX.

**Balmorel side (done).** `backcast/data/INDUSTRY_DE.inc` and
`backcast/data/INDIVUSERS_DE.inc` are new wrappers. Each includes base's
file of the same name, then `DE_ENTSOE.inc` again. The addons resolve
`../data/<X>_DE.inc` before base's, so `DE_ENTSOE.inc` is now final
whichever addon is on. Verified with the minimal script:

- All 121 `DE_ENTSOE` cells are final.
- The 18 other (region, user) cells are unchanged.
- The `DE_ENTSOE` regions sum to 2,279.4 TWh after the hooks, against
  1,771.9 before. IE was 36.2 then, from the all-island `IE_SEM`. With
  Ireland's control area it is 29.1, and the total is 2,272.4.

## Why (a′) is not enough

(a′) leaves out Eurostat's electricity for heating, `H`: household space
and water heating, plus electric boilers and heat pumps in district
heating. Balmorel's `ENDOGENOUS_ELECT2HEAT` (E2H) covers more than that:
industrial process heat, services heating, and individual users in
`INDIVUSERS_DH` / `DH_TERTIARY`. Under (a′) each country's load gap is
therefore `(E2H − H) / (1 − d)` plus transmission losses. That mixes a
heating scope difference into every country's load, and from there into
generation, prices and flows. In `backcast_R2023`, E2H − H is IT +49.5,
DE +32.3, ES +31.0 and FR +17.9 TWh (Europe +131). In the 2026-10-28 run
IT was already +45.

Option C takes the heating out with the same scope Balmorel adds it back:

```
X_k = (L_k − T_k) × (1 − d_k) − E_k
```

- `L_k` is ENTSO-E's load of canonical region `k` over the Backcast
  Calendar, as now.
- `T_k` and `E_k` are the previous run's `TRANS_LOSSES` and
  `ENDOGENOUS_ELECT2HEAT`, summed over the 8736 hours and over `k`'s
  Balmorel regions.
- `d_k` is `DISLOSS_E`, as now.

Balmorel's compared load is `(EXO + E2H) / (1 − d) + T`. With `EXO = X` and
unchanged E2H and T, it equals `L` exactly. E2H against `H` stays a
Validation Metric, now outside the load.

### E2H moves with the price, so this iterates

E2H is endogenous. Lower exogenous demand means lower prices, and so more
electric heating. From the 2026-10-28 run to `backcast_R2023`:

- EXO fell 476 TWh (2,243 → 1,767).
- E2H rose 140 TWh (229 → 369).
- That is about −0.3 TWh of E2H per TWh of EXO.

This is only a rough figure. The same commit also changed thermal
availability, VRE levels and the must-run floor. Per country it varies a
lot: FR −0.37, DE −0.19, IT −0.06, ES −0.59, SE −0.46, NO −0.34. IT's E2H
barely moves, so its excess is structural (capacity or heat-demand
allocation) rather than a price effect.

**Projections that hold E2H fixed are therefore misleading.** Honouring
(a′) with E2H fixed at 369 would overshoot by +167 TWh. Once E2H falls
back towards its 2026-10-28 level (about 229 at an EXO of about 2,243),
that overshoot mostly disappears. The plain fixed-point iteration
`X_{n+1} = (L − T)(1 − d) − E_n` converges whenever −1 < slope ≤ 0. The
error shrinks by |slope| each run. Assuming the aggregate slope of −0.3 and
starting from `backcast_R2023`:

| Run | X (TWh) | E2H | Load gap at final-consumption level |
|---|---|---|---|
| 1 | 2,122 | 263 | −106 |
| 2 | 2,229 | 231 | −32 |
| 3 | 2,260 | 221 | −10 |
| 4 | 2,270 | 218 | −3 |

**Starting point:** the fixed point lies close to (a′), because E2H there
(~218) is close to `H` (238). The first `--heat model` iteration should
therefore take E2H from a run solved with the wrappers and the current
(a′) `DE_ENTSOE.inc`, not from `backcast_R2023`. `backcast_R2023`'s E2H is
inflated by its double-subtracted EXO. From a wrapper run, one or two `C`
iterations should be enough. Mostly they move demand between countries:
IT down by about 45, FR up by about 25.

## Change

1. **Option `--heat eurostat|model`** on `demand-level`, default `model`.
   - `eurostat` is today's (a′): `X_c = L_c(1 − d_c) − H_c`.
   - `model` is option C.
   - Add `--load-results <path>` (default
     `<scenario>/backcastoutput/balmorel_load.csv`, which `format` writes).
     It is required for `model`. If the file is missing, the error should
     say: "run `format` on a solved backcast first, or use `--heat
     eurostat` for the first run of a new backcast year".

2. **Read the previous run** with a new function in `demand.py`,
   `previous_run_heat(load_results, year) -> pd.DataFrame`, indexed by
   Balmorel region with columns `EXO`, `E2H` and `TLoss`, all in MWh over
   the 8736 hours.
   - The file has one row per (Region, Season, Time, Category) with
     non-zero `Value`. Zero hours are dropped, so a region can have fewer
     than 8736 rows (108 in R2023).
   - Require exactly one `Scenario` and `Year == year`. Require 52 × 168
     distinct (Season, Time) pairs across the whole file, which means an
     hourly full-year run. A full-year run with `T_full` has a seventh of
     that.
   - Categories: `EXOGENOUS`, `ENDOGENOUS_ELECT2HEAT`, `TRANS_LOSSES`. A
     missing category counts as 0. Ignore `ENDO_INTRASTO` and
     `DIST_LOSSES`.

3. **Consistency check, before `DE_ENTSOE.inc` is overwritten.** Per
   region in the current `DE_ENTSOE.inc`, compare `EXO` with its `DE` ×
   8736/8760.
   - Where they differ by more than 1%, warn: "the previous run did not
     solve with this DE_ENTSOE.inc. The INDUSTRY_DE/INDIVUSERS_DE wrappers
     may be missing, or the file was regenerated since. Its E2H may be far
     from this level's."
   - Against `backcast_R2023` this fires for every region (1,767 against
     2,266 TWh). That is intended: R2023 is not a valid starting point.
   - Also warn if the scenario has no `data/INDUSTRY_DE.inc` or
     `data/INDIVUSERS_DE.inc` that includes `DE_ENTSOE.inc`, as is already
     done for `DE.inc`. Check only addons whose base file exists in
     `base/data`.

4. **Level per canonical region** (`model`):
   `X_k = NetLoad_k − TLoss_k × (1 − d_k) − E2H_k`, where `NetLoad_k =
   L_k(1 − d_k)` as today.
   - E2H and T are per Balmorel region, so sum them over `k`'s regions
     (DE4-*), and use them directly for NO1-5, SE1-4 and DK1-2. No load
     share split of heat is needed, unlike `H`.
   - DE_LU: LU is its own Balmorel region with its own E2H. The LU share
     of the DE_LU load is split by `FC_E` as now. Then subtract each
     region's own E2H and T.
   - Keep the coverage check, and the fallback to base for countries
     without ENTSO-E load or with coverage outside the bounds (AL, and UK
     and CH, which have no Eurostat data). Under `model`, `H` is no longer
     needed, so only the coverage check needs Eurostat. Skip that check
     where `FC_E` is missing, and say so in `Note`. CH, which has ENTSO-E
     load, is then written too.
   - Then split within `k` and over `DEUSER` as now.

5. **Hours: write `DE = X × 8760 / 8736`**, for both `--heat` values.
   Balmorel's `EXOGENOUS` summed over the 8736 modelled hours equals
   `DE × 8736/8760` (verified to 0.0 TWh). `L` is summed over the same
   8736 hours. Today's `DE_ENTSOE.inc` is therefore 0.27% too low,
   6.2 TWh for Europe.

6. **User shares.** Once the input GDX is rebuilt with the wrappers in
   place (`--reload-input`), its `DE` for the `DE_ENTSOE` regions *is* the
   previous `DE_ENTSOE.inc`. The user split then stays at its fixed point,
   which is harmless. `BaseTWh` then means "previous level", not base,
   though. Label the column `InputTWh`, or document this. The `RESE`/`PII`
   zeros inherited from the clamps are also harmless: `OTHER` and `RESE`
   get the same profile, and step 2 below makes the hourly sum right
   regardless of the split. Don't fix them unless step 2 is skipped.

7. **Summary (`backcastoutput/demand_level.csv`).**
   - Keep every current column, including the Eurostat `H` parts.
   - Add `HeatSource` (`eurostat` or `model`), `PrevExoTWh`, `E2H_TWh`,
     `TransLossTWh`, `E2H_minus_H_TWh`, and `ResidualTWh` =
     `(L − T)(1 − d) − EXO − E2H` (what the previous run missed, at
     final-consumption level).
   - Print the Europe total of `ResidualTWh` and the sum of its absolute
     values. These are the convergence measure: iterate until they are
     below about 10 TWh.

8. **Header of `DE_ENTSOE.inc`** under `model`:

   ```gams
   * Electricity demand level for 2023: ENTSO-E load less transmission losses, net of
   * distribution losses, less the electricity <run> used for heat
   * (ENDOGENOUS_ELECT2HEAT, see CONTEXT.md) - generated, do not hand-edit
   ```

   `<run>` is the `Scenario` column of `balmorel_load.csv`.

Option, only if convergence is slow: `--relaxation ω`, with `X_new =
EXO_prev + ω(X_C − EXO_prev)`. A value of `ω = 1` gives the plain update.
Newton would be `ω = 1/(1 + slope)` ≈ 1.4. But IT's slope is about 0, so
ω > 1 overshoots there. Don't add it unless needed.

## Step 2: residual demand profile (`demand-profile --heat model`)

Today the Observed Demand Profile is ENTSO-E's total load, including
heating. Balmorel puts E2H's own heating shape on top of it. In
`backcast_R2023` the monthly Balmorel/ENTSO-E ratio was 0.93 in January
and 0.80 in summer. Part of that is the double-subtraction level error,
but a winter-heavy E2H on a winter-heavy profile also bends the shape.
Option: `--heat none|model` (default `none`, today's behaviour), with the
same `--load-results`.

For a canonical region `k` that has an ENTSO-E profile, at hour `h`:

```
R_k,h = L_k,h × (1 − T_k / L_k) × (1 − d_k) − Ē_k,h − P_k,h
```

- `Ē_k,h`: the previous run's E2H over `k`'s regions, averaged over hour
  `h`'s day. A day is the 24-term block T001–T024, T025–T048, … within each
  season; S01 T001 is 00:00 UTC on a Monday (`calendar.py`). The daily
  mean keeps the seasonal and weekly heating pattern but drops E2H's
  intraday dispatch. That dispatch is a price response, and feeding it
  back would make the profile oscillate between runs.
- `P_k,h`: `PII`'s exogenous hours from the input data: `DE(PII)` ×
  `DE_VAR_T(PII,h)` / Σ_h `DE_VAR_T(PII,h)`, summed over `k`'s regions,
  over the 8736 hours. `demand-profile` writes only `OTHER`/`RESE`, so this
  shape must be what `OTHER + RESE` add to `PII`.
- Then `Σ_h R_k,h = X_k − X_PII,k`, consistent with step 1.
- Clean as now: hours below `PLAUSIBLE_LOW` × median are interpolated.
  More than `MAX_IMPLAUSIBLE_SHARE` such hours means the residual is
  unreliable. Warn, and keep the total-load profile for that region.
- All of `k`'s regions get `R_k` (DE4-* as now). Regions on the input-data
  fallback (UK, CY, LU, MT and TR; AL and BA when their ENTSO-E data fail) get no residual
  treatment.
- Add to the report line: the source, the hours interpolated, and
  `winter/summer ratio before → after`.

Run it with the same `balmorel_load.csv` as `demand-level`. The level and
shape then come from one run.

## Tests

- `previous_run_heat`: sparse rows sum per region; a missing category is
  0; it rejects two scenarios, a wrong year, and a file with fewer than
  8736 (S,T).
- `model`, one region: `X = (L − T)(1 − d) − E`. With E2H and T unchanged,
  `X/(1 − d) + E/(1 − d) + T = L`.
- DE4-*: E2H and T are summed over the four, and base's ratios between
  them are kept.
- NO1-5: each region uses its own E2H and T, and there is no load share
  split.
- `DE` written = `X × 8760/8736` under both `--heat` values.
- The consistency warning fires when `EXO` differs from `DE_ENTSOE` ×
  8736/8760 by more than 1%, and stays silent within it.
- The wrapper warning fires when `data/INDIVUSERS_DE.inc` is missing, and
  when it doesn't include `DE_ENTSOE.inc`.
- `--heat eurostat` is unchanged apart from the hours factor.
- Residual profile: the daily mean of a toy E2H; `PII` subtracted;
  `Σ R = X − X_PII`; more than 2% non-positive hours falls back to total
  load.

## Verification

From the Balmorel root:

```
python -m pybalmorel.backcasting demand-level backcast backcast/entsoedata 2023 --heat model
```

Against `backcast_R2023`'s `balmorel_load.csv`, this should warn (step 3)
and give the values below. They are in TWh over 8736 hours; `DE` is ×
8760/8736.

| Country | L | T | E2H | H | `DE` (a′) now | X (C) | `DE` (C) | C − (a′) | E2H − H |
|---|---|---|---|---|---|---|---|---|---|
| IT | 275.6 | 4.2 | 59.6 | 10.1 | 251.7 | 198.3 | 198.8 | −52.9 | +49.5 |
| DE | 456.1 | 3.6 | 55.0 | 22.8 | 411.4 | 375.7 | 376.7 | −34.6 | +32.3 |
| ES | 228.9 | 0.7 | 41.2 | 10.2 | 207.2 | 175.6 | 176.0 | −31.2 | +31.0 |
| FR | 424.7 | 0.8 | 88.5 | 70.6 | 332.8 | 314.2 | 315.1 | −17.7 | +17.9 |
| SE | 130.3 | 2.6 | 26.2 | 20.3 | 102.6 | 94.2 | 94.5 | −8.1 | +5.9 |
| BE | 78.7 | 0.7 | 11.7 | 5.3 | 69.5 | 62.4 | 62.6 | −6.9 | +6.4 |
| NO | 134.1 | 0.8 | 24.0 | 29.3 | 98.1 | 102.6 | 102.9 | +4.7 | −5.3 |
| RS | 33.6 | 0.0 | 0.4 | 5.9 | 26.1 | 31.5 | 31.6 | +5.5 | −5.4 |
| AT | 58.1 | 0.2 | 3.4 | 8.1 | 47.1 | 51.6 | 51.7 | +4.6 | −4.7 |
| 30 countries | 2,637.4 | 20.0 | 369.2 | 237.9 | 2,272.4 | 2,122.0 | 2,127.8 | −144.6 | +131.3 |

IE (not shown) is L 32.4 and `DE` (a′) 29.1, from Ireland's control area
rather than the all-island `IE_SEM`. These numbers check the arithmetic only. Don't solve the backcast with
them, for the reason given under "Starting point".

## Notes for the user

- **Run order:**
  1. Solve the backcast with the wrappers and the current (a′)
     `DE_ENTSOE.inc`. This is iteration 0. It also confirms the wrapper fix
     in a solve.
  2. `format`.
  3. `demand-level --heat model` (and optionally `demand-profile --heat
     model`).
  4. Solve, and repeat steps 2-4 until the residual is below about 10 TWh.
- **What stays evidence:** after convergence, a country's total load (and,
  with step 2, its shape) matches ENTSO-E by construction. The evidence on
  demand is then E2H against Eurostat `H` per country. Read it knowing the
  scopes differ: E2H also covers industry and services. `E2H_minus_H_TWh`
  in the summary is that metric. The supply side (generation mix, prices,
  flows) no longer carries demand errors.
- **Transmission losses** move with flows too. They are small (20 TWh for
  Europe) and converge with E2H.

## Glossary (`CONTEXT.md`, Backcasting section)

Replace the **Demand level** entry once `--heat model` is the default:

```markdown
**Demand level**:
The annual exogenous electricity demand (`DE`) of a region in the backcast year: its ENTSO-E load over the Backcast Calendar less the previous backcast run's transmission losses, net of Balmorel's distribution losses, less the electricity the previous run used for heat (`ENDOGENOUS_ELECT2HEAT`), which Balmorel adds back endogenously. Because that heating responds to prices, the level is iterated over runs until Balmorel's load matches ENTSO-E's. Taken from ENTSO-E's load rather than Eurostat's final consumption because the two differ in coverage (DE: ENTSO-E sees 7% less). Written as `DE` overrides to `DE_ENTSOE.inc`, which the backcast applies after the INDUSTRY and INDIVUSERS addons have adjusted `DE`. A calibration input: a country's total load is not evidence, its electric heating is (against Eurostat's electricity for heating).
_Avoid_: Final consumption (Eurostat's figure, with different coverage); Demand (ambiguous)
```

The Balmorel `CONTEXT.md` gets the same entry; keep the two in step.

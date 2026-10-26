# pybalmorel

Python tooling for pre- and post-processing around the Balmorel energy system model, including the `weatheryear` module that converts external model outputs (CorRES, demand, hydro, COP) into Balmorel-ready `.inc` files for a chosen historical weather year. Also includes a backcasting toolbox that validates simulated Balmorel behaviour against historical ENTSO-E data.

## Language

### Weather-year preprocessing

**CapDev timestep**:
A representative `Season.Hour` pair (e.g. `S02.T073`) used for the reduced capacity-development (investment) time resolution. Built as the cross product of `CapDev_timesteps_to_keep.S` (representative seasons) and `.T` (representative hours) — both are lists of equal standing, not a season-plus-hours pair.
_Avoid_: CapDev season (a single `S` value is not itself a timestep)

**Day-Ahead (DA) resolution**:
The full hourly time series for a weather year, before it is reduced to CapDev timesteps.
_Avoid_: full resolution, raw resolution

**tech_to_keep**:
The required list of technology-run folder names (e.g. `Future_Onshore`, `PV_Rooftop`) that `WEATHERYEAR.get_vre_data()` actually processes when exporting VRE time series from CorRES. It is the only switch for including or excluding a technology; `RGs_to_keep` only chooses resource grades within it. Folders present under `weatheryear_inputs_folder` but not listed here are silently skipped; a folder that matches no recognized technology category at all raises instead of being skipped.

**turbine_to_keep**:
A finer filter within the `Future_Onshore`/`Future_Offshore_*` `tech_to_keep` categories, naming which specific turbine models (e.g. `SP277-HH100`) are processed. PV categories have no equivalent finer level — each PV `tech_to_keep` category is already a single model, varying only by resource grade.
_Avoid_: PV_to_keep (removed — PV data has no per-model dimension to filter)

**Technology identity**:
The `(turbine/PV model, resource grade, onshore/offshore, region)` tuple that uniquely identifies one renewable generation technology instance. `GGG_renewable`, `INVDATASET_renewable`, and `AAA_renewable` each spell this differently for their own set domain, but all derive from this one shared identity so their spellings can't independently drift.

**GGG_renewable**:
Balmorel generator (`GGG`) identifiers for renewable technologies, one per technology identity per investment vintage year (e.g. `GNR_WT-SP335-HH100_ONS_RG1_Y-2020`).

**INVDATASET_renewable**:
Renewable investment-option identifiers Balmorel's investment mode chooses among, one per technology identity, independent of region or vintage year (e.g. `VRE-ONS_SP335-HH100_RG1`).

**AAA_renewable**:
Region-qualified technology identifiers, one per technology identity per region, used to say where that technology is available (e.g. `IE_VRE-ONS_SP335-HH100_RG1`).

**INVDATA**:
The GAMS parameter linking an `AAA_renewable` member to the `INVDATASET_renewable` member it can invest in.

**Absolute Hydro FLH**:
Hydro full-load hours computed as CorRES inflow energy divided by the Balmorel capacity that receives it (`hydro_flh: mode: absolute`), instead of a factor on Balmorel's base FLH (the default, relative mode).
_Avoid_: Hydro factor (that is the relative mode)

**Demand Profile Fallback**:
For a region whose weather-year electricity demand profile fails the plausibility check (an hour at or below 0 or missing, a peak above 3 times the median, or the same values as another region's profile), the weather year writes no profile, so the region keeps base's `DE_VAR_T`. A stopgap for corrupt demand model data; a Backcast uses its Observed Demand Profile instead.

### Backcasting

**Observed Flow Limit**:
The 99th percentile of the hourly cross-border flow recorded by ENTSO-E in one direction of a canonical border within the Backcast Year, taken over the hours with flow in that direction, after summing every ENTSO-E zone pair of the border hour by hour. A direction without flow gets 0. Used as the exogenous transmission limit (`XKFX`) in a Backcast and as the `Limit` in Flow Validation. The percentile can be set; 100 gives the maximum (see ADR 0010).
_Avoid_: Observed Max Flow (the earlier yearly maximum), Capacity, Transmission Capacity, NTC

**Transmission Capacity (NTC)**:
The grid operator's rated/commercial cross-border transfer capability, independent of whether it was ever fully utilised. Deliberately _not_ used for backcasting — Observed Flow Limit is used instead, since backcasting aims to reproduce what actually happened in a given historical year, not what was technically possible.
_Avoid_: Capacity (when ambiguous with Observed Flow Limit)

**Canonical Region Name**:
A shared identifier used to bridge a Balmorel region and an ENTSO-E bidding zone when the two disagree on spelling or resolution (e.g. Balmorel's `DE4-E`/`DE4-N`/`DE4-S`/`DE4-W` and ENTSO-E's `IT-NORD`, `IT-CNOR`, etc. all canonicalize to `DE`/`IT`). Defined by `bidding_zone_translation`; a name absent from it is already canonical.

**ENTSO-E Zone Code**:
The raw identifier the ENTSO-E transparency platform API expects for a query (e.g. `10YNO-1--------2`, `DE_LU`) — one layer downstream of a Canonical Region Name, which a code can share (`FR`) or differ from entirely.
_Avoid_: Region, Zone (when ambiguous with Canonical Region Name)

**Backcast**:
A Balmorel scenario run for one Backcast Year from backcast inputs (Observed Flow Limit, historical fuel prices, CO2 tax), so its results can be compared with what actually happened. Preparing a Backcast means generating those inputs; validating a Backcast means comparing its results with ENTSO-E observations.
_Avoid_: Backcasting run, backcast scenario (when the run's results are meant)

**Backcast Year**:
The single historical year a backcast reproduces: its fuel and CO2 prices, its transmission limits, and its weather. In a backcast it is always the same year as the weather year. Chosen only when generating inputs; Balmorel just reads whatever has been generated.
_Avoid_: Weather year (keep that term for the weatheryear module, which is also used outside backcasting)

**Backcast Calendar**:
The mapping from a Backcast Year's clock time to Balmorel's 52 seasons (S01–S52) × 168 terms (T001–T168). S01 T001 is 00:00 UTC on the first Monday of the year, so every day has exactly 24 terms. Days outside the 52 full weeks are dropped. Daily prices apply to the UTC calendar day.
_Avoid_: Local time, Copenhagen time, CET

**Price Year**:
The currency year all backcast prices are expressed in: €2016. Every series is deflated with the euro-area HICP and converted from USD using the Eurostat annual-average exchange rate, both from tables bundled in `pybalmorel.backcasting.pricelevel` (see ADR 0009).

**CO2 Override**:
A flat, nominal €/tCO2 price for one Balmorel country (`CCC`) that replaces the EUA price in `TAX_CO2_ST`, e.g. the UK's own carbon price or 0 for a country without one. Every country without an override gets the EUA primary-auction price, so no list of ETS members is kept.
_Avoid_: ETS country list

**Nuclear Availability**:
The share of a country's nuclear `GKFX` that could run in one week of the Backcast Year: the highest hourly nuclear output ENTSO-E reports for that week, divided by the country's nuclear `GKFX`, clipped at 1. It includes outages, maintenance and closures: weeks after the country's observed series ends are rated zero. Written as weekly `GKRATE` overrides to `GKRATE_ENTSOE.inc`; a zero is written as `eps`, since Balmorel reads 0 as full capacity. A calibration input, not a validation result.
_Avoid_: Capacity factor, load factor (those describe output, not availability)

**Observed Demand Profile**:
The hourly ENTSO-E actual load of a region's Canonical Region Name in the Backcast Year, on the Backcast Calendar, used as the `DE_VAR_T` of the exogenous electricity users (`OTHER`, `RESE`). Implausible or missing hours are interpolated; a region with more than 2% of them takes its profile from the scenario's input data instead. Written to `DE_VAR_T_ENTSOE.inc`. Balmorel scales it to the annual `DE`, so only the shape is observed. ENTSO-E load is total load, so it also carries part of the endogenous demand's variation. A Calibration Input.
_Avoid_: Demand (the annual level still comes from `DE`)

**Natural-Inflow Hydro**:
Run-of-river and reservoir hydro fed by natural water inflow. It excludes pumped-storage output, which is electricity storage.
_Avoid_: Hydro (ambiguous about pumped storage)

**Hydro Inflow Fallback**:
For a country whose CorRES inflow fails the plausibility check, or that CorRES covers only partly or not at all, the inflow level comes from observed long-term Natural-Inflow Hydro instead; CorRES still provides that year's variation where it has data, and a country without CorRES data gets none. A stopgap until CorRES fixes and completes its inflow series (see ADR 0011).
_Avoid_: Hydro calibration (the Backcast Year's own generation is never the reference)

**Calibration Input**:
A Backcast input derived from observed data for the Backcast Year that says what was available or given that year (nuclear outages, the usable interconnector capacity, the shape of exogenous demand), not what the model should decide. Results that a calibration input fixes by construction are not evidence in Backcast validation.
_Avoid_: Tuning, fitting

**Validation Metric**:
A result the model must reproduce on its own to pass Backcast validation: prices, cross-border flows, the fossil mix, and the timing of nuclear and hydro output within the year. Never derived from the same data as a Calibration Input.
_Avoid_: Target (ambiguous between the two)

**Flow Validation**:
The comparison of Balmorel's hourly cross-border flows (`X_FLOW_YCRST`) with ENTSO-E's physical flows, per directed border between Canonical Region Names. Unlike the XKFX overrides, nothing is split: both sides are summed up to the canonical border and internal links are dropped. Hours Balmorel leaves out of its results count as zero flow. `Limit` is the Observed Flow Limit, which ENTSO-E exceeds in about 1% of its flowing hours by construction. ENTSO-E flows are physical (including loop flows) while Balmorel's are commercial, so some mismatch is expected and not a model error.

**Series Fuel**:
A fuel whose backcast price varies within the year (NATGAS and COAL daily; FUELOIL, HEAVYFUELOIL and LIGHTOIL weekly) rather than taking an annual value from the scenario data. The set of series fuels determines which fuels are dropped from the annual price table and flagged as non-constant.

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

### Backcasting

**Observed Max Flow**:
The maximum hourly cross-border electricity flow recorded by ENTSO-E on a given directed border-pair within a year. Used as an exogenous transmission constraint in backcasting runs, standing in for whatever combination of technical, market, maintenance, and social/political constraints actually limited flow that year.
_Avoid_: Capacity, Transmission Capacity, NTC

**Transmission Capacity (NTC)**:
The grid operator's rated/commercial cross-border transfer capability, independent of whether it was ever fully utilised. Deliberately _not_ used for backcasting — Observed Max Flow is used instead, since backcasting aims to reproduce what actually happened in a given historical year, not what was technically possible.
_Avoid_: Capacity (when ambiguous with Observed Max Flow)

**Canonical Region Name**:
A shared identifier used to bridge a Balmorel region and an ENTSO-E bidding zone when the two disagree on spelling or resolution (e.g. Balmorel's `DE4-E`/`DE4-N`/`DE4-S`/`DE4-W` and ENTSO-E's `IT-NORD`, `IT-CNOR`, etc. all canonicalize to `DE`/`IT`). Defined by `bidding_zone_translation`; a name absent from it is already canonical.

**ENTSO-E Zone Code**:
The raw identifier the ENTSO-E transparency platform API expects for a query (e.g. `10YNO-1--------2`, `DE_LU`) — one layer downstream of a Canonical Region Name, which a code can share (`FR`) or differ from entirely.
_Avoid_: Region, Zone (when ambiguous with Canonical Region Name)

**Backcast Year**:
The single historical year a backcast reproduces: its fuel and CO2 prices, its transmission limits, and its weather. In a backcast it is always the same year as the weather year. Chosen only when generating inputs; Balmorel just reads whatever has been generated.
_Avoid_: Weather year (keep that term for the weatheryear module, which is also used outside backcasting)

**Backcast Calendar**:
The mapping from a Backcast Year's clock time to Balmorel's 52 seasons (S01–S52) × 168 terms (T001–T168). S01 T001 is 00:00 UTC on the first Monday of the year, so every day has exactly 24 terms. Days outside the 52 full weeks are dropped. Daily prices apply to the UTC calendar day.
_Avoid_: Local time, Copenhagen time, CET

**Price Year**:
The currency year all backcast prices are expressed in: €2016. Every series is deflated with the euro-area HICP and converted from USD using the Eurostat annual-average exchange rate.

**Series Fuel**:
A fuel whose backcast price varies within the year (NATGAS and COAL daily; FUELOIL, HEAVYFUELOIL and LIGHTOIL weekly) rather than taking an annual value from the scenario data. The set of series fuels determines which fuels are dropped from the annual price table and flagged as non-constant.

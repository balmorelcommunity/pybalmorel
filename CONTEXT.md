# pybalmorel

Python tooling for pre- and post-processing around the Balmorel energy system model, including the `weatheryear` module that converts external model outputs (CorRES, demand, hydro, COP) into Balmorel-ready `.inc` files for a chosen historical weather year. Also includes a backcasting toolbox that validates simulated Balmorel behaviour against historical ENTSO-E data, and a converter that reports MainResults in the IAMC format used by model intercomparisons.

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
The raw identifier the ENTSO-E transparency platform API expects for a query (e.g. `10YNO-1--------2`, `DE_LU`) — one layer downstream of a Canonical Region Name, which a code can share (`FR`) or differ from entirely. A region's load can use another code than its other queries when the bidding zone is larger than the Balmorel region: IE's load is Ireland's control area (`IE`), since the `IE_SEM` bidding zone also covers Northern Ireland, which Balmorel has in UK (`load_zones`).
_Avoid_: Region, Zone (when ambiguous with Canonical Region Name)

**Backcast**:
A Balmorel scenario run for one Backcast Year from backcast inputs (Observed Flow Limit, historical fuel prices, CO2 tax), so its results can be compared with what actually happened. Preparing a Backcast means generating those inputs; validating a Backcast means comparing its results with ENTSO-E observations, to test Balmorel's supply side: what it dispatches and trades to meet a given load. Electric heating, the one Validation Metric on the demand side, is reported apart, as a finding about the heat sector.
_Avoid_: Backcasting run, backcast scenario (when the run's results are meant)

**Backcast Year**:
The single historical year a backcast reproduces: its fuel and CO2 prices, its transmission limits, and its weather. In a backcast it is always the same year as the weather year. Chosen only when generating inputs; Balmorel just reads whatever has been generated.
_Avoid_: Weather year (keep that term for the weatheryear module, which is also used outside backcasting)

**Backcast Calendar**:
The mapping from a Backcast Year's clock time to Balmorel's 52 seasons (S01–S52) × 168 terms (T001–T168). S01 T001 is 00:00 UTC on the first Monday of the year, so every day has exactly 24 terms. Days outside the 52 full weeks are dropped. Daily prices apply to the UTC calendar day.
_Avoid_: Local time, Copenhagen time, CET

**Price Year**:
The currency year all backcast prices are expressed in: €2016. Every series is deflated with the euro-area HICP and converted from USD using the Eurostat annual-average exchange rate, both from tables bundled in `pybalmorel.backcasting.pricelevel` (see ADR 0009). Backcast validation converts Balmorel's prices the other way, to nominal euros of the Backcast Year, before comparing them with ENTSO-E.
_Avoid_: Base year, EUR2012 (outdated header leftover)

**CO2 Override**:
A flat, nominal €/tCO2 price for one Balmorel country (`CCC`) that replaces the EUA price in `TAX_CO2_ST`, e.g. the UK's own carbon price or 0 for a country without one. Every country without an override gets the EUA primary-auction price, so no list of ETS members is kept.
_Avoid_: ETS country list

**Nuclear Availability**:
The share of a country's nuclear `GKFX` that could run in one week of the Backcast Year: the highest hourly nuclear output ENTSO-E reports for that week, divided by the country's nuclear `GKFX`, clipped at 1. It includes outages, maintenance and closures: weeks after the country's observed series ends are rated zero. Written as weekly `GKRATE` overrides to `GKRATE_ENTSOE.inc`; a zero is written as `eps`, since Balmorel reads 0 as full capacity (see ADR 0013). A calibration input, not a validation result.
_Avoid_: Capacity factor, load factor (those describe output, not availability)

**Thermal Availability**:
The share of a country's fossil, biomass or waste `GKFX` of one fuel group that could run in a given week of the Backcast Year: ENTSO-E's installed capacity as a share of `GKFX` (at most 1), less the capacity ENTSO-E reports as out of service that week. Taken from ENTSO-E's installed capacity and outage reports, never from observed output, because the fossil mix is a Validation Metric. Written as weekly `GKRATE` overrides to `GKRATE_THERMAL_ENTSOE.inc` (see ADR 0014). A Calibration Input.
_Avoid_: Capacity factor (that describes output); Nuclear Availability (that is taken from observed output)

**Must-run Floor**:
The lowest electricity output a zone's fossil, biomass or waste fuel group kept in a week of the Backcast Year when it would have paid to stop: the week's lowest observed hourly output (ENTSO-E), for weeks in which the zone's day-ahead price stayed at or below 40 €/MWh for at least 4 hours, and for biomass and waste in every week. Balmorel must produce at least that much, or pay a penalty per MWh short. It fixes only the bottom of the fossil mix by construction; the fossil mix above the floor stays a Validation Metric. Written to `MUSTRUN_FLOOR.inc`, whose existence switches Balmorel's `MUSTRUN` addon on. A Calibration Input.
_Avoid_: Minimum load (a property of one unit); Must-run (a plant flag, not an observed level)

**VRE Level**:
The annual output a country's wind or solar fleet could deliver in the Backcast Year: the weather year's full-load hours, scaled per country and kind (solar, onshore, offshore) so that it equals ENTSO-E's reported output for that year. Where ENTSO-E reports no offshore output for a country with Balmorel offshore capacity, onshore and offshore share one factor. Factors outside 0.6–1.5 are not written, since such a gap is a capacity or reporting problem. The hourly profile still comes from the weather year. Written as `WNDFLH`/`SOLEFLH` overrides to `WNDFLH_ENTSOE.inc` and `SOLEFLH_ENTSOE.inc` (see ADR 0012). A Calibration Input.
_Avoid_: Capacity factor (that describes output after curtailment)

**Observed Demand Profile**:
The hourly ENTSO-E actual load of a region's Canonical Region Name in the Backcast Year, on the Backcast Calendar, used as the `DE_VAR_T` of the exogenous electricity users (`OTHER`, `RESE`). Implausible or missing hours are interpolated; a region with more than 2% of them takes its profile from the scenario's input data instead. Written to `DE_VAR_T_ENTSOE.inc`. Balmorel scales it to the annual `DE`, so only the shape is observed. ENTSO-E load is total load, so it also carries part of the endogenous demand's variation. A Calibration Input.
_Avoid_: Demand (the annual level still comes from `DE`)

**Demand Level**:
The annual exogenous electricity demand (`DE`) of a region in the Backcast Year: its ENTSO-E load over the Backcast Calendar, extrapolated to the 8760 hours Balmorel spreads `DE` over, less what the previous backcast run added on top of `DE`: its transmission losses, the electricity it used for heat (`ENDOGENOUS_ELECT2HEAT`), and its distribution losses on anything but exogenous demand (on that heating, and on wind and solar output); all net of Balmorel's distribution losses. Its electric heating and losses respond to the level, so the level is iterated over runs for as long as the user finds the previous run's residual (its load's miss, net of distribution losses) worth closing. The first run of a new Backcast Year has no previous run and leaves out the electricity Eurostat reports for heating instead (household space and water heating, electric boilers and heat pumps in district heating). Taken from ENTSO-E's load rather than Eurostat's final consumption because the two differ in coverage (DE: ENTSO-E sees 7% less). Split over regions and users by the input data's `DE`. Written as `DE` overrides to `DE_ENTSOE.inc`, which the Backcast applies again after the INDUSTRY and INDIVUSERS addons have adjusted `DE` (see ADR 0015). ENTSO-E load is thereby a Calibration Input at every level, the system's and each country's, and a country's load gap is not a supply-side error. Electric heating, Balmorel's against Eurostat's, stays a Validation Metric.
_Avoid_: Final consumption (Eurostat's figure, with different coverage); Demand (the level alone, without the Observed Demand Profile)

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
A result the model must reproduce on its own to pass Backcast validation: prices, cross-border flows, the fossil mix, electric heating (reported apart, see Backcast), and the timing of nuclear and hydro output within the year. Never derived from the same data as a Calibration Input.
_Avoid_: Target (ambiguous between the two)

**Flow Validation**:
The comparison of Balmorel's hourly cross-border flows (`X_FLOW_YCRST`) with ENTSO-E's physical flows, per directed border between Canonical Region Names. Unlike the XKFX overrides, nothing is split: both sides are summed up to the canonical border and internal links are dropped. Hours Balmorel leaves out of its results count as zero flow. `Limit` is the Observed Flow Limit, which ENTSO-E exceeds in about 1% of its flowing hours by construction. ENTSO-E flows are physical (including loop flows) while Balmorel's are commercial, so some mismatch is expected and not a model error.

**Series Fuel**:
A fuel whose backcast price varies within the year (NATGAS and COAL daily; FUELOIL, HEAVYFUELOIL and LIGHTOIL weekly) rather than taking an annual value from the scenario data. The set of series fuels determines which fuels are dropped from the annual price table and flagged as non-constant.

### IAMC reporting

**IAMC Variable**:
A pipe-separated name from the IAMC common definitions (e.g. `Secondary Energy|Electricity|Gas|w/ CCS`), always reported in the unit those definitions give it (EJ/yr, GW, Mt CO2/yr). Only names that exist in the common definitions are reported; pybalmorel never makes up its own.
_Avoid_: Symbol, result (those are the Balmorel GDX parameters a variable is computed from)

**Definitions Snapshot**:
The copy of the IAMC common definitions (variable names, units, descriptions, country names) that pybalmorel ships, taken from one commit of the common-definitions repository and updated only on purpose. Every IAMC Variable and IAMC Region is checked against it. Whoever converts can pass a different copy in the same format.
_Avoid_: Variable list, varlist (the Template)

**Template**:
The variable list an intercomparison sends its participants, e.g. NMSF Study 2's `varlist.xlsx`. Its `Extended List` sheet is the part of the common definitions that intercomparison accepts, and its `Data` sheet the part it asks for. pybalmorel ships none; whoever converts passes one in. With a Template, output is limited to what its Extended List accepts; without one, every IAMC Variable Balmorel's results cover is reported. The `Data` sheet never limits what is reported.
_Avoid_: Variable list (ambiguous between the Template and the Definitions Snapshot)

**IAMC Model**:
The model label of a submission, e.g. `Balmorel-DTU`. Given by whoever converts, never derived from the files.

**IAMC Scenario**:
The scenario name of a submission, e.g. `NMSF2-LTS`. One or more Balmorel scenarios map to one IAMC Scenario, as long as their years don't overlap; without a mapping, it is the Balmorel scenario name.
_Avoid_: Scenario (alone, when the Balmorel run name is meant)

**IAMC Region**:
A country, spelled as in the common definitions' region list (e.g. `Czechia` for Balmorel's `CZECH_REPUBLIC`). Always a Balmorel country (`C`), never a Balmorel region (`R`) or area (`A`), and never an aggregate of countries.
_Avoid_: Region (alone, ambiguous with Balmorel's `R`)

**Coverage**:
Whether Balmorel's results account for everything an IAMC Variable's definition includes. A variable is reported only where they do. A parent whose definition reaches beyond the sectors Balmorel models (e.g. `Emissions|CO2`, or a `Primary Energy` total) is never reported, even when some of its children are. Only modelled years are reported, never interpolated ones.

**Other**:
The `…|Other` child of an IAMC Variable, which takes Balmorel output that fits none of its other children, such as a fuel with no known classification. Conversion continues, and a warning names what was put there.
_Avoid_: Unclassified (it is classified, as Other)

**OptiFlow Mapping**:
A table, specific to one study, saying which OptiFlow flows and processes capture, store and use CO2. OptiFlow names and the meaning of OptiFlow rows in Balmorel's emissions differ from study to study, so no mapping holds for all. Without one, an OptiFlow-coupled run still reports every variable those rows don't affect.

**Fuel Category**:
The IAMC fuel segment (`Coal`, `Gas`, `Oil`, `Biomass`, `Hydrogen`, `Nuclear`, `Hydro`, …) that a Balmorel fuel (`FFF`) is reported under. Only segments that occur in IAMC Variable names can be chosen. Defaults ship with pybalmorel, and whoever converts can override them, e.g. to move `MUNIWASTE` from `Biomass` to `Other`. A fuel belongs wholly to one category; it is never split between two.

**Mapping Rule**:
A row in pybalmorel's mapping tables that sends Balmorel output with a given technology type, fuel and commodity (and, optionally, only units whose names match a pattern) to segments of an IAMC Variable name. Defaults ship with pybalmorel; rows passed by whoever converts take precedence. Output no rule covers goes to Other.
_Avoid_: Mapping (alone, ambiguous with the OptiFlow Mapping)

**CCS Unit**:
A Balmorel unit (a `GGG` member) whose name carries the token `CCS`, e.g. `NGASCCS` or `STEAM-REFORMING-CCS`. Reported under `w/ CCS`; every other unit is `w/o CCS`. No fuel or technology type marks CCS, so the unit name is the only evidence.
_Avoid_: CC (Balmorel names use it for combined cycle)

**District-Heating Area / Individual Area / Industry Area**:
The three kinds of Balmorel heat area, told apart by name: individual areas contain `IDVU`, industry areas contain `IND-` (usually after a country or region prefix, e.g. `DE4-W_IND-LT-DH`), and every other heat area is a district-heating area. Centralized heat, which IAMC reports as `Secondary Energy|Heat` and `Final Energy|Heat`, is made and used in district-heating areas, and crosses into other areas only as Heat Exchange. Individual areas heat buildings on site, and industry areas supply process heat on site. Their fuel use, heat and emissions are not reported, because no IAMC Variable matches what they cover; the Conversion Notes give the amounts. Only the electricity they use is reported, as part of `Final Energy|Electricity`.
_Avoid_: Heat area (alone, when the kind matters)

**Heat Exchange**:
Heat that Balmorel's heat transmission moves between a district-heating area and an individual or industry area. It is netted per pair of areas and year, because much of it only makes a round trip, e.g. into an industry area's heat storage and back. A net flow out of district heating is consumption of centralized heat, reported in `Final Energy|Heat`. It is not reported as `Final Energy|Industry|Heat`, because the district-heating areas' own demand may include industrial customers. A net flow into district heating is centralized heat production. It is divided between the sending area's units in proportion to their yearly heat output (storage left out), and brings that share of their fuel input and emissions. The Conversion Notes report the method.
_Avoid_: Excess heat (only one of its sources), heat transmission (also covers flows between district-heating areas, which stay inside centralized heat)

**Storage**:
Units that store electricity, heat or hydrogen. Never part of Capacity or Secondary Energy, since the common definitions have no storage names and discharge is not generation.

**Backup Unit**:
A `GNR_BACKUP…` unit that dispatch runs place in every region with near-unlimited capacity, so that demand is always met. Its capacity is never reported. By default its output counts as supply, under its fuel, so that supply still meets demand; whoever converts can leave it out instead. Either way the Conversion Notes give the amounts.

**Output-Share Split**:
How the fuel input, emissions and captured CO2 of a unit with two outputs (a CHP plant, or an electrolyser that also delivers heat) are divided between them: in proportion to the energy of each output. The method is reported with the results.

**Net CO2 Emissions**:
Fossil CO2 emitted, minus the captured biogenic CO2 that is stored, as the IAMC emission variables define it ("the sum of sources and sinks"). Captured and stored CO2 are also reported on their own as Carbon Capture and Carbon Removal. Where a run doesn't say how much captured biogenic CO2 is stored, only the fossil CO2 is reported, with a warning.

**Conversion Notes**:
The table returned with the IAMC data that says how its numbers were made and what was left out: the split methods used, fossil-only fallbacks, what went into Other, backup output, and amounts left out under Coverage. Each note names its IAMC Scenario, Region and Variable. They are also printed as warnings, and written as a Notes sheet next to the data.
_Avoid_: Metadata, meta (IAMC uses those for scenario-level indicators)

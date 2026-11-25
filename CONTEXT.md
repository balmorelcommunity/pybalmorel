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
Whether Balmorel's results account for everything an IAMC Variable's definition includes. A variable is reported where they do. A parent whose definition reaches beyond the sectors Balmorel models (e.g. `Emissions|CO2`, which also counts what transport burns) is not reported, even when some of its children are. The exceptions are variables Balmorel covers only in part, reported with a note saying what they cover: a variable whose share is known to be partial, such as the demand-side emissions of industry, which Balmorel gives only for its heat units (a stem's note, or an OptiFlow Mapping row's note, says so); and a stem's total, such as `Primary Energy`, with the totals per Source below it, such as `Primary Energy|Gas`, which count only what Balmorel models and so can be lower than a whole-economy model's (a Conversion Note says what it counts). Only modelled years are reported, never interpolated ones.

**Other**:
The `…|Other` child of an IAMC Variable, which takes Balmorel output that fits none of its other children, such as a fuel with no known classification. Conversion continues, and a warning names what was put there.
_Avoid_: Unclassified (it is classified, as Other)

**OptiFlow Mapping**:
A table, specific to one study, saying which OptiFlow flows bring CO2 into a CO2 pool (the CO2 Balmorel's units capture from biomass, and what OptiFlow captures itself, e.g. by direct air capture or biogas upgrading), which take it out to geological storage, and which flows to report as they are ('report' rows), such as the fuel ships and aircraft take in, reported under `Final Energy|Bunkers`, or the CO2 sent to storage, reported under `Carbon Capture|Geological Storage`. A 'fuel' row gives the CO2 of a fossil fuel OptiFlow burns, as its flow times the row's factor (e.g. 0.0732 Mt CO2 per PJ of jet fuel), reported under the row's emissions variable; the rows are checked against the emissions Balmorel's results carry for OptiFlow, which are not reported as Balmorel's. Carried emissions that are negative are flagged as likely CO2 that OptiFlow stores, as in one study so far. CO2 that OptiFlow captures from such fuel (e.g. onboard capture on ships) enters a pool like any other, and its stored part is taken off those emissions. A row's note becomes a Conversion Note on each variable it reports, e.g. that all shipping counts as international. A pool's Stored Share is the CO2 stored over the CO2 entering it, per year and over all countries; only that share of the captured biogenic CO2 counts as Carbon Removal and as negative emissions. OptiFlow names, designs and units differ from study to study (the studies so far give CO2 flows in Mt), so no mapping holds for all. pybalmorel ships rows only for flows the add-on itself names: the heat and electricity OptiFlow gives district heating and the grid (`HEATFLOW` into `HeatBuffer` and `ELECFLOW` into `ElecBuffer`, in TWh), reported under `Secondary Energy|Heat|Other` and `Secondary Energy|Electricity|Other`. What OptiFlow takes back out of the buffers is final energy only for some processes, e.g. direct air capture, so a study's mapping reports it where it is, under its carrier with a Final Energy Sector. A study's mapping adds to the shipped rows and must not report their flows again. Where a mapping reports a variable and variables below it, e.g. `Final Energy|Bunkers` and `Final Energy|Bunkers|Liquids`, those below count towards the variables below the reported one only, so no flow counts twice; what it reports under `Primary Energy` counts towards the Source's aggregates too, e.g. `Primary Energy|Biomass|Modern`. Without one, an OptiFlow-coupled run still reports the fossil CO2, that heat and every variable that doesn't depend on OptiFlow; the rest is withheld, with a warning.
_Avoid_: Mapping (alone, ambiguous with the Mapping Rule)

**Fuel Category**:
The IAMC fuel segment (`Coal`, `Gas`, `Oil`, `Biomass`, `Hydrogen`, `Nuclear`, `Hydro`, …) that a Balmorel fuel (`FFF`) is reported under. Only segments that occur in IAMC Variable names can be chosen. Defaults ship with pybalmorel, and whoever converts can override them, e.g. to move `MUNIWASTE` from `Biomass` to `Other`. A fuel belongs wholly to one category; it is never split between two. The same table says how units count the fuel as Primary Energy: by input, by output (Direct Equivalent), or not at all.

**Mapping Rule**:
A row in pybalmorel's mapping tables that sends Balmorel output with a given technology type, fuel and commodity (and, optionally, only units whose names match a pattern) to segments of an IAMC Variable name. Defaults ship with pybalmorel; rows passed by whoever converts take precedence. Output no rule covers goes to Other. A rule can also say how its units count as Primary Energy, overriding their fuel's, e.g. geothermal units, whose Balmorel fuel is waste heat, count by what they make.
_Avoid_: Mapping (alone, ambiguous with the OptiFlow Mapping)

**CCS Unit**:
A Balmorel unit (a `GGG` member) whose name carries the token `CCS`, e.g. `NGASCCS` or `STEAM-REFORMING-CCS`. Reported under `w/ CCS`; every other unit is `w/o CCS`. No fuel or technology type marks CCS, so the unit name is the only evidence. Some results give no captured CO2 (e.g. 2024_kountouris). Then a CCS unit's captured CO2 is derived: its fuel input times what units without CCS emit per unit of the same fuel, less its own emissions. That emission factor is used only if it fits every unit without CCS that burns the fuel; otherwise that fuel's captured CO2 is left out, with a Conversion Note.
_Avoid_: CC (Balmorel names use it for combined cycle)

**District-Heating Area / Individual Area / Industry Area**:
The three kinds of Balmorel heat area, told apart by name: individual areas contain `IDVU`, industry areas contain `IND-` (usually after a country or region prefix, e.g. `DE4-W_IND-LT-DH`), and every other heat area is a district-heating area. The name patterns are rule rows (the 'areas' table, first match wins), so whoever converts can classify areas differently. Centralized heat, which IAMC reports as `Secondary Energy|Heat` and `Final Energy|Heat`, is made and used in district-heating areas, and crosses into other areas only as Heat Exchange. Individual areas heat buildings on site, and industry areas supply process heat on site. Their heat is not reported, because no IAMC Variable matches what it covers; the Conversion Notes give the amounts. What their heat units take in is final energy instead: fuel as On-Site Fuel Use, electricity as On-Site Use in `Final Energy|Electricity`. Their emissions and captured CO2 are reported on the demand side, as `Emissions|CO2|Energy|Demand|Industry` and `…|Residential and Commercial`, with a note that these cover only the heat units of those areas, not the sector's other fuel use. Units making electricity or hydrogen count in every kind of area, since where they can be invested in is a modelling choice.
_Avoid_: Heat area (alone, when the kind matters)

**Heat Exchange**:
Heat that Balmorel's heat transmission moves between a district-heating area and an individual or industry area. It is netted per pair of areas and year, because much of it only makes a round trip, e.g. into an industry area's heat storage and back. A net flow out of district heating is consumption of centralized heat, reported in `Final Energy|Heat`. It is not reported as `Final Energy|Industry|Heat`, because the district-heating areas' own demand may include industrial customers. A net flow into district heating is centralized heat production. It is divided between the units that made the heat, in proportion to the heat each area had (storage left out): the sending area's own units, and, traced back through heat transmission between individual and industry areas, the units of the areas that sent heat to it. Their emissions stay with the area that made the heat: on the demand side for individual and industry areas. The fuel and electricity they took in for it is no longer final energy (On-Site Fuel Use, On-Site Use), but turned into centralized heat. Heat that left district heating and came back through those areas, or that no unit can be traced to, goes to Other. The Conversion Notes report the method and the amounts.
_Avoid_: Excess heat (only one of its sources), heat transmission (also covers flows between district-heating areas, which stay inside centralized heat)

**Final Demand Category**:
A Balmorel demand category (the `Category` of `EL_DEMAND_YCR`, `H_DEMAND_YCRA` or `H2_DEMAND_YCR`) that counts as consumption in `Final Energy|Electricity`, `Final Energy|Heat` or `Final Energy|Hydrogen`. For electricity: exogenous demand, the transport add-on's (`EXO_TRANS`), electric vehicles' (`ENDO_EV`), demand response (`ENDO_DR`, which can be negative and then lowers final demand), the On-Site Use part of what heat units take in (`ENDOGENOUS_ELECT2HEAT`), and what carbon capture uses (`ENDO_CCS`), which is also reported by Final Energy Sector; not what electrolysers, biomethanation or OptiFlow take, nor storage and losses. Otherwise only the total is reported, since Balmorel's exogenous demand isn't split by sector. For heat: exogenous demand, and the net Heat Exchange out of district heating (`NET_EXCHANGE`, not a Balmorel category). For hydrogen: exogenous demand, flexible exogenous demand (`ENDO_REGIONAL`) and the transport add-on's demand (`ENDO_OTHERTRANS`). Storage loading, losses, and hydrogen that fuel cells, biomethanation or OptiFlow's processes turn into other energy are not final; they show as Secondary Energy less Final Energy. All the hydrogen OptiFlow takes (`ENDO_OPTIFLOW`) counts as not final, since its processes mostly make ammonia, methanol and other fuels from it. Some OptiFlow designs burn part of it in ships; an OptiFlow Mapping can report that part as `Final Energy|Bunkers|Hydrogen`. It stays out of `Final Energy|Hydrogen`, so it is never counted twice. The 'demand_categories' rule table says which is which; a category it lacks (e.g. OptiFlow's heat, `ENDO_OPTIFLOW` under `HEAT`) is not reported, and the Conversion Notes give the amounts. A row marked 'on-site' splits its category by On-Site Use.

**Final Energy Sector**:
The end-use sector of `Final Energy|<Sector>|<Carrier>`, e.g. `Carbon Management`, `Industry`, `Transportation`; IAMC splits Final Energy by sector and by carrier, both adding up to the same total. A Final Demand Category the 'demand_categories' rules give a sector is reported under the sector, at each of its levels, as well as under its carrier: carbon capture's electricity (`ENDO_CCS`, the electricity CCS units use per tonne of CO2 they capture) under `Final Energy|Carbon Management|Carbon Capture and Storage|Electricity` and `Final Energy|Carbon Management|Electricity`, and in `Final Energy|Electricity`. On-Site Fuel Use is reported by the sector its 'final' stem gives, `Industry` or `Residential and Commercial`, as well as by carrier. A sector's total over all carriers is not reported, as the results give no sector all the energy it uses. Direct air capture inside OptiFlow uses electricity within `ENDO_OPTIFLOW`, which is not final, and heat from district heating; an OptiFlow Mapping can report both, by carrier with the sector, so that they count likewise: e.g. `Final Energy|Heat` with sector `Carbon Management|Direct Air Capture` is reported there, under `Final Energy|Carbon Management|Heat` and under `Final Energy|Carbon Management|Direct Air Capture|Heat`.
_Avoid_: Sector (alone: an industry area is an Area Kind, and covers only part of the Industry sector)

**On-Site Use**:
The part of a demand category that units take in where what they make isn't reported, which counts as final demand. Heat pumps and electric boilers in individual and industry areas take in electricity (`ENDOGENOUS_ELECT2HEAT`) to make heat that isn't centralized heat, so that electricity is consumption, in `Final Energy|Electricity`; the same units in district-heating areas make centralized heat, so theirs is not. Units count when none of their output has an 'output' stem for their Area Kind; their fuel input of the row's Fuel Category moves from the category to `ON_SITE`, per region and year. An electrolyser in an industry area doesn't count, as its hydrogen is reported. The share of their input for heat sent into district heating as Heat Exchange doesn't count either, as that heat is centralized heat. In the studies so far, the input before that equals `ENDOGENOUS_ELECT2HEAT` in total. Where units take in more than the category gives, all of it counts, and the Conversion Notes say so.
_Avoid_: Individual demand (only one of the area kinds)

**On-Site Fuel Use**:
The fuel that heat units in individual and industry areas take in, which counts as final energy, as their heat isn't reported: the gas boilers heating buildings, the biomass boilers making process heat. It is reported by carrier (`Final Energy|Gases|Gas`, `Final Energy|Solids|Biomass`, `Final Energy|Solar`, …) and by Final Energy Sector: `Residential and Commercial` for individual areas, `Industry` for industry areas, or that sector's `Other` where the Definitions Snapshot has no such variable (e.g. solar heating under `Final Energy|Residential and Commercial|Other`). The carrier comes from the fuel (the 'carrier' column of the Fuel Category table), or a Mapping Rule, e.g. Geothermal for geothermal units. Fuel input counts as it is, also for solar and geothermal heat. Like Primary Energy, it is per unit and divided by the Output-Share Split, so a CHP unit's counts for its heat only where its electricity is reported. The share for heat sent into district heating as Heat Exchange doesn't count, as it turns into centralized heat; heat moved between individual and industry areas stays final in the area that made it. Only the 'final' rows of the 'stems' table make fuel use final, and they can't cover an Area Kind and commodity that an 'output' row reports, so nothing counts both as fuel and as what it is turned into. Electricity is On-Site Use, not this; hydrogen has no carrier yet. The Conversion Notes say that the sectors' other fuel use is not in Balmorel.
_Avoid_: Final energy (alone: also covers demand), Fuel consumption

**Net Exports**:
What a country sends to other countries less what it gets from them, reported as `Trade|Secondary Energy|Electricity [Volume]` and `Trade|Secondary Energy|Hydrogen [Volume]` (negative for net imports). Taken from electricity and hydrogen transmission between regions of different countries, and from Import Units. Transmission within a country is left out, and transmission to a region whose country the results don't give is not counted; the Conversion Notes give its amount. Net Exports with the opposite sign, the net imports, are also reported as `Primary Energy|Secondary Energy Trade`; summed over all countries they cancel out, apart from Import Units and trade with regions that have no IAMC Region.
_Avoid_: Trade (alone, ambiguous between the IAMC stem and the transmission it is computed from), Net imports (the opposite sign)

**Import Unit**:
A Balmorel unit that brings a commodity in from outside the model, such as the `ELECTROLYZER` units with fuel `IMPORT_H2`, marked by a Mapping Rule with the segment `import`. Its output counts as imports in Net Exports, not as Secondary Energy, and its capacity is not reported. The Conversion Notes give the amounts.
_Avoid_: Electrolyser (Balmorel gives import units that technology type)

**Electrolyser Capacity**:
The capacity of units that make hydrogen from electricity, reported as the hydrogen they make, as Balmorel states it. Every `Capacity|<output>|<input>` variable is measured on the output side: `Capacity|Electricity|Gas` is gas plants' electric output, and `Capacity|Electricity|Hydrogen` fuel cells', so `Capacity|Hydrogen|Electricity` is electrolysers' hydrogen output, and `Capacity|Hydrogen` adds electrolysers and steam reformers on the same side. The common definitions don't say which side capacity is measured on ("capacity to produce hydrogen from electrolysis"), and electrolysers are often quoted by electricity input elsewhere, which is larger by their input per output.
_Avoid_: Hydrogen capacity (for electrolysers, ambiguous between input and output side)

**Primary Energy**:
The energy that enters the units Balmorel models from outside the system it models, reported as `Primary Energy|<Source>|<what it is used for>` (e.g. `Primary Energy|Gas|Electricity|w/ CCS`), or as `Primary Energy|<Source>` where the common definitions don't split the Source by use (e.g. `Primary Energy|Wind`). Per unit, it is the fuel input, or what the unit makes (Direct Equivalent) for nuclear and the non-biomass renewables, divided over what the unit makes by the Output-Share Split. Units whose fuel other units made (electricity, heat, hydrogen, biomethane), or whose fuel is waste heat, count none, so nothing counts twice. Uses follow Secondary Energy: electricity, hydrogen, centralized heat, and the biogas that upgrading turns into biomethane (`Primary Energy|Biomass|Gases`). What units in individual and industry areas use for heat counts only towards `Primary Energy|<Source>` and `Primary Energy`, as the common definitions have `Primary Energy|<Source>|Heat` for centralized heat only. That includes the heat they send into district heating as Heat Exchange, whose Primary Energy stays with the areas that made it, as its emissions do. Net imports of electricity and hydrogen count as `Primary Energy|Secondary Energy Trade` (see Net Exports). Units counted by fuel input whose input the results don't give are not estimated; the Conversion Notes name them. OptiFlow's fuel input is not reported as Balmorel's, and the Conversion Notes give it. `Primary Energy` and its totals per Source (`Primary Energy|Gas`, `Primary Energy|Gas|w/ CCS`, `Primary Energy|Fossil`, …) sum all of it, each amount once, but count only what Balmorel models (see Coverage), not other sectors' fuel use nor OptiFlow's.
_Avoid_: Fuel input (only one way of counting it), Fuel consumption

**Direct Equivalent**:
Counting a unit's Primary Energy as the energy it makes, which the common definitions use for nuclear and the non-biomass renewables. The `primary` column of the Fuel Category table says, per fuel, whether its units count by input (the default), by output (Direct Equivalent: `NUCLEAR`, `SUN`, `WATER`, `WIND`), or not at all (`ELECTRIC`, `HEAT`, `HYDROGEN`, `IMPORT_H2`, `BIOMETHANE`, `WASTEHEAT`). A Mapping Rule can set it for some units instead, e.g. geothermal units. Balmorel gives nuclear units a fuel input, but it is not used, so that nuclear is counted as the other models count it.
_Avoid_: Substitution method (the other convention, not used)

**Source**:
The first segment below `Primary Energy`: the Fuel Category of a unit's fuel, or the segment its Mapping Rule gives (e.g. `Wind`, `Geothermal`). A stem's `{source}` is filled with it, so `Primary Energy|{source}|Electricity` becomes `Primary Energy|Gas|Electricity`, or `Primary Energy|Wind` where the Definitions Snapshot has no `Primary Energy|Wind|Electricity` and `Primary Energy|Wind` has no children. Where `Primary Energy|<Source>` has children but none for this use (e.g. no `Primary Energy|Gas|Heat`), the amount counts only towards `Primary Energy|<Source>` and the totals above it; the Conversion Notes give it. A Source the common definitions lack goes to `Primary Energy|Other`.
_Avoid_: Fuel (a Balmorel `FFF`, of which many share a Source)

**Commodity Balance**:
The check that, per region and year, a commodity's output (storage left out) less its Net Exports equals its demand in known categories, final or not. It runs for every commodity with a Final Energy stem, over the area kinds of that stem: heat over district-heating areas, with Heat Exchange counted as output and demand; electricity and hydrogen over whole regions. Results that make or use the commodity where the Reader doesn't look, such as transmission a result file doesn't list or a demand category the rules lack, break it; the Conversion Notes then name the region and the gap. A category given with the wrong sign makes a gap of twice its size, with the opposite sign: regions where taking one category with the opposite sign closes the gap in every year share one note per scenario, which names the category, so the gaps that remain stand out; elsewhere, the note gives the gap that taking a negative category with the opposite sign would leave. Results of Balmorel runs linked to OptiFlow have been seen to give `ENDO_OPTIFLOW` of electricity and heat as OptiFlow's net supply (`VFLOWBUFFER`), where Balmorel's balances count its negative as demand; the category isn't final, so nothing reported changes. Results with output of the commodity but no demand at all get one note instead. The conversion does not try to close a gap.
_Avoid_: District Heating Balance (the earlier, heat-only check)

**Storage**:
Units that store electricity, heat or hydrogen. Never part of Capacity or Secondary Energy, since the common definitions have no storage names and discharge is not generation.

**Backup Unit**:
A `GNR_BACKUP…` unit that dispatch runs place in every region with near-unlimited capacity, so that demand is always met. Its capacity is never reported. By default its output counts as supply, under its fuel, so that supply still meets demand; whoever converts can leave it out instead. Either way the Conversion Notes give the amounts.

**Output-Share Split**:
How the fuel input, Primary Energy, emissions and captured CO2 of a unit with two outputs (a CHP plant, or an electrolyser that also delivers heat) are divided between them: in proportion to the energy of each output. The method is reported with the results. Emissions or captured CO2 of a unit with no output in the results can't be divided; the Conversion Notes give the amounts, unless they are solver residue.

**Net CO2 Emissions**:
Fossil CO2 emitted, minus the captured biogenic CO2 that is stored, as the IAMC emission variables define it ("the sum of sources and sinks"). Captured and stored CO2 are also reported on their own as Carbon Capture and Carbon Removal. Runs not linked to OptiFlow have no use for captured CO2, so all of it counts as stored, reported as `Carbon Capture|Geological Storage`; for linked runs, the OptiFlow Mapping's 'report' rows give storage. Where a run doesn't say how much captured biogenic CO2 is stored, only the fossil CO2 is reported, with a warning.

**Price**:
Balmorel's average price of electricity, hydrogen or district heat: the mean over the year of the hourly marginal price of its balance, not weighted by consumption. A country's price is the mean over its regions (electricity, hydrogen) or district-heating areas (heat) weighted by their annual demand for the commodity. Where none has demand, the country has no price: the marginal cost of a balance without demand is an artifact of the LP (the cost of serving one more MWh that nobody asks for, often by the penalty on an unmet balance), and the Conversion Notes name those countries. Reported as `Price|Secondary Energy|<commodity>` only, not split by source, and empty, not 0, for years without prices. An average price beyond ±500 money per MWh may be that penalty rather than a market price; the Conversion Notes name the regions where one enters the reported price.
_Avoid_: Marginal cost (one hour's), Consumption-weighted price (Balmorel can give one, but MainResults doesn't hold it)

**Carbon Price**:
The CO2 tax that emitting units pay over their emissions, counting the units that pay any, reported as `Price|Carbon`. Where units pay different rates, the Conversion Notes give the range. A run that caps emissions instead of taxing them has no carbon price here, since MainResults doesn't hold the cap's shadow price.
_Avoid_: CO2 tax (what one unit pays), Emission price

**Currency**:
What one unit of the money in Balmorel's results, EUR_2016 (the currency and price year of its input data), is worth in a currency the IAMC units name, given to `to_iamc` as `currency={'USD_2010': <worth>}`. Where `currency` doesn't name the IAMC unit's currency, the Price Year tables (`backcasting/pricelevel.py`) give the worth for EUR or USD of a year they cover: EUR_2016 is brought to that year by the euro-area HICP and, for USD, exchanged at that year's mean rate (ADR 0017): one EUR_2016 is worth 1.2319 USD_2010. A Conversion Note gives the worth used. Prices in any other currency are not reported. The results themselves don't say which currency their money is in, so data in another currency would need `currency` to say so.
_Avoid_: Exchange rate (it also covers the price year)

**Investment Cost**:
Not reported: MainResults holds investment costs only as annuities spread over the years, not as the investments made, so `Investment|…` and `Capital Cost|…` can't be derived from it.

**Conversion Notes**:
The table returned with the IAMC data that says how its numbers were made and what was left out: the split methods used, fossil-only fallbacks, what went into Other, backup output, and amounts left out under Coverage. Each note names its IAMC Scenario, Region and Variable. When the same thing happens in several regions, there is one note per scenario that names the regions and gives the total, and its Region is left empty. They are also printed as warnings, and written as a Notes sheet next to the data.
_Avoid_: Metadata, meta (IAMC uses those for scenario-level indicators)

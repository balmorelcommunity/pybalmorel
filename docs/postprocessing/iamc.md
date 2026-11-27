# IAMC Reporting

`pybalmorel.iamc` converts Balmorel results to the IAMC format that model
intercomparisons ask for. Each row holds one model, scenario, country and
IAMC Variable, with one column per year. Names and units follow the
[IAMC common definitions](https://github.com/IAMconsortium/common-definitions).
It reads `MainResults`, so it needs a GAMS installation.

:::{tip}
Once in the IAMC format, Balmorel scenarios can take part in model
intercomparison projects and be submitted to the scenario databases that
IPCC assessment reports draw on, such as the AR7 Scenarios Database. A set
of scenarios along different emission pathways is the most useful, e.g.
net zero by 2050, a later target and current policies.
:::

## Quick start

```python
from pybalmorel import MainResults
from pybalmorel.iamc import write_iamc

results = MainResults(['MainResults_SC1.gdx', 'MainResults_SC2.gdx'], paths='path/to/results',
                      system_directory='/opt/gams/53')
data, notes = results.to_iamc('Balmorel-DTU')
write_iamc(data, notes, 'balmorel_iamc.xlsx')
```

`to_iamc` takes the IAMC Model label and returns two tables:

- `data` holds the IAMC data. Its columns are `Model`, `Scenario`, `Region`,
  `Variable`, `Unit` and one per modelled year. Regions are countries, and
  values are in the units of the common definitions: EJ/yr, GW, Mt CO2/yr
  or USD_2010/GJ.
- `notes` holds the Conversion Notes, in columns `Scenario`, `Region`,
  `Variable` and `Note`. They say how numbers were made and what was left
  out: what went under `…|Other`, what backup units supplied, which parts
  of a total Balmorel doesn't model, and where a commodity's supply and
  demand don't add up. The first notes are also printed during
  conversion. Read them before you submit.

`write_iamc` writes an .xlsx file with a `data` and a `notes` sheet, or a
.csv file plus `<name>_notes.csv`.

The how-to guides below cover the other arguments of `to_iamc`. The
{doc}`API reference <../autoapi/pybalmorel/iamc/index>` lists them all.

## What is reported

- Capacity and Secondary Energy of electricity, district heat and hydrogen,
  by Source and with or without CCS. IAMC calls district heat `Heat`.
- Capacity Additions of electricity, district heat and hydrogen: new
  installations per year (see below).
- Final Energy by carrier, and by sector where Balmorel knows the sector.
  Heat that individual and industry areas make where it is used is not
  reported as heat, because the common definitions count only centralized
  heat under `Heat`. What those areas take in is reported instead, as Final
  Energy of `Residential and Commercial` (individual areas) or `Industry`
  (industry areas): the fuel their heat units burn, the electricity those
  units use, and the district heat the areas get net from district heating.
  Their emissions count as demand-side emissions.
  The transport add-on's electricity counts under
  `Final Energy|Transportation|Electricity`. The hydrogen that its synthetic
  fuels are made of counts as liquids, under `Final Energy|Liquids|Hydrogen`
  and `Final Energy|Transportation|Liquids|Hydrogen`, not under
  `Final Energy|Hydrogen`.
- Primary Energy by Source and use. Nuclear and the non-biomass renewables
  count by what they make (direct equivalent).
- Emissions|CO2, Carbon Capture and Carbon Removal.
- The emission intensity of electricity: its emissions per electricity made,
  `Emission Intensity|CO2|Energy|Supply|Electricity`. An intensity can't be
  summed. To aggregate regions, divide their summed emissions by their summed
  electricity.
- Net exports of electricity and hydrogen between countries, under Trade.
- Prices of electricity, hydrogen and district heat, and the carbon price.

Totals such as `Final Energy`, `Primary Energy` and `Emissions|CO2` count
only what Balmorel models, so they can be lower than a whole-economy
model's. A Conversion Note says so. Variables whose definition reaches
beyond what Balmorel models are left out. So are investment and capital
costs, because MainResults holds only their annuities. Only modelled years
are reported.

Capacity Additions follow IAMC's definition: new installations per year, not
the net change in capacity. pybalmorel takes the rise in the capacity that
Balmorel invested in (category `ENDOGENOUS` of `G_CAP_YCRAF`) since the
previous model year, and divides it by the years between them. An investment
therefore counts once, spread over those years, and nothing accumulates.
Retirements are not subtracted; `Capacity|…` holds the capacity in place.
Exogenous capacity is input data, so it adds nothing. The first model year of
a Balmorel scenario has no year before it, so its additions are left empty.

## How-to guides

### Name the IAMC Scenarios

Each IAMC Scenario takes its Balmorel scenario's name unless you pass
`scenarios`. Balmorel scenarios can share a name if their years don't
overlap, e.g. one run per year:

```python
data, notes = results.to_iamc('Balmorel-DTU', scenarios={'LTS_2030': 'NMSF2-LTS',
                                                         'LTS_2050': 'NMSF2-LTS'})
```

### Limit the output to a Template

Intercomparisons send a variable list, the Template. Pass it to report only
the variables its `Extended List` sheet accepts. If it also has a `Region`
sheet, only those regions are reported.

```python
data, notes = results.to_iamc('Balmorel-DTU', template='varlist.xlsx')
```

Without a Template, every variable the results cover is reported.

### Add fuels, units or areas the shipped rules don't know

The [rule tables](#how-it-works) decide which IAMC Variable each Balmorel
name goes under. A fuel without a rule goes under `…|Other`, and a warning
names it. To fix that, pass your own rows with `rules`, as a DataFrame or a
CSV file per table:

```python
import pandas as pd

rules = {
    # Fuel Category, how it counts as Primary Energy, and its Final Energy carrier
    'fuels': pd.DataFrame([{'fuel': 'AMMONIA', 'category': 'Hydrogen', 'primary': 'no',
                            'carrier': 'Liquids|Hydrogen'}]),
    # Units with '_CC' in their name capture CO2 (by default, units with 'CCS' do)
    'mapping': pd.DataFrame([{'tech_type': '', 'fuel': '', 'commodity': '',
                              'unit_pattern': '_CC(_|$)', 'segments': '{category}|w/ CCS'}]),
    # Areas ending in '_IND' are industry areas
    'areas': pd.DataFrame([{'pattern': '_IND$', 'area_kind': 'industry'}]),
}
data, notes = results.to_iamc('Balmorel-DTU', rules=rules)
```

Your row replaces the shipped row with the same key, e.g. the same `fuel`.
`mapping` rows have no key: yours are added and tried first. `optiflow`
rows are different: they replace the base OptiFlow Mapping as a whole (see
below). Then run `check_rules(rules=rules)`. It lists the rows whose IAMC Variables
are not in the Definitions Snapshot.

### Report OptiFlow results

For a run linked to the OptiFlow add-on, `to_iamc` reads
`Optiflow_<MainResults file>` from the folder of each MainResults file. To
read another file, pass it per Balmorel scenario with `optiflow`.

OptiFlow designs differ between studies. An **OptiFlow Mapping** says how
the results of one design are reported. pybalmorel ships the Mapping of the
newest design, that of Fristed (2027), as the **base OptiFlow Mapping**.
`to_iamc` uses it when you pass none. A Conversion Note then says so, and
lists what the rows that match no flow would have reported. Many unmatched
rows mean your study has another design.

The base Mapping reports the fuel that ships and aircraft take in under
`Final Energy|Bunkers`, the CO2 that OptiFlow captures and stores, and the
heat and electricity that direct air capture uses. It reports the electricity
that OptiFlow uses to compress CO2 under
`Final Energy|Carbon Management|Carbon Capture and Storage|Electricity`,
beside what Balmorel's CCS units use. This covers all the CO2 that OptiFlow
collects, including CO2 that is made into fuel. It also counts Primary
Energy:

- The biomass that OptiFlow's biofuel plants and digesters take in, by what
  they make: `Primary Energy|Biomass|Liquids` and `Primary Energy|Biomass|Gases`.
- The fossil fuel that ships and aircraft burn, at the point where they burn
  it: `Primary Energy|Oil|Liquids` and `Primary Energy|Gas|Gases`. OptiFlow
  buys this fuel already refined, so what refining loses is not counted.

These amounts count towards the totals too, such as
`Primary Energy|Biomass|w/o CCS`, `Primary Energy|Fossil` and `Primary Energy`.

It also reports the fuel that OptiFlow's plants make, where it leaves the
plants and before it is moved between countries:

- Liquid fuels under `Secondary Energy|Liquids`: from biomass (Fischer-Tropsch
  diesel and jet fuel, pyrolysis oil and methanol) under
  `Secondary Energy|Liquids|Biomass`, and from hydrogen (ammonia, methanol and
  Fischer-Tropsch fuel) under `Secondary Energy|Liquids|Hydrogen`.
- Biomethane under `Secondary Energy|Gases` and `Secondary Energy|Gases|Biomass`.

A plant that adds hydrogen to biomass or biogas, such as methanation, counts
as making all of its fuel from biomass.

For another design, write your own Mapping. It replaces the base one as a
whole: none of the base rows apply. Each row matches flows by
`from_process`, `to_process` and `flow`, which are regular expressions, and
gives them a `role`. For example, a CSV file `optiflow_mystudy.csv`:

```text
from_process,to_process,flow,role,pool,unit,factor,variable,removal,emissions,note,sector
CO2_Source_Biogen,CO2,CO2_FLOW,balmorel,CO2,Mt CO2,,,,,,
CO2_DAC_.*,CO2,CO2_FLOW,capture,CO2,Mt CO2,,Carbon Capture|Direct Air Capture,Carbon Removal|Geological Storage|Direct Air Capture,Emissions|CO2|Other Capture and Removal,,
CO2,CO2_SEQUESTRATION,CO2_FLOW,store,CO2,Mt CO2,,,,,,
CO2,CO2_SEQUESTRATION,CO2_FLOW,report,,Mt CO2,,Carbon Capture|Geological Storage,,,,
.*_Eff,Sea_fuels_sum,,report,,PJ,,Final Energy|Bunkers|International Shipping,,,All shipping is counted as international.,
HeatBuffer_GJ,CO2_DAC_.*,HEATFLOW_GJ,report,,PJ,,Final Energy|Heat,,,,Carbon Management|Direct Air Capture
```

```python
data, notes = results.to_iamc('Balmorel-DTU', rules={'optiflow': 'optiflow_mystudy.csv'},
                              optiflow={'SC1': 'other/folder/Optiflow_MainResults_SC1.gdx'})
```

These rows do the following:

- They put two kinds of CO2 into one pool, `CO2`: the biogenic CO2 that
  Balmorel's units capture (`balmorel`) and the CO2 that direct air capture
  takes in (`capture`).
- The flow to sequestration (`store`) gives the pool's stored share. Only
  that share counts as Carbon Removal.
- Ship fuel is reported as bunkers.
- The heat that direct air capture uses is reported under
  `Final Energy|Heat`. The `sector` column also reports it under
  `Final Energy|Carbon Management|…`.

To change a few rows of the base design, copy
[optiflow_base.csv](https://github.com/Mathias157/pybalmorel/blob/master/src/pybalmorel/iamc/rule_tables/optiflow_base.csv),
edit it and pass the copy.

Some flows are the same in every design, because the add-on itself names
them: the heat and electricity OptiFlow gives to Balmorel through its
`HeatBuffer` and `ElecBuffer`. pybalmorel reports these with its own rows,
whichever Mapping applies. Your Mapping must not report them again, since
every row applies to every flow it matches.

When OptiFlow makes the transport fuels, the transport add-on must not ask
for the same fuels as hydrogen (`ENDO_OTHERTRANS`). Change the add-on's
settings for such runs. Otherwise the fuels count twice: once as the hydrogen
under `Final Energy|Liquids|Hydrogen`, and once as what OptiFlow reports.
`to_iamc` doesn't check this.

If no row of the Mapping brings the CO2 Balmorel's units capture into a
pool, that CO2 has no stored share. The emissions and removal that depend on
it are then left empty. The header of
[optiflow.csv](https://github.com/Mathias157/pybalmorel/blob/master/src/pybalmorel/iamc/rule_tables/optiflow.csv)
explains every role and column.

### Report prices in another currency

Balmorel's money is EUR_2016, and the common definitions use USD_2010.
pybalmorel converts with its own price-level tables, which give
1 EUR_2016 = 1.2319 USD_2010 ([ADR 0017](../adr/0017-iamc-currency-deflate-in-euros-then-exchange-at-the-target-years-rate.md)).
To use another worth, pass it:

```python
data, notes = results.to_iamc('Balmorel-DTU', currency={'USD_2010': 1.0067})
```

### Leave out backup units

Dispatch runs place `GNR_BACKUP…` units in every region so that demand is
always met. By default, their output counts as supply under their fuel,
with a Conversion Note giving the amounts. Their capacity is never
reported. To leave them out, pass `backup_units='exclude'`. To match other
names, pass a regular expression with `backup_pattern`.

### Update the IAMC definitions

pybalmorel ships a copy of the common definitions, the Definitions
Snapshot. To move to a newer version:

1. Run `pixi run update-iamc-definitions` from a clone of pybalmorel.
2. Review the diff of `src/pybalmorel/iamc/definitions/variables.csv`.
3. Run `pytest tests/test_iamc.py`, or `check_rules()`. Both list rule rows
   whose IAMC Variables the new snapshot lacks. Fix those rows.

To try another copy without changing pybalmorel, pass a folder holding
`variables.csv` and `regions.csv` with `definitions`.

## How it works

Conversion has three layers
([ADR 0016](../adr/0016-iamc-conversion-through-a-reader-mapping-rules-and-a-definitions-snapshot.md)):

1. **The reader** (`read_mainresults`). It is the only part that knows
   Balmorel's symbols. It returns one long table of what each unit and
   area does.
2. **The Mapping Rules.** These are CSV tables in
   [`iamc/rule_tables/`](https://github.com/Mathias157/pybalmorel/tree/master/src/pybalmorel/iamc/rule_tables).
   They say which IAMC Variable each Balmorel name goes under. The header
   comments of each table explain its columns.
3. **The Definitions Snapshot**, in `iamc/definitions/`. Every IAMC Variable
   and IAMC Region is checked against it, and units come from it.
   pybalmorel never invents names.

| Table | What its rows give |
| --- | --- |
| `fuels` | Per Balmorel fuel: its Fuel Category (e.g. `Gas`), how it counts as Primary Energy, and its Final Energy carrier |
| `mapping` | Per technology type, fuel, commodity or unit-name pattern: the segments below the stem, e.g. `Wind\|Offshore` or `{category}\|w/ CCS` |
| `stems` | Per quantity, commodity and area kind: the stem, e.g. `Secondary Energy\|Electricity`, and the total it counts towards, or `-` to leave it out on purpose, with a Conversion Note saying why |
| `aggregates` | Which Sources sum to an aggregate, e.g. `Coal`, `Gas` and `Oil` to `Fossil` |
| `countries` | Balmorel country to ISO3 code, which gives the IAMC Region |
| `areas` | Area-name patterns for individual and industry areas. Other areas are district heating |
| `demand_categories` | Which demand categories are final energy, their Final Energy Sector, and the carrier they count as. A row can be for the area kind where the demand is used |
| `ratios` | IAMC Variables that divide one reported variable by another, e.g. an emission intensity |
| `optiflow` | The OptiFlow Mapping: which OptiFlow flows to report, and how. The base one is in `optiflow_base.csv`; `optiflow.csv` has the rows for the add-on's own flows |

# IAMC Reporting

`pybalmorel.iamc` converts Balmorel results to the IAMC format that model
intercomparisons ask for. Each row holds one model, scenario, country and
IAMC Variable, with one column per year. Names and units follow the
[IAMC common definitions](https://github.com/IAMconsortium/common-definitions).
It reads `MainResults`, so it needs a GAMS installation.

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

- Capacity and Secondary Energy of electricity, heat and hydrogen, by Source
  and with or without CCS.
- Final Energy by carrier, and by sector where Balmorel knows the sector.
- Primary Energy by Source and use. Nuclear and the non-biomass renewables
  count by what they make (direct equivalent).
- Emissions|CO2, Carbon Capture and Carbon Removal.
- Net exports of electricity and hydrogen between countries, under Trade.
- Prices of electricity, hydrogen and district heat, and the carbon price.

Totals such as `Final Energy`, `Primary Energy` and `Emissions|CO2` count
only what Balmorel models, so they can be lower than a whole-economy
model's. A Conversion Note says so. Variables whose definition reaches
beyond what Balmorel models are left out. So are investment and capital
costs, because MainResults holds only their annuities. Only modelled years
are reported.

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
|---|---|
| `fuels` | Per Balmorel fuel: its Fuel Category (e.g. `Gas`), how it counts as Primary Energy, and its Final Energy carrier |
| `mapping` | Per technology type, fuel, commodity or unit-name pattern: the segments below the stem, e.g. `Wind\|Offshore` or `{category}\|w/ CCS` |
| `stems` | Per quantity, commodity and area kind: the stem, e.g. `Secondary Energy\|Electricity`, and the total it counts towards |
| `aggregates` | Which Sources sum to an aggregate, e.g. `Coal`, `Gas` and `Oil` to `Fossil` |
| `countries` | Balmorel country to ISO3 code, which gives the IAMC Region |
| `areas` | Area-name patterns for individual and industry areas. Other areas are district heating |
| `demand_categories` | Which demand categories are final energy, and their Final Energy Sector |
| `optiflow` | The OptiFlow Mapping: which OptiFlow flows to report, and how. The base one is in `optiflow_base.csv`; `optiflow.csv` has the rows for the add-on's own flows |

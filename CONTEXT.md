# pybalmorel

Python tooling for pre- and post-processing around the Balmorel energy system model, including the `weatheryear` module that converts external model outputs (CorRES, demand, hydro, COP) into Balmorel-ready `.inc` files for a chosen historical weather year.

## Language

### Weather-year preprocessing

**CapDev timestep**:
A representative `Season.Hour` pair (e.g. `S02.T073`) used for the reduced capacity-development (investment) time resolution. Built as the cross product of `CapDev_timesteps_to_keep.S` (representative seasons) and `.T` (representative hours) — both are lists of equal standing, not a season-plus-hours pair.
_Avoid_: CapDev season (a single `S` value is not itself a timestep)

**Day-Ahead (DA) resolution**:
The full hourly time series for a weather year, before it is reduced to CapDev timesteps.
_Avoid_: full resolution, raw resolution

**tech_to_keep**:
The list of technology-run folder names (e.g. `Future_Onshore`, `PV_Rooftop`) that `WEATHERYEAR.get_vre_data()` actually processes when exporting VRE time series from CorRES. Folders present under `weatheryear_inputs_folder` but not listed here are silently skipped.

"""
Backcasting Tests requiring GAMS

Tests of the backcast toolbox that need the GAMS GDX library, kept out of
test_backcasting.py so CI can run that without GAMS.

Created on 28.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os

import gams.core.gdx as gdx

from pybalmorel.backcasting.thermal import ACRONYM_SCALE, acronym_name, acronym_names

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in your .env file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)

# %% ------------------------------- ###
###          1. Acronyms            ###
### ------------------------------- ###


def test_acronym_names_round_trip(tmp_path):
    gdx_path = tmp_path / "acronyms.gdx"
    handle = gdx.new_gdxHandle_tp()
    gdx.gdxCreateD(handle, gams_system_directory, gdx.GMS_SSSIZE)
    gdx.gdxOpenWrite(handle, str(gdx_path), "pybalmorel")
    gdx.gdxAcronymAdd(handle, "GCND", "Condensing", 224)
    gdx.gdxAcronymAdd(handle, "COAL", "Hard coal", 396)
    gdx.gdxClose(handle)
    gdx.gdxFree(handle)

    names = acronym_names(gdx_path, gams_system_directory)

    assert sorted(names.values()) == ["COAL", "GCND"]
    assert acronym_name(224 * ACRONYM_SCALE, names) == "GCND"
    assert acronym_name(3.96e303, names) == "COAL"
    assert acronym_name(396.0, names) is None

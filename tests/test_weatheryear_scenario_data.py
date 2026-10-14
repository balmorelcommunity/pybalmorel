"""
Weather-Year Scenario Data Tests

Tests write_scenario_data, which turns WEATHERYEAR's CapDev output into the
.inc files a Balmorel scenario's data/ folder needs. GAMS-free: only the
written text is checked.

Created on 14.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pathlib import Path

import pytest

from pybalmorel.weatheryear.scenario_data import write_scenario_data

# %% ------------------------------- ###
###          1. Fixtures            ###
### ------------------------------- ###

WND_VAR_T = """\
TABLE   WND_VAR_T1(SSS,TTT,AAA)  'Variation of the wind generation'
          DK1_OFF_OFF_Existing_RG1  DK3_OFF_OFF_Existing_RG1  SE4_OFF_OFF_Existing_RG1
S01.T001                    0.1000                    0.2000                    0.3000
S01.T002                    0.4000                    0.5000                    0.6000
;
WND_VAR_T(AAA,SSS,TTT) = WND_VAR_T1(SSS,TTT,AAA);
WND_VAR_T(IA,SSS,TTT)$((NOT SUM((S,T), WND_VAR_T(IA,S,T))) AND WNDFLH(IA)) = WND_VAR_T('DK2_NoDH',SSS,TTT) ;
WND_VAR_T1(SSS,TTT,AAA)=0;
"""

SOURCE_FILES = {
    "WND_VAR_T.inc": WND_VAR_T,
    "WNDFLH.inc": "PARAMETER WNDFLH(AAA) /\nDK1_OFF_OFF_Existing_RG1 4000\n/;\n",
    "SOLE_VAR_T.inc": "TABLE SOLE_VAR_T1(SSS,TTT,AAA)\n          DK1_PV\nS01.T001  0.0\n;\n",
    "SOLEFLH.inc": "PARAMETER SOLEFLH(AAA) /\nDK1_PV 1000\n/;\n",
    "WTRRRVAR_T_WY.inc": "WTRRRVAR_T('NO2_A1', 'S01', 'T001') = 10.0;\n",
    "WTRRSVAR_S_WY.inc": "WTRRSVAR_S('SE4A', 'S01') = 5.0;\n",
    "WTRRRFLH_WY.inc": "WTRRRFLH('AT_A') = 1.1 * WTRRRFLH('AT_A') ;\n",
    "WTRRSFLH_WY.inc": "WTRRSFLH('AT_A') = 1.05;\n",
    "DE_VAR_T_OTHER.inc": "DE_VAR_T('DK1', 'OTHER', 'S01', 'T001') = 1.0;\n",
    "DE_VAR_T_RESE.inc": "DE_VAR_T('DK1', 'RESE', 'S01', 'T001') = 2.0;\n",
    "DH_VAR_T_RESIDENTIAL.inc": "DH_VAR_T('DK1_IDVU-SPACEHEAT', 'RESIDENTIAL', 'S01', 'T001') = 3.0;\n",
    "DH_VAR_T_RESH.inc": "DH_VAR_T('DK1_A', 'RESH', 'S01', 'T001') = 4.0;\n",
    "DH_VAR_T_TERTIARY.inc": "DH_VAR_T('DK1_IDVU-SPACEHEAT', 'TERTIARY', 'S01', 'T001') = 5.0;\n",
    "COP_WY_air_air.inc": "COP('AT_A', 'HP') = COP('AT_A', 'HP') * 1.0;\n",
}

STATIC_FILES = {
    "DH_RESH.inc": "DH(YYY,'DK1_A','RESH') = DH(YYY,'DK1_A','RESH')*1.02;\n",
    "GKFX_renewable.inc": "* existing fleet - must not be copied\n",
}


@pytest.fixture
def written(tmp_path: Path) -> Path:
    capdev_dir = tmp_path / "to_balmorel" / "CapDev" / "raw"
    capdev_dir.mkdir(parents=True)
    for name, text in SOURCE_FILES.items():
        (capdev_dir / name).write_text(text)
    for name, text in STATIC_FILES.items():
        (tmp_path / "to_balmorel" / name).write_text(text)

    dest_dir = tmp_path / "data"
    write_scenario_data(capdev_dir, tmp_path / "to_balmorel", dest_dir, drop_areas=("DK3",))
    return dest_dir


# %% ------------------------------- ###
###            2. Tests             ###
### ------------------------------- ###


def test_writes_only_files_balmorel_reads(written: Path):
    assert sorted(p.name for p in written.iterdir()) == [
        "DE_VAR_T.inc",
        "DH.inc",
        "DH_RESH.inc",
        "DH_VAR_T.inc",
        "INDIVUSERS_DH.inc",
        "INDIVUSERS_DH_VAR_T.inc",
        "SOLEFLH.inc",
        "SOLE_VAR_T.inc",
        "WNDFLH.inc",
        "WND_VAR_T.inc",
        "WTRRRFLH.inc",
        "WTRRRVAR_T.inc",
        "WTRRSFLH.inc",
        "WTRRSVAR_S.inc",
    ]


def test_demand_files_are_concatenated_after_the_base_default(written: Path):
    text = (written / "DE_VAR_T.inc").read_text()
    assert text.startswith("$include '../../base/data/DE_VAR_T.inc';\n")
    assert "'OTHER'" in text and "'RESE'" in text


def test_heat_profiles_include_base_and_individual_user_defaults_first(written: Path):
    lines = (written / "DH_VAR_T.inc").read_text().splitlines()
    assert lines[:2] == [
        "$include '../../base/data/DH_VAR_T.inc';",
        "$include '../../base/data/INDIVUSERS_DH_VAR_T.inc';",
    ]


def test_dh_loads_base_then_applies_weather_year_scaling(written: Path):
    assert (written / "DH.inc").read_text().splitlines() == [
        "$include '../../base/data/DH.inc';",
        "$include '../../base/data/INDIVUSERS_DH.inc';",
        "$include '../data/DH_RESH.inc';",
        "$include '../data/DH_RESIDENTIAL.inc';",
        "$include '../data/DH_TERTIARY.inc';",
    ]


def test_individual_user_overrides_are_empty_comments(written: Path):
    for name in ("INDIVUSERS_DH.inc", "INDIVUSERS_DH_VAR_T.inc"):
        assert all(line.startswith("*") for line in (written / name).read_text().splitlines())


def test_hydro_flh_scales_the_base_value(written: Path):
    rr = (written / "WTRRRFLH.inc").read_text()
    rs = (written / "WTRRSFLH.inc").read_text()
    assert rr.startswith("$onMulti\n$include '../../base/data/WTRRRFLH.inc';\n$offMulti\n")
    # Already multiplicative: left alone, not squared
    assert rr.count("WTRRRFLH('AT_A')") == 2
    assert "WTRRSFLH('AT_A') = 1.05*WTRRSFLH('AT_A');" in rs


def test_hydro_profiles_get_base_catch_all(written: Path):
    assert "= WTRRRVAR_T('NO2_A1',SSS,TTT);" in (written / "WTRRRVAR_T.inc").read_text()
    assert "=WTRRSVAR_S('SE4A',SSS);" in (written / "WTRRSVAR_S.inc").read_text()


def test_wind_gets_area_fallbacks_and_wind_catch_all(written: Path):
    text = (written / "WND_VAR_T.inc").read_text()
    assert "DK2_NoDH" not in text
    assert "WND_VAR_T('DK1_OFF_OFF_Existing_RG2',SSS,TTT)" in text
    assert "WND_VAR_T('AL_ONS_Existing_RG1',SSS,TTT)=WND_VAR_T('AL_VRE-ONS_SP199-HH150_RG1',SSS,TTT);" in text
    assert "WNDFLH('AL_ONS_Existing_RG1') = WNDFLH('AL_VRE-ONS_SP199-HH150_RG1');" in (
        written / "WNDFLH.inc"
    ).read_text()


def test_dropped_area_is_removed_from_wide_table_without_shifting_columns(written: Path):
    lines = (written / "WND_VAR_T.inc").read_text().splitlines()
    assert lines[1].split() == ["DK1_OFF_OFF_Existing_RG1", "SE4_OFF_OFF_Existing_RG1"]
    assert lines[2].split() == ["S01.T001", "0.1000", "0.3000"]
    assert lines[3].split() == ["S01.T002", "0.4000", "0.6000"]


def test_missing_source_folder_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="CapDev"):
        write_scenario_data(tmp_path / "CapDev" / "raw", tmp_path, tmp_path / "data")

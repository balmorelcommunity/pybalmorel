"""
Weather-Year Scenario Data

Turns WEATHERYEAR's CapDev output for one year into the .inc files a Balmorel
scenario's data/ folder needs. Balmorel's bb4datainc.inc only reads a
scenario's own data/<NAME>.inc when the filename matches exactly, and some
WEATHERYEAR output has a different name, is split across several files, or
holds scaling factors rather than values. Each rule below was verified against
Balmorel's override mechanism in the GREAT project
(mbrpdoc-great/scripts/preprocessing/clean_weather_year_inputs.py, its ADRs
0015, 0021, 0022, 0034 and 0036), where this logic comes from.

- Wind and solar profiles and FLH keep their names. Wind gets one fallback line
  per existing area CorRES has no profile for, and its catch-all borrows a wind
  area instead of DK2_NoDH.
- Hydro files lose WEATHERYEAR's _WY suffix. The FLH files are scaling factors,
  so the base values load first (under $onMulti) and are multiplied. The hydro
  profiles get base's catch-all for areas without a weather-year profile.
- Demand is split by user in WEATHERYEAR but read as one DE_VAR_T.inc and one
  DH_VAR_T.inc. Each loads the base default first, since the weather year only
  sets its own users' cells.
- Individual-user heat (INDIVUSERS_DH*.inc) assigns straight into DH and
  DH_VAR_T, so it is loaded inside DH.inc and DH_VAR_T.inc, and the addon's own
  override files are written empty so it isn't applied twice.
- Top-level to_balmorel/*.inc files are copied, except GKFX_renewable.inc (the
  existing fleet comes from base) and SUBTECHGROUPKPOT.inc.
- Heat-pump COP files are not written; models that use them need their own
  wrapper.

Created on 14.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import re
from pathlib import Path

#%% ------------------------------- ###
###          1. Constants           ###
### ------------------------------- ###

PASSTHROUGH_FILES = ["WND_VAR_T.inc", "SOLE_VAR_T.inc", "WNDFLH.inc", "SOLEFLH.inc"]

RENAME_FILES = {
    "WTRRSVAR_S_WY.inc": "WTRRSVAR_S.inc",
    "WTRRRVAR_T_WY.inc": "WTRRRVAR_T.inc",
    "WTRRSFLH_WY.inc": "WTRRSFLH.inc",
    "WTRRRFLH_WY.inc": "WTRRRFLH.inc",
}

CONCAT_FILES = {
    "DE_VAR_T.inc": ["DE_VAR_T_OTHER.inc", "DE_VAR_T_RESE.inc"],
    "DH_VAR_T.inc": ["DH_VAR_T_RESIDENTIAL.inc", "DH_VAR_T_RESH.inc", "DH_VAR_T_TERTIARY.inc"],
}

FLH_FACTOR_FILES = {"WTRRRFLH.inc", "WTRRSFLH.inc"}

# TABLE files with areas as columns: a dropped area must be cut out of every row
WIDE_TABLE_FILES = {"WND_VAR_T.inc", "SOLE_VAR_T.inc"}

STATIC_FILE_EXCLUDE = {"SUBTECHGROUPKPOT.inc", "GKFX_renewable.inc"}

# Existing wind areas CorRES' Existing_ERA5_GWA2 run has no profile for
WIND_AREA_FALLBACKS = {
    "AL_ONS_Existing_RG1": "AL_VRE-ONS_SP199-HH150_RG1",
    "DE4-N_OFF_OFF_Existing_RG2": "DE4-N_OFF_VRE-OFF_bottom_fixed_SP316-HH155_RG2",
    "IT_OFF1_OFF_Existing_RG2": "IT_OFF1_VRE-OFF_bottom_fixed_SP316-HH155_RG2",
    "NO3_OFF_OFF_Existing_RG2": "NO3_OFF_VRE-OFF_bottom_fixed_SP316-HH155_RG2",
}

_WND_CATCHALL_FROM = "WND_VAR_T('DK2_NoDH',SSS,TTT)"
_WND_CATCHALL_TO = "WND_VAR_T('DK1_OFF_OFF_Existing_RG2',SSS,TTT)"

HYDRO_PROFILE_FALLBACKS = {
    "WTRRRVAR_T.inc": (
        "WTRRRVAR_T(IA,SSS,TTT)$((NOT SUM((S,T),WTRRRVAR_T(IA,S,T))) AND WTRRRFLH(IA))"
        " = WTRRRVAR_T('NO2_A1',SSS,TTT);\n"
    ),
    "WTRRSVAR_S.inc": (
        "WTRRSVAR_S(AAA,SSS)$((WTRRSVAR_S(AAA,SSS) =0) and (WTRRSFLH(AAA) GE 1))"
        "=WTRRSVAR_S('SE4A',SSS);\n"
    ),
}

_INDIVUSERS_EMPTY = (
    "* Deliberately empty: DH.inc and DH_VAR_T.inc already load base's\n"
    "* individual-user heat data, so the indivusers addon must not apply it again.\n"
)

_RG_OFF_TO_BARE = {"RG1_OFF": "RG1", "RG2_OFF": "RG2", "RG3_OFF": "RG3"}

_FLH_ASSIGNMENT = re.compile(
    r"^(?P<param>WTRRRFLH|WTRRSFLH)\((?P<idx>'[^']+')\)\s*=\s*(?P<val>[^;]+);",
    re.MULTILINE,
)

#%% ------------------------------- ###
###          2. Functions           ###
### ------------------------------- ###


def _drop_area_lines(text: str, drop_areas: tuple[str, ...]) -> str:
    """Drop every line naming a dropped area, for files with one area per line."""
    return "".join(
        line for line in text.splitlines(keepends=True) if not any(area in line for area in drop_areas)
    )


def _drop_wide_table_columns(text: str, drop_areas: tuple[str, ...]) -> str:
    """Cut dropped areas' columns out of a TABLE header and every data row.

    The exact character span is removed, because re-joining a GAMS TABLE row
    with normalised whitespace breaks its column alignment.
    """
    lines = text.splitlines(keepends=True)
    header_idx = next(
        (i for i, line in enumerate(lines) if any(area in line for area in drop_areas)), None
    )
    if header_idx is None:
        return text
    header_matches = list(re.finditer(r"\S+", lines[header_idx]))
    drop_positions = [
        i for i, match in enumerate(header_matches) if any(area in match.group() for area in drop_areas)
    ]

    def _splice(line: str, matches: list, positions: list) -> str:
        spans = [(matches[pos - 1].end() if pos > 0 else 0, matches[pos].end()) for pos in positions]
        for start, end in sorted(spans, reverse=True):
            line = line[:start] + line[end:]
        return line

    lines[header_idx] = _splice(lines[header_idx], header_matches, drop_positions)
    for i in range(header_idx + 1, len(lines)):
        if lines[i].strip() == ";":
            break
        row_matches = list(re.finditer(r"\S+", lines[i]))
        # Row token 0 is the S.T label, so values are shifted by one
        if len(row_matches) == len(header_matches) + 1:
            lines[i] = _splice(lines[i], row_matches, [pos + 1 for pos in drop_positions])
    return "".join(lines)


def _finalize(text: str, filename: str, drop_areas: tuple[str, ...]) -> str:
    """Drop excluded areas and normalise offshore resource-grade labels."""
    if drop_areas:
        if filename in WIDE_TABLE_FILES:
            text = _drop_wide_table_columns(text, drop_areas)
        else:
            text = _drop_area_lines(text, drop_areas)
    for off, bare in _RG_OFF_TO_BARE.items():
        text = text.replace(off, bare)
    return text


def _make_flh_multiplicative(text: str) -> str:
    """Rewrite FLH factors as scalings of the loaded value; leave ones that already are."""

    def _sub(match: re.Match) -> str:
        param, idx, val = match.group("param"), match.group("idx"), match.group("val")
        if re.search(rf"\b{param}\s*\(\s*{re.escape(idx)}\s*\)", val):
            return match.group(0)
        return f"{param}({idx}) = {val}*{param}({idx});"

    return _FLH_ASSIGNMENT.sub(_sub, text)


def _append(text: str, extra: str) -> str:
    if extra and not text.endswith("\n"):
        text += "\n"
    return text + extra


def write_scenario_data(
    capdev_dir: str | Path,
    to_balmorel_dir: str | Path,
    dest_dir: str | Path,
    base_data_dir: str = "../../base/data",
    drop_areas: tuple[str, ...] = (),
) -> list[Path]:
    """Write one weather year's Balmorel scenario data files.

    Args:
        capdev_dir (str | Path): A CapDev variant folder from WEATHERYEAR, e.g.
            '<output>/<year>/to_balmorel/CapDev/raw' for the actual weather.
        to_balmorel_dir (str | Path): The '<output>/<year>/to_balmorel' folder,
            whose top-level .inc files are copied too.
        dest_dir (str | Path): The scenario's data/ folder. Created if needed;
            existing files with the same names are overwritten.
        base_data_dir (str, optional): GAMS path, relative to the scenario's
            model/ folder, of the base data the weather year is applied on top
            of. Defaults to '../../base/data'.
        drop_areas (tuple[str, ...], optional): Areas the model doesn't have,
            removed wherever they appear (matched as substrings). Defaults to ().

    Raises:
        FileNotFoundError: If capdev_dir doesn't exist.

    Returns:
        list[Path]: The files written.
    """
    capdev_dir, to_balmorel_dir, dest_dir = Path(capdev_dir), Path(to_balmorel_dir), Path(dest_dir)
    if not capdev_dir.is_dir():
        raise FileNotFoundError(f"WEATHERYEAR CapDev output not found at '{capdev_dir}'")
    dest_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    for filename in PASSTHROUGH_FILES:
        source = capdev_dir / filename
        if not source.exists():
            continue
        text = _finalize(source.read_text(), filename, drop_areas).replace(_WND_CATCHALL_FROM, _WND_CATCHALL_TO)
        if filename == "WNDFLH.inc":
            text = _append(text, "".join(
                f"WNDFLH('{target}') = WNDFLH('{origin}');\n" for target, origin in WIND_AREA_FALLBACKS.items()
            ))
        elif filename == "WND_VAR_T.inc":
            text = _append(text, "".join(
                f"WND_VAR_T('{target}',SSS,TTT)=WND_VAR_T('{origin}',SSS,TTT);\n"
                for target, origin in WIND_AREA_FALLBACKS.items()
            ))
        outputs[filename] = text

    for source_name, dest_name in RENAME_FILES.items():
        source = capdev_dir / source_name
        if not source.exists():
            continue
        text = _finalize(source.read_text(), dest_name, drop_areas)
        if dest_name in FLH_FACTOR_FILES:
            param = dest_name.removesuffix(".inc")
            text = (
                f"$onMulti\n$include '{base_data_dir}/{param}.inc';\n$offMulti\n"
                + _make_flh_multiplicative(text)
            )
        outputs[dest_name] = _append(text, HYDRO_PROFILE_FALLBACKS.get(dest_name, ""))

    base_includes = {
        "DE_VAR_T.inc": f"$include '{base_data_dir}/DE_VAR_T.inc';\n",
        "DH_VAR_T.inc": (
            f"$include '{base_data_dir}/DH_VAR_T.inc';\n"
            f"$include '{base_data_dir}/INDIVUSERS_DH_VAR_T.inc';\n"
        ),
    }
    for dest_name, source_names in CONCAT_FILES.items():
        sources = [capdev_dir / name for name in source_names]
        if all(source.exists() for source in sources):
            text = "".join(source.read_text() for source in sources)
            outputs[dest_name] = base_includes[dest_name] + _finalize(text, dest_name, drop_areas)

    for source in sorted(to_balmorel_dir.glob("*.inc")):
        if source.name not in STATIC_FILE_EXCLUDE:
            outputs[source.name] = _finalize(source.read_text(), source.name, drop_areas)

    outputs["DH.inc"] = (
        f"$include '{base_data_dir}/DH.inc';\n"
        f"$include '{base_data_dir}/INDIVUSERS_DH.inc';\n"
        "$include '../data/DH_RESH.inc';\n"
        "$include '../data/DH_RESIDENTIAL.inc';\n"
        "$include '../data/DH_TERTIARY.inc';\n"
    )
    outputs["INDIVUSERS_DH.inc"] = _INDIVUSERS_EMPTY
    outputs["INDIVUSERS_DH_VAR_T.inc"] = _INDIVUSERS_EMPTY

    for name, text in outputs.items():
        (dest_dir / name).write_text(text)
    return [dest_dir / name for name in outputs]

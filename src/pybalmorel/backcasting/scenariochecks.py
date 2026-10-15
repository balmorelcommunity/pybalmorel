"""
Scenario Checks

Read-only checks that a Balmorel backcast scenario will actually use the
inputs pybalmorel generates for it. Nothing here edits the scenario - it
only warns (see docs/adr/0006: pybalmorel writes data files, never options).

Created on 15.10.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import re
from pathlib import Path

# ------------------------------- #
#          1. Functions           #
# ------------------------------- #


def resolve_scenario_file(
    balmorel_scenario_path: str | Path, folder: str, file_name: str
) -> Path | None:
    """The file Balmorel reads for a scenario: its own copy, else the base one.

    Args:
        balmorel_scenario_path (str | Path): The scenario folder (e.g. .../backcast).
        folder (str): 'model' or 'data'.
        file_name (str): e.g. 'balopt.opt'.

    Returns:
        Path | None: The resolved file, or None if neither exists.
    """
    balmorel_scenario_path = Path(balmorel_scenario_path)
    for candidate in [
        balmorel_scenario_path / folder / file_name,
        balmorel_scenario_path.parent / "base" / folder / file_name,
    ]:
        if candidate.exists():
            return candidate
    return None


def read_setglobal(balopt_path: str | Path, option: str) -> str | None:
    """The value the last `$setglobal <option>` line in a balopt file sets.

    Args:
        balopt_path (str | Path): Path to balopt.opt.
        option (str): The global name, e.g. 'FUELPRICE_DOL'.

    Returns:
        str | None: The value, or None if the option is never set.
    """
    pattern = re.compile(rf"^\s*\$setglobal\s+{option}\s+(\S+)", re.IGNORECASE)
    value = None
    for line in Path(balopt_path).read_text(errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            value = match.group(1)
    return value


def check_balopt_option(
    balmorel_scenario_path: str | Path, option: str, expected: str
) -> bool:
    """Warn if the scenario's balopt.opt doesn't set `option` to `expected`.

    Args:
        balmorel_scenario_path (str | Path): The scenario folder.
        option (str): The global name, e.g. 'TAX_CO2_DOL'.
        expected (str): The required value, e.g. 'YYY_CCC_SSS_TTT'.

    Returns:
        bool: True if the option is set as expected.
    """
    balopt_path = resolve_scenario_file(balmorel_scenario_path, "model", "balopt.opt")
    if balopt_path is None:
        print(
            f"Warning: no balopt.opt found for {balmorel_scenario_path} - "
            f"make sure {option}={expected} is set, or the generated file is ignored."
        )
        return False

    value = read_setglobal(balopt_path, option)
    if value is None or value.upper() != expected.upper():
        print(
            f"Warning: {balopt_path} sets {option}={value or '<unset, model default>'}, "
            f"but the generated file needs {option}={expected} - set it, or "
            "Balmorel silently ignores the generated prices."
        )
        return False

    return True


def check_hardcoded_fuelprices(
    balmorel_scenario_path: str | Path,
    fuels: list[str],
    file_name: str = "HYDROGEN_FUELPRICE.inc",
) -> list[str]:
    """Warn about uncommented lines in an include file that name any of `fuels`.

    HYDROGEN_FUELPRICE.inc assigns FUELPRICE_HYDROGEN, which overrides
    IFUELPRICE wherever it is nonzero - a hardcoded COAL or NATGAS price there
    silently replaces the generated FUELPRICE.inc.

    Args:
        balmorel_scenario_path (str | Path): The scenario folder.
        fuels (list[str]): FFF fuel names to look for, e.g. ['NATGAS', 'COAL'].
        file_name (str, optional): The include to check. Defaults to 'HYDROGEN_FUELPRICE.inc'.

    Returns:
        list[str]: The offending lines (stripped).
    """
    inc_path = resolve_scenario_file(balmorel_scenario_path, "data", file_name)
    if inc_path is None:
        return []

    fuel_pattern = re.compile(r"'(" + "|".join(map(re.escape, fuels)) + r")'")
    in_ontext = False
    offending = []
    for line in inc_path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("$ontext"):
            in_ontext = True
        elif stripped.lower().startswith("$offtext"):
            in_ontext = False
        elif not in_ontext and not stripped.startswith("*") and fuel_pattern.search(stripped):
            offending.append(stripped)

    if offending:
        print(
            f"Warning: {inc_path} assigns prices for {fuels} - these override "
            "the generated FUELPRICE.inc. Remove them for a backcast:\n  "
            + "\n  ".join(offending)
        )

    return offending

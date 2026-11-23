"""
Update the IAMC Definitions Snapshot

Downloads one commit of github.com/IAMconsortium/common-definitions, reads it
with nomenclature-iamc (which expands the {Tag} placeholders), and writes the
snapshot pybalmorel.iamc converts against, to src/pybalmorel/iamc/definitions/:

- variables.csv: variable, unit, description, tier. Where a variable allows
  several units, the first.
- regions.csv: region, iso3. Countries only, one per ISO3 code: nomenclature's
  country list (what projects reporting by country switch on with
  `country: true`), plus country codes the repository defines for ISO3 codes
  the list lacks.
- SOURCE: the repository, commit, commit date and nomenclature-iamc version.

Run it in the pixi environment that has nomenclature-iamc (needs network):

    pixi run update-iamc-definitions               # the newest commit on main
    pixi run update-iamc-definitions --ref <sha>   # a given commit or branch

Then review `git diff src/pybalmorel/iamc/definitions/` and run
`pytest tests/test_iamc.py`, which lists the rule rows that target names the
new snapshot lacks.

Created on 23.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import argparse
import datetime
import importlib.metadata
import json
import tarfile
import tempfile
import urllib.request
from pathlib import Path
import pandas as pd
import nomenclature
from nomenclature import DataStructureDefinition

repository = "IAMconsortium/common-definitions"
output_dir = Path(__file__).resolve().parents[1] / "src" / "pybalmorel" / "iamc" / "definitions"
user_agent = "pybalmorel-update-iamc-definitions"


#%% ------------------------------- ###
###          1. Download            ###
### ------------------------------- ###

def resolve_commit(ref: str) -> tuple[str, str]:
    """Find the commit a branch, tag or commit hash points to.

    Args:
        ref (str): A branch, tag or (abbreviated) commit hash of common-definitions.

    Returns:
        tuple[str, str]: The full commit hash, and the commit date (ISO 8601).
    """
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/commits/{ref}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": user_agent},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        commit = json.load(response)
    return commit["sha"], commit["commit"]["committer"]["date"]


def download(sha: str, folder: Path) -> Path:
    """Download and unpack common-definitions at one commit.

    Args:
        sha (str): The full commit hash.
        folder (Path): An empty folder to unpack into.

    Returns:
        Path: The root of the unpacked repository.
    """
    request = urllib.request.Request(
        f"https://codeload.github.com/{repository}/tar.gz/{sha}", headers={"User-Agent": user_agent}
    )
    archive = folder / "common-definitions.tar.gz"
    with urllib.request.urlopen(request, timeout=300) as response:
        archive.write_bytes(response.read())

    unpacked = folder / "repository"
    with tarfile.open(archive) as tar:
        tar.extractall(unpacked, filter="data")
    roots = list(unpacked.iterdir())
    if len(roots) != 1:
        raise Exception(f"Expected one folder in the archive of {sha}, found {[root.name for root in roots]}.")
    return roots[0]


#%% ------------------------------- ###
###        2. Read Definitions      ###
### ------------------------------- ###

def read_variables(definitions: DataStructureDefinition) -> pd.DataFrame:
    """List the IAMC Variables with their unit, description and tier.

    Args:
        definitions (DataStructureDefinition): The common definitions, read by nomenclature.

    Returns:
        pd.DataFrame: One row per variable, sorted by name.
    """
    rows = []
    for code in definitions.variable.values():
        unit = code.unit
        if isinstance(unit, list):
            unit = unit[0] if unit else ""
        rows.append({
            "variable": code.name,
            "unit": unit or "",
            "description": " ".join(str(code.description or "").split()),
            "tier": getattr(code, "tier", None) or "",
        })
    return pd.DataFrame(rows).sort_values("variable", ignore_index=True)


def read_regions(definitions: DataStructureDefinition) -> pd.DataFrame:
    """List the country IAMC Regions with their ISO3 codes, one per code.

    common-definitions defines no countries itself: projects that report by country get them
    from nomenclature's country list (`country: true` in their nomenclature.yaml), so its names
    come first. Country codes the repository defines (a hierarchy naming countries, one ISO3
    code) are added for ISO3 codes the list lacks.

    Args:
        definitions (DataStructureDefinition): The common definitions, read by nomenclature.

    Returns:
        pd.DataFrame: One row per ISO3 code, with the columns 'region' and 'iso3', sorted by name.
    """
    region_by_iso3 = {country.alpha_3: country.name for country in nomenclature.countries}
    for code in definitions.region.values():
        iso3 = getattr(code, "iso3_codes", None)
        if isinstance(iso3, list):
            iso3 = iso3[0] if len(iso3) == 1 else None
        if iso3 and "countr" in str(code.hierarchy or "").lower() and iso3 not in region_by_iso3:
            region_by_iso3[str(iso3)] = code.name

    regions = pd.DataFrame({"region": list(region_by_iso3.values()), "iso3": list(region_by_iso3)})
    return regions.sort_values("region", ignore_index=True)


def report_changes(old_file: Path, variables: pd.DataFrame) -> None:
    """Print which variables the new snapshot adds and drops compared to the old one."""
    if not old_file.exists():
        return
    old = set(pd.read_csv(old_file, dtype=str, keep_default_na=False)["variable"])
    new = set(variables["variable"])
    added, dropped = sorted(new - old), sorted(old - new)
    print(f"{len(added)} variables added, {len(dropped)} dropped.")
    for name in dropped[:50]:
        print(f"  dropped: {name}")
    if len(dropped) > 50:
        print(f"  ... and {len(dropped) - 50} more")


#%% ------------------------------- ###
###              3. Main            ###
### ------------------------------- ###

def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate pybalmorel's IAMC Definitions Snapshot.")
    parser.add_argument("--ref", default="main", help="Branch, tag or commit of common-definitions (default: main).")
    parser.add_argument("--output", type=Path, default=output_dir, help=f"Snapshot folder (default: {output_dir}).")
    arguments = parser.parse_args()

    sha, date = resolve_commit(arguments.ref)
    print(f"common-definitions at {arguments.ref}: {sha} ({date})")

    with tempfile.TemporaryDirectory() as folder:
        root = download(sha, Path(folder))
        definitions = DataStructureDefinition(root / "definitions", dimensions=["region", "variable"])
        variables = read_variables(definitions)
        regions = read_regions(definitions)

    arguments.output.mkdir(parents=True, exist_ok=True)
    report_changes(arguments.output / "variables.csv", variables)
    variables.to_csv(arguments.output / "variables.csv", index=False, lineterminator="\n")
    regions.to_csv(arguments.output / "regions.csv", index=False, lineterminator="\n")
    (arguments.output / "SOURCE").write_text(
        f"repository: https://github.com/{repository}\n"
        f"commit: {sha}\n"
        f"commit date: {date}\n"
        f"nomenclature-iamc: {importlib.metadata.version('nomenclature-iamc')}\n"
        f"generated: {datetime.date.today().isoformat()}\n"
    )
    print(f"Wrote {len(variables)} variables and {len(regions)} country regions to {arguments.output}")


if __name__ == "__main__":
    main()

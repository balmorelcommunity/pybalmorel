"""
Transmission Outages

Download and parse ENTSO-E's transmission outage reports: document type A78,
"Unavailability of transmission infrastructure" (Transparency Platform
articles 10.1.A planned and 10.1.B forced). Each report gives, per direction
of a border, the capacity (MW) that one or more assets leave in service while
they are out.

pybalmorel has its own client for these, because entsoe-py 0.8.1's
query_unavailability_transmission reads only the first 200 documents of a
query (it pages by period, not by offset) and drops each report's asset name
and type. A border can have well over 200 reports in a year (DE_LU-NO2: 1,699
in 2023), and the asset names are what tells a report on a whole border from
one on a single line of it.

Created on 16.11.2026
@author: Mathias Berg Rosendal
         PostDoc at DTU Management (Energy Economics & Modelling)
"""
# ------------------------------- #
#        0. Script Settings       #
# ------------------------------- #

import io
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from warnings import warn

import pandas as pd
import requests
from entsoe.exceptions import NoMatchingDataError

from . import (
    get_full_year,
    no_data_file,
    read_no_data_pairs,
    transmission_files,
    zone_eic_code,
)

API_URL = "https://web-api.tp.entsoe.eu/api"

# The query name in the downloaded files' names
TRANSMISSION_OUTAGES = "unavailability_of_transmission"

# The API returns at most this many documents per request, and pages by offset up to MAX_OFFSET
PAGE_SIZE = 200
MAX_OFFSET = 4800

# HTTP statuses worth retrying: rate limited, and server errors (ENTSO-E also answers 599 on timeouts)
RETRY_STATUSES = (429, 500, 502, 503, 504, 599)

# Document statuses; an active document carries none
DOCSTATUS = {
    "A01": "Intermediate",
    "A02": "Final",
    "A05": "Active",
    "A09": "Cancelled",
    "A13": "Withdrawn",
    "X01": "Estimated",
}
BUSINESSTYPE = {"A53": "Planned maintenance", "A54": "Unplanned outage"}
PSRTYPE = {"B21": "AC Link", "B22": "DC Link", "B23": "Substation", "B24": "Transformer"}

# One row per period of a report's time series; start, end and avail_qty are
# empty for a time series without periods (e.g. borders that report their
# capacity as part of flow-based market coupling)
COLUMNS = [
    "mrid",
    "revision",
    "docstatus",
    "businesstype",
    "out_domain",
    "in_domain",
    "asset_mrid",
    "asset_name",
    "asset_psrtype",
    "unit",
    "start",
    "end",
    "avail_qty",
    "reason",
]

# ------------------------------- #
#           1. Parsing            #
# ------------------------------- #


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _text(element: ET.Element | None, path: str) -> str | None:
    for part in path.split("/"):
        if element is None:
            return None
        element = next(iter(_children(element, part)), None)
    return None if element is None else (element.text or "").strip()


def parse_transmission_outage_document(xml: bytes) -> list[dict]:
    """The rows of one A78 Unavailability_MarketDocument.

    A period's points hold from their position until the next point's, the
    last until the period ends. Several assets of one time series are joined
    with '|'.

    Args:
        xml (bytes): The document.

    Returns:
        list[dict]: One dict per period point, with the keys of COLUMNS.
    """
    root = ET.fromstring(xml)
    docstatus = _text(root, "docStatus/value")
    document = {
        "mrid": _text(root, "mRID"),
        "revision": int(_text(root, "revisionNumber") or 0),
        "docstatus": DOCSTATUS.get(docstatus, docstatus) if docstatus else "Active",
        "reason": "; ".join(
            filter(None, (_text(reason, "text") for reason in _children(root, "Reason")))
        ),
    }

    rows = []
    for series in _children(root, "TimeSeries"):
        assets = _children(series, "Asset_RegisteredResource")
        businesstype = _text(series, "businessType")
        psrtypes = (_text(asset, "asset_PSRType.psrType") or "" for asset in assets)
        series_info = {
            **document,
            "businesstype": BUSINESSTYPE.get(businesstype or "", businesstype),
            "out_domain": _text(series, "out_Domain.mRID"),
            "in_domain": _text(series, "in_Domain.mRID"),
            "asset_mrid": "|".join(_text(asset, "mRID") or "" for asset in assets),
            "asset_name": "|".join(_text(asset, "name") or "" for asset in assets),
            "asset_psrtype": "|".join(PSRTYPE.get(psrtype, psrtype) for psrtype in psrtypes),
            "unit": _text(series, "quantity_Measure_Unit.name"),
        }
        periods = _children(series, "Available_Period")
        if not periods:
            rows.append({**series_info, "start": None, "end": None, "avail_qty": None})
        for period in periods:
            period_start = pd.Timestamp(_text(period, "timeInterval/start"))
            period_end = pd.Timestamp(_text(period, "timeInterval/end"))
            resolution = pd.Timedelta(_text(period, "resolution"))
            points = sorted(
                (int(_text(point, "position") or 0), float(_text(point, "quantity") or "nan"))
                for point in _children(period, "Point")
            )
            for index, (position, quantity) in enumerate(points):
                end = (
                    period_start + resolution * (points[index + 1][0] - 1)
                    if index + 1 < len(points)
                    else period_end
                )
                rows.append(
                    {
                        **series_info,
                        "start": period_start + resolution * (position - 1),
                        "end": end,
                        "avail_qty": quantity,
                    }
                )

    return rows


def parse_transmission_outage_response(content: bytes) -> tuple[list[dict], int]:
    """The rows and the number of documents in one API response: a zip of documents or a single one.

    Args:
        content (bytes): The response body.

    Returns:
        tuple[list[dict], int]: The rows of every document, and the document count.
    """
    if content[:2] != b"PK":
        return parse_transmission_outage_document(content), 1

    rows, documents = [], 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.filename.endswith(".xml"):
                rows += parse_transmission_outage_document(archive.read(info))
                documents += 1
    return rows, documents


# ------------------------------- #
#           2. Requests           #
# ------------------------------- #


def _get(params: dict, timeout: int, retries: int) -> requests.Response:
    """GET from the API, retrying timeouts, rate limits and server errors with a growing wait."""
    for attempt in range(retries + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=timeout)
        except requests.exceptions.RequestException:
            if attempt == retries:
                raise
        else:
            if response.status_code not in RETRY_STATUSES or attempt == retries:
                return response
        time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def _acknowledgement_text(text: str) -> str:
    """The reason text of an API Acknowledgement_MarketDocument, or the start of the body."""
    try:
        reasons = _children(ET.fromstring(text), "Reason")
    except ET.ParseError:
        return text[:300]
    return "; ".join(filter(None, (_text(reason, "text") for reason in reasons))) or text[:300]


def query_transmission_outages(
    zone_from: str,
    zone_to: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    api_key: str,
    timeout: int = 180,
    retries: int = 4,
) -> pd.DataFrame:
    """Every transmission outage report for one direction of a border that overlaps [start, end).

    Pages through the reports PAGE_SIZE at a time. Withdrawn reports are left
    out by the API; cancelled ones are not.

    Args:
        zone_from (str): The zone the direction starts in, in any spelling (see zone_eic_code).
        zone_to (str): The zone it ends in.
        start (pd.Timestamp): Timezone-aware start of the window.
        end (pd.Timestamp): Timezone-aware end; at most a year after start.
        api_key (str): ENTSO-E transparency platform API key.
        timeout (int, optional): Seconds to wait for one response. Defaults to 180.
        retries (int, optional): Retries of a request that timed out or met a
            server error. Defaults to 4.

    Raises:
        NoMatchingDataError: If there are no reports.
        requests.exceptions.RequestException: If a request fails after its retries.

    Returns:
        pd.DataFrame: The reports, with COLUMNS.
    """
    params = {
        "securityToken": api_key,
        "documentType": "A78",
        "out_Domain": zone_eic_code(zone_from),
        "in_Domain": zone_eic_code(zone_to),
        "periodStart": start.tz_convert("UTC").strftime("%Y%m%d%H%M"),
        "periodEnd": end.tz_convert("UTC").strftime("%Y%m%d%H%M"),
    }

    rows, documents = [], 0
    for offset in range(0, MAX_OFFSET + 1, PAGE_SIZE):
        response = _get({**params, "offset": offset}, timeout, retries)
        if response.content[:2] == b"PK" or b"Unavailability_MarketDocument" in response.content[:500]:
            page_rows, page_documents = parse_transmission_outage_response(response.content)
            rows += page_rows
            documents += page_documents
            if page_documents < PAGE_SIZE:
                break
            if offset == MAX_OFFSET:
                warn(
                    f"{zone_from}-{zone_to} has more than {MAX_OFFSET + PAGE_SIZE} outage reports, "
                    "the API's limit, so the rest are missing. Query shorter windows."
                )
            continue

        text = _acknowledgement_text(response.text)
        if "No matching data found" in text:
            break
        raise requests.exceptions.HTTPError(
            f"HTTP {response.status_code} for {zone_from}-{zone_to}: {text}", response=response
        )

    if not documents:
        raise NoMatchingDataError
    return pd.DataFrame(rows, columns=COLUMNS)


def fetch_annual_transmission_outages(
    from_to_list: list[tuple[str, str]],
    year: int,
    path: str | Path,
    api_key: str,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    timeout: int = 180,
) -> None:
    """Download the transmission outage reports of every pair into '<year>_<from>-<to>_<TRANSMISSION_OUTAGES>.csv'.

    Like fetch_annual_transmission_data: pairs already downloaded, under any
    spelling, and pairs ENTSO-E had no reports for on an earlier run are
    skipped, and a failed request doesn't stop the loop, so rerun to retry.

    Args:
        from_to_list (list[tuple[str, str]]): Directed pairs of zones, e.g. neighbour_pairs(bidding_zones).
        year (int): The year in the file names.
        path (str | Path): The folder to save to.
        api_key (str): ENTSO-E transparency platform API key.
        start (pd.Timestamp | None, optional): Start of the window. Defaults
            to the start of `year` in Brussels time.
        end (pd.Timestamp | None, optional): End of the window, at most a year
            after start. Defaults to the end of `year` in Brussels time.
        timeout (int, optional): Seconds to wait for one response. Defaults to 180.
    """
    year_start, year_end = get_full_year(year)
    start = year_start if start is None else start
    end = year_end if end is None else end
    p = Path(path)
    fetched = set(transmission_files(p, year, TRANSMISSION_OUTAGES))
    no_data = read_no_data_pairs(p, year, TRANSMISSION_OUTAGES)
    for zone_from, zone_to in from_to_list:
        eic_pair = (zone_eic_code(zone_from), zone_eic_code(zone_to))
        if eic_pair in fetched or eic_pair in no_data:
            continue
        try:
            reports = query_transmission_outages(
                zone_from, zone_to, start, end, api_key, timeout=timeout
            )
        except NoMatchingDataError:
            print(f"No transmission outage reports for {zone_from}-{zone_to}")
            with open(no_data_file(p, year, TRANSMISSION_OUTAGES), "a") as f:
                f.write("\t".join(eic_pair) + "\n")
            continue
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {zone_from}-{zone_to}, rerun to retry")
            print(e)
            continue

        reports.to_csv(p / f"{year}_{zone_from}-{zone_to}_{TRANSMISSION_OUTAGES}.csv", index=False)
        print(f"{zone_from}-{zone_to}: {reports['mrid'].nunique()} outage reports")

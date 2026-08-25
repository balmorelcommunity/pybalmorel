"""
Testing of utils.py

Created on 03.10.2024
@author: Mathias Berg Rosendal, PhD Student at DTU Management (Energy Economics & Modelling)
"""
# %% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from pybalmorel.utils import (
    symbol_to_df,
    create_parameter_columns,
    create_set_columns,
    create_variable_columns,
    preformatted_columns,
)
import pandas as pd
import gams
import math
import os
import pytest

# ------------------------------- #
#             1. Utils            #
# ------------------------------- #

gams_system_directory = os.environ.get("GAMS_SYSTEM_DIR", None)
assert gams_system_directory is not None, (
    "GAMS system directory not found. "
    "Set GAMS_SYSTEM_DIR in the pyproject.toml file to point at your GAMS installation, e.g.:\n"
    "  GAMS_SYSTEM_DIR=/opt/gams/53"
)


def test_symbol_to_df_mainresults():
    ws = gams.GamsWorkspace(system_directory=gams_system_directory)
    db = ws.add_database_from_gdx(
        os.path.abspath("examples/files/MainResults_Example1.gdx")
    )

    f = symbol_to_df(db, "EL_PRICE_YCRST")
    assert type(f) == pd.DataFrame


# test_symbol_to_df_optiflow()


def test_symbol_to_df_all_endofmodel():
    ws = gams.GamsWorkspace(system_directory=gams_system_directory)
    db = ws.add_database_from_gdx(os.path.abspath("examples/files/all_endofmodel.gdx"))

    # A parameter
    f = symbol_to_df(db, "DE")
    print(f)
    assert type(f) == pd.DataFrame

    # A set
    f = symbol_to_df(db, "AAA")
    print(f)
    assert type(f) == pd.DataFrame


# ------------------------------- #
#   2. Characterization: parity   #
#      with pre-vectorization     #
#      per-record implementation  #
# ------------------------------- #


def _symbol_to_df_loop_reference(
    db: gams.GamsDatabase,
    symbol: str,
    cols: list | None = None,
    result_type: str = "balmorel",
    print_explanatory_text: bool = False,
):
    """
    The original per-record-loop implementation of symbol_to_df, kept here
    only as a correctness oracle for test_symbol_to_df_matches_loop_reference.
    Not used anywhere else; do not import this outside of this test module.
    """
    if not db[symbol].get_number_records() == 0:
        if type(db[symbol]) == gams.GamsParameter:
            df = dict((tuple(rec.keys), rec.value) for rec in db[symbol])
            df = pd.DataFrame(df, index=["Value"]).T.reset_index()
            df = create_parameter_columns(
                df, db, symbol, preformatted_columns[result_type.lower()], cols
            )
        elif type(db[symbol]) == gams.GamsSet:
            df = pd.DataFrame([tuple(rec.keys) for rec in db[symbol]])
            df = create_set_columns(
                df, db, symbol, preformatted_columns[result_type.lower()], cols
            )
        elif (
            type(db[symbol]) == gams.GamsVariable
            or type(db[symbol]) == gams.GamsEquation
        ):
            df = dict((tuple(rec.keys), rec.level) for rec in db[symbol])
            df = pd.DataFrame(
                df, index=["Value", "Marginal", "Lower", "Upper", "Scale"]
            ).T.reset_index()
            df = create_variable_columns(
                df, db, symbol, preformatted_columns[result_type.lower()], cols
            )
        else:
            raise TypeError(
                "%s is not supported by symbol_to_df" % (str(type(db[symbol])))
            )
    else:
        df = pd.DataFrame()

    return df


_PARITY_GDX_FILES = [
    "examples/files/MainResults_Example1.gdx",
    "examples/files/MainResults_Example3.gdx",
    "examples/files/all_endofmodel.gdx",
]


def _iter_symbol_names(db: gams.GamsDatabase):
    supported = (gams.GamsParameter, gams.GamsSet, gams.GamsVariable, gams.GamsEquation)
    for rec in db:
        if isinstance(rec, supported):
            yield rec.name


def _raw_level_attrs(db: gams.GamsDatabase, symbol: str):
    """rec.keys -> (level, marginal, lower, upper, scale), read directly off the GDX record."""
    return {
        tuple(rec.keys): (rec.level, rec.marginal, rec.lower, rec.upper, rec.scale)
        for rec in db[symbol]
    }


def _raw_values(db: gams.GamsDatabase, symbol: str):
    """rec.keys -> value, read directly off the GDX record."""
    return {tuple(rec.keys): rec.value for rec in db[symbol]}


def _floats_equal(a: float, b: float) -> bool:
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


@pytest.mark.parametrize("gdx_path", _PARITY_GDX_FILES)
def test_symbol_to_df_matches_loop_reference(gdx_path):
    """
    Guards the gams.transfer-based vectorized symbol_to_df against the
    original per-record-loop implementation, across every Parameter/Set/
    Variable/Equation symbol in each example gdx file.

    Two known bugs in the old loop-based implementation are deliberately
    NOT reproduced, and are checked against raw GDX records instead:
      - 0-domain (scalar) symbols crash the old implementation outright
        (the dict->DataFrame->transpose trick doesn't collapse for a
        single empty-tuple key), so there's no reference output to diff.
      - Marginal/Lower/Upper/Scale for Variables/Equations were always
        broadcast copies of Value in the old implementation (it only ever
        read rec.level into the dict), so they're not a valid oracle for
        those four columns.

    A third, unrelated pre-existing bug also surfaces here: some symbols
    (e.g. EL_PRICE_YCR in MainResults_Example3.gdx) have a stale column
    mapping in formatting.py that doesn't match the actual domain count in
    the gdx. Because create_parameter_columns/create_set_columns/
    create_variable_columns are shared, unmodified helpers, this raises a
    ValueError for BOTH the old and new implementation identically -- that's
    a formatting.py data-mapping issue, not a symbol_to_df extraction issue,
    so it's out of scope for this refactor. The test only requires that when
    one implementation raises, the other raises too (any exception cause);
    it never asserts that either succeeds.
    """
    ws = gams.GamsWorkspace(system_directory=gams_system_directory)
    db = ws.add_database_from_gdx(os.path.abspath(gdx_path))

    for symbol in _iter_symbol_names(db):
        gtype = type(db[symbol])

        try:
            expected = _symbol_to_df_loop_reference(db, symbol)
            reference_ok = True
        except (ValueError, KeyError):
            reference_ok = False
            expected = None

        try:
            actual = symbol_to_df(db, symbol)
        except (ValueError, KeyError) as exc:
            assert not reference_ok, (
                f"{symbol}: new implementation crashed but the old one didn't -- "
                f"regression ({type(exc).__name__}: {exc})"
            )
            # Same pre-existing bug (e.g. a stale formatting.py column
            # mapping) hits both implementations identically, via the
            # create_*_columns helpers they share -- out of scope here.
            continue

        if gtype in (gams.GamsVariable, gams.GamsEquation):
            if reference_ok:
                # Only domains + Value are trustworthy from the old reference.
                pd.testing.assert_frame_equal(
                    actual.iloc[:, :-4], expected.iloc[:, :-4]
                )

            raw = _raw_level_attrs(db, symbol)
            n_domains = len(actual.columns) - 5
            for row in actual.itertuples(index=False, name=None):
                key = row[:n_domains]
                level, marginal, lower, upper, scale = raw[key]
                value, m, l, u, s = row[-5:]
                assert _floats_equal(value, level)
                assert _floats_equal(m, marginal)
                assert _floats_equal(l, lower)
                assert _floats_equal(u, upper)
                assert _floats_equal(s, scale)
        elif reference_ok:
            pd.testing.assert_frame_equal(actual, expected)
        else:
            # 0-domain Parameter: old implementation's dict->transpose trick
            # crashes for scalars; validate against the raw record directly.
            raw = _raw_values(db, symbol)
            assert _floats_equal(actual["Value"].iloc[0], raw[()])

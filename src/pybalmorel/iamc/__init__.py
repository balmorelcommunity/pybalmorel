"""
IAMC Reporting

Converts Balmorel MainResults to the IAMC format that model intercomparisons
use, in three layers (see docs/adr/0016): a Reader that knows Balmorel
symbols, Mapping Rules as CSV tables in `rule_tables/`, and a Definitions Snapshot
of the IAMC common definitions in `definitions/`.

    data, notes = MainResults(...).to_iamc(model='Balmorel-DTU')
    write_iamc(data, notes, 'balmorel_iamc.xlsx')

Created on 23.11.2026
@author: Claude, Anthropic
         Mathias Berg Rosendal, PostDoc at DTU Wind and Energy Systems
"""
from .convert import convert, to_iamc, write_iamc
from .reader import read_mainresults
from .rules import check_rules, load_definitions, load_rules

__all__ = ["to_iamc", "write_iamc", "convert", "read_mainresults", "check_rules", "load_definitions", "load_rules"]

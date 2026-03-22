"""Tests for parse_dimacs."""

import tempfile

import pytest

from approximate_model_counting import ModelCounter, VariableInteractionGraph, parse_dimacs


def _write_cnf(content: str) -> str:
    """Write DIMACS content to a temp file, return path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as f:
        f.write(content)
        return f.name


def test_parse_simple_cnf():
    path = _write_cnf("p cnf 3 2\n1 2 0\n-1 3 0\n")
    clauses = parse_dimacs(path)
    assert clauses == [[1, 2], [-1, 3]]


def test_parse_with_comments():
    path = _write_cnf("c a comment\np cnf 2 1\n1 -2 0\n")
    clauses = parse_dimacs(path)
    assert clauses == [[1, -2]]


def test_parse_nonexistent_file():
    with pytest.raises(RuntimeError, match="Failed to read DIMACS file"):
        parse_dimacs("/nonexistent/file.cnf")


def test_roundtrip_with_model_counter():
    """Clauses from parse_dimacs work with ModelCounter and VariableInteractionGraph."""
    path = _write_cnf("p cnf 4 3\n1 2 0\n-2 3 0\n3 4 0\n")
    clauses = parse_dimacs(path)
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])
    assert info.solvable().name == "SATISFIABLE"
    vig = VariableInteractionGraph(clauses)
    assert sorted(vig.variables()) == [1, 2, 3, 4]

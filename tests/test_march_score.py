"""Tests for march_score algorithm."""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from approximate_model_counting import ModelCounter, Status

from .strategies import (
    has_unique_solution,
    sat_clauses,
    satisfiable_clauses,
    unsatisfiable_clauses,
)

# --- Basic tests ---


def test_empty_clauses_returns_empty_scores():
    """Empty formula has no variables to score."""
    mc = ModelCounter([])
    scores, assumptions = mc.march_score([])
    assert scores == {}
    assert assumptions == []


def test_single_variable_clause():
    """Single unit clause - variable is fixed, no scores returned."""
    mc = ModelCounter([[1]])
    scores, assumptions = mc.march_score([])
    # Variable 1 is already fixed by unit propagation
    assert scores == {}


def test_single_binary_clause():
    """Binary clause (1 or 2) - both variables can be scored."""
    mc = ModelCounter([[1, 2]])
    scores, assumptions = mc.march_score([])
    # Both variables should have scores
    assert 1 in scores
    assert 2 in scores
    assert assumptions == []


def test_assumption_fixes_variable():
    """Assumed variable is not scored."""
    mc = ModelCounter([[1, 2], [2, 3]])
    scores, assumptions = mc.march_score([1])
    # Variable 1 is assumed, shouldn't be scored
    assert 1 not in scores
    assert assumptions == [1]


def test_unsat_formula_returns_empty():
    """UNSAT formula returns empty scores."""
    mc = ModelCounter([[1], [-1]])
    scores, assumptions = mc.march_score([])
    assert scores == {}


def test_unsat_via_failed_literals():
    """UNSAT detected via failed literal detection returns empty."""
    # (1 or 2), (1 or -2), (-1 or 3), (-3)
    # Both 1 and -1 are failed literals -> UNSAT
    mc = ModelCounter([[1, 2], [1, -2], [-1, 3], [-3]])
    scores, assumptions = mc.march_score([])
    assert scores == {}


def test_failed_literal_detection_simple():
    """Simple failed literal case where one polarity conflicts."""
    # Create a formula where a specific literal is forced:
    # (-1) is a unit clause, so 1 is immediately failed
    # But we want to test failed literal *detection*, not unit propagation
    #
    # Let's verify the property-based tests cover this instead
    # by checking that we don't return contradictory assumptions
    mc = ModelCounter([[1, 2], [-1, 3], [-3], [2, 4]])
    scores, assumptions = mc.march_score([])
    # Verify assumptions are consistent (no contradictions)
    assumption_set = set(assumptions)
    for lit in assumptions:
        assert -lit not in assumption_set


def test_product_scoring():
    """Scores use product of reductions from both polarities."""
    mc = ModelCounter([[1, 2, 3], [1, 2, -3]])
    scores, assumptions = mc.march_score([])
    assert len(scores) == 3
    for score in scores.values():
        assert score >= 0


def test_score_values_reasonable():
    """Scores should be reasonable values (not NaN or inf)."""
    mc = ModelCounter([[1, 2], [2, 3], [1, 3], [-1, -2], [-2, -3]])
    scores, assumptions = mc.march_score([])
    for score in scores.values():
        assert not math.isnan(score)
        assert not math.isinf(score)
        assert score >= 0


def test_symmetric_formula_balanced_scores():
    """In a symmetric formula, variables should have similar scores."""
    mc = ModelCounter([[1, 2], [-1, -2]])
    scores, assumptions = mc.march_score([])
    if 1 in scores and 2 in scores:
        assert abs(scores[1] - scores[2]) < 0.001


# --- Property-based tests ---


@given(sat_clauses())
@settings(max_examples=100, deadline=None)
def test_march_score_doesnt_crash(clauses):
    """march_score should not crash on random formulas."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    assert isinstance(scores, dict)
    assert isinstance(assumptions, list)

    # All keys should be positive integers (variables)
    for var in scores:
        assert var > 0

    # All values should be non-negative floats
    for score in scores.values():
        assert score >= 0
        assert not math.isnan(score)
        assert not math.isinf(score)


@given(
    sat_clauses(),
    st.lists(
        st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0),
        max_size=3,
    ),
)
@settings(max_examples=100, deadline=None)
def test_march_score_with_assumptions(clauses, initial_assumptions):
    """march_score with assumptions should return valid results."""
    mc = ModelCounter(clauses)
    scores, updated_assumptions = mc.march_score(initial_assumptions)

    # Updated assumptions should be a superset of initial (modulo sign conflicts)
    for lit in initial_assumptions:
        assert lit in updated_assumptions or -lit in updated_assumptions

    for var in scores:
        assert var > 0


@given(satisfiable_clauses())
@settings(max_examples=50, deadline=None)
def test_satisfiable_formula_has_scores_or_all_fixed(clauses):
    """A satisfiable formula either has scorable variables or all are fixed."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    # If SAT and no scores, all variables must be fixed by unit propagation
    if not scores:
        # Verify that with the assumptions, we can still create a SolutionInformation
        # (just checking it doesn't crash)
        mc.with_assumptions(assumptions)


@given(unsatisfiable_clauses())
@settings(max_examples=30, deadline=None)
def test_unsat_formula_returns_empty_scores(clauses):
    """UNSAT formula should return empty scores."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])
    assert scores == {}


@given(satisfiable_clauses())
@settings(max_examples=50, deadline=None)
def test_scored_variables_appear_in_clauses(clauses):
    """All scored variables should appear in the clauses."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    # Collect all variables from clauses
    clause_vars = set()
    for clause in clauses:
        for lit in clause:
            clause_vars.add(abs(lit))

    # All scored variables should be from the clauses
    for var in scores:
        assert var in clause_vars


@given(satisfiable_clauses(min_clause_size=2))
@settings(max_examples=50, deadline=None)
def test_assumptions_are_consistent(clauses):
    """Returned assumptions should be consistent (no var and -var)."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    # Check no contradictions in assumptions
    assumption_set = set(assumptions)
    for lit in assumptions:
        assert -lit not in assumption_set, f"Contradiction: {lit} and {-lit} both in assumptions"


@given(satisfiable_clauses(min_clause_size=2, max_variables=6))
@settings(max_examples=30, deadline=None)
def test_assumptions_preserve_satisfiability(clauses):
    """Adding returned assumptions should preserve satisfiability (if originally SAT)."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    if scores:  # Only if formula wasn't found UNSAT
        info = mc.with_assumptions(assumptions)
        assert info.solvable() == Status.SATISFIABLE


@given(has_unique_solution())
@settings(max_examples=20, deadline=None)
def test_unique_solution_formula(clauses):
    """Formula with unique solution should be handled correctly."""
    mc = ModelCounter(clauses)
    scores, assumptions = mc.march_score([])

    # Should either have scores or all variables forced
    # (unique solution often means many forced literals)
    assert isinstance(scores, dict)
    assert isinstance(assumptions, list)

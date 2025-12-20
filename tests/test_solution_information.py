"""Tests for SolutionInformation class."""

from hypothesis import given
from hypothesis import strategies as st

from approximate_model_counting import SolutionInformation, Status


def test_empty_problem_is_satisfiable():
    """An empty SAT problem should be satisfiable."""
    si = SolutionInformation()
    assert si.solvable() == Status.SATISFIABLE


def test_single_positive_literal_is_satisfiable():
    """A single positive literal should be satisfiable."""
    si = SolutionInformation()
    si.add_clause([1])
    assert si.solvable() == Status.SATISFIABLE


def test_single_negative_literal_is_satisfiable():
    """A single negative literal should be satisfiable."""
    si = SolutionInformation()
    si.add_clause([-1])
    assert si.solvable() == Status.SATISFIABLE


def test_contradictory_unit_clauses_unsatisfiable():
    """Contradictory unit clauses should be unsatisfiable."""
    si = SolutionInformation()
    si.add_clause([1])
    si.add_clause([-1])
    assert si.solvable() == Status.UNSATISFIABLE


def test_assumption_makes_satisfiable_problem_unsatisfiable():
    """An assumption can make a satisfiable problem unsatisfiable."""
    si = SolutionInformation()
    si.add_clause([1])
    si.add_assumption(-1)
    assert si.solvable() == Status.UNSATISFIABLE


def test_assumption_consistency():
    """Assumptions consistent with clauses should be satisfiable."""
    si = SolutionInformation()
    si.add_clause([1])
    si.add_assumption(1)
    assert si.solvable() == Status.SATISFIABLE


def test_clear_assumptions():
    """Clearing assumptions should restore satisfiability."""
    si = SolutionInformation()
    si.add_clause([1])
    si.add_assumption(-1)
    assert si.solvable() == Status.UNSATISFIABLE

    si.clear_assumptions()
    assert si.solvable() == Status.SATISFIABLE


def test_multiple_assumptions():
    """Multiple assumptions should all be enforced."""
    si = SolutionInformation()
    si.add_clause([1, 2])
    si.add_assumption(-1)
    si.add_assumption(-2)
    assert si.solvable() == Status.UNSATISFIABLE


def test_multi_literal_clause():
    """Test clause with multiple literals."""
    si = SolutionInformation()
    si.add_clause([1, 2, 3])
    assert si.solvable() == Status.SATISFIABLE


def test_multiple_clauses_satisfiable():
    """Multiple compatible clauses should be satisfiable."""
    si = SolutionInformation()
    si.add_clause([1, 2])
    si.add_clause([-1, 3])
    si.add_clause([-2, -3])
    assert si.solvable() == Status.SATISFIABLE


def test_status_enum_values():
    """Test that Status enum has correct values."""
    assert Status.SATISFIABLE == Status.SATISFIABLE
    assert Status.UNSATISFIABLE == Status.UNSATISFIABLE
    assert Status.UNKNOWN == Status.UNKNOWN
    assert Status.SATISFIABLE != Status.UNSATISFIABLE
    assert Status.SATISFIABLE != Status.UNKNOWN
    assert Status.UNSATISFIABLE != Status.UNKNOWN


@given(st.lists(st.integers(min_value=-100, max_value=100).filter(lambda x: x != 0)))
def test_single_clause_always_satisfiable(literals):
    """A single clause (disjunction) is always satisfiable."""
    if not literals:
        return
    si = SolutionInformation()
    si.add_clause(literals)
    assert si.solvable() == Status.SATISFIABLE


@given(st.integers(min_value=1, max_value=100))
def test_positive_and_negative_literal_unsatisfiable(var):
    """Requiring both a variable and its negation is unsatisfiable."""
    si = SolutionInformation()
    si.add_clause([var])
    si.add_clause([-var])
    assert si.solvable() == Status.UNSATISFIABLE


@given(
    st.lists(
        st.lists(st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0), min_size=1),
        max_size=5,
    )
)
def test_solvable_is_deterministic(clauses):
    """Calling solvable multiple times should give same result."""
    if not clauses:
        return
    si = SolutionInformation()
    for clause in clauses:
        si.add_clause(clause)

    first_result = si.solvable()
    second_result = si.solvable()
    assert first_result == second_result

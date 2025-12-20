"""Tests for ModelCounter and SolutionInformation classes."""

from hypothesis import given
from hypothesis import strategies as st

from approximate_model_counting import ModelCounter, Status


def test_empty_problem_is_satisfiable():
    """An empty SAT problem should be satisfiable."""
    mc = ModelCounter([])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.SATISFIABLE


def test_single_positive_literal_is_satisfiable():
    """A single positive literal should be satisfiable."""
    mc = ModelCounter([[1]])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.SATISFIABLE


def test_single_negative_literal_is_satisfiable():
    """A single negative literal should be satisfiable."""
    mc = ModelCounter([[-1]])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.SATISFIABLE


def test_contradictory_unit_clauses_unsatisfiable():
    """Contradictory unit clauses should be unsatisfiable."""
    mc = ModelCounter([[1], [-1]])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.UNSATISFIABLE


def test_assumption_makes_satisfiable_problem_unsatisfiable():
    """An assumption can make a satisfiable problem unsatisfiable."""
    mc = ModelCounter([[1]])
    si = mc.with_assumptions([-1])
    assert si.solvable() == Status.UNSATISFIABLE


def test_assumption_consistency():
    """Assumptions consistent with clauses should be satisfiable."""
    mc = ModelCounter([[1]])
    si = mc.with_assumptions([1])
    assert si.solvable() == Status.SATISFIABLE


def test_different_assumptions_same_counter():
    """Different assumptions on the same counter should give different results."""
    mc = ModelCounter([[1]])
    si_positive = mc.with_assumptions([1])
    si_negative = mc.with_assumptions([-1])
    assert si_positive.solvable() == Status.SATISFIABLE
    assert si_negative.solvable() == Status.UNSATISFIABLE


def test_multiple_assumptions():
    """Multiple assumptions should all be enforced."""
    mc = ModelCounter([[1, 2]])
    si = mc.with_assumptions([-1, -2])
    assert si.solvable() == Status.UNSATISFIABLE


def test_multi_literal_clause():
    """Test clause with multiple literals."""
    mc = ModelCounter([[1, 2, 3]])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.SATISFIABLE


def test_multiple_clauses_satisfiable():
    """Multiple compatible clauses should be satisfiable."""
    mc = ModelCounter([[1, 2], [-1, 3], [-2, -3]])
    si = mc.with_assumptions([])
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
    mc = ModelCounter([literals])
    si = mc.with_assumptions([])
    assert si.solvable() == Status.SATISFIABLE


@given(st.integers(min_value=1, max_value=100))
def test_positive_and_negative_literal_unsatisfiable(var):
    """Requiring both a variable and its negation is unsatisfiable."""
    mc = ModelCounter([[var], [-var]])
    si = mc.with_assumptions([])
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
    mc = ModelCounter(clauses)
    si = mc.with_assumptions([])

    first_result = si.solvable()
    second_result = si.solvable()
    assert first_result == second_result


@given(
    st.lists(
        st.lists(st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0), min_size=1),
        max_size=5,
    ),
    st.lists(st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0), max_size=3),
)
def test_solution_information_is_immutable(clauses, assumptions):
    """SolutionInformation should give consistent results."""
    if not clauses:
        return
    mc = ModelCounter(clauses)
    si = mc.with_assumptions(assumptions)

    # Multiple calls should give same result
    result1 = si.solvable()
    result2 = si.solvable()
    assert result1 == result2

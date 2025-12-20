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


# Tests for current_clauses


def test_current_clauses_empty_problem():
    """Empty problem should return empty clauses."""
    mc = ModelCounter([])
    si = mc.with_assumptions([])
    assert si.current_clauses() == []


def test_current_clauses_no_assumptions():
    """Without assumptions, should return original clauses."""
    mc = ModelCounter([[1, 2], [-1, 3]])
    si = mc.with_assumptions([])
    clauses = si.current_clauses()
    # Should have the original clauses (possibly sorted)
    clause_set = {tuple(sorted(c)) for c in clauses}
    assert (-1, 3) in clause_set or (-1, 3) in clause_set
    assert (1, 2) in clause_set


def test_current_clauses_assumption_becomes_unit():
    """Assumption should appear as unit clause."""
    mc = ModelCounter([[1, 2]])
    si = mc.with_assumptions([1])
    clauses = si.current_clauses()
    # Should have unit clause [1]
    assert [1] in clauses


def test_current_clauses_satisfied_clause_removed():
    """Clause satisfied by assumption should be removed."""
    mc = ModelCounter([[1, 2], [3, 4]])
    si = mc.with_assumptions([1])
    clauses = si.current_clauses()
    # [1, 2] should be removed (satisfied by 1)
    # [3, 4] should remain
    # [1] should be added as unit
    clause_set = {tuple(c) for c in clauses}
    assert (1,) in clause_set
    assert (3, 4) in clause_set
    # Original clause [1, 2] should not appear
    assert (1, 2) not in clause_set


def test_current_clauses_falsified_literal_removed():
    """Falsified literals should be removed from clauses."""
    mc = ModelCounter([[1, 2]])
    si = mc.with_assumptions([-1])
    clauses = si.current_clauses()
    # -1 removes 1 from [1, 2], leaving [2]
    # -1 is also a unit clause
    clause_set = {tuple(c) for c in clauses}
    assert (-1,) in clause_set
    assert (2,) in clause_set  # Became unit after removing 1


def test_current_clauses_unit_propagation():
    """Unit propagation should work correctly."""
    # (1 OR 2) AND (-1)
    # After assumption -1: 1 is false, so [1, 2] becomes [2]
    # [2] is unit, so 2 becomes fixed
    mc = ModelCounter([[1, 2], [-1]])
    si = mc.with_assumptions([])
    clauses = si.current_clauses()
    clause_set = {tuple(c) for c in clauses}
    # -1 from original clause
    assert (-1,) in clause_set
    # 2 from propagation
    assert (2,) in clause_set


def test_current_clauses_contradiction_returns_empty_clause():
    """Contradiction should return empty clause."""
    mc = ModelCounter([[1], [-1]])
    si = mc.with_assumptions([])
    clauses = si.current_clauses()
    # Should return [[]] to indicate unsatisfiability
    assert clauses == [[]]


def test_current_clauses_assumption_contradiction():
    """Assumption contradicting clause should return empty clause."""
    mc = ModelCounter([[1]])
    si = mc.with_assumptions([-1])
    clauses = si.current_clauses()
    # Should return [[]] to indicate unsatisfiability
    assert clauses == [[]]


def test_current_clauses_no_duplicates():
    """Duplicate clauses should be removed."""
    mc = ModelCounter([[1, 2], [1, 2], [2, 1]])
    si = mc.with_assumptions([])
    clauses = si.current_clauses()
    # Should only have one copy of [1, 2]
    clause_set = [tuple(sorted(c)) for c in clauses]
    assert clause_set.count((1, 2)) == 1


def test_current_clauses_chain_propagation():
    """Chain of unit propagations should work."""
    # (1) AND (-1 OR 2) AND (-2 OR 3)
    # 1 is unit -> propagates
    # [1, -1 OR 2] -> 2 becomes unit
    # [2, -2 OR 3] -> 3 becomes unit
    mc = ModelCounter([[1], [-1, 2], [-2, 3]])
    si = mc.with_assumptions([])
    clauses = si.current_clauses()
    clause_set = {tuple(c) for c in clauses}
    assert (1,) in clause_set
    assert (2,) in clause_set
    assert (3,) in clause_set


def test_current_clauses_is_deterministic():
    """Multiple calls should return the same result."""
    mc = ModelCounter([[1, 2], [-1, 3]])
    si = mc.with_assumptions([1])
    clauses1 = si.current_clauses()
    clauses2 = si.current_clauses()
    assert clauses1 == clauses2

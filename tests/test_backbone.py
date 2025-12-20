"""Tests for backbone calculation."""

from hypothesis import given, settings
from hypothesis import strategies as st

from approximate_model_counting import ModelCounter, Status

# --- Basic tests ---


def test_empty_clauses_has_empty_backbone():
    """Empty formula has no backbone literals."""
    mc = ModelCounter([])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert backbone == []


def test_unit_clause_in_backbone():
    """A unit clause forces its literal into the backbone."""
    mc = ModelCounter([[1]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert 1 in backbone


def test_assumption_in_backbone():
    """Assumptions are included in the backbone."""
    mc = ModelCounter([[1, 2]])
    info = mc.with_assumptions([1])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert 1 in backbone


def test_unsatisfiable_has_empty_backbone():
    """UNSAT formula has empty backbone."""
    mc = ModelCounter([[1], [-1]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.UNSATISFIABLE
    backbone = info.get_backbone()
    assert backbone == []


def test_forced_literal_in_backbone():
    """A literal forced by unit propagation is in the backbone."""
    # (1 or 2) and (-1) forces 2
    mc = ModelCounter([[1, 2], [-1]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert -1 in backbone
    assert 2 in backbone


def test_free_variable_not_in_backbone():
    """A variable that can be either true or false is not in the backbone."""
    # (1 or 2) - both 1 and 2 can vary
    mc = ModelCounter([[1, 2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    # Neither 1 nor -1 should be in backbone (same for 2)
    assert 1 not in backbone and -1 not in backbone
    assert 2 not in backbone and -2 not in backbone


def test_implied_backbone_literal():
    """A literal implied by the formula structure is in the backbone."""
    # (1 or 2) and (1 or -2) - 1 must be true in all solutions
    mc = ModelCounter([[1, 2], [1, -2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert 1 in backbone


def test_multiple_backbone_literals():
    """Multiple forced literals should all be in the backbone."""
    # (-1) and (-2) and (3)
    mc = ModelCounter([[-1], [-2], [3]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert -1 in backbone
    assert -2 in backbone
    assert 3 in backbone


def test_backbone_with_complex_formula():
    """Test backbone on a more complex formula."""
    # (1 or 2) and (1 or 3) and (-2 or -3)
    # If 1 is false: need 2 and 3, but -2 or -3 fails
    # So 1 must be true
    mc = ModelCounter([[1, 2], [1, 3], [-2, -3]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    backbone = info.get_backbone()
    assert 1 in backbone


def test_backbone_is_cached():
    """Calling get_backbone multiple times returns same result."""
    mc = ModelCounter([[1], [2, 3]])
    info = mc.with_assumptions([])
    backbone1 = info.get_backbone()
    backbone2 = info.get_backbone()
    assert backbone1 == backbone2


# --- Property-based tests ---


@given(
    st.lists(
        st.lists(st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0), min_size=1),
        min_size=1,
    )
)
@settings(max_examples=100, deadline=None)
def test_backbone_literals_are_consistent(clauses):
    """Backbone should not contain both a literal and its negation."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])

    if info.solvable() == Status.SATISFIABLE:
        backbone = info.get_backbone()
        backbone_set = set(backbone)

        # No literal and its negation
        for lit in backbone:
            assert -lit not in backbone_set, f"Contradiction: {lit} and {-lit} in backbone"


@given(
    st.lists(
        st.lists(st.integers(min_value=-10, max_value=10).filter(lambda x: x != 0), min_size=1),
        min_size=1,
    )
)
@settings(max_examples=100, deadline=None)
def test_backbone_literals_satisfy_all_clauses_with_them(clauses):
    """Each backbone literal should be consistent with the formula."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])

    if info.solvable() == Status.SATISFIABLE:
        backbone = info.get_backbone()

        # Setting backbone literals should still be satisfiable
        if backbone:
            info2 = mc.with_assumptions(backbone)
            assert info2.solvable() == Status.SATISFIABLE


@given(
    st.lists(
        st.lists(st.integers(min_value=-5, max_value=5).filter(lambda x: x != 0), min_size=1),
        min_size=1,
    )
)
@settings(max_examples=50, deadline=None)
def test_backbone_negation_is_unsat(clauses):
    """Negating a backbone literal should make the formula UNSAT."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])

    if info.solvable() == Status.SATISFIABLE:
        backbone = info.get_backbone()

        # Negating any backbone literal should be UNSAT
        for lit in backbone:
            info2 = mc.with_assumptions([-lit])
            assert info2.solvable() == Status.UNSATISFIABLE, (
                f"Negating backbone literal {lit} should be UNSAT"
            )


@given(
    st.lists(
        st.lists(st.integers(min_value=-5, max_value=5).filter(lambda x: x != 0), min_size=1),
        min_size=1,
    ),
    st.lists(st.integers(min_value=-5, max_value=5).filter(lambda x: x != 0), max_size=3),
)
@settings(max_examples=50, deadline=None)
def test_backbone_includes_assumptions(clauses, assumptions):
    """Backbone should include the assumptions (if SAT)."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions(assumptions)

    if info.solvable() == Status.SATISFIABLE:
        backbone = info.get_backbone()
        backbone_set = set(backbone)

        # All assumptions should be in backbone (or their consequences)
        for lit in assumptions:
            # Either the literal is in backbone, or its negation leads to contradiction
            # (which would have been caught by solvable())
            assert lit in backbone_set, f"Assumption {lit} not in backbone"

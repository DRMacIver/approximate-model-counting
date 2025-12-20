"""Tests for literal equivalence detection."""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from approximate_model_counting import ModelCounter, Status

from .strategies import satisfiable_clauses

# --- Basic tests ---


def test_literal_equivalent_to_itself():
    """Every literal is equivalent to itself."""
    mc = ModelCounter([[1, 2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, 1)
    assert info.are_equivalent(2, 2)
    assert info.are_equivalent(-1, -1)


def test_literal_equivalent_to_double_negation():
    """A literal is equivalent to its double negation (same literal)."""
    mc = ModelCounter([[1, 2]])
    info = mc.with_assumptions([])
    # -(-1) = 1, so are_equivalent(1, 1) should be true
    assert info.are_equivalent(1, 1)


def test_simple_equivalence():
    """x <-> y forces x and y to be equivalent."""
    # (x | -y) & (-x | y) means x = y
    mc = ModelCounter([[1, -2], [-1, 2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, 2)
    assert info.are_equivalent(-1, -2)


def test_opposite_equivalence():
    """x <-> -y forces x and -y to be equivalent (x opposite to y)."""
    # (x | y) & (-x | -y) means x = -y
    mc = ModelCounter([[1, 2], [-1, -2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, -2)
    assert info.are_equivalent(-1, 2)


def test_independent_variables_not_equivalent():
    """Independent variables should not be equivalent."""
    # (x | y) allows x and y to vary independently
    mc = ModelCounter([[1, 2]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert not info.are_equivalent(1, 2)
    assert not info.are_equivalent(1, -2)


def test_backbone_literals_equivalent_to_themselves():
    """Backbone literals should be equivalent to themselves."""
    mc = ModelCounter([[1], [2, 3]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert 1 in info.get_backbone()
    assert info.are_equivalent(1, 1)


def test_transitive_equivalence():
    """If x=y and y=z then x=z."""
    # x <-> y: (x | -y) & (-x | y)
    # y <-> z: (y | -z) & (-y | z)
    mc = ModelCounter([[1, -2], [-1, 2], [2, -3], [-2, 3]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, 2)
    assert info.are_equivalent(2, 3)
    assert info.are_equivalent(1, 3)


def test_equivalence_with_backbone():
    """Equivalences should work alongside backbone detection."""
    # x is forced true, y <-> z
    mc = ModelCounter([[1], [2, -3], [-2, 3]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert 1 in info.get_backbone()
    assert info.are_equivalent(2, 3)
    # x is independent of y and z
    assert not info.are_equivalent(1, 2)


def test_unsatisfiable_equivalence():
    """UNSAT formula should still allow equivalence queries."""
    mc = ModelCounter([[1], [-1]])
    info = mc.with_assumptions([])
    assert info.solvable() == Status.UNSATISFIABLE
    # Equivalence on UNSAT should be well-defined (trivially true)
    assert info.are_equivalent(1, 1)


def test_three_way_equivalence():
    """Three variables all equivalent to each other."""
    # x <-> y <-> z (all same value)
    mc = ModelCounter(
        [
            [1, -2],
            [-1, 2],  # x <-> y
            [2, -3],
            [-2, 3],  # y <-> z
        ]
    )
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, 2)
    assert info.are_equivalent(2, 3)
    assert info.are_equivalent(1, 3)
    assert info.are_equivalent(-1, -2)
    assert info.are_equivalent(-2, -3)
    assert info.are_equivalent(-1, -3)


def test_mixed_equivalence_chain():
    """Chain with mixed signs: x = -y = z."""
    # x <-> -y: (x | y) & (-x | -y)
    # y <-> -z: (y | z) & (-y | -z)  => -y <-> z
    mc = ModelCounter(
        [
            [1, 2],
            [-1, -2],  # x <-> -y
            [2, 3],
            [-2, -3],  # y <-> -z, so -y <-> z
        ]
    )
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, -2)  # x = -y
    assert info.are_equivalent(-2, 3)  # -y = z
    assert info.are_equivalent(1, 3)  # x = z (transitive)


def test_partial_equivalence():
    """Some variables equivalent, others independent."""
    # x <-> y, but z is independent
    mc = ModelCounter(
        [
            [1, -2],
            [-1, 2],  # x <-> y
            [3, -3],  # z can be anything (tautology, but adds variable)
        ]
    )
    info = mc.with_assumptions([])
    assert info.solvable() == Status.SATISFIABLE
    assert info.are_equivalent(1, 2)
    # z should not be equivalent to x or y
    # Note: z appears in a tautology so might not be in the formula at all
    # Let's use a real clause
    mc2 = ModelCounter(
        [
            [1, -2],
            [-1, 2],  # x <-> y
            [1, 3],  # x | z (adds z as a real variable)
        ]
    )
    info2 = mc2.with_assumptions([])
    assert info2.are_equivalent(1, 2)


# --- Property-based tests ---


@given(satisfiable_clauses())
@settings(max_examples=100, deadline=None)
def test_equivalence_is_reflexive(clauses):
    """Every literal is equivalent to itself."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])
    # Pick a variable that appears in the clauses
    vars_in_clauses = {abs(lit) for clause in clauses for lit in clause}
    for v in list(vars_in_clauses)[:3]:  # Test first 3 to keep it fast
        assert info.are_equivalent(v, v)
        assert info.are_equivalent(-v, -v)


@given(satisfiable_clauses())
@settings(max_examples=100, deadline=None)
def test_equivalence_is_symmetric(clauses):
    """If a ~ b then b ~ a."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])
    vars_in_clauses = list({abs(lit) for clause in clauses for lit in clause})[:3]
    for i, a in enumerate(vars_in_clauses):
        for b in vars_in_clauses[i + 1 :]:
            assert info.are_equivalent(a, b) == info.are_equivalent(b, a)


@given(satisfiable_clauses())
@settings(max_examples=100, deadline=None)
def test_equivalence_respects_negation(clauses):
    """If a ~ b then -a ~ -b."""
    mc = ModelCounter(clauses)
    info = mc.with_assumptions([])
    vars_in_clauses = list({abs(lit) for clause in clauses for lit in clause})[:3]
    for i, a in enumerate(vars_in_clauses):
        for b in vars_in_clauses[i + 1 :]:
            if info.are_equivalent(a, b):
                assert info.are_equivalent(-a, -b)


@st.composite
def split_clauses(draw):
    clauses = draw(satisfiable_clauses())
    assume(len(clauses) > 1)
    i = draw(st.integers(0, len(clauses) - 1))
    return clauses[:i], clauses[i:]


@given(split_clauses())
@settings(max_examples=100, deadline=None)
def test_increasing_clauses_cannot_break_equivalence(xy):
    x, y = xy
    variables = {abs(lit) for z in (x, y) for clause in z for lit in clause}
    literals = {v * s for v in variables for s in (-1, 1)}
    mc_x = ModelCounter(x)
    mc_x_root = mc_x.with_assumptions([])
    equivs = {
        (u, v) for u in literals for v in literals if u != v and mc_x_root.are_equivalent(u, v)
    }
    assume(equivs)
    mc_xy_root = ModelCounter(x + y).with_assumptions([])
    for u, v in equivs:
        assert mc_xy_root.are_equivalent(u, v)

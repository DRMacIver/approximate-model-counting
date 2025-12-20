"""Tests for BooleanEquivalence class."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from approximate_model_counting import BooleanEquivalence


def test_empty_has_zero_representatives():
    """Empty BooleanEquivalence has no representatives."""
    be = BooleanEquivalence()
    assert be.num_representatives() == 0


def test_find_returns_self_for_new_literal():
    """Finding a new literal returns itself."""
    be = BooleanEquivalence()
    assert be.find(1) == 1
    assert be.find(5) == 5
    assert be.find(100) == 100


def test_find_negative_returns_negated():
    """Finding -a returns -find(a)."""
    be = BooleanEquivalence()
    assert be.find(-1) == -1
    assert be.find(-5) == -5
    # After finding positive, negative should be consistent
    be.find(3)
    assert be.find(-3) == -3


def test_find_zero_raises():
    """Finding literal 0 raises an error."""
    be = BooleanEquivalence()
    with pytest.raises(ValueError):
        be.find(0)


def test_merge_makes_literals_equivalent():
    """Merging two literals makes them have the same representative."""
    be = BooleanEquivalence()
    be.merge(1, 2)
    assert be.find(1) == be.find(2)


def test_merge_same_literal_is_noop():
    """Merging a literal with itself does nothing."""
    be = BooleanEquivalence()
    be.find(1)  # Initialize
    initial_reps = be.num_representatives()
    be.merge(1, 1)
    assert be.num_representatives() == initial_reps


def test_merge_already_equivalent_is_noop():
    """Merging already-equivalent literals does nothing."""
    be = BooleanEquivalence()
    be.merge(1, 2)
    reps_after_first = be.num_representatives()
    be.merge(1, 2)
    assert be.num_representatives() == reps_after_first
    be.merge(2, 1)
    assert be.num_representatives() == reps_after_first


def test_merge_transitive():
    """Equivalence is transitive: a=b and b=c implies a=c."""
    be = BooleanEquivalence()
    be.merge(1, 2)
    be.merge(2, 3)
    assert be.find(1) == be.find(3)


def test_merge_with_negation():
    """Merging a with -b means a and b are opposites."""
    be = BooleanEquivalence()
    be.merge(1, -2)
    # 1 and -2 should have same representative
    assert be.find(1) == be.find(-2)
    # Therefore 1 and 2 should have opposite representatives
    assert be.find(1) == -be.find(2)


def test_merge_contradiction_raises():
    """Merging a literal with its negation raises an error."""
    be = BooleanEquivalence()
    with pytest.raises(RuntimeError):
        be.merge(1, -1)


def test_merge_transitive_contradiction_raises():
    """Transitive contradiction is detected."""
    be = BooleanEquivalence()
    be.merge(1, 2)
    be.merge(2, 3)
    # Now 1 = 2 = 3, so merging 1 with -3 should fail
    with pytest.raises(RuntimeError):
        be.merge(1, -3)


def test_num_representatives_increases_on_new_literal():
    """Each new literal increases the representative count."""
    be = BooleanEquivalence()
    assert be.num_representatives() == 0
    be.find(1)
    assert be.num_representatives() == 1
    be.find(2)
    assert be.num_representatives() == 2
    be.find(3)
    assert be.num_representatives() == 3


def test_num_representatives_same_for_negation():
    """Finding -a doesn't create a new representative if a exists."""
    be = BooleanEquivalence()
    be.find(1)
    assert be.num_representatives() == 1
    be.find(-1)
    assert be.num_representatives() == 1


def test_num_representatives_decreases_on_merge():
    """Merging two distinct classes decreases the representative count."""
    be = BooleanEquivalence()
    be.find(1)
    be.find(2)
    assert be.num_representatives() == 2
    be.merge(1, 2)
    assert be.num_representatives() == 1


def test_complex_chain():
    """Test a complex chain of equivalences."""
    be = BooleanEquivalence()
    # Create chain: 1 = 2 = 3 = 4 = 5
    be.merge(1, 2)
    be.merge(2, 3)
    be.merge(3, 4)
    be.merge(4, 5)

    # All should have the same representative
    rep = be.find(1)
    assert be.find(2) == rep
    assert be.find(3) == rep
    assert be.find(4) == rep
    assert be.find(5) == rep

    # All negations should have negated representative
    assert be.find(-1) == -rep
    assert be.find(-5) == -rep


def test_mixed_sign_chain():
    """Test chain with mixed signs."""
    be = BooleanEquivalence()
    # 1 = -2 means 1 and 2 are opposites
    # -2 = 3 means 2 and 3 are opposites, so 1 = 3
    be.merge(1, -2)
    be.merge(-2, 3)

    assert be.find(1) == be.find(3)
    assert be.find(1) == -be.find(2)


# Property-based tests


@given(st.integers(min_value=1, max_value=1000))
def test_find_is_idempotent(v):
    """find(find(a)) == find(a)."""
    be = BooleanEquivalence()
    first = be.find(v)
    second = be.find(first)
    assert first == second


@given(st.integers(min_value=1, max_value=1000))
def test_find_negation_symmetry(v):
    """find(-a) == -find(a)."""
    be = BooleanEquivalence()
    pos = be.find(v)
    neg = be.find(-v)
    assert neg == -pos


@given(st.integers(min_value=1, max_value=100), st.integers(min_value=1, max_value=100))
def test_merge_is_symmetric(a, b):
    """merge(a, b) and merge(b, a) have the same effect."""
    be1 = BooleanEquivalence()
    be1.merge(a, b)

    be2 = BooleanEquivalence()
    be2.merge(b, a)

    # Both should have same equivalence
    assert (be1.find(a) == be1.find(b)) == (be2.find(a) == be2.find(b))


@given(
    st.lists(
        st.tuples(st.integers(min_value=1, max_value=20), st.integers(min_value=1, max_value=20)),
        max_size=10,
    )
)
def test_merge_sequence_consistent(merges):
    """A sequence of merges produces consistent equivalences."""
    be = BooleanEquivalence()

    for a, b in merges:
        # Skip if this would create a contradiction
        try:
            be.merge(a, b)
        except RuntimeError:
            continue

    # Check that equivalence is consistent - merged literals have same |rep|
    for a, b in merges:
        # If they were merged (and not contradicted), they should have the
        # same absolute representative (i.e., belong to same equivalence class)
        assert abs(be.find(a)) == abs(be.find(b))


@given(st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=20, unique=True))
def test_num_representatives_matches_classes(variables):
    """num_representatives equals the number of equivalence classes."""
    be = BooleanEquivalence()

    # Find all variables
    for v in variables:
        be.find(v)

    # Should have as many representatives as variables
    assert be.num_representatives() == len(variables)

    # Now merge some
    if len(variables) >= 2:
        be.merge(variables[0], variables[1])
        assert be.num_representatives() == len(variables) - 1

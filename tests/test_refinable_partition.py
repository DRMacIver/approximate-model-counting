"""Tests for RefinablePartition class."""

import pytest
from hypothesis import given, assume
from hypothesis import strategies as st

from approximate_model_counting import RefinablePartition


def test_initial_state_has_one_partition():
    """New partition starts with all elements in one partition."""
    rp = RefinablePartition(5)
    assert len(rp) == 1


def test_initial_partition_contains_all_elements():
    """The initial partition contains all elements."""
    rp = RefinablePartition(5)
    assert sorted(rp[0]) == [0, 1, 2, 3, 4]


def test_empty_partition():
    """Partition of size 0 has one empty partition."""
    rp = RefinablePartition(0)
    assert len(rp) == 1
    assert rp[0] == []


def test_negative_indexing():
    """Negative indices work like Python lists."""
    rp = RefinablePartition(5)
    rp.mark([0, 1])
    assert len(rp) == 2
    # rp[-1] should be the last partition (the marked one)
    assert rp[-1] == rp[len(rp) - 1]
    # rp[-2] should be the first partition
    assert rp[-2] == rp[0]


def test_index_out_of_range_raises():
    """Out of range index raises IndexError."""
    rp = RefinablePartition(5)
    with pytest.raises(IndexError):
        rp[1]
    with pytest.raises(IndexError):
        rp[-2]


def test_partition_of_returns_correct_partition():
    """partition_of returns the correct partition index."""
    rp = RefinablePartition(5)
    # Initially all in partition 0
    for i in range(5):
        assert rp.partition_of(i) == 0


def test_mark_splits_partition():
    """Marking elements splits the partition."""
    rp = RefinablePartition(5)
    rp.mark([0, 1])
    assert len(rp) == 2
    # Unmarked elements stay in original partition
    assert sorted(rp[0]) == [2, 3, 4]
    # Marked elements move to new partition
    assert sorted(rp[1]) == [0, 1]


def test_mark_updates_partition_of():
    """After marking, partition_of reflects the new partitions."""
    rp = RefinablePartition(5)
    rp.mark([0, 1])

    # Unmarked elements in partition 0
    assert rp.partition_of(2) == 0
    assert rp.partition_of(3) == 0
    assert rp.partition_of(4) == 0

    # Marked elements in partition 1
    assert rp.partition_of(0) == 1
    assert rp.partition_of(1) == 1


def test_mark_entire_partition_no_split():
    """Marking all elements in a partition doesn't split it."""
    rp = RefinablePartition(5)
    rp.mark([0, 1, 2, 3, 4])
    assert len(rp) == 1
    assert sorted(rp[0]) == [0, 1, 2, 3, 4]


def test_mark_empty_list_no_change():
    """Marking empty list doesn't change anything."""
    rp = RefinablePartition(5)
    rp.mark([])
    assert len(rp) == 1
    assert sorted(rp[0]) == [0, 1, 2, 3, 4]


def test_multiple_marks():
    """Multiple mark operations refine further."""
    rp = RefinablePartition(6)

    # First split: {0,1,2} vs {3,4,5}
    rp.mark([0, 1, 2])
    assert len(rp) == 2

    # Second split: {0} vs {1,2} in the marked partition
    rp.mark([0])
    assert len(rp) == 3


def test_mark_from_multiple_partitions():
    """Marking elements from multiple partitions splits each."""
    rp = RefinablePartition(6)

    # First split into {0,1,2} and {3,4,5}
    rp.mark([3, 4, 5])
    assert len(rp) == 2

    # Mark one from each partition
    rp.mark([0, 3])
    assert len(rp) == 4


def test_all_elements_accounted_for():
    """All elements appear in exactly one partition."""
    rp = RefinablePartition(10)
    rp.mark([0, 2, 4, 6, 8])
    rp.mark([0, 1, 2, 3])

    all_elements = []
    for i in range(len(rp)):
        all_elements.extend(rp[i])

    assert sorted(all_elements) == list(range(10))


def test_partition_of_consistent_with_getitem():
    """partition_of is consistent with __getitem__."""
    rp = RefinablePartition(10)
    rp.mark([1, 3, 5, 7, 9])
    rp.mark([0, 1])

    for i in range(10):
        partition_idx = rp.partition_of(i)
        assert i in rp[partition_idx]


# Property-based tests


@given(st.integers(min_value=0, max_value=100))
def test_initial_size_is_one(n):
    """Any partition starts with size 1."""
    rp = RefinablePartition(n)
    assert len(rp) == 1


@given(st.integers(min_value=1, max_value=50))
def test_initial_contains_all(n):
    """Initial partition contains all elements."""
    rp = RefinablePartition(n)
    assert sorted(rp[0]) == list(range(n))


@given(
    st.integers(min_value=1, max_value=20),
    st.lists(st.integers(min_value=0, max_value=19), max_size=10),
)
def test_mark_preserves_elements(n, to_mark):
    """Marking preserves all elements."""
    # Filter to valid indices
    to_mark = [x for x in to_mark if x < n]

    rp = RefinablePartition(n)
    rp.mark(to_mark)

    all_elements = []
    for i in range(len(rp)):
        all_elements.extend(rp[i])

    assert sorted(all_elements) == list(range(n))


@given(
    st.integers(min_value=1, max_value=20),
    st.lists(st.lists(st.integers(min_value=0, max_value=19), max_size=10), max_size=5),
)
def test_multiple_marks_preserve_elements(n, mark_sequences):
    """Multiple marks preserve all elements."""
    rp = RefinablePartition(n)

    for to_mark in mark_sequences:
        # Filter to valid indices
        to_mark = [x for x in to_mark if x < n]
        rp.mark(to_mark)

    all_elements = []
    for i in range(len(rp)):
        all_elements.extend(rp[i])

    assert sorted(all_elements) == list(range(n))


@given(
    st.integers(min_value=1, max_value=20),
    st.lists(st.lists(st.integers(min_value=0, max_value=19), max_size=10), max_size=5),
)
def test_partition_of_consistent(n, mark_sequences):
    """partition_of is always consistent with partition contents."""
    rp = RefinablePartition(n)

    for to_mark in mark_sequences:
        to_mark = [x for x in to_mark if x < n]
        rp.mark(to_mark)

    for elem in range(n):
        partition_idx = rp.partition_of(elem)
        assert 0 <= partition_idx < len(rp)
        assert elem in rp[partition_idx]


@given(
    st.integers(min_value=1, max_value=20),
    st.lists(st.integers(min_value=0, max_value=19), min_size=1, max_size=10),
)
def test_mark_increases_or_keeps_size(n, to_mark):
    """Marking never decreases the number of partitions."""
    to_mark = [x for x in to_mark if x < n]
    assume(len(to_mark) > 0)

    rp = RefinablePartition(n)
    old_size = len(rp)
    rp.mark(to_mark)
    assert len(rp) >= old_size

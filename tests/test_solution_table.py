"""Tests for SolutionTable class."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from approximate_model_counting import SolutionTable


def test_empty_variables_has_one_row():
    """A table with no variables has exactly one (empty) assignment."""
    table = SolutionTable([])
    assert len(table) == 1
    assert table[0] == []


def test_single_variable_has_two_rows():
    """A table with one variable has two assignments."""
    table = SolutionTable([1])
    assert len(table) == 2


def test_two_variables_has_four_rows():
    """A table with two variables has four assignments."""
    table = SolutionTable([1, 2])
    assert len(table) == 4


def test_size_is_power_of_two():
    """Size should be 2^n for n variables."""
    for n in range(7):
        variables = list(range(1, n + 1))
        table = SolutionTable(variables)
        assert len(table) == 2**n


def test_assignments_are_complete():
    """Each assignment should contain all variables (positive or negative)."""
    table = SolutionTable([1, 2, 3])
    for i in range(len(table)):
        assignment = table[i]
        # Should have one literal per variable
        assert len(assignment) == 3
        # Variables should be 1, 2, 3 (in absolute value)
        assert sorted(abs(lit) for lit in assignment) == [1, 2, 3]


def test_assignments_are_unique():
    """All assignments should be distinct."""
    table = SolutionTable([1, 2, 3])
    assignments = [tuple(table[i]) for i in range(len(table))]
    assert len(set(assignments)) == len(assignments)


def test_assignments_cover_all_combinations():
    """All possible combinations should be present."""
    table = SolutionTable([1, 2])
    assignments = {tuple(sorted(table[i])) for i in range(len(table))}
    expected = {
        (-2, -1),
        (-2, 1),
        (-1, 2),
        (1, 2),
    }
    assert assignments == expected


def test_add_variable_doubles_size():
    """Adding a variable should double the table size."""
    table = SolutionTable([1, 2])
    assert len(table) == 4
    table.add_variable(3)
    assert len(table) == 8


def test_contains_variable():
    """contains() should return True for variables in the table."""
    table = SolutionTable([1, 3, 5])
    assert table.contains(1)
    assert table.contains(3)
    assert table.contains(5)
    assert not table.contains(2)
    assert not table.contains(4)


def test_contains_rejects_non_positive():
    """contains() should return False for non-positive values."""
    table = SolutionTable([1, 2])
    assert not table.contains(0)
    assert not table.contains(-1)


def test_get_variables():
    """get_variables should return the list of variables."""
    table = SolutionTable([3, 1, 4])
    # Order may be preserved from construction
    assert set(table.variables) == {1, 3, 4}


def test_clone_creates_independent_copy():
    """Cloning should create an independent copy."""
    table = SolutionTable([1, 2])
    original_size = len(table)
    clone = table.clone()

    # Modify clone
    clone.remove_matching([1])

    # Original should be unchanged
    assert len(table) == original_size
    assert len(clone) == original_size // 2


def test_remove_matching_halves_size():
    """Removing matching rows for one literal halves the size."""
    table = SolutionTable([1, 2, 3])
    assert len(table) == 8
    table.remove_matching([1])
    assert len(table) == 4


def test_remove_matching_with_multiple_literals():
    """Removing with multiple literals removes intersection."""
    table = SolutionTable([1, 2, 3])
    assert len(table) == 8
    # Remove rows where x1=true AND x2=true
    table.remove_matching([1, 2])
    assert len(table) == 6


def test_remove_matching_all_rows():
    """Can remove all rows matching a full assignment."""
    table = SolutionTable([1, 2])
    assert len(table) == 4
    table.remove_matching([1, 2])
    assert len(table) == 3
    table.remove_matching([1, -2])
    assert len(table) == 2
    table.remove_matching([-1, 2])
    assert len(table) == 1
    table.remove_matching([-1, -2])
    assert len(table) == 0


def test_index_out_of_bounds_raises():
    """Accessing beyond size should raise IndexError."""
    table = SolutionTable([1, 2])
    with pytest.raises(IndexError):
        table[4]
    with pytest.raises(IndexError):
        table[100]


def test_invalid_variable_zero_raises():
    """Variable 0 should raise ValueError."""
    with pytest.raises(ValueError):
        SolutionTable([0])


def test_invalid_variable_negative_raises():
    """Negative variables should raise ValueError."""
    with pytest.raises(ValueError):
        SolutionTable([-1])


def test_too_many_variables_raises():
    """More than 63 variables should raise ValueError."""
    with pytest.raises(ValueError):
        SolutionTable(list(range(1, 65)))


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=6, unique=True))
def test_size_matches_expected(variables):
    """Size should always be 2^n."""
    table = SolutionTable(variables)
    assert len(table) == 2 ** len(variables)


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=5, unique=True))
def test_all_assignments_valid(variables):
    """All assignments should have correct structure."""
    table = SolutionTable(variables)
    var_set = set(variables)

    for i in range(len(table)):
        assignment = table[i]
        # Correct number of literals
        assert len(assignment) == len(variables)
        # All variables covered
        assert {abs(lit) for lit in assignment} == var_set


@given(
    st.lists(st.integers(min_value=1, max_value=50), min_size=2, max_size=5, unique=True),
    st.data(),
)
def test_remove_matching_reduces_size(variables, data):
    """Removing matching rows should reduce size appropriately."""
    table = SolutionTable(variables)
    n = len(variables)
    original_size = len(table)
    assert original_size == 2**n

    # Pick some variables to constrain
    num_constraints = data.draw(st.integers(min_value=1, max_value=len(variables)))
    constrained_vars = data.draw(
        st.permutations(variables).map(lambda x: list(x)[:num_constraints])
    )
    # Assign each a random polarity
    assignment = [v if data.draw(st.booleans()) else -v for v in constrained_vars]

    table.remove_matching(assignment)

    # Specifying k literals removes 2^(n-k) rows (the ones where all k match)
    rows_removed = 2 ** (n - num_constraints)
    expected_size = original_size - rows_removed
    assert len(table) == expected_size


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=5, unique=True))
def test_clone_preserves_size(variables):
    """Clone should have same size as original."""
    table = SolutionTable(variables)
    clone = table.clone()
    assert len(clone) == len(table)


@given(
    st.lists(st.integers(min_value=1, max_value=100), min_size=0, max_size=5, unique=True),
    st.integers(min_value=101, max_value=200),
)
def test_add_variable_doubles_size_property(variables, new_var):
    """Adding a variable should double size."""
    table = SolutionTable(variables)
    original_size = len(table)
    table.add_variable(new_var)
    assert len(table) == original_size * 2


def test_remove_matching_with_zero_literal_raises():
    """remove_matching with literal 0 should raise ValueError."""
    table = SolutionTable([1, 2])
    with pytest.raises(ValueError, match="Invalid variable 0"):
        table.remove_matching([0])


def test_remove_matching_with_unknown_variable_raises():
    """remove_matching with unknown variable should raise ValueError."""
    table = SolutionTable([1, 2])
    with pytest.raises(ValueError, match="Variable 99 not found"):
        table.remove_matching([99])


def test_add_variable_overflow_raises():
    """Adding a variable when size would overflow should raise OverflowError."""
    # Create a table with 63 variables (max allowed)
    # This table has 2^63 implicit rows, which is > SIZE_MAX/2
    table = SolutionTable(list(range(1, 64)))
    with pytest.raises(OverflowError, match="overflow"):
        table.add_variable(100)


class SolutionTableStateMachine(RuleBasedStateMachine):
    """Stateful test comparing SolutionTable to a set-based model."""

    table: SolutionTable
    model: set[frozenset[int]]
    variables: set[int]
    next_var: int

    @initialize(
        variables=st.lists(
            st.integers(min_value=1, max_value=50), min_size=0, max_size=6, unique=True
        )
    )
    def init_table(self, variables: list[int]) -> None:
        """Initialize with a set of variables."""
        self.variables = set(variables)
        self.table = SolutionTable(variables)
        # Model: set of all possible assignments as frozensets of literals
        # Each assignment is a frozenset like {1, -2, 3} meaning x1=T, x2=F, x3=T
        self.model = self._all_assignments(self.variables)
        # Next variable to add (guaranteed not in current set)
        self.next_var = max(variables) + 1 if variables else 1

    def _all_assignments(self, variables: set[int]) -> set[frozenset[int]]:
        """Generate all possible assignments for the given variables."""
        if not variables:
            return {frozenset()}
        sorted_vars = sorted(variables)
        result: set[frozenset[int]] = set()
        for i in range(2 ** len(sorted_vars)):
            assignment = frozenset(v if (i >> j) & 1 else -v for j, v in enumerate(sorted_vars))
            result.add(assignment)
        return result

    def _table_contents(self) -> set[frozenset[int]]:
        """Extract all assignments from the table as a set of frozensets."""
        return {frozenset(self.table[i]) for i in range(len(self.table))}

    @rule(polarity=st.booleans())
    def add_variable(self, polarity: bool) -> None:
        """Add a new variable to the table."""
        new_var = self.next_var
        self.next_var += 1

        # Skip if we'd have too many variables
        if len(self.variables) >= 10:
            return

        self.variables.add(new_var)
        self.table.add_variable(new_var)

        # Update model: each existing assignment spawns two new ones
        new_model: set[frozenset[int]] = set()
        for assignment in self.model:
            new_model.add(assignment | {new_var})
            new_model.add(assignment | {-new_var})
        self.model = new_model

    @rule(data=st.data())
    def remove_matching(self, data: st.DataObject) -> None:
        """Remove rows matching a partial assignment."""
        if not self.variables or not self.model:
            return

        # Pick 1 to all variables to constrain
        num_constraints = data.draw(st.integers(min_value=1, max_value=len(self.variables)))
        constrained_vars = data.draw(
            st.permutations(sorted(self.variables)).map(lambda x: list(x)[:num_constraints])
        )
        # Assign each a random polarity
        assignment = [v if data.draw(st.booleans()) else -v for v in constrained_vars]

        self.table.remove_matching(assignment)

        # Update model: remove assignments that match all literals in the assignment
        assignment_set = set(assignment)
        self.model = {a for a in self.model if not assignment_set.issubset(a)}

    @invariant()
    def sizes_match(self) -> None:
        """Table size should match model size."""
        assert len(self.table) == len(self.model)

    @invariant()
    def contents_match(self) -> None:
        """Table contents should match model exactly."""
        assert self._table_contents() == self.model

    @invariant()
    def variables_match(self) -> None:
        """Table variables should match tracked variables."""
        assert set(self.table.variables) == self.variables


TestSolutionTableStateMachine = SolutionTableStateMachine.TestCase

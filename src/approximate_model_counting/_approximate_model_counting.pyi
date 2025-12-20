"""Type stubs for the C++ extension module."""

from enum import Enum

class Status(Enum):
    """SAT solver result status."""

    SATISFIABLE: int
    UNSATISFIABLE: int
    UNKNOWN: int

class SolutionInformation:
    """Immutable view of a SAT problem with specific assumptions.

    Created via ModelCounter.with_assumptions(). Cannot be instantiated directly.
    """

    def solvable(self) -> Status:
        """Check if the problem is satisfiable with the assumptions."""
        ...
    def current_clauses(self) -> list[list[int]]:
        """Get clauses after unit propagation with assumptions.

        Returns the clauses after unit propagation:
        - Assumptions and their consequences appear as unit clauses
        - Satisfied clauses are removed
        - Falsified literals are removed from clauses
        - Duplicate clauses are skipped
        """
        ...

class ModelCounter:
    """SAT solver wrapper for model counting."""

    def __init__(self, clauses: list[list[int]]) -> None:
        """Create a ModelCounter with the given clauses."""
        ...
    def with_assumptions(self, assumptions: list[int]) -> SolutionInformation:
        """Create a SolutionInformation with the given assumptions."""
        ...

class SolutionTable:
    """Implicit representation of all satisfying assignments for a set of variables."""

    def __init__(self, variables: list[int]) -> None:
        """Create a SolutionTable with the given variables (max 63 variables)."""
        ...
    def __len__(self) -> int:
        """Get the number of possible assignments."""
        ...
    def __getitem__(self, index: int) -> list[int]:
        """Get the assignment at the given index."""
        ...
    def add_variable(self, variable: int) -> None:
        """Add a new variable to the table."""
        ...
    def remove_matching(self, assignment: list[int]) -> None:
        """Remove all rows matching the given assignment."""
        ...
    def clone(self) -> SolutionTable:
        """Create a copy of this SolutionTable."""
        ...
    def contains(self, variable: int) -> bool:
        """Check if a variable is in the table."""
        ...
    @property
    def variables(self) -> list[int]:
        """Get the list of variables in the table."""
        ...

class BooleanEquivalence:
    """Union-find data structure for boolean equivalences with negation support."""

    def __init__(self) -> None:
        """Create an empty BooleanEquivalence."""
        ...
    def find(self, literal: int) -> int:
        """Find the canonical representative of a literal.

        Raises ValueError if literal is 0.
        """
        ...
    def merge(self, a: int, b: int) -> None:
        """Merge two literals (assert they are equivalent).

        Raises RuntimeError if merging would create a contradiction (a = -a).
        """
        ...
    def num_representatives(self) -> int:
        """Get the number of equivalence classes."""
        ...

"""Type stubs for the C++ extension module."""

from enum import Enum

class Status(Enum):
    """SAT solver result status."""

    SATISFIABLE: int
    UNSATISFIABLE: int
    UNKNOWN: int

class SolutionInformation:
    """Wrapper around CaDiCaL SAT solver for solution counting."""

    def __init__(self) -> None: ...
    def solvable(self) -> Status:
        """Check if the current formula is satisfiable."""
        ...
    def add_clause(self, literals: list[int]) -> None:
        """Add a clause to the formula."""
        ...
    def add_assumption(self, literal: int) -> None:
        """Add an assumption (literal that must be true)."""
        ...
    def clear_assumptions(self) -> None:
        """Clear all assumptions."""
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

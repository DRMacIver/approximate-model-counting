"""Type stubs for the C++ extension module."""

from enum import Enum

def is_satisfiable(clauses: list[list[int]]) -> bool:
    """Check if a set of clauses is satisfiable."""
    ...

def find_solution(clauses: list[list[int]]) -> list[list[int]]:
    """Find a satisfying assignment.

    Returns [[solution]] if SAT, or [[]] if UNSAT.
    """
    ...

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
    def get_backbone(self) -> list[int]:
        """Get the backbone literals.

        Returns literals that must be true in all satisfying assignments.
        The backbone includes the assumptions and any literals forced by
        unit propagation or proven via SAT solving.

        Returns an empty list if UNSATISFIABLE.
        """
        ...
    def are_equivalent(self, a: int, b: int) -> bool:
        """Check if two literals are equivalent.

        Returns True if literals a and b must have the same value in all
        satisfying assignments. This includes the case where a and -b are
        always opposite (are_equivalent(a, -b) returns True).
        """
        ...
    def get_solution_table(self) -> SolutionTable:
        """Get the solution table for non-backbone variables.

        Returns a table where each row represents a partial assignment
        for variables not in the backbone. These assignments may be
        satisfiable when combined with the backbone.
        """
        ...
    def get_equivalence_classes(self) -> list[list[int]]:
        """Get equivalence classes for free variables.

        Returns a list of equivalence classes, where each class is a sorted
        list of variable numbers. Only classes with 2+ variables are returned.
        Variables in the same class have the same value in all solutions.
        """
        ...

class ModelCounter:
    """SAT solver wrapper for model counting."""

    def __init__(self, clauses: list[list[int]], seed: int | None = None) -> None:
        """Create a ModelCounter with the given clauses.

        If seed is provided, the random number generator is seeded for
        deterministic behavior. This ensures that repeated calls with the
        same seed produce identical results.
        """
        ...
    @staticmethod
    def from_file(path: str, seed: int | None = None) -> ModelCounter:
        """Create a ModelCounter by reading a DIMACS CNF file.

        Uses CaDiCaL's built-in parser.
        Raises RuntimeError if the file cannot be read or parsed.
        """
        ...
    def with_assumptions(self, assumptions: list[int]) -> SolutionInformation:
        """Create a SolutionInformation with the given assumptions."""
        ...
    def march_score(self, assumptions: list[int]) -> tuple[dict[int, float], list[int]]:
        """Calculate march-style variable scores.

        Returns a tuple of (scores, updated_assumptions) where:
        - scores: dict mapping variable (positive int) to its score
        - updated_assumptions: the input assumptions plus any forced literals
          discovered via failed literal detection
        """
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

class RefinablePartition:
    """Refinable partition of integers 0..size-1.

    Supports iterative refinement by marking elements to split partitions.
    """

    def __init__(self, size: int) -> None:
        """Create a partition of elements 0..size-1 (all in one partition)."""
        ...
    def __len__(self) -> int:
        """Get the number of partitions."""
        ...
    def __getitem__(self, index: int) -> list[int]:
        """Get elements in partition at index (supports negative indexing)."""
        ...
    def partition_of(self, element: int) -> int:
        """Get which partition an element is in."""
        ...
    def mark(self, values: list[int]) -> None:
        """Refine partitions by marking values.

        Marked values are moved to new partitions, splitting any partition
        that contains both marked and unmarked elements.
        """
        ...

class DecompositionNode:
    """A node in a decomposition tree of a variable interaction graph."""

    variables: list[int]
    """All variables at this node."""
    separator: list[int]
    """The split variables (empty for leaves)."""
    children: list[DecompositionNode]
    """One child per component (empty for leaves)."""
    def is_leaf(self) -> bool:
        """Return True if this is a leaf node (no children)."""
        ...

class VariableInteractionGraph:
    """Graph where variables are nodes and edges connect variables sharing a clause."""

    def __init__(self, clauses: list[list[int]]) -> None:
        """Build VIG from clauses.

        Extracts variables and creates edges between variables sharing a clause.
        """
        ...
    def variables(self) -> list[int]:
        """Get the sorted list of variables in the graph."""
        ...
    def num_edges(self) -> int:
        """Get the number of edges in the graph."""
        ...
    def decompose(self, n: int = 20) -> DecompositionNode:
        """Recursively decompose until components have at most n variables."""
        ...
    def find_separator(self, scope: list[int], excluded: set[int], n: int) -> list[int]:
        """Find the best n separator variables from scope.

        Variables in excluded are treated as already removed.
        """
        ...
    def enlarge_separator(
        self,
        current_separator: list[int],
        scope: list[int],
        excluded: set[int],
        n: int,
    ) -> list[int]:
        """Enlarge an existing separator to target size n.

        Returns current_separator plus the best additional variables,
        chosen by the same ranking as find_separator.
        """
        ...
    def connected_components(self, scope: list[int], excluded: set[int]) -> list[list[int]]:
        """Get connected components of scope after removing excluded variables."""
        ...

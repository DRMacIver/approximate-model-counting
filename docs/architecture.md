# Architecture

This project is a hybrid Python/C++ system for approximate model counting of SAT formulas. The C++ layer handles performance-critical SAT solving via the CaDiCaL solver, while Python provides the test suite, CLI/TUI, and high-level orchestration.

## Component Overview

```
                     Python Layer
                  +-----------------+
                  |   CLI (click)   |
                  |   TUI (textual) |
                  +--------+--------+
                           |
                  +--------v--------+
                  | Python package  |
                  | __init__.py     |
                  +--------+--------+
                           |  pybind11
                  +--------v--------+
                  | python_bindings |
                  +--------+--------+
                           |
                     C++ Layer
          +----------------+----------------+
          |                |                |
  +-------v------+  +-----v------+  +------v-------+
  | ModelCounter  |  |   Utils    |  | SolutionTable|
  | Solution-     |  | march_score|  | BitVector    |
  |  Information  |  | propagate  |  +--------------+
  +-------+-------+  +------------+
          |
  +-------v-------+  +-----------------+
  | Boolean-      |  | Refinable-      |
  |  Equivalence  |  |  Partition      |
  +---------------+  +-----------------+
          |
  +-------v-------+
  |   CaDiCaL     |
  |  SAT Solver   |
  +---------------+
```

## Core Classes

### ModelCounter

The entry point for working with SAT formulas. Create one from clauses or a DIMACS file:

```python
counter = ModelCounter([[1, 2], [-1, 3]], seed=42)
# or
counter = ModelCounter.from_file("formula.cnf", seed=42)
```

It owns a shared CaDiCaL solver instance and an RNG. Call `with_assumptions()` to create a `SolutionInformation` for a particular set of assumed literals. The solver is shared across all `SolutionInformation` instances, so only one can be actively computing at a time.

### SolutionInformation

Lazily computes everything about the solution space of the formula under given assumptions. On first access of any property, it runs the full analysis pipeline:

1. **Initial solve** - determine satisfiability
2. **Backbone detection** - find literals forced in all solutions
3. **Equivalence detection** - find literals that always have the same value
4. **Solution table construction** - build a compact table of possible assignments

The results are:
- `solvable()` - `Status.SATISFIABLE`, `UNSATISFIABLE`, or `UNKNOWN`
- `get_backbone()` - list of literals true in every solution (includes assumptions)
- `are_equivalent(a, b)` - whether two literals always agree
- `get_equivalence_classes()` - groups of equivalent variables
- `get_solution_table()` - compact representation of the solution space
- `current_clauses()` - simplified formula after unit propagation

### SolutionTable

An implicit representation of possible variable assignments. Instead of enumerating all 2^n assignments, it stores a compressed table that can be iteratively refined. Key operations:

- `add_variable(var)` - doubles the table size (each existing row splits into var=T and var=F)
- `remove_matching(core)` - removes rows matching a failed assignment
- `__getitem__(i)` - retrieves row i as a list of literals
- `__len__()` - current number of rows

Variables are added in order of their march score (highest first). After adding each variable, random rows are sampled and checked for satisfiability. Unsatisfiable rows are removed using the solver's conflict core. This continues until the row survives 10 consecutive checks or the table exceeds 1M rows.

### BooleanEquivalence

A union-find data structure for tracking literal equivalences. Handles the constraint that `find(x) = -find(-x)` (if x is equivalent to y, then -x is equivalent to -y). Returns equivalence classes containing 2+ variables.

### RefinablePartition

A partition refinement data structure. Elements start in a single partition. Calling `mark(subset)` splits each partition into "marked" and "unmarked" halves. Used during equivalence detection: each satisfying model marks the true literals, refining the partition until only genuinely equivalent literals remain in the same group.

## Build System

CMake fetches CaDiCaL and pybind11 from GitHub automatically. The Python packaging uses scikit-build-core to bridge CMake into uv/pip. The `Justfile` wraps all common operations.

```
CMakeLists.txt
  -> fetches CaDiCaL (rel-2.2.0) from GitHub
  -> fetches pybind11 (v2.13.6) from GitHub
  -> builds amc_core static library (all C++ sources)
  -> builds _approximate_model_counting (pybind11 module -> installed to package)
  -> builds _test_internals (test utilities -> installed to tests/)
  -> builds tool executables (analyze_cnf, test_* tools)

pyproject.toml
  -> scikit-build-core backend
  -> uv for dependency management
  -> pytest + hypothesis for testing
  -> ruff for formatting/linting
  -> basedpyright for type checking
```

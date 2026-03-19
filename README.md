# Approximate Model Counting

Approximate model counting for SAT formulas using Monte Carlo estimation methods.

Given a Boolean formula in CNF, this project computes structural information about the solution space: which variables are forced (backbone), which variables are equivalent, and a compact table of possible assignments. These provide lower bounds and structural insights for approximate model counting.

## How It Works

The core analysis pipeline for a formula proceeds in four phases:

1. **Satisfiability check** - determine if the formula has any solutions using CaDiCaL
2. **Backbone detection** - find literals that must be true in every solution, using iterative counter-model search with march-style variable scoring
3. **Equivalence detection** - find variables that always have the same (or opposite) values, using partition refinement
4. **Solution table construction** - build a compact table of possible variable assignments by incrementally adding variables and pruning unsatisfiable rows

See [docs/algorithms.md](docs/algorithms.md) for detailed algorithm descriptions.

## Quick Start

### Requirements

- Python 3.12+
- CMake 3.20+
- C++20 compatible compiler
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- [just](https://github.com/casey/just) for task running

### Build and Test

```bash
just build   # Build the project (fetches CaDiCaL and pybind11 automatically)
just test    # Run all tests
just check   # Run all checks (format, lint, test with 100% coverage)
```

### Usage

```python
from approximate_model_counting import ModelCounter, Status

# Create from clauses
counter = ModelCounter([[1, 2], [-1, 3], [-2, -3]], seed=42)

# Or from a DIMACS CNF file
counter = ModelCounter.from_file("formula.cnf", seed=42)

# Analyze with assumptions (empty list = no assumptions)
info = counter.with_assumptions([])

if info.solvable() == Status.SATISFIABLE:
    # Literals true in every solution
    backbone = info.get_backbone()

    # Groups of variables that always agree
    equiv_classes = info.get_equivalence_classes()

    # Compact table of possible assignments
    table = info.get_solution_table()
    print(f"{len(table)} possible assignment patterns")
```

### CLI

```bash
# Analyze a single file
amc formula.cnf --seed 42

# Analyze a directory of CNF files
amc benchmarks/data/2024/ --seed 42 -j 4

# Interactive TUI
amc benchmarks/data/2024/ --tui
```

### Benchmarks

Download Model Counting Competition benchmarks for testing:

```bash
cd benchmarks && python download.py
```

See [benchmarks/README.md](benchmarks/README.md) for details.

## Architecture

The project is a hybrid Python/C++ system. C++ handles the SAT solving and data structures via pybind11 bindings. Python provides testing (pytest + Hypothesis), CLI (click), and TUI (textual).

Key C++ components:
- **ModelCounter** - owns the CaDiCaL solver, creates `SolutionInformation` instances
- **SolutionInformation** - lazily computes backbone, equivalences, and solution table
- **SolutionTable** - implicit representation of possible assignments (max ~1M rows)
- **BooleanEquivalence** - union-find tracking literal equivalences (with negation)
- **RefinablePartition** - partition refinement for equivalence detection

See [docs/architecture.md](docs/architecture.md) for a full component diagram and detailed descriptions.

## Development

```bash
just format         # Format code (ruff for Python, clang-format for C++)
just check-format   # Check formatting
just lint           # Lint Python code
just test-coverage  # Run tests with 100% coverage requirement
just clean          # Clean build artifacts
```

See [docs/development.md](docs/development.md) for the full development guide.

## Status

This is an early-stage research project (v0.1.0). The core analysis pipeline works but the actual approximate counting algorithm is not yet implemented -- the current focus is on extracting structural information (backbone, equivalences, solution table) that will feed into a Monte Carlo counting approach.

Active areas of investigation:
- Handling UNKNOWN solver results when conflict limits are reached on hard subproblems
- Variable selection heuristics (see [notes/lookahead-sat-solving.txt](notes/lookahead-sat-solving.txt))
- Scaling to larger benchmarks from the Model Counting Competition

## License

TBD

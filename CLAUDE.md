# CLAUDE.md

This file provides guidance for Claude Code when working on this project.

## Project Overview

This is a hybrid Python/C++ project for exploring approximate model counting algorithms for SAT using Monte Carlo estimation methods. The C++ layer handles performance-critical operations using the CaDiCaL SAT solver, while Python provides testing, high-level algorithms, and the command-line interface.

## Build System

- **C++ build**: CMake with automatic fetching of CaDiCaL from GitHub
- **Python packaging**: uv + scikit-build-core + pybind11
- **Task runner**: Just (Justfile)

### Key Commands

```bash
just build          # Build the project
just test           # Run tests
just test-coverage  # Run tests with 100% coverage requirement (Python + C++)
just format         # Format all code (ruff for Python, clang-format for C++)
just check-format   # Check formatting without modifying
just lint           # Lint Python code
just clean          # Clean build artifacts
just check          # Run all checks (format, lint, coverage)
```

## Project Structure

```
src/
├── solution_information.hpp       # C++ headers
├── solution_information.cpp       # C++ implementation
└── approximate_model_counting/    # Python package
    └── __init__.py
bindings/
└── python_bindings.cpp            # pybind11 bindings
tests/
└── test_*.py                      # pytest tests (module-level, using Hypothesis)
```

## Code Standards

### C++
- **Standard**: C++20
- **Formatting**: clang-format (Google style base, 4-space indent, 100 char lines)
- **Namespace**: `amc`

### Python
- **Version**: 3.12+
- **Formatting**: ruff
- **Line length**: 100 characters

### Coverage
- **Requirement**: 100% for both Python and C++
- Coverage exclusions must include explanatory comments:
  ```cpp
  // Coverage exclusion: [reason why this line cannot be tested]
  return Status::UNKNOWN;  // LCOV_EXCL_LINE
  ```

## Testing

- Use pytest with module-level test functions (not class-based)
- Use Hypothesis heavily for property-based testing
- Test file naming: `test_*.py`
- Test function naming: `test_*`

## Architecture Notes

### SolutionInformation Class
Wraps a CaDiCaL solver instance with assumptions support:
- `add_clause(literals)` - Add a CNF clause
- `add_assumption(literal)` - Add a solving assumption
- `clear_assumptions()` - Clear all assumptions
- `solvable()` - Returns Status enum (SATISFIABLE, UNSATISFIABLE, UNKNOWN)

The UNKNOWN status is for future use with resource-limited solving (time/conflict limits).

### Python Bindings
- Status enum is exposed as a Python IntEnum-compatible type
- SolutionInformation is directly usable from Python
- Use relative imports in the Python package (`from ._approximate_model_counting import ...`)

## Dependencies

### Build-time
- CMake 3.20+
- C++20 compiler
- pybind11 (fetched by CMake)
- CaDiCaL (fetched by CMake)

### Runtime
- Python 3.12+

### Development
- uv (Python package management)
- just (task runner)
- lcov (C++ coverage - `brew install lcov` on macOS)
- clang-format (C++ formatting)
- ruff (Python formatting/linting)

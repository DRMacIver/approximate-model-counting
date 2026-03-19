# Development Guide

## Prerequisites

- Python 3.12+
- C++20 compatible compiler (clang or gcc)
- CMake 3.20+
- [uv](https://github.com/astral-sh/uv) - Python package manager
- [just](https://github.com/casey/just) - task runner
- clang-format - C++ formatting
- lcov - C++ coverage reporting (`brew install lcov` on macOS)

## Building

```bash
just build
```

This runs `uv sync` which triggers scikit-build-core to compile the C++ code via CMake. CaDiCaL and pybind11 are fetched automatically during the first build.

## Testing

```bash
just test           # Run all tests
just test-coverage  # Run with 100% coverage enforcement
```

Tests use pytest with Hypothesis for property-based testing. Test files are at the top level of `tests/` and use module-level functions (not classes).

Coverage is enforced at 100% for both Python (via pytest-cov) and C++ (via lcov). Any line excluded from coverage must have a comment explaining why:

```cpp
// Coverage exclusion: NRVO causes closing brace to appear uncovered
return result;  // LCOV_EXCL_LINE
```

## Code Style

```bash
just format       # Auto-format everything
just check-format # Check without modifying
just lint         # Lint Python code
just check        # Run all checks (format + lint + coverage)
```

- **Python**: ruff, 100-char lines
- **C++**: clang-format, Google style base, 4-space indent, 100-char lines
- **Namespace**: all C++ code is in `namespace amc`

## Project Layout

```
src/
  solution_information.{hpp,cpp}  - ModelCounter and SolutionInformation
  solution_table.{hpp,cpp}        - SolutionTable and BitVector
  boolean_equivalence.{hpp,cpp}   - Union-find for literal equivalences
  refinable_partition.{hpp,cpp}   - Partition refinement data structure
  utils.{hpp,cpp}                 - SAT utilities (is_satisfiable, march_score, etc.)
  approximate_model_counting/
    __init__.py                   - Python package (re-exports from C++ module)

bindings/
  python_bindings.cpp             - pybind11 bindings for all C++ types

tests/
  test_*.py                       - pytest test modules
  cpp/test_*.cpp                  - C++ test helpers exposed via pybind11
  coverage_data/                  - CNF files and expected-output JSON for tests

tools/
  analyze_benchmarks.py           - Benchmark analysis with equivalence detection
  analyze_cnf.cpp                 - C++ tool for CNF analysis
  test_*_unknown.cpp              - C++ tools for testing UNKNOWN handling

benchmarks/
  download.py                     - Download MC Competition benchmarks
  custom/                         - Hand-crafted test benchmarks
  data/                           - Downloaded benchmarks (gitignored)

notes/
  lookahead-sat-solving.txt       - Research notes on variable selection heuristics

scratch/                          - Experimental/WIP files (gitignored)
```

## Adding a New C++ Component

1. Create `src/newcomponent.{hpp,cpp}`
2. Add the `.cpp` to the `amc_core` target's source list in `CMakeLists.txt`
3. If it needs Python bindings, add them to `bindings/python_bindings.cpp`
4. If the Python bindings should be public, re-export from `src/approximate_model_counting/__init__.py`
5. Write tests in `tests/test_newcomponent.py`
6. Ensure 100% coverage with `just test-coverage`

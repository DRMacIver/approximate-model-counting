# Approximate Model Counting

Approximate model counting for SAT using Monte Carlo estimation methods.

This is a hybrid Python/C++ project that uses the CaDiCaL SAT solver for core solving functionality.

## Requirements

- Python 3.12+
- CMake 3.20+
- C++20 compatible compiler
- [uv](https://github.com/astral-sh/uv) for Python dependency management
- [just](https://github.com/casey/just) for task running
- clang-format for C++ formatting
- lcov for C++ coverage reporting (install with `brew install lcov` on macOS)

## Setup

Install dependencies and build the project:

```bash
just build
```

## Development

### Available Commands

- `just build` - Build the project
- `just test` - Run tests
- `just test-coverage` - Run tests with coverage (requires 100% coverage for both Python and C++)
- `just format` - Format all code (Python with ruff, C++ with clang-format)
- `just check-format` - Check code formatting
- `just lint` - Lint Python code
- `just lint-fix` - Fix linting issues
- `just clean` - Clean build artifacts
- `just check` - Run all checks (format, lint, test with coverage)

### Running Tests

```bash
just test
```

### Code Coverage

This project enforces 100% code coverage for both Python and C++:

```bash
just test-coverage
```

### Formatting

Format all code:

```bash
just format
```

Check formatting:

```bash
just check-format
```

## Usage

```python
from approximate_model_counting import SolutionInformation, Status

# Create a new solver instance
si = SolutionInformation()

# Add clauses (CNF formula)
si.add_clause([1, 2])      # (x1 OR x2)
si.add_clause([-1, 3])     # (NOT x1 OR x3)

# Check satisfiability
status = si.solvable()

if status == Status.SATISFIABLE:
    print("Formula is satisfiable")
elif status == Status.UNSATISFIABLE:
    print("Formula is unsatisfiable")
else:
    print("Unknown")

# Add assumptions (temporary constraints)
si.add_assumption(1)  # Assume x1 is true
status = si.solvable()

# Clear assumptions
si.clear_assumptions()
```

## Project Structure

```
approximate-model-counting/
├── src/                           # Source files
│   ├── solution_information.hpp   # C++ header
│   ├── solution_information.cpp   # C++ implementation
│   └── approximate_model_counting/ # Python package
│       └── __init__.py
├── bindings/                      # Python bindings (pybind11)
│   └── python_bindings.cpp
├── tests/                         # Python tests (pytest)
│   └── test_solution_information.py
├── CMakeLists.txt                 # CMake build configuration
├── pyproject.toml                 # Python project configuration
├── Justfile                       # Task runner commands
├── .clang-format                  # C++ formatting rules
└── README.md
```

## License

TBD

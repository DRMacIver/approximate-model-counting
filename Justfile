# Build the project
build:
    uv sync --all-extras
    uv pip install -e . --no-build-isolation

# Build with coverage instrumentation
build-coverage:
    uv sync --all-extras
    rm -rf build
    ENABLE_COVERAGE=ON SKBUILD_BUILD_DIR=build uv pip install -e . --no-build-isolation --force-reinstall

# Run tests
test:
    uv run pytest tests/ -v

# Run tests with coverage (Python + C++)
test-coverage:
    #!/usr/bin/env bash
    set -euo pipefail

    # Check for required tools
    if ! command -v lcov &> /dev/null; then
        echo "Error: lcov is required for C++ coverage but not found"
        echo "Install it with: brew install lcov (on macOS) or apt-get install lcov (on Linux)"
        exit 1
    fi

    # Clean previous coverage data
    find . -name "*.gcda" -delete
    find . -name "*.gcno" -delete
    rm -rf htmlcov coverage.xml .coverage coverage.info coverage_all.info

    # Build with coverage
    just build-coverage

    # Run Python tests with coverage
    uv run pytest tests/ --cov=approximate_model_counting --cov-report=html --cov-report=term --cov-fail-under=100

    # Generate C++ coverage report
    echo "Generating C++ coverage report..."
    mkdir -p build/gcov
    # Capture coverage from build directory to avoid .gcov files in project root
    # (gcov creates files in the current directory)
    pushd build/gcov > /dev/null
    lcov --capture --directory .. --output-file ../coverage_all.info \
        --ignore-errors mismatch,inconsistent,unsupported,format
    popd > /dev/null
    # Keep only our source files (exclude _deps which contains third-party code)
    lcov --extract build/coverage_all.info \
        '*/approximate-model-counting/src/*.cpp' \
        '*/approximate-model-counting/bindings/*.cpp' \
        --output-file coverage.info \
        --ignore-errors inconsistent
    lcov --list coverage.info

    # Check C++ coverage is 100%
    COVERAGE=$(lcov --summary coverage.info 2>&1 | grep "lines" | awk '{print $2}' | sed 's/%//')
    if [ -z "$COVERAGE" ]; then
        echo "Error: Could not determine C++ coverage"
        exit 1
    fi
    if (( $(echo "$COVERAGE < 100" | bc -l) )); then
        echo "C++ coverage is $COVERAGE%, required 100%"
        exit 1
    fi
    echo "C++ coverage: $COVERAGE%"

# Format all code
format:
    uv run ruff format .
    find src bindings -name "*.cpp" -o -name "*.hpp" | xargs clang-format -i

# Check formatting
check-format:
    uv run ruff format --check .
    find src bindings -name "*.cpp" -o -name "*.hpp" | xargs clang-format --dry-run -Werror

# Lint Python code
lint:
    uv run ruff check .

# Type check Python code
typecheck:
    uv run basedpyright

# Fix linting issues
lint-fix:
    uv run ruff check --fix .

# Clean build artifacts
clean:
    rm -rf build dist *.egg-info
    rm -rf htmlcov .coverage coverage.xml coverage.info coverage_all.info
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.so" -delete
    find . -name "*.gcda" -delete
    find . -name "*.gcno" -delete
    find . -name "*.gcov" -delete

# Run all checks (format, lint, typecheck, test with coverage)
check: check-format lint typecheck test-coverage

# Default target
default: build

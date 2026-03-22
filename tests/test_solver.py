"""Tests for the PySAT-compatible Solver wrapper."""

import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from approximate_model_counting import Solver

# --- Construction ---


def test_empty_solver():
    s = Solver()
    assert s.nof_vars() == 0
    assert s.nof_clauses() == 0


def test_bootstrap_with():
    s = Solver(bootstrap_with=[[1, 2], [-1, 3]])
    assert s.nof_clauses() == 2
    assert s.solve()


def test_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as f:
        f.write("p cnf 3 2\n1 2 0\n-1 3 0\n")
        path = f.name
    s = Solver.from_file(path)
    assert s.nof_vars() == 3
    assert s.nof_clauses() == 2
    assert s.solve()


def test_from_file_nonexistent():
    with pytest.raises(RuntimeError, match="Failed to read DIMACS file"):
        Solver.from_file("/nonexistent/file.cnf")


# --- add_clause / append_formula ---


def test_add_clause():
    s = Solver()
    s.add_clause([1, 2])
    s.add_clause([-1, -2])
    assert s.nof_clauses() == 2
    assert s.solve()


def test_append_formula():
    s = Solver()
    s.append_formula([[1, 2], [-1, -2]])
    assert s.nof_clauses() == 2
    assert s.solve()


# --- solve ---


def test_solve_sat():
    s = Solver(bootstrap_with=[[1, 2]])
    assert s.solve() is True


def test_solve_unsat():
    s = Solver(bootstrap_with=[[1], [-1]])
    assert s.solve() is False


def test_solve_with_assumptions_sat():
    s = Solver(bootstrap_with=[[1, 2]])
    assert s.solve(assumptions=[1]) is True


def test_solve_with_assumptions_unsat():
    s = Solver(bootstrap_with=[[1, 2]])
    assert s.solve(assumptions=[-1, -2]) is False


# --- get_model ---


def test_get_model_sat():
    s = Solver(bootstrap_with=[[1], [2]])
    s.solve()
    model = s.get_model()
    assert model is not None
    assert 1 in model
    assert 2 in model


def test_get_model_unsat():
    s = Solver(bootstrap_with=[[1], [-1]])
    s.solve()
    assert s.get_model() is None


def test_get_model_before_solve():
    s = Solver(bootstrap_with=[[1]])
    assert s.get_model() is None


def test_model_satisfies_clauses():
    clauses = [[1, 2, 3], [-1, -2], [-2, -3], [1, 3]]
    s = Solver(bootstrap_with=clauses)
    assert s.solve()
    model = s.get_model()
    assert model is not None
    model_set = set(model)
    for clause in clauses:
        assert any(lit in model_set for lit in clause)


# --- get_core ---


def test_get_core_unsat():
    s = Solver(bootstrap_with=[[1, 2]])
    s.solve(assumptions=[-1, -2])
    core = s.get_core()
    assert core is not None
    assert len(core) > 0
    # Core should be a subset of assumptions
    assert set(core) <= {-1, -2}


def test_get_core_sat():
    s = Solver(bootstrap_with=[[1, 2]])
    s.solve(assumptions=[1])
    assert s.get_core() is None


def test_get_core_before_solve():
    s = Solver(bootstrap_with=[[1]])
    assert s.get_core() is None


# --- propagate ---


def test_propagate_unit():
    s = Solver(bootstrap_with=[[1], [-1, 2]])
    status, lits = s.propagate()
    assert status is True
    assert 1 in lits
    assert 2 in lits


def test_propagate_conflict():
    s = Solver(bootstrap_with=[[1], [-1]])
    status, _ = s.propagate()
    assert status is False


def test_propagate_with_assumptions():
    s = Solver(bootstrap_with=[[-1, 2], [-2, 3]])
    status, lits = s.propagate(assumptions=[1])
    assert status is True
    assert 1 in lits
    assert 2 in lits
    assert 3 in lits


# --- solve_limited ---


def test_solve_limited_sat():
    s = Solver(bootstrap_with=[[1, 2]])
    result = s.solve_limited()
    assert result is True


def test_solve_limited_unsat():
    s = Solver(bootstrap_with=[[1], [-1]])
    result = s.solve_limited()
    assert result is False


def test_solve_limited_with_assumptions():
    s = Solver(bootstrap_with=[[1, 2]])
    assert s.solve_limited(assumptions=[1]) is True
    assert s.solve_limited(assumptions=[-1, -2]) is False


def test_solve_limited_unknown():
    """A zero conflict budget on a hard-enough problem returns None (UNKNOWN)."""
    # Build a formula that can't be solved by unit propagation alone.
    # Use a large random-looking 3-SAT instance.
    import random

    rng = random.Random(42)
    n_vars = 100
    clauses = []
    for _ in range(400):
        lits = rng.sample(range(1, n_vars + 1), 3)
        clauses.append([v if rng.random() < 0.5 else -v for v in lits])
    s = Solver(bootstrap_with=clauses)
    s.conf_budget(0)
    result = s.solve_limited()
    assert result is None


# --- budgets ---


def test_conf_budget():
    s = Solver(bootstrap_with=[[1, 2]])
    s.conf_budget(1000)
    assert s.solve()
    s.conf_budget()  # reset


def test_prop_budget():
    s = Solver(bootstrap_with=[[1, 2]])
    s.prop_budget(1000)
    assert s.solve()
    s.prop_budget()  # reset


# --- context manager ---


def test_context_manager():
    with Solver(bootstrap_with=[[1, 2]]) as s:
        assert s.solve()
        model = s.get_model()
        assert model is not None


# --- incremental solving ---


def test_incremental():
    s = Solver()
    s.add_clause([1, 2])
    assert s.solve()
    s.add_clause([-1])
    assert s.solve()
    model = s.get_model()
    assert model is not None
    assert -1 in model
    assert 2 in model
    s.add_clause([-2])
    assert s.solve() is False


# --- property-based tests ---


clause_strategy = st.lists(
    st.integers(min_value=-20, max_value=20).filter(lambda x: x != 0), min_size=1, max_size=5
)


@given(st.lists(clause_strategy, min_size=1, max_size=20))
@settings(max_examples=50)
def test_model_satisfies_formula(clauses):
    s = Solver(bootstrap_with=clauses)
    if s.solve():
        model = s.get_model()
        assert model is not None
        model_set = set(model)
        for clause in clauses:
            assert any(lit in model_set for lit in clause)


@given(st.lists(clause_strategy, min_size=1, max_size=20))
@settings(max_examples=50)
def test_solve_agrees_with_is_satisfiable(clauses):
    from approximate_model_counting import is_satisfiable

    s = Solver(bootstrap_with=clauses)
    assert s.solve() == is_satisfiable(clauses)

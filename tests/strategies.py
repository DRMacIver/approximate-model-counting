"""Hypothesis strategies for SAT formula generation."""

import operator

from hypothesis import assume
from hypothesis import strategies as st

from approximate_model_counting import find_solution as _find_solution
from approximate_model_counting import is_satisfiable


def find_solution(clauses: list[list[int]]) -> list[int] | None:
    """Find a satisfying assignment, or None if UNSAT."""
    result = _find_solution(clauses)
    if result == [[]]:
        return None
    return result[0]


@st.composite
def sat_clauses(draw, min_clause_size=1, max_variables=100):
    """Generate random SAT clauses."""
    n_variables = draw(st.integers(min_clause_size, max_variables))
    variables = range(1, n_variables + 1)

    literal = st.builds(operator.mul, st.sampled_from(variables), st.sampled_from((-1, 1)))

    clauses: list[list[int]] = []
    for max_size in [1, 2, 3, max_variables]:
        if max_size < min_clause_size:
            continue
        clauses.extend(
            draw(
                st.lists(
                    st.lists(
                        literal,
                        unique_by=abs,
                        min_size=min_clause_size,
                        max_size=max_size,
                    ),
                    min_size=0,
                    unique_by=frozenset,
                )
            )
        )

    assume(clauses)
    return clauses


@st.composite
def satisfiable_clauses(draw, min_clause_size=1, max_variables=10):
    """Generate satisfiable SAT clauses."""
    base = draw(sat_clauses(min_clause_size=min_clause_size, max_variables=max_variables))
    clauses: list[list[int]] = []
    for b in base:
        if is_satisfiable(clauses + [b]):
            clauses.append(b)

    assume(clauses)
    return clauses


@st.composite
def unsatisfiable_clauses(draw, min_clause_size=1, max_variables=8):
    """Generate unsatisfiable SAT clauses by adding conflict clauses."""
    clauses = draw(sat_clauses(min_clause_size=min_clause_size, max_variables=max_variables))
    assume(clauses)

    # Keep adding clauses that rule out solutions until UNSAT
    for _ in range(100):  # Limit iterations
        sol = find_solution(clauses)
        if sol is None:
            return clauses
        # Rule out this solution
        subset = draw(st.lists(st.sampled_from(sol), min_size=min_clause_size, unique=True))
        if subset:
            clauses.append([-lit for lit in subset])

    assume(False)  # Failed to make UNSAT
    return clauses


@st.composite
def has_unique_solution(draw, max_variables=6):
    """Generate clauses with exactly one satisfying assignment."""
    clauses = draw(sat_clauses(min_clause_size=2, max_variables=max_variables))
    sol = find_solution(clauses)
    assume(sol is not None)
    assert sol is not None  # For type checker

    # Keep ruling out alternative solutions
    for _ in range(50):
        other_sol = find_solution(clauses + [[-lit for lit in sol]])
        if other_sol is None:
            assert is_satisfiable(clauses)
            return clauses

        to_rule_out = sorted(set(other_sol) - set(sol))
        if not to_rule_out:
            break
        subset = draw(
            st.lists(
                st.sampled_from(to_rule_out),
                min_size=min(2, len(to_rule_out)),
                unique=True,
            )
        )
        if subset:
            clauses.append([-lit for lit in subset])

    assume(False)
    return clauses

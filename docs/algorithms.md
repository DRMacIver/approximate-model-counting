# Algorithms

This document explains the key algorithms used in the project's analysis pipeline.

## Analysis Pipeline

When `SolutionInformation.calculate()` runs, it performs four phases in sequence:

### Phase 1: Initial Solve

The formula (with assumptions) is checked for satisfiability using CaDiCaL. If unsatisfiable, computation stops immediately. If satisfiable, the first model is recorded and used to seed the subsequent phases.

### Phase 2: Backbone Detection

The **backbone** of a formula is the set of literals that must be true in every satisfying assignment. For example, if every solution has x3=true, then literal 3 is in the backbone.

The algorithm:

1. Start with the first model's literals as candidates.
2. Remove any literals already known from assumptions.
3. Order candidates by march score (highest first).
4. For the best candidate literal L, try to find a solution with -L assumed (plus the known backbone).
5. If a counter-model is found: discard all candidates not present in this new model.
6. If no counter-model exists (UNSAT): L is in the backbone. Additionally, use CaDiCaL's `propagate()`/`implied()` to collect all literals implied by the current backbone, adding them too.
7. Repeat until no candidates remain.

This is efficient because each counter-model eliminates multiple candidates at once, and implied literal collection avoids testing backbone members one by one.

### Phase 3: Equivalence Detection

Two non-backbone variables are **equivalent** if they always have the same value in every solution (or always opposite values). The algorithm uses partition refinement:

1. Start with all 2n literal-indices in a single partition.
2. Each satisfying model found during backbone detection refines the partition: literals set to true are "marked", splitting each partition into true/false halves.
3. For each remaining non-singleton partition, test whether members are genuinely equivalent:
   - Pick two literals x, y from the same partition.
   - Try to satisfy the formula with {x, -y} or {-x, y} (plus the backbone).
   - If satisfiable: the new model further refines the partition.
   - If both are UNSAT: x and y are equivalent; merge them in the `BooleanEquivalence` structure.
4. Repeat until all partitions are singletons or fully merged.

### Phase 4: Solution Table Construction

The solution table provides a compact representation of the possible assignments to non-backbone, non-equivalent variables. It works with **representative variables** (one per equivalence class).

1. Simplify the formula: propagate backbone literals, normalize equivalent literals, deduplicate clauses.
2. Rank remaining variables by march score.
3. For each variable (highest score first):
   - Add it to the table (doubling the row count).
   - Validate by randomly sampling rows and checking satisfiability.
   - If a row is UNSAT, extract the conflict core and remove all matching rows.
   - Stop adding variables if the table exceeds 1M rows.
   - Move on after a row survives 10 consecutive satisfiability checks.

The result is a table where each row represents a partial assignment that is *likely* satisfiable, providing a lower bound on the model count.

## March Score (Variable Selection)

Variables are ranked using the march heuristic from lookahead SAT solvers. For each variable x:

```
score(x) = reduction(x=true) * reduction(x=false)
```

Where `reduction` is the weighted count of clauses shortened by unit propagation after assuming x's polarity. The weighting follows:

```
weight(k) = 5^(2-k)
```

So binary clauses (k=2) get weight 1, ternary (k=3) get 0.2, etc. This reflects that shorter clauses are exponentially more constraining.

The product combination favors balanced variables (where both polarities are similarly constraining), which tends to minimize search tree size.

**Failed literal detection**: If propagating a literal causes a conflict, its negation is immediately forced and added to the assumptions. This is a sound inference that simplifies the formula.

## Conflict Limits

All SAT solver calls use a conflict limit of 100. This means the solver may return UNKNOWN (status 0) instead of a definitive SAT/UNSAT answer for hard subproblems. Currently, the project does not handle UNKNOWN gracefully — this is an area of active development (see the `scratch/` directory for experimental work on this).

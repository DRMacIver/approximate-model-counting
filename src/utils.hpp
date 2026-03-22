#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include "cadical.hpp"

namespace amc {

// Parse a DIMACS CNF file and return the clauses.
// Throws std::runtime_error if the file cannot be read or parsed.
std::vector<std::vector<int>> parse_dimacs(const std::string& path);

// Check if a set of clauses is satisfiable.
bool is_satisfiable(const std::vector<std::vector<int>>& clauses);

// Find a satisfying assignment.
// Returns {{solution}} if SAT, or {{}} (vector containing empty vector) if UNSAT.
std::vector<std::vector<int>> find_solution(const std::vector<std::vector<int>>& clauses);

// Propagate assumptions and return simplified clauses.
// - Assumptions and their consequences appear as unit clauses
// - Satisfied clauses are removed
// - Falsified literals are removed from clauses
// - Duplicate clauses are skipped
// Returns {{}} (vector containing empty clause) if propagation detects a conflict.
std::vector<std::vector<int>> propagate_and_simplify(CaDiCaL::Solver& solver,
                                                     const std::vector<int>& assumptions);

// Calculate march-style variable scores using weighted clause reduction.
//
// For each variable not fixed by assumptions, computes:
//   score(x) = reduction(x=true) × reduction(x=false)
//
// where reduction is the weighted count of clauses reduced by unit propagation,
// using weights γ^(2-k) with γ=5 (binary=1, ternary=0.2, etc.).
//
// Failed literal detection: If propagating a literal causes a conflict, its
// negation is forced true, added to assumptions, and scoring restarts.
//
// Parameters:
//   solver - CaDiCaL solver with clauses loaded
//   assumptions - mutable list of assumed literals; may grow if failed literals found
//
// Returns:
//   Map from variable (positive int) to its score. Only includes variables
//   that appear in at least one clause and are not fixed by assumptions.
std::unordered_map<int, double> march_score(CaDiCaL::Solver& solver, std::vector<int>& assumptions);

}  // namespace amc

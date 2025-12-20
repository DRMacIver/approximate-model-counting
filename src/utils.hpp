#pragma once

#include <vector>

#include "cadical.hpp"

namespace amc {

// Propagate assumptions and return simplified clauses.
// - Assumptions and their consequences appear as unit clauses
// - Satisfied clauses are removed
// - Falsified literals are removed from clauses
// - Duplicate clauses are skipped
// Returns {{}} (vector containing empty clause) if propagation detects a conflict.
std::vector<std::vector<int>> propagate_and_simplify(CaDiCaL::Solver& solver,
                                                     const std::vector<int>& assumptions);

}  // namespace amc

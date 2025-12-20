#include "utils.hpp"

#include <algorithm>
#include <cassert>
#include <set>
#include <unordered_set>

namespace amc {

namespace {

// Helper class to collect clauses from CaDiCaL's traverse_clauses
class ClauseCollector : public CaDiCaL::ClauseIterator {
public:
    std::vector<std::vector<int>>& clauses;

    explicit ClauseCollector(std::vector<std::vector<int>>& c) : clauses(c) {}

    bool clause(const std::vector<int>& c) override {
        clauses.push_back(c);
        return true;  // continue traversal
    }
};

}  // namespace

std::vector<std::vector<int>> propagate_and_simplify(CaDiCaL::Solver& solver,
                                                     const std::vector<int>& assumptions) {
    // Set assumptions and propagate using CaDiCaL
    for (int lit : assumptions) {
        solver.assume(lit);
    }

    int result = solver.propagate();
    if (result == 20) {
        // Conflict detected during propagation
        return {{}};
    }

    // Get all implied literals (includes assumptions and their consequences)
    std::vector<int> implied_lits;
    solver.implied(implied_lits);
    std::unordered_set<int> fixed(implied_lits.begin(), implied_lits.end());

    // Get all clauses from the solver
    std::vector<std::vector<int>> clauses;
    ClauseCollector collector(clauses);
    solver.traverse_clauses(collector);

    // Simplify clauses using the fixed literals
    // Use set for deduplication (clauses are sorted for comparison)
    std::set<std::vector<int>> result_set;

    // Add unit clauses for all fixed literals
    for (int lit : fixed) {
        result_set.insert({lit});
    }

    // Process remaining clauses
    for (auto& clause : clauses) {
        // Check if clause is satisfied by any fixed literal
        bool satisfied = false;
        std::vector<int> simplified;

        for (int lit : clause) {
            if (fixed.count(lit)) {
                satisfied = true;
                break;
            }
            // Keep literal if its negation is not fixed
            if (!fixed.count(-lit)) {
                simplified.push_back(lit);
            }
        }

        if (!satisfied) {
            // Empty clause shouldn't happen since propagate() didn't conflict
            assert(!simplified.empty());
            // LCOV_EXCL_START - defensive assertion: implied() already returns all unit-propagated
            // literals
            if (simplified.size() == 1) {
                // Unit clause should already be in fixed via implied()
                assert(fixed.count(simplified[0]));
            } else {
                // LCOV_EXCL_STOP
                // Non-unit unsatisfied clause - add to result
                std::sort(simplified.begin(), simplified.end());
                result_set.insert(std::move(simplified));
            }
        }
    }

    return {result_set.begin(), result_set.end()};
}

}  // namespace amc

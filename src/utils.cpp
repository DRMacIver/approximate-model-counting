#include "utils.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <set>
#include <unordered_set>

namespace amc {

namespace {

// March scoring weight: γ^(2-k) where γ=5
// Binary clauses (k=2) have weight 1, ternary (k=3) have weight 0.2, etc.
constexpr double GAMMA = 5.0;

double clause_weight(size_t size) {
    if (size < 2)
        return 0.0;
    return std::pow(GAMMA, 2.0 - static_cast<double>(size));
}

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

std::unordered_map<int, double> march_score(CaDiCaL::Solver& solver,
                                            std::vector<int>& assumptions) {
    // Restart loop - we restart at the end of each pass if any failed literals were found
    while (true) {
        // Get simplified clauses after propagating assumptions
        auto all_clauses = propagate_and_simplify(solver, assumptions);

        // Check for conflict (empty clause)
        if (all_clauses.size() == 1 && all_clauses[0].empty()) {
            return {};
        }

        // Separate unit clauses (fixed literals) from non-unit clauses
        std::unordered_set<int> fixed;
        std::vector<std::vector<int>> clauses;
        for (const auto& clause : all_clauses) {
            if (clause.size() == 1) {
                fixed.insert(clause[0]);
            } else {
                clauses.push_back(clause);
            }
        }

        // Find all variables that appear in non-unit clauses (these are unfixed)
        std::unordered_set<int> unfixed_vars;
        for (const auto& clause : clauses) {
            for (int lit : clause) {
                unfixed_vars.insert(std::abs(lit));
            }
        }

        // Compute base weight of non-unit clauses
        double base_weight = 0.0;
        for (const auto& clause : clauses) {
            base_weight += clause_weight(clause.size());
        }

        // Calculate scores for each unfixed variable
        std::unordered_map<int, double> scores;
        std::unordered_set<int> newly_fixed;  // Track vars fixed by failed literal detection
        size_t assumptions_start = assumptions.size();

        for (int var : unfixed_vars) {
            // Skip if this variable was already determined to be fixed in this pass
            if (newly_fixed.count(var)) {
                continue;
            }

            double pos_reduction = 0.0;
            double neg_reduction = 0.0;
            bool pos_failed = false;
            bool neg_failed = false;

            // Try positive literal
            std::vector<int> pos_assumptions = assumptions;
            pos_assumptions.push_back(var);
            auto pos_clauses = propagate_and_simplify(solver, pos_assumptions);

            if (pos_clauses.size() == 1 && pos_clauses[0].empty()) {
                // Conflict: var is a failed literal, -var must be true
                pos_failed = true;
                assumptions.push_back(-var);
                newly_fixed.insert(var);
            } else {
                // Calculate remaining weight after propagating +var
                double pos_remaining = 0.0;
                for (const auto& clause : pos_clauses) {
                    if (clause.size() >= 2) {
                        pos_remaining += clause_weight(clause.size());
                    }
                }
                pos_reduction = base_weight - pos_remaining;
            }

            // Try negative literal (only if positive didn't fail)
            if (!pos_failed) {
                std::vector<int> neg_assumptions = assumptions;
                neg_assumptions.push_back(-var);
                auto neg_clauses = propagate_and_simplify(solver, neg_assumptions);

                if (neg_clauses.size() == 1 && neg_clauses[0].empty()) {
                    // Conflict: -var is a failed literal, var must be true
                    neg_failed = true;
                    assumptions.push_back(var);
                    newly_fixed.insert(var);
                } else {
                    // Calculate remaining weight after propagating -var
                    double neg_remaining = 0.0;
                    for (const auto& clause : neg_clauses) {
                        if (clause.size() >= 2) {
                            neg_remaining += clause_weight(clause.size());
                        }
                    }
                    neg_reduction = base_weight - neg_remaining;
                }
            }

            // Only record score if neither polarity failed
            if (!pos_failed && !neg_failed) {
                scores[var] = pos_reduction * neg_reduction;
            }
        }

        // Restart if any new literals were learned during this pass
        if (assumptions.size() > assumptions_start) {
            continue;
        }

        return scores;
    }
}

}  // namespace amc

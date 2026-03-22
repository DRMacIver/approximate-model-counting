#include "utils.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <set>
#include <stdexcept>
#include <unordered_set>

namespace amc {

namespace {

// March scoring weight: γ^(2-k) where γ=5
// Binary clauses (k=2) have weight 1, ternary (k=3) have weight 0.2, etc.
constexpr double GAMMA = 5.0;

double clause_weight(size_t size) {
    // If a clause reduces to size < 2, either:
    // - size 0 = conflict (caught earlier by propagate_and_simplify returning {{}})
    // - size 1 = unit propagation would have caught it and added to pos_fixed,
    //            making the clause satisfied rather than reduced
    assert(size >= 2);
    return std::pow(GAMMA, 2.0 - static_cast<double>(size));
}

// Helper class to collect clauses from CaDiCaL's traverse_clauses
class ClauseCollector final : public CaDiCaL::ClauseIterator {
public:
    std::vector<std::vector<int>>& clauses;

    explicit ClauseCollector(std::vector<std::vector<int>>& c) : clauses(c) {}

    bool clause(const std::vector<int>& c) override {
        clauses.push_back(c);
        return true;  // continue traversal
    }
};

}  // namespace

std::vector<std::vector<int>> parse_dimacs(const std::string& path) {
    CaDiCaL::Solver solver;
    solver.set("quiet", 1);
    int vars = 0;
    const char* error = solver.read_dimacs(path.c_str(), vars, 1);
    if (error) {
        throw std::runtime_error(std::string("Failed to read DIMACS file: ") + error);
    }
    std::vector<std::vector<int>> clauses;
    ClauseCollector collector(clauses);
    solver.traverse_clauses(collector);
    return clauses;
}

bool is_satisfiable(const std::vector<std::vector<int>>& clauses) {
    CaDiCaL::Solver solver;
    for (const auto& clause : clauses) {
        for (int lit : clause) {
            solver.add(lit);
        }
        solver.add(0);
    }
    return solver.solve() == 10;
}

std::vector<std::vector<int>> find_solution(const std::vector<std::vector<int>>& clauses) {
    CaDiCaL::Solver solver;
    for (const auto& clause : clauses) {
        for (int lit : clause) {
            solver.add(lit);
        }
        solver.add(0);
    }
    if (solver.solve() != 10) {
        return {{}};  // Empty clause = UNSAT
    }
    std::vector<int> solution;
    for (int var = 1; var <= solver.vars(); var++) {
        solution.push_back(solver.val(var));
    }
    return {solution};
}

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

        // Calculate scores for each unfixed variable
        std::unordered_map<int, double> scores;
        std::unordered_set<int> newly_fixed;  // Track vars fixed by failed literal detection
        size_t assumptions_start = assumptions.size();

        for (int var : unfixed_vars) {
            // unfixed_vars is a set (each var appears once), and we only add the current
            // var to newly_fixed. We never revisit processed vars.
            assert(newly_fixed.count(var) == 0);

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
                // Get implied literals after propagation
                std::unordered_set<int> pos_fixed;
                for (const auto& clause : pos_clauses) {
                    if (clause.size() == 1) {
                        pos_fixed.insert(clause[0]);
                    }
                }

                // Calculate weighted reduction for positive polarity
                // For each base clause, check if satisfied or reduced
                for (const auto& clause : clauses) {
                    bool satisfied = false;
                    size_t reduced_size = 0;

                    for (int lit : clause) {
                        if (pos_fixed.count(lit)) {
                            satisfied = true;
                            break;
                        }
                        if (!pos_fixed.count(-lit)) {
                            reduced_size++;
                        }
                    }

                    if (!satisfied && reduced_size < clause.size()) {
                        pos_reduction += clause_weight(reduced_size);
                    }
                }
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
                    // Get implied literals after propagation
                    std::unordered_set<int> neg_fixed;
                    for (const auto& clause : neg_clauses) {
                        if (clause.size() == 1) {
                            neg_fixed.insert(clause[0]);
                        }
                    }

                    // Calculate weighted reduction for negative polarity
                    for (const auto& clause : clauses) {
                        bool satisfied = false;
                        size_t reduced_size = 0;

                        for (int lit : clause) {
                            if (neg_fixed.count(lit)) {
                                satisfied = true;
                                break;
                            }
                            if (!neg_fixed.count(-lit)) {
                                reduced_size++;
                            }
                        }

                        if (!satisfied && reduced_size < clause.size()) {
                            neg_reduction += clause_weight(reduced_size);
                        }
                    }
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

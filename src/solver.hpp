#pragma once

#include <memory>
#include <optional>
#include <vector>

#include "cadical.hpp"

namespace amc {

// PySAT-compatible SAT solver interface wrapping CaDiCaL.
class Solver {
public:
    explicit Solver(const std::vector<std::vector<int>>& bootstrap_with = {});

    // Load from a DIMACS CNF file.
    static Solver from_file(const std::string& path);

    ~Solver();

    // Allow move, disallow copy
    Solver(Solver&&) = default;
    Solver& operator=(Solver&&) = default;
    Solver(const Solver&) = delete;
    Solver& operator=(const Solver&) = delete;

    // Add a single clause.
    void add_clause(const std::vector<int>& clause);

    // Add multiple clauses.
    void append_formula(const std::vector<std::vector<int>>& formula);

    // Solve with optional assumptions.
    // Returns true if SAT, false if UNSAT.
    bool solve(const std::vector<int>& assumptions = {});

    // Solve with resource limits. Returns true (SAT), false (UNSAT),
    // or nullopt (UNKNOWN/budget exhausted).
    std::optional<bool> solve_limited(const std::vector<int>& assumptions = {});

    // Get the satisfying assignment from the last successful solve().
    // Returns nullopt if the last call was UNSAT or no solve has been performed.
    std::optional<std::vector<int>> get_model() const;

    // Get the unsatisfiable core (subset of assumptions) from the last
    // UNSAT solve(). Returns nullopt if SAT or no assumptions were used.
    std::optional<std::vector<int>> get_core() const;

    // Unit propagation under assumptions without full solving.
    // Returns (status, propagated_literals) where status is true if
    // no conflict, false if conflict detected.
    std::pair<bool, std::vector<int>> propagate(const std::vector<int>& assumptions = {});

    // Number of variables in the solver.
    int nof_vars() const;

    // Number of clauses added.
    int nof_clauses() const;

    // Set conflict budget for solve_limited(). -1 = unlimited.
    void conf_budget(int budget = -1);

    // Set propagation budget for solve_limited(). -1 = unlimited.
    void prop_budget(int budget = -1);

private:
    std::unique_ptr<CaDiCaL::Solver> solver_;
    int last_result_ = 0;  // 0=unknown, 10=SAT, 20=UNSAT
    std::vector<int> last_assumptions_;
    int num_clauses_ = 0;
};

}  // namespace amc

#include "solver.hpp"

#include <stdexcept>

namespace amc {

Solver::Solver(const std::vector<std::vector<int>>& bootstrap_with)
    : solver_(std::make_unique<CaDiCaL::Solver>()) {
    solver_->set("quiet", 1);
    for (const auto& clause : bootstrap_with) {
        add_clause(clause);
    }
}

Solver Solver::from_file(const std::string& path) {
    Solver s;
    int vars = 0;
    const char* error = s.solver_->read_dimacs(path.c_str(), vars, 1);
    if (error) {
        throw std::runtime_error(std::string("Failed to read DIMACS file: ") + error);
    }
    // We don't know the exact clause count from read_dimacs, but
    // CaDiCaL tracks it internally. We approximate via irredundant().
    s.num_clauses_ = static_cast<int>(s.solver_->irredundant());
    return s;
}

Solver::~Solver() = default;

void Solver::add_clause(const std::vector<int>& clause) {
    for (int lit : clause) {
        solver_->add(lit);
    }
    solver_->add(0);
    num_clauses_++;
}

void Solver::append_formula(const std::vector<std::vector<int>>& formula) {
    for (const auto& clause : formula) {
        add_clause(clause);
    }
}

bool Solver::solve(const std::vector<int>& assumptions) {
    last_assumptions_ = assumptions;
    for (int lit : assumptions) {
        solver_->assume(lit);
    }
    last_result_ = solver_->solve();
    return last_result_ == 10;
}

std::optional<bool> Solver::solve_limited(const std::vector<int>& assumptions) {
    last_assumptions_ = assumptions;
    for (int lit : assumptions) {
        solver_->assume(lit);
    }
    last_result_ = solver_->solve();
    if (last_result_ == 10)
        return true;
    if (last_result_ == 20)
        return false;
    return std::nullopt;
}

std::optional<std::vector<int>> Solver::get_model() const {
    if (last_result_ != 10)
        return std::nullopt;
    std::vector<int> model;
    int n = solver_->vars();
    model.reserve(n);
    for (int v = 1; v <= n; v++) {
        model.push_back(solver_->val(v));
    }
    return model;
}

std::optional<std::vector<int>> Solver::get_core() const {
    if (last_result_ != 20)
        return std::nullopt;
    std::vector<int> core;
    for (int lit : last_assumptions_) {
        if (solver_->failed(lit)) {
            core.push_back(lit);
        }
    }
    return core;
}

std::pair<bool, std::vector<int>> Solver::propagate(const std::vector<int>& assumptions) {
    for (int lit : assumptions) {
        solver_->assume(lit);
    }
    int result = solver_->propagate();
    std::vector<int> propagated;
    if (result != 20) {
        solver_->implied(propagated);
    }
    return {result != 20, propagated};
}

int Solver::nof_vars() const {
    return solver_->vars();
}

int Solver::nof_clauses() const {
    return num_clauses_;
}

void Solver::conf_budget(int budget) {
    if (budget < 0) {
        solver_->limit("conflicts", -1);
    } else {
        solver_->limit("conflicts", budget);
    }
}

void Solver::prop_budget(int budget) {
    if (budget < 0) {
        solver_->limit("propagations", -1);
    } else {
        solver_->limit("propagations", budget);
    }
}

}  // namespace amc

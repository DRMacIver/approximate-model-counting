#include "solution_information.hpp"

#include "utils.hpp"

namespace amc {

// SolutionInformation implementation

SolutionInformation::SolutionInformation(std::shared_ptr<CaDiCaL::Solver> solver,
                                         std::vector<int> assumptions)
    : solver_(std::move(solver)), assumptions_(std::move(assumptions)) {}

Status SolutionInformation::solvable() const {
    // Set assumptions before solving
    for (int lit : assumptions_) {
        solver_->assume(lit);
    }

    int result = solver_->solve();

    switch (result) {
        case 10:
            return Status::SATISFIABLE;
        case 20:
            return Status::UNSATISFIABLE;
        default:
            // Coverage exclusion: UNKNOWN is only returned when solving with
            // resource limits (time/conflict limits), which will be added later.
            // Currently untestable without that functionality.
            return Status::UNKNOWN;  // LCOV_EXCL_LINE
    }
}

std::vector<std::vector<int>> SolutionInformation::current_clauses() const {
    return propagate_and_simplify(*solver_, assumptions_);
}

// ModelCounter implementation

ModelCounter::ModelCounter(const std::vector<std::vector<int>>& clauses)
    : solver_(std::make_shared<CaDiCaL::Solver>()) {
    for (const auto& clause : clauses) {
        for (int lit : clause) {
            solver_->add(lit);
        }
        solver_->add(0);  // Terminate clause
    }
}

ModelCounter::~ModelCounter() = default;

// Coverage exclusion: NRVO (Named Return Value Optimization) causes the
// closing brace to show as uncovered even though the function executes.
// LCOV_EXCL_START
SolutionInformation ModelCounter::with_assumptions(const std::vector<int>& assumptions) const {
    return {solver_, assumptions};
}
// LCOV_EXCL_STOP

}  // namespace amc

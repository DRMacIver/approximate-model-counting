#include "solution_information.hpp"

namespace amc {

SolutionInformation::SolutionInformation()
    : solver_(std::make_unique<CaDiCaL::Solver>()), assumptions_() {}

SolutionInformation::~SolutionInformation() = default;

Status SolutionInformation::solvable() {
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

void SolutionInformation::add_clause(const std::vector<int>& literals) {
    for (int lit : literals) {
        solver_->add(lit);
    }
    solver_->add(0);  // Terminate clause
}

void SolutionInformation::add_assumption(int literal) {
    assumptions_.push_back(literal);
}

void SolutionInformation::clear_assumptions() {
    assumptions_.clear();
}

}  // namespace amc

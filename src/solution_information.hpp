#pragma once

#include <memory>
#include <vector>

#include "cadical.hpp"

namespace amc {

enum class Status { SATISFIABLE = 10, UNSATISFIABLE = 20, UNKNOWN = 0 };

class SolutionInformation {
public:
    SolutionInformation();
    ~SolutionInformation();

    // Delete copy constructor and assignment
    SolutionInformation(const SolutionInformation&) = delete;
    SolutionInformation& operator=(const SolutionInformation&) = delete;

    // Allow move constructor and assignment
    SolutionInformation(SolutionInformation&&) = default;
    SolutionInformation& operator=(SolutionInformation&&) = default;

    Status solvable();

    // Helper methods for building up the problem
    void add_clause(const std::vector<int>& literals);
    void add_assumption(int literal);
    void clear_assumptions();

private:
    std::unique_ptr<CaDiCaL::Solver> solver_;
    std::vector<int> assumptions_;
};

}  // namespace amc

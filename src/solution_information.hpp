#pragma once

#include <memory>
#include <vector>

#include "cadical.hpp"

namespace amc {

enum class Status { SATISFIABLE = 10, UNSATISFIABLE = 20, UNKNOWN = 0 };

class ModelCounter;

class SolutionInformation {
public:
    // SolutionInformation is immutable after construction
    Status solvable() const;

    // Returns the clauses after unit propagation with the current assumptions.
    // - Assumptions and their consequences appear as unit clauses
    // - Satisfied clauses are removed
    // - Falsified literals are removed from clauses
    // - Duplicate clauses are skipped
    std::vector<std::vector<int>> current_clauses() const;

    // Allow copy and move (shares solver reference)
    SolutionInformation(const SolutionInformation&) = default;
    SolutionInformation& operator=(const SolutionInformation&) = default;
    SolutionInformation(SolutionInformation&&) = default;
    SolutionInformation& operator=(SolutionInformation&&) = default;

private:
    friend class ModelCounter;

    // Private constructor - only ModelCounter can create instances
    SolutionInformation(std::shared_ptr<CaDiCaL::Solver> solver, std::vector<int> assumptions);

    std::shared_ptr<CaDiCaL::Solver> solver_;
    std::vector<int> assumptions_;
};

class ModelCounter {
public:
    explicit ModelCounter(const std::vector<std::vector<int>>& clauses);
    ~ModelCounter();

    // Delete copy constructor and assignment (solver state is mutable)
    ModelCounter(const ModelCounter&) = delete;
    ModelCounter& operator=(const ModelCounter&) = delete;

    // Allow move constructor and assignment
    ModelCounter(ModelCounter&&) = default;
    ModelCounter& operator=(ModelCounter&&) = default;

    // Create a SolutionInformation with the given assumptions
    SolutionInformation with_assumptions(const std::vector<int>& assumptions) const;

private:
    std::shared_ptr<CaDiCaL::Solver> solver_;
};

}  // namespace amc

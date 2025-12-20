#pragma once

#include <memory>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "boolean_equivalence.hpp"
#include "cadical.hpp"
#include "solution_table.hpp"

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

    // Returns the backbone: literals that must be true in all satisfying assignments.
    // The backbone includes the assumptions and any literals forced by unit propagation.
    // Returns empty vector if UNSATISFIABLE.
    const std::vector<int>& get_backbone() const;

    // Check if two literals are equivalent (must have the same value in all solutions).
    // Returns true if a and b are always equal, or if a and -b are always equal (opposite).
    // For opposite literals, are_equivalent(a, -b) returns true.
    bool are_equivalent(int a, int b) const;

    // Allow copy and move (shares solver reference)
    SolutionInformation(const SolutionInformation&) = default;
    SolutionInformation& operator=(const SolutionInformation&) = default;
    SolutionInformation(SolutionInformation&&) = default;
    SolutionInformation& operator=(SolutionInformation&&) = default;

private:
    friend class ModelCounter;

    // Private constructor - only ModelCounter can create instances
    SolutionInformation(std::shared_ptr<CaDiCaL::Solver> solver, std::vector<int> assumptions);

    // Lazily compute satisfiability (called by solvable())
    void calculate() const;

    std::shared_ptr<CaDiCaL::Solver> solver_;
    std::vector<int> assumptions_;
    mutable bool calculated_ = false;
    mutable Status status_ = Status::UNKNOWN;
    mutable std::vector<int> backbone_ = {};
    mutable BooleanEquivalence equivalence_ = {};
    mutable SolutionTable table_ = SolutionTable({});
    mutable std::unordered_set<int> free_variables_ = {};
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

    // Calculate march-style variable scores.
    // The assumptions parameter is modified in-place if failed literals are found.
    // Returns a map from variable to score.
    std::unordered_map<int, double> march_score(std::vector<int>& assumptions) const;

private:
    std::shared_ptr<CaDiCaL::Solver> solver_;
};

}  // namespace amc

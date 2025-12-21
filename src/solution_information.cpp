#include "solution_information.hpp"

#include <algorithm>
#include <cassert>
#include <random>
#include <unordered_set>

#include "refinable_partition.hpp"
#include "utils.hpp"

namespace amc {

std::vector<int> get_model(CaDiCaL::Solver& solver) {
    int vars = solver.vars();
    std::vector<int> model;
    for (int i = 1; i <= vars; i++) {
        model.push_back(solver.val(i));
    }
    return model;
}

std::vector<int> literals_to_indices(const std::vector<int>& model, int vars) {
    std::vector<int> result;
    for (int i : model) {
        int j = std::abs(i) - 1;
        if (i < 0) {
            j += vars;
        }
        result.push_back(j);
    }
    return result;
}

int index_to_literal(int i, int vars) {
    if (i >= vars) {
        return -index_to_literal(i - vars, vars);
    }
    return i + 1;
}

// SolutionInformation implementation

SolutionInformation::SolutionInformation(std::shared_ptr<CaDiCaL::Solver> solver,
                                         std::vector<int> assumptions)
    : solver_(std::move(solver)), assumptions_(std::move(assumptions)) {}

void SolutionInformation::calculate() const {
    if (calculated_) {
        return;
    }
    calculated_ = true;

    // Set assumptions before solving
    for (int lit : assumptions_) {
        solver_->assume(lit);
    }

    int result = solver_->solve();

    switch (result) {
        case 10:
            status_ = Status::SATISFIABLE;
            break;
        case 20:
            status_ = Status::UNSATISFIABLE;
            break;
        default:
            // Coverage exclusion: UNKNOWN is only returned when solving with
            // resource limits (time/conflict limits), which will be added later.
            // Currently untestable without that functionality.
            status_ = Status::UNKNOWN;  // LCOV_EXCL_LINE
            break;                      // LCOV_EXCL_LINE
    }

    if (status_ == Status::UNSATISFIABLE) {
        return;
    }

    int num_vars = solver_->vars();
    if (num_vars == 0) {
        // No variables, nothing to compute
        backbone_ = assumptions_;
        return;
    }

    RefinablePartition partitions(num_vars * 2);
    // Calculate backbone: literals that must be true in all solutions
    auto model = get_model(*solver_);
    partitions.mark(literals_to_indices(model, num_vars));

    std::unordered_set<int> backbone_candidates(model.begin(), model.end());
    backbone_ = assumptions_;
    auto scores = amc::march_score(*solver_, backbone_);
    for (int v : backbone_) {
        backbone_candidates.erase(v);
        backbone_candidates.erase(-v);
    }

    while (!backbone_candidates.empty()) {
        // Pick candidate with highest march score
        auto it = std::max_element(
            backbone_candidates.begin(), backbone_candidates.end(),
            [&](int a, int b) { return scores[std::abs(a)] < scores[std::abs(b)]; });
        int best = *it;

        // Try to find a model with the opposite polarity
        for (int v : backbone_) {
            solver_->assume(v);
        }
        solver_->assume(-best);

        if (solver_->solve() == 10) {
            // Found counter-model: remove non-matching candidates
            auto inverted_model = get_model(*solver_);
            partitions.mark(literals_to_indices(inverted_model, num_vars));
            std::unordered_set<int> inverted_model_set(inverted_model.begin(),
                                                       inverted_model.end());
            std::erase_if(backbone_candidates,
                          [&](int x) { return inverted_model_set.count(x) == 0; });
        } else {
            // No counter-model: this literal is in the backbone
            backbone_.push_back(best);
            // Get all implied literals
            for (int v : backbone_) {
                solver_->assume(v);
            }
            solver_->propagate();
            std::vector<int> implied;
            solver_->implied(implied);
            for (int v : implied) {
                if (backbone_candidates.count(v)) {
                    backbone_.push_back(v);
                }
                backbone_candidates.erase(v);
                backbone_candidates.erase(-v);
            }
        }
    }
    for (size_t i = 0; i < static_cast<size_t>(partitions.size());) {
        auto part = partitions[static_cast<int>(i)];
        assert(!part.empty());
        if (part.size() == 1) {
            i++;
            continue;
        }
        // Sort by score (highest first)
        std::sort(part.begin(), part.end(), [&](int a, int b) {
            return scores[std::abs(index_to_literal(a, num_vars))] >
                   scores[std::abs(index_to_literal(b, num_vars))];
        });
        int x = index_to_literal(part[0], num_vars);
        bool split = false;
        for (size_t j = 1; j < part.size(); j++) {
            int y = index_to_literal(part[j], num_vars);
            if (equivalence_.find(y) == equivalence_.find(x)) {
                continue;
            }
            bool any_sat = false;
            std::vector<std::vector<int>> assignments = {{x, -y}, {-x, y}};
            for (const auto& splitter : assignments) {
                for (int v : backbone_) {
                    solver_->assume(v);
                }
                for (int v : splitter) {
                    solver_->assume(v);
                }
                if (solver_->solve() == 10) {
                    auto splitting_model = get_model(*solver_);
                    partitions.mark(literals_to_indices(splitting_model, num_vars));
                    any_sat = true;
                }
            }
            if (any_sat) {
                split = true;
                break;
            }
            equivalence_.merge(x, y);
        }
        if (!split) {
            i++;
        }
    }

    std::set<std::vector<int>> normalised_clauses_set;
    for (const auto& clause : propagate_and_simplify(*solver_, backbone_)) {
        std::set<int> normalised_clause;
        for (int lit : clause) {
            normalised_clause.insert(equivalence_.find(lit));
        }
        std::vector<int> sorted_clause(normalised_clause.begin(), normalised_clause.end());
        normalised_clauses_set.insert(sorted_clause);
    }
    std::vector<std::vector<int>> normalised_clauses(normalised_clauses_set.begin(),
                                                     normalised_clauses_set.end());
    assert(normalised_clauses.size() > 0);
    scores = march_score(*solver_, backbone_);

    std::vector<int> table_candidates;
    table_candidates.reserve(scores.size());
    for (const auto& [k, v] : scores) {
        table_candidates.push_back(k);
    }
    std::sort(table_candidates.begin(), table_candidates.end(),
              [&](int a, int b) { return scores[a] > scores[b]; });
    std::random_device rd;
    std::mt19937 rng(rd());

    std::unordered_set<int> used = {};

    constexpr size_t MAX_TABLE_SIZE = 1'000'000;
    constexpr int REQUIRED_SUCCESSES = 10;

    for (int var : table_candidates) {
        int representative = abs(equivalence_.find(var));
        if (used.contains(representative))
            continue;
        if (table_.size() > MAX_TABLE_SIZE)
            break;
        used.insert(representative);
        table_.add_variable(var);
        int successes = 0;
        while (successes < REQUIRED_SUCCESSES && table_.size() > 1) {
            std::uniform_int_distribution<int> row_dist(0, table_.size() - 1);
            int row_idx = row_dist(rng);
            std::vector<int64_t> row = table_[row_idx];
            solver_->reset_assumptions();
            for (int lit : backbone_)
                solver_->assume(lit);
            for (int64_t lit : row)
                solver_->assume(lit);
            if (solver_->solve() == 10) {
                successes += 1;
            } else {
                successes = 0;
                std::vector<int64_t> core;
                core.reserve(row.size());
                for (int64_t lit : row)
                    if (solver_->failed(lit))
                        core.push_back(lit);
                assert(core.size() > 0);
                table_.remove_matching(core);
            }
        }
    }
}

Status SolutionInformation::solvable() const {
    calculate();
    return status_;
}

std::vector<std::vector<int>> SolutionInformation::current_clauses() const {
    return propagate_and_simplify(*solver_, assumptions_);
}

const std::vector<int>& SolutionInformation::get_backbone() const {
    calculate();
    return backbone_;
}

bool SolutionInformation::are_equivalent(int a, int b) const {
    calculate();
    return equivalence_.find(a) == equivalence_.find(b);
}

const SolutionTable& SolutionInformation::get_solution_table() const {
    calculate();
    return table_;
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

std::unordered_map<int, double> ModelCounter::march_score(std::vector<int>& assumptions) const {
    return amc::march_score(*solver_, assumptions);
}

}  // namespace amc

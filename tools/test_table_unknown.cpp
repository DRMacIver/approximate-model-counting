#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <random>
#include <vector>

#include "../src/solution_table.hpp"
#include "../src/utils.hpp"
#include "cadical.hpp"

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <cnf_file>" << std::endl;
        return 1;
    }

    CaDiCaL::Solver solver;
    solver.set("quiet", 1);

    int vars = 0;
    const char* error = solver.read_dimacs(argv[1], vars, 1);
    if (error) {
        std::cerr << "Failed to read DIMACS: " << error << std::endl;
        return 1;
    }

    // Initial solve must be SAT
    solver.limit("conflicts", 100);
    int result = solver.solve();
    if (result != 10) {
        // Not SAT - uninteresting
        return 1;
    }

    // Calculate march scores
    std::vector<int> empty_backbone;
    auto scores = amc::march_score(solver, empty_backbone);

    // Sort variables by score (highest first)
    std::vector<int> candidates;
    candidates.reserve(scores.size());
    for (const auto& [var, score] : scores) {
        candidates.push_back(var);
    }
    std::sort(candidates.begin(), candidates.end(),
              [&](int a, int b) { return scores[a] > scores[b]; });

    // Build solution table
    SolutionTable table({});
    std::mt19937 rng(0);  // Fixed seed for reproducibility

    constexpr size_t MAX_TABLE_SIZE = 1'000'000;
    constexpr int REQUIRED_SUCCESSES = 10;

    for (int var : candidates) {
        if (table.size() > MAX_TABLE_SIZE)
            break;

        // Before adding variable, check if it can be set both ways
        // If either returns UNKNOWN, this is uninteresting
        for (int sign : {1, -1}) {
            int lit = sign * var;
            solver.assume(lit);
            solver.limit("conflicts", 100);
            int check_result = solver.solve();
            if (check_result == 0) {
                // UNKNOWN when checking variable - uninteresting
                return 1;
            }
        }

        table.add_variable(var);

        int successes = 0;
        while (successes < REQUIRED_SUCCESSES && table.size() > 1) {
            std::uniform_int_distribution<int> row_dist(0, table.size() - 1);
            int row_idx = row_dist(rng);
            std::vector<int64_t> row = table[row_idx];

            solver.reset_assumptions();
            for (int64_t lit : row) {
                solver.assume(lit);
            }
            solver.limit("conflicts", 100);
            int table_result = solver.solve();

            if (table_result == 0) {
                // UNKNOWN during table validation - this is what we want!
                return 0;
            }

            if (table_result != 20) {
                successes += 1;
            } else {
                successes = 0;
                std::vector<int64_t> core;
                core.reserve(row.size());
                for (int64_t lit : row) {
                    if (solver.failed(lit)) {
                        core.push_back(lit);
                    }
                }
                if (!core.empty()) {
                    table.remove_matching(core);
                }
            }
        }
    }

    // No UNKNOWN found during table building
    return 1;
}

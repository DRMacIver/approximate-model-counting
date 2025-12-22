#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <unordered_map>
#include <vector>

#include "cadical.hpp"

class ScoreCalculator : public CaDiCaL::ClauseIterator {
public:
    std::unordered_map<int, double> scores;

    bool clause(const std::vector<int>& c) override {
        if (!c.empty()) {
            double contribution = std::pow(5.0, 2.0 - static_cast<double>(c.size()));
            for (int lit : c) {
                scores[lit] += contribution;
            }
        }
        return true;  // continue traversal
    }
};

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

    // Compute scores by traversing clauses
    ScoreCalculator calc;
    solver.traverse_clauses(calc);

    // Check SAT with conflict limit
    solver.limit("conflicts", 100);
    int result = solver.solve();
    if (result != 10) {
        // Not SAT (UNSAT or UNKNOWN on initial solve)
        return 1;
    }

    // Save the model immediately
    std::vector<int> model;
    for (int i = 1; i <= solver.vars(); i++) {
        model.push_back(solver.val(i));
    }

    // Sort by score (highest first - hardest to flip)
    std::sort(model.begin(), model.end(), [&](int a, int b) {
        return calc.scores[a] > calc.scores[b];
    });

    // Try flipping each literal
    for (int lit : model) {
        solver.assume(-lit);
        solver.limit("conflicts", 100);
        int flip_result = solver.solve();
        if (flip_result == 0) {
            // UNKNOWN - found what we're looking for
            return 0;
        }
    }

    // No UNKNOWN found
    return 1;
}

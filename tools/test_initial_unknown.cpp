#include <cstdlib>
#include <iostream>

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

    // Check if initial solve returns UNKNOWN
    solver.limit("conflicts", 100);
    int result = solver.solve();
    if (result == 0) {
        // UNKNOWN on initial solve
        return 0;
    }

    return 1;
}

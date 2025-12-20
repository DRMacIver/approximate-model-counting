#include "solution_table.hpp"
#include <pybind11/pybind11.h>
#include <stdexcept>

namespace py = pybind11;

// Test function: BitVector::size() returns correct length
bool test_bitvector_size() {
    BitVector bv;
    if (bv.size() != 0) return false;

    bv.push(true);
    if (bv.size() != 1) return false;

    bv.push(false);
    if (bv.size() != 2) return false;

    // Push many values
    for (int i = 0; i < 100; i++) {
        bv.push(i % 2 == 0);
    }
    if (bv.size() != 102) return false;

    return true;
}

// Test function: BitVector::get() returns false for out-of-bounds access
bool test_bitvector_get_out_of_bounds() {
    BitVector bv;
    // Empty vector - any index is out of bounds
    if (bv.get(0) != false) return false;
    if (bv.get(100) != false) return false;

    bv.push(true);
    // Index 0 is valid and true
    if (bv.get(0) != true) return false;
    // Index 1 is out of bounds
    if (bv.get(1) != false) return false;
    if (bv.get(1000) != false) return false;

    return true;
}

PYBIND11_MODULE(_test_internals, m) {
    m.doc() = "Internal test functions for C++ code not exposed to Python";

    m.def("test_bitvector_size", &test_bitvector_size,
          "Test that BitVector::size() works correctly");
    m.def("test_bitvector_get_out_of_bounds", &test_bitvector_get_out_of_bounds,
          "Test that BitVector::get() returns false for out-of-bounds access");
}

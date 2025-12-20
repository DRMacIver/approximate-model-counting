#include "solution_table.hpp"
#include <pybind11/pybind11.h>
#include <stdexcept>

namespace py = pybind11;

// Test function: BitVector::size() returns correct length
void check_bitvector_size() {
    BitVector bv;
    if (bv.size() != 0) throw std::runtime_error("Empty BitVector should have size 0");

    bv.push(true);
    if (bv.size() != 1) throw std::runtime_error("BitVector should have size 1 after one push");

    bv.push(false);
    if (bv.size() != 2) throw std::runtime_error("BitVector should have size 2 after two pushes");

    // Push many values
    for (int i = 0; i < 100; i++) {
        bv.push(i % 2 == 0);
    }
    if (bv.size() != 102) throw std::runtime_error("BitVector should have size 102 after 102 pushes");
}

// Test function: BitVector::get() returns false for out-of-bounds access
void check_bitvector_get_out_of_bounds() {
    BitVector bv;
    // Empty vector - any index is out of bounds
    if (bv.get(0) != false) throw std::runtime_error("Empty BitVector get(0) should return false");
    if (bv.get(100) != false) throw std::runtime_error("Empty BitVector get(100) should return false");

    bv.push(true);
    // Index 0 is valid and true
    if (bv.get(0) != true) throw std::runtime_error("BitVector get(0) should return true after push(true)");
    // Index 1 is out of bounds
    if (bv.get(1) != false) throw std::runtime_error("BitVector get(1) should return false (out of bounds)");
    if (bv.get(1000) != false) throw std::runtime_error("BitVector get(1000) should return false (out of bounds)");
}

PYBIND11_MODULE(_test_internals, m) {
    m.doc() = "Internal test functions for C++ code not exposed to Python";

    m.def("check_bitvector_size", &check_bitvector_size,
          "Test that BitVector::size() works correctly");
    m.def("check_bitvector_get_out_of_bounds", &check_bitvector_get_out_of_bounds,
          "Test that BitVector::get() returns false for out-of-bounds access");
}

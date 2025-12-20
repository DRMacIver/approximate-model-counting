#include "solution_table.hpp"
#include <algorithm>
#include <stdexcept>
#include <sstream>
#include <cstdlib>

// BitVector implementation
BitVector::BitVector() : len(0) {}

size_t BitVector::size() const {
    return len;
}

bool BitVector::get(size_t index) const {
    if (index >= len) {
        return false;
    }

    size_t word_index = index / 64;
    size_t bit_index = index % 64;

    return (data[word_index] & (1ULL << bit_index)) != 0;
}

void BitVector::push(bool value) {
    size_t word_index = len / 64;
    size_t bit_index = len % 64;

    // If we need a new word, add it
    if (word_index >= data.size()) {
        data.push_back(0);
    }

    uint64_t mask = 1ULL << bit_index;
    if (value) {
        data[word_index] |= mask;
    } else {
        data[word_index] &= ~mask;
    }

    len++;
}

// SolutionTable implementation
SolutionTable::SolutionTable(const std::vector<int64_t>& vars) : variables(vars), reified(0) {
    size_t n = variables.size();
    if (n >= 64) {
        throw std::invalid_argument("Too many variables for SolutionTable (max 63)");
    }

    for (int64_t v : variables) {
        if (v <= 0) {
            throw std::invalid_argument("Invalid variable " + std::to_string(v));
        }
    }

    rows.push_back(BitVector());
}

void SolutionTable::reify(int64_t variable) {
    size_t i = var_index(variable);

    if (i >= reified) {
        std::swap(variables[i], variables[reified]);
        reified++;

        size_t old_size = rows.size();
        for (size_t j = 0; j < old_size; j++) {
            BitVector new_row = rows[j];
            new_row.push(true);
            rows.push_back(new_row);
            rows[j].push(false);
        }
    }
}

size_t SolutionTable::var_index(int64_t variable) const {
    if (variable <= 0) {
        throw std::invalid_argument("Invalid variable " + std::to_string(variable));
    }

    auto it = std::find(variables.begin(), variables.end(), variable);
    if (it == variables.end()) {
        std::ostringstream oss;
        oss << "Variable " << variable << " not found in SolutionTable variables [";
        for (size_t i = 0; i < variables.size(); i++) {
            if (i > 0) oss << ", ";
            oss << variables[i];
        }
        oss << "]";
        throw std::invalid_argument(oss.str());
    }

    return it - variables.begin();
}

size_t SolutionTable::size() const {
    return rows.size() * (1ULL << (variables.size() - reified));
}

std::vector<int64_t> SolutionTable::operator[](size_t index) const {
    if (index >= size()) {
        throw std::out_of_range("Index out of bounds");
    }

    size_t unreified = variables.size() - reified;

    BitVector result_mask = rows[index >> unreified];

    size_t bits = index;
    for (size_t i = 0; i < unreified; i++) {
        result_mask.push((bits & 1) != 0);
        bits >>= 1;
    }

    std::vector<int64_t> result;
    for (size_t i = 0; i < variables.size(); i++) {
        if (result_mask.get(i)) {
            result.push_back(variables[i]);
        } else {
            result.push_back(-variables[i]);
        }
    }

    std::sort(result.begin(), result.end(),
              [](int64_t a, int64_t b) { return std::abs(a) < std::abs(b); });

    return result;
}

void SolutionTable::add_variable(int64_t variable) {
    if (size() >= SIZE_MAX / 2) {
        throw std::overflow_error("Adding variable would overflow SolutionTable size");
    }
    variables.push_back(variable);
}

void SolutionTable::remove_matching(const std::vector<int64_t>& assignment) {
    for (int64_t v : assignment) {
        reify(std::abs(v));
    }

    std::vector<size_t> indices;
    std::vector<bool> values;

    for (int64_t v : assignment) {
        size_t i = var_index(std::abs(v));
        indices.push_back(i);
        values.push_back(v > 0);
    }

    rows.erase(
        std::remove_if(rows.begin(), rows.end(),
            [&](const BitVector& row) {
                for (size_t i = 0; i < indices.size(); i++) {
                    if (row.get(indices[i]) != values[i]) {
                        return false;
                    }
                }
                return true;
            }),
        rows.end()
    );
}

SolutionTable SolutionTable::clone() const {
    return *this;
}

bool SolutionTable::contains(int64_t variable) const {
    if (variable <= 0) {
        return false;
    }
    return std::find(variables.begin(), variables.end(), variable) != variables.end();
}

const std::vector<int64_t>& SolutionTable::get_variables() const {
    return variables;
}

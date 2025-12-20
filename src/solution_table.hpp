#pragma once

#include <vector>
#include <cstdint>

class BitVector {
private:
    std::vector<uint64_t> data;
    size_t len;

public:
    BitVector();

    size_t size() const;
    bool get(size_t index) const;
    void push(bool value);
};

// A SolutionTable holds the set of all possible satisfying assignments
// of a set of variables in some SAT problem. It is designed to do so
// implicitly rather than having to store the whole table wherever possible.
// When a core is found, you can remove all matching solutions. This may
// reorder the table arbitrarily.
class SolutionTable {
private:
    std::vector<int64_t> variables;
    std::vector<BitVector> rows;
    size_t reified;

    void reify(int64_t variable);
    size_t var_index(int64_t variable) const;

public:
    // Constructor
    SolutionTable(const std::vector<int64_t>& vars);

    // Get SolutionTable size (number of rows)
    size_t size() const;

    // Get a specific row as an assignment
    std::vector<int64_t> operator[](size_t index) const;

    // Add a new variable to the SolutionTable
    void add_variable(int64_t variable);

    // Remove all rows matching the given assignment
    void remove_matching(const std::vector<int64_t>& assignment);

    // Clone the SolutionTable
    SolutionTable clone() const;

    // Check if variable is in the SolutionTable
    bool contains(int64_t variable) const;

    // Get the list of variables
    const std::vector<int64_t>& get_variables() const;
};

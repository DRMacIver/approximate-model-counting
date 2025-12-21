#pragma once

#include <cstdlib>
#include <unordered_map>
#include <vector>

class BooleanEquivalence {
private:
    std::unordered_map<int, int> table;
    int representatives;

public:
    BooleanEquivalence();

    // Find the canonical representative of a literal
    int find(int a);

    // Merge two literals (asserting they're equivalent)
    void merge(int a, int b);

    // Get number of equivalence classes
    int num_representatives() const;

    // Get all non-trivial equivalence classes (classes with 2+ variables)
    // Returns a vector of sorted variable vectors
    std::vector<std::vector<int>> get_equivalence_classes();
};

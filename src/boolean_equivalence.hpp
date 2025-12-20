#pragma once

#include <unordered_map>
#include <cstdlib>

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
};

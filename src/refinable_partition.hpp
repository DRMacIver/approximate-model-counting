#pragma once

#include <utility>
#include <vector>

class RefinablePartition {
private:
    std::vector<int> values;
    std::vector<int> values_indexes;
    int n_partitions;
    std::vector<std::pair<int, int>> partitions;
    std::vector<int> partitions_indexes;

    int adjust_indices(int i) const;

public:
    RefinablePartition(int size);

    // Number of partitions
    int size() const;

    // Get elements in partition i
    std::vector<int> operator[](int i) const;

    // Get which partition element i is in
    int partition_of(int i) const;

    // Refine partitions by marking values
    void mark(const std::vector<int>& marked_values);
};

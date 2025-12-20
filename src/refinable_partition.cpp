#include "refinable_partition.hpp"

#include <cassert>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

RefinablePartition::RefinablePartition(int size)
    : values(size),
      values_indexes(size),
      n_partitions(1),
      partitions(size > 0 ? size : 1),
      partitions_indexes(size, 0) {
    for (int i = 0; i < size; i++) {
        values[i] = i;
        values_indexes[i] = i;
    }

    partitions[0] = {0, size};
}

// LCOV_EXCL_START - NRVO causes closing brace to show as uncovered
int RefinablePartition::adjust_indices(int i) const {
    if (i < -n_partitions || i >= n_partitions) {
        throw std::out_of_range("partition index out of range");
    }
    if (i < 0) {
        i += n_partitions;
    }
    return i;
}
// LCOV_EXCL_STOP

int RefinablePartition::size() const {
    return n_partitions;
}

std::vector<int> RefinablePartition::operator[](int i) const {
    i = adjust_indices(i);
    auto [start, end] = partitions[i];
    return std::vector<int>(values.begin() + start, values.begin() + end);
}

int RefinablePartition::partition_of(int i) const {
    return partitions_indexes[values_indexes[i]];
}

void RefinablePartition::mark(const std::vector<int>& marked_values) {
    std::unordered_map<int, int> marked;
    std::unordered_set<int> seen;
    int n = static_cast<int>(values.size());

    for (int v : marked_values) {
        // Bounds check
        if (v < 0 || v >= n) {
            throw std::out_of_range("marked value out of range");
        }

        // Skip duplicates
        if (seen.count(v))
            continue;
        seen.insert(v);

        int i = values_indexes[v];
        int partition = partitions_indexes[i];
        marked[partition]++;

        auto [start, end] = partitions[partition];
        assert(start <= i && i < end);

        int j = end - marked[partition];
        assert(i <= j);

        std::swap(values[i], values[j]);
        values_indexes[values[i]] = i;
        values_indexes[values[j]] = j;
    }

    for (const auto& [partition, mark_count] : marked) {
        auto [start, end] = partitions[partition];

        // Entire partition was marked, nothing to do
        if (start + mark_count == end) {
            continue;
        }

        int new_partition = n_partitions;
        n_partitions++;

        partitions[partition].second = end - mark_count;
        partitions[new_partition].first = end - mark_count;
        partitions[new_partition].second = end;

        for (int i = partitions[new_partition].first; i < partitions[new_partition].second; i++) {
            partitions_indexes[i] = new_partition;
        }
    }
}

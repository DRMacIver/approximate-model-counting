#include "boolean_equivalence.hpp"
#include <vector>
#include <stdexcept>

BooleanEquivalence::BooleanEquivalence() : representatives(0) {}

int BooleanEquivalence::find(int a) {
    if (a == 0) {
        throw std::invalid_argument("Invalid variable 0");
    }

    int sign = (a < 0) ? -1 : 1;
    int abs_a = std::abs(a);

    auto it = table.find(abs_a);
    if (it == table.end()) {
        representatives++;
        table[abs_a] = abs_a;
        return a;
    }

    if (table[abs_a] == abs_a) {
        return a;
    }

    // Path compression - track edge signs to preserve sign information
    std::vector<int> trail;
    std::vector<int> edge_signs;
    int value = abs_a;
    int result_sign = sign;

    while (table[value] != value) {
        trail.push_back(value);
        int next = table[value];
        if (next < 0) {
            edge_signs.push_back(-1);
            result_sign *= -1;
            next = -next;
        } else {
            edge_signs.push_back(1);
        }
        value = next;
    }

    // Compress the path with correct cumulative signs
    int cumulative = 1;
    for (int i = trail.size() - 1; i >= 0; i--) {
        cumulative *= edge_signs[i];
        table[trail[i]] = cumulative * value;
    }

    return result_sign * value;
}

void BooleanEquivalence::merge(int a, int b) {
    if (a == b) return;

    int a2 = find(a);
    int b2 = find(b);

    if (a2 == b2) return;

    if (a2 == -b2) {
        throw std::runtime_error(
            "Attempted to merge " + std::to_string(a) + " (=" +
            std::to_string(a2) + ") with " + std::to_string(b) +
            " (=" + std::to_string(b2) + ")"
        );
    }

    representatives--;

    int abs_a2 = std::abs(a2);
    int abs_b2 = std::abs(b2);

    // Merge smaller into larger
    if (abs_a2 > abs_b2) {
        std::swap(abs_a2, abs_b2);
        std::swap(a2, b2);
    }

    // Store negated if signs differ
    if ((a2 < 0) == (b2 < 0)) {
        table[abs_b2] = abs_a2;
    } else {
        table[abs_b2] = -abs_a2;
    }
}

int BooleanEquivalence::num_representatives() const {
    return representatives;
}

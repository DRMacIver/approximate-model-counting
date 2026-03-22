#pragma once

#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace amc {

struct DecompositionNode {
    std::vector<int> variables;               // all variables at this node
    std::vector<int> separator;               // the split variables (empty for leaves)
    std::vector<DecompositionNode> children;  // one per component (empty for leaves)

    bool is_leaf() const;
};

class VariableInteractionGraph {
public:
    // Build from clauses (extracts variables, creates edges between
    // variables sharing a clause)
    explicit VariableInteractionGraph(const std::vector<std::vector<int>>& clauses);

    // Core queries
    const std::vector<int>& variables() const;
    int num_edges() const;

    // The main algorithm: recursively decompose until components <= n
    DecompositionNode decompose(int n = 20) const;

    // Lower-level building block: find the best n separator variables
    // from within scope, treating excluded as already removed.
    // Optional scores map is used as tiebreaker (higher = preferred).
    std::vector<int> find_separator(const std::vector<int>& scope,
                                    const std::unordered_set<int>& excluded, int n,
                                    const std::unordered_map<int, double>& scores = {}) const;

    // Enlarge an existing separator to target size n by adding the best
    // additional variables from scope. The returned set includes all of
    // current_separator plus new variables chosen by the same ranking as
    // find_separator. Variables in current_separator must be in scope and
    // not in excluded.
    // Optional scores map is used as tiebreaker (higher = preferred).
    std::vector<int> enlarge_separator(const std::vector<int>& current_separator,
                                       const std::vector<int>& scope,
                                       const std::unordered_set<int>& excluded, int n,
                                       const std::unordered_map<int, double>& scores = {}) const;

    // Connected components of scope after removing excluded
    std::vector<std::vector<int>> connected_components(
        const std::vector<int>& scope, const std::unordered_set<int>& excluded) const;

private:
    DecompositionNode decompose_recursive(const std::vector<int>& scope,
                                          const std::unordered_set<int>& excluded, int n) const;

    // Shared implementation: find separator starting from initial set
    std::vector<int> find_separator_impl(const std::vector<int>& scope,
                                         const std::unordered_set<int>& excluded,
                                         const std::vector<int>& initial, int n,
                                         const std::unordered_map<int, double>& scores) const;

    // Adjacency list: variable -> set of neighboring variables
    std::unordered_map<int, std::unordered_set<int>> adjacency_;
    std::vector<int> variables_;
    int num_edges_;
};

}  // namespace amc

#include "variable_interaction_graph.hpp"

#include <igraph.h>

#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <queue>
#include <unordered_map>

namespace amc {

bool DecompositionNode::is_leaf() const {
    return children.empty();
}

VariableInteractionGraph::VariableInteractionGraph(const std::vector<std::vector<int>>& clauses) {
    std::unordered_set<int> var_set;
    num_edges_ = 0;

    for (const auto& clause : clauses) {
        // Extract variables from the clause
        std::vector<int> vars;
        for (int lit : clause) {
            int v = std::abs(lit);
            var_set.insert(v);
            vars.push_back(v);
        }
        // Add edges between all pairs of variables in the clause
        for (size_t i = 0; i < vars.size(); i++) {
            for (size_t j = i + 1; j < vars.size(); j++) {
                if (vars[i] != vars[j]) {
                    // Only count new edges
                    if (adjacency_[vars[i]].insert(vars[j]).second) {
                        adjacency_[vars[j]].insert(vars[i]);
                        num_edges_++;
                    }
                }
            }
        }
    }

    variables_.assign(var_set.begin(), var_set.end());
    std::sort(variables_.begin(), variables_.end());
}

const std::vector<int>& VariableInteractionGraph::variables() const {
    return variables_;
}

int VariableInteractionGraph::num_edges() const {
    return num_edges_;
}

std::vector<std::vector<int>> VariableInteractionGraph::connected_components(
    const std::vector<int>& scope, const std::unordered_set<int>& excluded) const {
    // Build the set of active variables (scope minus excluded)
    std::unordered_set<int> active(scope.begin(), scope.end());
    for (int v : excluded) {
        active.erase(v);
    }

    if (active.empty()) {
        return {};
    }

    // BFS to find connected components
    std::unordered_set<int> visited;
    std::vector<std::vector<int>> components;

    for (int start : active) {
        if (visited.count(start))
            continue;

        std::vector<int> component;
        std::queue<int> q;
        q.push(start);
        visited.insert(start);

        while (!q.empty()) {
            int v = q.front();
            q.pop();
            component.push_back(v);

            auto it = adjacency_.find(v);
            if (it != adjacency_.end()) {
                for (int neighbor : it->second) {
                    if (active.count(neighbor) && !visited.count(neighbor)) {
                        visited.insert(neighbor);
                        q.push(neighbor);
                    }
                }
            }
        }

        std::sort(component.begin(), component.end());
        components.push_back(std::move(component));
    }

    // Sort components by first element for determinism
    std::sort(components.begin(), components.end());
    return components;
}

std::vector<int> VariableInteractionGraph::find_separator(const std::vector<int>& scope,
                                                          const std::unordered_set<int>& excluded,
                                                          int n) const {
    return find_separator_impl(scope, excluded, {}, n);
}  // LCOV_EXCL_LINE - NRVO closing brace

std::vector<int> VariableInteractionGraph::enlarge_separator(
    const std::vector<int>& current_separator, const std::vector<int>& scope,
    const std::unordered_set<int>& excluded, int n) const {
    return find_separator_impl(scope, excluded, current_separator, n);
}

std::vector<int> VariableInteractionGraph::find_separator_impl(
    const std::vector<int>& scope, const std::unordered_set<int>& excluded,
    const std::vector<int>& initial, int n) const {
    // Build active set
    std::unordered_set<int> active(scope.begin(), scope.end());
    for (int v : excluded) {
        active.erase(v);
    }

    std::vector<int> active_vars(active.begin(), active.end());
    std::sort(active_vars.begin(), active_vars.end());

    if (static_cast<int>(active_vars.size()) <= n) {
        return active_vars;
    }

    // Start with the initial set (already-selected variables)
    std::unordered_set<int> already_selected(initial.begin(), initial.end());
    std::vector<int> separator(initial.begin(), initial.end());

    if (static_cast<int>(separator.size()) >= n) {
        std::sort(separator.begin(), separator.end());
        return separator;
    }

    // Build igraph from active variables
    // Map: variable -> igraph vertex index
    std::unordered_map<int, int> var_to_idx;
    for (size_t i = 0; i < active_vars.size(); i++) {
        var_to_idx[active_vars[i]] = static_cast<int>(i);
    }

    // Collect edges as pairs of igraph vertex indices
    std::vector<igraph_integer_t> edges;
    for (int v : active_vars) {
        auto it = adjacency_.find(v);
        if (it == adjacency_.end())
            continue;
        for (int neighbor : it->second) {
            if (active.count(neighbor) && v < neighbor) {
                edges.push_back(static_cast<igraph_integer_t>(var_to_idx[v]));
                edges.push_back(static_cast<igraph_integer_t>(var_to_idx[neighbor]));
            }
        }
    }

    igraph_integer_t nv = static_cast<igraph_integer_t>(active_vars.size());
    igraph_t graph;
    igraph_vector_int_t edge_vec;
    igraph_vector_int_init(&edge_vec, static_cast<igraph_integer_t>(edges.size()));
    for (size_t i = 0; i < edges.size(); i++) {
        VECTOR(edge_vec)[i] = edges[i];
    }
    igraph_create(&graph, &edge_vec, nv, IGRAPH_UNDIRECTED);
    igraph_vector_int_destroy(&edge_vec);

    // Run Louvain community detection
    igraph_vector_int_t membership;
    igraph_vector_int_init(&membership, 0);
    igraph_community_multilevel(&graph, nullptr, 1, &membership, nullptr, nullptr);

    int num_communities = 0;
    for (igraph_integer_t i = 0; i < igraph_vector_int_size(&membership); i++) {
        int c = static_cast<int>(VECTOR(membership)[i]);
        if (c + 1 > num_communities)
            num_communities = c + 1;
    }

    // Identify boundary variables: variables with neighbors in multiple communities
    std::vector<std::pair<int, int>> boundary_vars;  // (inter-community edges, variable)

    for (int i = 0; i < nv; i++) {
        int var = active_vars[i];
        if (already_selected.count(var))
            continue;
        int my_community = static_cast<int>(VECTOR(membership)[i]);
        int inter_community_edges = 0;

        auto it = adjacency_.find(var);
        if (it != adjacency_.end()) {
            for (int neighbor : it->second) {
                if (!active.count(neighbor))
                    continue;
                int ni = var_to_idx[neighbor];
                int neighbor_community = static_cast<int>(VECTOR(membership)[ni]);
                if (neighbor_community != my_community) {
                    inter_community_edges++;
                }
            }
        }

        if (inter_community_edges > 0) {
            boundary_vars.push_back({inter_community_edges, var});
        }
    }

    if (num_communities > 1 && !boundary_vars.empty()) {
        // Sort boundary vars by inter-community edge count (descending), then by variable
        // for determinism
        std::sort(boundary_vars.begin(), boundary_vars.end(), [](const auto& a, const auto& b) {
            if (a.first != b.first)
                return a.first > b.first;
            return a.second < b.second;
        });

        for (const auto& [count, var] : boundary_vars) {
            if (static_cast<int>(separator.size()) >= n)
                break;
            separator.push_back(var);
            already_selected.insert(var);
        }
    }

    // If we still need more variables, use degree-based greedy selection
    if (static_cast<int>(separator.size()) < n) {
        // Compute degree within active subgraph for each non-selected variable
        std::vector<std::pair<int, int>> candidates;  // (degree, variable)
        for (int var : active_vars) {
            if (already_selected.count(var))
                continue;
            int degree = 0;
            auto it = adjacency_.find(var);
            if (it != adjacency_.end()) {
                for (int neighbor : it->second) {
                    if (active.count(neighbor)) {
                        degree++;
                    }
                }
            }
            candidates.push_back({degree, var});
        }

        // Sort by degree descending, then variable ascending for determinism
        std::sort(candidates.begin(), candidates.end(), [](const auto& a, const auto& b) {
            if (a.first != b.first)
                return a.first > b.first;
            return a.second < b.second;
        });

        for (const auto& [degree, var] : candidates) {
            if (static_cast<int>(separator.size()) >= n)
                break;
            separator.push_back(var);
        }
    }

    igraph_vector_int_destroy(&membership);
    igraph_destroy(&graph);

    std::sort(separator.begin(), separator.end());
    return separator;
}

DecompositionNode VariableInteractionGraph::decompose(int n) const {
    std::unordered_set<int> excluded;
    return decompose_recursive(variables_, excluded, n);
}

DecompositionNode VariableInteractionGraph::decompose_recursive(
    const std::vector<int>& scope, const std::unordered_set<int>& excluded, int n) const {
    // Filter out excluded variables from scope
    std::vector<int> active;
    for (int v : scope) {
        if (!excluded.count(v)) {
            active.push_back(v);
        }
    }

    if (static_cast<int>(active.size()) <= n) {
        // Base case: small enough to handle directly
        DecompositionNode node;
        node.variables = active;
        return node;
    }

    // Find separator
    std::vector<int> separator = find_separator(active, excluded, n);

    // Build new excluded set
    std::unordered_set<int> new_excluded = excluded;
    for (int v : separator) {
        new_excluded.insert(v);
    }

    // Find connected components after removing separator
    auto components = connected_components(active, new_excluded);

    // Build node
    DecompositionNode node;
    node.variables = active;
    node.separator = separator;

    for (const auto& component : components) {
        node.children.push_back(decompose_recursive(component, new_excluded, n));
    }

    // If there's only one component (separator didn't disconnect), make it a leaf
    if (node.children.size() <= 1) {
        // The separator didn't help split, just return everything as a leaf
        node.separator.clear();
        node.children.clear();
    }

    return node;
}

}  // namespace amc

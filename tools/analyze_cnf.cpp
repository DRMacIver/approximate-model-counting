#include <algorithm>
#include <chrono>
#include <cmath>
#include <iostream>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "../src/boolean_equivalence.hpp"
#include "../src/refinable_partition.hpp"
#include "../src/solution_table.hpp"
#include "../src/utils.hpp"
#include "cadical.hpp"

// Collect clauses for analysis
class ClauseCollector : public CaDiCaL::ClauseIterator {
public:
    std::vector<std::vector<int>> clauses;
    std::unordered_map<int, int> lit_counts;
    std::unordered_map<int, int> var_counts;
    int max_var = 0;

    bool clause(const std::vector<int>& c) override {
        clauses.push_back(c);
        for (int lit : c) {
            lit_counts[lit]++;
            int var = std::abs(lit);
            var_counts[var]++;
            max_var = std::max(max_var, var);
        }
        return true;
    }
};

std::string escape_json(const std::string& s) {
    std::string result;
    for (char c : s) {
        if (c == '"')
            result += "\\\"";
        else if (c == '\\')
            result += "\\\\";
        else if (c == '\n')
            result += "\\n";
        else
            result += c;
    }
    return result;
}

// Helper functions for equivalence detection
std::vector<int> get_model(CaDiCaL::Solver& solver) {
    int vars = solver.vars();
    std::vector<int> model;
    for (int i = 1; i <= vars; i++) {
        model.push_back(solver.val(i));
    }
    return model;
}

std::vector<int> literals_to_indices(const std::vector<int>& model, int vars) {
    std::vector<int> result;
    for (int i : model) {
        int j = std::abs(i) - 1;
        if (i < 0) {
            j += vars;
        }
        result.push_back(j);
    }
    return result;
}

int index_to_literal(int i, int vars) {
    if (i >= vars) {
        return -index_to_literal(i - vars, vars);
    }
    return i + 1;
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <cnf_file>" << std::endl;
        return 1;
    }

    auto start_time = std::chrono::high_resolution_clock::now();

    CaDiCaL::Solver solver;
    solver.set("quiet", 1);

    int vars = 0;
    const char* error = solver.read_dimacs(argv[1], vars, 1);
    if (error) {
        std::cout << "{\"error\": \"" << escape_json(error) << "\"}" << std::endl;
        return 0;
    }

    // Collect clause statistics
    ClauseCollector collector;
    solver.traverse_clauses(collector);

    int num_clauses = collector.clauses.size();
    int num_vars = collector.max_var;

    // Clause length distribution
    std::map<int, int> clause_length_dist;
    int total_clause_len = 0;
    int min_clause_len = num_vars + 1;
    int max_clause_len = 0;
    int unit_clauses = 0;
    int binary_clauses = 0;
    int ternary_clauses = 0;

    for (const auto& c : collector.clauses) {
        int len = c.size();
        clause_length_dist[len]++;
        total_clause_len += len;
        min_clause_len = std::min(min_clause_len, len);
        max_clause_len = std::max(max_clause_len, len);
        if (len == 1) unit_clauses++;
        if (len == 2) binary_clauses++;
        if (len == 3) ternary_clauses++;
    }

    double mean_clause_len = num_clauses > 0 ? (double)total_clause_len / num_clauses : 0;
    double density = num_vars > 0 ? (double)num_clauses / num_vars : 0;

    // Pure literals (appear only positive or only negative)
    int pure_literals = 0;
    for (int v = 1; v <= num_vars; v++) {
        bool has_pos = collector.lit_counts.count(v) > 0;
        bool has_neg = collector.lit_counts.count(-v) > 0;
        if (has_pos != has_neg) pure_literals++;
    }

    // Variable frequency stats
    int max_var_freq = 0;
    int min_var_freq = num_clauses + 1;
    for (const auto& [var, count] : collector.var_counts) {
        max_var_freq = std::max(max_var_freq, count);
        min_var_freq = std::min(min_var_freq, count);
    }
    if (collector.var_counts.empty()) min_var_freq = 0;

    // SAT solving with increasing conflict limits
    std::string solvability = "UNKNOWN";
    int solve_conflicts = 0;
    double solve_time_ms = 0;

    for (int limit : {100, 1000, 10000, 100000}) {
        solver.limit("conflicts", limit);
        auto solve_start = std::chrono::high_resolution_clock::now();
        int result = solver.solve();
        auto solve_end = std::chrono::high_resolution_clock::now();
        solve_time_ms =
            std::chrono::duration<double, std::milli>(solve_end - solve_start).count();

        if (result == 10) {
            solvability = "SAT";
            solve_conflicts = limit;
            break;
        } else if (result == 20) {
            solvability = "UNSAT";
            solve_conflicts = limit;
            break;
        }
        solve_conflicts = limit;
    }

    // If SAT, try to compute backbone and equivalences
    int backbone_size = -1;
    int table_size = -1;
    int num_equivalence_classes = -1;
    int vars_in_nontrivial_classes = -1;
    int largest_class_size = -1;
    int num_nontrivial_classes = -1;
    std::string class_size_distribution = "";

    if (solvability == "SAT") {
        int num_vars = solver.vars();
        // Get model
        std::vector<int> model = get_model(solver);

        // Initialize partition for equivalence tracking
        RefinablePartition partitions(num_vars * 2);
        partitions.mark(literals_to_indices(model, num_vars));

        // Simple backbone detection with limited tries
        std::vector<int> backbone;
        std::unordered_set<int> candidates(model.begin(), model.end());

        int checks = 0;
        const int max_checks = 100;  // Limit backbone checks

        while (!candidates.empty() && checks < max_checks) {
            int lit = *candidates.begin();
            candidates.erase(candidates.begin());

            solver.assume(-lit);
            solver.limit("conflicts", 100);
            int result = solver.solve();
            checks++;

            if (result == 20) {
                // lit is in backbone
                backbone.push_back(lit);
            } else if (result == 10) {
                // Found counter-model, remove non-matching
                auto counter_model = get_model(solver);
                partitions.mark(literals_to_indices(counter_model, num_vars));
                std::unordered_set<int> new_model(counter_model.begin(), counter_model.end());
                std::erase_if(candidates, [&](int x) { return new_model.count(x) == 0; });
            }
        }

        backbone_size = backbone.size();

        // Equivalence detection using refinable partition
        BooleanEquivalence equivalence;
        auto scores = amc::march_score(solver, backbone);

        const int max_equiv_checks = 200;
        int equiv_checks = 0;

        for (size_t i = 0; i < static_cast<size_t>(partitions.size()) && equiv_checks < max_equiv_checks;) {
            auto part = partitions[static_cast<int>(i)];
            if (part.size() == 1) {
                i++;
                continue;
            }
            // Sort by score (highest first)
            std::sort(part.begin(), part.end(), [&](int a, int b) {
                return scores[std::abs(index_to_literal(a, num_vars))] >
                       scores[std::abs(index_to_literal(b, num_vars))];
            });
            int x = index_to_literal(part[0], num_vars);
            bool split = false;
            for (size_t j = 1; j < part.size() && equiv_checks < max_equiv_checks; j++) {
                int y = index_to_literal(part[j], num_vars);
                if (equivalence.find(y) == equivalence.find(x)) {
                    continue;
                }
                bool any_sat = false;
                std::vector<std::vector<int>> assignments = {{x, -y}, {-x, y}};
                for (const auto& splitter : assignments) {
                    for (int v : backbone) {
                        solver.assume(v);
                    }
                    for (int v : splitter) {
                        solver.assume(v);
                    }
                    solver.limit("conflicts", 100);
                    equiv_checks++;
                    int result = solver.solve();
                    if (result == 10) {
                        auto splitting_model = get_model(solver);
                        partitions.mark(literals_to_indices(splitting_model, num_vars));
                        any_sat = true;
                        break;
                    }
                }
                if (any_sat) {
                    split = true;
                    break;
                }
                equivalence.merge(x, y);
            }
            if (!split) {
                i++;
            }
        }

        // Calculate equivalence statistics
        auto classes = equivalence.get_equivalence_classes();
        num_nontrivial_classes = classes.size();
        vars_in_nontrivial_classes = 0;
        largest_class_size = 0;
        std::map<int, int> size_counts;
        for (const auto& cls : classes) {
            int sz = cls.size();
            vars_in_nontrivial_classes += sz;
            largest_class_size = std::max(largest_class_size, sz);
            size_counts[sz]++;
        }
        // Count singleton classes (variables not in any non-trivial class)
        int singleton_count = num_vars - vars_in_nontrivial_classes;
        num_equivalence_classes = num_nontrivial_classes + singleton_count;

        // Build size distribution string
        std::string dist;
        for (const auto& [sz, cnt] : size_counts) {
            if (!dist.empty()) dist += ", ";
            dist += std::to_string(sz) + ":" + std::to_string(cnt);
        }
        class_size_distribution = dist;

        // Try to estimate solution table size
        SolutionTable table({});

        std::vector<int> table_candidates;
        for (const auto& [var, score] : scores) {
            table_candidates.push_back(var);
        }
        std::sort(table_candidates.begin(), table_candidates.end(),
                  [&](int a, int b) { return scores[a] > scores[b]; });

        // Add variables until table gets large or we've added enough
        int vars_added = 0;
        const int max_vars_to_add = 50;
        const size_t max_table_size = 100000;

        std::unordered_set<int> used_representatives;
        for (int var : table_candidates) {
            int rep = std::abs(equivalence.find(var));
            if (used_representatives.count(rep)) continue;
            if (vars_added >= max_vars_to_add || table.size() > max_table_size) break;

            used_representatives.insert(rep);
            table.add_variable(var);
            vars_added++;

            // Quick validation
            if (table.size() > 1) {
                std::vector<int64_t> row = table[0];
                solver.reset_assumptions();
                for (int l : backbone) solver.assume(l);
                for (int64_t l : row) solver.assume(l);
                solver.limit("conflicts", 100);
                if (solver.solve() == 20) {
                    // Row is invalid, remove it
                    std::vector<int64_t> core;
                    for (int64_t l : row)
                        if (solver.failed(l)) core.push_back(l);
                    if (!core.empty()) table.remove_matching(core);
                }
            }
        }

        table_size = table.size();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    double total_time_ms =
        std::chrono::duration<double, std::milli>(end_time - start_time).count();

    // Output JSON
    std::cout << "{\n";
    std::cout << "  \"file\": \"" << escape_json(argv[1]) << "\",\n";
    std::cout << "  \"variables\": " << num_vars << ",\n";
    std::cout << "  \"clauses\": " << num_clauses << ",\n";
    std::cout << "  \"density\": " << density << ",\n";
    std::cout << "  \"unit_clauses\": " << unit_clauses << ",\n";
    std::cout << "  \"binary_clauses\": " << binary_clauses << ",\n";
    std::cout << "  \"ternary_clauses\": " << ternary_clauses << ",\n";
    std::cout << "  \"min_clause_len\": " << (num_clauses > 0 ? min_clause_len : 0) << ",\n";
    std::cout << "  \"max_clause_len\": " << max_clause_len << ",\n";
    std::cout << "  \"mean_clause_len\": " << mean_clause_len << ",\n";
    std::cout << "  \"pure_literals\": " << pure_literals << ",\n";
    std::cout << "  \"min_var_freq\": " << min_var_freq << ",\n";
    std::cout << "  \"max_var_freq\": " << max_var_freq << ",\n";
    std::cout << "  \"solvability\": \"" << solvability << "\",\n";
    std::cout << "  \"solve_conflicts\": " << solve_conflicts << ",\n";
    std::cout << "  \"solve_time_ms\": " << solve_time_ms << ",\n";
    std::cout << "  \"backbone_size\": " << backbone_size << ",\n";
    std::cout << "  \"num_equivalence_classes\": " << num_equivalence_classes << ",\n";
    std::cout << "  \"vars_in_nontrivial_classes\": " << vars_in_nontrivial_classes << ",\n";
    std::cout << "  \"num_nontrivial_classes\": " << num_nontrivial_classes << ",\n";
    std::cout << "  \"largest_class_size\": " << largest_class_size << ",\n";
    std::cout << "  \"class_size_distribution\": \"" << class_size_distribution << "\",\n";
    std::cout << "  \"table_size\": " << table_size << ",\n";
    std::cout << "  \"total_time_ms\": " << total_time_ms << "\n";
    std::cout << "}" << std::endl;

    return 0;
}

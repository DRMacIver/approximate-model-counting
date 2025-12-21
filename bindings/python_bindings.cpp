#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "boolean_equivalence.hpp"
#include "refinable_partition.hpp"
#include "solution_information.hpp"
#include "solution_table.hpp"
#include "utils.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_approximate_model_counting, m) {
    m.doc() = "Approximate model counting using Monte Carlo methods";

    m.def("is_satisfiable", &amc::is_satisfiable, py::arg("clauses"),
          "Check if a set of clauses is satisfiable");

    m.def("find_solution", &amc::find_solution, py::arg("clauses"),
          "Find a satisfying assignment, or empty list if UNSAT");

    py::enum_<amc::Status>(m, "Status")
        .value("SATISFIABLE", amc::Status::SATISFIABLE)
        .value("UNSATISFIABLE", amc::Status::UNSATISFIABLE)
        .value("UNKNOWN", amc::Status::UNKNOWN)
        .export_values();

    py::class_<amc::SolutionInformation>(m, "SolutionInformation")
        .def("solvable", &amc::SolutionInformation::solvable,
             "Check if the problem is solvable with the assumptions")
        .def("current_clauses", &amc::SolutionInformation::current_clauses,
             "Get clauses after unit propagation with assumptions")
        .def("get_backbone", &amc::SolutionInformation::get_backbone,
             "Get the backbone literals (must be true in all solutions)")
        .def("are_equivalent", &amc::SolutionInformation::are_equivalent, py::arg("a"),
             py::arg("b"), "Check if two literals are equivalent (same value in all solutions)")
        .def("get_solution_table", &amc::SolutionInformation::get_solution_table,
             py::return_value_policy::reference_internal,
             "Get the solution table for non-backbone variables");

    py::class_<amc::ModelCounter>(m, "ModelCounter")
        .def(py::init<const std::vector<std::vector<int>>&, std::optional<uint64_t>>(),
             py::arg("clauses"), py::arg("seed") = std::nullopt,
             "Create a ModelCounter with the given clauses. If seed is provided, the RNG is "
             "seeded for deterministic behavior.")
        .def("with_assumptions", &amc::ModelCounter::with_assumptions, py::arg("assumptions"),
             "Create a SolutionInformation with the given assumptions")
        .def(
            "march_score",
            [](const amc::ModelCounter& mc, std::vector<int> assumptions) {
                // Copy assumptions since we need to return both scores and updated assumptions
                auto scores = mc.march_score(assumptions);
                return std::make_pair(scores, assumptions);
            },
            py::arg("assumptions"),
            "Calculate march-style variable scores. Returns (scores_dict, updated_assumptions).");

    py::class_<SolutionTable>(m, "SolutionTable")
        .def(py::init<const std::vector<int64_t>&>(), py::arg("variables"),
             "Create a SolutionTable with the given variables (max 63 variables)")
        .def("__len__", &SolutionTable::size, "Get the number of possible assignments")
        .def("__getitem__", &SolutionTable::operator[], py::arg("index"),
             "Get the assignment at the given index")
        .def("add_variable", &SolutionTable::add_variable, py::arg("variable"),
             "Add a new variable to the table")
        .def("remove_matching", &SolutionTable::remove_matching, py::arg("assignment"),
             "Remove all rows matching the given assignment")
        .def("clone", &SolutionTable::clone, "Create a copy of this SolutionTable")
        .def("contains", &SolutionTable::contains, py::arg("variable"),
             "Check if a variable is in the table")
        .def_property_readonly("variables", &SolutionTable::get_variables,
                               "Get the list of variables in the table");

    py::class_<BooleanEquivalence>(m, "BooleanEquivalence")
        .def(py::init<>(), "Create an empty BooleanEquivalence")
        .def("find", &BooleanEquivalence::find, py::arg("literal"),
             "Find the canonical representative of a literal")
        .def("merge", &BooleanEquivalence::merge, py::arg("a"), py::arg("b"),
             "Merge two literals (assert they are equivalent)")
        .def("num_representatives", &BooleanEquivalence::num_representatives,
             "Get the number of equivalence classes");

    py::class_<RefinablePartition>(m, "RefinablePartition")
        .def(py::init<int>(), py::arg("size"), "Create a partition of elements 0..size-1")
        .def("__len__", &RefinablePartition::size, "Get the number of partitions")
        .def("__getitem__", &RefinablePartition::operator[], py::arg("index"),
             "Get elements in partition at index (supports negative indexing)")
        .def("partition_of", &RefinablePartition::partition_of, py::arg("element"),
             "Get which partition an element is in")
        .def("mark", &RefinablePartition::mark, py::arg("values"),
             "Refine partitions by marking values");
}

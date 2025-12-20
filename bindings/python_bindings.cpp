#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "solution_information.hpp"
#include "solution_table.hpp"

namespace py = pybind11;

PYBIND11_MODULE(_approximate_model_counting, m) {
    m.doc() = "Approximate model counting using Monte Carlo methods";

    py::enum_<amc::Status>(m, "Status")
        .value("SATISFIABLE", amc::Status::SATISFIABLE)
        .value("UNSATISFIABLE", amc::Status::UNSATISFIABLE)
        .value("UNKNOWN", amc::Status::UNKNOWN)
        .export_values();

    py::class_<amc::SolutionInformation>(m, "SolutionInformation")
        .def("solvable", &amc::SolutionInformation::solvable,
             "Check if the problem is solvable with the assumptions")
        .def("current_clauses", &amc::SolutionInformation::current_clauses,
             "Get clauses after unit propagation with assumptions");

    py::class_<amc::ModelCounter>(m, "ModelCounter")
        .def(py::init<const std::vector<std::vector<int>>&>(), py::arg("clauses"),
             "Create a ModelCounter with the given clauses")
        .def("with_assumptions", &amc::ModelCounter::with_assumptions, py::arg("assumptions"),
             "Create a SolutionInformation with the given assumptions");

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
}

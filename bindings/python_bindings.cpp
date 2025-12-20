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
        .def(py::init<>())
        .def("solvable", &amc::SolutionInformation::solvable,
             "Check if the problem is solvable with current assumptions")
        .def("add_clause", &amc::SolutionInformation::add_clause, py::arg("literals"),
             "Add a clause to the solver (disjunction of literals)")
        .def("add_assumption", &amc::SolutionInformation::add_assumption, py::arg("literal"),
             "Add an assumption (literal that must be true)")
        .def("clear_assumptions", &amc::SolutionInformation::clear_assumptions,
             "Clear all assumptions");

    py::class_<SolutionTable>(m, "SolutionTable")
        .def(py::init<const std::vector<int64_t>&>(), py::arg("variables"),
             "Create a SolutionTable with the given variables (max 63 variables)")
        .def("__len__", &SolutionTable::size,
             "Get the number of possible assignments")
        .def("__getitem__", &SolutionTable::operator[], py::arg("index"),
             "Get the assignment at the given index")
        .def("add_variable", &SolutionTable::add_variable, py::arg("variable"),
             "Add a new variable to the table")
        .def("remove_matching", &SolutionTable::remove_matching, py::arg("assignment"),
             "Remove all rows matching the given assignment")
        .def("clone", &SolutionTable::clone,
             "Create a copy of this SolutionTable")
        .def("contains", &SolutionTable::contains, py::arg("variable"),
             "Check if a variable is in the table")
        .def_property_readonly("variables", &SolutionTable::get_variables,
             "Get the list of variables in the table");
}

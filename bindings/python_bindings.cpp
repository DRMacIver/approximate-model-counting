#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "solution_information.hpp"

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
}

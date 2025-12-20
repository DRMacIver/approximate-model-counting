"""Tests for internal C++ code not exposed to Python API."""

from tests._test_internals import (  # pyright: ignore[reportMissingModuleSource]
    check_bitvector_get_out_of_bounds,
    check_bitvector_size,
)


def test_bitvector_size_works():
    """BitVector::size() returns correct length."""
    check_bitvector_size()


def test_bitvector_get_out_of_bounds_returns_false():
    """BitVector::get() returns false for out-of-bounds access."""
    check_bitvector_get_out_of_bounds()

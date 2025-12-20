"""Type stubs for the C++ test internals module."""

def check_bitvector_size() -> None:
    """Check that BitVector::size() works correctly.

    Raises RuntimeError if the check fails.
    """
    ...

def check_bitvector_get_out_of_bounds() -> None:
    """Check that BitVector::get() returns false for out-of-bounds access.

    Raises RuntimeError if the check fails.
    """
    ...

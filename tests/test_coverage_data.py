"""Tests that exercise CNF files in tests/coverage_data/ for C++ coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from approximate_model_counting import ModelCounter, Status


def get_coverage_cnf_files() -> list[Path]:
    """Get all CNF files in the coverage_data directory."""
    coverage_dir = Path(__file__).parent / "coverage_data"
    return sorted(coverage_dir.glob("*.cnf"))


@pytest.fixture(params=get_coverage_cnf_files(), ids=lambda p: p.name)
def cnf_file(request: pytest.FixtureRequest) -> Path:
    """Fixture that provides each CNF file in coverage_data."""
    return request.param


class TestCoverageData:
    """Test suite for coverage data CNF files."""

    def test_cnf_loads_successfully(self, cnf_file: Path) -> None:
        """Test that each CNF file can be loaded."""
        mc = ModelCounter.from_file(str(cnf_file))
        assert mc is not None

    def test_cnf_exercises_solver(self, cnf_file: Path) -> None:
        """Test that each CNF exercises the solver and related methods."""
        mc = ModelCounter.from_file(str(cnf_file))
        info = mc.with_assumptions([])

        # Check solvability
        status = info.solvable()
        assert status in (Status.SATISFIABLE, Status.UNSATISFIABLE, Status.UNKNOWN)

        if status == Status.SATISFIABLE:
            # Exercise backbone computation
            backbone = info.get_backbone()
            assert isinstance(backbone, list)

            # Exercise solution table
            table = info.get_solution_table()
            assert len(table) >= 1

            # Exercise equivalence checking if we have backbone variables
            if len(backbone) >= 2:
                # Check self-equivalence
                assert info.are_equivalent(backbone[0], backbone[0])

            # Exercise table iteration
            if len(table) > 0:
                row = table[0]
                assert isinstance(row, list)


class TestSpecificCoverageScenarios:
    """Tests for specific coverage scenarios."""

    def test_empty_formula(self) -> None:
        """Empty formula has trivial solution."""
        mc = ModelCounter.from_file(str(Path(__file__).parent / "coverage_data" / "empty.cnf"))
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        # Empty formula should have empty backbone (no forced literals)
        backbone = info.get_backbone()
        assert backbone == []

    def test_constructor_from_clauses(self) -> None:
        """Test ModelCounter constructed from clauses directly."""
        clauses = [[1, 2], [-1, 2], [1, -2]]
        mc = ModelCounter(clauses)
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE

    def test_constructor_from_clauses_with_seed(self) -> None:
        """Test ModelCounter with seed parameter."""
        clauses = [[1, 2], [-1, -2]]
        mc = ModelCounter(clauses, seed=42)
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE

    def test_with_assumptions(self) -> None:
        """Test passing assumptions to with_assumptions."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "two_vars_sat.cnf")
        )
        # Assume x1 = true
        info = mc.with_assumptions([1])
        assert info.solvable() == Status.SATISFIABLE
        backbone = info.get_backbone()
        assert 1 in backbone

    def test_current_clauses(self) -> None:
        """Test current_clauses method."""
        clauses = [[1, 2], [-1, -2]]
        mc = ModelCounter(clauses)
        info = mc.with_assumptions([])
        current = info.current_clauses()
        assert isinstance(current, list)
        assert len(current) >= 0

    def test_march_score(self) -> None:
        """Test march_score method."""
        clauses = [[1, 2], [-1, -2], [2, 3]]
        mc = ModelCounter(clauses)
        assumptions: list[int] = []
        result = mc.march_score(assumptions)
        # Returns (scores_dict, updated_assumptions)
        assert isinstance(result, tuple)
        scores, _ = result
        assert isinstance(scores, dict)

    def test_unit_clause_in_backbone(self) -> None:
        """Unit clause should appear in backbone."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "unit_positive.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        backbone = info.get_backbone()
        assert 1 in backbone

    def test_negative_unit_in_backbone(self) -> None:
        """Negative unit clause should appear in backbone."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "unit_negative.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        backbone = info.get_backbone()
        assert -1 in backbone

    def test_unsat_formula(self) -> None:
        """Contradictory clauses should be unsatisfiable."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "unsat_units.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.UNSATISFIABLE

    def test_equivalence_detected(self) -> None:
        """Equivalent variables should be detected."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "equivalence.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        # Variables 1 and 2 should be equivalent
        assert info.are_equivalent(1, 2)

    def test_backbone_with_free_vars(self) -> None:
        """Formula with forced and free variables."""
        mc = ModelCounter.from_file(str(Path(__file__).parent / "coverage_data" / "backbone.cnf"))
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        backbone = info.get_backbone()
        # 1 should be in backbone (unit clause)
        assert 1 in backbone
        # 2 and 3 should not be in backbone (free variables)
        assert 2 not in backbone and -2 not in backbone

    def test_partition_split(self) -> None:
        """Test partition splitting with non-equivalent variables."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "partition_split.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        # Get backbone and table to trigger partition logic
        _ = info.get_backbone()
        table = info.get_solution_table()
        assert len(table) >= 1

    def test_invalid_file_raises(self) -> None:
        """Test that invalid file raises an error."""
        import pytest

        with pytest.raises(RuntimeError, match="Failed to read DIMACS file"):
            ModelCounter.from_file(str(Path(__file__).parent / "coverage_data" / "invalid.txt"))

    def test_large_table_size_limit(self) -> None:
        """Test that large table triggers MAX_TABLE_SIZE limit."""
        mc = ModelCounter.from_file(
            str(Path(__file__).parent / "coverage_data" / "large_table.cnf")
        )
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE
        # This should trigger the table size limit
        # The formula has 21 independent variable pairs, which would create 2^21 rows
        # But MAX_TABLE_SIZE (1,000,000) limits it to ~1 million rows
        table = info.get_solution_table()
        # Table should be limited by MAX_TABLE_SIZE (around 1-2 million, not 2^21)
        assert len(table) > 1_000_000  # Exceeded the limit (break triggered)
        assert len(table) < 2_100_000  # But not the full 2^21 ≈ 2.1 million

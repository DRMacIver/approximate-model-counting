"""Tests for the CLI module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from approximate_model_counting import ModelCounter, Status
from approximate_model_counting.cli import (
    build_solution_info,
    collect_cnf_files,
    main,
    process_file,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cnf(temp_dir: Path) -> Path:
    """Create a sample CNF file."""
    cnf_path = temp_dir / "sample.cnf"
    cnf_path.write_text("""\
c Sample CNF
p cnf 3 3
1 2 0
-1 -2 0
2 3 0
""")
    return cnf_path


@pytest.fixture
def unsat_cnf(temp_dir: Path) -> Path:
    """Create an UNSAT CNF file."""
    cnf_path = temp_dir / "unsat.cnf"
    cnf_path.write_text("""\
c UNSAT CNF
p cnf 1 2
1 0
-1 0
""")
    return cnf_path


class TestCollectCnfFiles:
    """Tests for collect_cnf_files."""

    def test_collects_single_file(self, sample_cnf: Path):
        result = collect_cnf_files((str(sample_cnf),))
        assert result == [sample_cnf]

    def test_collects_from_directory(self, temp_dir: Path, sample_cnf: Path):
        result = collect_cnf_files((str(temp_dir),))
        assert sample_cnf in result

    def test_collects_recursively(self, temp_dir: Path):
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        nested_cnf = subdir / "nested.cnf"
        nested_cnf.write_text("p cnf 1 1\n1 0\n")

        result = collect_cnf_files((str(temp_dir),))
        assert nested_cnf in result

    def test_empty_directory(self, temp_dir: Path):
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        result = collect_cnf_files((str(empty_dir),))
        assert result == []


class TestBuildSolutionInfo:
    """Tests for build_solution_info."""

    def test_basic_structure(self, sample_cnf: Path):
        mc = ModelCounter.from_file(str(sample_cnf))
        info = mc.with_assumptions([])
        result = build_solution_info(info)

        assert "backbone" in result
        assert "equivalence_classes" in result
        assert "table_variables" in result
        assert "table_size" in result
        assert "sample_rows" in result

    def test_backbone_is_list(self, sample_cnf: Path):
        mc = ModelCounter.from_file(str(sample_cnf))
        info = mc.with_assumptions([])
        result = build_solution_info(info)

        assert isinstance(result["backbone"], list)

    def test_sample_rows_limited_to_10(self, temp_dir: Path):
        # Create a formula with many solutions
        cnf_path = temp_dir / "many_solutions.cnf"
        cnf_path.write_text("p cnf 10 1\n1 2 3 4 5 6 7 8 9 10 0\n")

        mc = ModelCounter.from_file(str(cnf_path))
        info = mc.with_assumptions([])
        result = build_solution_info(info)

        assert len(result["sample_rows"]) <= 10


class TestProcessFile:
    """Tests for process_file."""

    def test_satisfiable_formula(self, sample_cnf: Path):
        result = process_file(sample_cnf, seed=42)

        assert result["file"] == str(sample_cnf)
        assert result["status"] == "SATISFIABLE"
        assert "root" in result
        assert "samples" in result

    def test_unsatisfiable_formula(self, unsat_cnf: Path):
        result = process_file(unsat_cnf, seed=42)

        assert result["status"] == "UNSATISFIABLE"
        assert result["samples"] == []

    def test_deterministic_with_seed(self, sample_cnf: Path):
        result1 = process_file(sample_cnf, seed=42)
        result2 = process_file(sample_cnf, seed=42)

        assert result1 == result2

    def test_samples_use_table_rows(self, sample_cnf: Path):
        result = process_file(sample_cnf, seed=42)

        # Should have some samples if the formula is SAT
        if result["status"] == "SATISFIABLE" and result["root"]["table_size"] > 0:
            assert len(result["samples"]) <= 10


class TestMainCli:
    """Tests for the main CLI command."""

    def test_no_paths_shows_message(self):
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "No paths specified" in result.output

    def test_processes_single_file(self, sample_cnf: Path):
        runner = CliRunner()
        result = runner.invoke(main, [str(sample_cnf), "--seed", "42"])
        assert result.exit_code == 0

        json_path = sample_cnf.with_suffix(".json")
        assert json_path.exists()

    def test_creates_json_output(self, sample_cnf: Path):
        runner = CliRunner()
        runner.invoke(main, [str(sample_cnf), "--seed", "42"])

        json_path = sample_cnf.with_suffix(".json")
        with open(json_path) as f:
            data = json.load(f)

        assert data["file"] == str(sample_cnf)
        assert data["status"] == "SATISFIABLE"

    def test_skips_existing_without_overwrite(self, sample_cnf: Path):
        json_path = sample_cnf.with_suffix(".json")
        json_path.write_text('{"existing": true}')

        runner = CliRunner()
        result = runner.invoke(main, [str(sample_cnf)])
        assert result.exit_code == 0

        # File should not have been overwritten
        with open(json_path) as f:
            data = json.load(f)
        assert data == {"existing": True}

    def test_overwrites_with_flag(self, sample_cnf: Path):
        json_path = sample_cnf.with_suffix(".json")
        json_path.write_text('{"existing": true}')

        runner = CliRunner()
        result = runner.invoke(main, [str(sample_cnf), "--overwrite", "--seed", "42"])
        assert result.exit_code == 0

        with open(json_path) as f:
            data = json.load(f)
        assert "existing" not in data
        assert data["status"] == "SATISFIABLE"

    def test_processes_directory(self, temp_dir: Path, sample_cnf: Path):
        runner = CliRunner()
        result = runner.invoke(main, [str(temp_dir), "--seed", "42"])
        assert result.exit_code == 0

        json_path = sample_cnf.with_suffix(".json")
        assert json_path.exists()

    def test_no_cnf_files_shows_message(self, temp_dir: Path):
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(main, [str(empty_dir)])
        assert result.exit_code == 0
        assert "No CNF files found" in result.output


class TestFromFile:
    """Tests for ModelCounter.from_file."""

    def test_reads_valid_cnf(self, sample_cnf: Path):
        mc = ModelCounter.from_file(str(sample_cnf))
        info = mc.with_assumptions([])
        assert info.solvable() == Status.SATISFIABLE

    def test_reads_unsat_cnf(self, unsat_cnf: Path):
        mc = ModelCounter.from_file(str(unsat_cnf))
        info = mc.with_assumptions([])
        assert info.solvable() == Status.UNSATISFIABLE

    def test_raises_on_missing_file(self, temp_dir: Path):
        with pytest.raises(RuntimeError, match="Failed to read DIMACS file"):
            ModelCounter.from_file(str(temp_dir / "nonexistent.cnf"))

    def test_with_seed(self, sample_cnf: Path):
        mc1 = ModelCounter.from_file(str(sample_cnf), seed=42)
        mc2 = ModelCounter.from_file(str(sample_cnf), seed=42)

        info1 = mc1.with_assumptions([])
        info2 = mc2.with_assumptions([])

        table1 = info1.get_solution_table()
        table2 = info2.get_solution_table()

        assert len(table1) == len(table2)
        assert list(table1.variables) == list(table2.variables)

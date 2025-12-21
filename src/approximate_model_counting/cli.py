"""Command-line interface for processing CNF files."""

from __future__ import annotations

import json
import random
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.progress import Progress, TaskID

from approximate_model_counting import ModelCounter, SolutionInformation, Status

if TYPE_CHECKING:
    from collections.abc import Iterator

# Default timeout in seconds (10 minutes)
DEFAULT_TIMEOUT = 600


def collect_cnf_files(paths: tuple[str, ...]) -> list[Path]:
    """Collect all CNF files from the given paths (files or directories)."""
    cnf_files: list[Path] = []
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            cnf_files.append(path)
        elif path.is_dir():
            cnf_files.extend(path.rglob("*.cnf"))
    return cnf_files


def build_solution_info(info: SolutionInformation) -> dict[str, Any]:
    """Extract solution information to a JSON-serializable dict."""
    backbone = list(info.get_backbone())
    table = info.get_solution_table()

    # Build equivalence classes (only multi-variable classes)
    equiv_classes: list[list[int]] = []
    seen: set[int] = set()
    for var in table.variables:
        if var in seen:
            continue
        equiv_class = [var]
        for other in table.variables:
            if other != var and info.are_equivalent(var, other):
                equiv_class.append(other)
                seen.add(other)
        if len(equiv_class) > 1:
            equiv_classes.append(sorted(equiv_class, key=abs))
        seen.add(var)

    # Sample up to 10 rows
    sample_rows: list[list[int]] = []
    for i in range(min(10, len(table))):
        sample_rows.append(list(table[i]))

    return {
        "backbone": backbone,
        "equivalence_classes": equiv_classes,
        "table_variables": list(table.variables),
        "table_size": len(table),
        "sample_rows": sample_rows,
    }


def process_file(cnf_path: Path, seed: int | None) -> dict[str, Any]:
    """Process a single CNF file and return JSON-serializable result."""
    mc = ModelCounter.from_file(str(cnf_path), seed=seed)

    # Root analysis (no assumptions)
    root_info = mc.with_assumptions([])
    result: dict[str, Any] = {
        "file": str(cnf_path),
        "status": root_info.solvable().name,
        "root": build_solution_info(root_info),
        "samples": [],
    }

    if root_info.solvable() == Status.SATISFIABLE:
        table = root_info.get_solution_table()
        # Sample 10 random rows
        if len(table) > 0:
            rng = random.Random(seed)
            num_samples = min(10, len(table))
            indices = rng.sample(range(len(table)), num_samples)
            for idx in indices:
                row = list(table[idx])
                sample_info = mc.with_assumptions(row)
                result["samples"].append(build_solution_info(sample_info))

    return result


def _process_file_wrapper(args: tuple[Path, int | None]) -> tuple[Path, dict[str, Any]]:
    """Wrapper for process_file for use with ProcessPoolExecutor."""
    cnf_path, seed = args
    return cnf_path, process_file(cnf_path, seed)


def make_timeout_result(cnf_path: Path, timeout_seconds: float) -> dict[str, Any]:
    """Create a placeholder result for a timed-out file."""
    return {
        "file": str(cnf_path),
        "status": "TIMEOUT",
        "timeout_seconds": timeout_seconds,
        "root": None,
        "samples": [],
    }


def process_files_with_progress(
    cnf_files: list[Path],
    seed: int | None,
    workers: int | None,
    overwrite: bool,
    timeout: float | None,
) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Process files in parallel with progress tracking.

    Args:
        cnf_files: List of CNF files to process.
        seed: RNG seed for reproducibility.
        workers: Number of parallel workers.
        overwrite: Whether to overwrite existing JSON files.
        timeout: Timeout in seconds per file, or None to disable.
    """
    files_to_process: list[Path] = []
    for cnf in cnf_files:
        json_path = cnf.with_suffix(".json")
        if not overwrite and json_path.exists():
            continue
        files_to_process.append(cnf)

    if not files_to_process:
        return

    with Progress() as progress:
        task: TaskID = progress.add_task("Processing CNF files...", total=len(files_to_process))
        with ProcessPoolExecutor(max_workers=workers) as executor:
            args = [(f, seed) for f in files_to_process]
            futures = {executor.submit(_process_file_wrapper, arg): arg[0] for arg in args}
            for future in as_completed(futures):
                cnf_path = futures[future]
                try:
                    _, result = future.result(timeout=timeout)
                except TimeoutError:
                    # Cancel the future and create a timeout result
                    future.cancel()
                    result = make_timeout_result(cnf_path, timeout if timeout else 0)
                progress.advance(task)
                yield cnf_path, result


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--seed", type=int, default=None, help="RNG seed for reproducibility")
@click.option("--overwrite/--no-overwrite", default=False, help="Overwrite existing JSON files")
@click.option("--workers", "-j", type=int, default=None, help="Number of parallel workers")
@click.option(
    "--timeout",
    "-t",
    type=float,
    default=DEFAULT_TIMEOUT,
    help=f"Timeout per file in seconds (default: {DEFAULT_TIMEOUT}s = 10 min, 0 to disable)",
)
@click.option("--tui", is_flag=True, help="Use Textual TUI instead of progress bar")
def main(
    paths: tuple[str, ...],
    seed: int | None,
    overwrite: bool,
    workers: int | None,
    timeout: float,
    tui: bool,
) -> None:
    """Process CNF files and output solution information as JSON.

    PATHS can be CNF files or directories (searched recursively for *.cnf files).
    Output files are written alongside input files with .json extension.
    """
    if not paths:
        click.echo("No paths specified. Use --help for usage information.")
        return

    cnf_files = collect_cnf_files(paths)

    if not cnf_files:
        click.echo("No CNF files found.")
        return

    # Convert timeout=0 to None (disabled)
    effective_timeout = timeout if timeout > 0 else None

    if tui:
        from approximate_model_counting.tui import run_tui

        run_tui(cnf_files, seed, overwrite, workers, effective_timeout)
    else:
        for cnf_path, result in process_files_with_progress(
            cnf_files, seed, workers, overwrite, effective_timeout
        ):
            json_path = cnf_path.with_suffix(".json")
            json_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze all benchmark CNF files and generate JSON sidecars + summary markdown."""

import json
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, median, stdev


def analyze_file(cnf_path: Path, analyzer_path: Path, timeout: int = 60) -> dict | None:
    """Run analyzer on a single CNF file."""
    try:
        result = subprocess.run(
            [str(analyzer_path), str(cnf_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": f"Analyzer failed: {result.stderr}", "file": str(cnf_path)}
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "file": str(cnf_path)}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "file": str(cnf_path)}
    except Exception as e:
        return {"error": str(e), "file": str(cnf_path)}


def categorize(data: dict) -> list[str]:
    """Assign categories based on analysis results."""
    categories = []

    if "error" in data:
        categories.append("error")
        return categories

    # Solvability
    solv = data.get("solvability", "UNKNOWN")
    if solv == "SAT":
        categories.append("satisfiable")
    elif solv == "UNSAT":
        categories.append("unsatisfiable")
    else:
        categories.append("hard-to-solve")

    # Size categories
    vars = data.get("variables", 0)
    clauses = data.get("clauses", 0)
    if vars < 100:
        categories.append("tiny")
    elif vars < 1000:
        categories.append("small")
    elif vars < 10000:
        categories.append("medium")
    else:
        categories.append("large")

    # Structure
    if data.get("unit_clauses", 0) > vars * 0.1:
        categories.append("many-units")
    if data.get("pure_literals", 0) > vars * 0.1:
        categories.append("many-pure")
    if data.get("density", 0) > 10:
        categories.append("dense")
    if data.get("density", 0) < 2:
        categories.append("sparse")

    # Backbone
    backbone = data.get("backbone_size", -1)
    if backbone > 0 and vars > 0:
        backbone_ratio = backbone / vars
        if backbone_ratio > 0.5:
            categories.append("large-backbone")
        elif backbone_ratio < 0.01:
            categories.append("tiny-backbone")

    # Table size
    table = data.get("table_size", -1)
    if table == 1:
        categories.append("unique-solution")
    elif table > 10000:
        categories.append("many-solutions")

    return categories


def generate_summary(all_results: list[dict], output_path: Path):
    """Generate summary markdown from all results."""
    # Separate successful and failed
    successful = [r for r in all_results if "error" not in r]
    failed = [r for r in all_results if "error" in r]

    # Aggregate stats
    by_solvability = defaultdict(list)
    by_category = defaultdict(list)
    interesting = []

    for r in successful:
        by_solvability[r.get("solvability", "UNKNOWN")].append(r)
        cats = categorize(r)
        for cat in cats:
            by_category[cat].append(r)

        # Flag interesting cases
        dominated_categories = {"satisfiable", "unsatisfiable", "small", "medium", "tiny", "large"}
        dominated_categories |= {"hard-to-solve"}
        dominated_categories |= {"sparse", "dense"}
        dominated_categories |= {"tiny-backbone"}
        dominated_categories |= {"error"}
        dominated_categories |= {"many-solutions"}
        dominated_categories |= {"large-backbone"}
        unique_cats = set(cats) - dominated_categories
        if unique_cats or "unique-solution" in cats or "hard-to-solve" in cats:
            interesting.append((r, cats))

    # Build markdown
    lines = ["# Benchmark Analysis Summary\n"]
    lines.append(f"Total files analyzed: {len(all_results)}\n")
    lines.append(f"Successful: {len(successful)}, Failed/Timeout: {len(failed)}\n")

    # Solvability breakdown
    lines.append("\n## Solvability\n")
    for solv in ["SAT", "UNSAT", "UNKNOWN"]:
        count = len(by_solvability[solv])
        pct = 100 * count / len(all_results) if all_results else 0
        lines.append(f"- **{solv}**: {count} ({pct:.1f}%)\n")

    # Size distribution
    lines.append("\n## Size Distribution\n")
    if successful:
        vars_list = [r["variables"] for r in successful]
        clauses_list = [r["clauses"] for r in successful]
        lines.append(f"- Variables: min={min(vars_list)}, max={max(vars_list)}, ")
        lines.append(f"median={median(vars_list):.0f}, mean={mean(vars_list):.0f}\n")
        lines.append(f"- Clauses: min={min(clauses_list)}, max={max(clauses_list)}, ")
        lines.append(f"median={median(clauses_list):.0f}, mean={mean(clauses_list):.0f}\n")

    # Category counts
    lines.append("\n## Categories\n")
    for cat in sorted(by_category.keys()):
        count = len(by_category[cat])
        lines.append(f"- **{cat}**: {count}\n")

    # Interesting files
    lines.append("\n## Notable Files\n")

    # Unique solutions
    unique_sol = [r for r in successful if r.get("table_size") == 1]
    if unique_sol:
        lines.append("\n### Unique Solution (table_size=1)\n")
        for r in unique_sol[:20]:
            name = Path(r["file"]).name
            lines.append(f"- `{name}`: {r['variables']} vars, {r['clauses']} clauses\n")
        if len(unique_sol) > 20:
            lines.append(f"- ... and {len(unique_sol) - 20} more\n")

    # Hard to solve
    hard = by_category.get("hard-to-solve", [])
    if hard:
        lines.append("\n### Hard to Solve (UNKNOWN with 100k conflicts)\n")
        for r in hard[:20]:
            name = Path(r["file"]).name
            lines.append(f"- `{name}`: {r['variables']} vars, {r['clauses']} clauses\n")
        if len(hard) > 20:
            lines.append(f"- ... and {len(hard) - 20} more\n")

    # Large backbone
    large_bb = by_category.get("large-backbone", [])
    if large_bb:
        lines.append("\n### Large Backbone (>50% of variables)\n")
        for r in sorted(large_bb, key=lambda x: -x.get("backbone_size", 0) / max(x.get("variables", 1), 1))[:20]:
            name = Path(r["file"]).name
            bb = r.get("backbone_size", 0)
            vars = r.get("variables", 1)
            lines.append(f"- `{name}`: backbone={bb}/{vars} ({100*bb/vars:.1f}%)\n")

    # Many units
    many_units = by_category.get("many-units", [])
    if many_units:
        lines.append("\n### Many Unit Clauses (>10% of variables)\n")
        for r in sorted(many_units, key=lambda x: -x.get("unit_clauses", 0))[:10]:
            name = Path(r["file"]).name
            units = r.get("unit_clauses", 0)
            lines.append(f"- `{name}`: {units} unit clauses\n")

    # Failed/timeout
    if failed:
        lines.append("\n### Failed or Timeout\n")
        for r in failed[:20]:
            name = Path(r["file"]).name
            err = r.get("error", "unknown")
            lines.append(f"- `{name}`: {err}\n")
        if len(failed) > 20:
            lines.append(f"- ... and {len(failed) - 20} more\n")

    # Typical behavior summary
    lines.append("\n## Typical Behavior\n")
    if successful:
        sat_count = len(by_solvability["SAT"])
        unsat_count = len(by_solvability["UNSAT"])
        lines.append(f"The benchmark set is roughly {100*sat_count/len(successful):.0f}% satisfiable, ")
        lines.append(f"{100*unsat_count/len(successful):.0f}% unsatisfiable.\n\n")

        solve_times = [r["solve_time_ms"] for r in successful if "solve_time_ms" in r]
        if solve_times:
            lines.append(f"Solve times range from {min(solve_times):.1f}ms to {max(solve_times):.1f}ms ")
            lines.append(f"(median {median(solve_times):.1f}ms).\n\n")

        densities = [r["density"] for r in successful if "density" in r]
        if densities:
            lines.append(f"Clause/variable density ranges from {min(densities):.2f} to {max(densities):.2f} ")
            lines.append(f"(median {median(densities):.2f}).\n")

    output_path.write_text("".join(lines))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze benchmark CNF files")
    parser.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks/data"))
    parser.add_argument("--analyzer", type=Path, default=Path("build/analyze_cnf"))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true", help="Skip files with existing JSON")
    args = parser.parse_args()

    if not args.analyzer.exists():
        print(f"Analyzer not found: {args.analyzer}", file=sys.stderr)
        print("Run: cmake --build build --target analyze_cnf", file=sys.stderr)
        sys.exit(1)

    cnf_files = sorted(args.benchmark_dir.rglob("*.cnf"))
    print(f"Found {len(cnf_files)} CNF files")

    if args.skip_existing:
        cnf_files = [f for f in cnf_files if not f.with_suffix(f.suffix + ".json").exists()]
        print(f"Analyzing {len(cnf_files)} files (skipping existing)")

    all_results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(analyze_file, cnf, args.analyzer.resolve(), args.timeout): cnf
            for cnf in cnf_files
        }

        for future in as_completed(futures):
            cnf_path = futures[future]
            result = future.result()
            completed += 1

            if result:
                # Write JSON sidecar
                json_path = cnf_path.with_suffix(cnf_path.suffix + ".json")
                json_path.write_text(json.dumps(result, indent=2))
                all_results.append(result)

                status = result.get("solvability", result.get("error", "?"))
                print(f"[{completed}/{len(cnf_files)}] {cnf_path.name}: {status}")
            else:
                print(f"[{completed}/{len(cnf_files)}] {cnf_path.name}: failed")

    # Also load any existing JSON files not processed this run
    if args.skip_existing:
        for json_file in args.benchmark_dir.rglob("*.cnf.json"):
            try:
                data = json.loads(json_file.read_text())
                if data not in all_results:
                    all_results.append(data)
            except Exception:
                pass

    # Generate summary
    summary_path = args.benchmark_dir / "ANALYSIS.md"
    generate_summary(all_results, summary_path)
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()

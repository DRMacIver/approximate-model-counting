#!/usr/bin/env python3
"""Download Model Counting Competition benchmarks from Zenodo.

This script downloads benchmark instances from the Model Counting Competition
(https://mccompetition.org/) for years 2020-2024.

Usage:
    python download.py [--track TRACK] [--year YEAR] [--all]

By default, downloads only Track 1 (Model Counting) benchmarks.
Use --all to download all tracks.
"""

from __future__ import annotations

import argparse
import lzma
import sys
import tarfile
import urllib.request
from pathlib import Path

# Zenodo record IDs for each year
ZENODO_RECORDS = {
    2024: "14249068",
    2023: "10012864",
    2022: "10012860",
    2021: "13988776",
    2020: "10031810",
}

# Available tracks per year
# Track 1: Model Counting (MC)
# Track 2: Weighted Model Counting (WMC)
# Track 3: Projected Model Counting (PMC)
# Track 4: Projected Weighted Model Counting (PWMC) or MC2 (2021)
TRACKS = {
    2024: {
        1: "mc2024-track1-mc_competition.tar",
        2: "mc2024-track2-wmc_competition.tar",
        "2b": "mc2024-track2b-wmc_bonus_competition.tar",
        3: "mc2024-track3-pmc_competition.tar",
        4: "mc2024-track4-pwmc_competition.tar",
    },
    2023: {
        1: "mc2023-track1-mc_competition.tar",
        2: "mc2023-track2-wmc_competition.tar",
        3: "mc2023-track3-pmc_competition.tar",
        4: "mc2023-track4-pwmc_competition.tar",
    },
    2022: {
        1: "mc2022-track1-mc_competition.tar",
        2: "mc2022-track2-wmc_competition.tar",
        3: "mc2022-track3-pmc_competition.tar",
        4: "mc2022-track4-pwmc_competition.tar",
    },
    2021: {
        1: "mc2021-track1-mc_competition.tar",
        2: "mc2021-track2-wmc_competition.tar",
        3: "mc2021-track3-pmc_competition.tar",
        4: "mc2021-track4-mc2_competition.tar",  # Different naming in 2021
    },
    2020: {
        1: "mc2020-track1-mc_competition.tar",
        2: "mc2020-track2-wmc_competition.tar",
        3: "mc2020-track3-pmc_competition.tar",
        # No track 4 in 2020
    },
}

TRACK_DESCRIPTIONS = {
    1: "Model Counting (MC)",
    2: "Weighted Model Counting (WMC)",
    "2b": "Weighted Model Counting Bonus (WMC)",
    3: "Projected Model Counting (PMC)",
    4: "Projected Weighted Model Counting (PWMC)",
}


def get_download_url(year: int, filename: str) -> str:
    """Get the Zenodo download URL for a file."""
    record_id = ZENODO_RECORDS[year]
    # Use the content endpoint for direct file download
    return f"https://zenodo.org/api/records/{record_id}/files/{filename}/content"


def download_file(url: str, dest: Path, desc: str) -> bool:
    """Download a file with progress indication."""
    print(f"Downloading {desc}...")
    print(f"  URL: {url}")
    print(f"  Destination: {dest}")

    try:
        # Create a simple progress indicator
        def report_progress(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 // total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\r  Progress: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="")

        urllib.request.urlretrieve(url, dest, reporthook=report_progress)
        print()  # Newline after progress
        return True
    except Exception as e:
        print(f"\n  Error: {e}")
        return False


def extract_tar(tar_path: Path, extract_dir: Path) -> bool:
    """Extract a tar archive."""
    print(f"  Extracting to {extract_dir}...")
    try:
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"  Error extracting: {e}")
        return False


def decompress_xz_files(directory: Path) -> int:
    """Decompress all .cnf.xz files in a directory tree."""
    count = 0
    xz_files = list(directory.rglob("*.cnf.xz"))
    if not xz_files:
        return 0

    print(f"  Decompressing {len(xz_files)} .cnf.xz files...")
    for xz_path in xz_files:
        cnf_path = xz_path.with_suffix("")  # Remove .xz suffix
        if cnf_path.exists():
            continue
        try:
            with lzma.open(xz_path, "rb") as xz_file, open(cnf_path, "wb") as cnf_file:
                cnf_file.write(xz_file.read())
            xz_path.unlink()  # Remove the .xz file after decompression
            count += 1
        except Exception as e:
            print(f"    Error decompressing {xz_path}: {e}")
    print(f"  Decompressed {count} files")
    return count


def download_track(
    year: int,
    track: int | str,
    base_dir: Path,
    extract: bool = True,
    keep_tar: bool = False,
) -> bool:
    """Download a specific track for a specific year."""
    if year not in TRACKS:
        print(f"Error: Year {year} not available")
        return False

    if track not in TRACKS[year]:
        print(f"Error: Track {track} not available for year {year}")
        return False

    filename = TRACKS[year][track]
    url = get_download_url(year, filename)

    # Create year directory
    year_dir = base_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    tar_path = year_dir / filename
    track_desc = TRACK_DESCRIPTIONS.get(track, f"Track {track}")
    desc = f"{year} {track_desc}"

    # Check if already extracted
    extract_marker = year_dir / f".extracted_{filename}"
    if extract_marker.exists():
        print(f"Skipping {desc} (already extracted)")
        return True

    # Download if needed
    if not tar_path.exists():
        if not download_file(url, tar_path, desc):
            return False
    else:
        print(f"Using cached {tar_path}")

    # Extract
    if extract:
        if extract_tar(tar_path, year_dir):
            # Decompress any .xz files
            decompress_xz_files(year_dir)
            extract_marker.touch()
            if not keep_tar:
                tar_path.unlink()
                print(f"  Removed {tar_path}")
        else:
            return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Model Counting Competition benchmarks from Zenodo."
    )
    parser.add_argument(
        "--track",
        type=str,
        default="1",
        help="Track to download (1=MC, 2=WMC, 3=PMC, 4=PWMC, all=all tracks). Default: 1",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Year to download (2020-2024). Default: all years",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all tracks for all years",
    )
    parser.add_argument(
        "--keep-tar",
        action="store_true",
        help="Keep tar files after extraction",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Don't extract tar files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: benchmarks/data",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tracks and years",
    )

    args = parser.parse_args()

    if args.list:
        print("Available benchmarks:")
        print()
        for year in sorted(ZENODO_RECORDS.keys(), reverse=True):
            print(f"  {year}:")
            for track, filename in TRACKS[year].items():
                desc = TRACK_DESCRIPTIONS.get(track, f"Track {track}")
                print(f"    Track {track}: {desc}")
                print(f"      File: {filename}")
            print()
        return 0

    # Determine output directory
    if args.output_dir:
        base_dir = args.output_dir
    else:
        script_dir = Path(__file__).parent
        base_dir = script_dir / "data"

    base_dir.mkdir(parents=True, exist_ok=True)

    # Determine years to download
    years = [args.year] if args.year else sorted(ZENODO_RECORDS.keys())

    # Determine tracks to download
    if args.all or args.track.lower() == "all":
        tracks_to_download = None  # All tracks
    else:
        try:
            tracks_to_download = [int(args.track)]
        except ValueError:
            tracks_to_download = [args.track]  # For "2b"

    print(f"Output directory: {base_dir}")
    print()

    success_count = 0
    fail_count = 0

    for year in years:
        tracks = tracks_to_download or list(TRACKS[year].keys())
        for track in tracks:
            if track not in TRACKS.get(year, {}):
                continue
            if download_track(
                year,
                track,
                base_dir,
                extract=not args.no_extract,
                keep_tar=args.keep_tar,
            ):
                success_count += 1
            else:
                fail_count += 1

    print()
    print(f"Downloaded: {success_count} tracks")
    if fail_count:
        print(f"Failed: {fail_count} tracks")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

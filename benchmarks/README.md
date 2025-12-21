# Model Counting Competition Benchmarks

This directory contains scripts to download and manage benchmarks from the
[Model Counting Competition](https://mccompetition.org/).

## Quick Start

Download all Track 1 (Model Counting) benchmarks from 2020-2024:

```bash
python download.py
```

This will download and decompress 1000 benchmark instances (200 per year) to
`benchmarks/data/`. The compressed archives are approximately 170 MB total.

## Available Tracks

The Model Counting Competition has multiple tracks:

| Track | Name | Description |
|-------|------|-------------|
| 1 | MC | Model Counting - count all satisfying assignments |
| 2 | WMC | Weighted Model Counting - count with literal weights |
| 3 | PMC | Projected Model Counting - count over subset of variables |
| 4 | PWMC | Projected Weighted Model Counting - weighted + projected |

For approximate model counting, **Track 1 (MC)** is the most relevant.

## Download Options

```bash
# Download only Track 1 (default)
python download.py

# Download all tracks
python download.py --all

# Download specific year
python download.py --year 2024

# Download specific track
python download.py --track 3

# List available benchmarks
python download.py --list

# Keep tar files after extraction
python download.py --keep-tar

# Custom output directory
python download.py --output-dir /path/to/dir
```

## Data Sources

All benchmarks are hosted on Zenodo:

| Year | Zenodo Record | DOI |
|------|---------------|-----|
| 2024 | [14249068](https://zenodo.org/records/14249068) | 10.5281/zenodo.14249068 |
| 2023 | [10012864](https://zenodo.org/records/10012864) | 10.5281/zenodo.10012864 |
| 2022 | [10012860](https://zenodo.org/records/10012860) | 10.5281/zenodo.10012860 |
| 2021 | [13988776](https://zenodo.org/records/13988776) | 10.5281/zenodo.13988776 |
| 2020 | [10031810](https://zenodo.org/records/10031810) | 10.5281/zenodo.10031810 |

## File Format

The benchmarks are in DIMACS CNF format (`.cnf` files). After extraction,
the directory structure will be:

```
data/
├── 2024/
│   └── mc2024_track1/
│       ├── instance1.cnf
│       ├── instance2.cnf
│       └── ...
├── 2023/
│   └── mc2023_track1/
│       └── ...
└── ...
```

## Using with the CLI

After downloading, you can process benchmarks with the `amc` CLI:

```bash
# Process all 2024 benchmarks
amc benchmarks/data/2024/ --seed 42 -j 4

# Process with timeout (default 10 min)
amc benchmarks/data/2024/ --timeout 300

# Use the TUI for progress
amc benchmarks/data/2024/ --tui
```

## Citation

If you use these benchmarks, please cite the Model Counting Competition:

```bibtex
@misc{mc_competition,
  title = {Model Counting Competition},
  url = {https://mccompetition.org/},
  note = {Benchmarks available at https://mccompetition.org/past_iterations}
}
```

## License

The benchmarks are provided by the Model Counting Competition organizers.
See the individual Zenodo records for license information.

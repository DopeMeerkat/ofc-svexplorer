# Echo Analysis

## Purpose

Dummy tool for verifying the tool discovery and execution pipeline. Does not perform real scientific analysis.

## Inputs

- `input_path`: Path to a CSV or JSON file with data.
- `output_dir`: Directory where results are written.

## Outputs

- `metrics.json` — execution metadata and basic statistics.
- `results.csv` — echoed input with an added `echo_label` column.
- `stdout.log` — captured standard output.

## Constraints

- CPU-only, no GPU required.
- Maximum runtime: 30 seconds.
- No access to production database.

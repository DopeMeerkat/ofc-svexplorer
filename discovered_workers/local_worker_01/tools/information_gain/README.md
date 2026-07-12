# Information Gain

Computes information gain for each feature against a target column.

## Inputs

- `input_path`: CSV with features and target.
- `output_dir`: Output directory.
- `target_column` (optional): Target column name. Defaults to last column.

## Outputs

- `metrics.json`: Top features, row count, execution time.
- `feature_ranking.csv`: All features sorted by information gain.
- `results.csv`: Echoed input data.

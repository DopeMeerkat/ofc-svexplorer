# Decision Tree Classifier

Trains a decision tree classifier on phenotype-feature data.

## Inputs

- `input_path`: CSV with features and target.
- `output_dir`: Output directory.
- `target_column` (optional): Target column. Defaults to last column.
- `random_state` (optional): Random seed. Default 42.

## Outputs

- `metrics.json`: Accuracy, F1, execution metadata.
- `feature_importance.csv`: Features sorted by importance.
- `results.csv`: Echoed input data.

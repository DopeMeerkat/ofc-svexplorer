# Random Forest Classifier

Trains a random forest classifier on phenotype-feature data.

## Inputs

- `input_path`: CSV with features and target.
- `output_dir`: Output directory.
- `target_column` (optional): Target column. Defaults to last column.
- `n_estimators` (optional): Number of trees. Default 100.
- `random_state` (optional): Random seed. Default 42.

## Outputs

- `metrics.json`: Accuracy, F1, ROC-AUC, execution metadata.
- `feature_importance.csv`: Features sorted by importance.
- `results.csv`: Echoed input data.

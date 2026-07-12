"""
OFC Visualization Uploader page for information-gain, Manhattan, bar plots, and SV statistics.
"""

import base64
import io
import math
from pathlib import Path

from dash import html, dcc, callback, Input, Output, State, no_update, dash_table
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import entropy as scipy_entropy
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from utils.manhattan import (
    DEFAULT_DB_PATH,
    chrom_sort_key,
    clean_item_id,
    connect_readonly,
    load_gene_locations,
    load_sv_locations,
    prepare_plot_points,
    split_event_group,
)
from utils.styling import UCONN_NAVY


BAR_X_AXES = {
    'gender': {'label': 'Gender', 'sql': 'p.gender'},
    'race': {'label': 'Race', 'sql': 'p.race'},
    'chrom': {'label': 'Chromosome', 'sql': 'ps.chrom'},
    'child': {'label': 'Child', 'sql': 'p.child'},
    'proband': {'label': 'Proband', 'sql': 'p.proband'},
    'affected': {'label': 'Affected', 'sql': 'p.affected'},
    'pheno': {'label': 'Phenotype', 'sql': 'p.pheno'},
    'sv_type': {'label': 'SV Type', 'sql': 'ps.type'},
    'sv_length_distribution': {'label': 'SV Length Distribution'},
}

BAR_Y_METRICS = {
    'unique_svs': {'label': 'Unique SVs', 'sql': 'COUNT(DISTINCT ps.id)'},
    'samples': {'label': 'Samples', 'sql': 'COUNT(DISTINCT ps.sample)'},
}

MAX_BAR_CATEGORIES = 25

PRESET_DATASETS = {
    'gene_pairs': {
        'filename': '2pair_gene.parquet',
        'path': Path(__file__).resolve().parents[1] / '2pair_gene.parquet',
        'kind': 'gene',
    },
    'sv_pairs': {
        'filename': '2pair_sv.parquet',
        'path': Path(__file__).resolve().parents[1] / '2pair_sv.parquet',
        'kind': 'gene',
    },
}


def entropy(column):
    """Calculate entropy of a column."""
    _, counts = np.unique(column, return_counts=True)
    probs = counts / len(column)
    return scipy_entropy(probs, base=2)


def information_gain(data, feature, target):
    """Calculate information gain for a feature."""
    original_entropy = entropy(data[target].values)
    total_rows = len(data)
    weighted_entropy = 0
    for value in data[feature].unique():
        subset = data[data[feature] == value]
        prob = len(subset) / total_rows
        weighted_entropy += prob * entropy(subset[target].values)
    return original_entropy - weighted_entropy


def conditional_entropy(data, feature, target):
    """Calculate conditional entropy for a feature."""
    total = len(data)
    ce = 0.0
    for value in data[feature].unique():
        subset = data[data[feature] == value]
        prob = len(subset) / total
        ce += prob * entropy(subset[target].values)
    return ce


def parse_uploaded_csv(contents, filename):
    """Decode an uploaded CSV into a DataFrame."""
    if not filename or not filename.lower().endswith('.csv'):
        raise ValueError('Please upload a CSV file.')

    _, content_string = contents.split(',', 1)
    decoded = base64.b64decode(content_string)
    return pd.read_csv(io.StringIO(decoded.decode('utf-8')))


def load_preset_points(preset):
    """Load precomputed Manhattan points from a known server-side parquet file."""
    dataset = PRESET_DATASETS.get(preset)
    if dataset is None:
        raise ValueError('Unknown preexisting dataset.')
    if not dataset['path'].is_file():
        raise FileNotFoundError(f"Preexisting dataset not found: {dataset['filename']}")

    points = pd.read_parquet(dataset['path'])
    required = {'chrom', 'x', 'neg_log10_p', 'plotted_item', 'partner_item', 'start', 'end', 'p_value'}
    missing = sorted(required - set(points.columns))
    if missing:
        raise ValueError(f"Precomputed Manhattan data is missing columns: {', '.join(missing)}")

    points.attrs['chrom_centers'] = points.groupby('chrom')['x'].agg(lambda values: (values.min() + values.max()) / 2).to_dict()
    return points, dataset


def create_preview_table(df, details=None):
    details = details or []
    return html.Div([
        html.H4('Data Preview', style={'color': UCONN_NAVY, 'fontSize': '18px'}),
        *[html.P(detail, style={'marginBottom': '5px'}) for detail in details],
        html.Div(
            dcc.Markdown(df.head().to_markdown(index=False)),
            style={'overflowX': 'auto', 'whiteSpace': 'nowrap', 'fontFamily': 'monospace'},
        ),
    ], style={'marginBottom': '30px'})


def information_gain_features(df, target_col):
    """Use zero-containing indicator columns as information-gain features."""
    features = []
    excluded = []
    for column in df.columns:
        if column == target_col:
            continue
        numeric_values = pd.to_numeric(df[column], errors='coerce')
        if numeric_values.eq(0).any():
            features.append(column)
        else:
            excluded.append(column)
    return features, excluded


def render_information_gain(df, filename):
    """Create the existing information-gain visualization."""
    if df.empty:
        raise ValueError('The uploaded CSV is empty.')

    all_columns = df.columns.tolist()
    target_col = all_columns[-1]
    features, excluded_features = information_gain_features(df, target_col)
    if not features:
        raise ValueError(
            'Information gain requires at least one feature column containing a zero. '
            'The final column is used as the target.'
        )

    encoded_df = df.copy()
    for col in encoded_df.columns:
        if encoded_df[col].dtype == 'object':
            encoded_df[col], _ = pd.factorize(encoded_df[col])

    target_entropy = entropy(encoded_df[target_col].values)
    ig_results = []
    for feature in features:
        ig_results.append({
            'Feature': feature,
            'Score': information_gain(encoded_df, feature, target_col),
            'Conditional Entropy': conditional_entropy(encoded_df, feature, target_col),
        })

    ig_df = pd.DataFrame(ig_results).sort_values('Score', ascending=False)
    fig = px.bar(
        ig_df,
        x='Score',
        y='Feature',
        color='Score',
        color_continuous_scale='viridis',
        labels={'Score': 'Information Gain', 'Feature': 'Feature'},
        title=f'Information Gain between Features and Target ({target_col})',
        height=max(500, len(ig_df) * 50),
        custom_data=['Conditional Entropy'],
    )
    fig.update_traces(
        hovertemplate='<b>%{y}</b><br>Information gain: %{x:.5f}<br>Conditional entropy: %{customdata[0]:.5f}<extra></extra>'
    )
    fig.update_layout(
        bargap=0.3,
        bargroupgap=0.1,
        margin=dict(l=120, r=40, t=80, b=80),
        yaxis=dict(automargin=True),
    )
    fig.add_annotation(
        x=0,
        y=-1.5,
        text=f'Target Entropy ({target_col}): {target_entropy:.4f}',
        showarrow=False,
        xanchor='left',
        yanchor='top',
        font={'size': 14, 'color': UCONN_NAVY},
    )

    return html.Div([
        html.H5(f'File: {filename}', style={'marginTop': '20px', 'marginBottom': '15px'}),
        create_preview_table(encoded_df, [
            f'Target column: {target_col}',
            f'Analyzed zero-containing features: {len(features):,}',
            f'Excluded columns without zeros: {", ".join(excluded_features) if excluded_features else "None"}',
        ]),
        dcc.Graph(figure=fig, style={'height': 'auto', 'marginTop': '20px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})



def prepare_model_feature_data(df):
    """Prepare uploaded feature/target data for tree-based feature importance."""
    if df.empty:
        raise ValueError('The uploaded CSV is empty.')

    all_columns = df.columns.tolist()
    target_col = all_columns[-1]
    features, excluded_features = information_gain_features(df, target_col)
    if not features:
        raise ValueError(
            'Model feature importance requires at least one feature column containing a zero. '
            'The final column is used as the target.'
        )

    model_df = df[features + [target_col]].copy()
    for column in model_df.columns:
        if model_df[column].dtype == 'object':
            model_df[column], _ = pd.factorize(model_df[column], sort=True)

    feature_df = model_df[features].apply(pd.to_numeric, errors='coerce').fillna(0)
    target = pd.to_numeric(model_df[target_col], errors='coerce')
    if target.isna().any():
        target, _ = pd.factorize(model_df[target_col], sort=True)
        target = pd.Series(target, index=model_df.index)
    else:
        target = target.fillna(0)

    if pd.Series(target).nunique(dropna=True) < 2:
        raise ValueError('The target column must contain at least two classes.')

    return feature_df, target.astype(int), target_col, features, excluded_features, model_df


def render_tree_feature_importance(df, filename, model_kind):
    """Render Random Forest or Decision Tree feature importances."""
    feature_df, target, target_col, features, excluded_features, model_df = prepare_model_feature_data(df)

    if model_kind == 'random_forest':
        model = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1, class_weight='balanced')
        title_prefix = 'Random Forest Feature Importance'
        score_label = 'Random Forest Importance'
    else:
        model = DecisionTreeClassifier(random_state=42, class_weight='balanced')
        title_prefix = 'Decision Tree Feature Importance'
        score_label = 'Decision Tree Importance'

    model.fit(feature_df, target)
    importance_df = pd.DataFrame({
        'Feature': features,
        'Score': model.feature_importances_,
    }).sort_values('Score', ascending=False)

    fig = px.bar(
        importance_df,
        x='Score',
        y='Feature',
        color='Score',
        color_continuous_scale='viridis',
        labels={'Score': score_label, 'Feature': 'Feature'},
        title=f'{title_prefix} for Target ({target_col})',
        height=max(500, len(importance_df) * 50),
    )
    fig.update_traces(
        hovertemplate='<b>%{y}</b><br>Importance: %{x:.5f}<extra></extra>'
    )
    fig.update_layout(
        bargap=0.3,
        bargroupgap=0.1,
        margin=dict(l=120, r=40, t=80, b=80),
        yaxis=dict(automargin=True),
    )

    return html.Div([
        html.H5(f'File: {filename}', style={'marginTop': '20px', 'marginBottom': '15px'}),
        create_preview_table(model_df, [
            f'Target column: {target_col}',
            f'Analyzed zero-containing features: {len(features):,}',
            f'Excluded columns without zeros: {", ".join(excluded_features) if excluded_features else "None"}',
        ]),
        dcc.Graph(figure=fig, style={'height': 'auto', 'marginTop': '20px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})



def _metric_summary(metrics_df):
    """Create compact mean/std rows for repeated train/test metrics."""
    rows = []
    for metric in ['accuracy', 'balanced_accuracy', 'f1_weighted', 'roc_auc']:
        values = pd.to_numeric(metrics_df[metric], errors='coerce').dropna()
        if values.empty:
            continue
        rows.append({
            'Metric': metric.replace('_', ' ').title(),
            'Mean': round(values.mean(), 4),
            'Std': round(values.std(ddof=0), 4),
            'Min': round(values.min(), 4),
            'Max': round(values.max(), 4),
        })
    return pd.DataFrame(rows)


def render_random_forest_train_test(df, filename, n_runs=100, n_estimators=50):
    """Run repeated train/test Random Forest fits and summarize held-out results."""
    feature_df, target, target_col, features, excluded_features, model_df = prepare_model_feature_data(df)
    class_counts = pd.Series(target).value_counts()

    if len(feature_df) < 5:
        raise ValueError('Train/test Random Forest requires at least 5 rows.')

    importances = []
    metric_rows = []
    test_size = 0.2
    n_classes = len(class_counts)
    n_test = max(1, int(math.ceil(len(feature_df) * test_size)))
    n_train = len(feature_df) - n_test
    stratify = target if class_counts.min() >= 2 and n_test >= n_classes and n_train >= n_classes else None

    for run_index in range(n_runs):
        split = train_test_split(
            feature_df,
            target,
            test_size=test_size,
            random_state=42 + run_index,
            stratify=stratify,
        )
        x_train, x_test, y_train, y_test = split
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=42 + run_index,
            n_jobs=-1,
            class_weight='balanced',
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)

        roc_auc = np.nan
        if len(np.unique(y_test)) == 2 and hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(x_test)
            if probabilities.shape[1] == 2:
                roc_auc = roc_auc_score(y_test, probabilities[:, 1])

        metric_rows.append({
            'run': run_index + 1,
            'accuracy': accuracy_score(y_test, predictions),
            'balanced_accuracy': balanced_accuracy_score(y_test, predictions),
            'f1_weighted': f1_score(y_test, predictions, average='weighted', zero_division=0),
            'roc_auc': roc_auc,
        })
        importances.append(model.feature_importances_)

    metrics_df = pd.DataFrame(metric_rows)
    importance_array = np.vstack(importances)
    importance_df = pd.DataFrame({
        'Feature': features,
        'Score': importance_array.mean(axis=0),
        'Std': importance_array.std(axis=0),
    }).sort_values('Score', ascending=False)

    fig = px.bar(
        importance_df,
        x='Score',
        y='Feature',
        color='Score',
        color_continuous_scale='viridis',
        labels={'Score': 'Mean Random Forest Importance', 'Feature': 'Feature'},
        title=f'Random Forest Train/Test Feature Importance over {n_runs} Runs ({target_col})',
        height=max(500, len(importance_df) * 50),
        custom_data=['Std'],
    )
    fig.update_traces(
        error_x={'array': importance_df['Std'], 'visible': True},
        hovertemplate='<b>%{y}</b><br>Mean importance: %{x:.5f}<br>Std: %{customdata[0]:.5f}<extra></extra>',
    )
    fig.update_layout(
        bargap=0.3,
        bargroupgap=0.1,
        margin=dict(l=120, r=40, t=80, b=80),
        yaxis=dict(automargin=True),
    )

    summary_df = _metric_summary(metrics_df)
    return html.Div([
        html.H5(f'File: {filename}', style={'marginTop': '20px', 'marginBottom': '15px'}),
        create_preview_table(model_df, [
            f'Target column: {target_col}',
            f'Train/test runs: {n_runs:,}',
            f'Random Forest trees per run: {n_estimators:,}',
            f'Test split: {test_size:.0%}',
            f'Analyzed zero-containing features: {len(features):,}',
            f'Excluded columns without zeros: {", ".join(excluded_features) if excluded_features else "None"}',
        ]),
        html.H4('Held-Out Performance', style={'color': UCONN_NAVY, 'fontSize': '18px'}),
        dash_table.DataTable(
            data=summary_df.to_dict('records'),
            columns=[{'name': column, 'id': column} for column in summary_df.columns],
            style_table={'overflowX': 'auto', 'marginBottom': '25px'},
            style_cell={'textAlign': 'left', 'padding': '7px'},
            style_header={'backgroundColor': '#9ECEEB', 'fontWeight': 'bold'},
        ),
        dcc.Graph(figure=fig, style={'height': 'auto', 'marginTop': '20px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})


def prepare_manhattan_dataframe(df, kind, cohort, p_col):
    """Use utils.manhattan helpers to turn uploaded pairs into plot points."""
    if p_col not in df.columns:
        raise ValueError(f'Column not found in input: {p_col}')

    pairs = df.copy()
    if 'item_1' not in pairs.columns or 'item_2' not in pairs.columns:
        if 'event_group' not in pairs.columns:
            raise ValueError('Manhattan input must contain item_1/item_2 or event_group.')
        pairs[['item_1', 'item_2']] = pairs['event_group'].apply(
            lambda value: pd.Series(split_event_group(value))
        )

    item_ids = set(pairs['item_1'].dropna().map(clean_item_id))
    item_ids.update(pairs['item_2'].dropna().map(clean_item_id))

    conn = connect_readonly(DEFAULT_DB_PATH)
    try:
        if kind == 'gene':
            locations = load_gene_locations(conn, item_ids)
        else:
            locations = load_sv_locations(conn, item_ids, cohort=cohort)
    finally:
        conn.close()

    points = prepare_plot_points(pairs, locations, p_col)
    if points.empty:
        raise ValueError('No Manhattan plot points were created. Check item IDs and database locations.')

    missing = sorted(item_ids - set(locations['item']))
    return points, len(item_ids), len(locations), missing


def create_interactive_manhattan(points, title, p_threshold):
    """Render Manhattan points as an interactive Plotly graph with hover details."""
    chroms = sorted(points['chrom'].unique(), key=chrom_sort_key)
    centers = points.attrs['chrom_centers']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    fig = go.Figure()

    hover_columns = [
        'event_group', 'plotted_item', 'partner_item', 'chrom', 'start', 'end',
        'p_value', 'neg_log10_p', 'odds_ratio', 'case_hit', 'control_hit',
        'n_known_hit_samples', 'samples',
    ]
    for column in hover_columns:
        if column not in points.columns:
            points[column] = ''

    for index, chrom in enumerate(chroms):
        subset = points[points['chrom'] == chrom]
        fig.add_trace(go.Scattergl(
            x=subset['x'],
            y=subset['neg_log10_p'],
            mode='markers',
            name=chrom.replace('chr', ''),
            customdata=subset[hover_columns].to_numpy(),
            marker={'size': 7, 'opacity': 0.8, 'color': colors[index % len(colors)]},
            hovertemplate=(
                '<b>%{customdata[1]}</b><br>'
                'Pair: %{customdata[0]}<br>'
                'Partner: %{customdata[2]}<br>'
                'Location: %{customdata[3]}:%{customdata[4]}-%{customdata[5]}<br>'
                'p-value: %{customdata[6]:.3e}<br>'
                '-log10(p): %{customdata[7]:.3f}<br>'
                'Odds ratio: %{customdata[8]}<br>'
                'Case hits: %{customdata[9]}<br>'
                'Control hits: %{customdata[10]}<br>'
                'Known-hit samples: %{customdata[11]}<br>'
                'Samples: %{customdata[12]}<extra></extra>'
            ),
        ))

    if p_threshold is not None and p_threshold > 0:
        fig.add_hline(
            y=-math.log10(p_threshold),
            line_dash='dash',
            line_color='#555555',
            annotation_text=f'p = {p_threshold:g}',
            annotation_position='top left',
        )

    fig.update_layout(
        title=title or 'Two-hit Manhattan-like plot',
        height=650,
        margin=dict(l=70, r=30, t=80, b=70),
        showlegend=False,
        hovermode='closest',
        xaxis={
            'title': 'Chromosome',
            'tickmode': 'array',
            'tickvals': [centers[chrom] for chrom in chroms],
            'ticktext': [chrom.replace('chr', '') for chrom in chroms],
            'showgrid': False,
        },
        yaxis={'title': '-log10(p-value)', 'gridcolor': '#E5E7EB'},
        plot_bgcolor='#FFFFFF',
        paper_bgcolor='#FFFFFF',
    )
    return fig


def render_manhattan(df, filename, kind, cohort, p_col, p_threshold, title):
    points, item_count, located_count, missing = prepare_manhattan_dataframe(df, kind, cohort, p_col)
    fig = create_interactive_manhattan(points, title, p_threshold)
    details = [
        f'Input pairs: {len(df):,}',
        f'Unique items in pairs: {item_count:,}',
        f'Items with database locations: {located_count:,}',
        f'Plot points created: {len(points):,}',
    ]
    if missing:
        details.append(f'Items without database locations: {len(missing):,}')

    return html.Div([
        html.H5(f'File: {filename}', style={'marginTop': '20px', 'marginBottom': '15px'}),
        create_preview_table(df, details),
        dcc.Graph(figure=fig, style={'height': '650px', 'marginTop': '20px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})


def _is_chromosome_axis(axis):
    """Return whether an axis name represents chromosome values."""
    return str(axis).strip().lower() in {'chrom', 'chr', 'chromosome'}


def _is_sv_length_axis(axis):
    """Return whether an axis is the database SV-length distribution."""
    return axis == 'sv_length_distribution'


def _format_base_pairs(value):
    """Format a base-pair boundary for a compact bin label."""
    value = int(value)
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f} Mb'
    if value >= 1_000:
        return f'{value / 1_000:.1f} kb'
    return f'{value} bp'


def _build_sv_length_axis(conn, bin_count=10):
    """Build logarithmic SV-length bins from the joined database range."""
    min_length, max_length = conn.execute("""
        SELECT MIN(ps.length), MAX(ps.length)
        FROM phenotype p
        JOIN phenotype_svs ps ON ps.sample = p.bam_id
        WHERE ps.length > 0
    """).fetchone()
    if min_length is None or max_length is None:
        raise ValueError('No positive SV lengths were found.')

    boundaries = sorted(set(
        int(round(value))
        for value in np.geomspace(min_length, max_length + 1, num=bin_count + 1)
    ))
    if boundaries[-1] <= max_length:
        boundaries[-1] = int(max_length) + 1

    clauses = []
    labels = []
    for index, (lower, upper) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
        label = f'{index}. {_format_base_pairs(lower)} - {_format_base_pairs(upper - 1)}'
        labels.append(label)
        clauses.append(f"WHEN ps.length >= {lower} AND ps.length < {upper} THEN '{label}'")
    return f"CASE {' '.join(clauses)} END", labels


def _chromosome_category_sort_key(value):
    """Sort chromosome labels in genomic order, with unknown labels last."""
    chrom = str(value).strip()
    if not chrom.lower().startswith('chr'):
        chrom = f'chr{chrom}'
    suffix = chrom[3:]
    if suffix.lower() in {'x', 'y', 'm', 'mt'}:
        chrom = f'chr{suffix.upper()}'
    return chrom_sort_key(chrom)


def _selected_bar_axes(x_axes, available_axes):
    """Return valid X axes, promoting chromosome to the primary axis."""
    selected = []
    for axis in x_axes or []:
        if axis in available_axes and axis not in selected:
            selected.append(axis)
    if not selected:
        raise ValueError('Select at least one X axis.')

    chromosome_axes = [axis for axis in selected if _is_chromosome_axis(axis)]
    length_axes = [axis for axis in selected if _is_sv_length_axis(axis)]
    other_axes = [
        axis for axis in selected
        if not _is_chromosome_axis(axis) and not _is_sv_length_axis(axis)
    ]
    return chromosome_axes + length_axes + other_axes


def _create_grouped_bar_figure(grouped, x_axes, metrics, axis_labels, metric_labels, y_title):
    """Create grouped bars with genomic or descending-magnitude ordering."""
    primary_axis = x_axes[0]
    secondary_axes = x_axes[1:]
    grouped = grouped.copy()
    for axis in x_axes:
        grouped[axis] = grouped[axis].astype(str)

    if _is_chromosome_axis(primary_axis):
        primary_order = sorted(
            grouped[primary_axis].drop_duplicates().astype(str),
            key=_chromosome_category_sort_key,
        )
    elif _is_sv_length_axis(primary_axis):
        primary_order = sorted(
            grouped[primary_axis].drop_duplicates().astype(str),
            key=lambda value: int(value.split('.', 1)[0]),
        )
    else:
        primary_order = (
            grouped.groupby(primary_axis, dropna=False)[metrics]
            .sum()
            .sum(axis=1)
            .sort_values(ascending=False)
            .index.astype(str)
            .tolist()
        )

    if secondary_axes:
        grouped['series'] = grouped[secondary_axes].apply(
            lambda row: ' / '.join(
                f'{axis_labels[axis]}: {row[axis]}' for axis in secondary_axes
            ),
            axis=1,
        )
    else:
        grouped['series'] = ''

    long_df = grouped.melt(
        id_vars=[*x_axes, 'series'],
        value_vars=metrics,
        var_name='metric',
        value_name='value',
    )
    long_df['metric'] = long_df['metric'].map(metric_labels)
    if len(metrics) > 1:
        long_df['series'] = long_df.apply(
            lambda row: f'{row["series"]} / {row["metric"]}'.strip(' /'),
            axis=1,
        )
    elif not secondary_axes:
        long_df['series'] = long_df['metric']

    series_order = (
        long_df.groupby('series', dropna=False)['value']
        .sum()
        .sort_values(ascending=False)
        .index.astype(str)
        .tolist()
    )
    selected_labels = [axis_labels[axis] for axis in x_axes]
    metric_names = [metric_labels[metric] for metric in metrics]
    fig = px.bar(
        long_df,
        x=primary_axis,
        y='value',
        color='series',
        barmode='group',
        category_orders={primary_axis: primary_order, 'series': series_order},
        labels={primary_axis: axis_labels[primary_axis], 'value': y_title, 'series': 'Breakdown'},
        title=f'{", ".join(metric_names)} by {" and ".join(selected_labels)}',
    )
    fig.update_traces(hovertemplate='<b>%{x}</b><br>%{fullData.name}: %{y:,}<extra></extra>')
    fig.update_layout(
        height=600,
        margin=dict(l=70, r=30, t=80, b=80),
        xaxis={'type': 'category', 'automargin': True},
        yaxis={'title': y_title, 'rangemode': 'tozero', 'gridcolor': '#E5E7EB'},
        legend={'title': 'Breakdown'},
        plot_bgcolor='#FFFFFF',
        paper_bgcolor='#FFFFFF',
    )
    return fig, primary_order


def load_bar_graph_data(x_axes, y_metric):
    """Aggregate a selected metric and groupings from the phenotype/SV join."""
    axes = _selected_bar_axes(x_axes, BAR_X_AXES)
    if y_metric not in BAR_Y_METRICS:
        raise ValueError('Select a Y value.')
    metrics = [y_metric]

    conn = connect_readonly(DEFAULT_DB_PATH)
    try:
        axis_sql = []
        for axis in axes:
            if _is_sv_length_axis(axis):
                expression, _ = _build_sv_length_axis(conn)
                axis_sql.append(expression)
            else:
                axis_sql.append(BAR_X_AXES[axis]['sql'])

        axis_selects = [
            f'CAST({sql} AS TEXT) AS axis_{index}'
            for index, sql in enumerate(axis_sql)
        ]
        count_sql = ', '.join(f'COUNT(DISTINCT {sql})' for sql in axis_sql)
        metric_sql = ', '.join(
            f"{BAR_Y_METRICS[metric]['sql']} AS {metric}"
            for metric in metrics
        )
        where_sql = ' AND '.join(f'{sql} IS NOT NULL' for sql in axis_sql)

        category_counts = conn.execute(f"""
            SELECT {count_sql}
            FROM phenotype p
            JOIN phenotype_svs ps ON ps.sample = p.bam_id
            WHERE {where_sql}
        """).fetchone()
        for axis, category_count in zip(axes, category_counts):
            if category_count > MAX_BAR_CATEGORIES:
                raise ValueError(
                    f'{BAR_X_AXES[axis]["label"]} has {category_count:,} unique values. '
                    f'Bar graphs support at most {MAX_BAR_CATEGORIES} per X axis.'
                )

        rows = conn.execute(f"""
            SELECT {', '.join(axis_selects)}, {metric_sql}
            FROM phenotype p
            JOIN phenotype_svs ps ON ps.sample = p.bam_id
            WHERE {where_sql}
            GROUP BY {', '.join(axis_sql)}
        """).fetchall()
    finally:
        conn.close()

    df = pd.DataFrame([dict(row) for row in rows])
    df = df.rename(columns={f'axis_{index}': axis for index, axis in enumerate(axes)})
    return df, axes, metrics


def render_bar_graph(x_axes, y_metric):
    """Render grouped bars for selected database dimensions and metric."""
    df, axes, metrics = load_bar_graph_data(x_axes, y_metric)
    if df.empty:
        raise ValueError('No joined phenotype and SV data was found.')

    fig, primary_order = _create_grouped_bar_figure(
        df,
        axes,
        metrics,
        {axis: BAR_X_AXES[axis]['label'] for axis in axes},
        {metric: BAR_Y_METRICS[metric]['label'] for metric in metrics},
        'Count',
    )
    labels = [BAR_X_AXES[axis]['label'] for axis in axes]
    order_description = ('in genomic order' if _is_chromosome_axis(axes[0]) else 'in ascending log-length order' if _is_sv_length_axis(axes[0]) else 'ordered by descending magnitude')
    return html.Div([
        html.P(
            f'Data source: phenotype joined to phenotype_svs on bam_id/sample. '
            f'{len(primary_order)} {labels[0].lower()} groups, {order_description}.',
            style={'marginBottom': '15px'},
        ),
        dcc.Graph(figure=fig, style={'height': '600px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})


def inspect_uploaded_bar_columns(df):
    """Find CSV grouping columns and high-cardinality unique-count fields."""
    if df.empty:
        raise ValueError('The uploaded CSV is empty.')

    unique_counts = {
        column: df[column].nunique(dropna=True)
        for column in df.columns
    }
    x_columns = [
        column for column, count in unique_counts.items()
        if 0 < count <= MAX_BAR_CATEGORIES
    ]
    unique_columns = [
        column for column, count in unique_counts.items()
        if count > MAX_BAR_CATEGORIES
    ]
    if not x_columns:
        raise ValueError(
            f'The uploaded CSV has no columns with at most {MAX_BAR_CATEGORIES} unique values.'
        )
    return x_columns, unique_columns


def _column_display_name(column):
    """Format uploaded column names for control labels."""
    return str(column).replace('_', ' ').title().replace('Id', 'ID')


def _uploaded_bar_metric_options(unique_columns):
    """Build row-count and distinct-count Y options for an uploaded CSV."""
    return [
        {'label': 'Item Count', 'value': 'item_count'},
        *[
            {'label': f'Unique {_column_display_name(column)}', 'value': f'unique::{column}'}
            for column in unique_columns
        ],
    ]


def render_uploaded_bar_graph(df, filename, x_axes, y_metric):
    """Count uploaded rows or unique high-cardinality values by selected X axes."""
    x_columns, unique_columns = inspect_uploaded_bar_columns(df)
    axes = _selected_bar_axes(x_axes, x_columns)
    plot_data = df.dropna(subset=axes).copy()
    if plot_data.empty:
        raise ValueError('The selected X axes contain no complete values.')

    if y_metric == 'item_count':
        metric_label = 'Item Count'
        grouped = plot_data.groupby(axes, as_index=False, dropna=True).size()
        grouped = grouped.rename(columns={'size': 'count_value'})
    elif isinstance(y_metric, str) and y_metric.startswith('unique::'):
        unique_column = y_metric.split('::', 1)[1]
        if unique_column not in unique_columns:
            raise ValueError('Select a valid unique-value Y metric.')
        metric_label = f'Unique {_column_display_name(unique_column)}'
        grouped = (
            plot_data.groupby(axes, as_index=False, dropna=True)[unique_column]
            .nunique(dropna=True)
            .rename(columns={unique_column: 'count_value'})
        )
    else:
        raise ValueError('Select a Y value.')

    fig, primary_order = _create_grouped_bar_figure(
        grouped,
        axes,
        ['count_value'],
        {axis: axis for axis in axes},
        {'count_value': metric_label},
        'Count',
    )
    order_description = 'in genomic order' if _is_chromosome_axis(axes[0]) else 'ordered by descending magnitude'
    return html.Div([
        html.P(
            f'File: {filename}. {metric_label} grouped by {" and ".join(axes)}. '
            f'{len(primary_order)} primary groups, {order_description}.',
            style={'marginBottom': '15px'},
        ),
        create_preview_table(df, [
            f'Rows: {len(df):,}',
            f'Grouped combinations: {len(grouped):,}',
        ]),
        dcc.Graph(figure=fig, style={'height': '600px', 'marginBottom': '40px'}),
    ], style={'padding': '10px'})


def validate_sv_statistics_dataframe(df):
    """Require the columns needed to calculate SV count statistics."""
    required = ['sample', 'type', 'length']
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"SV statistics CSV is missing required columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError('The uploaded CSV is empty.')


SV_STATISTIC_COLUMNS = [
    ('Total structural variants', 'total'),
    ('Deletion', 'deletion'),
    ('Duplication', 'duplication'),
    ('Insertion', 'insertion'),
    ('Inversion', 'inversion'),
    ('Breakend', 'breakend'),
    ('Structural variants over 50bp', 'over_50bp'),
]


def _sv_count_statistics(per_person_counts):
    """Summarize each requested SV count across people."""
    rows = []
    for label, column in SV_STATISTIC_COLUMNS:
        counts = pd.to_numeric(per_person_counts[column], errors='coerce').fillna(0)
        rows.append({
            'metric': label,
            'median': round(float(counts.median()), 3),
            'min': int(counts.min()),
            'max': int(counts.max()),
        })
    return pd.DataFrame(rows)


def build_dataframe_statistics(df):
    """Build requested SV counts from an uploaded CSV."""
    validate_sv_statistics_dataframe(df)
    working = df.copy()
    working['sample'] = working['sample'].fillna('').astype(str).str.strip()
    working = working[working['sample'] != '']
    if working.empty:
        raise ValueError('SV statistics CSV must contain at least one non-empty sample value.')

    sv_type = working['type'].fillna('').astype(str).str.upper().str.strip()
    length = pd.to_numeric(working['length'], errors='coerce').abs()
    indicators = pd.DataFrame({
        'sample': working['sample'],
        'total': 1,
        'deletion': (sv_type == 'DEL').astype(int),
        'duplication': (sv_type == 'DUP').astype(int),
        'insertion': (sv_type == 'INS').astype(int),
        'inversion': (sv_type == 'INV').astype(int),
        'breakend': sv_type.isin(['BND', 'BREAKEND']).astype(int),
        'over_50bp': (length > 50).astype(int),
    })
    return _sv_count_statistics(indicators.groupby('sample', as_index=False).sum())


def load_phenotype_svs_statistics():
    """Build requested SV counts directly from phenotype_svs in SQLite."""
    conn = connect_readonly(DEFAULT_DB_PATH)
    try:
        rows = conn.execute("""
            SELECT
                p.bam_id AS sample,
                COUNT(ps.id) AS total,
                COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'DEL' THEN 1 END) AS deletion,
                COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'DUP' THEN 1 END) AS duplication,
                COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'INS' THEN 1 END) AS insertion,
                COUNT(CASE WHEN UPPER(TRIM(ps.type)) = 'INV' THEN 1 END) AS inversion,
                COUNT(CASE WHEN UPPER(TRIM(ps.type)) IN ('BND', 'BREAKEND') THEN 1 END) AS breakend,
                COUNT(CASE WHEN ABS(CAST(ps.length AS REAL)) > 50 THEN 1 END) AS over_50bp
            FROM phenotype AS p
            LEFT JOIN phenotype_svs AS ps ON ps.sample = p.bam_id
            GROUP BY p.bam_id
        """).fetchall()
    finally:
        conn.close()
    return _sv_count_statistics(pd.DataFrame([dict(row) for row in rows]))


def render_statistics_table(statistics, source_label):
    """Render statistics using the same tabular style as the Database page."""
    return html.Div([
        html.P(f'Source: {source_label}', style={'marginBottom': '12px'}),
        dash_table.DataTable(
            data=statistics.to_dict('records'),
            columns=[{'name': column, 'id': column} for column in statistics.columns],
            page_size=20,
            sort_action='native',
            filter_action='native',
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '7px', 'maxWidth': '360px'},
            style_header={'backgroundColor': '#9ECEEB', 'fontWeight': 'bold'},
        ),
    ], style={'padding': '10px'})


def information_gain_format_help():
    markdown = '| age_group | sv_type | affected |\n| --- | --- | --- |\n| child | DEL | 1 |\n| parent | DUP | 0 |'
    return html.Div([
        html.H4('Expected Information Gain CSV Format', style={'color': UCONN_NAVY, 'fontSize': '16px'}),
        html.P('Provide feature columns followed by the target column as the final column. Feature columns without any zero values, such as sample identifiers, are excluded from the analysis.'),
        dcc.Markdown(markdown),
    ], style={'backgroundColor': '#f8f9fa', 'padding': '14px', 'borderRadius': '6px'})


def sv_statistics_format_help():
    markdown = """| sample | type | length |
| --- | --- | ---: |
| KFG136 | DEL | 1049 |
| KFG136 | BND | 25 |"""
    return html.Div([
        html.H4('Expected SV Statistics CSV Format', style={'color': UCONN_NAVY, 'fontSize': '16px'}),
        html.P('Sample, type, and length are required. Additional phenotype_svs columns are allowed.'),
        html.Code('sample, type, length', style={'whiteSpace': 'normal'}),
        dcc.Markdown(markdown),
    ], style={'backgroundColor': '#f8f9fa', 'padding': '14px', 'borderRadius': '6px'})


def processing_error(message):
    return html.Div([
        html.H5('Error generating visualization.', style={'color': '#A61B1B'}),
        html.P(str(message)),
    ], style={'padding': '15px'})


def page_layout():
    """Create the visualization uploader page layout."""
    control_style = {'marginBottom': '18px'}
    return html.Div([
        html.H2('OFC Visualization Uploader', style={'color': UCONN_NAVY, 'marginBottom': '20px'}),
        html.Div([
            html.H3('Visualization', style={'color': UCONN_NAVY, 'fontSize': '18px', 'marginBottom': '8px'}),
            dcc.Dropdown(
                id='visualization-upload-mode',
                options=[
                    {'label': 'Information Gain', 'value': 'information_gain'},
                    {'label': 'Random Forest', 'value': 'random_forest'},
                    {'label': 'Decision Tree', 'value': 'decision_tree'},
                    {'label': 'Random Forest Train/Test', 'value': 'random_forest_train_test'},
                    {'label': 'Manhattan Plot', 'value': 'manhattan'},
                    {'label': 'Bar Graph', 'value': 'bar_graph'},
                    {'label': 'SV Statistics', 'value': 'sv_statistics'},
                ],
                value='information_gain',
                clearable=False,
                style={'maxWidth': '420px'},
            ),
        ], style=control_style),
        html.Div(id='visualization-mode-help', style={'marginBottom': '12px'}),
        html.Div([
            dcc.Upload(
                id='bar-upload-csv',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select CSV File', style={'fontWeight': 'bold', 'color': UCONN_NAVY}),
                ]),
                style={
                    'width': '100%', 'height': '70px', 'lineHeight': '70px', 'borderWidth': '2px',
                    'borderStyle': 'dashed', 'borderRadius': '8px', 'textAlign': 'center',
                    'margin': '0 0 22px 0', 'backgroundColor': '#fafafa', 'cursor': 'pointer',
                },
                multiple=False,
            ),
        ], id='bar-upload-data', style={'display': 'none'}),
        html.Div([
            sv_statistics_format_help(),
            dcc.Upload(
                id='sv-statistics-upload-csv',
                children=html.Div(['Drag and Drop or ', html.A('Select phenotype_svs CSV', style={'fontWeight': 'bold', 'color': UCONN_NAVY})]),
                style={
                    'width': '100%', 'height': '70px', 'lineHeight': '70px', 'borderWidth': '2px',
                    'borderStyle': 'dashed', 'borderRadius': '8px', 'textAlign': 'center',
                    'margin': '18px 0', 'backgroundColor': '#fafafa', 'cursor': 'pointer',
                },
                multiple=False,
            ),
            html.Button('Download Statistics CSV', id='sv-statistics-download-button', n_clicks=0,
                        style={'backgroundColor': UCONN_NAVY, 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'padding': '8px 15px'}),
            dcc.Download(id='sv-statistics-download'),
        ], id='sv-statistics-controls', style={'display': 'none'}),
        html.Div([
            html.Div([
                html.Label('Item Type', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Dropdown(
                    id='manhattan-kind',
                    options=[
                        {'label': 'Gene Pairs', 'value': 'gene'},
                        {'label': 'SV Pairs', 'value': 'sv'},
                    ],
                    value='gene',
                    clearable=False,
                ),
            ]),
            html.Div([
                html.Label('SV Cohort', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Dropdown(
                    id='manhattan-cohort',
                    options=[
                        {'label': 'Combined', 'value': 'combined'},
                        {'label': 'Kids First', 'value': 'kidsfirst'},
                        {'label': 'Background', 'value': 'background'},
                    ],
                    value='combined',
                    clearable=False,
                    disabled=True,
                ),
            ]),
            html.Div([
                html.Label('P-value Column', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Input(id='manhattan-p-column', value='p_value', type='text', style={'width': '100%', 'height': '38px'}),
            ]),
            html.Div([
                html.Label('P-value Threshold', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Input(id='manhattan-p-threshold', value=0.05, type='number', min=0, step='any', style={'width': '100%', 'height': '38px'}),
            ]),
            html.Div([
                html.Label('Plot Title', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Input(id='manhattan-title', value='Two-hit Manhattan-like plot', type='text', style={'width': '100%', 'height': '38px'}),
            ], style={'gridColumn': 'span 2'}),
        ], id='manhattan-settings', style={'display': 'none'}),
        html.Div([
            html.Div([
                html.Label('X Axes', style={'fontWeight': '600', 'marginBottom': '8px'}),
                dcc.Checklist(
                    id='bar-x-axis',
                    options=[
                        {'label': config['label'], 'value': value}
                        for value, config in BAR_X_AXES.items()
                    ],
                    value=['chrom'],
                    inline=True,
                    inputStyle={'marginRight': '6px'},
                    labelStyle={
                        'display': 'inline-block', 'border': '1px solid #B7C2CE',
                        'borderRadius': '6px', 'padding': '8px 12px',
                        'margin': '0 8px 8px 0', 'cursor': 'pointer',
                    },
                ),
            ], style={'marginBottom': '14px'}),
            html.Div([
                html.Label('Y Value', style={'fontWeight': '600', 'marginBottom': '8px'}),
                dcc.RadioItems(
                    id='bar-y-values',
                    options=[
                        {'label': config['label'], 'value': value}
                        for value, config in BAR_Y_METRICS.items()
                    ],
                    value='unique_svs',
                    inline=True,
                    inputStyle={'marginRight': '6px'},
                    labelStyle={'margin': '0 18px 8px 0', 'cursor': 'pointer'},
                ),
            ]),
        ], id='bar-graph-settings', style={'display': 'none'}),
        html.Div([
            html.Div([
                html.Label('Preexisting Data', style={'fontWeight': '600', 'marginBottom': '6px'}),
                dcc.Dropdown(
                    id='visualization-preset-data',
                    options=[
                        {'label': '2pair_gene.parquet', 'value': 'gene_pairs'},
                        {'label': '2pair_sv.parquet', 'value': 'sv_pairs'},
                    ],
                    placeholder='Select server-side data',
                    clearable=True,
                    style={'maxWidth': '420px'},
                ),
            ], id='visualization-preset-container', style={'marginBottom': '20px'}),
            dcc.Upload(
                id='upload-csv',
                children=html.Div(['Drag and Drop or ', html.A('Select CSV File', style={'fontWeight': 'bold', 'color': UCONN_NAVY})]),
                style={
                    'width': '100%', 'height': '70px', 'lineHeight': '70px', 'borderWidth': '2px',
                    'borderStyle': 'dashed', 'borderRadius': '8px', 'textAlign': 'center',
                    'margin': '20px 0 30px 0', 'backgroundColor': '#fafafa', 'cursor': 'pointer',
                },
                multiple=False,
            ),
        ], id='visualization-input-data'),
        dcc.Loading(
            children=html.Div(id='output-visualization', style={'marginTop': '20px'}),
            type='default',
        ),
    ], style={'padding': '25px', 'maxWidth': '1200px', 'margin': '0 auto'})


@callback(
    Output('visualization-mode-help', 'children'),
    Output('manhattan-settings', 'style'),
    Output('bar-graph-settings', 'style'),
    Output('visualization-input-data', 'style'),
    Output('bar-upload-data', 'style'),
    Output('visualization-preset-container', 'style'),
    Output('sv-statistics-controls', 'style'),
    Input('visualization-upload-mode', 'value'),
)
def update_visualization_mode(mode):
    hidden = {'display': 'none'}
    if mode == 'manhattan':
        return '', {
            'display': 'grid',
            'gridTemplateColumns': 'repeat(2, minmax(0, 1fr))',
            'gap': '16px',
            'marginBottom': '24px',
            'maxWidth': '760px',
        }, hidden, {'display': 'block'}, hidden, {'marginBottom': '20px'}, hidden
    if mode == 'bar_graph':
        return html.P(
            'Select one or more X axes. The first is the group axis and additional axes create grouped bars. Upload an optional CSV below. Columns with at most 25 unique values '
            'become X-axis options. Y can count all rows or unique values from high-cardinality columns. '
            'Without a CSV, the joined phenotype data is used.',
            style={'marginBottom': '0'},
        ), hidden, {'display': 'block', 'marginBottom': '24px'}, hidden, {'display': 'block'}, hidden, hidden
    if mode == 'sv_statistics':
        return html.P('Statistics default to the phenotype_svs database table. Upload a CSV below to profile it instead.'), hidden, hidden, hidden, hidden, hidden, {'display': 'block', 'marginBottom': '20px'}
    return information_gain_format_help(), hidden, hidden, {'display': 'block'}, hidden, hidden, hidden


@callback(
    Output('bar-x-axis', 'options'),
    Output('bar-x-axis', 'value'),
    Output('bar-y-values', 'options'),
    Output('bar-y-values', 'value'),
    Input('bar-upload-csv', 'contents'),
    Input('visualization-upload-mode', 'value'),
    State('bar-upload-csv', 'filename'),
)
def update_bar_axis_options(contents, mode, filename):
    """Switch bar axis choices between database defaults and uploaded columns."""
    if mode != 'bar_graph' or contents is None:
        return (
            [{'label': config['label'], 'value': value} for value, config in BAR_X_AXES.items()],
            ['chrom'],
            [{'label': config['label'], 'value': value} for value, config in BAR_Y_METRICS.items()],
            'unique_svs',
        )

    try:
        df = parse_uploaded_csv(contents, filename)
        x_columns, unique_columns = inspect_uploaded_bar_columns(df)
        return (
            [{'label': column, 'value': column} for column in x_columns],
            [x_columns[0]],
            _uploaded_bar_metric_options(unique_columns),
            'item_count',
        )
    except Exception:
        return [], [], [], None


@callback(
    Output('manhattan-cohort', 'disabled'),
    Input('manhattan-kind', 'value'),
)
def update_cohort_disabled(kind):
    return kind != 'sv'


@callback(
    Output('visualization-upload-mode', 'value'),
    Output('manhattan-kind', 'value'),
    Input('visualization-preset-data', 'value'),
    prevent_initial_call=True,
)
def select_preset_mode(preset):
    if preset is None:
        return no_update, no_update
    return 'manhattan', PRESET_DATASETS[preset]['kind']


@callback(
    Output('output-visualization', 'children'),
    Input('upload-csv', 'contents'),
    Input('bar-upload-csv', 'contents'),
    Input('sv-statistics-upload-csv', 'contents'),
    Input('visualization-preset-data', 'value'),
    Input('visualization-upload-mode', 'value'),
    Input('manhattan-kind', 'value'),
    Input('manhattan-cohort', 'value'),
    Input('manhattan-p-column', 'value'),
    Input('manhattan-p-threshold', 'value'),
    Input('manhattan-title', 'value'),
    Input('bar-x-axis', 'value'),
    Input('bar-y-values', 'value'),
    State('upload-csv', 'filename'),
    State('bar-upload-csv', 'filename'),
    State('sv-statistics-upload-csv', 'filename'),
)
def update_output(
    contents, bar_contents, statistics_contents, preset, mode, kind, cohort, p_col, p_threshold, title,
    bar_x_axis, bar_y_values, filename, bar_filename, statistics_filename,
):
    """Update the visualization based on uploaded file and selected mode."""
    if mode == 'sv_statistics':
        try:
            if statistics_contents is not None:
                dataframe = parse_uploaded_csv(statistics_contents, statistics_filename)
                statistics = build_dataframe_statistics(dataframe)
                return render_statistics_table(statistics, statistics_filename)
            return render_statistics_table(load_phenotype_svs_statistics(), 'phenotype_svs database table')
        except Exception as exc:
            print(exc)
            return processing_error(exc)

    if mode == 'bar_graph':
        try:
            if bar_contents is not None:
                df = parse_uploaded_csv(bar_contents, bar_filename)
                return render_uploaded_bar_graph(df, bar_filename, bar_x_axis, bar_y_values)
            return render_bar_graph(bar_x_axis, bar_y_values)
        except Exception as exc:
            print(exc)
            return processing_error(exc)

    if contents is None and (mode != 'manhattan' or preset is None):
        return html.Div()

    try:
        threshold = float(p_threshold) if p_threshold not in (None, '') else None
        if mode == 'manhattan' and preset is not None:
            points, dataset = load_preset_points(preset)
            fig = create_interactive_manhattan(points, title, threshold)
            return html.Div([
                html.H5(f"File: {dataset['filename']}", style={'marginTop': '20px', 'marginBottom': '15px'}),
                html.P(f'Precomputed plot points: {len(points):,}', style={'marginBottom': '15px'}),
                dcc.Graph(figure=fig, style={'height': '650px', 'marginTop': '20px', 'marginBottom': '40px'}),
            ], style={'padding': '10px'})

        df = parse_uploaded_csv(contents, filename)
        if mode == 'manhattan':
            return render_manhattan(df, filename, kind, cohort, p_col or 'p_value', threshold, title)
        if mode == 'random_forest_train_test':
            return render_random_forest_train_test(df, filename)
        if mode in {'random_forest', 'decision_tree'}:
            return render_tree_feature_importance(df, filename, mode)
        return render_information_gain(df, filename)
    except Exception as exc:
        print(exc)
        return processing_error(exc)


@callback(
    Output('sv-statistics-download', 'data'),
    Input('sv-statistics-download-button', 'n_clicks'),
    State('sv-statistics-upload-csv', 'contents'),
    State('sv-statistics-upload-csv', 'filename'),
    prevent_initial_call=True,
)
def download_sv_statistics(n_clicks, contents, filename):
    if not n_clicks:
        return no_update
    try:
        if contents is not None:
            statistics = build_dataframe_statistics(parse_uploaded_csv(contents, filename))
        else:
            statistics = load_phenotype_svs_statistics()
    except Exception:
        return no_update
    return dcc.send_data_frame(statistics.to_csv, 'sv_statistics.csv', index=False)

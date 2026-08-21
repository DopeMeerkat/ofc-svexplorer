"""
Table page for the UCONN OFC SV Browser application.
"""

from dash import ALL, ctx, html, dash_table, Input, Output, State, callback, no_update, dcc
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, page_title_style, uconn_styles

from utils import case_studies
from utils.curated_table import CURATED_TABLE_PATH, curated_table_footnote_lines
from utils.database import load_table_data
import re
from urllib.parse import quote

TABLE_CSV_PATH = CURATED_TABLE_PATH

CLICKABLE_COLUMNS = {
    'gene': 'gene',
    'fusorsvid': 'sv',
    'fusorsvids': 'sv',
}

PRIMARY_COLUMN_ORDER = [
    'gene',
    'interactionpartners',
    'fusorsvid',
    'fusorsvids',
]


def _normalize_column_name(column_name):
    return re.sub(r'[^a-z0-9]', '', str(column_name).lower())


def _ordered_columns(df):
    columns = list(df.columns)
    primary = []
    for target in PRIMARY_COLUMN_ORDER:
        primary.extend(
            column for column in columns
            if _normalize_column_name(column) == target and column not in primary
        )
    return primary + [column for column in columns if column not in primary]


def _split_cell_values(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return []
    values = [part.strip() for part in text.split(',')]
    return [value for value in values if value]


def _strip_case_study_marker(value):
    return str(value or '').strip().removesuffix('*').strip()


def _case_gene_key(value):
    text = _strip_case_study_marker(value)
    if not text:
        return ''
    # Summary labels and some source tables may include aliases like KDM8 (JMJD5).
    return text.split('(', 1)[0].strip().split()[0].upper()


def _case_study_gene_map():
    """Return {GENE_SYMBOL: case_id} for available case-study JSON entries."""
    gene_map = {}
    for study in case_studies.list_case_studies():
        case_id = study.get('id')
        if not case_id:
            continue
        data = case_studies.load_case_study(case_id) or {}
        title_gene = _case_gene_key(data.get('title') or case_id)
        id_gene = _case_gene_key(case_id)
        for gene in {title_gene, id_gene}:
            if gene:
                gene_map[gene] = case_id
    return gene_map


def _case_id_for_gene(value):
    return _case_study_gene_map().get(_case_gene_key(value))


def _mark_case_study_genes(df):
    """Add an asterisk to displayed Gene values that have case studies."""
    gene_map = _case_study_gene_map()
    if not gene_map:
        return df
    df = df.copy()
    for column in df.columns:
        if _normalize_column_name(column) != 'gene':
            continue
        df[column] = df[column].apply(
            lambda value: f"{_strip_case_study_marker(value)}*"
            if _case_gene_key(value) in gene_map else value
        )
    return df


def _modal_style(display='flex'):
    if display == 'none':
        return {'display': 'none'}
    return {
        'position': 'fixed',
        'top': '0',
        'left': '0',
        'width': '100%',
        'height': '100%',
        'backgroundColor': 'rgba(2, 37, 75, 0.42)',
        'display': display,
        'alignItems': 'center',
        'justifyContent': 'center',
        'zIndex': '999',
        'backdropFilter': 'blur(2px)',
    }


def _button_style(background=UCONN_NAVY, color='white'):
    return {
        'background': background,
        'color': color,
        'border': f'1px solid {background}',
        'padding': '11px 14px',
        'borderRadius': '6px',
        'marginBottom': '10px',
        'cursor': 'pointer',
        'width': '100%',
        'textAlign': 'left',
        'fontWeight': '700',
        'boxShadow': '0 2px 8px rgba(2, 37, 75, 0.10)',
    }


def _table_columns(columns):
    return [{"name": column, "id": column} for column in columns]


def _build_action_options(selected_item):
    item_type = selected_item.get('type')
    value = selected_item.get('selected')
    label = 'SV' if item_type == 'sv' else 'Gene'
    pathway_gene = selected_item.get('pathway_gene') or value
    buttons = [
        html.Button('Open in IGV', id='open-table-item-igv-button', n_clicks=0, style=_button_style()),
        html.Button(
            f'Open pathway view ({pathway_gene})',
            id='open-table-item-pathway-button',
            n_clicks=0,
            style=_button_style(UCONN_LIGHT_BLUE, UCONN_NAVY),
        ),
        html.Button(
            'Open Case Study',
            id='open-table-item-case-study-button',
            n_clicks=0,
            style={**_button_style('#F8FAFC', UCONN_NAVY), 'display': 'none' if not selected_item.get('case_study_id') else 'block'},
        ),
    ]

    return html.Div([
        html.P(f'Selected {label}: {value}', style={'fontWeight': '700', 'fontSize': '16px', 'marginBottom': '8px', 'color': UCONN_NAVY}),
        html.P('Choose an action:', style={'marginBottom': '12px', 'color': '#4B5563'}),
        *buttons,
    ])


def page_layout(search=None):
    """
    Create the table page layout
    
    Returns:
        dash.html.Div: Table page layout
    """
    csv_path = TABLE_CSV_PATH
    title = 'Table Inspection'
    description = 'Curated 41-gene overlap table with direct links to IGV, pathway context, and available case studies.'

    df = load_table_data(csv_path)
    if df.empty:
        return html.Div(f'No data found in {csv_path}', style={'padding': '30px', 'color': 'red'})
    ordered_columns = _ordered_columns(df)
    df = df[ordered_columns]
    df = _mark_case_study_genes(df)

    return html.Div([
        html.H2(title, style=page_title_style),
        html.P(description,
               style={'marginBottom': '15px', 'color': UCONN_NAVY, 'fontStyle': 'italic'}),
        html.Div([
            html.Span(f'{len(df)} genes', style={
                'display': 'inline-block',
                'backgroundColor': '#EAF4FB',
                'border': f'1px solid {UCONN_LIGHT_BLUE}',
                'borderRadius': '999px',
                'padding': '5px 12px',
                'fontWeight': '700',
                'fontSize': '13px',
                'color': UCONN_NAVY,
                'marginRight': '8px',
            }),
            html.Span('Selectable gene and SV fields open navigation options.',
                      style={'fontSize': '13px', 'color': '#4B5563'}),
        ], style={'marginBottom': '12px'}),
        html.P('Genes with curated case studies are marked with an asterisk.', style={'fontSize': '13px', 'color': '#4B5563', 'margin': '0 0 10px 0'}),
        dash_table.DataTable(
            id='gene-table',
            data=df.to_dict('records'),
            columns=_table_columns(ordered_columns),
            page_action='none',
            sort_action='native',
            filter_action='native',
            fixed_rows={'headers': True},
            style_table={
                'overflowX': 'auto',
                'overflowY': 'auto',
                'maxHeight': '72vh',
                'border': f'1px solid {UCONN_LIGHT_BLUE}',
                'borderRadius': '8px',
                'boxShadow': '0 8px 24px rgba(2, 37, 75, 0.08)',
            },
            style_cell={
                'textAlign': 'left',
                'padding': '10px 12px',
                'fontFamily': '"Open Sans", sans-serif',
                'fontSize': '13px',
                'lineHeight': '1.35',
                'whiteSpace': 'normal',
                'height': 'auto',
                'minWidth': '110px',
                'maxWidth': '280px',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis',
            },
            style_header={
                'backgroundColor': UCONN_NAVY,
                'color': 'white',
                'fontWeight': '700',
                'border': f'1px solid {UCONN_NAVY}',
                'padding': '12px',
            },
            style_filter={
                'backgroundColor': '#F7FAFC',
                'border': f'1px solid {UCONN_LIGHT_BLUE}',
                'fontSize': '12px',
            },
            style_data={
                'backgroundColor': 'white',
                'border': '1px solid #E5E7EB',
                'color': '#1F2937',
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'Gene'},
                    'fontWeight': 'bold',
                    'color': UCONN_NAVY,
                    'backgroundColor': '#F8FBFD',
                    'cursor': 'pointer',
                    'minWidth': '110px',
                    'maxWidth': '150px',
                },
                {
                    'if': {'column_id': 'FusorSV_id(s)'},
                    'color': '#005EA8',
                    'backgroundColor': '#FBFDFF',
                    'cursor': 'pointer',
                    'fontWeight': '600',
                    'minWidth': '180px',
                    'maxWidth': '240px',
                },
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': '#FAFCFE',
                },
                {
                    'if': {'state': 'active'},
                    'backgroundColor': '#D9ECF8',
                    'border': f'2px solid {UCONN_NAVY}',
                }
            ],
            selected_rows=[],
        ),
        html.Div([
            html.P(line, style={'margin': '2px 0'})
            for line in curated_table_footnote_lines()
        ], style={'fontSize': '12px', 'color': '#4B5563', 'lineHeight': '1.45', 'marginTop': '10px'}),
        dcc.Store(id='table-selected-item-store', data=None),
        
        # Custom modal-like container using divs
        html.Div(
            id='gene-options-container',
            children=[
                html.Div(
                    id='gene-options-content',
                    children=[
                        html.Div([
                            html.H3('Selection Options', style={'color': UCONN_NAVY, 'marginBottom': '8px'}),
                            html.Div(id='gene-options-details'),
                            html.Div([
                                html.Button('Close', id='close-options-button',
                                          style={'background': '#F8FAFC', 'color': UCONN_NAVY, 'border': f'1px solid {UCONN_LIGHT_BLUE}', 'borderRadius': '6px', 'padding': '8px 16px', 'fontWeight': '700', 'cursor': 'pointer'})
                            ], style={'marginTop': '20px', 'textAlign': 'right'})
                        ], style={'padding': '20px'})
                    ],
                    style={
                        'backgroundColor': 'white',
                        'borderRadius': '8px',
                        'boxShadow': '0 18px 50px rgba(2, 37, 75, 0.22)',
                        'border': f'1px solid {UCONN_LIGHT_BLUE}',
                        'maxWidth': '520px',
                        'margin': '0 auto',
                        'position': 'relative',
                        'zIndex': '1000'
                    }
                )
            ],
            style={
                'position': 'fixed',
                'top': '0',
                'left': '0',
                'width': '100%',
                'height': '100%',
                'backgroundColor': 'rgba(2, 37, 75, 0.42)',
                'alignItems': 'center',
                'justifyContent': 'center',
                'zIndex': '999',
                'display': 'none'
            }
        ),
    ], style=uconn_styles['content'])

@callback(
    Output('gene-options-container', 'style'),
    Output('gene-options-details', 'children'),
    Output('table-selected-item-store', 'data'),
    Input('gene-table', 'active_cell'),
    State('gene-table', 'data'),
    State('gene-table', 'derived_viewport_data'),
    prevent_initial_call=True
)
def show_gene_options(active_cell, table_data, viewport_data):
    """Handle table cell selection and show navigation choices."""
    if not active_cell or not table_data:
        return _modal_style('none'), no_update, None

    column_id = active_cell.get('column_id')
    item_type = CLICKABLE_COLUMNS.get(_normalize_column_name(column_id))
    if not item_type:
        return _modal_style('none'), no_update, None

    row = active_cell.get('row')
    visible_rows = viewport_data or table_data
    if row is None or row >= len(visible_rows):
        return _modal_style('none'), no_update, None
    gene_row = visible_rows[row]
    values = _split_cell_values(gene_row.get(column_id, ''))
    if not values:
        return _modal_style('none'), no_update, None

    values = [_strip_case_study_marker(value) for value in values]
    pathway_gene = _strip_case_study_marker(gene_row.get('Gene', '')) if item_type == 'sv' else None
    selected = values[0] if len(values) == 1 else None
    selection_data = {
        'type': item_type,
        'items': values,
        'selected': selected,
        'pathway_gene': pathway_gene,
        'case_study_id': _case_id_for_gene(selected) if item_type == 'gene' and selected else None,
    }

    if len(values) == 1:
        return _modal_style(), _build_action_options(selection_data), selection_data

    label = 'SV' if item_type == 'sv' else 'gene/partner'
    options_content = html.Div([
        html.P(f'Select a {label}:', style={'fontWeight': 'bold', 'fontSize': '16px', 'marginBottom': '15px'}),
        html.Div([
            html.Button(
                value,
                id={'type': 'table-item-choice-button', 'index': index},
                n_clicks=0,
                style=_button_style(UCONN_LIGHT_BLUE, UCONN_NAVY),
            ) for index, value in enumerate(values)
        ]),
    ])
    return _modal_style(), options_content, selection_data


@callback(
    Output('gene-options-details', 'children', allow_duplicate=True),
    Output('table-selected-item-store', 'data', allow_duplicate=True),
    Input({'type': 'table-item-choice-button', 'index': ALL}, 'n_clicks'),
    State('table-selected-item-store', 'data'),
    prevent_initial_call=True,
)
def select_table_item(choice_clicks, selection_data):
    if not selection_data or not any(choice_clicks or []):
        return no_update, no_update
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        return no_update, no_update
    index = triggered.get('index')
    values = selection_data.get('items') or []
    if index is None or index >= len(values):
        return no_update, no_update
    selection_data = {**selection_data, 'selected': values[index]}
    if selection_data.get('type') == 'gene':
        selection_data['case_study_id'] = _case_id_for_gene(values[index])
    return _build_action_options(selection_data), selection_data

# Callback to close the options container
@callback(
    Output('gene-options-container', 'style', allow_duplicate=True),
    Input('close-options-button', 'n_clicks'),
    prevent_initial_call=True
)
def close_options(n_clicks):
    """Close the options container when close button is clicked"""
    return _modal_style('none')

@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('url', 'search', allow_duplicate=True),
    Output('gene-options-container', 'style', allow_duplicate=True),
    Input('open-table-item-igv-button', 'n_clicks'),
    Input('open-table-item-pathway-button', 'n_clicks'),
    Input('open-table-item-case-study-button', 'n_clicks'),
    State('table-selected-item-store', 'data'),
    prevent_initial_call=True
)
def navigate_from_table_item(igv_clicks, pathway_clicks, case_study_clicks, selection_data):
    """Navigate to IGV or Pathway for the selected table item."""
    if not selection_data or not selection_data.get('selected'):
        return no_update, no_update, no_update

    selected = selection_data['selected']
    if ctx.triggered_id == 'open-table-item-igv-button' and igv_clicks:
        query_key = 'sv' if selection_data.get('type') == 'sv' else 'gene'
        return '/population', f'?{query_key}={quote(selected)}', _modal_style('none')

    if ctx.triggered_id == 'open-table-item-pathway-button' and pathway_clicks:
        pathway_gene = selection_data.get('pathway_gene') or selected
        return '/pathway', f'?gene={quote(pathway_gene)}', _modal_style('none')

    if ctx.triggered_id == 'open-table-item-case-study-button' and case_study_clicks:
        case_id = selection_data.get('case_study_id')
        if case_id:
            return '/case-study', f'?case={quote(case_id)}&tab=case-studies', _modal_style('none')

    return no_update, no_update, no_update

"""
Gene search component for the UCONN OFC SV Browser application.
"""

from dash import html, dcc, Input, Output, State, callback, no_update
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles
from utils.database import search_genes

def create_gene_search():
    """
    Create a gene search component with input, button and results area
    
    Returns:
        dash.html.Div: Gene search component
    """
    return html.Div([
        html.H3('Search Genes', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
        html.P('Enter a gene name to search and navigate directly to that location:', style={'marginBottom': '10px'}),
        html.Div([
            dcc.Input(
                id='gene-search-input',
                type='text',
                placeholder='Enter gene name...',
                style={
                    'width': '70%', 
                    'padding': '8px',
                    'borderRadius': '4px',
                    'border': f'1px solid {UCONN_LIGHT_BLUE}',
                    'marginRight': '10px'
                }
            ),
            html.Button(
                'Search', 
                id='gene-search-button', 
                n_clicks=0,
                style={
                    'backgroundColor': UCONN_NAVY,
                    'color': '#FFFFFF',
                    'border': 'none',
                    'padding': '8px 15px',
                    'borderRadius': '4px',
                    'cursor': 'pointer'
                }
            )
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'}),
        html.Div(id='gene-search-results', children=[]),
    ], style={'marginBottom': '30px'})

# Callback for gene search functionality
@callback(
    Output('gene-search-results', 'children'),
    Input('gene-search-button', 'n_clicks'),
    State('gene-search-input', 'value'),
    prevent_initial_call=True
)
def update_search_results(n_clicks, search_term):
    """
    Update search results based on input
    """
    if not search_term:
        return html.Div("Enter a gene name to search", style={'color': 'gray', 'fontSize': '14px'})
    
    # Search for genes matching the search term
    genes = search_genes(search_term)
    
    if not genes:
        return html.Div(f"No genes found matching '{search_term}'", style={'color': 'red', 'fontSize': '14px'})
    
    # Create a dropdown with search results
    options = [{'label': gene['label'], 'value': str(i)} for i, gene in enumerate(genes)]
    
    return html.Div([
        html.P(f"Found {len(genes)} genes matching '{search_term}':", 
              style={'marginBottom': '5px', 'fontSize': '14px', 'color': UCONN_NAVY}),
        dcc.Dropdown(
            id='gene-search-dropdown',
            options=options,
            placeholder='Select a gene...',
            style={**uconn_styles['dropdown'], 'marginBottom': '10px'}
        ),
        # Store the full gene data for later use
        dcc.Store(id='gene-search-data', data=genes)
    ])

# Callback to handle gene selection from search results
@callback(
    Output('selected-gene', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('gene-search-dropdown', 'value'),
    State('gene-search-data', 'data'),
    prevent_initial_call=True
)
def handle_search_selection(selected_index, genes_data):
    """
    Handle selection of a gene from search results
    """
    if selected_index is None or not genes_data:
        return no_update, no_update
    
    # Get the selected gene by index
    selected_gene = genes_data[int(selected_index)]
    print("\n======= GENE SEARCH SELECTION DEBUG =======")
    print(f"Selected gene: {selected_gene}")
    
    # Create the required gene dictionary format
    gene_dict = {
        'id': selected_gene['id'],
        'Gene': selected_gene['id'],  # Add 'Gene' field for compatibility with table selection
        'chrom': selected_gene['chrom'],
        'x1': selected_gene['x1'],
        'x2': selected_gene['x2'],
        'length': selected_gene['length'],
        'strand': selected_gene['strand']
    }
    
    # Return gene data and redirect to genome browser
    return gene_dict, '/'

# Callback to handle Enter key in search input
@callback(
    Output('gene-search-button', 'n_clicks', allow_duplicate=True),
    Input('gene-search-input', 'n_submit'),
    prevent_initial_call=True
)
def search_on_enter(n_submit):
    """
    Trigger search when Enter key is pressed
    """
    if n_submit:
        return 1  # Simulate button click
    return no_update

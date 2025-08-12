"""
Custom gene search component for the Family Genomes page.
This is a modified version that doesn't redirect to the genome browser.
"""

from dash import html, dcc, Input, Output, State, callback, no_update
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles
from utils.database import search_genes

def create_family_gene_search():
    """
    Create a gene search component for the Family Genomes page
    
    Returns:
        dash.html.Div: Gene search component
    """
    return html.Div([
        html.H3('Search Genes', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
        html.P('Enter a gene name to search and navigate directly to that location:', style={'marginBottom': '10px'}),
        html.Div([
            dcc.Input(
                id='family-gene-search-input',
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
                id='family-gene-search-button', 
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
        html.Div(id='family-gene-search-results', children=[]),
    ], style={'marginBottom': '30px'})

# Callback for gene search functionality
@callback(
    Output('family-gene-search-results', 'children'),
    Input('family-gene-search-button', 'n_clicks'),
    State('family-gene-search-input', 'value'),
    prevent_initial_call=True
)
def update_family_search_results(n_clicks, search_term):
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
    
    print(f"\n=== GENE SEARCH RESULTS ===")
    print(f"Found {len(genes)} genes matching '{search_term}'")
    print(f"First gene: {genes[0] if genes else 'None'}")
    
    # Always set the first option as the default value if we have results
    default_value = '0' if options else None
    print(f"Setting default value to: {default_value}")
    
    return html.Div([
        html.P(f"Found {len(genes)} genes matching '{search_term}':", 
              style={'marginBottom': '5px', 'fontSize': '14px', 'color': UCONN_NAVY}),
        dcc.Dropdown(
            id='family-gene-search-dropdown',
            options=options,
            value=default_value,  # Set first gene as default
            placeholder='Select a gene...',
            style={**uconn_styles['dropdown'], 'marginBottom': '10px'},
            clearable=False  # Prevent clearing the selection
        ),
        # Store the full gene data for later use
        dcc.Store(id='family-gene-search-data', data=genes)
    ])

# Callback to handle gene selection from search results
@callback(
    Output('selected-gene-store', 'data'),
    Input('family-gene-search-dropdown', 'value'),
    State('family-gene-search-data', 'data'),
    prevent_initial_call=True
)
def handle_family_search_selection(selected_index, genes_data):
    """
    Handle selection of a gene from search results
    """
    print(f"\n=== HANDLE GENE SELECTION ===")
    print(f"Selected index: {selected_index}")
    print(f"Have gene data: {bool(genes_data)}")
    
    if genes_data is None:
        print("No gene data available")
        return no_update
    
    if selected_index is None and genes_data:
        # If no selection but we have data, default to first gene
        print("No selection, defaulting to first gene")
        selected_index = '0'
    
    try:
        print("\n======= FAMILY GENE SEARCH SELECTION DEBUG =======")
        print(f"Selected index: {selected_index}, type: {type(selected_index)}")
        print(f"Genes data: {genes_data[:2]}...")  # Print just first 2 genes to avoid log clutter
        
        # Safely convert string index to integer
        idx = None
        if selected_index is not None:
            try:
                idx = int(selected_index)
            except ValueError:
                print(f"Failed to convert index '{selected_index}' to integer")
                return no_update
                
        # Get the selected gene by index
        if idx is not None and 0 <= idx < len(genes_data):
            selected_gene = genes_data[idx]
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
            
            print(f"Family gene search returning gene dict: {gene_dict}")
            
            # Return gene data without redirecting
            return gene_dict
        else:
            print(f"Invalid index: {idx}, genes_data length: {len(genes_data)}")
            return no_update
            
    except (IndexError, TypeError, KeyError) as e:
        print(f"Error processing selected gene: {e}")
        return no_update

# Callback to handle Enter key in search input
@callback(
    Output('family-gene-search-button', 'n_clicks', allow_duplicate=True),
    Input('family-gene-search-input', 'n_submit'),
    prevent_initial_call=True
)
def family_search_on_enter(n_submit):
    """
    Trigger search when Enter key is pressed
    """
    if n_submit:
        return 1  # Simulate button click
    return no_update

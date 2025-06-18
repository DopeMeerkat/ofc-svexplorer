"""
Table page for the UCONN OFC SV Browser application.
"""

from dash import html, dash_table, Input, Output, State, callback, no_update, dcc
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles

from utils.database import load_table_data
import os

# Load NCBI IDs from file
def load_ncbi_ids(file_path='assets/ncbi_ids.txt'):
    """
    Load NCBI gene IDs from a text file
    
    Args:
        file_path (str): Path to the text file containing gene names and NCBI IDs
        
    Returns:
        dict: Dictionary mapping gene names to NCBI IDs
    """
    ncbi_ids = {}
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        gene_name = parts[0]
                        ncbi_id = parts[1]
                        ncbi_ids[gene_name] = ncbi_id
            print(f"Loaded {len(ncbi_ids)} NCBI IDs from {file_path}")
        else:
            print(f"NCBI IDs file not found at {file_path}")
    except Exception as e:
        print(f"Error loading NCBI IDs: {e}")
    
    return ncbi_ids

# Load NCBI IDs once when the module is imported
NCBI_IDS = load_ncbi_ids()

def page_layout():
    """
    Create the table page layout
    
    Returns:
        dash.html.Div: Table page layout
    """
    df = load_table_data()
    if df.empty:
        return html.Div('No data found in table.csv', style={'padding': '30px', 'color': 'red'})
    
    return html.Div([
        html.H2('Table Data', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        html.P('Click on any row to view options for the gene', 
               style={'marginBottom': '15px', 'color': UCONN_NAVY, 'fontStyle': 'italic'}),
        dash_table.DataTable(
            id='gene-table',
            data=df.to_dict('records'),
            columns=[{"name": i, "id": i} for i in df.columns],
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left', 
                'padding': '5px',
                'cursor': 'pointer'  # Add pointer cursor to indicate clickable rows
            },
            style_header={'backgroundColor': UCONN_LIGHT_BLUE, 'fontWeight': 'bold'},
            style_data_conditional=[
                {
                    'if': {'column_id': 'Gene'},
                    'fontWeight': 'bold',
                    'color': UCONN_NAVY
                },
                {
                    'if': {'state': 'active'},  # When a cell is clicked
                    'backgroundColor': UCONN_LIGHT_BLUE,
                    'border': f'1px solid {UCONN_NAVY}'
                }
            ],
            page_size=20,
            # Remove row_selectable to eliminate checkboxes but keep row selection capability
            selected_rows=[],
        ),
        
        # Custom modal-like container using divs
        html.Div(
            id='gene-options-container',
            children=[
                html.Div(
                    id='gene-options-content',
                    children=[
                        html.Div([
                            html.H3('Gene Options', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                            html.Div(id='gene-options-details'),
                            html.Div([
                                html.Button('Close', id='close-options-button', 
                                          style={'marginRight': '10px', 'background': '#f8f9fa', 'border': f'1px solid {UCONN_NAVY}', 'padding': '5px 15px'})
                            ], style={'marginTop': '20px', 'textAlign': 'right'})
                        ], style={'padding': '20px'})
                    ],
                    style={
                        'backgroundColor': 'white', 
                        'borderRadius': '5px', 
                        'boxShadow': '0 4px 8px rgba(0,0,0,0.2)',
                        'maxWidth': '500px', 
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
                'backgroundColor': 'rgba(0,0,0,0.5)',
                'display': 'flex',
                'alignItems': 'center',
                'justifyContent': 'center',
                'zIndex': '999',
                'display': 'none'  # Initially hidden
            }
        ),
    ], style=uconn_styles['content'])

# Callback to handle gene table row selection and show options
@callback(
    Output('gene-options-container', 'style'),
    Output('gene-options-details', 'children'),
    Input('gene-table', 'active_cell'),
    State('gene-table', 'data'),
    prevent_initial_call=True
)
def show_gene_options(active_cell, table_data):
    """
    Handle selection of a gene from the table and show options
    """
    if active_cell:
        row = active_cell['row']
        gene_row = table_data[row]
        print("\n======= GENE TABLE CLICK DEBUG =======")
        print(f"Selected row: {row}")
        print(f"Row data: {gene_row}")
        
        # Extract gene name value from the row
        gene_value = gene_row.get('Gene', '')
        
        if gene_value:
            # Create option buttons for the gene
            options_content = html.Div([
                html.P(f'Selected Gene: {gene_value}', style={'fontWeight': 'bold', 'fontSize': '16px', 'marginBottom': '15px'}),
                html.P('Choose an action:', style={'marginBottom': '10px'}),
                
                # Option 1: View in Genome Browser
                html.Div([
                    html.Button('View in Genome Browser', 
                               id='view-in-browser-button',
                               n_clicks=0,
                               **{'data-gene': gene_value},  # Store gene value as data attribute
                               style={
                                   'background': UCONN_NAVY, 
                                   'color': 'white', 
                                   'border': 'none', 
                                   'padding': '10px 15px',
                                   'borderRadius': '3px',
                                   'marginRight': '10px',
                                   'cursor': 'pointer',
                                   'width': '100%',
                                   'textAlign': 'left'
                               }),
                ], style={'marginBottom': '10px'}),
                
                # Option 2: View in NCBI Gene Database - Direct link approach
                html.Div([
                    html.A(
                        'View in NCBI Gene Database',
                        # Use direct ID if available, otherwise use search URL
                        href=(f"https://www.ncbi.nlm.nih.gov/gene/{NCBI_IDS[gene_value]}" 
                             if gene_value in NCBI_IDS else 
                             f"https://www.ncbi.nlm.nih.gov/gene/?term={gene_value}[Gene+Name]+AND+human[Organism]"),
                        target='_blank',
                        style={
                            'background': UCONN_LIGHT_BLUE, 
                            'color': UCONN_NAVY, 
                            'border': 'none', 
                            'padding': '10px 15px',
                            'borderRadius': '3px',
                            'cursor': 'pointer',
                            'width': '100%',
                            'textAlign': 'left',
                            'display': 'block',
                            'textDecoration': 'none'
                        },
                    ),
                    # Show information about which NCBI ID is being used
                    html.P(
                        f"Using NCBI ID: {NCBI_IDS.get(gene_value, 'Not found - using gene name search')}", 
                        style={'fontSize': '12px', 'color': '#666', 'marginTop': '5px', 'textAlign': 'center'}
                    ) if gene_value else None
                ], style={'marginBottom': '10px'}),
                
                # Add description from table data if available
                html.Div([
                    html.P('Gene Description:', style={'fontWeight': 'bold', 'marginTop': '15px', 'marginBottom': '5px'}),
                    html.P(gene_row.get('Description', 'No description available'), style={'marginLeft': '10px'})
                ])
            ])
            
            # Show modal by updating display style
            return {'position': 'fixed', 'top': '0', 'left': '0', 'width': '100%', 'height': '100%',
                    'backgroundColor': 'rgba(0,0,0,0.5)', 'display': 'flex', 'alignItems': 'center',
                    'justifyContent': 'center', 'zIndex': '999'}, options_content
        else:
            print("No Gene column found in the row data")
            return {'display': 'none'}, no_update
        
    return {'display': 'none'}, no_update

# Callback to close the options container
@callback(
    Output('gene-options-container', 'style', allow_duplicate=True),
    Input('close-options-button', 'n_clicks'),
    prevent_initial_call=True
)
def close_options(n_clicks):
    """Close the options container when close button is clicked"""
    return {'display': 'none'}

# Callback to handle Genome Browser option
@callback(
    Output('selected-gene', 'data'),
    Output('url', 'pathname'),
    Output('gene-options-container', 'style', allow_duplicate=True),
    Input('view-in-browser-button', 'n_clicks'),
    State('view-in-browser-button', 'data-gene'),
    prevent_initial_call=True
)
def navigate_to_genome_browser(n_clicks, gene):
    """Navigate to genome browser with selected gene"""
    if n_clicks and gene:
        # Create a simplified dictionary with just the Gene value for the DB lookup
        simplified_row = {'Gene': gene}
        print(f"Navigating to genome browser for gene: {gene}")
        
        # Return the simplified data, redirect to genome browser, and close the options container
        return simplified_row, '/', {'display': 'none'}
    
    return no_update, no_update, no_update

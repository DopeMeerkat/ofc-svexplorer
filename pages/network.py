"""
Network visualization page using dash_cytoscape for the UCONN OFC SV Browser application.
"""

from dash import html, dcc, callback, Input, Output, no_update
import dash_cytoscape as cyto
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import get_gene_network_data

# Load the cytoscape stylesheet
cyto.load_extra_layouts()

def page_layout():
    """
    Create the network visualization page layout
    
    Returns:
        dash.html.Div: The network visualization page layout
    """
    return html.Div([
        html.Div([
            html.H2('Gene Network Visualization', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Explore gene interactions using this network visualization tool. You can interact with the network by dragging nodes and zooming.', 
                  style={'fontSize': '16px', 'lineHeight': '1.5'})
        ], style={'marginBottom': '30px'}),
        
        html.Div([
            html.Div([
                html.H3('Network Controls', style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='network-layout-dropdown',
                    options=[
                        {'label': 'Preset', 'value': 'preset'},
                        {'label': 'Circle', 'value': 'circle'},
                        {'label': 'Concentric', 'value': 'concentric'},
                        {'label': 'Cose', 'value': 'cose'},
                        {'label': 'Grid', 'value': 'grid'},
                        {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                    ],
                    value='cose',
                    style={'marginBottom': '10px'}
                ),
                html.Button('Reset View', id='reset-view-button', 
                           style={
                               'backgroundColor': UCONN_NAVY,
                               'color': 'white',
                               'border': 'none',
                               'padding': '10px 15px',
                               'borderRadius': '4px',
                               'cursor': 'pointer'
                           })
            ], style={'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'}),
            
            html.Div([
                cyto.Cytoscape(
                    id='gene-network',
                    layout={'name': 'cose'},
                    style={'width': '100%', 'height': '600px', 'border': f'1px solid {UCONN_NAVY}'},
                    elements=generate_default_network(),
                    stylesheet=[
                        # Group selectors
                        {
                            'selector': 'node',
                            'style': {
                                'content': 'data(label)',
                                'background-color': UCONN_NAVY,
                                'color': 'white',
                                'text-valign': 'center',
                                'text-halign': 'center',
                                'font-size': '12px'
                            }
                        },
                        {
                            'selector': 'edge',
                            'style': {
                                'width': 2,
                                'line-color': UCONN_LIGHT_BLUE,
                                'curve-style': 'bezier'
                            }
                        },
                        # Class selectors
                        {
                            'selector': '.highlighted',
                            'style': {
                                'background-color': '#FFD700',
                                'color': UCONN_NAVY,
                                'border-width': 2,
                                'border-color': UCONN_NAVY
                            }
                        },
                        {
                            'selector': '.selected-edge',
                            'style': {
                                'width': 4,
                                'line-color': '#FFD700'
                            }
                        }
                    ]
                )
            ], style={'width': '75%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        ]),
        
        html.Div([
            html.H3('Selected Gene Information', style={'color': UCONN_NAVY, 'marginTop': '20px'}),
            html.Div(id='gene-info-display', style={'marginTop': '10px', 'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'})
        ])
    ], style={'padding': '20px'})

def generate_default_network():
    """
    Generate a default network for initial display
    
    Returns:
        list: List of cytoscape elements (nodes and edges)
    """
    # This is placeholder data - in a real implementation, you might fetch this from your database
    return [
        # Nodes
        {'data': {'id': 'gene1', 'label': 'Test'}, 'position': {'x': 100, 'y': 100}},
        {'data': {'id': 'gene2', 'label': 'Hello'}, 'position': {'x': 200, 'y': 100}},
        {'data': {'id': 'gene3', 'label': 'World'}, 'position': {'x': 150, 'y': 200}},
        {'data': {'id': 'gene4', 'label': 'G1'}, 'position': {'x': 250, 'y': 200}},
        {'data': {'id': 'gene5', 'label': 'G2'}, 'position': {'x': 300, 'y': 100}},
        
        # Edges
        {'data': {'source': 'gene1', 'target': 'gene2'}},
        {'data': {'source': 'gene1', 'target': 'gene3'}},
        {'data': {'source': 'gene2', 'target': 'gene4'}},
        {'data': {'source': 'gene3', 'target': 'gene4'}},
        {'data': {'source': 'gene2', 'target': 'gene5'}}
    ]

# Callback to update the network layout
@callback(
    Output('gene-network', 'layout'),
    Input('network-layout-dropdown', 'value')
)
def update_layout(layout_name):
    """
    Update the network layout based on dropdown selection
    
    Args:
        layout_name (str): The name of the layout algorithm to use
        
    Returns:
        dict: Layout configuration
    """
    return {'name': layout_name}

# Callback to display gene information when a node is clicked
@callback(
    Output('gene-info-display', 'children'),
    Input('gene-network', 'tapNodeData')
)
def display_gene_info(node_data):
    """
    Display information about the selected gene
    
    Args:
        node_data (dict): Data associated with the selected node
        
    Returns:
        dash.html.Div: Gene information display
    """
    if not node_data:
        return html.P("Click on a gene node to view detailed information.")
    
    # In a real implementation, you would fetch detailed gene information from your database
    return html.Div([
        html.H4(f"Gene: {node_data['label']}", style={'color': UCONN_NAVY}),
        html.P(f"ID: {node_data['id']}"),
        html.P("Additional gene information would be displayed here. This could include genomic position, associated conditions, variants, or other relevant biological data.")
    ])

# Callback to reset the network view
@callback(
    Output('gene-network', 'elements'),
    Input('reset-view-button', 'n_clicks')
)
def reset_view(n_clicks):
    """
    Reset the network view when the reset button is clicked
    
    Args:
        n_clicks (int): Number of times the button has been clicked
        
    Returns:
        list: Network elements
    """
    if n_clicks is None:
        return no_update
    
    return generate_default_network()

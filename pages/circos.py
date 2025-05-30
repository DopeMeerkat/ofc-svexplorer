"""
Circos plot visualization page using dash_bio.Circos for the UCONN OFC SV Browser application.
This page displays genomic data in a circular layout, allowing for visualization of relationships
between different genomic regions.
"""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bio as dashbio
import pandas as pd
import numpy as np
import json

from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import get_circos_data

def page_layout():
    """
    Create the circos plot visualization page layout
    
    Returns:
        dash.html.Div: The circos visualization page layout
    """
    return html.Div([
        html.Div([
            html.H2('Circos Plot Visualization', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Explore genomic relationships using this interactive Circos plot. This visualization displays genomic data in a circular layout, allowing you to see relationships between different chromosomal regions.', 
                  style={'fontSize': '16px', 'lineHeight': '1.5'})
        ], style={'marginBottom': '30px'}),
        
        html.Div([
            html.Div([
                html.H3('Visualization Controls', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.Label('Select Data Type', style={'fontWeight': 'bold', 'color': UCONN_NAVY}),
                dcc.Dropdown(
                    id='circos-data-type',
                    options=[
                        {'label': 'Gene Density', 'value': 'gene_density'},
                        {'label': 'Structural Variations', 'value': 'structural_variations'},
                        {'label': 'Sample Comparison', 'value': 'sample_comparison'}
                    ],
                    value='gene_density',
                    style={'marginBottom': '15px'}
                ),
                
                html.Label('Select Chromosomes', style={'fontWeight': 'bold', 'color': UCONN_NAVY}),
                dcc.Checklist(
                    id='circos-chromosomes',
                    options=[
                        {'label': ' Chr 1', 'value': '1'},
                        {'label': ' Chr 2', 'value': '2'},
                        {'label': ' Chr 3', 'value': '3'},
                        {'label': ' Chr 4', 'value': '4'},
                        {'label': ' Chr 5', 'value': '5'},
                        {'label': ' Chr 6', 'value': '6'},
                        {'label': ' Chr 7', 'value': '7'},
                        {'label': ' Chr 8', 'value': '8'},
                        {'label': ' Chr 9', 'value': '9'},
                        {'label': ' Chr 10', 'value': '10'},
                        {'label': ' Chr 11', 'value': '11'},
                        {'label': ' Chr 12', 'value': '12'},
                        {'label': ' Chr 13', 'value': '13'},
                        {'label': ' Chr 14', 'value': '14'},
                        {'label': ' Chr 15', 'value': '15'},
                        {'label': ' Chr 16', 'value': '16'},
                        {'label': ' Chr 17', 'value': '17'},
                        {'label': ' Chr 18', 'value': '18'},
                        {'label': ' Chr 19', 'value': '19'},
                        {'label': ' Chr 20', 'value': '20'},
                        {'label': ' Chr 21', 'value': '21'},
                        {'label': ' Chr 22', 'value': '22'},
                        {'label': ' Chr X', 'value': 'X'},
                        {'label': ' Chr Y', 'value': 'Y'},
                    ],
                    value=['1', '2', '3', '4', '5'],
                    style={'marginBottom': '15px', 'columnCount': 2}
                ),
                
                html.Button('Update Visualization', id='update-circos-button', 
                           style={
                               'backgroundColor': UCONN_NAVY,
                               'color': 'white',
                               'border': 'none',
                               'padding': '10px 15px',
                               'borderRadius': '4px',
                               'cursor': 'pointer',
                               'marginTop': '10px'
                           })
            ], style={'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '10px'}),
            
            html.Div([
                html.Div(id='circos-loading-container', children=[
                    dcc.Loading(
                        id="circos-loading",
                        type="circle",
                        children=html.Div(id='circos-container', children=[
                            # Circos component will be loaded here via callback
                        ])
                    )
                ], style={'height': '600px', 'position': 'relative'})
            ], style={'width': '75%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ]),
        
        html.Div([
            html.H3('Selected Region Information', style={'color': UCONN_NAVY, 'marginTop': '20px'}),
            html.Div(id='circos-info-display', style={'marginTop': '10px', 'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'})
        ])
    ], style={'padding': '20px'})

# Callback to update the Circos visualization
@callback(
    Output('circos-container', 'children'),
    [Input('update-circos-button', 'n_clicks')],
    [State('circos-data-type', 'value'),
     State('circos-chromosomes', 'value')]
)
def update_circos_visualization(n_clicks, data_type, chromosomes):
    """
    Update the Circos visualization based on selected parameters
    
    Args:
        n_clicks (int): Number of times the update button has been clicked
        data_type (str): Selected data type to visualize
        chromosomes (list): List of selected chromosomes
        
    Returns:
        dashbio.Circos: Updated Circos component
    """
    if n_clicks is None:
        # Initial load - provide default visualization
        return generate_default_circos()
    
    # Get the data for the selected options
    layout_data, track_data = get_circos_data(data_type, chromosomes)
    
    return dashbio.Circos(
        id='circos-graph',
        layout=layout_data,
        tracks=track_data,
        config={
            'innerRadius': 300,
            'outerRadius': 320,
            'labels': {
                'display': True,
                'size': 14,
                'color': UCONN_NAVY,
                'radialOffset': 15,
            },
            'ticks': {
                'display': True,
                'color': UCONN_NAVY,
                'spacing': 1000000,
                'labels': True,
                'labelSpacing': 10,
                'labelSuffix': 'Mb',
                'labelDenominator': 1000000,
                'labelDisplay0': True,
                'labelSize': 10,
                'labelColor': UCONN_NAVY,
                'labelFont': 'Arial'
            }
        },
        style={'width': '100%', 'height': '600px'}
    )

# Callback to display information about a selected region
@callback(
    Output('circos-info-display', 'children'),
    Input('circos-graph', 'eventDatum')
)
def display_selected_data(selected_data):
    """
    Display information about the selected region in the Circos plot
    
    Args:
        selected_data (dict): Data associated with the selected region
        
    Returns:
        dash.html.Div: Information display
    """
    if not selected_data:
        return html.P("Click on a region in the Circos plot to view detailed information.")
    
    try:
        # Format the output based on the type of data selected
        if 'block_id' in selected_data:
            # This is a chromosome block
            return html.Div([
                html.H4(f"Chromosome: {selected_data['block_id']}", style={'color': UCONN_NAVY}),
                html.P(f"Start: {format_position(selected_data.get('start', 0))}"),
                html.P(f"End: {format_position(selected_data.get('end', 0))}"),
                html.P(f"Size: {format_size(selected_data.get('end', 0) - selected_data.get('start', 0))}")
            ])
        else:
            # This is a data point
            return html.Div([
                html.H4(f"Selected Data Point", style={'color': UCONN_NAVY}),
                html.P(f"Chromosome: {selected_data.get('block_id', 'Unknown')}"),
                html.P(f"Position: {format_position(selected_data.get('position', 0))}"),
                html.P(f"Value: {selected_data.get('value', 'N/A')}")
            ])
    except Exception as e:
        return html.P(f"Error parsing selection: {str(e)}")

def generate_default_circos():
    """
    Generate a default Circos visualization for initial load
    
    Returns:
        dashbio.Circos: Default Circos component
    """
    # Generate basic layout data for chromosomes 1-5
    layout_data = []
    for chrom in ['1', '2', '3', '4', '5']:
        size = get_chromosome_size(chrom)
        layout_data.append({
            'id': chrom,
            'label': f'Chr {chrom}',
            'color': UCONN_NAVY,
            'len': size
        })
    
    # Generate some sample histogram data
    histogram_data = []
    for chrom in ['1', '2', '3', '4', '5']:
        size = get_chromosome_size(chrom)
        num_points = 20
        step = size // num_points
        for i in range(num_points):
            pos = i * step
            # Create a sine wave pattern with some randomness
            value = (np.sin(i/num_points * 2 * np.pi) + 1) * 0.5 * 100 + np.random.randint(0, 20)
            histogram_data.append({
                'block_id': chrom,
                'position': pos,
                'value': value
            })
    
    # Sample chord data (connections between chromosomes)
    chord_data = [
        {'source': {'id': '1', 'start': 10000000, 'end': 20000000}, 
         'target': {'id': '2', 'start': 15000000, 'end': 25000000},
         'color': UCONN_LIGHT_BLUE},
        {'source': {'id': '3', 'start': 30000000, 'end': 40000000}, 
         'target': {'id': '5', 'start': 50000000, 'end': 60000000},
         'color': UCONN_LIGHT_BLUE},
        {'source': {'id': '2', 'start': 80000000, 'end': 90000000}, 
         'target': {'id': '4', 'start': 10000000, 'end': 20000000},
         'color': UCONN_LIGHT_BLUE}
    ]
    
    # Define tracks
    tracks = [
        {
            'type': 'CHORDS',
            'data': chord_data,
            'config': {
                'color': UCONN_LIGHT_BLUE,
                'opacity': 0.7,
                'tooltipContent': {'source': 'source', 'target': 'target'},
            }
        },
        {
            'type': 'HISTOGRAM',
            'data': histogram_data,
            'config': {
                'innerRadius': 250,
                'outerRadius': 300,
                'color': UCONN_LIGHT_BLUE,
                'tooltipContent': {
                    'position': 'position',
                    'value': 'value'
                }
            }
        }
    ]
    
    return dashbio.Circos(
        id='circos-graph',
        layout=layout_data,
        tracks=tracks,
        config={
            'innerRadius': 300,
            'outerRadius': 320,
            'labels': {
                'display': True,
                'size': 14,
                'color': UCONN_NAVY,
                'radialOffset': 15,
            },
            'ticks': {
                'display': True,
                'color': UCONN_NAVY,
                'spacing': 1000000,
                'labels': True,
                'labelSpacing': 10,
                'labelSuffix': 'Mb',
                'labelDenominator': 1000000,
                'labelDisplay0': True,
                'labelSize': 10,
                'labelColor': UCONN_NAVY,
                'labelFont': 'Arial'
            }
        },
        style={'width': '100%', 'height': '600px'}
    )

def get_chromosome_size(chrom):
    """
    Get the size of a chromosome (approximate values for human genome)
    
    Args:
        chrom (str): Chromosome identifier
        
    Returns:
        int: Size of the chromosome in base pairs
    """
    # Approximate sizes of human chromosomes in base pairs
    sizes = {
        '1': 248956422,
        '2': 242193529,
        '3': 198295559,
        '4': 190214555,
        '5': 181538259,
        '6': 170805979,
        '7': 159345973,
        '8': 145138636,
        '9': 138394717,
        '10': 133797422,
        '11': 135086622,
        '12': 133275309,
        '13': 114364328,
        '14': 107043718,
        '15': 101991189,
        '16': 90338345,
        '17': 83257441,
        '18': 80373285,
        '19': 58617616,
        '20': 64444167,
        '21': 46709983,
        '22': 50818468,
        'X': 156040895,
        'Y': 57227415
    }
    
    return sizes.get(chrom, 100000000)  # Default size if not found

def format_position(position):
    """Format a genomic position with commas for readability"""
    return f"{position:,}"

def format_size(size):
    """Format a genomic size with appropriate units"""
    if size >= 1000000:
        return f"{size/1000000:.2f} Mb"
    elif size >= 1000:
        return f"{size/1000:.2f} kb"
    else:
        return f"{size} bp"

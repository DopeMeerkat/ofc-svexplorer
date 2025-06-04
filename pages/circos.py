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
import sqlite3
import traceback
import sqlite3

from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import get_circos_data, DB_PATH

def page_layout():
    """
    Create the circos plot visualization page layout focused on gene interactions
    
    Returns:
        dash.html.Div: The circos visualization page layout
    """
    return html.Div([
        html.Div([
            html.H2('Circos Plot Visualization', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Explore gene interactions in a circular layout. The chords show relationships between different chromosomal regions.', 
                  style={'fontSize': '16px', 'lineHeight': '1.5'})
        ], style={'marginBottom': '30px'}),
        
        html.Div([
            html.Div([
                html.H3('Visualization Controls', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.Label('Data Type', style={'fontWeight': 'bold', 'color': UCONN_NAVY}),
                dcc.Dropdown(
                    id='circos-data-type',
                    options=[
                        {'label': 'Gene Interactions', 'value': 'gene_interactions'}
                    ],
                    value='gene_interactions',
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
                            update_circos_visualization(None, 'gene_interactions', ['1', '2', '3', '4', '5'])
                        ])
                    )
                ], style={'height': '700px', 'position': 'relative', 'paddingLeft': '40px', 'paddingBottom': '80px'})
            ], style={'width': '75%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ]),
    ], style={'padding': '20px', 'paddingBottom': '80px'})

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
    if not chromosomes or len(chromosomes) == 0:
        return html.Div("Please select at least one chromosome", style={'color': 'red', 'marginTop': '20px'})
    
    try:
        # Add 'chr' prefix to chromosomes
        chr_chromosomes = [f"chr{chrom}" for chrom in chromosomes]
        
        print("\n===== CIRCOS VISUALIZATION DEBUG =====")
        print(f"Selected data type: {data_type}")
        print(f"Selected chromosomes (original): {chromosomes}")
        print(f"Selected chromosomes (with chr prefix): {chr_chromosomes}")
        print(f"Number of chromosomes selected: {len(chromosomes)}")
        
        # Print each chromosome in detail for debugging
        print("\nDetailed chromosome information:")
        for i, chrom in enumerate(chromosomes):
            chr_chrom = f"chr{chrom}"
            print(f"  Chromosome {i+1}:")
            print(f"    Original format: '{chrom}' (type: {type(chrom).__name__})")
            print(f"    With chr prefix: '{chr_chrom}' (type: {type(chr_chrom).__name__})")
            print(f"    Starts with 'chr': {chr_chrom.startswith('chr')}")
            
            # Check if this chromosome is in our size dictionary (use the lookup function)
            from pages.circos import get_chromosome_size
            size = get_chromosome_size(chr_chrom)
            print(f"    Size from lookup: {size}")
        print(f"Using chr prefix: True")
        
        # Get the data for the selected options
        layout_data, track_data = get_circos_data(data_type, chr_chromosomes)
        
        # Check if we got valid layout data
        if not layout_data or len(layout_data) == 0:
            print("ERROR: No layout data generated!")
            return html.Div("Error: No layout data could be generated for the selected chromosomes.", 
                          style={'color': 'red', 'marginTop': '20px'})
        
        print(f"Generated layout data for {len(layout_data)} chromosomes")
        for layout_item in layout_data:
            print(f"  - Layout for {layout_item['id']}: length {layout_item['len']}")
        
        # If using gene interactions, check if we got any data
        if data_type == 'gene_interactions':
            if not track_data or not track_data[0].get('data'):
                print("WARNING: No gene interaction data found for the selected chromosomes")
                return html.Div([
                    html.P("No gene interaction data found for the selected chromosomes.", 
                          style={'color': 'orange', 'marginTop': '20px'}),
                    html.P("Try selecting different chromosomes or a different visualization type.")
                ])
            else:
                # Combine source and target genes into a single name field for tooltip
                for item in track_data[0].get('data', []):
                    item['name'] = f"{item.get('source_gene', 'Unknown')} → {item.get('target_gene', 'Unknown')}"
                
                track_data[0]['config'] = {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7,
                    'thickness': 4,
                    'tooltipContent': {
                        'name': 'name',
                    },
                    'tooltipStyle': {
                        'backgroundColor': 'rgba(0, 0, 0, 0.8)',
                        'color': 'white',
                        'padding': '8px',
                        'borderRadius': '4px',
                        'fontSize': '12px'
                    }
                }
        else:
            # For other data types, ensure default config is used
            for track in track_data:
                track['config'] = {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7
                }
        
        print("===== END CIRCOS VISUALIZATION DEBUG =====\n")
        
        return dashbio.Circos(
            id='circos-graph',
            layout=layout_data,
            tracks=track_data,
            config={
                'innerRadius': 300,
                'outerRadius': 320,
                'labels': {
                    'display': True,
                    'size': 18,  # Increased from 16 to 18
                    'color': UCONN_NAVY,
                    'radialOffset': 80,  # Increased from 30 to 45 to move labels higher
                    'position': 'center',
                    'font': 'Arial',
                    'backgroundColor': '#ffffff',
                    'padding': 6,  # Increased from 4 to 6
                    'borderRadius': 4,  # Increased from 2 to 4
                    'style': {
                        'fontWeight': 'bold'  # Make font bold
                    }
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
                    'labelFont': 'Arial',
                    'majorSpacing': 5000000,
                    'minorSpacing': 1000000,
                    'minorTickLength': 5,
                    'majorTickLength': 10
                },
                'zoomLimit': {
                    'min': 0.5,
                    'max': 10
                },
                'defaultTrackStyle': {
                    'tooltipShowEvent': 'mouseover',
                    'tooltipHideEvent': 'mouseout',
                    'tooltipPosition': 'auto',
                    'tooltipPadding': 10,
                    'tooltipStyle': {
                        'backgroundColor': 'rgba(0, 0, 0, 0.8)',
                        'color': 'white',
                        'padding': '8px',
                        'borderRadius': '4px',
                        'fontSize': '12px'
                    }
                }
            },
            style={'width': '100%', 'height': '700px'}
        )
    except Exception as e:
        traceback.print_exc()
        return html.Div(f"Error generating visualization: {str(e)}", style={'color': 'red', 'marginTop': '20px'})

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
        if 'block_id' in selected_data and 'value' not in selected_data and 'start' in selected_data and 'end' in selected_data:
            # This is a highlight region
            return html.Div([
                html.H4(f"Selected Region: {selected_data['block_id']}", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
                html.Div([
                    html.Div([
                        html.Strong("Chromosome:"),
                        html.Span(f" {selected_data['block_id']}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Start Position:"),
                        html.Span(f" {format_position(selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("End Position:"),
                        html.Span(f" {format_position(selected_data.get('end', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Region Size:"),
                        html.Span(f" {format_size(selected_data.get('end', 0) - selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'})
                ], style={'padding': '10px', 'backgroundColor': '#f5f5f5', 'borderRadius': '4px', 'marginBottom': '15px'}),
                html.Hr(style={'margin': '15px 0'}),
                html.P("This highlighted region represents an area of interest in the genome, which may contain significant genetic features or variations.", 
                      style={'fontStyle': 'italic', 'color': '#666'})
            ])
        elif 'block_id' in selected_data and 'value' not in selected_data:
            # This is a chromosome block
            return html.Div([
                html.H4(f"Chromosome: {selected_data['block_id']}", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
                html.Div([
                    html.Div([
                        html.Strong("Chromosome:"),
                        html.Span(f" {selected_data['block_id']}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Start:"),
                        html.Span(f" {format_position(selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("End:"),
                        html.Span(f" {format_position(selected_data.get('end', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Size:"),
                        html.Span(f" {format_size(selected_data.get('end', 0) - selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'})
                ], style={'padding': '10px', 'backgroundColor': '#f5f5f5', 'borderRadius': '4px', 'marginBottom': '15px'}),
                html.Hr(style={'margin': '15px 0'}),
                html.P("Click on chords to see gene interaction details or explore the visualization by hovering over different regions.", 
                      style={'fontStyle': 'italic', 'color': '#666'})
            ])
        elif 'source' in selected_data and 'target' in selected_data:
            # This is a chord (gene interaction or SV)
            source = selected_data.get('source', {})
            target = selected_data.get('target', {})
            
            # Check if we have direct gene information in the data
            source_gene = selected_data.get('source_gene', "Unknown")
            target_gene = selected_data.get('target_gene', "Unknown")
            tooltip = source_gene + " - " + target_gene


            print('HELLO', source, target, source_gene, target_gene)
            
            # If we don't have direct gene information, try to find genes at these locations
            if source_gene == "Unknown" or target_gene == "Unknown":
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                if source_gene == "Unknown" and 'id' in source and 'start' in source and 'end' in source:
                    cursor.execute("""
                        SELECT id FROM genes 
                        WHERE chrom = ? AND x1 <= ? AND x2 >= ?
                        LIMIT 1
                    """, (source['id'], source['end'], source['start']))
                    result = cursor.fetchone()
                    if result:
                        source_gene = result[0]
                
                if target_gene == "Unknown" and 'id' in target and 'start' in target and 'end' in target:
                    cursor.execute("""
                        SELECT id FROM genes 
                        WHERE chrom = ? AND x1 <= ? AND x2 >= ?
                        LIMIT 1
                    """, (target['id'], target['end'], target['start']))
                    result = cursor.fetchone()
                    if result:
                        target_gene = result[0]
                
                conn.close()
            
            # Calculate distance between interacting regions
            source_mid = (source.get('start', 0) + source.get('end', 0)) / 2
            target_mid = (target.get('start', 0) + target.get('end', 0)) / 2
            
            # Check if this is same chromosome or different chromosomes
            if source.get('id') == target.get('id'):
                distance = abs(source_mid - target_mid)
                distance_str = format_size(distance)
                distance_type = "Distance along chromosome"
            else:
                distance_type = "Interaction between chromosomes"
                distance_str = "Inter-chromosomal"
            
            return html.Div([
                html.H4(f"Gene Interaction", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
                html.Div([
                    html.Div([
                        html.Strong("Source:"),
                        html.Span(f" {source_gene} ({source.get('id', 'Unknown')})", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Source Location:"),
                        html.Span(f" {format_position(source.get('start', 0))}-{format_position(source.get('end', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Target:"),
                        html.Span(f" {target_gene} ({target.get('id', 'Unknown')})", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong("Target Location:"),
                        html.Span(f" {format_position(target.get('start', 0))}-{format_position(target.get('end', 0))}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'}),
                    html.Div([
                        html.Strong(distance_type + ":"),
                        html.Span(f" {distance_str}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'})
                ], style={'padding': '10px', 'backgroundColor': '#f5f5f5', 'borderRadius': '4px', 'marginBottom': '15px'}),
                html.Hr(style={'margin': '15px 0'}),
                html.P("""
                    This chord represents an interaction between two genomic regions, which may indicate
                    functional relationships, regulatory interactions, or structural variations.
                """, style={'fontStyle': 'italic', 'color': '#666'})
            ])
        else:
            # This is a data point (e.g., histogram, heatmap)
            
            # Determine the data type
            data_type = "Data Point"
            if 'value' in selected_data:
                if 'position' in selected_data:
                    data_type = "Histogram Data"
                elif 'start' in selected_data and 'end' in selected_data:
                    data_type = "Heatmap Data"
            
            # Basic info div to populate
            info_div = [
                html.H4(f"Selected {data_type}", style={'color': UCONN_NAVY, 'marginBottom': '10px'}),
                html.Div([
                    html.Div([
                        html.Strong("Chromosome:"),
                        html.Span(f" {selected_data.get('block_id', 'Unknown')}", style={'marginLeft': '10px'})
                    ], style={'marginBottom': '5px'})
                ], style={'padding': '10px', 'backgroundColor': '#f5f5f5', 'borderRadius': '4px', 'marginBottom': '15px'})
            ]
            
            # Add histogram-specific info
            if 'position' in selected_data:
                position_div = html.Div([
                    html.Strong("Position:"),
                    html.Span(f" {format_position(selected_data.get('position', 0))}", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(position_div)
                
                # Calculate relative position
                chrom_size = get_chromosome_size(selected_data.get('block_id', 'chr1'))
                rel_pos = (selected_data.get('position', 0) / chrom_size * 100)
                rel_pos_div = html.Div([
                    html.Strong("Relative Position:"),
                    html.Span(f" {rel_pos:.2f}% of chromosome length", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(rel_pos_div)
            
            # Add heatmap-specific info
            elif 'start' in selected_data and 'end' in selected_data:
                start_div = html.Div([
                    html.Strong("Start:"),
                    html.Span(f" {format_position(selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(start_div)
                
                end_div = html.Div([
                    html.Strong("End:"),
                    html.Span(f" {format_position(selected_data.get('end', 0))}", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(end_div)
                
                size_div = html.Div([
                    html.Strong("Region Size:"),
                    html.Span(f" {format_size(selected_data.get('end', 0) - selected_data.get('start', 0))}", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(size_div)
            
            # Add value info if present
            if 'value' in selected_data:
                value_div = html.Div([
                    html.Strong("Value:"),
                    html.Span(f" {selected_data.get('value', 'N/A')}", style={'marginLeft': '10px'})
                ], style={'marginBottom': '5px'})
                info_div[1].children.append(value_div)
            
            # Add explanation at the end
            info_div.extend([
                html.Hr(style={'margin': '15px 0'}),
                html.P(f"""
                    This {data_type.lower()} represents a quantitative measurement in the genome.
                    Higher values may indicate regions with more genetic activity or significance.
                """, style={'fontStyle': 'italic', 'color': '#666'})
            ])
            
            return html.Div(info_div)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return html.P(f"Error parsing selection: {str(e)}")

def generate_default_circos():
    """
    Generate a default Circos visualization for initial load
    
    Returns:
        dashbio.Circos: Default Circos component
    """
    print("\n===== CIRCOS DEFAULT VISUALIZATION DEBUG =====")
    print("Generating default visualization with chromosomes 1-5")
    
    # Generate basic layout data for chromosomes 1-5
    layout_data = []
    for chrom in ['1', '2', '3', '4', '5']:
        # Add 'chr' prefix
        db_chrom = f"chr{chrom}"
        size = get_chromosome_size(db_chrom)
        layout_data.append({
            'id': db_chrom,
            'label': f'Chr {chrom}',
            'color': UCONN_NAVY,
            'len': size,
            'labelLink': {
                'url': f'#chr{chrom}',  # Anchor link to allow jumping to specific chromosomes
                'target': '_self'
            },
            'labelBackgroundColor': '#f8f9fa',
            'labelTextAlign': 'center',
            'highlight': True,  # Enable highlighting on mouse hover
            'highlightColor': UCONN_LIGHT_BLUE,
            'highlightOpacity': 0.3
        })
    
    # No need for histogram data for gene interactions
    
    # Sample chord data (connections between chromosomes)
    chord_data = [
        {'source': {'id': f"chr1", 'start': 10000000, 'end': 20000000}, 
         'target': {'id': f"chr2", 'start': 15000000, 'end': 25000000},
         'color': UCONN_LIGHT_BLUE,
         'source_gene': 'Gene1-A',
         'target_gene': 'Gene2-B'},
        {'source': {'id': f"chr3", 'start': 30000000, 'end': 40000000}, 
         'target': {'id': f"chr5", 'start': 50000000, 'end': 60000000},
         'color': UCONN_LIGHT_BLUE,
         'source_gene': 'Gene3-C',
         'target_gene': 'Gene5-D'},
        {'source': {'id': f"chr2", 'start': 80000000, 'end': 90000000}, 
         'target': {'id': f"chr4", 'start': 10000000, 'end': 20000000},
         'color': UCONN_LIGHT_BLUE,
         'source_gene': 'Gene2-E',
         'target_gene': 'Gene4-F'}
    ]
    
    # Focusing just on gene interactions, no need for additional tracks
    
    print(f"Generated {len(chord_data)} default chord connections")
    print(f"First chord: {chord_data[0]['source']['id']} -> {chord_data[0]['target']['id']}")
    print("===== END CIRCOS DEFAULT VISUALIZATION DEBUG =====\n")
    
    # Define tracks - only use one track type to avoid duplicate tracks
    tracks = [
        # Chord track - for gene interactions or structural variations
        {
            'type': 'CHORDS',
            'data': chord_data,
            'config': {
                'color': UCONN_LIGHT_BLUE,
                'opacity': 0.7,
                'thickness': 4,  # Increase chord thickness
                'tooltipContent': {
                    'source': 'source',
                    'sourceID': 'id',
                    'sourceEnd': 'source_gene',
                    'target': 'target',
                    'targetID': 'id',
                    'targetEnd': 'target_gene'
                },
                'tooltipStyle': {
                    'backgroundColor': 'rgba(0, 0, 0, 0.8)',
                    'color': 'white',
                    'padding': '8px',
                    'borderRadius': '4px',
                    'fontSize': '12px'
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
                'size': 18,
                'color': UCONN_NAVY,
                'radialOffset': 80,  # Increased to 45 to match main visualization
                'position': 'center',
                'font': 'Arial',
                'backgroundColor': '#ffffff',
                'padding': 6,
                'borderRadius': 4,
                'style': {
                    'fontWeight': 'bold'
                }
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
            },
            'events': {}
        },
        style={'width': '100%', 'height': '700px'}
    )

def get_chromosome_size(chrom):
    """
    Get the size of a chromosome (approximate values for human genome)
    
    Args:
        chrom (str): Chromosome identifier
        
    Returns:
        int: Size of the chromosome in base pairs
    """
    # Import the function from utils.database to ensure consistency
    from utils.database import get_chromosome_size as db_get_chromosome_size
    
    # Forward the call to the database utility function
    print(f"Circos get_chromosome_size: Forwarding request for '{chrom}' to database utility")
    return db_get_chromosome_size(chrom)

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

# Callback to update the visualization explanation based on the selected data type
@callback(
    Output('visualization-explanation', 'children'),
    [Input('circos-data-type', 'value')]
)
def update_visualization_explanation(data_type):
    """
    Update the visualization explanation based on the selected data type
    
    Args:
        data_type (str): Selected data type
        
    Returns:
        dash.html.Div: Updated explanation
    """
    explanations = {
        'gene_density': html.Div([
            html.H4('Gene Density View', style={'color': UCONN_NAVY}),
            html.P('This visualization shows the density of genes across different regions of each chromosome.'),
            html.P('Taller histogram bars indicate regions with higher gene density. This can help identify gene-rich regions of the genome.'),
            html.Hr(),
            html.H5('Features of this visualization:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Histogram tracks show the density of genes along each chromosome'),
                html.Li('Highlighted regions (orange overlay) indicate areas with particularly high gene density'),
                html.Li('Axis labels show the scale of gene density values')
            ]),
            html.H5('How to interact:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Hover over histogram bars to see exact values'),
                html.Li('Click on regions to see detailed information below'),
                html.Li('Hover over chromosome segments to highlight them')
            ])
        ]),
        'structural_variations': html.Div([
            html.H4('Structural Variations View', style={'color': UCONN_NAVY}),
            html.P('This visualization shows structural variations (SVs) between different chromosomal regions.'),
            html.P('Each chord represents a structural variation such as deletions, duplications, inversions, or translocations. Click on any chord to see details.'),
            html.Hr(),
            html.H5('Features of this visualization:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Chord connections show structural variations between chromosomal regions'),
                html.Li('Chord thickness indicates the significance of the structural variation'),
                html.Li('Text labels mark notable structural variations for easy identification')
            ]),
            html.H5('How to interact:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Hover over chords to see the connected regions'),
                html.Li('Click on a chord to see detailed information about the structural variation'),
                html.Li('Use the text labels as a guide to find significant variations')
            ])
        ]),
        'gene_interactions': html.Div([
            html.H4('Gene Interactions View', style={'color': UCONN_NAVY}),
            html.P('This visualization shows interactions between genes across chromosomes. Each chord represents a relationship between genes located on different chromosomes or positions.'),
            html.P('The thickness of the chord indicates the strength or significance of the interaction. Hover over or click on any chord to see details about the connected genes.'),
            html.Hr(),
            html.H5('Features of this visualization:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Chord connections show interactions between genes'),
                html.Li('Chord thickness indicates interaction strength'),
                html.Li('Heatmap track shows the frequency of interactions along each chromosome')
            ]),
            html.H5('How to interact:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Hover over chords to see the interacting genes'),
                html.Li('Click on a chord to see detailed information about the gene interaction'),
                html.Li('Examine the heatmap to identify hotspots of gene interaction activity')
            ])
        ]),
        'sample_comparison': html.Div([
            html.H4('Sample Comparison View', style={'color': UCONN_NAVY}),
            html.P('This visualization combines gene density and structural variations to allow comparison between samples.'),
            html.P('The histogram tracks show gene density, while the chords show structural variations. This combined view helps identify correlations between gene density and structural changes.'),
            html.Hr(),
            html.H5('Features of this visualization:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Histogram tracks show gene density along chromosomes'),
                html.Li('Chord connections show structural variations between regions'),
                html.Li('Highlighted regions indicate areas of particular interest'),
                html.Li('Combined view allows correlation analysis between gene density and structural changes')
            ]),
            html.H5('How to interact:', style={'color': UCONN_NAVY}),
            html.Ul([
                html.Li('Hover over histogram bars to see gene density values'),
                html.Li('Click on chords to see details about structural variations'),
                html.Li('Examine highlighted regions to identify areas of interest')
            ])
        ])
    }
    
    return [
        html.H3('About This Visualization', style={'color': UCONN_NAVY, 'marginTop': '20px'}),
        html.Div(explanations.get(data_type, 'Select a visualization type to see more information.'), 
                style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px', 'marginTop': '10px'})
    ]

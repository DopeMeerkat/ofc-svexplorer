"""
Family Genomes Browser page for the UCONN OFC SV Browser application.
This page allows users to visualize structural variations within families,
showing data for parents and children in a side-by-side comparison.
"""

from dash import html, dcc, callback, Input, Output, State, no_update, ALL, MATCH, callback_context
import dash_bio as dashbio
import sqlite3
import json
import pandas as pd
from dash.exceptions import PreventUpdate

from app import app, HOSTED_GENOME_DICT
from components.family_gene_search import create_family_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import (
    get_family_ids, get_family_members, get_gene_by_id, 
    create_family_tracks, get_tracks_for_genome, DB_PATH,
    get_families_by_sv, get_child_sv_data
)

def page_layout(selected_gene=None):
    """
    Create the family genomes browser page layout
    
    Args:
        selected_gene (dict, optional): Selected gene information
    
    Returns:
        dash.html.Div: The family genomes browser page layout
    """
    # Get the list of available family IDs for the dropdown
    family_ids = get_family_ids()
    family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in family_ids]
    
    # If no families are found, provide a default empty option
    if not family_dropdown_options:
        family_dropdown_options = [{'label': 'No families available', 'value': ''}]
    
    # Set up chromosome and locus from selected gene (if provided)
    dropdown_options = [{'label': 'Select a chromosome...', 'value': ''}] + HOSTED_GENOME_DICT
    chrom = ''
    locus = ''
    if selected_gene:
        # selected_gene is a dict with keys matching the gene table columns
        chrom = selected_gene.get('chrom', '')
        x1 = selected_gene.get('x1', '')
        x2 = selected_gene.get('x2', '')
        if chrom and x1 and x2:
            print(f"Setting locus to: {chrom}:{x1}-{x2}")
            locus = f"{chrom}:{x1}-{x2}"
    
    return html.Div([
        html.Div([
            html.Div([
                html.H2('Family Genomes Browser', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.P('Explore structural variations within families. Select a family to view variations across parents and children.', 
                      style={'fontSize': '16px', 'lineHeight': '1.5'})
            ], style={'marginBottom': '30px'}),
            
            html.Div([
                html.Div([
                    # Step 1: Search by Structural Variation
                    html.H3('1. Search by Structural Variation', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.P('Find families with a specific structural variation:', style={'marginBottom': '10px'}),
                    html.Div([
                        dcc.Input(
                            id='sv-search-input',
                            type='text',
                            placeholder='Enter SV ID...',
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
                            id='sv-search-button', 
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
                    html.Div(id='sv-search-results', style={'marginBottom': '20px'}),
                    
                    # Step 2: Select Family
                    html.H3('2. Select Family', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.P('Choose a family to view:', style={'marginBottom': '10px'}),
                    dcc.Dropdown(
                        id='family-select',
                        options=family_dropdown_options,
                        value=family_ids[0] if family_ids else '',
                        style={'marginBottom': '20px'}
                    ),
                    
                    # Step 3: Search Genes
                    html.H3('3. Search Genes', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    # Gene search component
                    create_family_gene_search(),
                    
                    # Step 4: Load IGV Browser
                    html.H3('4. Load IGV Browser', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.Button(
                        'Load IGV Browser', 
                        id='load-igv-button', 
                        n_clicks=0,
                        style={
                            'backgroundColor': UCONN_NAVY,
                            'color': '#FFFFFF',
                            'border': 'none',
                            'padding': '12px 20px',
                            'borderRadius': '4px',
                            'cursor': 'pointer',
                            'marginBottom': '20px',
                            'width': '100%',
                            'fontSize': '16px'
                        }
                    ),
                    
                    # Hidden chromosome select (we'll keep this for functionality but it won't be displayed to the user)
                    html.Div([
                        dcc.Dropdown(
                            id='family-igv-genome-select',
                            options=dropdown_options,
                            value=chrom,
                        )
                    ], style={'display': 'none'}),
                    
                    # Family Information (initially hidden)
                    html.Div([
                        html.H3('Family Information', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                        html.Div(id='family-info-display', style={'marginBottom': '20px'})
                    ], id='family-info-container', style={'display': 'none'})
                ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px 0 0'}),
                
                html.Div([
                    dcc.Loading(
                        id="family-igv-loading",
                        type="circle",
                        children=[
                            html.Div([
                                html.Div(
                                    "Click 'Load IGV Browser' to view genomic data", 
                                    id='igv-placeholder',
                                    style={
                                        'height': '300px', 
                                        'display': 'flex', 
                                        'alignItems': 'center', 
                                        'justifyContent': 'center',
                                        'fontSize': '18px',
                                        'color': UCONN_NAVY,
                                        'backgroundColor': '#f8f9fa',
                                        'border': f'1px dashed {UCONN_LIGHT_BLUE}',
                                        'borderRadius': '4px'
                                    }
                                ),
                                html.Div(id='family-igv-browser-container', style={'height': '800px'})
                            ])
                        ]
                    )
                ], style={'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'})
            ], style={'display': 'flex'}),
            
            # Add CSV download information section
            html.Div([
                html.Hr(style={'marginTop': '30px', 'marginBottom': '20px'}),
                html.H4('Download Structural Variations Data', style={'color': UCONN_NAVY}),
                html.P('You can download a CSV file containing all structural variations for each child in the family. '
                      'Click the "Download SVs" button next to a child\'s information to download the data.'),
                html.P('The CSV contains gene associations, functional information, and regulatory details for each structural variation.')
            ], style={'marginTop': '30px'})
        ], style={'padding': '20px'}),
        
        # Store for selected gene data
        dcc.Store(id='selected-gene-store', data=None),
        
        # Store for families found by SV search
        dcc.Store(id='sv-families-store', data=None),
    ])

@callback(
    Output('family-info-display', 'children'),
    Input('family-select', 'value')
)
def update_family_info(family_id):
    """
    Update the family information display
    
    Args:
        family_id (str): Selected family ID
        
    Returns:
        dash.html.Div: Family information display
    """
    if not family_id:
        return html.P("Please select a family to view information.")
    
    try:
        # Get family members
        family_members = get_family_members(family_id)
        
        if not family_members['parents'] and not family_members['children']:
            return html.P(f"No data found for family {family_id}")
        
        # Display family information
        info_elements = [
            html.H4(f"Family ID: {family_id}", style={'color': UCONN_NAVY}),
        ]
        
        # Display parents
        if family_members['parents']:
            info_elements.append(html.H5("Parents:"))
            parent_list = []
            for parent in family_members['parents']:
                gender = 'Male' if parent['gender'] == 'M' else 'Female'
                parent_list.append(html.Li(f"{gender} (ID: {parent['bam_id']})"))
            info_elements.append(html.Ul(parent_list))
        
        # Display children
        if family_members['children']:
            info_elements.append(html.H5("Children:"))
            child_list = []
            for i, child in enumerate(family_members['children']):
                gender = 'Male' if child['gender'] == 'M' else 'Female'
                proband = " - Proband" if child['proband'] == 1 else ""
                affected = " - Affected" if child['affected'] == 1 else ""
                
                # Create a download button for each child
                download_id = f"download-child-sv-{i}"
                
                child_info = html.Li([
                    f"{gender}{proband}{affected} (ID: {child['bam_id']})",
                    html.Button(
                        "Download SVs", 
                        id={'type': 'download-child-button', 'index': i, 'child_id': child['bam_id']},
                        style={
                            'backgroundColor': UCONN_LIGHT_BLUE,
                            'color': '#FFFFFF',
                            'border': 'none',
                            'padding': '5px 10px',
                            'borderRadius': '4px',
                            'cursor': 'pointer',
                            'marginLeft': '10px',
                            'fontSize': '12px'
                        }
                    ),
                    dcc.Download(id={'type': 'download-child-sv', 'index': i})
                ])
                
                child_list.append(child_info)
            
            info_elements.append(html.Ul(child_list))
        
        return html.Div(info_elements)
    
    except Exception as e:
        print(f"Error getting family information: {e}")
        return html.P(f"Error retrieving information for family {family_id}")

@callback(
    [Output('family-igv-browser-container', 'children'),
     Output('family-info-container', 'style')],
    [Input('load-igv-button', 'n_clicks'),
     Input('family-select', 'value'),
     Input('family-igv-genome-select', 'value'),
     Input('selected-gene-store', 'data')],
    prevent_initial_call=True
)
def update_family_igv_browser(n_clicks, family_id, chrom, selected_gene):
    """
    Update the IGV browser with family data
    
    Args:
        n_clicks (int): Number of times the load button has been clicked
        family_id (str): Selected family ID
        chrom (str): Selected chromosome
        selected_gene (dict): Selected gene information
        
    Returns:
        tuple: (IGV browser component, family info visibility style)
    """
    if not n_clicks or not family_id:
        return no_update, {'display': 'none'}
    
    print(f"\n=== UPDATE FAMILY IGV BROWSER ===")
    print(f"Family ID: {family_id}")
    print(f"Chromosome: {chrom}")
    print(f"Selected gene: {selected_gene}")
    
    try:
        # Set up locus based on selected gene (if provided)
        locus = ""
        if selected_gene and isinstance(selected_gene, dict):
            try:
                print(f"Processing selected gene for locus: {selected_gene}")
                selected_gene_chrom = selected_gene.get('chrom', '')
                x1 = selected_gene.get('x1', '')
                x2 = selected_gene.get('x2', '')
                if selected_gene_chrom and x1 and x2:
                    locus = f"{selected_gene_chrom}:{x1}-{x2}"
                    print(f"Setting locus to: {locus}")
                    # If gene is on a different chromosome than selected, use the gene's chromosome
                    if selected_gene_chrom != chrom and selected_gene_chrom:
                        chrom = selected_gene_chrom
                        print(f"Updated chromosome to: {chrom} from gene data")
            except Exception as gene_error:
                print(f"Error processing selected gene data: {gene_error}")
                import traceback
                traceback.print_exc()
                # Continue without the gene locus if there's an issue
        
        # Create family tracks with BAM files
        # First get the family members for this family ID
        family_members = get_family_members(family_id)
        
        # Then create the tracks with the family members
        family_tracks = create_family_tracks(family_members)
        
        if not family_tracks:
            return html.Div(html.P("No data available for the selected family.", style={'color': 'red'})), {'display': 'block'}
        
        # Get SV tracks for this chromosome
        sv_tracks = get_tracks_for_genome(chrom)
        
        # Combine tracks
        all_tracks = sv_tracks + family_tracks
        
        # Set up locus for the IGV browser
        browser_locus = None
        if locus:
            browser_locus = locus
        elif chrom:
            browser_locus = chrom
        
        # Create the IGV browser component with direct properties
        igv_browser = dashbio.Igv(
            id='family-igv-browser',
            genome='hg38',
            tracks=all_tracks,
            locus=browser_locus,
            style={'height': '700px', 'width': '100%'}
        )
        
        return igv_browser, {'display': 'block'}
        
    except Exception as e:
        print(f"Error creating IGV browser: {e}")
        return html.Div(html.P(f"Error loading IGV browser: {str(e)}", style={'color': 'red'})), {'display': 'none'}
        return html.P("Please select a family to view the genome browser.")
    
    if not chrom and not (selected_gene and selected_gene.get('chrom')):
        return html.P("Please select a chromosome to view the genome browser.")
    
    # If a gene is selected but no chromosome is manually selected, use the gene's chromosome
    if not chrom and selected_gene and selected_gene.get('chrom'):
        chrom = selected_gene.get('chrom')
        print(f"Using chromosome from selected gene: {chrom}")
    
    try:
        # Get family members
        family_members = get_family_members(family_id)
        
        if not family_members['parents'] and not family_members['children']:
            return html.P(f"No data found for family {family_id}")
        
        # Create IGV tracks for the selected chromosome
        # First add the reference tracks
        reference_tracks = get_tracks_for_genome(chrom)
        
        # Then add family-specific tracks
        family_tracks = create_family_tracks(family_members)
        
        # Combine all tracks
        all_tracks = reference_tracks + family_tracks
        
        # Determine locus if a gene is selected
        locus = chrom
        if selected_gene and selected_gene.get('chrom', '') == chrom:
            x1 = selected_gene.get('x1', '')
            x2 = selected_gene.get('x2', '')
            if x1 and x2:
                print(f"Setting locus to: {chrom}:{x1}-{x2}")
                locus = f"{chrom}:{x1}-{x2}"
                
                # Add some padding around the gene for better visualization
                x1_padded = max(0, int(x1) - 5000)
                x2_padded = int(x2) + 5000
                locus = f"{chrom}:{x1_padded}-{x2_padded}"
                print(f"Padded locus: {locus}")
        
        # Create the IGV browser component
        return dashbio.Igv(
            id='family-igv',
            genome='hg38',
            locus=locus,
            tracks=all_tracks
        )
    
    except Exception as e:
        print(f"Error updating family IGV browser: {e}")
        return html.P(f"Error loading IGV browser for family {family_id} and chromosome {chrom}")

# Callback to update the IGV browser when a gene is selected
@callback(
    Output('family-igv-genome-select', 'value'),
    Input('selected-gene-store', 'data')
)
def update_chromosome_from_gene(selected_gene):
    """
    Update the selected chromosome when a gene is selected
    
    Args:
        selected_gene (dict): Selected gene information
        
    Returns:
        str: Selected chromosome
    """
    print(f"\n=== UPDATE CHROMOSOME FROM GENE ===")
    print(f"Selected gene data type: {type(selected_gene)}")
    print(f"Selected gene content: {selected_gene}")
    
    if not selected_gene:
        return ''
    
    try:
        # Check if we have a direct chrom field
        if isinstance(selected_gene, dict) and 'chrom' in selected_gene and selected_gene['chrom']:
            chrom = selected_gene['chrom']
            print(f"Setting chromosome to: {chrom} (direct from gene data)")
            return chrom
        
        # If not, try to get the gene by ID (for compatibility with the other selection methods)
        if isinstance(selected_gene, dict) and 'Gene' in selected_gene:
            gene_id = selected_gene['Gene']
            gene_info = get_gene_by_id(gene_id)
            if gene_info and 'chrom' in gene_info:
                chrom = gene_info['chrom']
                print(f"Setting chromosome to: {chrom} (from database)")
                return chrom
    except Exception as e:
        print(f"Error in update_chromosome_from_gene: {e}")
        import traceback
        traceback.print_exc()
    
    # If we couldn't get a chromosome, return empty string
    print("Could not determine chromosome from gene data")
    return ''

@callback(
    [Output('sv-search-results', 'children'),
     Output('sv-families-store', 'data'),
     Output('family-select', 'options'),
     Output('family-select', 'value')],
    [Input('sv-search-button', 'n_clicks')],
    [State('sv-search-input', 'value')]
)
def search_families_by_sv(n_clicks, sv_id):
    """
    Search for families that have a specific structural variation
    
    Args:
        n_clicks (int): Number of times the search button has been clicked
        sv_id (str): The SV ID to search for
        
    Returns:
        tuple: (search results message, families data, updated dropdown options, default selected family)
    """
    if not n_clicks or not sv_id:
        # Get all family IDs for the dropdown
        all_families = get_family_ids()
        family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in all_families]
        
        if not family_dropdown_options:
            family_dropdown_options = [{'label': 'No families available', 'value': ''}]
            
        return no_update, None, family_dropdown_options, no_update
    
    # Get families with this SV
    sv_families = get_families_by_sv(sv_id)
    
    if not sv_families:
        # No families found with this SV
        message = html.Div([
            html.P(f"No families found with SV: {sv_id}", style={'color': 'red'})
        ])
        
        # Get all family IDs for the dropdown (reset to default)
        all_families = get_family_ids()
        family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in all_families]
        
        return message, None, family_dropdown_options, all_families[0] if all_families else ''
    
    # Families found with this SV
    message = html.Div([
        html.P(f"Found {len(sv_families)} families with SV: {sv_id}", style={'color': 'green'}),
        html.P("Family dropdown has been updated with matching families.")
    ])
    
    # Create dropdown options for families with this SV
    family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in sv_families]
    
    # Set the default selected value to the first family in the list
    default_family = sv_families[0] if sv_families else ''
    
    return message, sv_families, family_dropdown_options, default_family

@callback(
    Output({'type': 'download-child-sv', 'index': ALL}, 'data'),
    Input({'type': 'download-child-button', 'index': ALL, 'child_id': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def download_child_sv_data(n_clicks_list):
    """
    Download SV data for a specific child when the download button is clicked
    
    Args:
        n_clicks_list (list): List of click counts for each download button
        
    Returns:
        dict: Download data dictionary for dcc.Download component
    """
    # Find which button was clicked
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    # Get the button ID that was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not button_id:
        raise PreventUpdate
    
    # Parse the JSON string to get the button properties
    try:
        button_props = json.loads(button_id)
        child_id = button_props.get('child_id')
        index = button_props.get('index')
        
        if not child_id or index is None:
            raise PreventUpdate
        
        # Get SV data for this child
        child_sv_data = get_child_sv_data(child_id)
        
        if child_sv_data.empty:
            print(f"No SV data found for child {child_id}")
            # Return a CSV with just the headers
            return [{'index': index, 'content': child_sv_data.to_csv(index=False), 'filename': f"{child_id}_sv_data.csv", 'type': 'text/csv'}]
        
        # Generate the CSV file
        csv_data = child_sv_data.to_csv(index=False)
        
        # Return a list with one item corresponding to the button that was clicked
        return_data = [None] * len(n_clicks_list)
        return_data[index] = {
            'content': csv_data,
            'filename': f"{child_id}_sv_data.csv",
            'type': 'text/csv'
        }
        
        return return_data
        
    except Exception as e:
        print(f"Error processing download request: {e}")
        import traceback
        traceback.print_exc()
        raise PreventUpdate

@callback(
    Output('igv-placeholder', 'style'),
    Input('family-igv-browser-container', 'children')
)
def hide_placeholder_when_igv_loaded(igv_content):
    """
    Hide the placeholder text when the IGV browser is loaded
    
    Args:
        igv_content: The content of the IGV browser container
        
    Returns:
        dict: CSS style to hide or show the placeholder
    """
    if igv_content is None:
        # Show placeholder when no IGV browser
        return {
            'height': '300px', 
            'display': 'flex', 
            'alignItems': 'center', 
            'justifyContent': 'center',
            'fontSize': '18px',
            'color': UCONN_NAVY,
            'backgroundColor': '#f8f9fa',
            'border': f'1px dashed {UCONN_LIGHT_BLUE}',
            'borderRadius': '4px'
        }
    else:
        # Hide placeholder when IGV is loaded
        return {'display': 'none'}

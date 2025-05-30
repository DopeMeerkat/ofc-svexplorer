"""
Family Genomes Browser page for the UCONN OFC SV Browser application.
This page allows users to visualize structural variations within families,
showing data for parents and children in a side-by-side comparison.
"""

from dash import html, dcc, callback, Input, Output, State
import dash_bio as dashbio
import sqlite3
import json

from app import app, HOSTED_GENOME_DICT
from components.family_gene_search import create_family_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import (
    get_family_ids, get_family_members, get_gene_by_id, 
    create_family_tracks, get_tracks_for_genome, DB_PATH
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
            
            # Gene search component
            create_family_gene_search(),
            
            html.Div([
                html.Div([
                    html.H3('Select Family', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.P('Choose a family to view:', style={'marginBottom': '10px'}),
                    dcc.Dropdown(
                        id='family-select',
                        options=family_dropdown_options,
                        value=family_ids[0] if family_ids else '',
                        style={'marginBottom': '20px'}
                    ),
                    
                    html.H3('Select Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.P('Choose the chromosome you would like to display:', style={'marginBottom': '10px'}),
                    dcc.Dropdown(
                        id='family-igv-genome-select',
                        options=dropdown_options,
                        value=chrom,
                        style={'marginBottom': '20px'}
                    ),
                    
                    html.H3('Family Information', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.Div(id='family-info-display', style={'marginBottom': '20px'})
                ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px 0 0'}),
                
                html.Div([
                    dcc.Loading(
                        id="family-igv-loading",
                        type="circle",
                        children=[
                            html.Div(id='family-igv-browser-container', style={'height': '800px'})
                        ]
                    )
                ], style={'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'})
            ], style={'display': 'flex'})
        ], style={'padding': '20px'}),
        
        # Store for selected gene data
        dcc.Store(id='selected-gene-store', data=None),
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
            for child in family_members['children']:
                gender = 'Male' if child['gender'] == 'M' else 'Female'
                proband = " - Proband" if child['proband'] == 1 else ""
                affected = " - Affected" if child['affected'] == 1 else ""
                child_list.append(html.Li(f"{gender}{proband}{affected} (ID: {child['bam_id']})"))
            info_elements.append(html.Ul(child_list))
        
        return html.Div(info_elements)
    
    except Exception as e:
        print(f"Error getting family information: {e}")
        return html.P(f"Error retrieving information for family {family_id}")

@callback(
    Output('family-igv-browser-container', 'children'),
    [Input('family-select', 'value'),
     Input('family-igv-genome-select', 'value'),
     Input('selected-gene-store', 'data')]
)
def update_family_igv_browser(family_id, chrom, selected_gene):
    """
    Update the IGV browser with family data
    
    Args:
        family_id (str): Selected family ID
        chrom (str): Selected chromosome
        selected_gene (dict): Selected gene information
        
    Returns:
        dashbio.Igv: Updated IGV browser component
    """
    print(f"\n=== UPDATE FAMILY IGV BROWSER ===")
    print(f"Family ID: {family_id}")
    print(f"Chromosome: {chrom}")
    print(f"Selected gene: {selected_gene}")
    
    if not family_id:
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
    print(f"Selected gene: {selected_gene}")
    
    if not selected_gene:
        return ''
    
    # Check if we have a direct chrom field
    if 'chrom' in selected_gene and selected_gene['chrom']:
        chrom = selected_gene['chrom']
        print(f"Setting chromosome to: {chrom} (direct from gene data)")
        return chrom
    
    # If not, try to get the gene by ID (for compatibility with the other selection methods)
    if 'Gene' in selected_gene:
        gene_id = selected_gene['Gene']
        gene_info = get_gene_by_id(gene_id)
        if gene_info and 'chrom' in gene_info:
            chrom = gene_info['chrom']
            print(f"Setting chromosome to: {chrom} (from database)")
            return chrom
    
    # If we couldn't get a chromosome, return empty string
    print("Could not determine chromosome from gene data")
    return ''

# We've removed the conflicting callback that was redirecting to the genome browser.
# The family_gene_search.py component already has a callback that updates selected-gene-store,
# so we don't need a duplicate callback here that was causing issues.

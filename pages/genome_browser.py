"""
Genome browser page for the UCONN OFC SV Browser application.
"""

from dash import html, dcc, Input, Output, State, callback
import dash_bio as dashbio
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles
from utils.database import get_tracks_for_genome, check_database_connection
from components.gene_search import create_gene_search
import os.path

def page_layout(selected_gene=None):
    """
    Create the genome browser page layout
    
    Args:
        selected_gene (dict, optional): Selected gene data
        
    Returns:
        dash.html.Div: Genome browser page layout
    """
    from app import HOSTED_GENOME_DICT
    
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
                html.H2('Interactive Genome Browser', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.P('Explore genomic data using this interactive visualization tool. Select a chromosome from the dropdown menu below to view the corresponding genomic tracks.', 
                      style={'fontSize': '16px', 'lineHeight': '1.5'})
            ], style={'marginBottom': '30px'}),
            # Gene search component
            create_gene_search(),
            html.Div([
                html.H3('Select Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Choose the chromosome you would like to display:', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='default-igv-genome-select',
                    options=dropdown_options,
                    value=chrom,
                    placeholder='Select a chromosome...',
                    style=uconn_styles['dropdown']
                ),
            ], style={'marginBottom': '20px'}),
            dcc.Loading(
                id='default-igv-container',
                type='circle',
                color=UCONN_NAVY,
                style=uconn_styles['loading']
            ),
            html.Div([
                html.P(f"Selected gene locus: {locus if locus else 'None'}", 
                      style={'fontSize': '14px', 'fontStyle': 'italic', 'color': UCONN_NAVY}) 
                if selected_gene else ''
            ], style={'marginBottom': '10px'}),
            html.Div(
                id='db-status',
                children=check_database_connection(),
                style=uconn_styles['statusBar']
            )
        ], style=uconn_styles['content']),
        
        # Hidden store to keep track of gene locus
        dcc.Store(id='current-locus', data=locus)
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px'})

# Return the IGV component with the selected genome.
@callback(
    Output('default-igv-container', 'children'),
    Input('default-igv-genome-select', 'value'),
    State('current-locus', 'data')
)
def return_igv(chrom, locus):
    """
    Return the IGV component for the selected chromosome
    """
    if not chrom:
        return html.Div(
            "Please select a chromosome from the dropdown",
            style={'padding': '20px', 'textAlign': 'center', 'color': UCONN_NAVY}
        )
    
    # Get tracks for selected chromosome
    tracks = get_tracks_for_genome(chrom)
    
    # Set view location - use full locus if available, otherwise default to first 1Mb
    view_locus = locus if locus and locus.startswith(f"{chrom}:") else f"{chrom}:1-1000000"
    print(f"Setting IGV view to: {view_locus}")
    
    return html.Div([
        html.Div([
            html.H3(f"Viewing Chromosome: {chrom}", style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            dashbio.Igv(
                id='default-igv',
                genome='hg38',  # Using hg38 as reference, adjust if needed
                locus=view_locus,
                minimumBases=100,
                tracks=tracks,
                style={'width': '100%', 'height': '600px', 'border': f'1px solid {UCONN_LIGHT_BLUE}'}
            )
        ], style={'padding': '15px', 'backgroundColor': '#FFFFFF', 'borderRadius': '5px'})
    ])

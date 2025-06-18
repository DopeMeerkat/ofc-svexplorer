"""
Population Structural Variations Browser page for the UCONN OFC SV Browser application.
This page shows combined structural variations across all families with separate tracks
for mother, father, child, and background reference data.
"""

from dash import html, dcc, callback, Input, Output
import dash_bio as dashbio
import sqlite3
import json

from app import app, HOSTED_GENOME_DICT
from components.population_gene_search import create_population_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import get_tracks_for_genome, DB_PATH, get_sample_counts

def page_layout(selected_gene=None):
    """
    Create the population structural variations browser page layout
    
    Args:
        selected_gene (dict, optional): Selected gene information
    
    Returns:
        dash.html.Div: The population SV browser page layout
    """
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
            html.H2('Population Structural Variations Browser', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Explore combined structural variations across the population. View aggregated data for mothers, fathers, children, and background reference variations.', 
                  style={'fontSize': '16px', 'lineHeight': '1.5'})
        ], style={'marginBottom': '30px'}),
        
        # Gene search component
        create_population_gene_search(),
        
        html.Div([
            html.Div([
                html.H3('Select Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Choose the chromosome you would like to display:', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='pop-igv-genome-select',
                    options=dropdown_options,
                    value=chrom,
                    style={'marginBottom': '20px'}
                ),
                
                html.H3('Track Information', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                # Track information with sample counts - updated dynamically
                html.Div(id='track-info-container', style={'marginBottom': '20px'})
            ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px 0 0'}),
            
            html.Div([
                dcc.Loading(
                    id="pop-igv-loading",
                    type="circle",
                    children=[
                        html.Div(id='pop-igv-browser-container', style={'height': '800px'})
                    ]
                )
            ], style={'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ], style={'display': 'flex'})
    ], style={'padding': '20px'})

@callback(
    Output('pop-igv-browser-container', 'children'),
    [Input('pop-igv-genome-select', 'value'),
     Input('pop-selected-gene-store', 'data')]
)
def update_population_igv_browser(chrom, selected_gene):
    """
    Update the IGV browser with population SV data
    
    Args:
        chrom (str): Selected chromosome
        selected_gene (dict): Selected gene information
        
    Returns:
        dashbio.Igv: Updated IGV browser component
    """
    print(f"\n=== UPDATE POPULATION IGV BROWSER ===")
    print(f"Chromosome: {chrom}")
    print(f"Selected gene: {selected_gene}")
    
    if not chrom and not (selected_gene and selected_gene.get('chrom')):
        return html.P("Please select a chromosome to view the genome browser.")
    
    # If a gene is selected but no chromosome is manually selected, use the gene's chromosome
    if not chrom and selected_gene and selected_gene.get('chrom'):
        chrom = selected_gene.get('chrom')
        print(f"Using chromosome from selected gene: {chrom}")
    
    try:
        # First add the reference tracks
        reference_tracks = get_tracks_for_genome(chrom)
        
        # Then add population tracks
        population_tracks = create_population_tracks(chrom)
        
        # Combine all tracks
        all_tracks = reference_tracks + population_tracks
        
        # Determine locus if a gene is selected
        locus = chrom
        if selected_gene and selected_gene.get('chrom', '') == chrom:
            x1 = selected_gene.get('x1', '')
            x2 = selected_gene.get('x2', '')
            if x1 and x2:
                print(f"Setting locus to: {chrom}:{x1}-{x2}")
                # Add some padding around the gene for better visualization
                x1_padded = max(0, int(x1) - 5000)
                x2_padded = int(x2) + 5000
                locus = f"{chrom}:{x1_padded}-{x2_padded}"
                print(f"Padded locus: {locus}")
        
        # Create the IGV browser component
        return dashbio.Igv(
            id='pop-igv',
            genome='hg38',
            locus=locus,
            tracks=all_tracks
        )
    
    except Exception as e:
        print(f"Error updating population IGV browser: {e}")
        return html.P(f"Error loading IGV browser for chromosome {chrom}")

# Callback to update chromosome dropdown when a gene is selected
@callback(
    Output('pop-igv-genome-select', 'value'),
    Input('pop-selected-gene-store', 'data'),
    prevent_initial_call=True
)
def update_chromosome_from_gene(selected_gene):
    """
    Update the chromosome dropdown value when a gene is selected
    
    Args:
        selected_gene (dict): Selected gene information
        
    Returns:
        str: Selected chromosome
    """
    print(f"\n=== UPDATE CHROMOSOME FROM GENE SELECTION ===")
    print(f"Selected gene: {selected_gene}")
    
    if not selected_gene:
        return ''
    
    # Check if we have chromosome information
    chrom = ''
    if 'chrom' in selected_gene and selected_gene['chrom']:
        chrom = selected_gene['chrom']
    
    return chrom

def create_population_tracks(chrom):
    """
    Create aggregated tracks for population SVs
    
    Args:
        chrom (str): The chromosome to create tracks for
        
    Returns:
        list: List of track objects for the IGV browser
    """
    # Create separate tracks for mothers, fathers, children, and background
    mother_track = create_parent_track(chrom, 'F', 'Mothers (Combined)')
    father_track = create_parent_track(chrom, 'M', 'Fathers (Combined)')
    child_track = create_child_track(chrom)
    background_track = create_background_track(chrom)
    
    return [mother_track, father_track, child_track, background_track]

def create_parent_track(chrom, gender, name):
    """
    Create track with SVs from all parents of specified gender
    
    Args:
        chrom (str): The chromosome to filter by
        gender (str): Parent gender ('M' or 'F')
        name (str): Track name
        
    Returns:
        dict: Track object for IGV browser
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get SVs from all parents of the specified gender on the given chromosome
        cursor.execute("""
            SELECT ps.sample, ps.id, ps.type, ps.chrom, ps.start, ps."end", ps.length 
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE ps.chrom = ? AND p.gender = ? AND p.child = 0
            ORDER BY ps.start
        """, (chrom, gender))
        
        # Create a dictionary to count occurrences of SVs with same ID
        sv_counts = {}
        sv_details = {}
        
        # Process rows and count occurrences
        for row in cursor.fetchall():
            sv_id = row['id']
            
            # Store details for the first occurrence
            if sv_id not in sv_details:
                sv_details[sv_id] = {
                    'chr': row['chrom'],
                    'start': row['start'],
                    'end': row['end'],
                    'type': row['type']
                }
            
            # Increment count
            if sv_id in sv_counts:
                sv_counts[sv_id] += 1
            else:
                sv_counts[sv_id] = 1
        
        # Create track features with count information
        features = []
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]
            feature = {
                'chr': details['chr'],
                'start': details['start'],
                'end': details['end'],
                'name': sv_id,
                'description': f"Type: {details['type']}<br>Count: {count}<br>Size: {details['end'] - details['start']} bp",
                'type': details['type']
            }
            features.append(feature)
        
        conn.close()
        
        # Set track color based on gender
        color = "#CC3366" if gender == 'F' else "#3366CC"
        
        # Create the track
        track = {
            'name': name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'EXPANDED',
            'color': color,
            'height': 100
        }
        
        return track
    
    except Exception as e:
        print(f"Error creating parent track: {e}")
        return {
            'name': name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': [],
            'displayMode': 'EXPANDED',
            'color': "#CC3366" if gender == 'F' else "#3366CC",
            'height': 100
        }

def create_child_track(chrom):
    """
    Create track with SVs from all children
    
    Args:
        chrom (str): The chromosome to filter by
        
    Returns:
        dict: Track object for IGV browser
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get SVs from all children on the given chromosome
        cursor.execute("""
            SELECT ps.sample, ps.id, ps.type, ps.chrom, ps.start, ps."end", ps.length,
                   p.affected, p.proband
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE ps.chrom = ? AND p.child = 1
            ORDER BY ps.start
        """, (chrom,))
        
        # Create dictionaries to count and track SV details
        sv_counts = {}
        sv_details = {}
        sv_statuses = {}
        
        # Process rows and count occurrences
        for row in cursor.fetchall():
            sv_id = row['id']
            
            # Store details for the first occurrence
            if sv_id not in sv_details:
                sv_details[sv_id] = {
                    'chr': row['chrom'],
                    'start': row['start'],
                    'end': row['end'],
                    'type': row['type']
                }
            
            # Track status information
            status = []
            if row['affected'] == 1:
                status.append("Affected")
            if row['proband'] == 1:
                status.append("Proband")
            
            if status:
                if sv_id not in sv_statuses:
                    sv_statuses[sv_id] = set()
                for s in status:
                    sv_statuses[sv_id].add(s)
            
            # Increment count
            if sv_id in sv_counts:
                sv_counts[sv_id] += 1
            else:
                sv_counts[sv_id] = 1
        
        # Create track features with count information
        features = []
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]
            
            # Format status string for description
            status_list = list(sv_statuses.get(sv_id, set()))
            status_str = f"Status: {', '.join(status_list)}<br>" if status_list else ""
            
            feature = {
                'chr': details['chr'],
                'start': details['start'],
                'end': details['end'],
                'name': sv_id,
                'description': f"Type: {details['type']}<br>{status_str}Count: {count}<br>Size: {details['end'] - details['start']} bp",
                'type': details['type']
            }
            features.append(feature)
        
        conn.close()
        
        # Create the track
        track = {
            'name': 'Children (Combined)',
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'EXPANDED',
            'color': UCONN_NAVY,
            'height': 100
        }
        
        return track
    
    except Exception as e:
        print(f"Error creating child track: {e}")
        return {
            'name': 'Children (Combined)',
            'sourceType': 'annotation',
            'format': 'bed',
            'features': [],
            'displayMode': 'EXPANDED',
            'color': UCONN_NAVY,
            'height': 100
        }

def create_background_track(chrom):
    """
    Create track with background SVs from reference populations
    
    Args:
        chrom (str): The chromosome to filter by
        
    Returns:
        dict: Track object for IGV browser
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get background SVs on the given chromosome
        cursor.execute("""
            SELECT id, type, chrom, start, "end", length, freq, pheno, gender, pop_code, superpop_code
            FROM background_svs
            WHERE chrom = ?
            ORDER BY start
        """, (chrom,))
        
        # Create dictionaries to count and track SV details
        sv_counts = {}
        sv_details = {}
        sv_pop_info = {}
        
        # Process rows and count occurrences
        for row in cursor.fetchall():
            sv_id = row['id']
            
            # Store details for the first occurrence
            if sv_id not in sv_details:
                sv_details[sv_id] = {
                    'chr': row['chrom'],
                    'start': row['start'],
                    'end': row['end'],
                    'type': row['type']
                }
            
            # Collect population information
            pop_info = []
            if row['pop_code']:
                pop_info.append(f"Pop: {row['pop_code']}")
            if row['superpop_code']:
                pop_info.append(f"SuperPop: {row['superpop_code']}")
            if row['freq']:
                pop_info.append(f"Freq: {row['freq']}")
            
            if pop_info:
                if sv_id not in sv_pop_info:
                    sv_pop_info[sv_id] = set()
                for info in pop_info:
                    sv_pop_info[sv_id].add(info)
            
            # Increment count
            if sv_id in sv_counts:
                sv_counts[sv_id] += 1
            else:
                sv_counts[sv_id] = 1
        
        # Create track features with count information
        features = []
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]
            
            # Format population information for description
            pop_info_list = list(sv_pop_info.get(sv_id, set()))
            pop_str = f"{','.join(pop_info_list)}<br>" if pop_info_list else "".replace(',', '<br>')
            
            feature = {
                'chr': details['chr'],
                'start': details['start'],
                'end': details['end'],
                'name': sv_id,
                'description': f"Type: {details['type']}<br>{pop_str}Count: {count}<br>Size: {details['end'] - details['start']} bp",
                'type': details['type']
            }
            features.append(feature)
        
        conn.close()
        
        # Create the track
        track = {
            'name': 'Background Reference SVs',
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'EXPANDED',
            'color': '#669900',  # Green color for background track
            'height': 100
        }
        
        return track
        
    except Exception as e:
        print(f"Error creating background track: {e}")
        return {
            'name': 'Background Reference SVs',
            'sourceType': 'annotation',
            'format': 'bed',
            'features': [],
            'displayMode': 'EXPANDED',
            'color': '#669900',
            'height': 100
        }

# Callback to update track information with sample counts
@callback(
    Output('track-info-container', 'children'),
    Input('pop-igv-genome-select', 'value')  # Any input to trigger initial load
)
def update_track_info(_):
    """Update the track information section with sample counts"""
    try:
        counts = get_sample_counts()
        return html.Div([
            html.H4('Mother Track', style={'color': '#CC3366'}),
            html.P([
                'Combined structural variations from all mothers in the dataset. ',
                html.Strong(f'({counts["mother"]} samples)')
            ]),
            html.H4('Father Track', style={'color': '#3366CC'}),
            html.P([
                'Combined structural variations from all fathers in the dataset. ',
                html.Strong(f'({counts["father"]} samples)')
            ]),
            html.H4('Child Track', style={'color': UCONN_NAVY}),
            html.P([
                'Combined structural variations from all children in the dataset. ',
                html.Strong(f'({counts["child"]} samples)')
            ]),
            html.H4('Background Track', style={'color': '#669900'}),
            html.P([
                'Reference structural variations from population databases. ',
                html.Strong(f'({counts["background"]} samples)')
            ])
        ])
    except Exception as e:
        print(f"Error updating track info: {e}")
        return html.Div('Error loading track information')

"""
Population Structural Variations Browser page for the UCONN OFC SV Browser application.
This page shows combined structural variations across all families with separate tracks
for mother, father, child, and background reference data.
"""

from dash import html, dcc, callback, Input, Output
import dash_bio as dashbio
import sqlite3
import json
from urllib.parse import parse_qs

from app import app, HOSTED_GENOME_DICT, build_local_igv_reference
from components.population_gene_search import create_population_gene_search
from utils.styling import control_label_style, muted_text_style, page_title_style, uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import get_tracks_for_genome, get_exon_track_for_genome, DB_PATH, get_sample_counts, get_gene_by_id, normalize_sv_table


OFC_RELEVANT_ENHANCER_CELLS = ('MESENCHYMAL', 'NEURALCREST')
ENHANCER_CANDIDATE_TABLES = {'active_enhancer_candidates'}
NOCCl_WINDOW_BUFFER = 80000

def _get_sv_by_id(sv_id):
    """Look up a structural variant locus from phenotype_svs only."""
    if not sv_id:
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, type, chrom, MIN(start) AS start, MAX("end") AS end FROM phenotype_svs WHERE id = ? GROUP BY id, type, chrom',
            (sv_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'id': row['id'],
            'Gene': row['id'],
            'type': 'sv',
            'sv_type': row['type'],
            'chrom': row['chrom'],
            'x1': row['start'],
            'x2': row['end'],
        }
    except Exception as e:
        print(f"Error loading SV locus: {e}")
        return None


def _selected_item_from_search(search):
    query = parse_qs((search or '').lstrip('?'))
    gene = (query.get('gene') or [''])[0].strip()
    if gene:
        gene_dict = get_gene_by_id(gene)
        if gene_dict:
            return {**gene_dict, 'Gene': gene_dict.get('id')}

    sv_id = (query.get('sv') or [''])[0].strip()
    if sv_id:
        return _get_sv_by_id(sv_id)

    chrom = (query.get('chrom') or [''])[0].strip()
    start = (query.get('start') or [''])[0].strip()
    end = (query.get('end') or [''])[0].strip()
    if chrom and start and end:
        try:
            return {
                'id': f'{chrom}:{start}-{end}',
                'Gene': f'{chrom}:{start}-{end}',
                'type': 'locus',
                'chrom': chrom,
                'x1': int(start),
                'x2': int(end),
            }
        except ValueError:
            pass

    return None


def page_layout(selected_gene=None, search=None):
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
    selected_gene = _selected_item_from_search(search) or selected_gene
    if selected_gene:
        # selected_gene is a dict with keys matching the gene table columns
        chrom = selected_gene.get('chrom', '')
        x1 = selected_gene.get('x1', '')
        x2 = selected_gene.get('x2', '')
        if chrom and x1 and x2:
            print(f"Setting initial locus to: {chrom}:{x1}-{x2}")
            locus = f"{chrom}:{x1}-{x2}"

    return html.Div([
        html.Div([
            html.H2('IGV / Population SV Browser', style=page_title_style),
            html.P(
                'Review cohort-level SV calls and regulatory annotation tracks in an IGV genome browser. Tracks are aggregated by source and do not display sample identifiers.',
                style=muted_text_style,
            ),
        ], style={'marginBottom': '30px'}),

        # Gene search component
        create_population_gene_search(initial_gene=selected_gene),

        html.Div([
            html.Div([
                html.H3('Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Select a chromosome or use gene/SV search to jump to a locus.', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='pop-igv-genome-select',
                    options=dropdown_options,
                    value=chrom,
                    style={'marginBottom': '20px'}
                ),

                html.H3('Track Information', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                # Track information with sample counts - updated dynamically
                html.Div(id='track-info-container', style={'marginBottom': '20px'}),

                html.H3('SV Dataset', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Select the SV call set displayed in the cohort tracks.', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='pop-sv-source',
                    options=[
                        {'label': 'Filtered SVs', 'value': 'filtered_svs'},
                        {'label': 'All SVs', 'value': 'phenotype_svs'},
                    ],
                    value='filtered_svs',
                    style={'marginBottom': '20px'}
                ),
                html.P('Flanking window around selected SVs (bp):', style={**control_label_style, 'marginBottom': '8px'}),
                dcc.Input(
                    id='pop-viewport-buffer',
                    type='number',
                    min=0,
                    step=500,
                    value=1000,
                    style={'width': '100%', 'marginBottom': '20px'}
                ),

                html.H3('Annotation Tracks', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Add regulatory and gene-model tracks to the IGV view.', style={'marginBottom': '10px'}),
                dcc.Checklist(
                    id='pop-optional-tracks',
                    options=[
                        {'label': 'Exons', 'value': 'exons'},
                        # {'label': 'Poised enhancer candidates', 'value': 'poised_enhancer_candidates'},
                        {'label': 'Active enhancer candidates', 'value': 'active_enhancer_candidates'},
                        {'label': 'Promoter candidates', 'value': 'promoter_candidates'},
                        {'label': 'Insulator candidates', 'value': 'insulator_candidates'},
                        {'label': 'No-cleft embryo cCREs', 'value': 'noccl_cCREs'},
                    ],
                    value=['exons', 'active_enhancer_candidates', 'noccl_cCREs'],
                    style={'marginBottom': '20px'}
                ),
            ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '0 20px 0 0'}),

            html.Div([
                dcc.Loading(
                    id="pop-igv-loading",
                    type="circle",
                    children=[
                        html.Div(id='pop-igv-browser-container', style={'minHeight': '800px', 'height': 'auto'})
                    ]
                )
            ], style={'width': '70%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ], style={'display': 'flex'})
    ], style={'padding': '20px'})

@callback(
    Output('pop-igv-browser-container', 'children'),
    [Input('pop-igv-genome-select', 'value'),
     Input('pop-selected-gene-store', 'data'),
     Input('pop-optional-tracks', 'value'),
     Input('pop-sv-source', 'value'),
     Input('pop-viewport-buffer', 'value')]
)
def update_population_igv_browser(chrom, selected_gene, optional_tracks, sv_source, viewport_buffer):
    """
    Update the IGV browser with population SV data

    Args:
        chrom (str): Selected chromosome
        selected_gene (dict): Selected gene information
        optional_tracks (list): Selected optional annotation tracks
        sv_source (str): SV source table (filtered_svs or phenotype_svs)
        viewport_buffer (int): Buffer (bp) loaded around a searched SV

    Returns:
        dashbio.Igv: Updated IGV browser component
    """
    print(f"\n=== UPDATE POPULATION IGV BROWSER ===")
    print(f"Chromosome: {chrom}")
    print(f"Selected gene: {selected_gene}")
    print(f"SV source: {sv_source}")
    print(f"Viewport buffer (bp): {viewport_buffer}")

    if not chrom and not (selected_gene and selected_gene.get('chrom')):
        return html.P("Please select a chromosome to view the genome browser.")

    # If a gene is selected but no chromosome is manually selected, use the gene's chromosome
    if not chrom and selected_gene and selected_gene.get('chrom'):
        chrom = selected_gene.get('chrom')
        print(f"Using chromosome from selected gene: {chrom}")

    try:
        # Determine the IGV viewport. Population optional tracks remain chromosome-wide.
        locus = chrom
        x1_padded = None
        x2_padded = None
        if selected_gene and selected_gene.get('chrom', '') == chrom:
            x1 = selected_gene.get('x1', '')
            x2 = selected_gene.get('x2', '')
            if x1 and x2:
                item_type = selected_gene.get('type')
                if item_type == 'sv':
                    buffer_bp = max(0, int(viewport_buffer or 1000))
                elif item_type == 'locus':
                    buffer_bp = 0
                else:
                    buffer_bp = 5000
                print(f"Setting locus to: {chrom}:{x1}-{x2}")
                x1_padded = max(0, int(x1) - buffer_bp)
                x2_padded = int(x2) + buffer_bp
                locus = f"{chrom}:{x1_padded}-{x2_padded}"
                print(f"Padded locus: {locus}")

        # Reference annotation tracks
        reference_tracks = get_tracks_for_genome(chrom)

        # Population SV tracks
        sv_source = normalize_sv_table(sv_source)
        population_tracks = create_population_tracks(chrom, sv_source)

        # Optional annotation tracks based on checklist. Unlike Family SVs, Population
        # loads selected annotation tracks for the entire selected chromosome.
        optional_tracks_list = []
        if optional_tracks:
            if 'exons' in optional_tracks:
                exon_tracks = get_exon_track_for_genome(chrom)
                optional_tracks_list.extend(exon_tracks)
            candidate_configs = [
                # ('poised_enhancer_candidates', 'Poised Enhancer Candidates', '#FF6B6B'),
                ('active_enhancer_candidates', 'Active Enhancer Candidates', '#4ECDC4'),
                ('promoter_candidates', 'Promoter Candidates', '#45B7D1'),
                ('insulator_candidates', 'Insulator Candidates', '#96CEB4'),
            ]
            for table_name, display_name, color in candidate_configs:
                if table_name in optional_tracks:
                    track = create_candidate_region_track(chrom, table_name, display_name, color)
                    optional_tracks_list.append(track)
            if 'noccl_cCREs' in optional_tracks:
                # Load a generous window around the searched gene/SV instead of the
                # entire chromosome, so dense chromosomes are not truncated by the
                # per-track feature cap. Falls back to the whole chromosome when no
                # locus has been searched.
                noccl_start = None
                noccl_end = None
                if selected_gene and selected_gene.get('chrom', '') == chrom and selected_gene.get('x1') and selected_gene.get('x2'):
                    noccl_start = max(0, int(selected_gene['x1']) - NOCCl_WINDOW_BUFFER)
                    noccl_end = int(selected_gene['x2']) + NOCCl_WINDOW_BUFFER
                optional_tracks_list.append(create_noccl_ccre_track(chrom, start=noccl_start, end=noccl_end))

        # Combine all tracks
        all_tracks = reference_tracks + optional_tracks_list + population_tracks

        # Create the IGV browser component
        return dashbio.Igv(
            id='pop-igv',
            reference=build_local_igv_reference(chrom),
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

def create_population_tracks(chrom, sv_table='filtered_svs'):
    """
    Create aggregated tracks for population SVs

    Args:
        chrom (str): The chromosome to create tracks for
        sv_table (str): SV source table (filtered_svs or phenotype_svs)

    Returns:
        list: List of track objects for the IGV browser
    """
    sv_table = normalize_sv_table(sv_table)
    # Create separate tracks for mothers, fathers, children, and background
    mother_track = create_parent_track(chrom, 'F', 'Mothers (Combined)', sv_table)
    father_track = create_parent_track(chrom, 'M', 'Fathers (Combined)', sv_table)
    child_track = create_child_track(chrom, sv_table)
    background_track = create_background_track(chrom)

    return [mother_track, father_track, child_track, background_track]


def _format_frequency(freq, count, denominator):
    """Format a precomputed SV frequency for IGV tooltips."""
    try:
        freq_value = float(freq or 0)
    except (TypeError, ValueError):
        freq_value = 0.0
    return f"Frequency: {freq_value:.2%}"

def create_parent_track(chrom, gender, name, sv_table='filtered_svs'):
    """
    Create track with SVs from all parents of specified gender

    Args:
        chrom (str): The chromosome to filter by
        gender (str): Parent gender ('M' or 'F')
        name (str): Track name
        sv_table (str): SV source table (filtered_svs or phenotype_svs)

    Returns:
        dict: Track object for IGV browser
    """
    sv_table = normalize_sv_table(sv_table)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query to get SVs from all parents of the specified gender on the given chromosome
        cursor.execute(f"""
            SELECT ps.sample, ps.id, ps.type, ps.chrom, ps.start, ps."end", ps.length,
                   ps.count_mother, ps.freq_mother, ps.count_father, ps.freq_father
            FROM {sv_table} ps
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
                    'type': row['type'],
                    'count_mother': row['count_mother'],
                    'freq_mother': row['freq_mother'],
                    'count_father': row['count_father'],
                    'freq_father': row['freq_father'],
                }

            # Increment count
            if sv_id in sv_counts:
                sv_counts[sv_id] += 1
            else:
                sv_counts[sv_id] = 1

        # Create track features with count information
        features = []
        role = 'mother' if gender == 'F' else 'father'
        count_col = f'count_{role}'
        freq_col = f'freq_{role}'
        sample_counts = get_sample_counts()
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]
            frequency_text = _format_frequency(details.get(freq_col), details.get(count_col), sample_counts.get(role))
            feature = {
                'chr': details['chr'],
                'start': details['start'],
                'end': details['end'],
                'name': sv_id,
                'description': f"Type: {details['type']}<br>{frequency_text}<br>Size: {details['end'] - details['start']} bp",
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

def create_child_track(chrom, sv_table='filtered_svs'):
    """
    Create track with SVs from all children

    Args:
        chrom (str): The chromosome to filter by
        sv_table (str): SV source table (filtered_svs or phenotype_svs)

    Returns:
        dict: Track object for IGV browser
    """
    sv_table = normalize_sv_table(sv_table)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query to get SVs from all children on the given chromosome
        cursor.execute(f"""
            SELECT ps.sample, ps.id, ps.type, ps.chrom, ps.start, ps."end", ps.length,
                   ps.count_child, ps.freq_child, p.affected, p.proband
            FROM {sv_table} ps
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
                    'type': row['type'],
                    'count_child': row['count_child'],
                    'freq_child': row['freq_child'],
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
        sample_counts = get_sample_counts()
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
                'description': f"Type: {details['type']}<br>{status_str}{_format_frequency(details.get('freq_child'), details.get('count_child'), sample_counts.get('child'))}<br>Size: {details['end'] - details['start']} bp",
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
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query to get background SVs on the given chromosome
        cursor.execute("""
            SELECT id, type, chrom, start, "end", length, freq, count_background, freq_background, pheno, gender, pop_code, superpop_code
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
                    'type': row['type'],
                    'count_background': row['count_background'],
                    'freq_background': row['freq_background'],
                }

            # Collect population information
            pop_info = []
            if row['pop_code']:
                pop_info.append(f"Pop: {row['pop_code']}")
            if row['superpop_code']:
                pop_info.append(f"SuperPop: {row['superpop_code']}")

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

        conn.close()

        # Load additional information from CSV file if the chromosome is 19
        # This is an enhancement to add more detailed descriptions
        sv_additional_info = {}
        if chrom == '19':
            try:
                import pandas as pd
                import os
                import numpy as np

                csv_path = os.path.join('assets', 'cellvar_chr19_table.csv')
                if os.path.exists(csv_path):
                    # Read and inspect the CSV file

                    # Load the CSV with proper handling of missing values
                    df = pd.read_csv(csv_path)

                    df = df.replace({np.nan: None})  # Replace NaN with None for easier handling

                    # For debugging CSV SV IDs
                    sample_svs = []

                    # Group by SV ID to collect all information
                    for sv_id, group in df.groupby('sv_id'):
                        # Debug: Check SV ID format in CSV
                        if len(sample_svs) < 5:
                            sample_svs.append(sv_id)

                        if sv_id not in sv_additional_info:
                            # Get the first row for basic info
                            first_row = group.iloc[0]

                            # Store basic SV information with safe gets
                            sv_additional_info[sv_id] = {
                                'gene_names': set(filter(None, group['gene_name'].unique())),
                                'sv_type': first_row.get('sv_type', 'Unknown'),
                                'functional_likelihood': float(first_row.get('functional_likelihood', 0)),
                                'frequency': float(first_row.get('frequency', 0)),
                                'sample_count': int(first_row.get('sample_count', 0)),
                                'regulatory_types': set(filter(None, group['regulatory_type'].unique() if 'regulatory_type' in group else [])),
                                'regulatory_cell_types': set(filter(None, group['regulatory_cell_type'].unique() if 'regulatory_cell_type' in group else [])),
                                'expected_value': float(first_row.get('expected_value', 0)),
                                'regulatory_scores': {},
                                'regulatory_ids': set(filter(None, group['regulatory_id'].unique() if 'regulatory_id' in group else [])),
                                'regulatory_details': []
                            }

                            # Collect regulatory scores for each cell type
                            for _, row in group.iterrows():
                                cell_type = row.get('regulatory_cell_type')
                                if cell_type and 'regulatory_cell_score' in row and row['regulatory_cell_score'] is not None:
                                    if cell_type not in sv_additional_info[sv_id]['regulatory_scores']:
                                        sv_additional_info[sv_id]['regulatory_scores'][cell_type] = float(row['regulatory_cell_score'])

                                # Collect detailed regulatory information
                                if all(k in row and row[k] is not None for k in ['regulatory_id', 'regulatory_type', 'regulatory_score']):
                                    sv_additional_info[sv_id]['regulatory_details'].append({
                                        'id': row['regulatory_id'],
                                        'type': row['regulatory_type'],
                                        'score': float(row['regulatory_score']),
                                        'cell_type': row.get('regulatory_cell_type', ''),
                                        'cell_score': float(row.get('regulatory_cell_score', 0)) if row.get('regulatory_cell_score') is not None else 0
                                    })


            except Exception as e:
                print(f"Error loading additional SV info from CSV: {e}")
                # Add traceback for better debugging
                import traceback
                traceback.print_exc()

        # Create track features with count and additional information
        features = []

        # Debug: Check for ID mismatches between database SVs and CSV SVs
        db_sv_ids = set(sv_counts.keys())
        csv_sv_ids = set(sv_additional_info.keys())
        common_ids = db_sv_ids.intersection(csv_sv_ids)


        # Try to fix ID format mismatches if there are few or no matches
        if len(common_ids) < min(len(db_sv_ids), len(csv_sv_ids)) * 0.1:  # Less than 10% match

            # Try to create a mapping between CSV and DB IDs
            db_samples = list(db_sv_ids)[:5]
            csv_samples = list(csv_sv_ids)[:5]
            sv_id_mapping = {}

            # Check if CSV IDs might need a prefix
            if len(common_ids) == 0:
                # Try common transformations
                transformations = [
                    # Add C_ prefix
                    lambda x: f"C_{x}" if not x.startswith("C_") else x,
                    # Remove C_ prefix
                    lambda x: x[2:] if x.startswith("C_") else x,
                    # Try with just the numeric part
                    lambda x: ''.join(c for c in x if c.isdigit()),
                ]

                # Test transformations on sample IDs
                for transform in transformations:
                    csv_transformed = {transform(id) for id in csv_samples}
                    matches = csv_transformed.intersection(db_samples)
                    if matches:
                        # Apply this transformation to all CSV IDs
                        transformed_mapping = {}
                        for csv_id in csv_sv_ids:
                            transformed_id = transform(csv_id)
                            if transformed_id in db_sv_ids:
                                transformed_mapping[transformed_id] = sv_additional_info[csv_id]

                        if transformed_mapping:
                            sv_additional_info = transformed_mapping
                            break

        sample_counts = get_sample_counts()
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]

            # Format population information for description
            pop_info_list = list(sv_pop_info.get(sv_id, set()))
            pop_str = "<br>".join(pop_info_list) + "<br>" if pop_info_list else ""

            # Add additional information from CSV if available
            additional_info = ""
            if sv_id in sv_additional_info:
                info = sv_additional_info[sv_id]

                # Format gene names (wrap long lists with line breaks)
                if info['gene_names']:
                    additional_info += f"Associated genes:<br>{_wrap_items(list(info['gene_names']), max_per_line=4)}<br>"

                # Add functional and regulatory information
                if 'functional_likelihood' in info:
                    additional_info += f"Functional likelihood: {info['functional_likelihood']:.3f}<br>"
                if 'expected_value' in info:
                    additional_info += f"Expected value: {info['expected_value']:.3f}<br>"
                if 'frequency' in info:
                    additional_info += f"Frequency: {info['frequency']:.6f}<br>"

                # Add regulatory information (wrap long lists with line breaks)
                if info['regulatory_types']:
                    additional_info += f"Regulatory elements:<br>{_wrap_items(list(info['regulatory_types']), max_per_line=4)}<br>"

                if info['regulatory_cell_types']:
                    additional_info += f"Cell types:<br>{_wrap_items(list(info['regulatory_cell_types']), max_per_line=4)}<br>"

                # Add regulatory scores by cell type
                if info.get('regulatory_scores') and len(info['regulatory_scores']) > 0:
                    additional_info += "<br><b>Regulatory scores by cell type:</b><br>"
                    for cell_type, score in info['regulatory_scores'].items():
                        if cell_type:  # Ensure cell type is not empty
                            additional_info += f"- {cell_type}: {score:.3f}<br>"

                # Add detailed regulatory information for specialists
                if info.get('regulatory_details') and len(info['regulatory_details']) > 0:
                    additional_info += "<br><b>Detailed Regulatory Information:</b><br>"
                    # Limit to the top 3 regulatory elements to avoid too much information
                    for i, reg_detail in enumerate(info['regulatory_details'][:3]):
                        detail_line = f"- {reg_detail.get('type', 'Unknown')} ({reg_detail.get('id', 'Unknown')})"

                        if 'score' in reg_detail:
                            detail_line += f": Score {reg_detail['score']:.3f}"

                        if reg_detail.get('cell_type'):
                            detail_line += f", Cell: {reg_detail['cell_type']}"
                            if 'cell_score' in reg_detail and reg_detail['cell_score']:
                                score_value = float(reg_detail['cell_score'])
                                detail_line += f" (Score: {score_value:.3f})"
                                # try:
                                #     score_value = float(reg_detail['cell_score'])
                                #     detail_line += f" (Score: {score_value:.3f})"
                                # except (ValueError, TypeError):
                                #     # Skip score formatting if conversion fails
                                #     pass

                        additional_info += detail_line + "<br>"

                    # Indicate if there are more details
                    if len(info['regulatory_details']) > 3:
                        additional_info += f"... (+{len(info['regulatory_details'])-3} more regulatory elements)<br>"

            # Create the description (simple flat format like the children track)
            description = f"Type: {details['type']}<br>"
            description += f"Size: {details['end'] - details['start']} bp<br>"
            description += f"{_format_frequency(details.get('freq_background'), details.get('count_background'), sample_counts.get('background'))}<br>"

            # Add population information if available
            if pop_str:
                description += pop_str

            # Add the additional info if available
            if additional_info:
                description += additional_info

            feature = {
                'chr': details['chr'],
                'start': details['start'],
                'end': details['end'],
                'name': sv_id,
                'description': description,
                'type': details['type']
            }
            features.append(feature)

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

def _wrap_items(items, max_per_line=5):
    """Break a list of strings into multiple lines of at most max_per_line items."""
    if not items:
        return ""
    lines = []
    for i in range(0, len(items), max_per_line):
        lines.append(", ".join(items[i:i + max_per_line]))
    return "<br>".join(lines)


def create_candidate_region_track(chrom, table_name, display_name, color, start=None, end=None):
    """Create an IGV annotation track from a candidate region table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        peak_col = 'peak_bp_overlap' if table_name == 'promoter_candidates' else 'peak_bp_dist'

        params = [chrom]
        where_extra = ""
        if start is not None and end is not None:
            where_extra = "AND start <= ? AND end >= ?"
            params.extend([int(end), int(start)])
        if table_name in ENHANCER_CANDIDATE_TABLES:
            placeholders = ', '.join(['?'] * len(OFC_RELEVANT_ENHANCER_CELLS))
            where_extra = f"{where_extra} AND cell IN ({placeholders})"
            params.extend(OFC_RELEVANT_ENHANCER_CELLS)

        cursor.execute(f"""
            SELECT cell, chrom, start, "end", length, score, gene, {peak_col} AS peak_value
            FROM {table_name}
            WHERE chrom = ? {where_extra}
            ORDER BY start
        """, params)

        rows = cursor.fetchall()
        conn.close()

        features = []
        for row in rows:
            description = (
                f"Cell: {row['cell']}<br>"
                f"Gene: {row['gene'] or 'N/A'}<br>"
                f"Score: {row['score']}<br>"
                f"Length: {row['length']} bp"
            )
            peak_val = row['peak_value']
            if peak_val:
                description += f"<br>Peak: {peak_val}"

            features.append({
                'chr': row['chrom'],
                'start': row['start'],
                'end': row['end'],
                'name': f"{row['gene'] or row['cell']}",
                'description': description,
            })

        return {
            'name': display_name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'SQUISHED',
            'color': color,
            'height': 50,
        }

    except Exception as e:
        print(f"Error creating {table_name} track: {e}")
        return {
            'name': display_name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': [],
            'displayMode': 'SQUISHED',
            'color': color,
            'height': 50,
        }


def create_noccl_ccre_track(chrom, start=None, end=None, max_features=10000):
    """Create an IGV annotation track from imported no-cleft embryo cCRE BED rows."""
    display_name = 'No-cleft Embryo cCREs'
    color = '#7C3AED'

    def format_targets(targets, per_line=2):
        values = [value.strip() for value in str(targets or '').split(',') if value.strip()]
        if not values:
            return 'N/A'
        lines = [', '.join(values[index:index + per_line]) for index in range(0, len(values), per_line)]
        return '<br>'.join(lines)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'noccl_cCREs'")
        if not cursor.fetchone():
            conn.close()
            return {
                'name': f'{display_name} (not imported)',
                'sourceType': 'annotation',
                'format': 'bed',
                'features': [],
                'displayMode': 'SQUISHED',
                'color': color,
                'height': 50,
            }

        params = [chrom]
        where_extra = ""
        if start is not None and end is not None:
            where_extra = 'AND start <= ? AND "end" >= ?'
            params.extend([int(end), int(start)])

        cursor.execute(f"""
            SELECT chrom, start, "end", ccre_id, score, strand, ccre_type, source, item_rgb, targets
            FROM noccl_cCREs
            WHERE chrom = ? {where_extra}
            ORDER BY start
            LIMIT ?
        """, [*params, int(max_features)])
        rows = cursor.fetchall()
        conn.close()

        features = []
        for row in rows:
            description = (
                f"cCRE ID: {row['ccre_id']}<br>"
                f"Type: {row['ccre_type'] or 'N/A'}<br>"
                f"Source: {row['source'] or 'N/A'}<br>"
                f"Score: {row['score']}<br>"
                f"RGB: {row['item_rgb'] or 'N/A'}"
            )
            features.append({
                'chr': row['chrom'],
                'start': row['start'],
                'end': row['end'],
                'name': row['ccre_id'],
                'description': description,
                'targets': format_targets(row['targets']),
            })

        suffix = '' if len(features) < max_features else f' (first {max_features:,})'
        return {
            'name': f'{display_name}{suffix}',
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'SQUISHED',
            'color': color,
            'height': 70,
        }

    except Exception as e:
        print(f"Error creating noccl_cCREs track: {e}")
        return {
            'name': display_name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': [],
            'displayMode': 'SQUISHED',
            'color': color,
            'height': 50,
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

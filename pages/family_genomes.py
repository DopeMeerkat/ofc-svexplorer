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
from urllib.parse import parse_qs
from dash.exceptions import PreventUpdate

from app import app, HOSTED_GENOME_DICT, build_local_igv_reference
from components.family_gene_search import create_family_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import (
    get_family_ids, get_family_members, get_gene_by_id, 
    create_family_tracks, get_tracks_for_genome, DB_PATH,
    get_families_by_sv, get_child_sv_data
)
from pages.population_svs import create_background_track


OFC_RELEVANT_ENHANCER_CELLS = ('MESENCHYMAL', 'NEURALCREST')
ENHANCER_CANDIDATE_TABLES = {'active_enhancer_candidates'}

def _parse_search(search):
    """Parse family + chromosome/start/end coordinates from a URL query string."""
    query = parse_qs((search or '').lstrip('?'))
    family = (query.get('family') or [''])[0].strip()
    chrom = (query.get('chrom') or [''])[0].strip()
    start = (query.get('start') or [''])[0].strip()
    end = (query.get('end') or [''])[0].strip()
    locus = None
    if chrom and start and end:
        try:
            locus = {
                'id': f'{chrom}:{start}-{end}',
                'Gene': f'{chrom}:{start}-{end}',
                'type': 'locus',
                'chrom': chrom,
                'x1': int(start),
                'x2': int(end),
            }
        except ValueError:
            locus = None
    return family, locus

def page_layout(selected_gene=None, search=None):
    """
    Create the family genomes browser page layout
    
    Args:
        selected_gene (dict, optional): Selected gene information
        search (str, optional): URL query string to prefill family and locus
    
    Returns:
        dash.html.Div: The family genomes browser page layout
    """
    # Get the list of available family IDs for the dropdown
    family_ids = get_family_ids()
    family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in family_ids]
    
    # If no families are found, provide a default empty option
    if not family_dropdown_options:
        family_dropdown_options = [{'label': 'No families available', 'value': ''}]
    
    # Parse URL query for family/locus prefill
    url_family, url_locus = _parse_search(search)
    if url_locus:
        selected_gene = url_locus
    family_value = url_family if url_family in family_ids else (family_ids[0] if family_ids else '')
    auto_load = 1 if (url_family or url_locus) else 0
    
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
                        value=family_value,
                        style={'marginBottom': '20px'}
                    ),
                    
                    # Step 3: Search Genes
                    html.H3('3. Search Genes', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    # Gene search component
                    create_family_gene_search(),
                    
                    # Step 4: Load IGV Browser
                    html.H3('4. Load IGV Browser', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                    html.H4('Optional Overlap Tracks', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '16px'}),
                    html.P('These tracks load only entries overlapping the active searched gene or SV interval.', style={'fontSize': '13px', 'marginBottom': '8px'}),
                    dcc.Checklist(
                        id='family-optional-tracks',
                        options=[
                            {'label': 'Exons', 'value': 'exons'},
                            # {'label': 'Poised enhancer candidates', 'value': 'poised_enhancer_candidates'},
                            {'label': 'Active enhancer candidates', 'value': 'active_enhancer_candidates'},
                            {'label': 'Promoter candidates', 'value': 'promoter_candidates'},
                            {'label': 'Insulator candidates', 'value': 'insulator_candidates'},
                            {'label': 'No-cleft embryo cCREs', 'value': 'noccl_cCREs'},
                        ],
                        value=[
                            'exons',
                            # 'poised_enhancer_candidates',
                            'active_enhancer_candidates',
                            'promoter_candidates',
                            'insulator_candidates',
                            'noccl_cCREs',
                        ],
                        style={'marginBottom': '16px'}
                    ),
                    html.H4('SV Source Tracks', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '16px'}),
                    html.P('Choose which structural variant sets to display for each family member. The background track shows reference population variants.', style={'fontSize': '13px', 'marginBottom': '8px'}),
                    dcc.Checklist(
                        id='family-sv-source',
                        options=[
                            {'label': 'Filtered SVs', 'value': 'filtered_svs'},
                            {'label': 'All SVs', 'value': 'phenotype_svs'},
                            {'label': 'Background', 'value': 'background_svs'},
                        ],
                        value=['phenotype_svs'],
                        style={'marginBottom': '16px'}
                    ),
                    html.Button(
                        'Load IGV Browser', 
                        id='load-igv-button', 
                        n_clicks=auto_load,
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
        dcc.Store(id='selected-gene-store', data=selected_gene),
        
        # Store for families found by SV search
        dcc.Store(id='sv-families-store', data=None),
        dcc.Store(id='selected-family-sv-store', data=None),
        dcc.Store(id='active-family-locus-store', data=None),
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
                pheno = parent.get('pheno', '')
                proband = parent.get('proband', 0)
                parent_list.append(html.Li(f"{gender} (ID: {parent['bam_id']}) — pheno: {pheno}, proband: {proband}"))
            info_elements.append(html.Ul(parent_list))
        
        # Display children
        if family_members['children']:
            info_elements.append(html.H5("Children:"))
            child_list = []
            for i, child in enumerate(family_members['children']):
                gender = 'Male' if child['gender'] == 'M' else 'Female'
                pheno = child.get('pheno', '')
                proband = child.get('proband', 0)
                affected = child.get('affected', 0)
                
                # Create a download button for each child
                child_info = html.Li([
                    f"{gender} (ID: {child['bam_id']}) — pheno: {pheno}, proband: {proband}, affected: {affected}",
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


def _get_sv_locus_by_id(sv_id):
    """Return aggregate coordinates for a searched SV ID without sample identifiers."""
    if not sv_id:
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, type, chrom, MIN(start) AS start, MAX("end") AS end, COUNT(DISTINCT sample) AS samples
            FROM phenotype_svs
            WHERE id = ?
            GROUP BY id, type, chrom
            ORDER BY samples DESC
            LIMIT 1
            """,
            (sv_id.strip(),),
        ).fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'type': row['type'],
            'chrom': row['chrom'],
            'start': int(row['start']),
            'end': int(row['end']),
            'samples': int(row['samples']),
        }
    finally:
        conn.close()


def _gene_locus_from_selection(selected_gene):
    """Return a generic locus dictionary from selected gene data."""
    if not isinstance(selected_gene, dict):
        return None
    chrom = selected_gene.get('chrom')
    start = selected_gene.get('x1')
    end = selected_gene.get('x2')
    if not chrom or start in (None, '') or end in (None, ''):
        return None
    return {
        'id': selected_gene.get('Gene') or selected_gene.get('id') or 'Selected gene',
        'type': selected_gene.get('type') or 'gene',
        'chrom': chrom,
        'start': int(start),
        'end': int(end),
    }


def _empty_track(name, color='#666666'):
    return {
        'name': name,
        'sourceType': 'annotation',
        'format': 'bed',
        'features': [],
        'displayMode': 'SQUISHED',
        'color': color,
        'height': 50,
    }


def _normalize_loci(loci):
    if not loci:
        return []
    if isinstance(loci, dict):
        loci = [loci]
    normalized = []
    seen = set()
    for locus in loci:
        if not isinstance(locus, dict):
            continue
        if not locus.get('chrom') or locus.get('start') is None or locus.get('end') is None:
            continue
        key = (locus.get('type'), locus.get('chrom'), int(locus.get('start')), int(locus.get('end')))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(locus)
    return normalized


def _expand_loci(loci, buffer_bp=100000):
    """Return copies of loci with start/end expanded by a buffer for overlap queries."""
    expanded = []
    for locus in _normalize_loci(loci):
        expanded.append({
            'id': locus.get('id'),
            'type': locus.get('type'),
            'chrom': locus['chrom'],
            'start': max(0, int(locus['start']) - buffer_bp),
            'end': int(locus['end']) + buffer_bp,
        })
    return expanded


def _format_grouped_exon_values(values, max_items=20):
    items = [item for item in str(values or '').split(',') if item]
    if not items:
        return 'N/A'
    shown = items[:max_items]
    suffix = '' if len(items) <= max_items else f"<br>...and {len(items) - max_items} more"
    return '<br>'.join(shown) + suffix


def _create_exon_overlap_track(loci):
    """Create an exon annotation track limited to selected intervals."""
    name = 'Exons'
    color = '#2E8B57'
    loci = _normalize_loci(loci)
    if not loci:
        return _empty_track(name, color)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = []
        for locus in loci:
            chrom = str(locus['chrom'])
            chrom_without_prefix = chrom[3:] if chrom.lower().startswith('chr') else chrom
            chrom_with_prefix = chrom if chrom.lower().startswith('chr') else f'chr{chrom}'
            rows.extend(conn.execute("""
                SELECT
                    gene_id,
                    chrom,
                    exon_start,
                    exon_end,
                    strand,
                    COUNT(*) AS transcript_count,
                    GROUP_CONCAT(DISTINCT transcript_id) AS transcript_ids,
                    GROUP_CONCAT(DISTINCT exon_number) AS exon_numbers,
                    GROUP_CONCAT(DISTINCT source) AS sources
                FROM exons
                WHERE chrom IN (?, ?)
                  AND exon_start <= ?
                  AND exon_end >= ?
                GROUP BY gene_id, chrom, exon_start, exon_end, strand
                ORDER BY exon_start
            """, (chrom_without_prefix, chrom_with_prefix, int(locus['end']), int(locus['start']))).fetchall())
        conn.close()

        features = []
        for row in rows:
            transcript_count = int(row['transcript_count'] or 0)
            transcript_label = 'transcript' if transcript_count == 1 else 'transcripts'
            features.append({
                'chr': row['chrom'],
                'start': row['exon_start'],
                'end': row['exon_end'],
                'name': f"{row['gene_id']} exon ({transcript_count} {transcript_label})",
                'description': (
                    f"Gene: {row['gene_id']}<br>"
                    f"Transcripts: {transcript_count}<br>"
                    f"Transcript IDs:<br>{_format_grouped_exon_values(row['transcript_ids'])}<br>"
                    f"Exon number(s):<br>{_format_grouped_exon_values(row['exon_numbers'])}<br>"
                    f"Strand: {row['strand'] or 'N/A'}<br>"
                    f"Source: {_format_grouped_exon_values(row['sources'])}"
                ),
                'strand': row['strand'],
            })
        return {
            'name': name,
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'SQUISHED',
            'color': color,
            'height': 80,
        }
    except Exception as e:
        print(f"Error creating exon overlap track: {e}")
        return _empty_track(name, color)


def _create_candidate_overlap_track(table_name, display_name, color, loci):
    """Create a candidate-region track limited to selected intervals."""
    loci = _normalize_loci(loci)
    if not loci:
        return _empty_track(display_name, color)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        peak_col = 'peak_bp_overlap' if table_name == 'promoter_candidates' else 'peak_bp_dist'
        rows = []
        for locus in loci:
            params = [locus['chrom'], locus['end'], locus['start']]
            cell_filter = ""
            if table_name in ENHANCER_CANDIDATE_TABLES:
                placeholders = ', '.join(['?'] * len(OFC_RELEVANT_ENHANCER_CELLS))
                cell_filter = f"AND cell IN ({placeholders})"
                params.extend(OFC_RELEVANT_ENHANCER_CELLS)
            rows.extend(cursor.execute(f"""
                SELECT cell, chrom, start, "end", length, score, gene, {peak_col} AS peak_value
                FROM {table_name}
                WHERE chrom = ? AND start <= ? AND "end" >= ? {cell_filter}
                ORDER BY start
            """, params).fetchall())
        conn.close()

        features = []
        for row in rows:
            description = (
                f"Cell: {row['cell']}<br>"
                f"Gene: {row['gene'] or 'N/A'}<br>"
                f"Score: {row['score']}<br>"
                f"Length: {row['length']} bp"
            )
            if row['peak_value']:
                description += f"<br>Peak: {row['peak_value']}"
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
        print(f"Error creating {table_name} overlap track: {e}")
        return _empty_track(display_name, color)


def _create_noccl_ccre_overlap_track(loci, max_features=10000):
    """Create no-cleft embryo cCRE track limited to selected intervals."""
    display_name = 'No-cleft Embryo cCREs'
    color = '#7C3AED'

    def format_targets(targets, per_line=2):
        values = [value.strip() for value in str(targets or '').split(',') if value.strip()]
        if not values:
            return 'N/A'
        lines = [', '.join(values[index:index + per_line]) for index in range(0, len(values), per_line)]
        return '<br>'.join(lines)

    loci = _normalize_loci(loci)
    if not loci:
        return _empty_track(display_name, color)
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'noccl_cCREs'")
        if not cursor.fetchone():
            conn.close()
            return _empty_track(f'{display_name} (not imported)', color)

        rows = []
        for locus in loci:
            rows.extend(cursor.execute("""
                SELECT chrom, start, "end", ccre_id, score, strand, ccre_type, source, item_rgb, targets
                FROM noccl_cCREs
                WHERE chrom = ? AND start <= ? AND "end" >= ?
                ORDER BY start
                LIMIT ?
            """, (locus['chrom'], locus['end'], locus['start'], int(max_features))).fetchall())
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
        print(f"Error creating noccl_cCREs overlap track: {e}")
        return _empty_track(display_name, color)


def _create_family_optional_overlap_tracks(optional_tracks, loci):
    """Build optional annotation tracks for the active gene and/or SV intervals."""
    loci = _normalize_loci(loci)
    if not optional_tracks or not loci:
        return []

    tracks = []
    if 'exons' in optional_tracks:
        tracks.append(_create_exon_overlap_track(loci))

    candidate_configs = [
        # ('poised_enhancer_candidates', 'Poised Enhancers', '#FF6B6B'),
        ('active_enhancer_candidates', 'Active Enhancers', '#4ECDC4'),
        ('promoter_candidates', 'Promoters', '#45B7D1'),
        ('insulator_candidates', 'Insulators', '#96CEB4'),
    ]
    for table_name, display_name, color in candidate_configs:
        if table_name in optional_tracks:
            tracks.append(_create_candidate_overlap_track(table_name, display_name, color, loci))

    if 'noccl_cCREs' in optional_tracks:
        tracks.append(_create_noccl_ccre_overlap_track(loci))

    return tracks


@callback(
    Output('active-family-locus-store', 'data'),
    [Input('selected-gene-store', 'data'),
     Input('selected-family-sv-store', 'data')],
    prevent_initial_call=True
)
def update_active_family_locus(selected_gene, selected_sv):
    """Track whether the latest selected interval came from gene or SV search."""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'selected-gene-store':
        gene_locus = _gene_locus_from_selection(selected_gene)
        return gene_locus

    if trigger_id == 'selected-family-sv-store':
        if isinstance(selected_sv, dict) and selected_sv.get('chrom') and selected_sv.get('start') is not None and selected_sv.get('end') is not None:
            return {
                'id': selected_sv.get('id') or selected_sv.get('sv_id') or 'Selected SV',
                'type': 'sv',
                'chrom': selected_sv['chrom'],
                'start': int(selected_sv['start']),
                'end': int(selected_sv['end']),
            }
        return None

    return no_update

@callback(
    [Output('family-igv-browser-container', 'children'),
     Output('family-info-container', 'style')],
    [Input('load-igv-button', 'n_clicks'),
     Input('family-select', 'value'),
     Input('family-igv-genome-select', 'value'),
     Input('selected-gene-store', 'data'),
     Input('family-optional-tracks', 'value'),
     Input('family-sv-source', 'value'),
     Input('selected-family-sv-store', 'data')]
)
def update_family_igv_browser(n_clicks, family_id, chrom, selected_gene, optional_tracks, sv_sources, selected_sv):
    """
    Update the IGV browser with family data
    
    Args:
        n_clicks (int): Number of times the load button has been clicked
        family_id (str): Selected family ID
        chrom (str): Selected chromosome
        selected_gene (dict): Selected gene information
        optional_tracks (list): Selected optional annotation tracks
        sv_sources (list): Selected SV source tables (filtered_svs, phenotype_svs, background_svs)
        
    Returns:
        tuple: (IGV browser component, family info visibility style)
    """
    if not n_clicks or not family_id:
        return no_update, {'display': 'none'}
    
    print(f"\n=== UPDATE FAMILY IGV BROWSER ===")
    print(f"Family ID: {family_id}")
    print(f"Chromosome: {chrom}")
    print(f"Selected gene: {selected_gene}")
    print(f"Selected SV: {selected_sv}")
    print(f"SV sources: {sv_sources}")
    
    try:
        # Gene search controls the viewport when present; SV-only loading keeps the existing behavior.
        locus = ""
        gene_locus = _gene_locus_from_selection(selected_gene)
        sv_locus = selected_sv if isinstance(selected_sv, dict) else None
        if sv_locus and sv_locus.get('chrom') and sv_locus.get('start') is not None and sv_locus.get('end') is not None:
            sv_locus = {
                'id': sv_locus.get('id') or sv_locus.get('sv_id') or 'Selected SV',
                'type': 'sv',
                'chrom': sv_locus['chrom'],
                'start': int(sv_locus['start']),
                'end': int(sv_locus['end']),
            }
        else:
            sv_locus = None

        viewport_locus = gene_locus or sv_locus
        if viewport_locus:
            chrom = viewport_locus['chrom']
            item_type = viewport_locus.get('type')
            buffer_bp = 50000 if item_type == 'locus' else (5000 if item_type == 'gene' else 1000)
            start = max(0, int(viewport_locus['start']) - buffer_bp)
            end = int(viewport_locus['end']) + buffer_bp
            locus = f"{chrom}:{start}-{end}"
            print(f"Setting IGV viewport to: {locus}")
        
        # Create family tracks with BAM files
        # First get the family members for this family ID
        family_members = get_family_members(family_id)

        if not family_members['parents'] and not family_members['children']:
            return html.Div(html.P("No data available for the selected family.", style={'color': 'red'})), {'display': 'block'}

        # Build one set of member tracks per selected SV source, plus the background track if requested.
        sv_sources = sv_sources or []
        source_labels = {
            'filtered_svs': 'Filtered',
            'phenotype_svs': 'All',
            'background_svs': 'Background',
        }
        family_tracks = []
        for source in sv_sources:
            if source == 'background_svs':
                if chrom:
                    family_tracks.append(create_background_track(chrom))
                continue
            label = source_labels.get(source, source)
            family_tracks.extend(create_family_tracks(family_members, sv_table=source, track_label=label))

        if not family_tracks:
            return html.Div(html.P("No data available for the selected family.", style={'color': 'red'})), {'display': 'block'}

        # Optional tracks can include both gene and SV intervals; IGV still jumps to the gene if present.
        # Annotation tracks load from a 100 kb buffer around the active intervals for flanking context.
        sv_tracks = get_tracks_for_genome(chrom)
        track_loci = _expand_loci([gene_locus, sv_locus], buffer_bp=100000)
        optional_overlap_tracks = _create_family_optional_overlap_tracks(optional_tracks, track_loci)
        
        # Combine tracks
        all_tracks = sv_tracks + optional_overlap_tracks + family_tracks
        
        # Set up locus for the IGV browser
        browser_locus = None
        if locus:
            browser_locus = locus
        elif chrom:
            browser_locus = chrom
        
        # Create the IGV browser component with direct properties
        igv_browser = dashbio.Igv(
            id='family-igv-browser',
            reference=build_local_igv_reference(chrom),
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
            reference=build_local_igv_reference(chrom),
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
     Output('family-select', 'value'),
     Output('selected-family-sv-store', 'data')],
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
            
        return no_update, None, family_dropdown_options, no_update, None
    
    # Get families with this SV
    sv_families = get_families_by_sv(sv_id)
    sv_locus = _get_sv_locus_by_id(sv_id)
    
    if not sv_families:
        # No families found with this SV
        message = html.Div([
            html.P(f"No families found with SV: {sv_id}", style={'color': 'red'})
        ])
        
        # Get all family IDs for the dropdown (reset to default)
        all_families = get_family_ids()
        family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in all_families]
        
        return message, None, family_dropdown_options, all_families[0] if all_families else '', sv_locus
    
    # Families found with this SV
    coordinate_text = ''
    if sv_locus:
        coordinate_text = f" Selected interval: {sv_locus['chrom']}:{sv_locus['start']:,}-{sv_locus['end']:,}."
    message = html.Div([
        html.P(f"Found {len(sv_families)} families with SV: {sv_id}", style={'color': 'green'}),
        html.P(f"Family dropdown has been updated with matching families.{coordinate_text}")
    ])
    
    # Create dropdown options for families with this SV
    family_dropdown_options = [{'label': f'Family {family_id}', 'value': family_id} for family_id in sv_families]
    
    # Set the default selected value to the first family in the list
    default_family = sv_families[0] if sv_families else ''
    
    return message, sv_families, family_dropdown_options, default_family, sv_locus

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

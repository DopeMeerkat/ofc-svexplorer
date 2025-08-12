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
        # Connect to database
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
                    print(f"\n===== CSV FILE INFO =====")
                    print(f"CSV file exists at: {csv_path}")
                    # Check file size
                    import os
                    file_size = os.path.getsize(csv_path)
                    print(f"File size: {file_size} bytes")
                    
                    # Read and inspect the CSV file
                    print("Loading CSV data...")
                    
                    # Load the CSV with proper handling of missing values
                    df = pd.read_csv(csv_path)
                    print(f"CSV loaded successfully with {len(df)} rows and {len(df.columns)} columns")
                    print(f"CSV columns: {df.columns.tolist()}")
                    print(f"Number of unique SV IDs in CSV: {df['sv_id'].nunique()}")
                    print(f"First few SV IDs: {df['sv_id'].unique()[:5].tolist()}")
                    
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
                                # Additional detailed information
                                'samples': first_row.get('samples', ""),
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
                    
                    print(f"Loaded additional info for {len(sv_additional_info)} SVs from CSV")
                    
                    # Debug output for sv_additional_info
                    print("\n===== DEBUGGING SV ADDITIONAL INFO =====")
                    print(f"Total SVs with additional info: {len(sv_additional_info)}")
                    
                    # Print first 3 SVs as examples
                    sample_svs = list(sv_additional_info.keys())[:3]
                    for i, sv_id in enumerate(sample_svs):
                        info = sv_additional_info[sv_id]
                        print(f"\n--- SV #{i+1}: {sv_id} ---")
                        print(f"Gene Names: {info['gene_names']}")
                        print(f"SV Type: {info['sv_type']}")
                        print(f"Functional Likelihood: {info['functional_likelihood']}")
                        print(f"Frequency: {info['frequency']}")
                        print(f"Sample Count: {info['sample_count']}")
                        print(f"Regulatory Types: {info['regulatory_types']}")
                        print(f"Regulatory Cell Types: {info['regulatory_cell_types']}")
                        print(f"Expected Value: {info['expected_value']}")
                        print(f"Samples: {info['samples'][:100]}..." if len(info['samples']) > 100 else f"Samples: {info['samples']}")
                        print(f"Regulatory Scores: {info['regulatory_scores']}")
                        print(f"Regulatory IDs: {info['regulatory_ids']}")
                        print(f"Regulatory Details: {len(info['regulatory_details'])} entries")
                        if info['regulatory_details']:
                            print(f"  First Regulatory Detail: {info['regulatory_details'][0]}")
                    
                    print("\n===== END OF DEBUGGING INFO =====\n")
                    
                    # Optionally, save the full debug output to a file for detailed inspection
                    try:
                        import json
                        
                        # Convert sets to lists for JSON serialization
                        debug_info = {}
                        for sv_id, info in sv_additional_info.items():
                            debug_info[sv_id] = {k: (list(v) if isinstance(v, set) else v) for k, v in info.items()}
                        
                        with open('sv_debug_info.json', 'w') as f:
                            json.dump(debug_info, f, indent=2, default=str)
                        print("Detailed debug info written to sv_debug_info.json")
                    except Exception as e:
                        print(f"Could not save debug info to file: {e}")
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
        
        print(f"\n===== ID MATCHING DEBUG =====")
        print(f"SVs from database: {len(db_sv_ids)}")
        print(f"SVs from CSV: {len(csv_sv_ids)}")
        print(f"SVs in both: {len(common_ids)}")
        
        # Try to fix ID format mismatches if there are few or no matches
        if len(common_ids) < min(len(db_sv_ids), len(csv_sv_ids)) * 0.1:  # Less than 10% match
            print("WARNING: Very few matching IDs between database and CSV!")
            
            # Show sample IDs from both sources for comparison
            print("\nSample DB IDs:")
            db_samples = list(db_sv_ids)[:5]
            for sv_id in db_samples:
                print(f"  - {sv_id}")
            
            print("\nSample CSV IDs:")
            csv_samples = list(csv_sv_ids)[:5]
            for sv_id in csv_samples:
                print(f"  - {sv_id}")
            
            # Try to create a mapping between CSV and DB IDs
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
                        print(f"Found potential ID transformation: {len(matches)} matches")
                        # Apply this transformation to all CSV IDs
                        transformed_mapping = {}
                        for csv_id in csv_sv_ids:
                            transformed_id = transform(csv_id)
                            if transformed_id in db_sv_ids:
                                transformed_mapping[transformed_id] = sv_additional_info[csv_id]
                        
                        if transformed_mapping:
                            print(f"Created mapping for {len(transformed_mapping)} IDs")
                            sv_additional_info = transformed_mapping
                            break
        
        for sv_id, count in sv_counts.items():
            details = sv_details[sv_id]
            
            # Format population information for description
            pop_info_list = list(sv_pop_info.get(sv_id, set()))
            pop_str = f"{','.join(pop_info_list)}<br>" if pop_info_list else ""
            
            # Add additional information from CSV if available
            additional_info = ""
            if sv_id in sv_additional_info:
                print(f"Processing additional info for SV: {sv_id}")
                info = sv_additional_info[sv_id]
                
                # Format gene names
                gene_str = ", ".join(info['gene_names']) if info['gene_names'] else ""
                if gene_str:
                    additional_info += f"Associated genes: {gene_str}<br>"
                
                # Add functional and regulatory information
                if 'functional_likelihood' in info:
                    additional_info += f"Functional likelihood: {info['functional_likelihood']:.3f}<br>"
                if 'expected_value' in info:
                    additional_info += f"Expected value: {info['expected_value']:.3f}<br>"
                if 'frequency' in info:
                    additional_info += f"Frequency: {info['frequency']:.6f}<br>"
                if 'sample_count' in info and info['sample_count'] > 0:
                    additional_info += f"Sample count: {info['sample_count']}<br>"
                
                # Add regulatory information
                reg_types = ", ".join(info['regulatory_types']) if info['regulatory_types'] else ""
                if reg_types:
                    additional_info += f"Regulatory elements: {reg_types}<br>"
                
                cell_types = ", ".join(info['regulatory_cell_types']) if info['regulatory_cell_types'] else ""
                if cell_types:
                    additional_info += f"Cell types: {cell_types}<br>"
                
                # Add regulatory scores by cell type
                if info.get('regulatory_scores') and len(info['regulatory_scores']) > 0:
                    additional_info += "<br><b>Regulatory scores by cell type:</b><br>"
                    for cell_type, score in info['regulatory_scores'].items():
                        if cell_type:  # Ensure cell type is not empty
                            additional_info += f"- {cell_type}: {score:.3f}<br>"
                
                # Add sample information
                if info.get('samples'):
                    sample_list = info['samples'].split(',')
                    sample_list = [s.strip() for s in sample_list if s.strip()]  # Clean up empty entries
                    if sample_list:
                        if len(sample_list) <= 5:
                            additional_info += f"<br><b>Samples:</b> {', '.join(sample_list)}<br>"
                        else:
                            # Show first 5 samples and count
                            additional_info += f"<br><b>Samples:</b> {', '.join(sample_list[:5])}... (+{len(sample_list)-5} more)<br>"
                
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
            
            # Create the description with both standard and additional info
            description = f"<b>Basic Information:</b><br>"
            description += f"Type: {details['type']}<br>"
            description += f"Size: {details['end'] - details['start']} bp<br>"
            description += f"Count: {count}<br>"
            
            # Add population information if available
            if pop_str:
                description += f"<br><b>Population Information:</b><br>{pop_str}"
            
            # Add the additional info if available
            if additional_info:
                description += f"<br><b>Extended Information:</b><br>{additional_info}"
                print(f"Added extended information to SV: {sv_id}, info length: {len(additional_info)}")
            else:
                print(f"No extended information available for SV: {sv_id}")
            
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

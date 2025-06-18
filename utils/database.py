"""
Database utilities for the UCONN OFC SV Browser application.
This module handles all database connections and queries.
"""

import sqlite3
import os.path
import pandas as pd

# Database path
DB_PATH = '/data/cellvar.db/cellvar.db'

def load_genomes_from_db(db_path=DB_PATH):
    """
    Load available chromosomes from the database
    
    Args:
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of dictionaries with chromosome values and labels
    """
    if not os.path.exists(db_path):
        print(f"Warning: Database file {db_path} not found")
        return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]  # Default fallback
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Connected to database")
        
        # Get unique chromosomes from the genes table
        cursor.execute("SELECT DISTINCT chrom FROM genes ORDER BY chrom")
        chromosomes = cursor.fetchall()
        
        # Format results for Dash dropdown
        genome_options = [{'value': chrom[0], 'label': f"Chromosome {chrom[0]}"} for chrom in chromosomes]
        
        conn.close()
        
        # If no chromosomes found in the database, provide defaults
        if not genome_options:
            print("No chromosomes found in database, using defaults")
            return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]
        
        return genome_options
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]

def check_database_connection(db_path=DB_PATH):
    """
    Check if database connection is working
    
    Args:
        db_path (str): Path to the SQLite database
        
    Returns:
        bool: True if connection works, False otherwise
    """
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.cursor()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return False

def get_tracks_for_genome(chrom, db_path=DB_PATH):
    """
    Get gene tracks for a specific chromosome from database
    
    Args:
        chrom (str): Chromosome identifier
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of track objects for the IGV browser
    """
    tracks = []
    if not os.path.exists(db_path):
        return tracks
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query genes for the selected chromosome
        cursor.execute("""
            SELECT id, chrom, x1, x2, strand 
            FROM genes 
            WHERE chrom = ?
            ORDER BY x1
        """, (chrom,))
        
        genes = cursor.fetchall()
        conn.close()
        
        # Convert genes to BED format for IGV
        bed_content = "\n".join([f"{g[1]}\t{g[2]}\t{g[3]}\t{g[0]}\t.\t{g[4]}" for g in genes])
        
        if bed_content:
            tracks.append({
                'name': f'Genes ({chrom})',
                'url': 'data:application/bed,' + bed_content,
                'format': 'bed',
                'displayMode': 'EXPANDED'
            })
            
        return tracks
        
    except sqlite3.Error as e:
        print(f"Database error when fetching genes: {e}")
        return []

def check_database_connection(db_path=DB_PATH):
    """
    Check connection to database and return status component
    
    Args:
        db_path (str): Path to the SQLite database
        
    Returns:
        dash.html.Div: Component displaying database status
    """
    from dash import html
    from utils.styling import UCONN_NAVY
    
    if not os.path.exists(db_path):
        return html.Div(f"Database not found: {db_path}", style={'color': 'red'})
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if genes table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='genes'")
        table_exists = cursor.fetchone()
        
        # Count genes
        gene_count = 0
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM genes")
            gene_count = cursor.fetchone()[0]
        
        conn.close()
        
        if not table_exists:
            return html.Div("Database exists but missing 'genes' table", style={'color': 'orange'})
        
        return html.Div([
            html.Span("Database connected. ", style={'fontWeight': 'bold'}),
            html.Span(f"Genes: {gene_count}", style={'marginLeft': '5px'})
        ], style={'display': 'flex', 'alignItems': 'center'})
        
    except sqlite3.Error as e:
        return html.Div(f"Database error: {e}", style={'color': 'red'})

def search_genes(search_term, db_path=DB_PATH):
    """
    Search for genes in the database that match the search term
    
    Args:
        search_term (str): Gene name or pattern to search for
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of dictionaries with gene details
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        return []
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Search for genes with a LIKE query to match partial names too
        cursor.execute("""
            SELECT id, chrom, x1, x2, length, strand 
            FROM genes 
            WHERE id LIKE ? 
            ORDER BY id
            LIMIT 30
        """, (f'%{search_term}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        # Format results as a list of dictionaries
        genes = []
        for row in results:
            genes.append({
                'id': row[0],
                'chrom': row[1],
                'x1': row[2],
                'x2': row[3],
                'length': row[4],
                'strand': row[5],
                'label': f"{row[0]} ({row[1]}:{row[2]}-{row[3]})"  # Format for display
            })
            
        return genes
    except sqlite3.Error as e:
        print(f"Database error when searching genes: {e}")
        return []

def get_gene_by_id(gene_id, db_path=DB_PATH):
    """
    Get gene details by ID
    
    Args:
        gene_id (str): Gene ID to look up
        db_path (str): Path to the SQLite database
        
    Returns:
        dict: Dictionary with gene details or None if not found
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        return None
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, chrom, x1, x2, length, strand FROM genes WHERE id = ?", (gene_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"No gene found with ID: {gene_id}")
            return None
            
        return {
            'id': result[0], 
            'chrom': result[1], 
            'x1': result[2], 
            'x2': result[3], 
            'length': result[4], 
            'strand': result[5]
        }
    except sqlite3.Error as e:
        print(f"Database error when fetching gene: {e}")
        return None

def load_table_data(csv_path='assets/table.csv'):
    """
    Load data from CSV file for the data table
    
    Args:
        csv_path (str): Path to CSV file
        
    Returns:
        pandas.DataFrame: DataFrame with table data
    """
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        print(f"Error loading table: {e}")
        return pd.DataFrame()

def get_gene_network_data(gene_id=None, db_path=DB_PATH):
    """
    Get gene network data for visualization
    
    Args:
        gene_id (str, optional): Gene ID to center the network on
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of nodes and edges for network visualization
    """
    # This is a placeholder implementation that would be replaced
    # with actual database queries in a production environment
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # If a specific gene is provided, build a network around it
        if gene_id:
            # Query would get this gene and related genes
            # For now, returning placeholder data
            return [
                # Nodes
                {'data': {'id': gene_id, 'label': f'Gene {gene_id}'}},
                {'data': {'id': f'{gene_id}_rel1', 'label': f'Related 1'}},
                {'data': {'id': f'{gene_id}_rel2', 'label': f'Related 2'}},
                {'data': {'id': f'{gene_id}_rel3', 'label': f'Related 3'}},
                
                # Edges
                {'data': {'source': gene_id, 'target': f'{gene_id}_rel1'}},
                {'data': {'source': gene_id, 'target': f'{gene_id}_rel2'}},
                {'data': {'source': gene_id, 'target': f'{gene_id}_rel3'}},
                {'data': {'source': f'{gene_id}_rel1', 'target': f'{gene_id}_rel2'}}
            ]
        
        # If no specific gene, return a sample network of top genes
        # In a real implementation, this would query the most relevant genes
        cursor.execute("SELECT gene, Gene FROM genes LIMIT 10")
        genes = cursor.fetchall()
        
        nodes = [{'data': {'id': row[0], 'label': row[1]}} for row in genes]
        
        # Create some sample edges between these genes
        # In a real implementation, these would be based on actual relationships
        edges = []
        for i in range(len(genes) - 1):
            edges.append({'data': {'source': genes[i][0], 'target': genes[i+1][0]}})
            
            # Add some cross connections for a more interesting network
            if i < len(genes) - 2:
                edges.append({'data': {'source': genes[i][0], 'target': genes[i+2][0]}})
        
        conn.close()
        return nodes + edges
        
    except sqlite3.Error as e:
        print(f"Database error in get_gene_network_data: {e}")
        # Return a minimal default network
        return [
            {'data': {'id': 'sample1', 'label': 'Sample 1'}},
            {'data': {'id': 'sample2', 'label': 'Sample 2'}},
            {'data': {'source': 'sample1', 'target': 'sample2'}}
        ]

def get_circos_data(data_type, chromosomes, db_path=DB_PATH):
    """
    Get data for Circos visualization
    
    Args:
        data_type (str): Type of data to visualize ('gene_density', 'structural_variations', 
                        'sample_comparison', 'gene_interactions')
        chromosomes (list): List of chromosomes to include
        db_path (str): Path to the SQLite database
        
    Returns:
        tuple: (layout_data, track_data) for Circos visualization
    """
    from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE
    import numpy as np
    from utils.circos_helpers import (
        generate_highlights_for_dense_regions,
        generate_notable_sv_labels,
        generate_interaction_heatmap
    )
    
    # Generate layout data for selected chromosomes
    layout_data = []
    print(f"\n===== CIRCOS DATA GENERATION DEBUG =====")
    print(f"Generating layout data for chromosomes: {chromosomes}")
    print(f"Number of chromosomes: {len(chromosomes)}")
    print(f"Chromosome types: {[type(c).__name__ for c in chromosomes]}")
    
    # Sort chromosomes for better visualization
    sorted_chromosomes = sorted(chromosomes, key=lambda c: 
                               int(c.replace('chr', '')) if c.replace('chr', '').isdigit() 
                               else (99 if c.replace('chr', '').upper() == 'X' 
                                    else (100 if c.replace('chr', '').upper() == 'Y' 
                                         else 101)))
    
    for i, chrom in enumerate(sorted_chromosomes):
        size = get_chromosome_size(chrom)
        print(f"  - Chromosome {i+1}: '{chrom}', Size: {size}")
        
        # Format a more descriptive label - strip 'chr' prefix if present for display
        display_label = chrom
        if display_label.lower().startswith('chr'):
            display_label = display_label[3:]
            
        layout_data.append({
            'id': chrom,
            'label': f'Chr {display_label}',
            'color': UCONN_NAVY,
            'len': size,
            'labelLink': {
                'url': f'#chr{display_label}',  # Anchor link to allow jumping to specific chromosomes
                'target': '_self'
            },
            'labelBackgroundColor': '#f8f9fa',
            'labelTextAlign': 'center',
            'highlight': True,  # Enable highlighting on mouse hover
            'highlightColor': UCONN_LIGHT_BLUE,
            'highlightOpacity': 0.3
        })
    
    # Generate track data based on the selected data type
    if data_type == 'gene_density':
        # Generate histogram data for gene density
        histogram_data = generate_gene_density_data(chromosomes, db_path)
        
        # Only use one track type to avoid duplicate tracks
        tracks = [
            {
                'type': 'HISTOGRAM',
                'data': histogram_data,
                'config': {
                    'innerRadius': 0.65,
                    'outerRadius': 0.85,
                    'color': UCONN_LIGHT_BLUE,
                    'fillColor': UCONN_LIGHT_BLUE,
                    'fillOpacity': 0.5,
                    'strokeWidth': 1,
                    'strokeColor': UCONN_NAVY,
                    'axes': {
                        'display': True,
                        'color': '#CCCCCC',
                        'thickness': 0.5,
                        'values': [0, 25, 50, 75, 100]
                    },
                    'tooltipContent': {
                        'source': 'Source Gene',
                        'target': 'Target Gene',
                        'position': 'Position',
                        'value': 'Value'
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
        
    elif data_type == 'structural_variations':
        # Generate chord data for structural variations
        chord_data = generate_sv_data(chromosomes, db_path)
        
        # Only use one track type to avoid duplicate tracks
        tracks = [
            {
                'type': 'CHORDS',
                'data': chord_data,
                'config': {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7,
                    'thickness': 4,  # Increase chord thickness for better visibility
                    'tooltipContent': {
                        'source_gene': 'source_gene',
                        'target_gene': 'target_gene'
                    }
                }
            }
        ]
    
    elif data_type == 'gene_interactions':
        # Generate chord data for gene interactions from table.csv
        chord_data = generate_gene_interactions_data(chromosomes, db_path)
        
        # Only use one track type to avoid duplicate tracks
        tracks = [
            {
                'type': 'CHORDS',
                'data': chord_data,
                'config': {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7,
                    'thickness': 4,  # Increase chord thickness for better visibility
                    'tooltipContent': {
                        'source_gene': 'Gene',
                        'target_gene': 'Interacts with',
                        'source': {'id': 'Source Location', 'start': 'Start', 'end': 'End'},
                        'target': {'id': 'Target Location', 'start': 'Start', 'end': 'End'}
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
        
    elif data_type == 'sample_comparison':
        # Generate both histogram and chord data for sample comparison
        histogram_data = generate_gene_density_data(chromosomes, db_path)
        chord_data = generate_sv_data(chromosomes, db_path)
        
        # Generate highlight regions for key areas of interest
        highlight_data = []
        # Add some key regions of interest
        for chrom in sorted_chromosomes:
            size = get_chromosome_size(chrom)
            # Add a random region of interest in each chromosome
            start_pos = np.random.randint(0, size - size//5)
            end_pos = start_pos + np.random.randint(size//10, size//5)
            highlight_data.append({
                'block_id': chrom,
                'start': start_pos,
                'end': end_pos,
                'color': f'rgba({np.random.randint(100, 255)}, {np.random.randint(100, 255)}, {np.random.randint(100, 255)}, 0.3)'
            })
        
        tracks = [
            {
                'type': 'HIGHLIGHT',
                'data': highlight_data,
                'config': {
                    'innerRadius': 0.95,
                    'outerRadius': 1,
                    'opacity': 0.8,
                    'tooltipContent': {
                        'block_id': 'Region',
                        'start': 'Start',
                        'end': 'End'
                    }
                }
            },
            {
                'type': 'CHORDS',
                'data': chord_data,
                'config': {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7,
                    'thickness': 4,  # Increase chord thickness for better visibility
                    'tooltipContent': {
                        'source': 'source',
                        'target': 'target',
                        'source_gene': 'Source Gene',
                        'target_gene': 'Target Gene'
                    },
                }
            },
            {
                'type': 'HISTOGRAM',
                'data': histogram_data,
                'config': {
                    'innerRadius': 0.65,
                    'outerRadius': 0.85,
                    'color': UCONN_LIGHT_BLUE,
                    'fillColor': UCONN_LIGHT_BLUE,
                    'fillOpacity': 0.5,
                    'strokeWidth': 1,
                    'strokeColor': UCONN_NAVY,
                    'axes': {
                        'display': True,
                        'color': '#CCCCCC',
                        'thickness': 0.5,
                        'values': [0, 25, 50, 75, 100]
                    },
                    'tooltipContent': {
                        'position': 'Position',
                        'value': 'Value'
                    }
                }
            }
        ]
    
    return layout_data, tracks

def generate_gene_density_data(chromosomes, db_path=DB_PATH):
    """
    Generate gene density data for selected chromosomes
    
    Args:
        chromosomes (list): List of chromosomes to include
        db_path (str): Path to the SQLite database
        
    Returns:
        list: Histogram data for Circos visualization
    """
    import numpy as np
    
    # This would ideally query the database for real gene density data
    # For now, generate simulated data
    histogram_data = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for chrom in chromosomes:
            # Query could look something like this in a real implementation:
            # cursor.execute("""
            #    SELECT COUNT(*), FLOOR(x1 / 1000000) * 1000000 as bin
            #    FROM genes 
            #    WHERE chrom = ? 
            #    GROUP BY bin
            #    ORDER BY bin
            # """, (chrom,))
            
            # For demonstration, generate simulated data
            size = get_chromosome_size(chrom)
            num_bins = 50
            bin_size = size // num_bins
            
            # Generate some random density values with higher values toward the middle
            for i in range(num_bins):
                position = i * bin_size
                # Create a bell curve pattern with some randomness
                center_factor = 1 - abs((i - num_bins/2) / (num_bins/2)) * 0.8
                value = center_factor * 100 + np.random.randint(0, 20)
                
                histogram_data.append({
                    'block_id': chrom,
                    'position': position,
                    'value': value
                })
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error in generate_gene_density_data: {e}")
    
    return histogram_data

def generate_sv_data(chromosomes, db_path=DB_PATH):
    """
    Generate structural variation data for selected chromosomes
    
    Args:
        chromosomes (list): List of chromosomes to include
        db_path (str): Path to the SQLite database
        
    Returns:
        list: Chord data for Circos visualization
    """
    from utils.styling import UCONN_LIGHT_BLUE
    import numpy as np
    
    # This would ideally query the database for real structural variation data
    # For now, generate simulated data
    chord_data = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # In a real implementation, we would query for actual SVs
        # For demonstration, generate random connections between chromosomes
        
        # Generate around 10-20 connections, but ensure they stay within selected chromosomes
        num_connections = min(len(chromosomes) * 3, 20)
        
        for _ in range(num_connections):
            # Select two random chromosomes
            if len(chromosomes) < 2:
                continue
                
            source_idx = np.random.randint(0, len(chromosomes))
            target_idx = np.random.randint(0, len(chromosomes))
            
            # Ensure source and target are different
            while target_idx == source_idx and len(chromosomes) > 1:
                target_idx = np.random.randint(0, len(chromosomes))
                
            source_chrom = chromosomes[source_idx]
            target_chrom = chromosomes[target_idx]
            
            source_size = get_chromosome_size(source_chrom)
            target_size = get_chromosome_size(target_chrom)
            
            # Generate random positions
            source_start = np.random.randint(0, source_size - 10000000)
            source_end = source_start + np.random.randint(1000000, 10000000)
            
            target_start = np.random.randint(0, target_size - 10000000)
            target_end = target_start + np.random.randint(1000000, 10000000)
            
            # Add the chord
            chord_data.append({
                'source': {'id': source_chrom, 'start': source_start, 'end': source_end}, 
                'target': {'id': target_chrom, 'start': target_start, 'end': target_end},
                'color': UCONN_LIGHT_BLUE,
                'value': np.random.randint(1, 10),  # Some measure of importance/frequency
                'source_gene': find_gene_at_location(source_chrom, source_start, source_end, cursor),
                'target_gene': find_gene_at_location(target_chrom, target_start, target_end, cursor)
            })
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error in generate_sv_data: {e}")
    
    return chord_data

def generate_gene_interactions_data(chromosomes, db_path=DB_PATH):
    """
    Generate gene interaction data for Circos visualization
    
    Args:
        chromosomes (list): List of chromosomes to include
        db_path (str): Path to the SQLite database
        
    Returns:
        list: Chord data for Circos visualization representing gene interactions
        
    Note:
        This function adds 2Mb padding to both start and end positions of gene
        interactions to make the chords more visible in the Circos plot.
    """
    from utils.styling import UCONN_LIGHT_BLUE, UCONN_NAVY
    import pandas as pd
    import csv
    
    chord_data = []
    
    try:
        # Load the interaction data from table.csv
        table_df = pd.read_csv('assets/table.csv')
        
        print("\n===== CIRCOS GENE INTERACTION DEBUGGING =====")
        print(f"Found {len(table_df)} rows in table.csv")
        print("Column headers:", table_df.columns.tolist())
        
        # Connect to the database to get gene coordinates
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Process each gene in the table
        for index, row in table_df.iterrows():
            gene_id = row['Gene']
            interaction_partners = row.get('Interaction_partner(s)', '')
            
            print(f"\nSource gene: {gene_id}")
            print(f"  Interaction partners: '{interaction_partners}'")
            
            # Skip if no interaction partners
            if pd.isna(interaction_partners) or interaction_partners == '-' or not interaction_partners:
                print(f"  No valid interaction partners for {gene_id}, skipping")
                continue
                
            # Get the coordinates of the source gene
            cursor.execute("""
                SELECT id, chrom, x1, x2 
                FROM genes 
                WHERE id = ?
            """, (gene_id,))
            source_gene = cursor.fetchone()
            
            if not source_gene:
                print(f"  WARNING: Source gene {gene_id} not found in database")
                continue
                
            source_chrom = source_gene[1]
            print(f"  Source gene {gene_id} found on chromosome {source_chrom}")
            
            # Skip if source chromosome not in selected chromosomes
            if source_chrom not in chromosomes:
                print(f"  Skipping {gene_id} - chromosome {source_chrom} not in selected chromosomes")
                continue
                
            # Process each interaction partner
            partners = [p.strip() for p in interaction_partners.split(',')]
            print(f"  Parsed partners: {partners}")
            
            for partner in partners:
                # Handle family names (e.g., "SMAD family")
                if "family" in partner.lower():
                    family_prefix = partner.split()[0]
                    print(f"  Processing family: {partner} (prefix: {family_prefix})")
                    
                    # Query for genes that start with this prefix
                    cursor.execute("""
                        SELECT id, chrom, x1, x2 
                        FROM genes 
                        WHERE id LIKE ?
                    """, (f"{family_prefix}%",))
                    family_genes = cursor.fetchall()
                    print(f"  Found {len(family_genes)} genes in the {family_prefix} family")
                    
                    for family_gene in family_genes:
                        target_chrom = family_gene[1];
                        
                        # Skip if target chromosome not in selected chromosomes
                        if target_chrom not in chromosomes:
                            continue
                            
                        # Add padding to make chords wider and more visible
                        padding = 2000000  # 2Mb padding on each side for better visibility
                        source_start_padded = max(0, source_gene[2] - padding)
                        source_end_padded = source_gene[3] + padding
                        target_start_padded = max(0, family_gene[2] - padding)
                        target_end_padded = family_gene[3] + padding
                        
                        # Add chord between source gene and this family member with gene names as labels
                        chord_data.append({
                            'source': {
                                'id': source_chrom, 
                                'start': source_start_padded, 
                                'end': source_end_padded,
                                'gene_id': source_gene[0]  # Add source gene ID
                            }, 
                            'target': {
                                'id': target_chrom, 
                                'start': target_start_padded, 
                                'end': target_end_padded,
                                'gene_id': family_gene[0]  # Add target gene ID
                            },
                            'color': UCONN_LIGHT_BLUE,
                            'value': 1,  # Interaction strength
                            'source_gene': source_gene[0],  # Source gene name
                            'target_gene': family_gene[0]   # Target gene name
                        })
                else:
                    # Direct partner lookup
                    print(f"  Looking up direct partner: {partner}")
                    cursor.execute("""
                        SELECT id, chrom, x1, x2 
                        FROM genes 
                        WHERE id = ?
                    """, (partner,))
                    target_gene = cursor.fetchone()
                    
                    if not target_gene:
                        print(f"  WARNING: Interaction partner {partner} for gene {gene_id} not found in database")
                        continue
                    
                    print(f"  Found partner gene {partner} on chromosome {target_gene[1]}")
                        
                    target_chrom = target_gene[1]
                    
                    # Skip if target chromosome not in selected chromosomes
                    if target_chrom not in chromosomes:
                        print(f"  Skipping {partner} - chromosome {target_chrom} not in selected chromosomes")
                        continue
                        
                    # Add padding to make chords wider and more visible
                    padding = 2000000  # 2Mb padding on each side for better visibility
                    source_start_padded = max(0, source_gene[2] - padding)
                    source_end_padded = source_gene[3] + padding
                    target_start_padded = max(0, target_gene[2] - padding)
                    target_end_padded = target_gene[3] + padding
                    
                    # Add chord between source and target gene with gene names as labels
                    chord_data.append({
                        'source': {
                            'id': source_chrom, 
                            'start': source_start_padded, 
                            'end': source_end_padded,
                            'gene_id': source_gene[0]  # Add source gene ID
                        }, 
                        'target': {
                            'id': target_chrom, 
                            'start': target_start_padded, 
                            'end': target_end_padded,
                            'gene_id': target_gene[0]  # Add target gene ID
                        },
                        'color': UCONN_NAVY,
                        'value': 1,  # Interaction strength
                        'source_gene': source_gene[0],  # Source gene name
                        'target_gene': target_gene[0]   # Target gene name
                    })
        
        conn.close()
        print(f"\nGenerated {len(chord_data)} gene interaction chords for Circos visualization")
        print("===== END CIRCOS GENE INTERACTION DEBUGGING =====\n")
        
    except Exception as e:
        print(f"Error generating gene interactions data: {e}")
        import traceback
        traceback.print_exc()
    
    return chord_data

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
        'Y': 57227415,
        'MT': 16569,
        'M': 16569
    }
    
    # Normalize chromosome name (strip "chr" prefix if present)
    chrom_normalized = chrom
    if isinstance(chrom, str):  # Ensure chrom is a string
        if chrom_normalized.lower().startswith('chr'):
            chrom_normalized = chrom_normalized[3:]
        
        print(f"Chromosome size lookup: '{chrom}' → normalized: '{chrom_normalized}'")
        
        # Try different formats to find a match
        formats_to_try = [
            chrom_normalized,                   # As is
            chrom_normalized.upper(),           # Uppercase
            chrom_normalized.lower(),           # Lowercase 
            chrom_normalized.strip(),           # Trimmed
            chrom_normalized.strip().upper(),   # Trimmed uppercase
            chrom_normalized.strip().lower()    # Trimmed lowercase
        ]
        
        for format_to_try in formats_to_try:
            if format_to_try in sizes:
                print(f"  Found match with format: '{format_to_try}'")
                return sizes[format_to_try]
        
        # Special handling for 'chrM' and 'chrMT' (mitochondrial)
        if chrom_normalized.upper() in ['M', 'MT']:
            print(f"  Matched as mitochondrial chromosome")
            return sizes['MT']
        
        print(f"  WARNING: No match found for chromosome '{chrom}' (normalized: '{chrom_normalized}')")
        print(f"  Attempted formats: {formats_to_try}")
        print(f"  Available keys in size dictionary: {list(sizes.keys())}")
    else:
        print(f"  ERROR: Chromosome is not a string: {chrom} (type: {type(chrom).__name__})")
    
    # Default size if not found
    return 100000000

def get_family_ids(db_path=DB_PATH):
    """
    Get a list of all family IDs from the phenotype table
    
    Args:
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of unique family IDs
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT family_id FROM phenotype ORDER BY family_id")
        family_ids = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return family_ids
    except sqlite3.Error as e:
        print(f"Database error in get_family_ids: {e}")
        return []

def get_family_members(family_id, db_path=DB_PATH):
    """
    Get family members for a specific family ID
    
    Args:
        family_id (str): The family ID to get members for
        db_path (str): Path to the SQLite database
        
    Returns:
        dict: Dictionary with keys 'parents' and 'children', each containing a list of member information
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT family_id, part_id, bio_id, bam_id, pheno, child, proband, affected, gender, race
            FROM phenotype
            WHERE family_id = ?
            ORDER BY child, gender
        """, (family_id,))
        
        columns = ['family_id', 'part_id', 'bio_id', 'bam_id', 'pheno', 'child', 'proband', 'affected', 'gender', 'race']
        family_members = {
            'parents': [],
            'children': []
        }
        
        for row in cursor.fetchall():
            member_info = dict(zip(columns, row))
            if member_info['child'] == 1:
                family_members['children'].append(member_info)
            else:
                family_members['parents'].append(member_info)
        
        conn.close()
        return family_members
    except sqlite3.Error as e:
        print(f"Database error in get_family_members: {e}")
        return {'parents': [], 'children': []}

def get_sample_svs(bam_id, db_path=DB_PATH):
    """
    Get structural variations for a specific sample
    
    Args:
        bam_id (str): The BAM ID (sample) to get SVs for
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of dictionaries containing SV information
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sample, id, type, chrom, start, "end", length, likelihood, methods, freq, pheno, gender
            FROM phenotype_svs
            WHERE sample = ?
            ORDER BY chrom, start
        """, (bam_id,))
        
        svs = []
        for row in cursor.fetchall():
            sv_info = dict(row)
            svs.append(sv_info)
        
        conn.close()
        return svs
    except sqlite3.Error as e:
        print(f"Database error in get_sample_svs: {e}")
        return []

def create_family_tracks(family_members, db_path=DB_PATH):
    """
    Create IGV tracks for each family member's structural variations
    
    Args:
        family_members (dict): Dictionary with family member information
        db_path (str): Path to the SQLite database
        
    Returns:
        list: List of track objects for the IGV browser
    """
    from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE
    
    tracks = []
    
    # Process parents
    for i, parent in enumerate(family_members['parents']):
        bam_id = parent['bam_id']
        gender = 'Male' if parent['gender'] == 'M' else 'Female'
        
        # Get SVs for this parent
        svs = get_sample_svs(bam_id)
        
        # Create track features
        features = []
        for sv in svs:
            feature = {
                'chr': sv['chrom'],
                'start': sv['start'],
                'end': sv['end'],
                'name': sv['id'],
                'type': sv['type']
            }
            features.append(feature)
        
        # Create the parent track
        parent_color = "#3366CC" if parent['gender'] == 'M' else "#CC3366"
        parent_track = {
            'name': f"Parent {i+1} ({gender})",
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'EXPANDED',
            'color': parent_color,
            'height': 50
        }
        
        tracks.append(parent_track)
    
    # Process children
    for i, child in enumerate(family_members['children']):
        bam_id = child['bam_id']
        gender = 'Male' if child['gender'] == 'M' else 'Female'
        proband_status = " - Proband" if child['proband'] == 1 else ""
        affected_status = " - Affected" if child['affected'] == 1 else ""
        
        # Get SVs for this child
        svs = get_sample_svs(bam_id)
        
        # Create track features
        features = []
        for sv in svs:
            feature = {
                'chr': sv['chrom'],
                'start': sv['start'],
                'end': sv['end'],
                'name': sv['id'],
                'type': sv['type']
            }
            features.append(feature)
        
        # Create the child track
        child_color = UCONN_NAVY if child['gender'] == 'M' else UCONN_LIGHT_BLUE
        child_track = {
            'name': f"Child {i+1} ({gender}{proband_status}{affected_status})",
            'sourceType': 'annotation',
            'format': 'bed',
            'features': features,
            'displayMode': 'EXPANDED',
            'color': child_color,
            'height': 50
        }
        
        tracks.append(child_track)
    
    return tracks

def find_gene_at_location(chrom, start, end, cursor):
    """
    Find a gene at a specific genomic location
    
    Args:
        chrom (str): Chromosome
        start (int): Start position
        end (int): End position
        cursor: Database cursor
        
    Returns:
        str: Gene ID if found, or a location descriptor if not
    """
    try:
        # Look up the gene in the database
        cursor.execute("""
            SELECT id FROM genes 
            WHERE chrom = ? AND 
                  ((x1 <= ? AND x2 >= ?) OR  -- Gene contains the region
                   (x1 >= ? AND x1 <= ?) OR  -- Region overlaps start of gene
                   (x2 >= ? AND x2 <= ?))    -- Region overlaps end of gene
            ORDER BY length DESC
            LIMIT 1
        """, (chrom, start, end, start, end, start, end))
        
        result = cursor.fetchone()
        if result:
            return result[0]  # Return the gene ID
        else:
            # If no gene is found, return a location descriptor
            return f"Chr{chrom}:{start:,}-{end:,}"
    except Exception as e:
        print(f"Error finding gene at location: {e}")
        return f"Chr{chrom}:{start:,}-{end:,}"

def get_sample_counts():
    """
    Get the count of samples for each track type (mother, father, child)
    
    Returns:
        dict: Dictionary with counts for each track type and background
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        counts = {}
        
        # Get parent and child counts from phenotype_svs joined with phenotype
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN p.child = 1 THEN 'child'
                    WHEN p.gender = 'F' THEN 'mother'
                    WHEN p.gender = 'M' THEN 'father'
                END as role,
                COUNT(DISTINCT s.sample) as count
            FROM phenotype_svs s
            JOIN phenotype p ON s.sample = p.bam_id
            GROUP BY 
                CASE 
                    WHEN p.child = 1 THEN 'child'
                    WHEN p.gender = 'F' THEN 'mother'
                    WHEN p.gender = 'M' THEN 'father'
                END
            HAVING role IS NOT NULL
        """)
        
        for role, count in cursor.fetchall():
            counts[role] = count
            
        # Get background sample count from background_svs
        cursor.execute("SELECT COUNT(DISTINCT sample) FROM background_svs")
        counts['background'] = cursor.fetchone()[0]
        
        # Ensure all expected keys exist
        for key in ['mother', 'father', 'child', 'background']:
            if key not in counts:
                counts[key] = 0
        
        conn.close()
        return counts
        
    except sqlite3.Error as e:
        print(f"Database error when getting sample counts: {e}")
        return {'mother': 0, 'father': 0, 'child': 0, 'background': 0}

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
        data_type (str): Type of data to visualize ('gene_density', 'structural_variations', 'sample_comparison')
        chromosomes (list): List of chromosomes to include
        db_path (str): Path to the SQLite database
        
    Returns:
        tuple: (layout_data, track_data) for Circos visualization
    """
    from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE
    import numpy as np
    
    # Generate layout data for selected chromosomes
    layout_data = []
    for chrom in chromosomes:
        size = get_chromosome_size(chrom)
        layout_data.append({
            'id': chrom,
            'label': f'Chr {chrom}',
            'color': UCONN_NAVY,
            'len': size
        })
    
    # Generate track data based on the selected data type
    if data_type == 'gene_density':
        # Generate histogram data for gene density
        histogram_data = generate_gene_density_data(chromosomes, db_path)
        
        tracks = [
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
        
    elif data_type == 'structural_variations':
        # Generate chord data for structural variations
        chord_data = generate_sv_data(chromosomes, db_path)
        
        tracks = [
            {
                'type': 'CHORDS',
                'data': chord_data,
                'config': {
                    'color': UCONN_LIGHT_BLUE,
                    'opacity': 0.7,
                    'tooltipContent': {'source': 'source', 'target': 'target'},
                }
            }
        ]
        
    elif data_type == 'sample_comparison':
        # Generate both histogram and chord data for sample comparison
        histogram_data = generate_gene_density_data(chromosomes, db_path)
        chord_data = generate_sv_data(chromosomes, db_path)
        
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
                'value': np.random.randint(1, 10)  # Some measure of importance/frequency
            })
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error in generate_sv_data: {e}")
    
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
        'Y': 57227415
    }
    
    return sizes.get(chrom, 100000000)  # Default size if not found

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

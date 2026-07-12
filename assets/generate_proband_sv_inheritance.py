#!/usr/bin/env python3
"""
Script to generate proband SV inheritance data and save it as a CSV file.
This script can be run independently of the web application.

The script filters structural variations (SVs) to only include those that are
present in the cellvar_ofc_children_table.csv file and adds the associated
gene information from that file.

Usage:
    python generate_proband_sv_inheritance.py

Output:
    Creates a CSV file with inheritance patterns of structural variations in probands,
    including the associated gene for each SV.
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
import csv

# Add the parent directory to the path so we can import from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.database import DB_PATH
except ImportError:
    # If running outside the project structure, use a default path
    DB_PATH = "/data/cellvar.db"
    print(f"Using default database path: {DB_PATH}")

def get_proband_sv_inheritance():
    """
    Get inheritance data for all unique SVs from probands, showing how many
    are inherited from father, mother, or both parents. Also includes the gene
    associated with each SV from the cellvar_ofc_children_table.csv file.
    
    Returns:
        tuple: (DataFrame with inheritance information, total proband count)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get total count of unique probands for percentage calculation
        total_query = """
        SELECT COUNT(DISTINCT bam_id) AS total_probands 
        FROM phenotype 
        WHERE proband = 1
        """
        total_df = pd.read_sql_query(total_query, conn)
        total_proband_count = total_df['total_probands'].iloc[0]
        print(f"Total proband count: {total_proband_count}")
        
        # Load the cellvar_ofc_children_table.csv to get gene information
        ofc_children_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cellvar_ofc_children_table.csv')
        gene_sv_mapping = {}
        print(f"Loading gene information from {ofc_children_path}")
        
        try:
            with open(ofc_children_path, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        gene = row[0]
                        sv_id = row[1]
                        if sv_id not in gene_sv_mapping:
                            gene_sv_mapping[sv_id] = gene
            print(f"Loaded gene information for {len(gene_sv_mapping)} SVs")
        except Exception as e:
            print(f"Error loading gene information: {e}")
            print("Continuing without gene information")
        
        # Get list of SVs from the cellvar_ofc_children_table.csv
        sv_ids_from_csv = list(gene_sv_mapping.keys())
        sv_ids_str = ', '.join(f"'{sv_id}'" for sv_id in sv_ids_from_csv)
        
        # Check if we have SVs to filter by
        sv_filter_clause = f"AND ps.id IN ({sv_ids_str})" if sv_ids_from_csv else ""
        
        # Complex query to find inheritance patterns for each SV
        query = f"""
        WITH 
        -- Get all SV IDs from probands with their family IDs
        proband_svs AS (
            SELECT 
                ps.id AS sv_id, 
                p.family_id,
                p.bam_id AS proband_bam_id
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.proband = 1
            {sv_filter_clause}
        ),
        
        -- For each proband SV, check if it exists in father and mother
        family_inheritance AS (
            SELECT 
                pb.sv_id,
                pb.family_id,
                -- Check if father has the same SV
                MAX(CASE WHEN 
                    EXISTS (
                        SELECT 1 FROM phenotype_svs ps
                        JOIN phenotype p ON ps.sample = p.bam_id
                        WHERE ps.id = pb.sv_id 
                        AND p.family_id = pb.family_id
                        AND p.gender = 'M' 
                        AND p.child = 0
                    ) THEN 1 ELSE 0 END) AS from_father,
                -- Check if mother has the same SV
                MAX(CASE WHEN 
                    EXISTS (
                        SELECT 1 FROM phenotype_svs ps
                        JOIN phenotype p ON ps.sample = p.bam_id
                        WHERE ps.id = pb.sv_id 
                        AND p.family_id = pb.family_id
                        AND p.gender = 'F' 
                        AND p.child = 0
                    ) THEN 1 ELSE 0 END) AS from_mother
            FROM proband_svs pb
            GROUP BY pb.sv_id, pb.family_id
        ),
        
        -- Aggregate inheritance stats for each SV
        inheritance_summary AS (
            SELECT 
                sv_id,
                COUNT(family_id) AS proband_count,
                SUM(from_father) AS father_count,
                SUM(from_mother) AS mother_count,
                SUM(CASE WHEN from_father = 1 AND from_mother = 1 THEN 1 ELSE 0 END) AS both_parents_count
            FROM family_inheritance
            GROUP BY sv_id
        )
        
        -- Get additional SV details and return final results
        SELECT 
            isum.sv_id,
            isum.proband_count,
            isum.father_count,
            isum.mother_count,
            isum.both_parents_count,
            -- Get first occurrence details for each SV
            (SELECT type FROM phenotype_svs WHERE id = isum.sv_id LIMIT 1) AS sv_type,
            (SELECT chrom FROM phenotype_svs WHERE id = isum.sv_id LIMIT 1) AS sv_chrom,
            (SELECT start FROM phenotype_svs WHERE id = isum.sv_id LIMIT 1) AS sv_start,
            (SELECT "end" FROM phenotype_svs WHERE id = isum.sv_id LIMIT 1) AS sv_end,
            (SELECT length FROM phenotype_svs WHERE id = isum.sv_id LIMIT 1) AS sv_length
        FROM inheritance_summary isum
        ORDER BY isum.proband_count DESC, isum.sv_id
        """
        
        print("Executing query to retrieve SV inheritance data...")
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Calculate percentage of probands with each SV
        df['proband_percentage'] = round((df['proband_count'] / total_proband_count * 100), 2)
        
        # Add gene information to the DataFrame
        df['gene'] = df['sv_id'].map(gene_sv_mapping)
        print(f"Added gene information to {df['gene'].notna().sum()} of {len(df)} SVs")
        
        return df, total_proband_count
        
    except Exception as e:
        print(f"Error getting proband SV inheritance: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), 0

def save_to_csv(df, output_file=None):
    """
    Save the DataFrame to a CSV file
    
    Args:
        df: pandas DataFrame to save
        output_file: path to output file, if None, a default name will be used
    """
    if df.empty:
        print("No data to save")
        return
        
    # Format the chromosome names nicely for the CSV
    df['sv_chrom'] = df['sv_chrom'].apply(lambda x: x.replace('chr', '') if x.startswith('chr') else x)
    
    # Rename columns for better readability in the CSV
    df = df.rename(columns={
        'sv_id': 'SV ID',
        'proband_count': 'Proband Count',
        'proband_percentage': 'Percentage of Probands (%)',
        'father_count': 'Inherited From Father',
        'mother_count': 'Inherited From Mother',
        'both_parents_count': 'Inherited From Both Parents',
        'sv_type': 'SV Type',
        'sv_chrom': 'Chromosome',
        'sv_start': 'Start Position',
        'sv_end': 'End Position',
        'sv_length': 'Length (bp)',
        'gene': 'Associated Gene'
    })
    
    # Generate default output filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"proband_sv_inheritance_{timestamp}.csv"
        # Make sure the path is absolute
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_file)
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Data saved to {output_file}")
    print(f"Total SVs: {len(df)}")

def main():
    """Main function to run the script"""
    print("Generating proband SV inheritance data...")
    df, total_proband_count = get_proband_sv_inheritance()
    
    if df.empty:
        print("No data retrieved, check database connection or query")
        return
        
    print(f"Retrieved data for {len(df)} structural variations across {total_proband_count} probands")
    
    # Save to CSV with default filename
    save_to_csv(df)

if __name__ == "__main__":
    main()

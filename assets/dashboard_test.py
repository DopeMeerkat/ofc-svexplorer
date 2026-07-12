#!/usr/bin/env python3
"""
Test script to verify that the dashboard can load the proband SV inheritance data from CSV.
This script simulates the dashboard's loading function.
"""

import os
import sys
import pandas as pd
import glob

# Add the parent directory to the path so we can import from pages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_proband_sv_inheritance():
    """
    Load proband SV inheritance data from the pre-generated CSV file
    
    Returns:
        tuple: (DataFrame with inheritance information, total proband count)
    """
    try:
        # Get the most recent CSV file from the assets directory
        csv_pattern = os.path.join(os.path.dirname(__file__), 'proband_sv_inheritance*.csv')
        csv_files = glob.glob(csv_pattern)
        
        if not csv_files:
            # Use the default file if no timestamped files are found
            default_csv = os.path.join(os.path.dirname(__file__), 'proband_sv_inheritance.csv')
            if os.path.exists(default_csv):
                csv_file = default_csv
            else:
                print("No proband SV inheritance CSV file found")
                return pd.DataFrame(), 0
        else:
            # Use the most recent file based on modification time
            csv_file = max(csv_files, key=os.path.getmtime)
            
        print(f"Loading proband SV inheritance data from {csv_file}")
        df = pd.read_csv(csv_file)
        
        # Rename columns back to the original names if they were renamed in the CSV
        column_mapping = {
            'SV ID': 'sv_id',
            'Proband Count': 'proband_count',
            'Percentage of Probands (%)': 'proband_percentage',
            'Inherited From Father': 'father_count',
            'Inherited From Mother': 'mother_count',
            'Inherited From Both Parents': 'both_parents_count',
            'SV Type': 'sv_type',
            'Chromosome': 'sv_chrom',
            'Start Position': 'sv_start',
            'End Position': 'sv_end',
            'Length (bp)': 'sv_length'
        }
        
        # Apply the column renaming if needed
        for csv_col, code_col in column_mapping.items():
            if csv_col in df.columns:
                df = df.rename(columns={csv_col: code_col})
                
        # Get the total proband count from the first row's percentage
        if 'proband_percentage' in df.columns and not df.empty:
            total_proband_count = int(round(df.iloc[0]['proband_count'] / df.iloc[0]['proband_percentage'] * 100, 0))
        else:
            # If percentage column doesn't exist or DataFrame is empty, use a default value
            print("Could not determine total proband count from percentage")
            total_proband_count = 242  # Default value
            
        return df, total_proband_count
        
    except Exception as e:
        print(f"Error loading proband SV inheritance data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), 0

def simulate_dashboard():
    """Simulate the dashboard's loading and processing of the data"""
    print("Simulating dashboard loading of proband SV inheritance data...")
    
    # Load the data
    df, total_proband_count = load_proband_sv_inheritance()
    
    if df.empty:
        print("No data available for proband SVs")
        return
    
    # Format the chromosome nicely
    df['sv_chrom'] = df['sv_chrom'].apply(lambda x: x.replace('chr', 'Chr ') if isinstance(x, str) and x.startswith('chr') else f"Chr {x}" if isinstance(x, str) else x)
    
    # Get basic stats
    print(f"\nTotal SVs found: {len(df)} unique structural variants among {total_proband_count} probands")
    print(f"Data preview (first 5 rows):")
    print(df.head())
    
    # Calculate statistics for the table
    print("\nCalculating percentages for interpretation...")
    df['from_father_pct'] = (df['father_count'] / df['proband_count'] * 100).round(1)
    df['from_mother_pct'] = (df['mother_count'] / df['proband_count'] * 100).round(1)
    df['from_both_pct'] = (df['both_parents_count'] / df['proband_count'] * 100).round(1)
    
    # Show sample output
    print("\nSample row with calculated percentages:")
    print(df.iloc[0][['sv_id', 'proband_count', 'proband_percentage', 'father_count', 'from_father_pct', 'mother_count', 'from_mother_pct', 'both_parents_count', 'from_both_pct']])
    
    print("\nSimulation completed successfully!")

if __name__ == "__main__":
    simulate_dashboard()

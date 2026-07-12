#!/usr/bin/env python3
"""
Test script to verify loading of the proband SV inheritance CSV file.
"""

import os
import sys
import pandas as pd
import glob

# Add the parent directory to the path so we can import from the project
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

def main():
    """Test loading the CSV file"""
    df, total_proband_count = load_proband_sv_inheritance()
    if not df.empty:
        print(f"Successfully loaded CSV with {len(df)} rows")
        print(f"Total proband count: {total_proband_count}")
        print("\nSample data:")
        print(df.head())
        print("\nColumn names:", df.columns.tolist())
    else:
        print("Failed to load CSV data")

if __name__ == "__main__":
    main()

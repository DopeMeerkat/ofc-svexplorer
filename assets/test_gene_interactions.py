#!/usr/bin/env python3
"""
Test script to verify gene interactions table with MSC and NCC columns
"""
import os
import sys
import pandas as pd

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import database functions
from utils.database import get_all_gene_interactions

def main():
    """Test gene interactions table with MSC and NCC columns"""
    print("Testing gene interactions table with MSC and NCC columns")
    
    # Load gene interactions
    interactions_df = get_all_gene_interactions()
    
    if interactions_df.empty:
        print("No gene interactions data available")
        return
        
    # Print data summary
    print(f"Total interactions: {len(interactions_df)}")
    
    # Filter to get unique source genes and their MSC/NCC scores
    unique_genes = {}
    for _, row in interactions_df.iterrows():
        gene = row['source_gene']
        if gene not in unique_genes:
            unique_genes[gene] = {
                'gene': gene, 
                'msc': row.get('source_MSC', None),
                'ncc': row.get('source_NCC', None)
            }
            
        gene = row['target_gene']
        if gene not in unique_genes:
            unique_genes[gene] = {
                'gene': gene, 
                'msc': row.get('target_MSC', None),
                'ncc': row.get('target_NCC', None)
            }
    
    # Convert to DataFrame for display
    gene_scores_df = pd.DataFrame(list(unique_genes.values()))
    
    # Sort by gene name
    gene_scores_df = gene_scores_df.sort_values(by='gene').reset_index(drop=True)
    
    # Print first few rows
    print("\nGenes with MSC and NCC scores:")
    for _, row in gene_scores_df.head(10).iterrows():
        print(f"Gene: {row['gene']}, MSC: {row['msc']}, NCC: {row['ncc']}")

if __name__ == "__main__":
    main()

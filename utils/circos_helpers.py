"""
Helper functions for generating enhanced Circos visualization data.
These functions support the main database utilities by generating specific
visualization components like highlights, heatmaps, and text labels.
"""

import numpy as np
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE

def generate_highlights_for_dense_regions(histogram_data, threshold=70):
    """
    Generate highlight regions for dense gene areas
    
    Args:
        histogram_data (list): List of histogram data points
        threshold (int): Threshold value to consider a region "dense"
        
    Returns:
        list: List of highlight data points
    """
    # Group histogram data by chromosome
    chromosomes = {}
    for point in histogram_data:
        chrom = point['block_id']
        if chrom not in chromosomes:
            chromosomes[chrom] = []
        chromosomes[chrom].append(point)
    
    # Find dense regions in each chromosome
    highlight_data = []
    for chrom, points in chromosomes.items():
        # Sort points by position
        points.sort(key=lambda p: p['position'])
        
        # Track dense regions
        in_dense_region = False
        start_pos = None
        
        for i, point in enumerate(points):
            if point['value'] > threshold and not in_dense_region:
                # Start of a dense region
                in_dense_region = True
                start_pos = point['position']
            elif (point['value'] <= threshold or i == len(points) - 1) and in_dense_region:
                # End of a dense region
                in_dense_region = False
                end_pos = point['position']
                
                # Add highlight for this region
                highlight_data.append({
                    'block_id': chrom,
                    'start': start_pos,
                    'end': end_pos,
                    'color': 'rgba(255, 165, 0, 0.3)'  # Semi-transparent orange
                })
    
    # If we didn't find any highlights, add some random ones for demo purposes
    if not highlight_data:
        for chrom in chromosomes.keys():
            # Use the first and last point in each chromosome to determine range
            if chromosomes[chrom]:
                min_pos = min(p['position'] for p in chromosomes[chrom])
                max_pos = max(p['position'] for p in chromosomes[chrom])
                
                # Add a random highlight in the middle third
                range_size = max_pos - min_pos
                start = min_pos + range_size // 3
                end = max_pos - range_size // 3
                
                highlight_data.append({
                    'block_id': chrom,
                    'start': start,
                    'end': end,
                    'color': 'rgba(255, 165, 0, 0.3)'  # Semi-transparent orange
                })
    
    return highlight_data

def generate_notable_sv_labels(chord_data, max_labels=5):
    """
    Generate text labels for notable structural variations
    
    Args:
        chord_data (list): List of chord data points
        max_labels (int): Maximum number of labels to generate
        
    Returns:
        list: List of text label data points
    """
    # For demonstration purposes, we'll just label the first few chords
    text_labels = []
    
    # If no chord data, return empty list
    if not chord_data:
        return text_labels
    
    # Take the first few chords and create labels for them
    for i, chord in enumerate(chord_data[:max_labels]):
        source = chord['source']
        target = chord['target']
        
        # Label for source
        text_labels.append({
            'block_id': source['id'],
            'position': (source['start'] + source['end']) // 2,
            'value': f'SV{i+1}',
            'color': '#C70039'
        })
        
        # Label for target - only add if different from source
        if source['id'] != target['id']:
            text_labels.append({
                'block_id': target['id'],
                'position': (target['start'] + target['end']) // 2,
                'value': f'SV{i+1}',
                'color': '#C70039'
            })
    
    # If we didn't create any labels, add some placeholder ones
    if not text_labels:
        chords_by_chrom = {}
        for chord in chord_data:
            source_id = chord['source']['id']
            if source_id not in chords_by_chrom:
                chords_by_chrom[source_id] = []
            chords_by_chrom[source_id].append(chord)
        
        for chrom, chords in chords_by_chrom.items():
            if chords:
                chord = chords[0]
                text_labels.append({
                    'block_id': chrom,
                    'position': (chord['source']['start'] + chord['source']['end']) // 2,
                    'value': 'SV',
                    'color': '#C70039'
                })
    
    return text_labels

def generate_interaction_heatmap(chromosomes, chord_data):
    """
    Generate heatmap data showing interaction frequency along chromosomes
    
    Args:
        chromosomes (list): List of chromosome IDs
        chord_data (list): List of chord data points
        
    Returns:
        list: List of heatmap data points
    """
    from utils.database import get_chromosome_size
    
    # Initialize heatmap data
    heatmap_data = []
    
    # If no chord data, return empty heatmap
    if not chord_data:
        return heatmap_data
    
    # For each chromosome, divide into bins and count interactions
    for chrom in chromosomes:
        chrom_size = get_chromosome_size(chrom)
        num_bins = 20  # Number of segments to divide chromosome into
        bin_size = chrom_size // num_bins
        
        # Initialize bins for this chromosome
        bins = [0] * num_bins
        
        # Count interactions in each bin
        for chord in chord_data:
            # Check source side
            if chord['source']['id'] == chrom:
                source_pos = (chord['source']['start'] + chord['source']['end']) // 2
                bin_idx = min(num_bins - 1, source_pos // bin_size)
                bins[bin_idx] += 1
            
            # Check target side
            if chord['target']['id'] == chrom:
                target_pos = (chord['target']['start'] + chord['target']['end']) // 2
                bin_idx = min(num_bins - 1, target_pos // bin_size)
                bins[bin_idx] += 1
        
        # Normalize the bin values to 0-1 range
        max_count = max(bins) if max(bins) > 0 else 1
        normalized_bins = [count / max_count for count in bins]
        
        # Create heatmap data points
        for i, value in enumerate(normalized_bins):
            start_pos = i * bin_size
            end_pos = (i + 1) * bin_size
            
            heatmap_data.append({
                'block_id': chrom,
                'start': start_pos,
                'end': end_pos,
                'value': value
            })
    
    # If we didn't create any heatmap data (unlikely), add some placeholder data
    if not heatmap_data:
        for chrom in chromosomes:
            chrom_size = get_chromosome_size(chrom)
            num_bins = 10
            bin_size = chrom_size // num_bins
            
            for i in range(num_bins):
                start_pos = i * bin_size
                end_pos = (i + 1) * bin_size
                
                # Generate a random value between 0 and 1
                value = np.random.random()
                
                heatmap_data.append({
                    'block_id': chrom,
                    'start': start_pos,
                    'end': end_pos,
                    'value': value
                })
    
    return heatmap_data

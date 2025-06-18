"""
OFC Visualization Uploader page - allows users to upload CSV files 
and displays information gain plots based on the ofc_vis.ipynb implementation.
"""

from dash import html, dcc, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import entropy as scipy_entropy
import base64
import io
import json

from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE

# Helper functions from the notebook
def entropy(column):
    """Calculate entropy of a column"""
    value, counts = np.unique(column, return_counts=True)
    probs = counts / len(column)
    return scipy_entropy(probs, base=2)

def information_gain(data, feature, target):
    """Calculate information gain for a feature"""
    original_entropy = entropy(data[target].values)
    total_rows = len(data)
    weighted_entropy = 0
    for value in data[feature].unique():
        subset = data[data[feature] == value]
        prob = len(subset) / total_rows
        weighted_entropy += prob * entropy(subset[target].values)
    return original_entropy - weighted_entropy

def conditional_entropy(data, feature, target):
    """Calculate conditional entropy for a feature"""
    total = len(data)
    ce = 0.0
    for value in data[feature].unique():
        subset = data[data[feature] == value]
        prob = len(subset) / total
        ce += prob * entropy(subset[target].values)
    return ce

def parse_contents(contents, filename):
    """Parse uploaded file contents and create visualizations"""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        if 'csv' in filename:
            # Read the CSV file
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            
            # Encode non-numeric categorical columns as integers
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col], _ = pd.factorize(df[col])
            
            # Get column headers from the DataFrame
            all_columns = df.columns.tolist()
            # Default to the third-to-last column as target (can be customized by user)
            if len(all_columns) >= 3:
                target_col = all_columns[-1]
            else:
                target_col = all_columns[-1]  # Use last column if not enough columns
                
            features = [col for col in all_columns if col != target_col]
            
            # Compute target entropy
            target_entropy = entropy(df[target_col].values)
            
            # Calculate information gain and conditional entropy for each feature
            ig_results = []
            for feature in features:
                ig = information_gain(df, feature, target_col)
                ce = conditional_entropy(df, feature, target_col)
                ig_results.append({
                    'Feature': feature,
                    'Score': ig,
                    'Conditional Entropy': ce
                })
            
            # Create a DataFrame for plotting
            ig_df = pd.DataFrame(ig_results)
            
            # Sort by descending information gain score
            ig_df = ig_df.sort_values('Score', ascending=False)
            
            # Create the bar plot using Plotly
            fig = px.bar(
                ig_df, 
                x='Score', 
                y='Feature',
                color='Score',
                color_continuous_scale='viridis',
                labels={'Score': 'Information Gain', 'Feature': 'Feature'},
                title=f'Information Gain between Features and Target ({target_col})',
                height=max(500, len(ig_df) * 50)  # Dynamic height based on number of features
            )
            
            # Improve spacing and layout
            fig.update_layout(
                bargap=0.3,        # Gap between bars
                bargroupgap=0.1,   # Gap between bar groups
                margin=dict(l=120, r=40, t=80, b=80),  # Margins
                xaxis=dict(
                    title_font=dict(size=14),
                    tickfont=dict(size=12),
                ),
                yaxis=dict(
                    title_font=dict(size=14),
                    tickfont=dict(size=12),
                    automargin=True  # Make sure y-axis labels aren't cut off
                )
            )
            
            # Add annotations for conditional entropy
            annotations = []
            for i, row in ig_df.iterrows():
                annotations.append({
                    'x': row['Score'],
                    'y': row['Feature'],
                    'text': f"H={row['Conditional Entropy']:.4f}",
                    'showarrow': False,
                    'xanchor': 'left',
                    'xshift': 15,  # Increased spacing
                    'font': {'color': 'black', 'size': 11},
                    'opacity': 0.8
                })
            
            fig.update_layout(annotations=annotations)
            
            # Add text with target entropy
            fig.add_annotation(
                x=0,
                y=-1.5,  # More space at the bottom
                text=f"Target Entropy ({target_col}): {target_entropy:.4f}",
                showarrow=False,
                xanchor='left',
                yanchor='top',
                font={'size': 14, 'color': UCONN_NAVY}
            )
            
            # Create a simple data table to show the first few rows
            preview_table = html.Div([
                html.H4('Data Preview'),
                html.P(f"Target column: {target_col}"),
                html.Div(
                    dcc.Markdown(df.head().to_markdown()),
                    style={'overflowX': 'auto', 'whiteSpace': 'nowrap', 'fontFamily': 'monospace'}
                )
            ], style={'marginBottom': '30px'})
            
            return html.Div([
                html.H5(f'File: {filename}', style={'marginTop': '20px', 'marginBottom': '15px'}),
                preview_table,
                dcc.Graph(figure=fig, style={'height': 'auto', 'marginTop': '20px', 'marginBottom': '40px'})
            ], style={'padding': '10px'})
            
        else:
            return html.Div([
                html.H5('Please upload a CSV file.')
            ])
    
    except Exception as e:
        print(e)
        return html.Div([
            html.H5('Error processing this file.'),
            html.P(str(e))
        ])

def page_layout():
    """Create the visualization uploader page layout"""
    return html.Div([
        html.H2('OFC Visualization Uploader', style={'color': UCONN_NAVY, 'marginBottom': '20px'}),
        html.P('Upload CSV files to visualize information gain and entropy metrics for structural variations.', 
               style={'fontSize': '16px', 'lineHeight': '1.5', 'marginBottom': '25px'}),
        
        # Instructions panel
        html.Div([
            html.H4('Instructions', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.Ul([
                html.Li('Upload a CSV file with feature columns and at least one target column', 
                        style={'marginBottom': '10px'}),
                html.Li('By default, the third-to-last column will be used as the target',
                        style={'marginBottom': '10px'}),
                html.Li('Categorical features will be automatically encoded',
                        style={'marginBottom': '10px'}),
                html.Li('The visualization will show information gain for each feature')
            ], style={'paddingLeft': '20px'}),
        ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '8px', 'marginBottom': '30px'}),
        
        # Upload component
        dcc.Upload(
            id='upload-csv',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select CSV File', style={'fontWeight': 'bold', 'color': UCONN_NAVY})
            ]),
            style={
                'width': '100%',
                'height': '70px',
                'lineHeight': '70px',
                'borderWidth': '2px',
                'borderStyle': 'dashed',
                'borderRadius': '8px',
                'textAlign': 'center',
                'margin': '20px 0 30px 0',
                'backgroundColor': '#fafafa',
                'cursor': 'pointer'
            },
            multiple=False
        ),
        
        # Output area for graph and data
        html.Div(id='output-visualization', style={'marginTop': '20px'})
    ], style={'padding': '25px', 'maxWidth': '1200px', 'margin': '0 auto'})

@callback(
    Output('output-visualization', 'children'),
    Input('upload-csv', 'contents'),
    State('upload-csv', 'filename')
)
def update_output(contents, filename):
    """Update the visualization based on uploaded file"""
    if contents is not None:
        return parse_contents(contents, filename)
    return html.Div()

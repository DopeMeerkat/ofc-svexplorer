"""
Image pages for the UCONN OFC SV Browser application.
"""

from dash import html
from utils.styling import UCONN_NAVY, uconn_styles

# Existing image pages are commented out and kept for reference
# def image1_page():
#     """
#     Create the first image page layout
#     
#     Returns:
#         dash.html.Div: Image page layout
#     """
#     return html.Div([
#         html.H2('Image 1', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
#         html.Img(
#             src='/assets/image1.png',
#             style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
#         ),
#     ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

# def image2_page():
#     """
#     Create the second image page layout
#     
#     Returns:
#         dash.html.Div: Image page layout
#     """
#     return html.Div([
#         html.H2('Image 2', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
#         html.Img(
#             src='/assets/image2.png',
#             style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
#         ),
#     ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

# def image3_page():
#     """
#     Create the third image page layout
#     
#     Returns:
#         dash.html.Div: Image page layout
#     """
#     return html.Div([
#         html.H2('Image 3', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
#         html.Img(
#             src='/assets/image3.png',
#             style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
#         ),
#     ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

# def image4_page():
#     """
#     Create the fourth image page layout
#     
#     Returns:
#         dash.html.Div: Image page layout
#     """
#     return html.Div([
#         html.H2('Image 4', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
#         html.Img(
#             src='/assets/image4.png',
#             style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
#         ),
#     ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def go_terms_page():
    """
    Create the GO Terms analysis page layout with multiple visualizations
    
    Returns:
        dash.html.Div: GO Terms page layout with multiple visualizations
    """
    return html.Div([
        html.H2('GO Term Analysis', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        
        # First visualization: GO Terms Information Gain
        html.Div([
            html.H3('GO Terms Information Gain', style={'color': UCONN_NAVY, 'marginBottom': '12px'}),
            html.P('Top 50 GO terms with highest information gain for predicting phenotypes.', 
                   style={'marginBottom': '15px', 'fontSize': '16px', 'lineHeight': '1.5'}),
            html.Img(
                src='/assets/go_terms_information_gain_db_top50.png',
                style={'width': '100%', 'maxWidth': '900px', 'display': 'block', 'margin': '0 auto 30px auto', 'border': '1px solid #eee'}
            ),
        ]),
        
        # Second visualization: GO Term Correlation Heatmap
        html.Div([
            html.H3('GO Term Correlation Heatmap', style={'color': UCONN_NAVY, 'marginBottom': '12px'}),
            html.P('Correlation matrix showing relationships between GO terms across samples.', 
                   style={'marginBottom': '15px', 'fontSize': '16px', 'lineHeight': '1.5'}),
            html.Img(
                src='/assets/go_term_correlation_heatmap_db.png',
                style={'width': '100%', 'maxWidth': '900px', 'display': 'block', 'margin': '0 auto 30px auto', 'border': '1px solid #eee'}
            ),
        ]),
        
        # Third visualization: Phenotype Distribution by GO Term
        html.Div([
            html.H3('Phenotype Distribution by GO Term', style={'color': UCONN_NAVY, 'marginBottom': '12px'}),
            html.P('Distribution of phenotypes across significant GO terms.', 
                   style={'marginBottom': '15px', 'fontSize': '16px', 'lineHeight': '1.5'}),
            html.Img(
                src='/assets/phenotype_distribution_by_go_term_db.png',
                style={'width': '100%', 'maxWidth': '900px', 'display': 'block', 'margin': '0 auto 30px auto', 'border': '1px solid #eee'}
            ),
        ]),
        
        # Analysis summary
        html.Div([
            html.H3('Analysis Summary', style={'color': UCONN_NAVY, 'marginBottom': '12px'}),
            html.P([
                'The GO term analysis visualizations above show the relationship between gene ontology terms and phenotypes in our dataset. ',
                'The information gain chart identifies GO terms that are most predictive of phenotypic outcomes. ',
                'The correlation heatmap reveals clusters of related GO terms that tend to co-occur. ',
                'The phenotype distribution visualization demonstrates how specific GO terms are associated with different phenotypic presentations.'
            ], style={'marginBottom': '15px', 'fontSize': '16px', 'lineHeight': '1.8'})
        ]),
        
    ], style={**uconn_styles['content'], 'maxWidth': '1000px', 'margin': '40px auto 0 auto', 'padding': '20px'})

"""
Image pages for the UCONN OFC SV Browser application.
"""

from dash import html
from utils.styling import UCONN_NAVY, uconn_styles

def image1_page():
    """
    Create the first image page layout
    
    Returns:
        dash.html.Div: Image page layout
    """
    return html.Div([
        html.H2('Image 1', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image1.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image2_page():
    """
    Create the second image page layout
    
    Returns:
        dash.html.Div: Image page layout
    """
    return html.Div([
        html.H2('Image 2', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image2.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image3_page():
    """
    Create the third image page layout
    
    Returns:
        dash.html.Div: Image page layout
    """
    return html.Div([
        html.H2('Image 3', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image3.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image4_page():
    """
    Create the fourth image page layout
    
    Returns:
        dash.html.Div: Image page layout
    """
    return html.Div([
        html.H2('Image 4', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image4.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

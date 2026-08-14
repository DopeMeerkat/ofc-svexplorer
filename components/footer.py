"""
Footer component for the UCONN OFC SV Browser application.
"""

from datetime import date

from dash import html
from utils.styling import UCONN_NAVY

def create_uconn_footer():
    """
    Create a branded footer component
    
    Returns:
        dash.html.Footer: Footer component
    """
    current_year = date.today().year
    return html.Footer([
        html.Div([
            html.Img(
                src='/assets/banner_footer_kidsfirst.png',
                style={'width': '100%', 'maxWidth': '400px', 'marginBottom': '10px'}
            ),
            html.P([
                '© ', str(current_year), ' University of Connecticut'
            ], style={'color': UCONN_NAVY}),
            html.P('OFC-SV Explorer research portal', style={'color': UCONN_NAVY, 'margin': '0'})
        ], style={'textAlign': 'center', 'width': '100%'})
    ], style={'backgroundColor': '#FFFFFF', 'color': UCONN_NAVY, 'padding': '15px 0px', 'textAlign': 'center', 'fontSize': '12px', 'marginTop': '20px', 'width': '100%'})

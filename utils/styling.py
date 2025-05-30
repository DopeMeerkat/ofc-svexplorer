"""
Styling utilities for the UCONN OFC SV Browser application.
This module contains color definitions and style dictionaries.
"""

# UCONN Colors
UCONN_NAVY = '#02254B'
UCONN_LIGHT_BLUE = '#9ECEEB'
UCONN_WHITE = '#FFFFFF'
UCONN_GRAY = '#E8E8E8'

# Define custom styles that align with UCONN branding
uconn_styles = {
    'page': {
        'fontFamily': '"Open Sans", sans-serif',
        'backgroundColor': UCONN_WHITE,
        'color': '#333',
        'minHeight': '100vh',
    },
    'header': {
        'backgroundColor': UCONN_NAVY,
        'color': UCONN_WHITE,
        'padding': '10px 20px',
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'space-between',
        'marginBottom': '20px',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.1)',
    },
    'logo': {
        'height': '60px',
        'marginRight': '15px',
    },
    'title': {
        'fontSize': '24px',
        'fontWeight': 'bold',
        'margin': 0,
    },
    'content': {
        'padding': '20px',
        'backgroundColor': UCONN_WHITE,
        'borderRadius': '5px',
        'marginBottom': '20px',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.05)',
    },
    'footer': {
        'backgroundColor': UCONN_NAVY,
        'color': UCONN_WHITE,
        'padding': '15px 20px',
        'textAlign': 'center',
        'fontSize': '12px',
        'marginTop': '20px',
    },
    'dropdown': {
        'backgroundColor': UCONN_WHITE,
        'border': f'1px solid {UCONN_LIGHT_BLUE}',
        'borderRadius': '4px',
        'padding': '8px',
        'marginBottom': '20px',
        'width': '100%',
        'maxWidth': '400px',
    },
    'button': {
        'backgroundColor': UCONN_NAVY,
        'color': UCONN_WHITE,
        'border': 'none',
        'borderRadius': '4px',
        'padding': '8px 15px',
        'cursor': 'pointer',
    },
    'loading': {
        'marginTop': '20px',
    },
    'statusBar': {
        'padding': '10px',
        'borderRadius': '4px',
        'marginTop': '15px',
        'backgroundColor': UCONN_GRAY,
        'fontSize': '14px',
        'border': f'1px solid {UCONN_LIGHT_BLUE}',
    }
}

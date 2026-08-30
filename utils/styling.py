"""
Styling utilities for the UCONN OFC SV Browser application.
This module contains color definitions and style dictionaries.
"""

# UCONN Colors
UCONN_NAVY = '#02254B'
UCONN_LIGHT_BLUE = '#9ECEEB'
UCONN_WHITE = '#FFFFFF'
UCONN_GRAY = '#E8E8E8'
UCONN_ICE = '#F6FAFD'
TEXT_DARK = '#1F2937'
TEXT_MUTED = '#52606D'
BORDER_LIGHT = '#D8E2EA'

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
        'padding': '24px',
        'backgroundColor': UCONN_WHITE,
        'borderRadius': '10px',
        'marginBottom': '20px',
        'boxShadow': '0 2px 10px rgba(2, 37, 75, 0.06)',
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


page_title_style = {
    'color': UCONN_NAVY,
    'fontSize': '30px',
    'fontWeight': '700',
    'letterSpacing': '-0.02em',
    'margin': '0 0 8px 0',
}

section_title_style = {
    'color': UCONN_NAVY,
    'fontSize': '20px',
    'fontWeight': '700',
    'margin': '0 0 12px 0',
}

body_text_style = {
    'fontSize': '16px',
    'lineHeight': '1.65',
    'color': TEXT_DARK,
    'margin': '0 0 14px 0',
}

muted_text_style = {
    'fontSize': '14px',
    'lineHeight': '1.55',
    'color': TEXT_MUTED,
    'margin': '0 0 12px 0',
}

card_style = {
    'backgroundColor': UCONN_WHITE,
    'border': f'1px solid {BORDER_LIGHT}',
    'borderRadius': '10px',
    'padding': '18px',
    'boxShadow': '0 2px 8px rgba(2, 37, 75, 0.04)',
}

control_label_style = {
    'fontWeight': '700',
    'color': UCONN_NAVY,
    'fontSize': '14px',
    'marginBottom': '6px',
}

button_style = {
    'backgroundColor': UCONN_NAVY,
    'color': UCONN_WHITE,
    'border': f'1px solid {UCONN_NAVY}',
    'borderRadius': '6px',
    'padding': '9px 14px',
    'cursor': 'pointer',
    'fontWeight': '700',
}

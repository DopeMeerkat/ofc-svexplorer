"""
Header component for the UCONN OFC SV Browser application.
"""

from dash import html, dcc
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles

def create_uconn_header():
    """
    Create a branded header component with navigation tabs
    
    Returns:
        dash.html.Div: Header component
    """
    # Header: blue background, left-aligned, with logo and professional tabs (no rounded edges, inverted color scheme)
    return html.Div([
        html.Div([
            html.Img(
                src='/assets/husky.jpg',
                style={'height': '54px', 'marginRight': '18px', 'borderRadius': '50%', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
            ),
            html.Div([
                html.H1('OFC SV Browser', style={
                    **uconn_styles['title'],
                    'margin': 0,
                    'padding': 0,
                    'color': UCONN_NAVY.replace(UCONN_NAVY, '#FFFFFF')
                }),
                html.P('Browsing tool for Orofacial Cleft Structural Variations', style={
                    'margin': 0,
                    'fontSize': '14px',
                    'color': '#FFFFFF'
                })
            ])
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),
        # Tabs navigation
        dcc.Tabs(
            id='main-tabs',
            value='/summary',
            children=[
                dcc.Tab(label='Summary', value='/summary',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Genome Browser', value='/',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Table', value='/table',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 1', value='/image1',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 2', value='/image2',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 3', value='/image3',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 4', value='/image4',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Network', value='/network',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Circos Plot', value='/circos',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Family Genomes', value='/family',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Population SVs', value='/population',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
            ],
            style={'marginTop': '8px', 'backgroundColor': UCONN_NAVY, 'borderRadius': '0', 'border': f'1px solid {UCONN_NAVY}', 'width': '100%'},
            colors={
                'border': UCONN_NAVY,
                'primary': UCONN_NAVY,
                'background': UCONN_NAVY
            }
        )
    ], style={
        'backgroundColor': UCONN_NAVY,
        'color': '#FFFFFF',
        'padding': '18px 30px 0 30px',
        'display': 'flex',
        'flexDirection': 'column',
        'alignItems': 'flex-start',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.05)',
        'borderBottom': f'2px solid {UCONN_LIGHT_BLUE}'
    })

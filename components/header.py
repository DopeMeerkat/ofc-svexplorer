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
            html.Div([
                html.H1('OFC SV Explorer', style={
                    **uconn_styles['title'],
                    'margin': 0,
                    'padding': 0,
                    'color': '#FFFFFF'
                }),
                html.P('Structural variation and regulatory annotation portal for orofacial cleft research', style={
                    'margin': 0,
                    'fontSize': '14px',
                    'color': '#FFFFFF'
                })
            ]),
            html.Div([
                html.A(
                    'Gallery',
                    href='https://github.com/DopeMeerkat/ofc-svexplorer/blob/prod/gallery.md',
                    target='_blank',
                    style={
                        'color': '#FFFFFF',
                        'textDecoration': 'underline',
                        'fontWeight': '600',
                        'fontSize': '14px',
                        'marginRight': '18px',
                    },
                ),
                html.A(
                    'GitHub',
                    href='https://github.com/DopeMeerkat/ofc-svexplorer/tree/prod',
                    target='_blank',
                    style={
                        'color': '#FFFFFF',
                        'textDecoration': 'underline',
                        'fontWeight': '600',
                        'fontSize': '14px',
                    },
                ),
            ], style={'display': 'flex', 'alignItems': 'flex-start', 'paddingTop': '4px'})
        ], style={'display': 'flex', 'alignItems': 'flex-start', 'justifyContent': 'space-between', 'width': '100%', 'marginBottom': '8px'}),
        # Tabs navigation
        dcc.Tabs(
            id='main-tabs',
            value='/summary',
            children=[
                dcc.Tab(label='Summary', value='/summary',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Database Overview', value='/database',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Table Inspection', value='/table',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='IGV/Population', value='/population',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Pathway', value='/pathway',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Case Study', value='/case-study',
                        style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                # Image tabs commented out as requested
                # dcc.Tab(label='Image 1', value='/image1',
                #         style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                #         selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                # ),
                # dcc.Tab(label='Image 2', value='/image2',
                #         style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                #         selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                # ),
                # dcc.Tab(label='Image 3', value='/image3',
                #         style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                #         selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                # ),
                # dcc.Tab(label='Image 4', value='/image4',
                #         style={'color': '#FFFFFF', 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                #         selected_style={'color': UCONN_NAVY, 'backgroundColor': '#FFFFFF', 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                # ),
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

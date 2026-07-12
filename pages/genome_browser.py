"""
Genome browser page for the UCONN OFC SV Browser application.
"""

from dash import html, dcc, Input, Output, State, callback, clientside_callback
import dash_bio as dashbio
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles
from utils.database import get_tracks_for_genome, check_database_connection
from app import build_local_igv_reference
from components.gene_search import create_gene_search
import os
import os.path

def page_layout(selected_gene=None):
    """
    Create the genome browser page layout
    
    Args:
        selected_gene (dict, optional): Selected gene data
        
    Returns:
        dash.html.Div: Genome browser page layout
    """
    from app import HOSTED_GENOME_DICT
    
    dropdown_options = [{'label': 'Select a chromosome...', 'value': ''}] + HOSTED_GENOME_DICT
    chrom = ''
    locus = ''
    if selected_gene:
        # selected_gene is a dict with keys matching the gene table columns
        chrom = selected_gene.get('chrom', '')
        x1 = selected_gene.get('x1', '')
        x2 = selected_gene.get('x2', '')
        if chrom and x1 and x2:
            print(f"Setting locus to: {chrom}:{x1}-{x2}")
            locus = f"{chrom}:{x1}-{x2}"
    
    debug_controls = []
    if os.getenv("IGV_DEBUG_PANEL", "false").lower() == "true":
        debug_controls = [
            dcc.Interval(id='igv-client-ping', interval=2000, n_intervals=0),
            html.Div(id='igv-client-status', style={
                'fontSize': '12px',
                'color': UCONN_NAVY,
                'marginBottom': '10px',
            }),
        ]

    return html.Div([
        html.Div([
            html.Div([
                html.H2('Interactive Genome Browser', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.P('Explore genomic data using this interactive visualization tool. Select a chromosome from the dropdown menu below to view the corresponding genomic tracks.', 
                      style={'fontSize': '16px', 'lineHeight': '1.5'})
            ], style={'marginBottom': '30px'}),
            # Gene search component
            create_gene_search(),
            html.Div([
                html.H3('Select Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Choose the chromosome you would like to display:', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='default-igv-genome-select',
                    options=dropdown_options,
                    value=chrom,
                    placeholder='Select a chromosome...',
                    style=uconn_styles['dropdown']
                )
            ], style={'marginBottom': '20px'}),
            dcc.Loading(
                id='default-igv-container',
                type='circle',
                color=UCONN_NAVY,
                style=uconn_styles['loading']
            ),
            html.Div([
                html.P(f"Selected gene locus: {locus if locus else 'None'}", 
                      style={'fontSize': '14px', 'fontStyle': 'italic', 'color': UCONN_NAVY}) 
                if selected_gene else ''
            ], style={'marginBottom': '10px'}),
            html.Div(
                id='db-status',
                children=check_database_connection(),
                style=uconn_styles['statusBar']
            ),
            *debug_controls
        ], style=uconn_styles['content']),
        
        # Hidden store to keep track of gene locus
        dcc.Store(id='current-locus', data=locus)
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px'})

clientside_callback(
    """
    function(n) {
        try {
            var igvStatus = window.igv ? 'present' : 'missing';
            var hasDashBio = false;
            var registry = window.__dash_component_registry__ || window.dash_component_registry || window._dash_component_registry;
            if (registry) {
                var reg = registry.registry || registry._components || registry.components || registry;
                if (reg) {
                    if (reg['dash_bio']) {
                        hasDashBio = true;
                    } else {
                        var keys = Object.keys(reg);
                        for (var i = 0; i < keys.length; i++) {
                            if (keys[i].indexOf('dash_bio') !== -1) {
                                hasDashBio = true;
                                break;
                            }
                        }
                    }
                }
            }
            var scriptTag = document.querySelector("script[src*='dash_bio/bundle']") ? 'yes' : 'no';
            var resourceLoaded = 'unknown';
            if (window.performance && performance.getEntriesByType) {
                var entries = performance.getEntriesByType('resource');
                resourceLoaded = 'no';
                for (var j = 0; j < entries.length; j++) {
                    if (entries[j].name.indexOf('dash_bio/bundle') !== -1) {
                        resourceLoaded = 'yes';
                        break;
                    }
                }
            }
            return 'IGV client status: window.igv is ' + igvStatus
                + '; dash_bio registered=' + (hasDashBio ? 'yes' : 'no')
                + '; script tag=' + scriptTag
                + '; resource loaded=' + resourceLoaded;
        } catch (e) {
            return 'IGV client status: error checking window.igv: ' + e;
        }
    }
    """,
    Output('igv-client-status', 'children'),
    Input('igv-client-ping', 'n_intervals'),
)

# Return the IGV component with the selected genome.
@callback(
    Output('default-igv-container', 'children'),
    Input('default-igv-genome-select', 'value'),
    State('current-locus', 'data')
)
def return_igv(chrom, locus):
    """
    Return the IGV component for the selected chromosome.
    """
    if os.getenv("IGV_MINIMAL_TEST", "false").lower() == "true":
        return html.Div([
            html.Div([
                html.H3("IGV Minimal Test", style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                dashbio.Igv(
                    id='default-igv',
                    reference=build_local_igv_reference('1'),
                    locus='1:1-1000000',
                    tracks=[],
                    style={'width': '100%', 'height': '600px', 'border': f'1px solid {UCONN_LIGHT_BLUE}'}
                )
            ], style={'padding': '15px', 'backgroundColor': '#FFFFFF', 'borderRadius': '5px'})
        ])

    if not chrom:
        return html.Div(
            "Please select a chromosome from the dropdown",
            style={'padding': '20px', 'textAlign': 'center', 'color': UCONN_NAVY}
        )
    
    # Get tracks for selected chromosome
    try:
        tracks = get_tracks_for_genome(chrom)
        print(f"Retrieved {len(tracks)} tracks for chromosome {chrom}")
    except Exception as e:
        print(f"Error getting tracks: {e}")
        import traceback
        traceback.print_exc()
        tracks = []
    
    # Set view location - use full locus if available, otherwise default to first 1Mb
    view_locus = locus if locus and locus.startswith(f"{chrom}:") else f"{chrom}:1-1000000"
    print(f"Setting IGV view to: {view_locus}")
    
    # Track count feedback
    track_info = f"{len(tracks)} track(s) loaded"
    
    debug_panel = None
    if os.getenv("IGV_DEBUG_PANEL", "false").lower() == "true":
        debug_rows = []
        for track in tracks:
            debug_rows.append({
                "name": track.get("name"),
                "format": track.get("format"),
                "url_len": len(track.get("url", "")) if track.get("url") else 0,
                "feature_count": len(track.get("features", [])) if track.get("features") else 0,
            })
        debug_panel = html.Pre(
            "IGV debug\n"
            f"chrom={chrom}\n"
            f"locus={view_locus}\n"
            f"tracks={len(tracks)}\n"
            + "\n".join(
                f"- {row['name']} | {row['format']} | url_len={row['url_len']} | features={row['feature_count']}"
                for row in debug_rows
            ),
            style={
                'whiteSpace': 'pre-wrap',
                'fontSize': '12px',
                'backgroundColor': '#F7F9FC',
                'border': f'1px solid {UCONN_LIGHT_BLUE}',
                'borderRadius': '4px',
                'padding': '8px',
                'marginBottom': '10px',
            },
        )

    return html.Div([
        html.Div([
            html.H3(f"Viewing Chromosome: {chrom}", style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.Div([
                html.P(track_info, style={'fontSize': '14px', 'color': UCONN_NAVY, 'marginBottom': '10px'})
            ]),
            debug_panel if debug_panel else html.Div(),
            dashbio.Igv(
                id='default-igv',
                reference=build_local_igv_reference(chrom),
                locus=view_locus,
                minimumBases=100,
                tracks=tracks,
                style={'width': '100%', 'height': '600px', 'border': f'1px solid {UCONN_LIGHT_BLUE}'}
            )
        ], style={'padding': '15px', 'backgroundColor': '#FFFFFF', 'borderRadius': '5px'})
    ])

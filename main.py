from dash import Dash, html, dcc, Input, Output, State, callback, dash_table, no_update
import dash_bio as dashbio
import sqlite3
import os.path
import pandas as pd
from dash import ctx

# Create a Dash app with external stylesheets for responsive design and fonts
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        'https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
    ]
)

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

# Function to load genome data from SQLite database
def load_genomes_from_db(db_path):
    if not os.path.exists(db_path):
        print(f"Warning: Database file {db_path} not found")
        return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]  # Default fallback
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Connected to database")
        
        # Get unique chromosomes from the genes table
        cursor.execute("SELECT DISTINCT chrom FROM genes ORDER BY chrom")
        chromosomes = cursor.fetchall()
        
        # Format results for Dash dropdown
        genome_options = [{'value': chrom[0], 'label': f"Chromosome {chrom[0]}"} for chrom in chromosomes]
        
        conn.close()
        
        # If no chromosomes found in the database, provide defaults
        if not genome_options:
            print("No chromosomes found in database, using defaults")
            return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]
        
        return genome_options
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return [{'value': 'hg38', 'label': 'Human (GRCh38/hg38)'}]

# Load genomes from the database
HOSTED_GENOME_DICT = load_genomes_from_db('/data/cellvar.db/cellvar.db')

# Function to get gene tracks for a specific chromosome from database
def get_tracks_for_genome(db_path, chrom):
    tracks = []
    if not os.path.exists(db_path):
        return tracks
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query genes for the selected chromosome
        cursor.execute("""
            SELECT id, chrom, x1, x2, strand 
            FROM genes 
            WHERE chrom = ?
            ORDER BY x1
        """, (chrom,))
        
        genes = cursor.fetchall()
        conn.close()
        
        # Convert genes to BED format for IGV
        bed_content = "\n".join([f"{g[1]}\t{g[2]}\t{g[3]}\t{g[0]}\t.\t{g[4]}" for g in genes])
        
        if bed_content:
            tracks.append({
                'name': f'Genes ({chrom})',
                'url': 'data:application/bed,' + bed_content,
                'format': 'bed',
                'displayMode': 'EXPANDED'
            })
            
        return tracks
        
    except sqlite3.Error as e:
        print(f"Database error when fetching genes: {e}")
        return []

# Database status component
def check_database_connection(db_path):
    if not os.path.exists(db_path):
        return html.Div(f"Database not found: {db_path}", style={'color': 'red'})
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if genes table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='genes'")
        table_exists = cursor.fetchone()
        
        # Count genes
        gene_count = 0
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM genes")
            gene_count = cursor.fetchone()[0]
        
        conn.close()
        
        if not table_exists:
            return html.Div("Database exists but missing 'genes' table", style={'color': 'orange'})
        
        return html.Div([
            html.Span("Database connected. ", style={'fontWeight': 'bold'}),
            html.Span(f"Genes: {gene_count}", style={'marginLeft': '5px'})
        ], style={'display': 'flex', 'alignItems': 'center'})
        
    except sqlite3.Error as e:
        return html.Div(f"Database error: {e}", style={'color': 'red'})

# Create a branded header component
def create_uconn_header():
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
                    'color': UCONN_WHITE
                }),
                html.P('Browsing tool for Orofacial Cleft Structural Variations', style={
                    'margin': 0,
                    'fontSize': '14px',
                    'color': UCONN_WHITE
                })
            ])
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),
        # Tabs navigation
        dcc.Tabs(
            id='main-tabs',
            value='/summary',
            children=[
                dcc.Tab(label='Summary', value='/summary',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Genome Browser', value='/',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Table', value='/table',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 1', value='/image1',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 2', value='/image2',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 3', value='/image3',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
                ),
                dcc.Tab(label='Image 4', value='/image4',
                        style={'color': UCONN_WHITE, 'backgroundColor': UCONN_NAVY, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0'},
                        selected_style={'color': UCONN_NAVY, 'backgroundColor': UCONN_WHITE, 'fontWeight': 'bold', 'fontSize': '14px', 'padding': '7px 18px', 'marginRight': '2px', 'border': f'1px solid {UCONN_NAVY}', 'borderRadius': '0', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}
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
        'color': UCONN_WHITE,
        'padding': '18px 30px 0 30px',
        'display': 'flex',
        'flexDirection': 'column',
        'alignItems': 'flex-start',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.05)',
        'borderBottom': f'2px solid {UCONN_LIGHT_BLUE}'
    })

# Create a footer component
def create_uconn_footer():
    current_year = 2025
    return html.Footer([
        html.Div([
            html.Img(
                src='/assets/banner_footer_kidsfirst.png',
                style={'width': '100%', 'maxWidth': '400px', 'marginBottom': '10px'}
            ),
            html.P([
                '© ', str(current_year), ' University of Connecticut'
            ], style={'color': UCONN_NAVY}),
            html.P([
                html.A('Privacy Policy', href='#', style={'color': UCONN_NAVY, 'marginRight': '15px', 'textDecoration': 'none'}),
                html.A('Terms of Use', href='#', style={'color': UCONN_NAVY, 'textDecoration': 'none'})
            ])
        ], style={'textAlign': 'center', 'width': '100%'})
    ], style={'backgroundColor': UCONN_WHITE, 'color': UCONN_NAVY, 'padding': '15px 0px', 'textAlign': 'center', 'fontSize': '12px', 'marginTop': '20px', 'width': '100%'})

# Read the CSV table for the table page
TABLE_CSV_PATH = 'assets/table.csv'
def load_table_data():
    try:
        df = pd.read_csv(TABLE_CSV_PATH)
        return df
    except Exception as e:
        print(f"Error loading table: {e}")
        return pd.DataFrame()

# Table page layout
def table_page():
    df = load_table_data()
    if df.empty:
        return html.Div('No data found in table.csv', style={'padding': '30px', 'color': 'red'})
    return html.Div([
        html.H2('Table Data', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        html.P('Click on any row to view the gene in the Genome Browser', 
               style={'marginBottom': '15px', 'color': UCONN_NAVY, 'fontStyle': 'italic'}),
        dash_table.DataTable(
            id='gene-table',
            data=df.to_dict('records'),
            columns=[{"name": i, "id": i} for i in df.columns],
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left', 
                'padding': '5px',
                'cursor': 'pointer'  # Add pointer cursor to indicate clickable rows
            },
            style_header={'backgroundColor': UCONN_LIGHT_BLUE, 'fontWeight': 'bold'},
            style_data_conditional=[
                {
                    'if': {'column_id': 'Gene'},
                    'fontWeight': 'bold',
                    'color': UCONN_NAVY
                },
                {
                    'if': {'state': 'active'},  # When a cell is clicked
                    'backgroundColor': UCONN_LIGHT_BLUE,
                    'border': f'1px solid {UCONN_NAVY}'
                }
            ],
            page_size=20,
            # Remove row_selectable to eliminate checkboxes but keep row selection capability
            selected_rows=[],
        )
    ], style=uconn_styles['content'])

# Function to search for genes in the database
def search_genes(search_term):
    """Search for genes in the database that match the search term"""
    db_path = '/data/cellvar.db/cellvar.db'
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found")
        return []
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Search for genes with a LIKE query to match partial names too
        cursor.execute("""
            SELECT id, chrom, x1, x2, length, strand 
            FROM genes 
            WHERE id LIKE ? 
            ORDER BY id
            LIMIT 30
        """, (f'%{search_term}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        # Format results as a list of dictionaries
        genes = []
        for row in results:
            genes.append({
                'id': row[0],
                'chrom': row[1],
                'x1': row[2],
                'x2': row[3],
                'length': row[4],
                'strand': row[5],
                'label': f"{row[0]} ({row[1]}:{row[2]}-{row[3]})"  # Format for display
            })
            
        return genes
    except sqlite3.Error as e:
        print(f"Database error when searching genes: {e}")
        return []

# Main genome browser page layout

def genome_browser_page(selected_gene=None):
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
    
    return html.Div([
        html.Div([
            html.Div([
                html.H2('Interactive Genome Browser', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
                html.P('Explore genomic data using this interactive visualization tool. Select a chromosome from the dropdown menu below to view the corresponding genomic tracks.', 
                      style={'fontSize': '16px', 'lineHeight': '1.5'})
            ], style={'marginBottom': '30px'}),
            html.Div([
                html.H3('Search Genes', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Enter a gene name to search and navigate directly to that location:', style={'marginBottom': '10px'}),
                html.Div([
                    dcc.Input(
                        id='gene-search-input',
                        type='text',
                        placeholder='Enter gene name...',
                        style={
                            'width': '70%', 
                            'padding': '8px',
                            'borderRadius': '4px',
                            'border': f'1px solid {UCONN_LIGHT_BLUE}',
                            'marginRight': '10px'
                        }
                    ),
                    html.Button(
                        'Search', 
                        id='gene-search-button', 
                        n_clicks=0,
                        style={
                            'backgroundColor': UCONN_NAVY,
                            'color': UCONN_WHITE,
                            'border': 'none',
                            'padding': '8px 15px',
                            'borderRadius': '4px',
                            'cursor': 'pointer'
                        }
                    )
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'}),
                html.Div(id='gene-search-results', children=[]),
            ], style={'marginBottom': '30px'}),
            html.Div([
                html.H3('Select Chromosome', style={'color': UCONN_NAVY, 'marginBottom': '10px', 'fontSize': '18px'}),
                html.P('Choose the chromosome you would like to display:', style={'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='default-igv-genome-select',
                    options=dropdown_options,
                    value=chrom,
                    placeholder='Select a chromosome...',
                    style=uconn_styles['dropdown']
                ),
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
                children=check_database_connection('/data/cellvar.db/cellvar.db'),
                style=uconn_styles['statusBar']
            )
        ], style=uconn_styles['content']),
        
        # Hidden store to keep track of gene locus
        dcc.Store(id='current-locus', data=locus)
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px'})

# Summary page layout
def summary_page():
    # Professional formatting for the summary
    return html.Div([
        html.H2('Project Summary', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.P("Cleft lip is the 4th most common birth defect in the U.S. and is known to affect annually one in 800 babies worldwide. The Kids First program aims to uncover the etiology of these diseases and foster data sharing within the pediatric research community.", style={'fontSize': '17px', 'marginBottom': '18px', 'lineHeight': '1.7'}),
        html.P("Expert-Driven Small Projects to Strengthen Gabriella Miller Kids First Discovery (RFA-RM-22-006) is intended to \"engage experts in a variety of activities that will enhance the utility of childhood cancer and/or structural birth defects genomic datasets generated by the Kids First program and/or associated phenotypic datasets and resources\". In this proposal we specifically propose to analyze in-depth the Kids First curated datasets assembled for the cohort Orofacial Cleft: African and Asian Ancestry (253 Families) currently available through the framework CAVATICA at the Kids First data portal.", style={'fontSize': '17px', 'marginBottom': '18px', 'lineHeight': '1.7'}),
        html.P("Currently single nucleotide variation (SNV) analysis in syndromic and non-syndromic OFC has found functional impairments in genes such as IRF6, BMP4, MAPK3, etc. However, considering that Structural Variations (SVS) account for more total base-pair variation in human genomes than SNVs, we argue that this topic is an important and missing component of this Kids First project. Exploring the role of SVS in the manifestation of the OFC phenotype will require a search beyond gene regions, since intergenic SVS can cause impairment to normal enhancers and transcription factors. We will explore three main SV types: deletion, duplication and inversions by looking for common and individual SV alleles that differ from the parents. We will also look at the OFC associated genes along with the related transcription factors, paralogs and associated intergenic regions to fully characterize potentially causative SVs. Using a set of preidentified 39 gene loci including IRF6, we will closely survey the 244 triads and use a healthy human cohort to filter the results (1000 Genome Project Phase 3 study, 2504 samples). This analysis will complement the SNV analysis for this data that has already been completed and will provide additional context for the total genomic landscape. We will disseminate our work to the scientific community and compare our results with previous copy number variation (CNV) literature and share the SV triad workflows we develop to enable a similar analysis on other Gabriella Miller Kids First Pediatric Research Program (Kids First) datasets.", style={'fontSize': '17px', 'marginBottom': '18px', 'lineHeight': '1.7'}),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

# Image page layouts
def image1_page():
    return html.Div([
        html.H2('Image 1', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image1.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image2_page():
    return html.Div([
        html.H2('Image 2', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image2.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image3_page():
    return html.Div([
        html.H2('Image 3', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image3.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

def image4_page():
    return html.Div([
        html.H2('Image 4', style={'color': UCONN_NAVY, 'marginBottom': '18px', 'fontWeight': 'bold'}),
        html.Img(
            src='/assets/image4.png',
            style={'width': '100%', 'maxWidth': '800px', 'display': 'block', 'margin': '0 auto'}
        ),
    ], style={**uconn_styles['content'], 'maxWidth': '900px', 'margin': '40px auto 0 auto'})

# Updated layout with header and tabs, no sidebar
def layout_with_tabs():
    return html.Div([
        create_uconn_header(),
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='selected-gene', data=None),  # Add this missing Store component
        html.Div(id='page-content'),
        create_uconn_footer()
    ], style={**uconn_styles['page'], 'margin': '0', 'padding': '0'})
app.layout = layout_with_tabs

# Callback to update the URL when a tab is clicked
@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('selected-gene', 'data', allow_duplicate=True),
    Input('main-tabs', 'value'),
    prevent_initial_call=True
)
def update_url_from_tab(tab_value):
    # When using tab navigation, clear any previously selected gene
    return tab_value, None

# Return the IGV component with the selected genome.
@callback(
    Output('default-igv-container', 'children'),
    Input('default-igv-genome-select', 'value'),
    State('current-locus', 'data')
)
def return_igv(chrom, locus):
    if not chrom:
        return html.Div(
            "Please select a chromosome from the dropdown",
            style={'padding': '20px', 'textAlign': 'center', 'color': UCONN_NAVY}
        )
    
    # Get tracks for selected chromosome
    tracks = get_tracks_for_genome('/data/cellvar.db/cellvar.db', chrom)
    
    # Set view location - use full locus if available, otherwise default to first 1Mb
    view_locus = locus if locus and locus.startswith(f"{chrom}:") else f"{chrom}:1-1000000"
    print(f"Setting IGV view to: {view_locus}")
    
    return html.Div([
        html.Div([
            html.H3(f"Viewing Chromosome: {chrom}", style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            dashbio.Igv(
                id='default-igv',
                genome='hg38',  # Using hg38 as reference, adjust if needed
                locus=view_locus,
                minimumBases=100,
                tracks=tracks,
                style={'width': '100%', 'height': '600px', 'border': f'1px solid {UCONN_LIGHT_BLUE}'}
            )
        ], style={'padding': '15px', 'backgroundColor': UCONN_WHITE, 'borderRadius': '5px'})
    ])

# Page routing callback
@callback(
    Output('page-content', 'children'),
    Output('main-tabs', 'value'),
    Input('url', 'pathname'),
    State('selected-gene', 'data')
)
def display_page(pathname, selected_gene):
    # Track if we're coming from table selection vs tab navigation
    from_table_selection = False
    
    # If a gene is selected and the URL is changing to the genome browser ('/')
    if selected_gene and pathname == '/':
        # Query the database for the gene details
        db_path = '/data/cellvar.db/cellvar.db'
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get the 'Gene' value from the selected_gene data
            gene_id = selected_gene.get('Gene', '')
            
            # Make sure we have a valid gene ID
            if not gene_id:
                print("ERROR: No valid gene ID found in selected_gene data")
                print(f"Selected gene data: {selected_gene}")
                return genome_browser_page(), '/'
                
            print(f"\n=== DISPLAY_PAGE DEBUG ===")
            print(f"Selected gene: {gene_id}")
            print(f"Full selected_gene data: {selected_gene}")
            
            # Query for gene coordinates
            cursor.execute("SELECT id, chrom, x1, x2, length, strand FROM genes WHERE id = ?", (gene_id,))
            result = cursor.fetchone()
            print(f"Database query result: {result}")
            conn.close()
            
            if result:
                # Create a dictionary with gene details from database
                gene_dict = {
                    'id': result[0], 
                    'chrom': result[1], 
                    'x1': result[2], 
                    'x2': result[3], 
                    'length': result[4], 
                    'strand': result[5]
                }
                from_table_selection = True
                print(f"Redirecting to genome browser with gene: {gene_dict}")
                return genome_browser_page(selected_gene=gene_dict), '/'
            else:
                print(f"No gene found with ID: {gene_id}")
        except Exception as e:
            print(f"Error loading gene from db: {e}")
            import traceback
            traceback.print_exc()
    
    # Handle normal page routing
    if pathname == '/table':
        return table_page(), '/table'
    if pathname == '/':
        # When navigating directly via tab, don't pass any gene
        return genome_browser_page(), '/'
    if pathname == '/image1':
        return image1_page(), '/image1'
    if pathname == '/image2':
        return image2_page(), '/image2'
    if pathname == '/image3':
        return image3_page(), '/image3'
    if pathname == '/image4':
        return image4_page(), '/image4'
    # Default and /summary
    return summary_page(), '/summary'

# Callback for gene search functionality
@callback(
    Output('gene-search-results', 'children'),
    Input('gene-search-button', 'n_clicks'),
    State('gene-search-input', 'value'),
    prevent_initial_call=True
)
def update_search_results(n_clicks, search_term):
    if not search_term:
        return html.Div("Enter a gene name to search", style={'color': 'gray', 'fontSize': '14px'})
    
    # Search for genes matching the search term
    genes = search_genes(search_term)
    
    if not genes:
        return html.Div(f"No genes found matching '{search_term}'", style={'color': 'red', 'fontSize': '14px'})
    
    # Create a dropdown with search results
    options = [{'label': gene['label'], 'value': str(i)} for i, gene in enumerate(genes)]
    
    return html.Div([
        html.P(f"Found {len(genes)} genes matching '{search_term}':", 
              style={'marginBottom': '5px', 'fontSize': '14px', 'color': UCONN_NAVY}),
        dcc.Dropdown(
            id='gene-search-dropdown',
            options=options,
            placeholder='Select a gene...',
            style={**uconn_styles['dropdown'], 'marginBottom': '10px'}
        ),
        # Store the full gene data for later use
        dcc.Store(id='gene-search-data', data=genes)
    ])

# Callback to handle gene selection from search results
@callback(
    Output('selected-gene', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('gene-search-dropdown', 'value'),
    State('gene-search-data', 'data'),
    prevent_initial_call=True
)
def handle_search_selection(selected_index, genes_data):
    if selected_index is None or not genes_data:
        return no_update, no_update
    
    # Get the selected gene by index
    selected_gene = genes_data[int(selected_index)]
    print("\n======= GENE SEARCH SELECTION DEBUG =======")
    print(f"Selected gene: {selected_gene}")
    
    # Create the required gene dictionary format
    gene_dict = {
        'id': selected_gene['id'],
        'Gene': selected_gene['id'],  # Add 'Gene' field for compatibility with table selection
        'chrom': selected_gene['chrom'],
        'x1': selected_gene['x1'],
        'x2': selected_gene['x2'],
        'length': selected_gene['length'],
        'strand': selected_gene['strand']
    }
    
    # Return gene data and redirect to genome browser
    return gene_dict, '/'

# Callback to handle Enter key in search input
@callback(
    Output('gene-search-button', 'n_clicks', allow_duplicate=True),
    Input('gene-search-input', 'n_submit'),
    prevent_initial_call=True
)
def search_on_enter(n_submit):
    if n_submit:
        return 1  # Simulate button click
    return no_update

# Callback to handle gene table row selection
@callback(
    Output('selected-gene', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('gene-table', 'active_cell'),
    State('gene-table', 'data'),
    prevent_initial_call=True
)
def store_selected_gene_and_redirect(active_cell, table_data):
    if active_cell:
        row = active_cell['row']
        gene_row = table_data[row]
        print("\n======= GENE TABLE CLICK DEBUG =======")
        print(f"Selected row: {row}")
        print(f"Row data: {gene_row}")
        
        # Extract only the gene name value from the row
        gene_value = gene_row.get('Gene', '')
        
        if gene_value:
            # Create a simpler dictionary with just the Gene value for the DB lookup
            simplified_row = {'Gene': gene_value}
            print(f"Using gene: {gene_value}")
            
            # Return the simplified data and redirect to genome browser
            return simplified_row, '/'
        else:
            print("No Gene column found in the row data")
            return no_update, no_update
        
    return no_update, no_update

if __name__ == '__main__':
    app.run(debug=True, port=8002)
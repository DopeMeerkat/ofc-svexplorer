"""
Dashboard page for analyzing structural variations across the population.
This page provides summary statistics, visualizations, and search functionality.
"""

from dash import html, dcc, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import pandas as pd
import io
import os
import glob

from app import app
from components.population_gene_search import create_population_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import DB_PATH, get_all_gene_interactions
# No longer directly importing the generation function
# from assets.generate_proband_sv_inheritance import get_proband_sv_inheritance

def get_sv_summary_stats():
    """Get summary statistics for structural variations"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get total counts by SV type
        cursor.execute("""
            SELECT type, COUNT(*) as count 
            FROM phenotype_svs 
            GROUP BY type
        """)
        sv_types = dict(cursor.fetchall())
        
        # Get affected vs unaffected counts
        cursor.execute("""
            SELECT affected, COUNT(DISTINCT ps.sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
            GROUP BY affected
        """)
        affected_stats = dict(cursor.fetchall())
        
        # Get gender distribution
        cursor.execute("""
            SELECT gender, COUNT(DISTINCT ps.sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            GROUP BY gender
        """)
        gender_stats = dict(cursor.fetchall())
        
        conn.close()
        return {
            'sv_types': sv_types,
            'affected_stats': affected_stats,
            'gender_stats': gender_stats
        }
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_sv_size_distribution():
    """Get size distribution of structural variations"""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT type, length
            FROM phenotype_svs
            WHERE length > 0
        """, conn)
        conn.close()
        return df
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_chromosome_distribution():
    """Get distribution of SVs across chromosomes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT chrom, COUNT(*) as count
            FROM phenotype_svs
            GROUP BY chrom
            ORDER BY chrom
        """, conn)
        conn.close()
        return df
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def load_proband_sv_inheritance():
    """
    Load proband SV inheritance data from the pre-generated CSV file
    
    Returns:
        tuple: (DataFrame with inheritance information, total proband count)
    """
    try:
        # Get the most recent CSV file from the assets directory
        csv_pattern = os.path.join(os.path.dirname(__file__), '..', 'assets', 'proband_sv_inheritance*.csv')
        csv_files = glob.glob(csv_pattern)
        
        if not csv_files:
            # Use the default file if no timestamped files are found
            default_csv = os.path.join(os.path.dirname(__file__), '..', 'assets', 'proband_sv_inheritance.csv')
            if os.path.exists(default_csv):
                csv_file = default_csv
            else:
                print("No proband SV inheritance CSV file found")
                return pd.DataFrame(), 0
        else:
            # Use the most recent file based on modification time
            csv_file = max(csv_files, key=os.path.getmtime)
            
        print(f"Loading proband SV inheritance data from {csv_file}")
        df = pd.read_csv(csv_file)
        
        # Rename columns back to the original names if they were renamed in the CSV
        column_mapping = {
            'SV ID': 'sv_id',
            'Proband Count': 'proband_count',
            'Percentage of Probands (%)': 'proband_percentage',
            'Inherited From Father': 'father_count',
            'Inherited From Mother': 'mother_count',
            'Inherited From Both Parents': 'both_parents_count',
            'SV Type': 'sv_type',
            'Chromosome': 'sv_chrom',
            'Start Position': 'sv_start',
            'End Position': 'sv_end',
            'Length (bp)': 'sv_length',
            'Associated Gene': 'gene'
        }
        
        # Apply the column renaming if needed
        for csv_col, code_col in column_mapping.items():
            if csv_col in df.columns:
                df = df.rename(columns={csv_col: code_col})
                
        # Get the total proband count from the first row's percentage
        if 'proband_percentage' in df.columns and not df.empty:
            total_proband_count = int(round(df.iloc[0]['proband_count'] / df.iloc[0]['proband_percentage'] * 100, 0))
        else:
            # If percentage column doesn't exist or DataFrame is empty, query the database
            conn = sqlite3.connect(DB_PATH)
            total_query = "SELECT COUNT(DISTINCT bam_id) AS total_probands FROM phenotype WHERE proband = 1"
            total_df = pd.read_sql_query(total_query, conn)
            conn.close()
            total_proband_count = total_df['total_probands'].iloc[0]
            
        return df, total_proband_count
        
    except Exception as e:
        print(f"Error loading proband SV inheritance data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), 0

def get_chromosome_distribution_by_category():
    """Get percentage distribution of SVs across chromosomes, separated by category"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get mother SVs by chromosome
        mother_df = pd.read_sql_query("""
            SELECT ps.chrom, COUNT(*) as count, 'Mother' as category
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'F' AND p.child = 0
            GROUP BY ps.chrom
            ORDER BY ps.chrom
        """, conn)
        
        # Get father SVs by chromosome
        father_df = pd.read_sql_query("""
            SELECT ps.chrom, COUNT(*) as count, 'Father' as category
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'M' AND p.child = 0
            GROUP BY ps.chrom
            ORDER BY ps.chrom
        """, conn)
        
        # Get child SVs by chromosome
        child_df = pd.read_sql_query("""
            SELECT ps.chrom, COUNT(*) as count, 'Child' as category
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
            GROUP BY ps.chrom
            ORDER BY ps.chrom
        """, conn)
        
        # Get background SVs by chromosome
        background_df = pd.read_sql_query("""
            SELECT chrom, COUNT(*) as count, 'Background' as category
            FROM background_svs
            GROUP BY chrom
            ORDER BY chrom
        """, conn)
        
        conn.close()
        
        # Calculate percentages for each category
        # Mother percentages
        if not mother_df.empty:
            total_mother = mother_df['count'].sum()
            mother_df['percentage'] = mother_df['count'] / total_mother * 100
        
        # Father percentages
        if not father_df.empty:
            total_father = father_df['count'].sum()
            father_df['percentage'] = father_df['count'] / total_father * 100
        
        # Child percentages
        if not child_df.empty:
            total_child = child_df['count'].sum()
            child_df['percentage'] = child_df['count'] / total_child * 100
            
        # Background percentages
        if not background_df.empty:
            total_background = background_df['count'].sum()
            background_df['percentage'] = background_df['count'] / total_background * 100
            
        # Combine all dataframes
        combined_df = pd.concat([mother_df, father_df, child_df, background_df])
        
        return combined_df
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_top_frequent_svs_in_children():
    """Get the top most frequent SVs in children"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get total counts for each category
        cursor.execute("""
            SELECT 
                'Child' as category,
                COUNT(DISTINCT ps.id) as total
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
        """)
        child_total = cursor.fetchone()[1]
        
        cursor.execute("""
            SELECT 
                'Mother' as category,
                COUNT(DISTINCT ps.id) as total
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'F' AND p.child = 0
        """)
        mother_total = cursor.fetchone()[1]
        
        cursor.execute("""
            SELECT 
                'Father' as category,
                COUNT(DISTINCT ps.id) as total
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'M' AND p.child = 0
        """)
        father_total = cursor.fetchone()[1]
        
        cursor.execute("""
            SELECT 
                'Background' as category,
                COUNT(DISTINCT id) as total
            FROM background_svs
        """)
        background_total = cursor.fetchone()[1]
        
        # Store totals
        category_totals = {
            'Child': child_total,
            'Mother': mother_total,
            'Father': father_total,
            'Background': background_total
        }
        
        # Get top SVs in children by count
        cursor.execute("""
            SELECT id, COUNT(DISTINCT sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
            GROUP BY id
            ORDER BY count DESC
            LIMIT 20
        """)
        
        top_svs = cursor.fetchall()
        top_sv_ids = tuple([sv[0] for sv in top_svs])
        
        if len(top_sv_ids) == 0:
            conn.close()
            return None, None
        
        # Format the IN clause properly
        if len(top_sv_ids) == 1:
            top_sv_ids = f"({top_sv_ids[0]})"
        else:
            top_sv_ids = str(top_sv_ids)
        
        # Get child SVs with counts
        child_svs = pd.read_sql_query(f"""
            SELECT id, COUNT(DISTINCT sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1 AND id IN {top_sv_ids}
            GROUP BY id
            ORDER BY count DESC
        """, conn)
        
        # Get mother SVs with counts
        mother_svs = pd.read_sql_query(f"""
            SELECT id, COUNT(DISTINCT sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'F' AND p.child = 0 AND id IN {top_sv_ids}
            GROUP BY id
        """, conn)
        
        # Get father SVs with counts
        father_svs = pd.read_sql_query(f"""
            SELECT id, COUNT(DISTINCT sample) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'M' AND p.child = 0 AND id IN {top_sv_ids}
            GROUP BY id
        """, conn)
        
        # Get background SVs with counts
        background_svs = pd.read_sql_query(f"""
            SELECT id, COUNT(*) as count
            FROM background_svs
            WHERE id IN {top_sv_ids}
            GROUP BY id
        """, conn)
        
        # Get additional info about these SVs (type, chromosome, etc.)
        sv_info = pd.read_sql_query(f"""
            SELECT DISTINCT id, type, chrom, start, "end", length
            FROM phenotype_svs
            WHERE id IN {top_sv_ids}
        """, conn)
        
        conn.close()
        
        # Merge the data into a single dataframe
        result_df = child_svs.rename(columns={'count': 'child_count'})
        
        # Merge mother counts
        result_df = pd.merge(
            result_df, 
            mother_svs.rename(columns={'count': 'mother_count'}),
            on='id', 
            how='left'
        )
        
        # Merge father counts
        result_df = pd.merge(
            result_df, 
            father_svs.rename(columns={'count': 'father_count'}),
            on='id', 
            how='left'
        )
        
        # Merge background counts
        result_df = pd.merge(
            result_df, 
            background_svs.rename(columns={'count': 'background_count'}),
            on='id', 
            how='left'
        )
        
        # Merge SV info
        result_df = pd.merge(result_df, sv_info, on='id', how='left')
        
        # Replace NaN with 0 for counts
        result_df['mother_count'] = result_df['mother_count'].fillna(0).astype(int)
        result_df['father_count'] = result_df['father_count'].fillna(0).astype(int)
        result_df['background_count'] = result_df['background_count'].fillna(0).astype(int)
        
        # Calculate percentages
        result_df['child_pct'] = (result_df['child_count'] / category_totals['Child'] * 100).round(2)
        result_df['mother_pct'] = (result_df['mother_count'] / category_totals['Mother'] * 100).round(2)
        result_df['father_pct'] = (result_df['father_count'] / category_totals['Father'] * 100).round(2)
        result_df['background_pct'] = (result_df['background_count'] / category_totals['Background'] * 100).round(2)
        
        return result_df, category_totals
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def page_layout():
    """Create the dashboard page layout"""
    return html.Div([
        # Header section
        html.Div([
            html.H2('Population SV Analysis Dashboard', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Interactive dashboard for analyzing structural variations across the population', 
                  style={'fontSize': '16px', 'lineHeight': '1.5'}),
        ], style={'marginBottom': '30px'}),
        
        # Gene search component
        create_population_gene_search(),
        
        # # Summary statistics section
        # html.Div([
        #     html.H3('Summary Statistics', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        #     html.Div(id='summary-stats-container', style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '20px'})
        # ], style={'marginBottom': '30px'}),
        
        # # SV type distribution
        # html.Div([
        #     html.H3('SV Type Distribution', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        #     html.Div([
        #         dcc.Graph(id='sv-type-pie'),
        #         dcc.Graph(id='sv-type-bar')
        #     ], style={'display': 'flex', 'gap': '20px'})
        # ], style={'marginBottom': '30px'}),
        
        # Chromosome distribution
        html.Div([
            html.H3('Chromosome Distribution by Category', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('Compare the percentage distribution of structural variations across chromosomes for different categories. Each bar represents the percentage of SVs in that chromosome relative to the total SVs in its category:',
                  style={'marginBottom': '10px'}),
            
            html.Div([
                html.Div([
                    html.Span('●', style={'color': '#CC3366', 'marginRight': '5px', 'fontSize': '18px'}),
                    html.Span('Mothers', style={'color': UCONN_NAVY})
                ], style={'marginRight': '15px', 'display': 'inline-block'}),
                
                html.Div([
                    html.Span('●', style={'color': '#3366CC', 'marginRight': '5px', 'fontSize': '18px'}),
                    html.Span('Fathers', style={'color': UCONN_NAVY})
                ], style={'marginRight': '15px', 'display': 'inline-block'}),
                
                html.Div([
                    html.Span('●', style={'color': UCONN_NAVY, 'marginRight': '5px', 'fontSize': '18px'}),
                    html.Span('Children', style={'color': UCONN_NAVY})
                ], style={'marginRight': '15px', 'display': 'inline-block'}),
                
                html.Div([
                    html.Span('●', style={'color': '#669900', 'marginRight': '5px', 'fontSize': '18px'}),
                    html.Span('Background', style={'color': UCONN_NAVY})
                ], style={'marginRight': '15px', 'display': 'inline-block'})
            ], style={'marginBottom': '15px'}),
            
            dcc.Graph(id='chromosome-distribution')
        ], style={'marginBottom': '30px'}),
        
        # Top 20 Most Frequent SVs in Children
        html.Div([
            html.H3('Top 20 Most Frequent SVs in Children', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('This section shows the top 20 most frequent structural variations in children by absolute count, with comparison to their occurrence in mothers, fathers, and background populations. Both raw counts and percentages within each category are shown.',
                  style={'marginBottom': '10px'}),
            
            # Tabs for table and chart views
            dcc.Tabs([
                dcc.Tab(label='Table View', children=[
                    html.Div(id='top-svs-table-container', style={'marginTop': '15px'})
                ], style={'color': UCONN_NAVY}, selected_style={'color': UCONN_NAVY, 'borderTop': f'3px solid {UCONN_NAVY}'}),
                
                dcc.Tab(label='Chart View', children=[
                    dcc.Graph(id='top-svs-chart')
                ], style={'color': UCONN_NAVY}, selected_style={'color': UCONN_NAVY, 'borderTop': f'3px solid {UCONN_NAVY}'})
            ], style={'marginBottom': '15px'})
        ], style={'marginBottom': '30px'}),
        
        # Proband SV Inheritance Analysis
        html.Div([
            html.H3('Proband SV Inheritance Analysis', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('This section displays the inheritance patterns of structural variations found in probands. For each SV, the table shows how many cases are inherited from the father, mother, or both parents.',
                  style={'marginBottom': '15px'}),
            
            # Loading container for the table
            dcc.Loading(
                id="proband-inheritance-loading",
                type="circle",
                color=UCONN_NAVY,
                children=[
                    html.Div(id='proband-inheritance-table-container', style={'marginBottom': '20px'})
                ]
            ),
            
            html.Div([
                html.Button(
                    [
                        html.I(className="fa fa-download", style={'marginRight': '10px'}),
                        "Download Proband SV Inheritance Data (CSV)"
                    ],
                    id='download-proband-sv-button',
                    style={
                        'backgroundColor': UCONN_NAVY,
                        'color': 'white',
                        'border': 'none',
                        'padding': '10px 15px',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'display': 'flex',
                        'alignItems': 'center',
                        'justifyContent': 'center',
                        'width': 'fit-content'
                    }
                ),
                dcc.Download(id='download-proband-sv-data')
            ], style={'marginBottom': '20px'})
        ], style={'marginBottom': '30px'}),
        
        # Gene Interactions Section
        html.Div([
            html.H3('Gene Interactions', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
            html.P('This section provides information about long-range gene interactions identified in the dataset. These interactions represent functional relationships between genes based on literature review and experimental data, identical to those shown in the Circos plot and IGV browser.',
                  style={'marginBottom': '15px'}),
            
            html.Div([
                html.Button(
                    [
                        html.I(className="fa fa-download", style={'marginRight': '10px'}),
                        "Download All Gene Interactions (CSV)"
                    ],
                    id='download-interactions-button',
                    style={
                        'backgroundColor': UCONN_NAVY,
                        'color': 'white',
                        'border': 'none',
                        'padding': '10px 15px',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'display': 'flex',
                        'alignItems': 'center',
                        'justifyContent': 'center',
                        'width': 'fit-content'
                    }
                ),
                dcc.Download(id='download-gene-interactions')
            ], style={'marginBottom': '20px'})
        ], style={'marginBottom': '30px'}),
        
        # # # Background analysis
        # html.Div([
        #     html.H3('Background SV Analysis', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        #     html.Div([
        #         dcc.Graph(id='background-sv-comparison'),
        #         dcc.Graph(id='background-sv-frequency')
        #     ], style={'display': 'flex', 'gap': '20px'})
        # ], style={'marginBottom': '30px'}),

    ], style=uconn_styles['content'])

# Callbacks
@callback(
    Output('chromosome-distribution', 'figure'),
    Input('chromosome-distribution', 'id')
)
def update_chromosome_distribution(trigger):
    """Update the chromosome distribution chart"""
    # Get data
    df = get_chromosome_distribution_by_category()
    if df is None:
        return go.Figure()
    
    # Update chromosome labels for display
    df['chrom'] = df['chrom'].apply(lambda x: f"Chr {x}")
    
    # Create the figure
    fig = px.bar(
        df, 
        x='chrom', 
        y='percentage', 
        color='category',
        barmode='group',
        color_discrete_map={
            'Mother': '#CC3366', 
            'Father': '#3366CC', 
            'Child': UCONN_NAVY, 
            'Background': '#669900'
        },
        labels={'percentage': '% of SVs in Category', 'chrom': 'Chromosome', 'category': 'Category'}
    )
    
    # Customize layout
    fig.update_layout(
        title='',
        legend_title_text='',
        height=500,
        font=dict(family="Arial", size=12),
        margin=dict(t=30, b=50, l=50, r=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
            tickangle=-45
        ),
        yaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12)
        )
    )
    
    return fig

@callback(
    Output('top-svs-table-container', 'children'),
    Input('top-svs-table-container', 'id')
)
def update_top_svs_table(trigger):
    """Update the top SVs table"""
    # Get data
    df, _ = get_top_frequent_svs_in_children()
    if df is None:
        return html.P("No data available", style={'color': 'gray', 'fontStyle': 'italic'})
    
    # Format the table data
    table_rows = []
    for _, row in df.iterrows():
        table_rows.append(html.Tr([
            html.Td(row['id'], style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(row['type'], style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"Chr {row['chrom']}", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"{row['child_count']} ({row['child_pct']}%)", style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'backgroundColor': 'rgba(21, 71, 123, 0.1)'}),
            html.Td(f"{row['mother_count']} ({row['mother_pct']}%)", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"{row['father_count']} ({row['father_pct']}%)", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"{row['background_count']} ({row['background_pct']}%)", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
        ]))
    
    # Create the table
    table = html.Table([
        html.Thead(
            html.Tr([
                html.Th("SV ID", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Type", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Chr", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Children", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Mothers", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Fathers", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                html.Th("Background", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
            ])
        ),
        html.Tbody(table_rows)
    ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'})
    
    return table

@callback(
    Output('top-svs-chart', 'figure'),
    Input('top-svs-chart', 'id')
)
def update_top_svs_chart(trigger):
    """Update the top SVs chart"""
    # Get data
    df, category_totals = get_top_frequent_svs_in_children()
    if df is None:
        return go.Figure()
    
    # Prepare data for chart
    chart_data = []
    
    # Format the SV labels
    df['sv_label'] = df.apply(lambda row: f"{row['id']} ({row['type']})", axis=1)
    
    # Prepare data for Children
    for _, row in df.iterrows():
        chart_data.append({
            'sv_label': row['sv_label'],
            'count': row['child_count'],
            'category': 'Children',
            'percentage': row['child_pct']
        })
        
        # Prepare data for Mothers
        chart_data.append({
            'sv_label': row['sv_label'],
            'count': row['mother_count'],
            'category': 'Mothers',
            'percentage': row['mother_pct']
        })
        
        # Prepare data for Fathers
        chart_data.append({
            'sv_label': row['sv_label'],
            'count': row['father_count'],
            'category': 'Fathers',
            'percentage': row['father_pct']
        })
    
    chart_df = pd.DataFrame(chart_data)
    
    # Create the chart
    fig = px.bar(
        chart_df,
        x='sv_label',
        y='count',
        color='category',
        barmode='group',
        color_discrete_map={
            'Children': UCONN_NAVY,
            'Mothers': '#CC3366',
            'Fathers': '#3366CC'
        },
        labels={'count': 'Number of Samples', 'sv_label': 'Structural Variation', 'category': 'Category'}
    )
    
    # Customize layout
    fig.update_layout(
        title='',
        height=500,
        font=dict(family="Arial", size=12),
        margin=dict(t=30, b=100, l=50, r=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=11),
            tickangle=-45,  # Angle the SV labels for better readability
            categoryorder='total descending'  # Order by total count
        ),
        yaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12)
        )
    )
    
    # Add value labels on top of bars
    for trace in fig.data:
        category = trace.name
        category_data = chart_df[chart_df['category'] == category]
        
        # Add text above each bar
        fig.add_traces(
            go.Scatter(
                x=category_data['sv_label'],
                y=category_data['count'] + 0.5,  # Slightly above the bar
                text=category_data['count'].astype(int).astype(str),
                mode='text',
                showlegend=False,
                textfont=dict(color='rgba(0,0,0,0.6)', size=9),
                hoverinfo='skip'
            )
        )
    
    return fig

# Add callback to create proband inheritance table
@callback(
    Output('proband-inheritance-table-container', 'children'),
    Input('proband-inheritance-table-container', 'id')
)
def update_proband_inheritance_table(trigger):
    """Update the proband SV inheritance table"""
    # Load proband SV inheritance data from CSV
    df, total_proband_count = load_proband_sv_inheritance()
    
    if df.empty:
        return html.P("No proband SV inheritance data available", style={'color': 'gray', 'fontStyle': 'italic'})
    
    # Calculate percentages for clearer interpretation
    df['from_father_pct'] = (df['father_count'] / df['proband_count'] * 100).round(1)
    df['from_mother_pct'] = (df['mother_count'] / df['proband_count'] * 100).round(1)
    df['from_both_pct'] = (df['both_parents_count'] / df['proband_count'] * 100).round(1)
    
    # Format the table data - limit to first 50 rows for better performance
    table_rows = []
    for _, row in df.head(50).iterrows():
        table_rows.append(html.Tr([
            html.Td(row['sv_id'], style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(row.get('gene', ''), style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(row['sv_type'], style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"Chr {row['sv_chrom']}", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
            html.Td(f"{row['proband_count']}", style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'center'}),
            html.Td([
                html.Span(f"{row['father_count']} ", style={'fontWeight': 'bold'}),
                html.Span(f"({row['from_father_pct']}%)", style={'fontSize': '12px', 'color': '#666'})
            ], style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'center'}),
            html.Td([
                html.Span(f"{row['mother_count']} ", style={'fontWeight': 'bold'}),
                html.Span(f"({row['from_mother_pct']}%)", style={'fontSize': '12px', 'color': '#666'})
            ], style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'center'}),
            html.Td([
                html.Span(f"{row['both_parents_count']} ", style={'fontWeight': 'bold'}),
                html.Span(f"({row['from_both_pct']}%)", style={'fontSize': '12px', 'color': '#666'})
            ], style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'center', 'backgroundColor': 'rgba(21, 71, 123, 0.1)'}),
        ]))
    
    # Create the table
    table = html.Div([
        html.P(f"Showing top 50 of {len(df)} SVs found in probands", style={'fontStyle': 'italic', 'marginBottom': '10px'}),
        html.Table([
            html.Thead(
                html.Tr([
                    html.Th("SV ID", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("Associated Gene", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("Type", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("Chromosome", style={'padding': '8px', 'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("Proband Count", style={'padding': '8px', 'textAlign': 'center', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("From Father", style={'padding': '8px', 'textAlign': 'center', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("From Mother", style={'padding': '8px', 'textAlign': 'center', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                    html.Th("From Both Parents", style={'padding': '8px', 'textAlign': 'center', 'backgroundColor': UCONN_NAVY, 'color': 'white'}),
                ])
            ),
            html.Tbody(table_rows)
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'})
    ])
    
    return table

# Add callback for downloading proband SV inheritance data
@callback(
    Output('download-proband-sv-data', 'data'),
    Input('download-proband-sv-button', 'n_clicks'),
    prevent_initial_call=True
)
def download_proband_sv_data(n_clicks):
    """Generate a CSV file with proband SV inheritance data"""
    if not n_clicks:
        return None
    
    # Load proband SV inheritance data from CSV
    df, total_proband_count = load_proband_sv_inheritance()
    
    if df.empty:
        return None
    
    # Calculate percentages for the export
    df['from_father_pct'] = (df['father_count'] / df['proband_count'] * 100).round(1)
    df['from_mother_pct'] = (df['mother_count'] / df['proband_count'] * 100).round(1)
    df['from_both_pct'] = (df['both_parents_count'] / df['proband_count'] * 100).round(1)
    
    # Rename columns for better readability in CSV
    df_export = df.rename(columns={
        'sv_id': 'Proband SV ID',
        'proband_count': 'Number of Probands',
        'father_count': 'Inherited from Father',
        'mother_count': 'Inherited from Mother',
        'both_parents_count': 'Inherited from Both Parents',
        'from_father_pct': 'Father Inheritance %',
        'from_mother_pct': 'Mother Inheritance %',
        'from_both_pct': 'Both Parents Inheritance %',
        'sv_type': 'SV Type',
        'sv_chrom': 'Chromosome',
        'sv_start': 'Start Position',
        'sv_end': 'End Position',
        'sv_length': 'SV Length'
    })
    
    # Prepare CSV download
    csv_string = df_export.to_csv(index=False)
    return dict(content=csv_string, filename="proband_sv_inheritance.csv")

# MSC/NCC table has been completely removed

# Add callback for downloading gene interactions
@callback(
    Output('download-gene-interactions', 'data'),
    Input('download-interactions-button', 'n_clicks'),
    prevent_initial_call=True
)
def download_gene_interactions(n_clicks):
    """Generate a CSV file with all gene interactions"""
    if not n_clicks:
        return None
        
    # Get all gene interactions
    interactions_df = get_all_gene_interactions()
    
    if interactions_df.empty:
        return None
    
    # Prepare CSV download
    csv_string = interactions_df.to_csv(index=False)
    return dict(content=csv_string, filename="gene_interactions.csv")

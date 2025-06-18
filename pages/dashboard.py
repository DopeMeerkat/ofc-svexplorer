"""
Dashboard page for analyzing structural variations across the population.
This page provides summary statistics, visualizations, and search functionality.
"""

from dash import html, dcc, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import pandas as pd

from app import app
from components.population_gene_search import create_population_gene_search
from utils.styling import uconn_styles, UCONN_NAVY, UCONN_LIGHT_BLUE
from utils.database import DB_PATH

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

def get_top_svs_by_category():
    """Get top 20 most frequent SVs for children with comparison to other categories"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get the total counts for each category to use for percentage calculations
        category_totals = {}
        
        # Total SVs for children
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
        """)
        category_totals['Child'] = cursor.fetchone()[0]
        
        # Total SVs for mothers
        cursor.execute("""
            SELECT COUNT(*) 
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'F' AND p.child = 0
        """)
        category_totals['Mother'] = cursor.fetchone()[0]
        
        # Total SVs for fathers
        cursor.execute("""
            SELECT COUNT(*) 
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'M' AND p.child = 0
        """)
        category_totals['Father'] = cursor.fetchone()[0]
        
        # Total SVs for background
        cursor.execute("""
            SELECT COUNT(*) 
            FROM background_svs
        """)
        category_totals['Background'] = cursor.fetchone()[0]
        
        # Get top 20 most frequent SV IDs for children
        child_svs = pd.read_sql_query("""
            SELECT ps.id, COUNT(*) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.child = 1
            GROUP BY ps.id
            ORDER BY count DESC
            LIMIT 20
        """, conn)
        
        # Get list of top 20 SV IDs to use in subsequent queries
        top_sv_ids = tuple(child_svs['id'].tolist())
        
        if not top_sv_ids:
            return None
            
        # If there's only one SV ID, adjust the tuple format for SQL
        if len(top_sv_ids) == 1:
            top_sv_ids = f"('{top_sv_ids[0]}')"
        
        # Get counts for these SVs in mothers
        mother_svs = pd.read_sql_query(f"""
            SELECT ps.id, COUNT(*) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'F' AND p.child = 0 AND ps.id IN {top_sv_ids}
            GROUP BY ps.id
        """, conn)
        
        # Get counts for these SVs in fathers
        father_svs = pd.read_sql_query(f"""
            SELECT ps.id, COUNT(*) as count
            FROM phenotype_svs ps
            JOIN phenotype p ON ps.sample = p.bam_id
            WHERE p.gender = 'M' AND p.child = 0 AND ps.id IN {top_sv_ids}
            GROUP BY ps.id
        """, conn)
        
        # Get counts for these SVs in background
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
        
        return result_df
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

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
        
        # # Size analysis
        # html.Div([
        #     html.H3('SV Size Analysis', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        #     dcc.Graph(id='sv-size-boxplot')
        # ], style={'marginBottom': '30px'}),
        
        # # Background analysis
        # html.Div([
        #     html.H3('Background SV Analysis', style={'color': UCONN_NAVY, 'marginBottom': '15px'}),
        #     html.Div([
        #         dcc.Graph(id='background-sv-comparison'),
        #         dcc.Graph(id='background-sv-frequency')
        #     ], style={'display': 'flex', 'gap': '20px'})
        # ])
    ], style={'padding': '20px'})

@callback(
    Output('summary-stats-container', 'children'),
    Input('url', 'pathname')
)
def update_summary_stats(pathname):
    """Update summary statistics display"""
    stats = get_sv_summary_stats()
    if not stats:
        return html.P("Error loading summary statistics")
    
    stat_cards = []
    
    # SV Type counts
    for sv_type, count in stats['sv_types'].items():
        stat_cards.append(
            html.Div([
                html.H4(sv_type, style={'color': UCONN_NAVY}),
                html.P(f"{count:,} variants")
            ], style={
                'backgroundColor': 'white',
                'padding': '15px',
                'borderRadius': '5px',
                'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                'minWidth': '150px'
            })
        )
    
    # Affected/Unaffected stats
    affected_count = stats['affected_stats'].get(1, 0)
    unaffected_count = stats['affected_stats'].get(0, 0)
    stat_cards.append(
        html.Div([
            html.H4('Patient Status', style={'color': UCONN_NAVY}),
            html.P(f"Affected: {affected_count:,}"),
            html.P(f"Unaffected: {unaffected_count:,}")
        ], style={
            'backgroundColor': 'white',
            'padding': '15px',
            'borderRadius': '5px',
            'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
            'minWidth': '150px'
        })
    )
    
    return stat_cards

@callback(
    [Output('sv-type-pie', 'figure'),
     Output('sv-type-bar', 'figure')],
    Input('url', 'pathname')
)
def update_sv_type_charts(pathname):
    """Update SV type distribution charts"""
    stats = get_sv_summary_stats()
    if not stats:
        return {}, {}
    
    # Prepare data
    types = list(stats['sv_types'].keys())
    counts = list(stats['sv_types'].values())
    
    # Create pie chart
    pie_fig = px.pie(
        values=counts,
        names=types,
        title='SV Type Distribution',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    pie_fig.update_traces(textposition='inside', textinfo='percent+label')
    
    # Create bar chart
    bar_fig = px.bar(
        x=types,
        y=counts,
        title='SV Count by Type',
        labels={'x': 'SV Type', 'y': 'Count'},
        color_discrete_sequence=[UCONN_NAVY]
    )
    
    return pie_fig, bar_fig

@callback(
    Output('chromosome-distribution', 'figure'),
    Input('url', 'pathname')
)
def update_chromosome_chart(pathname):
    """Update chromosome distribution chart"""
    df = get_chromosome_distribution_by_category()
    if df is None:
        return {}
    
    # Define a custom color map for categories
    color_map = {
        'Mother': '#CC3366',  # Pink/rose color for mothers
        'Father': '#3366CC',  # Blue color for fathers
        'Child': UCONN_NAVY,  # Navy color for children
        'Background': '#669900'  # Green color for background
    }
    
    fig = px.bar(
        df,
        x='chrom',
        y='percentage',  # Now using percentage instead of count
        color='category',
        barmode='group',  # Group bars by chromosome
        title='SV Distribution Across Chromosomes by Category (% within each category)',
        labels={'chrom': 'Chromosome', 'percentage': 'Percentage (%)', 'category': 'Category'},
        color_discrete_map=color_map,
        height=500  # Increase height for better visibility
    )
    
    # Improve layout
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(t=80, b=50),
        xaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
            tickangle=-45  # Angle the chromosome labels for better readability
        ),
        yaxis=dict(
            title_font=dict(size=14),
            tickfont=dict(size=12),
            # Add percentage format to y-axis
            tickformat='.1f',  # Show one decimal place
            range=[0, df['percentage'].max() * 1.1]  # Add 10% headroom to max value
        )
    )
    
    # Add value labels on top of bars
    for trace in fig.data:
        category = trace.name
        category_data = df[df['category'] == category]
        
        # Add text above each bar
        fig.add_traces(
            go.Scatter(
                x=category_data['chrom'],
                y=category_data['percentage'] + 0.5,  # Slightly above the bar
                text=category_data['percentage'].round(1).astype(str) + '%',
                mode='text',
                showlegend=False,
                textfont=dict(color='rgba(0,0,0,0.6)', size=9),
                hoverinfo='skip'
            )
        )
    
    return fig

@callback(
    Output('sv-size-boxplot', 'figure'),
    Input('url', 'pathname')
)
def update_size_analysis_chart(pathname):
    """Update SV size analysis chart"""
    df = get_sv_size_distribution()
    if df is None:
        return {}
    
    fig = px.box(
        df,
        x='type',
        y='length',
        title='SV Size Distribution by Type',
        labels={'type': 'SV Type', 'length': 'Size (bp)'},
        color='type',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_layout(showlegend=False)
    fig.update_yaxes(type='log')
    
    return fig

@callback(
    [Output('background-sv-comparison', 'figure'),
     Output('background-sv-frequency', 'figure')],
    Input('url', 'pathname')
)
def update_background_analysis_charts(pathname):
    """Update background SV analysis charts"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Compare SV types between population and background
        population_df = pd.read_sql_query("""
            SELECT type, COUNT(*) as count, 'Population' as source
            FROM phenotype_svs
            GROUP BY type
            UNION ALL
            SELECT type, COUNT(*) as count, 'Background' as source
            FROM background_svs
            GROUP BY type
        """, conn)
        
        # Get frequency distribution from background SVs
        frequency_df = pd.read_sql_query("""
            SELECT freq, COUNT(*) as count
            FROM background_svs
            WHERE freq IS NOT NULL
            GROUP BY freq
            ORDER BY freq
        """, conn)
        
        conn.close()
        
        # Create comparison chart
        comp_fig = px.bar(
            population_df,
            x='type',
            y='count',
            color='source',
            barmode='group',
            title='SV Types: Population vs Background',
            labels={'type': 'SV Type', 'count': 'Count', 'source': 'Source'},
            color_discrete_sequence=[UCONN_NAVY, UCONN_LIGHT_BLUE]
        )
        
        # Create frequency distribution chart
        freq_fig = px.line(
            frequency_df,
            x='freq',
            y='count',
            title='Background SV Frequency Distribution',
            labels={'freq': 'Frequency', 'count': 'Count'},
            line_shape='spline'
        )
        freq_fig.update_traces(line_color=UCONN_NAVY)
        
        return comp_fig, freq_fig
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {}, {}

@callback(
    Output('top-svs-table-container', 'children'),
    Input('url', 'pathname')
)
def update_top_svs_table(pathname):
    """Update top SVs table"""
    df = get_top_svs_by_category()
    if df is None:
        return html.P("No data available for top SVs analysis")
    
    # Create a formatted table with the data
    table_header = [
        html.Thead(html.Tr([
            html.Th('SV ID', style={'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Type', style={'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Chromosome', style={'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Position', style={'textAlign': 'left', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Length', style={'textAlign': 'right', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Child', style={'textAlign': 'right', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Mother', style={'textAlign': 'right', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Father', style={'textAlign': 'right', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'}),
            html.Th('Background', style={'textAlign': 'right', 'backgroundColor': UCONN_NAVY, 'color': 'white', 'padding': '10px'})
        ]))
    ]
    
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        bg_color = '#f5f5f5' if i % 2 == 0 else 'white'
        rows.append(html.Tr([
            html.Td(row['id'], style={'padding': '8px', 'backgroundColor': bg_color}),
            html.Td(row['type'], style={'padding': '8px', 'backgroundColor': bg_color}),
            html.Td(row['chrom'], style={'padding': '8px', 'backgroundColor': bg_color}),
            html.Td(f"{row['start']:,} - {row['end']:,}", style={'padding': '8px', 'backgroundColor': bg_color}),
            html.Td(f"{row['length']:,}", style={'textAlign': 'right', 'padding': '8px', 'backgroundColor': bg_color}),
            html.Td([
                html.Div(f"{row['child_count']:,}", style={'fontWeight': 'bold'}),
                html.Div(f"({row['child_pct']:.2f}%)", style={'fontSize': '11px', 'color': '#666'})
            ], style={'textAlign': 'right', 'padding': '8px', 'backgroundColor': bg_color, 'color': UCONN_NAVY}),
            html.Td([
                html.Div(f"{row['mother_count']:,}"),
                html.Div(f"({row['mother_pct']:.2f}%)", style={'fontSize': '11px', 'color': '#666'})
            ], style={'textAlign': 'right', 'padding': '8px', 'backgroundColor': bg_color, 'color': '#CC3366'}),
            html.Td([
                html.Div(f"{row['father_count']:,}"),
                html.Div(f"({row['father_pct']:.2f}%)", style={'fontSize': '11px', 'color': '#666'})
            ], style={'textAlign': 'right', 'padding': '8px', 'backgroundColor': bg_color, 'color': '#3366CC'}),
            html.Td([
                html.Div(f"{row['background_count']:,}"),
                html.Div(f"({row['background_pct']:.2f}%)", style={'fontSize': '11px', 'color': '#666'})
            ], style={'textAlign': 'right', 'padding': '8px', 'backgroundColor': bg_color, 'color': '#669900'})
        ]))
    
    table_body = [html.Tbody(rows)]
    
    table = html.Table(
        table_header + table_body,
        style={
            'borderCollapse': 'collapse',
            'width': '100%',
            'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
            'borderRadius': '5px',
            'overflow': 'hidden'
        }
    )
    
    return html.Div([
        html.P('This table shows the top 20 most frequent SVs in children ranked by absolute count. For each category (Child, Mother, Father, Background), both the raw count and percentage (in parentheses) are displayed.', 
               style={'marginBottom': '15px', 'fontStyle': 'italic'}),
        table
    ])

@callback(
    Output('top-svs-chart', 'figure'),
    Input('url', 'pathname')
)
def update_top_svs_chart(pathname):
    """Update top SVs chart"""
    df = get_top_svs_by_category()
    if df is None:
        return {}
    
    # Create a melted dataframe for the chart
    chart_df = pd.melt(
        df,
        id_vars=['id', 'type', 'chrom'],
        value_vars=['child_count', 'mother_count', 'father_count', 'background_count'],
        var_name='category',
        value_name='count'
    )
    
    # Clean up category names
    chart_df['category'] = chart_df['category'].str.replace('_count', '').str.capitalize()
    
    # Create a composite label for each SV that includes type and chromosome
    chart_df['sv_label'] = chart_df['id'] + ' (' + chart_df['type'] + ', ' + chart_df['chrom'] + ')'
    
    # Define a custom color map for categories
    color_map = {
        'Child': UCONN_NAVY,       # Navy color for children
        'Mother': '#CC3366',       # Pink/rose color for mothers
        'Father': '#3366CC',       # Blue color for fathers
        'Background': '#669900'    # Green color for background
    }
    
    # Create the grouped bar chart
    fig = px.bar(
        chart_df,
        x='sv_label',
        y='count',
        color='category',
        barmode='group',
        title='Top 20 Most Frequent SVs in Children by Count (with comparison to other categories)',
        labels={
            'sv_label': 'Structural Variation',
            'count': 'Count (absolute number)',
            'category': 'Category'
        },
        color_discrete_map=color_map,
        height=600  # Increase height for better visibility
    )
    
    # Improve layout
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(t=80, b=120),  # Add more bottom margin for x-axis labels
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
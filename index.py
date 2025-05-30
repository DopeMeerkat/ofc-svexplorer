"""
Main routing and layout for the UCONN OFC SV Browser application.
"""

from dash import html, dcc, Input, Output, State, callback
import traceback
import sqlite3

from app import app
from components.header import create_uconn_header
from components.footer import create_uconn_footer
from utils.styling import uconn_styles
from utils.database import get_gene_by_id, DB_PATH

# Import pages
from pages import summary
from pages import genome_browser
from pages import table
from pages import image_pages
from pages import network
from pages import circos
from pages import family_genomes

# Define the app layout with components
def layout():
    """
    Create the main app layout with header, content area, and footer
    
    Returns:
        dash.html.Div: Main app layout
    """
    return html.Div([
        create_uconn_header(),
        dcc.Location(id='url', refresh=False),
        dcc.Store(id='selected-gene', data=None),
        html.Div(id='page-content'),
        create_uconn_footer()
    ], style={**uconn_styles['page'], 'margin': '0', 'padding': '0'})

app.layout = layout()

# Main routing callback
@callback(
    Output('page-content', 'children'),
    Output('main-tabs', 'value'),
    Input('url', 'pathname'),
    State('selected-gene', 'data')
)
def display_page(pathname, selected_gene):
    """
    Display the appropriate page based on URL path and selected gene
    """
    print(f"\n=== DISPLAY_PAGE DEBUG ===")
    print(f"Pathname: {pathname}")
    print(f"Selected gene: {selected_gene}")
    
    # Special case for the family page - don't redirect when coming from the family page
    # even if a gene is selected
    if pathname == '/family':
        return family_genomes.page_layout(selected_gene=selected_gene), '/family'
        
    # If a gene is selected and the URL is changing to the genome browser ('/')
    if selected_gene and pathname == '/':
        # Query the database for the gene details
        try:
            # Get the 'Gene' value from the selected_gene data
            gene_id = selected_gene.get('Gene', '')
            
            # Make sure we have a valid gene ID
            if not gene_id:
                print("ERROR: No valid gene ID found in selected_gene data")
                print(f"Selected gene data: {selected_gene}")
                return genome_browser.page_layout(), '/'
                
            print(f"Selected gene: {gene_id}")
            print(f"Full selected_gene data: {selected_gene}")
            
            # Get gene details from database
            gene_dict = get_gene_by_id(gene_id)
            
            if gene_dict:
                print(f"Redirecting to genome browser with gene: {gene_dict}")
                return genome_browser.page_layout(selected_gene=gene_dict), '/'
            else:
                print(f"No gene found with ID: {gene_id}")
                return genome_browser.page_layout(), '/'
                
        except Exception as e:
            print(f"Error loading gene from db: {e}")
            traceback.print_exc()
            return genome_browser.page_layout(), '/'
    
    # Handle normal page routing
    if pathname == '/table':
        return table.page_layout(), '/table'
    if pathname == '/':
        # When navigating directly via tab, don't pass any gene
        return genome_browser.page_layout(), '/'
    if pathname == '/image1':
        return image_pages.image1_page(), '/image1'
    if pathname == '/image2':
        return image_pages.image2_page(), '/image2'
    if pathname == '/image3':
        return image_pages.image3_page(), '/image3'
    if pathname == '/image4':
        return image_pages.image4_page(), '/image4'
    if pathname == '/network':
        return network.page_layout(), '/network'
    if pathname == '/circos':
        return circos.page_layout(), '/circos'
    if pathname == '/family':
        # Always pass selected_gene to family genomes page, it will handle it internally
        return family_genomes.page_layout(selected_gene=selected_gene), '/family'
    # Default and /summary
    return summary.page_layout(), '/summary'

# Callback to update the URL when a tab is clicked
@callback(
    Output('url', 'pathname', allow_duplicate=True),
    Output('selected-gene', 'data', allow_duplicate=True),
    Input('main-tabs', 'value'),
    prevent_initial_call=True
)
def update_url_from_tab(tab_value):
    """
    Update URL when a tab is clicked and clear gene selection
    """
    # When using tab navigation, clear any previously selected gene
    return tab_value, None

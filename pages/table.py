"""
Table page for the UCONN OFC SV Browser application.
"""

from dash import html, dash_table, Input, Output, State, callback, no_update
from utils.styling import UCONN_NAVY, UCONN_LIGHT_BLUE, uconn_styles
from utils.database import load_table_data

def page_layout():
    """
    Create the table page layout
    
    Returns:
        dash.html.Div: Table page layout
    """
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

# Callback to handle gene table row selection
@callback(
    Output('selected-gene', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('gene-table', 'active_cell'),
    State('gene-table', 'data'),
    prevent_initial_call=True
)
def store_selected_gene_and_redirect(active_cell, table_data):
    """
    Handle selection of a gene from the table
    """
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

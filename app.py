"""
Main application entry point for UCONN OFC SV Browser.
This file initializes the Dash application and server.
"""

from dash import Dash
from utils.database import load_genomes_from_db, DB_PATH

# Create the Dash application instance
app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        'https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap',
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css'
    ]
)

# Configure the application
app.title = "UCONN OFC SV Browser"

# Load genome information from database
HOSTED_GENOME_DICT = load_genomes_from_db(DB_PATH)

# Export the server variable for WSGI deployment
server = app.server

# Import the views after initializing the app to avoid circular imports
# This uses the index.py as the router
if __name__ == '__main__':
    from index import *
    
    app.run_server(debug=True, host='0.0.0.0', port=8003)

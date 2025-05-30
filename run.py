"""
Runner script for the UCONN OFC SV Browser application.
"""

from app import app, server
from index import *

if __name__ == '__main__':
    
    app.run_server(debug=True, host='0.0.0.0', port=19530)

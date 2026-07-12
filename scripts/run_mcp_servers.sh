#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

PYTHONPATH=. python mcp_servers/ofc_db_server.py &
DB_PID=$!

PYTHONPATH=. python mcp_servers/ofc_visualization_server.py &
VIS_PID=$!

PYTHONPATH=. python mcp_servers/ofc_overlap_server.py &
OVERLAP_PID=$!

PYTHONPATH=. python mcp_servers/ofc_discovery_server.py &
DISCOVERY_PID=$!

trap "kill $DB_PID $VIS_PID $OVERLAP_PID $DISCOVERY_PID 2>/dev/null || true" EXIT

echo "Started MCP servers:"
echo "  DB:            http://127.0.0.1:8101/mcp"
echo "  Visualization: http://127.0.0.1:8102/mcp"
echo "  Overlap:       http://127.0.0.1:8103/mcp"
echo "  Discovery:     http://127.0.0.1:8104/mcp"

wait
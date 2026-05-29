#!/usr/bin/env bash
set -euo pipefail

python mcp_servers/ofc_db_server.py &
DB_PID=$!

python mcp_servers/ofc_visualization_server.py &
VIZ_PID=$!

trap "kill ${DB_PID} ${VIZ_PID}" EXIT

wait

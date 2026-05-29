# MCP Architecture

This project supports an optional MCP-based architecture for the AI Query page. MCP is disabled by default and can be enabled with environment variables.

## Overview

```
Dash AI Query page
    ↓
AI Query orchestrator
    ↓
MCP client manager
    ├── DB MCP server
    └── Visualization MCP server
```

- The Dash app is the MCP host.
- MCP servers are deterministic and do not call LLMs.
- The orchestrator and agents handle all LLM calls.

## Processes and Ports

- Dash app: 127.0.0.1:8002
- DB MCP server: 127.0.0.1:8101
- Visualization MCP server: 127.0.0.1:8102
- Ollama: 127.0.0.1:11434

## Feature Flags

```
MCP_ENABLED=false
MCP_TRANSPORT=http
MCP_DB_SERVER_URL=http://127.0.0.1:8101/mcp
MCP_VIZ_SERVER_URL=http://127.0.0.1:8102/mcp
MCP_TIMEOUT_SECONDS=30
```

## Tools

### DB MCP
- health_check
- get_supported_query_capabilities
- validate_select_sql
- execute_readonly_sql
- explain_query_plan
- summarize_result_shape

### Visualization MCP
- health_check
- get_supported_visualizations
- recommend_visualization
- build_bar_chart_spec
- build_table_spec
- build_igv_gene_view_spec

## Local Run

```
python mcp_servers/ofc_db_server.py
python mcp_servers/ofc_visualization_server.py
MCP_ENABLED=true python run.py
```

## Fallback Behavior

When MCP is disabled or unavailable, the AI Query page continues using the direct SQL flow.

## Security Restrictions

- Read-only SQL execution only.
- Reject non-SELECT or multi-statement SQL.
- Reject schema-changing or write statements.
- Visualization tools do not execute SQL.
- MCP servers bind only to 127.0.0.1.

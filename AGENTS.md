# AGENTS.md

## Project Context

This is an internal UConn research dashboard for OFC/SV analysis. The app is a Dash-based web portal backed by a local SQLite database and several local MCP-style HTTP servers. The current goal is to extend the AI Query/MCP system so the LLM can discover and call additional analysis tools, such as random forest, decision tree, information gain, overlap analysis, visualization, and future compute-heavy scripts.

The project is currently deployed on a school VM machine. Treat this as a server environment, not a local-only laptop setup. Deployment may involve `systemctl`, `nginx`, long-running processes, and ports proxied by nginx. Do not assume Docker, Kubernetes, Slurm, or cloud infrastructure unless explicitly introduced.

The next intended architecture is **local discovery first**: simulate multiple external compute machines on the same VM before supporting actual remote machines. Create a project subdirectory that acts like a separate "machine" or worker node, with its own tools/scripts and metadata. The main app/MCP broker should discover tools from that local simulated worker before expanding to real networked desktops or lab machines.

## Commands

* Start the normal Dash app with:

  ```bash
  python run.py
  ```

  `run.py` imports `app.py` and `index.py` and serves on `0.0.0.0:8002`.

* `python app.py` is a secondary/debug path that serves on port `8003`; do not assume it is the normal runner.

* Start MCP servers individually with:

  ```bash
  PYTHONPATH=. python mcp_servers/ofc_db_server.py
  PYTHONPATH=. python mcp_servers/ofc_visualization_server.py
  PYTHONPATH=. python mcp_servers/ofc_overlap_server.py
  PYTHONPATH=. python mcp_servers/ofc_discovery_server.py
  ```

* The MCP Query page (`/mcp-query`) provides a UI to upload datasets, get LLM tool recommendations, and run discovered tools through the discovery MCP server.
* Discovered tools are located under `discovered_workers/local_worker_01/tools/`:
  * `echo_analysis` — dummy tool for pipeline testing
  * `information_gain` — compute information gain for features against a target
  * `random_forest` — train a random forest classifier with feature importance
  * `decision_tree` — train a decision tree classifier with feature importance
* Start all MCP servers with:

  ```bash
  scripts/run_mcp_servers.sh
  ```

  This starts all four MCP servers and kills them together on exit.

* Verify the discovery MCP server independently with:

  ```bash
  PYTHONPATH=. python scripts/test_discovery_mcp_server.py
  ```

  (Requires the discovery MCP server to be running on port 8104.)

* There is no verified root `requirements.txt`, `pyproject.toml`, lint config, or pytest config in this checkout; do not invent package-manager commands.

* Avoid adding new dependency-management assumptions unless the user explicitly asks for them.

## Deployment Environment

* The app is intended to run on a school VM/server.
* The VM may use `systemctl` services for long-running app/MCP processes.
* The VM may use `nginx` as a reverse proxy in front of the Dash app.
* Do not casually change ports, host bindings, nginx assumptions, or service behavior without explaining the impact.
* Prefer changes that work when launched from the project root with `PYTHONPATH=.`.
* If adding long-running worker/discovery processes, make them runnable manually first before assuming systemd integration.
* Do not require production database access for basic app startup, metadata discovery, or tool registration logic.

## App Structure

* `app.py` creates the Dash app/server and local IGV reference routes.
* `index.py` owns layout routing and imports page modules from `pages/`.
* Main pages live under `pages/`.
* Shared header/footer/search components live under `components/`.
* `utils/database.py` is the active database utility module.
* `utils/database_ai_query.py` appears duplicative/stale unless a caller explicitly imports it.
* `main.py` is a large older standalone Dash app path; prefer `run.py` + `app.py` + `index.py` when changing the current app.

## Data And Secrets

* The SQLite database path is hard-coded as:

  ```text
  /data/cellvar.db/cellvar.db
  ```

  in active code.

* Keep cohort data/internal access assumptions intact.

* README identifies this as an internal UConn research dashboard.

* `api_key.txt` is gitignored and used by `utils/openai_client.py`.

* Do not read, print, expose, or commit `api_key.txt`.

* Do not move sensitive database access into worker scripts unless explicitly requested.

* For distributed/discovered tools, prefer passing analysis-ready CSV/parquet inputs or dataset IDs rather than giving workers unrestricted database access.

## AI Query And MCP

* `pages/ai_query.py` currently defaults `MCP_ENABLED` to true unless `MCP_ENABLED=false` is set.
* MCP is currently implemented as local stdlib HTTP servers on `127.0.0.1`:

  * DB MCP server: `8101`
  * Visualization MCP server: `8102`
  * Overlap MCP server: `8103`
  * Discovery MCP server: `8104`
* Clients call the `/mcp` endpoint.
* MCP servers should stay deterministic.
* LLM calls belong in `agents/`, page/orchestrator code, or a broker/orchestration layer, not inside `mcp_servers/`.
* AI Query schema rules are duplicated in:

  * `pages/ai_query.py`
  * `agents/db_agent.py`
* Update both if changing query behavior.
* SQL execution must remain read-only through `utils.database.run_readonly_query` and/or MCP validation.
* Do not let the LLM generate arbitrary shell commands or unchecked SQL.
* Tool calls should use validated schemas, fixed entrypoints, and controlled parameters.

## Planned Tool Discovery Architecture

The next implementation direction is to add discoverable analysis tools. Start with a **same-machine simulation** before supporting real external machines.

Recommended first step:

```text
project_root/
  discovered_workers/
    local_worker_01/
      worker.yaml
      tools/
        random_forest/
          tool.yaml
          README.md
          run.py
        information_gain/
          tool.yaml
          README.md
          run.py
```

This `discovered_workers/local_worker_01/` directory should act as a stand-in for another desktop or compute machine.

The goal is not yet true remote networking. The goal is to prove:

1. A worker can describe itself.
2. A worker can expose tool metadata.
3. The main app/broker can discover the worker.
4. The LLM can see approved tools.
5. A selected tool can be invoked with validated inputs.
6. Results can be returned in a structured format.

Use machine-readable metadata such as YAML or JSON for tool definitions. Markdown can be used for human-readable documentation, but should not be the only source of tool metadata.

Prefer a metadata file like:

```text
tool.yaml
```

with fields such as:

```yaml
id: random_forest
version: 1.0.0
display_name: Random Forest Classifier
description: Train a random forest model on an analysis-ready phenotype-feature matrix.
entrypoint:
  command: python run.py
inputs:
  dataset_path:
    type: file
    required: true
  phenotype_column:
    type: string
    required: true
outputs:
  metrics:
    path: metrics.json
    type: json
  feature_importance:
    path: feature_importance.csv
    type: csv
constraints:
  requires_gpu: false
  max_runtime_seconds: 1800
```

Do not expose arbitrary scripts directly to the LLM. Expose curated tools through a registry/broker layer.

## Discovery Design Principles

* Use a central registry or broker pattern.
* The OFC website/LLM should talk to a central MCP/broker interface.
* The broker should discover approved worker directories and tools.
* Workers should not directly receive arbitrary LLM-generated commands.
* The broker should validate:

  * tool ID
  * tool version
  * input schema
  * allowed file paths
  * output directory
  * timeout/runtime constraints
* Start with synchronous execution only if tools are fast.
* For longer computations, design toward job IDs:

  * `submit_analysis_job`
  * `get_job_status`
  * `get_job_results`

The target architecture is:

```text
OFC Website / AI Query
        ↓
Central MCP/Broker Layer
        ↓
Tool Registry / Discovery
        ↓
Simulated Local Worker Directory
        ↓
Validated Script Execution
        ↓
Structured Results
```

Later, this can become:

```text
OFC Website / AI Query
        ↓
Central MCP/Broker Layer
        ↓
Registered Remote Workers
        ↓
Validated Script Execution
        ↓
Structured Results
```

but do not jump to real remote machines before the local simulation works.

## Worker/Tool Execution Rules

* Tools should accept explicit input paths and output directories.
* Tools should write outputs into a job-specific result directory.
* Prefer structured outputs:

  * `metrics.json`
  * `results.csv`
  * `feature_importance.csv`
  * `stdout.log`
  * `stderr.log`
  * plots under `plots/`
* Do not require direct access to `/data/cellvar.db/cellvar.db` unless the tool is explicitly a database tool.
* Prefer analysis-ready matrices generated by the main app or existing database utilities.
* Do not execute unchecked shell strings.
* Use `subprocess.run([...])` with argument lists if invoking scripts.
* Add timeouts for tool execution.
* Keep tool metadata deterministic and easy to inspect.

## Current Analysis Direction

Relevant analysis scripts/tools may include:

* information gain over SV/gene/pathway feature matrices
* random forest classification
* decision tree classification and visualization
* feature importance ranking
* phenotype/SV subset analysis
* de novo SV analysis
* inherited SV analysis
* exon-overlap analysis
* two-hit or gene-pair analysis
* pathway/Reactome/GO summarization
* Manhattan-style p-value visualizations

When adding new tools, prefer building around existing project concepts:

* samples as rows
* SVs/genes/pathways/features as columns
* phenotype or case/control label as the target column
* optional subset CSVs, such as de novo SV lists
* output files that the Dash app can display or download

## Tests And Verification

* Existing `assets/test_*.py` files are standalone scripts, not configured pytest tests.
* Avoid verification that requires the production database unless `/data/cellvar.db/cellvar.db` exists.
* For discovery/tool registry work, create small dummy metadata and dummy input files so tests can run without the production database.
* For worker simulation, verify:

  * worker metadata loads
  * tool metadata loads
  * invalid metadata fails cleanly
  * approved tool can be listed
  * simple dummy tool can run
  * output directory is created
  * structured result files are produced

## Development Style

* Prefer small, incremental changes.
* Do not rewrite the existing app architecture unless necessary.
* Keep current Dash app entrypoint behavior intact.
* Keep current local MCP servers working.
* Add discovery as a parallel/extension layer first, not as a replacement for the existing MCP servers.
* Preserve read-only database safety.
* Avoid hidden dependency additions.
* Avoid code that only works on one personal laptop path.
* Assume the project may be run from a server shell, systemd service, or nginx-backed deployment.

## Important Do-Not-Do Items

* Do not read or print `api_key.txt`.
* Do not commit secrets.
* Do not make SQL write-capable from AI Query.
* Do not let the LLM execute arbitrary shell commands.
* Do not assume the production database exists during lightweight verification.
* Do not replace `run.py` as the normal Dash app entrypoint.
* Do not treat `main.py` as the active app unless explicitly instructed.
* Do not expose unapproved discovered scripts as MCP tools.
* Do not jump directly to real remote personal desktops before implementing local simulated-worker discovery.

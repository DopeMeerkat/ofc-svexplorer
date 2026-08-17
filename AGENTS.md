# AGENTS.md

## Project Context

This is an internal UConn research dashboard for OFC/SV analysis. The app is a Dash-based web portal backed by a local SQLite database and several local MCP-style HTTP servers. The current goal is to extend the AI Query/MCP system so the LLM can discover and call additional analysis tools, such as random forest, decision tree, information gain, overlap analysis, visualization, and future compute-heavy scripts.

The project is currently deployed on a school VM machine. Treat this as a server environment, not a local-only laptop setup. Deployment may involve `systemctl`, `nginx`, long-running processes, and ports proxied by nginx. Do not assume Docker, Kubernetes, Slurm, or cloud infrastructure unless explicitly introduced.

The project is being prepared as a final publication-facing version. Specific sample IDs are sensitive and must not be displayed in the UI, logs, downloadable publication views, screenshots, or other user-facing outputs unless the user explicitly requests an internal-only exception. Prefer aggregate counts, anonymized labels, row numbers, or other non-identifying display values when sample-level data is needed.

The publication-facing navigation should be reduced to these tabs/pages only: Summary, Database Overview, Table Inspection, IGV/Population, Pathway, and Case Study. The IGV/Population tab corresponds to the current Population SV functionality. The Family SV page exists in code and is useful internally, but do not include it in publication-facing documentation unless the user explicitly asks for internal/development material.

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

## Recent Session Context

These are current project decisions and implementation details from the latest publication-polish work:

* `README.md` was rewritten as a practical user guide similar in tone/structure to `README_example1.md`. It documents Summary, Database Overview, Table Inspection, IGV/Population, Pathway, and Case Study. It intentionally does not document Family SV.
* The Case Study page (`pages/case_study.py`) is currently a flat, grouped report-style page using the standard site content container. Do not restore separate rounded card/bubble sections. Thin horizontal dividers were removed at the user's request.
* Population SV (`pages/population_svs.py`) optional annotation tracks now load for the entire selected chromosome, even when IGV jumps to a selected gene/SV locus. This differs intentionally from Family SV.
* Family SV (`pages/family_genomes.py`) optional annotation tracks are interval-limited. If both a gene and an SV are selected, the IGV viewport should jump to the gene location while annotation tracks may include both the gene interval and SV interval. Existing family tracks should remain unchanged.
* Family SV supports URL deep-linking. `/family?family=<Family_ID>&chrom=chrN&start=<int>&end=<int>` prefills the family dropdown, the hidden chromosome select, and the active locus. `pages/family_genomes.py` parses this via `_parse_search(search)` and `page_layout(selected_gene, search)`; `index.py` must pass `search` to the family page (there is an early `/family` handler in `display_page` that must also forward `search`).
* The family IGV viewport uses `_gene_locus_from_selection`, which preserves a `locus` type for URL-prefilled coordinates. Viewport buffers: 50,000 bp for a URL-prefilled `locus`, 5,000 bp for a gene, 1,000 bp for a searched SV.
* `update_family_igv_browser` intentionally has no `prevent_initial_call` so a URL prefill auto-loads IGV on page load; the body already no-ops when `n_clicks=0`.
* Family SV optional annotation tracks load from a 100,000 bp buffer around the active gene/SV intervals via `_expand_loci(loci, buffer_bp=100000)`, so enhancer, exon, promoter, insulator, and cCRE tracks include flanking context. Do not confuse this with the Population page, which loads annotation tracks chromosome-wide.
* Enhancer candidate tracks should be OFC-relevant only. The selected `cell` labels are `MESENCHYMAL` and `NEURALCREST` for `poised_enhancer_candidates` and `active_enhancer_candidates`.
* The active database tables were trimmed in place after backup copies were created:
  * `poised_enhancer_candidates_backup` keeps the original full poised enhancer table.
  * `active_enhancer_candidates_backup` keeps the original full active enhancer table.
  * `noccl_cCREs_backup` keeps the active cCRE table as it existed before the latest trim operation.
  * Active `poised_enhancer_candidates` now contains only `MESENCHYMAL` and `NEURALCREST` rows.
  * Active `active_enhancer_candidates` now contains only `MESENCHYMAL` and `NEURALCREST` rows.
  * Active `noccl_cCREs` is limited to `dELS`, `pELS`, and `PLS`; this was already true before the latest trim.
* Indexes were added for faster IGV overlap queries:
  * `idx_poised_enhancer_candidates_cell_chrom_start_end`
  * `idx_active_enhancer_candidates_cell_chrom_start_end`
  * `idx_noccl_cCREs_type_chrom_start_end`
  * `idx_noccl_cCREs_chrom_start_end`
* Exon tracks are collapsed at query/display time, not by rewriting the `exons` table. This preserves transcript-level exon rows in the database but renders one feature per `gene_id`, chromosome, start, end, and strand. Tooltips list transcript count, transcript IDs, exon numbers, strand, and source. This affects shared Population exon tracks in `utils/database.py` and Family SV local exon tracks in `pages/family_genomes.py`.
* Example exon behavior verified during the session: `KCNQ5` exon 4 at `chr6:73077321-73077497` appears once as `KCNQ5 exon (5 transcripts)` instead of five stacked transcript features.
* Example locus check verified during the session: `KHDC3L` lies near the early/start side of `C_255108` (`chr6:73356293-73500501`), starting about 6.4 kb after the SV start.
* `exploration/build_master_list.py` appends a `Family_IGV_Link` column to `MasterList.csv` (in addition to the existing Population `IGV_Link`). Each link is a full URL in the form `http://ofc-svexplorer.cardinal.engr.uconn.edu/family?family=<Family_ID>&chrom=chrN&start=<int>&end=<int>` and pairs with the Family SV URL prefill above.

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

## Case Studies (local-only)

* The Case Study page (`pages/case_study.py`) renders curated content from JSON files in the committed `case_studies/` folder managed by `utils/case_studies.py`. Content is local-only: there is no OneDrive/rclone refresh.
* Case-study files live in `case_studies/` (committed to Git) so they travel with the repo when pushed/pulled. This includes per-gene `*.json` files plus the optional `SUMMARY.xlsx`/`SUMMARY.csv`.
* `utils.case_studies.cache_dir()` defaults to `case_studies/` and can be overridden with `CASE_STUDY_CACHE_DIR` via `os.environ` or the gitignored `rclone/.env` file.
* `rclone/.env.example` is committed as a template; `rclone/.env` and `rclone/cache/` are gitignored. Do not commit the real OneDrive remote path.
* JSON schema: top-level `title` and `sections` are required; `genes` is optional. The case-study key is the JSON filename stem (a file `X.json` is keyed as `X`, so name files `<key>.json`). A top-level `id` field is NOT used — do not add one. Each section has a `heading` and optional `paragraphs`; a paragraph item is a plain string or `{text, links, suffix}` where `links` is a list of `{label, href}`. Sections may include a `table` with `columns` and `rows`. When `text`/`links`/`suffix` are concatenated, the author controls spacing (e.g. end `text` with a trailing space before a link).
* A built-in fallback named `TET3-local` renders the original hard-coded TET3 content (with live DB supporting-data query) when no local JSON is available.
* JSON files that fail to parse/validate are skipped from the dropdown; `utils.case_studies.invalid_study_files()` lists them and the page shows a warning (with the filename and parse reason) above the case-study content.
* A curated gene summary can be placed in `case_studies/` as `SUMMARY.xlsx` (preferred) or `SUMMARY.csv`. `utils.case_studies.load_case_study_summary()` reads it (xlsx via the dependency-free `utils/xlsx_reader.py`) and returns `{file, columns, rows}` or `None`. When present, the Case Study page renders it as the first sub-tab (`Summary Table`); the second sub-tab (`Case Studies`) contains the case-study dropdown, warnings, and selected case-study content. `utils/xlsx_reader.py` auto-detects the header row, skipping leading rows with fewer than two non-empty cells (e.g. a merged title row), and supports an explicit 0-based `header_row` override.
* `scripts/convert_case_study_docx.py` converts `Case_Study_*.docx` sources into case-study JSON. It classifies paragraphs by label (`Function`, `IGV`, `Literature`, `Pathway`, `Supporting Data`), synthesizes `{text, links, suffix}` IGV (`/population?gene=<GENE>`) and Pathway (`/pathway?genes=...`) links, puts citation-like paragraphs in a "References" section and other unlabeled text under "EMT"/"Notes", and appends a "Supporting Data" evidence table computed via read-only DB queries (exon/enhancer/promoter overlap at freq <= 0.01) plus a gene-expression finding from `pLI/tab_43_genes.csv`. Run with `PYTHONPATH=. python scripts/convert_case_study_docx.py --input-dir <dir-with-docx>`; it writes `<gene>.json` into the committed `case_studies/` folder by default. The optional `--remote` flag uploads the generated JSONs + `SUMMARY.*` to OneDrive as a manual backup only (not pulled back). The resulting JSON for a gene named `TET3` overwrites the local `case_studies/TET3.json`.
* Table Inspection marks genes with available case studies by appending `*` in the `Gene` column and shows a note above the table. Clicking a marked gene opens the existing navigation modal with an additional `Open Case Study` action, which routes to `/case-study?case=<gene>&tab=case-studies`.

## Pathway Networks And rclone

* The Pathway page (`pages/pathway.py`) loads its edges/nodes from a local cache managed by `utils/pathway_networks.py`, with a "Network version" dropdown (e.g. Baseline, Extended1, Extended2) and a Refresh button that runs `rclone sync`.
* Each version is a subdirectory of the configured OneDrive pathway folder. Within a directory the first CSV whose filename starts with `edges` is used as the edge table and the first starting with `nodes` as the node table; any other CSVs (e.g. `go_gene_annotations.csv`) are ignored.
* Local cache defaults to `rclone/cache/pathway_networks/` (gitignored). Sync is restricted to `*.csv` and mirrors the remote, so local CSVs not on OneDrive are deleted; non-CSV files are left untouched.
* Configuration is env-driven via `os.environ` or the gitignored `rclone/.env` file:
  * `PATHWAY_RCLONE_BIN` (defaults to `CASE_STUDY_RCLONE_BIN`, else `rclone`)
  * `PATHWAY_RCLONE_REMOTE` (e.g. `uconn:.../Data/Pathway`); empty means refresh is disabled
  * `PATHWAY_CACHE_DIR` (default `rclone/cache/pathway_networks`)
  * `PATHWAY_REFRESH_TIMEOUT_SECONDS` (default `120`)
* If the cache is empty or unconfigured, `list_versions()` falls back to the bundled `pathway/edges_e.csv`/`nodes_e.csv` (Baseline) and `pathway/edges_v1.csv`/`nodes_v1.csv` (Extended1) so the page still renders.
* `utils.pathway_networks` redacts the remote path and cache dir from error messages. Network versions are loaded lazily and cached in `pages/pathway.py` (`_NETWORK_CACHE`, cleared on Refresh). GO annotations are still read from the local `pathway/go_gene_annotations.csv`.

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

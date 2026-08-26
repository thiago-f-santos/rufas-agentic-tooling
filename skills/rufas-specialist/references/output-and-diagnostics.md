# RuFaS Output Pools, Filter Routing, and Error Diagnostics

## 1. Output Architecture (`OutputManager`)

RuFaS structures runtime output into two distinct pool types:

### A. Data Pools (`variables_pool`)
- **Contents**: All time-series simulation variables registered via `OutputManager.add_variable()`.
- **Memory Optimization**: Features **Chunkification** (`chunkification=True`), writing temporary binary or text chunks to disk when memory usage thresholds are reached, then reassembling them during post-processing.
- **Export Control**: RuFaS does **not** dump variables by default. Export is strictly governed by filter files residing in `output/output_filters/` matching designated filename prefixes:
  - `csv_*` $\rightarrow$ Triggers CSV variable matrix export.
  - `json_*` $\rightarrow$ Triggers JSON variable export.
  - `graph_*` $\rightarrow$ Generates graphical plots (unless `-g / --no-graphics` is set).
  - `report_*` $\rightarrow$ Generates formatted PDF/text summary reports.

### B. Non-Data Pools (`logs_pool`, `warnings_pool`, `errors_pool`)
- **Contents**: Operational trace messages, input validation notices, non-fatal warnings, and terminal exception stack traces.
- **Export**: Always written to disk upon run termination into `output/logs/`:
  - `output/logs/errors.txt`
  - `output/logs/warnings.txt`
  - `output/logs/logs.txt`
  - `output/logs/variable_names_and_contexts.txt`
  - `output/logs/variables_usage_counts.txt`

---

## 2. Common RuFaS Diagnostic Scenarios & Fixes

### Scenario A: Empty Output Folder (No CSV files generated)
- **Root Cause**: No active filter file starting with `csv_` exists in `output/output_filters/`.
- **Fix**: Rename `output/output_filters/_csv_all_variables.txt` to `output/output_filters/csv_all_variables.txt` (or run `python -m tools.rufas_runner --enable-all-csv`).

### Scenario B: Early Termination / `RuntimeError: Dump all logs from main.py`
- **Root Cause**: Unhandled exception during daily loop or input parsing.
- **Diagnostic Step**: Open `output/logs/errors.txt`. Inspect the bottom stack trace for the failing module (`HerdManager`, `FieldManager`, `ManureManager`, or `InputManager`).
- **Common Triggers**:
  1. *Negative Soil Water Content*: Extreme dry weather causing matrix potential solvers to diverge. Check rainfall and soil wilting point parameters in `soil/*.json`.
  2. *Infeasible Ration LP*: Dietary constraints (e.g. min forage NDF or max fat) cannot be satisfied with available feedstuffs. Check `user_feeds.json` or relax dietary bounds in `animal_general.json`.
  3. *Manure Capacity Overflow*: Liquid pit volume exceeded without scheduled land application events in `manure_schedule/*.json`.

### Scenario C: Cross-Validation Failure at Startup
- **Root Cause**: Relational constraint violation detected by `CrossValidator`.
- **Fix**: Review console output or `output/logs/errors.txt`. Adjust the offending data file parameter (e.g. align weather date range or adjust feed storage dry matter bounds) using `python -m tools.rufas_inspector`.

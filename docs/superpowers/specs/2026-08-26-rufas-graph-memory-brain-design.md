# RuFaS Graph Memory Brain & Cross-Module Correlation Engine Design Specification

## 1. Executive Summary & Purpose

RuFaS whole-farm simulations involve 22 input configuration files, complex multi-module biophysical exchanges, and 2,038 output time-series variables. Finding relationships between model inputs and downstream outputs (e.g. how ration composition affects lagoon emissions) currently requires manual parsing of disconnected files.

This project introduces **RuFaS Graph Memory Brain**:
1. An embedded property graph database using **KùzuDB** (`kuzu`) queryable via OpenCypher / GQL.
2. A dual-layer knowledge graph capturing:
   - **Structural/Domain Layer**: Canonical input parameters, output variables (with units & descriptions), and biophysical causal impact pathways.
   - **Empirical Simulation Layer**: Multi-run ingestion, run-level summary metrics, and automated Pearson/Spearman statistical correlation edges.
3. An **On-Demand Obsidian Exporter** generating an interconnected Markdown knowledge vault with Dataview DQL query blocks and graph visual links for human exploration.
4. A dedicated **AI Agent Skill (`rufas-brain-specialist`)** enabling agents to navigate the knowledge graph, trace impact pathways, and offload raw metadata dictionary lookups from domain specialist skills.

---

## 2. Goals and Non-Goals

### Goals
- **Embedded Zero-Server Storage**: Fast local property graph database stored in `data/rufas_brain.kuzu/` with zero server infrastructure.
- **Biophysical & Statistical Linkage**: Connect input parameters to output variables via both deterministic causal pathways and empirical correlation edges ($|r| \ge 0.5$, $p < 0.05$).
- **Multi-Run Ingestion**: Ability to ingest sequential or sensitivity analysis simulation runs from `RuFaS/output/` and aggregate performance metrics.
- **OpenCypher & SQL-like Querying**: Rich query interface supporting multi-hop graph pattern matching.
- **Obsidian Vault Bridge**: On-demand generator for interactive human visual navigation, Dataview tables, and component notes.
- **Specialist Skill De-cluttering**: Offload variable dictionary lookups to `rufas-brain-specialist` so domain skills focus on biophysical kinetics and diagnostics.

### Non-Goals
- Real-time graph updates on every sub-millisecond simulation step (ingestion operates at daily/run completion intervals).
- Replacing RuFaS core simulation engine or modifying underlying Fortran/C/Python simulation kernels.
- Cloud database hosting (engine is strictly embedded and locally file-backed).

---

## 3. System Architecture

```
                                  ┌──────────────────────────┐
                                  │   RuFaS Input Metadata   │
                                  │ (22 Configuration Blobs) │
                                  └────────────┬─────────────┘
                                               │
                                               ▼
┌──────────────────────────┐       ┌─────────────────────────┐       ┌──────────────────────────┐
│ RuFaS Simulation Output  ├──────►│   rufas_brain Ingest    │◄──────┤   Domain Causal Rules    │
│ (2,038 CSV Variables)    │       │     & Ingestion CLI     │       │   (Biophysical Pathways) │
└──────────────────────────┘       └───────────┬─────────────┘       └──────────────────────────┘
                                               │
                                               ▼
                                  ┌──────────────────────────┐
                                  │  KùzuDB Embedded Engine  │
                                  │ (data/rufas_brain.kuzu/) │
                                  └──────┬────────────┬──────┘
                                         │            │
                  ┌──────────────────────┘            └──────────────────────┐
                  │                                                          │
                  ▼                                                          ▼
┌──────────────────────────────────┐                       ┌──────────────────────────────────┐
│    Obsidian Vault Exporter       │                       │     rufas-brain-specialist       │
│      (On-Demand Markdown)        │                       │        (AI Agent Skill)          │
│ ├── 01_Simulations/              │                       │ ├── OpenCypher Query Tool        │
│ ├── 02_Parameters/               │                       │ ├── Parameter Impact Tracer      │
│ ├── 03_Outputs/                  │                       │ ├── Correlation Explorer         │
│ └── 04_Correlations/             │                       │ └── Metadata Lookup Engine       │
└──────────────────────────────────┘                       └──────────────────────────────────┘
```

---

## 4. KùzuDB Graph Schema & Data Model

### Node Tables

#### 1. `Module`
- Represents the 5 core biophysical and economic subsystems.
- **Properties**:
  - `name`: STRING (PRIMARY KEY) e.g., `"animal"`, `"field_soil"`, `"feed_storage"`, `"manure"`, `"eee"`
  - `description`: STRING
  - `manager_class`: STRING e.g., `"HerdManager"`, `"FieldManager"`

#### 2. `ConfigBlob`
- Represents the 22 required configuration file blobs declared in scenario metadata.
- **Properties**:
  - `name`: STRING (PRIMARY KEY) e.g., `"animal"`, `"crop_configurations"`, `"feed_storage_instances"`
  - `title`: STRING
  - `file_path`: STRING
  - `description`: STRING
  - `format_type`: STRING (`"json"`, `"csv"`)

#### 3. `InputParameter`
- Represents individual configurable parameters within metadata files.
- **Properties**:
  - `id`: STRING (PRIMARY KEY) e.g., `"animal.herd_information.cow_num"`
  - `blob_name`: STRING
  - `param_name`: STRING
  - `data_type`: STRING (`"int"`, `"float"`, `"string"`, `"bool"`)
  - `unit`: STRING
  - `default_value`: STRING
  - `description`: STRING

#### 4. `OutputVariable`
- Represents the 2,038 time-series output variables generated by RuFaS reporters.
- **Properties**:
  - `name`: STRING (PRIMARY KEY) e.g., `"AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows"`
  - `module`: STRING
  - `unit`: STRING (extracted from parentheses, e.g., `"animals"`, `"kg"`, `"mm"`, `"kg CO2 / kg DM"`)
  - `category`: STRING (`"population"`, `"production"`, `"hydrology"`, `"carbon_pool"`, `"emissions"`)
  - `reporter_class`: STRING

#### 5. `SimulationRun`
- Represents an executed simulation run instance.
- **Properties**:
  - `run_id`: STRING (PRIMARY KEY) e.g., `"freestall_baseline_2026"`
  - `scenario_name`: STRING
  - `execution_date`: STRING (ISO-8601)
  - `start_date`: STRING (e.g., `"2013:1"`)
  - `end_date`: STRING (e.g., `"2013:60"`)
  - `duration_days`: INT64
  - `random_seed`: INT64
  - `status`: STRING (`"completed"`, `"failed"`)

#### 6. `RunMetric`
- Aggregated descriptive statistics for a specific variable in a specific run.
- **Properties**:
  - `id`: STRING (PRIMARY KEY) e.g., `"freestall_baseline_2026::milk_produced_kg"`
  - `run_id`: STRING
  - `var_name`: STRING
  - `mean_val`: DOUBLE
  - `min_val`: DOUBLE
  - `max_val`: DOUBLE
  - `sum_val`: DOUBLE
  - `non_null_count`: INT64

---

### Relationship Tables (Edges)

| Edge Table | From Node | To Node | Properties | Description |
|---|---|---|---|---|
| `CONFIG_OF` | `ConfigBlob` | `Module` | None | Maps config files to their owning biophysical module. |
| `CONTAINS_PARAM` | `ConfigBlob` | `InputParameter` | None | Maps config files to constituent parameters. |
| `CAUSALLY_INFLUENCES` | `InputParameter` | `OutputVariable` | `pathway: STRING`, `mechanism: STRING` | Biophysical causal influence pathway. |
| `SIMULATED_WITH` | `SimulationRun` | `InputParameter` | `value: STRING` | Records parameter value utilized during the run. |
| `GENERATED_METRIC` | `SimulationRun` | `RunMetric` | None | Links run to its output metric statistics. |
| `OF_VARIABLE` | `RunMetric` | `OutputVariable` | None | Links metric record to canonical variable node. |
| `CORRELATES_WITH` | `InputParameter` | `OutputVariable` | `pearson_r: DOUBLE`, `spearman_r: DOUBLE`, `p_value: DOUBLE`, `sample_size: INT64` | Empirical statistical correlation across multiple runs. |

---

## 5. Statistical Correlation Engine

When `rufas_brain compute-correlations` is invoked:
1. For every pair of `(InputParameter, OutputVariable)` across all ingested `SimulationRun` records ($N \ge 3$ runs with parameter variation):
2. Form numeric vectors $X = [x_1, x_2, \dots, x_N]$ (parameter values) and $Y = [y_1, y_2, \dots, y_N]$ (output metric mean values).
3. Compute:
   - **Pearson correlation coefficient ($r$)**: Measures linear relationship.
   - **Spearman rank correlation ($\rho$)**: Measures monotonic non-linear relationship.
   - **Two-tailed p-value**: Evaluates statistical significance.
4. If $|r| \ge 0.5$ or $|\rho| \ge 0.5$ with $p \le 0.05$, create or update edge `[:CORRELATES_WITH {pearson_r: r, spearman_r: rho, p_value: p, sample_size: N}]`.

---

## 6. Obsidian Vault Exporter (`export-obsidian`)

The on-demand exporter writes an Obsidian-compatible vault directory with the following structure:

```
vault/
├── 00_Dashboard.md                   # Top-level index with Dataview overview tables
├── 01_Simulations/
│   └── <run_id>.md                   # Run summary, parameters used, top metrics, links
├── 02_Input_Parameters/
│   └── <param_id>.md                 # Parameter spec, default value, influenced outputs
├── 03_Output_Variables/
│   └── <var_name>.md                 # Variable spec, units, module, driver parameters
├── 04_Correlations/
│   └── Significant_Correlations.md   # Dataview table of all |r| >= 0.5 relationships
└── 05_Modules/
    ├── Animal_Module.md
    ├── Field_Soil_Module.md
    ├── Feed_Storage_Module.md
    ├── Manure_Module.md
    └── EEE_Module.md
```

### Note Template Example: `02_Input_Parameters/animal_cow_num.md`
```markdown
---
id: animal.herd_information.cow_num
type: input_parameter
blob: animal
unit: animals
default: 100
tags: [input_parameter, animal_module]
---

# 🐮 Input Parameter: `cow_num`

- **Config Blob**: [[animal]]
- **Data Type**: `int`
- **Description**: Total number of mature cows in the herd.

## Biophysical Causal Outputs
- [[AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows]]
- [[AnimalModuleReporter.report_animal_population_statistics.daily_milk_production]]
- [[Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_nitrogen]]

## Empirical Correlations Across Simulation Runs
```dataview
TABLE 
  output_variable as "Output Variable",
  pearson_r as "Pearson r",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
WHERE input_param = "animal.herd_information.cow_num"
SORT abs(pearson_r) DESC
```
```

---

## 7. CLI & Tooling Interface (`tools/rufas_brain.py`)

A comprehensive CLI tool with subcommands:

1. **`python -m tools.rufas_brain init`**:
   - Initializes KùzuDB database in `data/rufas_brain.kuzu/`.
   - Creates all Node and Edge schema tables.
   - Populates canonical Module, ConfigBlob, and Input/Output ontology nodes.

2. **`python -m tools.rufas_brain ingest --output-dir <path> --run-id <id> [--scenario <name>]`**:
   - Ingests simulation run CSVs and logs.
   - Calculates summary metrics for all 2,038 variables.
   - Connects run to inputs and metric nodes.

3. **`python -m tools.rufas_brain compute-correlations [--min-r 0.5] [--max-p 0.05]`**:
   - Calculates cross-run correlation statistics and populates `CORRELATES_WITH` edges.

4. **`python -m tools.rufas_brain query "<opencypher_query>"`**:
   - Executes arbitrary OpenCypher query and returns tabular/JSON results.

5. **`python -m tools.rufas_brain export-obsidian --output-dir <path>`**:
   - Generates the complete Obsidian Markdown vault with Dataview queries.

6. **`python -m tools.rufas_brain trace-impact --param <param_name>`**:
   - Returns all causally influenced and statistically correlated output variables for a given input.

---

## 8. Dedicated Agent Skill: `rufas-brain-specialist`

A new agent skill in `skills/rufas-brain-specialist/SKILL.md`:
- **Role**: Whole-Farm Knowledge Graph & Correlation Specialist.
- **Triggering Conditions**:
  - Asking which inputs drive a specific output variable.
  - Finding correlations or tradeoffs across multiple simulation runs.
  - Looking up exact variable names, units, and descriptions across the 2,038 variables.
  - Querying the KùzuDB graph with OpenCypher.
  - Exporting or updating the Obsidian knowledge graph.

---

## 9. Verification & Safety Constraints

1. **Test Coverage**:
   - Unit tests in `tests/test_brain.py` covering schema creation, ingestion, metric aggregation, correlation calculations, Cypher queries, and Obsidian export file integrity.
2. **Deterministic Reproducibility**:
   - Entire KùzuDB database can be wiped and re-ingested from repository CSV/JSON files in seconds.
3. **Repository Cleanliness**:
   - `data/*.kuzu/` and local test vaults ignored in `.gitignore`.

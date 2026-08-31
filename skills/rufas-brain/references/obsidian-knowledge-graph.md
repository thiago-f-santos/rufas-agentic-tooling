# Obsidian Knowledge Graph Production Guide

## Overview

This guide explains how to generate, explore, and query the **RuFaS Obsidian Markdown Knowledge Graph**. The exporter transforms the KùzuDB property graph and simulation output catalogs into an interactive local markdown vault with visual graph connections and SQL-like Dataview query blocks.

---

## 🚀 How to Produce the Obsidian Vault

### 1. Basic On-Demand Production
To generate or update the vault from the current KùzuDB graph database:

```bash
# Export using Python module or rufas-brain CLI
rufas-brain export-obsidian --output-dir ./vault
python -m tools.rufas_brain export-obsidian --output-dir ./vault --db-path data/rufas_brain.kuzu

# Export to a custom path (e.g. your personal Obsidian Vault directory)
rufas-brain export-obsidian --output-dir ~/Documents/RuFaS_Obsidian_Vault
python -m tools.rufas_brain export-obsidian --output-dir ~/Documents/RuFaS_Obsidian_Vault --db-path data/rufas_brain.kuzu
```

### 2. Full Simulation-to-Vault Lifecycle
Whenever new RuFaS simulations are executed:

```bash
# Step 1: Ingest the newly completed simulation run
python -m tools.rufas_brain ingest --output-dir ../RuFaS/output --run-id "freestall_scenario_2026" --scenario "example_freestall"

# Step 2: Re-calculate cross-run empirical correlations
python -m tools.rufas_brain compute-correlations --min-r 0.5 --max-p 0.05

# Step 3: Produce / Refresh the Obsidian Vault
python -m tools.rufas_brain export-obsidian --output-dir ./vault
```

---

## 📁 Vault Directory Structure

```
vault/
├── 00_Dashboard.md                   # Central hub with system overview & Dataview summary tables
├── 01_Simulations/                   # Note per simulation run with parameter values & metrics
│   ├── freestall_baseline_60d.md
│   └── freestall_mitigation_01.md
├── 02_Parameters/                    # 2,790 parameter notes with YAML frontmatter & causal links
│   ├── animal_mature_body_weight.md
│   └── config_cow_num.md
├── 03_Outputs/                       # 2,038 output variable notes with units, categories & drivers
│   ├── AnimalModuleReporter_..._daily_milk_production.md
│   └── FieldDataReporter_..._N2O_emissions.md
├── 04_Correlations/                  # Empirical statistical correlation tables
│   └── Significant_Correlations.md   # Auto-generated Dataview table of all |r| >= 0.5 relationships
└── 05_Modules/                       # 5 Canonical subsystem overviews
    ├── Animal_Module.md
    ├── Field_Soil_Module.md
    ├── Feed_Storage_Module.md
    ├── Manure_Module.md
    └── EEE_Module.md
```

---

## 🎨 Recommended Obsidian Setup for Humans

### 1. Open the Vault in Obsidian
1. Open the **Obsidian** app.
2. Click **"Open folder as vault"**.
3. Select the exported `vault/` directory (or your custom export path).

### 2. Install the **Dataview** Community Plugin (Essential for SQL queries)
1. In Obsidian, go to **Settings (⚙️) ➔ Community Plugins ➔ Turn on community plugins**.
2. Click **Browse**, search for `Dataview`, and click **Install** then **Enable**.
3. In Dataview Settings, ensure **"Enable JavaScript Queries"** and **"Enable Inline Queries"** are turned ON.

### 3. Configure the Interactive **Graph View (`Ctrl + G`)**
To visually distinguish farm components in the 2D/3D Graph View:
1. Open Graph View (`Ctrl + G` or click the graph icon in the left ribbon).
2. Click the **Gear icon (⚙️)** in the top-right of the graph.
3. Under **Groups**, add the following color rules:
   - **`tag:#module`** ➔ 🟣 Purple (Subsystem hubs)
   - **`tag:#input_parameter`** ➔ 🟢 Green (Configurable farm inputs)
   - **`tag:#output_variable`** ➔ 🔵 Blue (Measured outputs)
   - **`tag:#simulation_run`** ➔ 🟠 Orange (Simulation run nodes)
   - **`tag:#emissions`** ➔ 🔴 Red (Greenhouse gas hotspots)

### 4. Visual Scenario Boards with **Obsidian Canvas**
You can create visual infinite boards (`.canvas` files) inside Obsidian:
- Drag notes from `01_Simulations/`, `02_Parameters/`, and `05_Modules/` onto the canvas.
- Connect cards with directional arrows to visually storyboard biological and financial flows.
- Add live markdown cards with Dataview query tables directly on the canvas.

---

## 🔍 Pre-Configured Dataview SQL Queries

Here are examples of queries you can copy and paste into any note in your vault:

### Query 1: Top 15 Emission Drivers & Significant Correlations
````markdown
```dataview
TABLE 
  input_param as "Input Driver",
  output_variable as "Output Emission Metric",
  pearson_r as "Pearson r",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
WHERE abs(pearson_r) >= 0.6
SORT abs(pearson_r) DESC
LIMIT 15
```
````

### Query 2: Compare Daily Milk Production Across Simulation Runs
````markdown
```dataview
TABLE 
  scenario_name as "Scenario",
  duration_days as "Duration (Days)",
  execution_date as "Run Date"
FROM #simulation_run
SORT execution_date DESC
```
````

### Query 3: Search Output Variables by Subsystem
````markdown
```dataview
TABLE 
  unit as "Measurement Unit",
  category as "Category",
  module as "Subsystem"
FROM #output_variable
WHERE module = "manure"
SORT category ASC
```
````

---

## 🛠️ Developer & Agent Tooling Reference

When an agent needs to produce or update the vault:
- Call `tools.rufas_brain.export_obsidian_vault(conn, output_dir)` programmatically in Python.
- Or execute `python -m tools.rufas_brain export-obsidian --output-dir <path>`.

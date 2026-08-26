---
name: rufas-specialist
description: Use when analyzing, running, configuring, or debugging the RuFaS (Ruminant Farm Systems) dairy farm simulation platform, including biophysical models (animal, crop, soil, manure, feed storage), EEE (economics, energy, emissions), metadata input graphs, or simulation error diagnostics.
---

# RuFaS Specialist Skill

## Overview

**RuFaS (Ruminant Farm Systems)** is a modular, daily-timestep, whole-farm biophysical simulation model. It integrates herd dynamics, crop and soil nutrient-water cycles, feed storage losses, manure handling/treatment, economics, energy use, and greenhouse gas (GHG) emissions.

This skill provides the authoritative domain, architecture, data flow, input configuration, and diagnostic principles for agents interacting with RuFaS.

---

## When to Use

### Use Cases & Symptoms
- Configuring or running RuFaS simulations from CLI or automated pipelines.
- Building, inspecting, or validating scenario metadata files, input datasets, and cross-validation rules.
- Tracing daily simulation data flows and inter-module exchanges between `FieldManager`, `FeedManager`, `HerdManager`, `ManureManager`, and `EEEManager`.
- Interpreting or modifying biophysical models: dairy herd nutrition, lactation, enteric methane, soil-crop dynamics, feed spoilage, manure lagoons/digesters.
- Diagnosing early termination errors, input schema mismatches, negative mass balances, or missing output CSV files.
- Analyzing simulation output data pools, greenhouse gas emission balances, and farm efficiency metrics.

### When NOT to Use
- Generic non-ruminant livestock modeling without RuFaS codebase involvement.
- General Python syntax or boilerplate tasks unrelated to the RuFaS platform.

---

## Core Architecture & Daily Execution Pipeline

RuFaS executes simulations through a strictly ordered daily loop orchestrated by `SimulationEngine`.

```
Daily Loop Sequence:
1. Field Operations (Manure schedule check -> nutrient request -> daily soil/crop update -> harvests)
2. Storage Reception (Store harvested crops in FeedManager storage units)
3. Harvest Schedule Update (Project next harvest dates for active crops)
4. Feed Planning (Project inventory -> calculate max daily feeds -> update purchases & degradations)
5. Ration Planning (Check interval -> solve least-cost/nutrient diets -> purchase feed buffers)
6. Animal Operations (Execute herd feeding, growth, lactation, enteric CH4 -> produce ManureStream)
7. Manure Operations (Route pen manure streams -> separation, pits, storage lagoons, digesters)
8. Record Keeping & EEE (Daily purchased feed emissions, time & weather logs)
9. Advance Time (Increment date and loop)
10. Post-Simulation (EEEManager estimates energy, fuel, electricity, and lifecycle farm emissions)
```

For complete technical specifications, variable bindings, and data structure schemas, consult:
- [simulation-flow.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/references/simulation-flow.md)
- [biophysical-modules.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/references/biophysical-modules.md)
- [eee-and-lifecycle.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/references/eee-and-lifecycle.md)

---

## Metadata Hierarchy & 22 Required File Blobs

RuFaS configuration follows a strict four-layer hierarchy:
1. **CLI Level (`main.py`)**: Accepts `--path-to-metadata`, `--output-dir`, `--verbosity`, `--no-graphics`, `--clear-output`.
2. **Task Manager Metadata (`task_manager_metadata.json`)**: Points to the task definition file (`tasks_properties`).
3. **Task Data File (`tasks/*.json`)**: Defines `parallel_workers`, task types (`SIMULATION_SINGLE_RUN`, `SIMULATION_MULTI_RUN`, `SENSITIVITY_ANALYSIS`), scenario metadata path, output prefix, and `cross_validation_file_paths`.
4. **Scenario Metadata (`<scenario>_metadata.json`)**: Maps logical keys to physical data files and schemas.

### The 22 Required File Blobs
A complete scenario metadata file must define all 22 required blobs:
`config`, `animal`, `animal_population`, `animal_mean_phenotype`, `animal_top_listing_semen`, `lactation`, `economy`, `emission`, `purchased_feeds_emissions`, `purchased_feed_land_use_change_emissions`, `feed`, `NRC_Comp`, `NASEM_Comp`, `manure_management`, `manure_processor_connection`, `crop_configurations`, `weather`, `user_feeds`, `tractor_dataset`, `EEE_constants`, `feed_storage_configurations`, `feed_storage_instances`.

For cross-validation rules and schema property definitions, consult:
- [input-metadata-schema.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/references/input-metadata-schema.md)

---

## Output Management & Filter Routing

- **Variable CSV Generation**: RuFaS does **not** dump variables to CSV by default. CSV generation requires filter files with prefix `csv_` (e.g. `output/output_filters/csv_all_variables.txt`).
- **Data Pools vs Non-Data Pools**:
  - `variables_pool`: Simulation time-series. Memory managed via chunkification. Export filtered by `csv_`, `json_`, `graph_`, `report_` prefixes.
  - `logs_pool`, `warnings_pool`, `errors_pool`: Operational diagnostics. Written unconditionally to `output/logs/` (`errors.txt`, `warnings.txt`, `logs.txt`).

For output filter syntax and log troubleshooting, consult:
- [output-and-diagnostics.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/references/output-and-diagnostics.md)

---

## Quick Reference Commands

| Task | Tool / Command |
|---|---|
| Inspect & validate metadata | `python -m tools.rufas_inspector --scenario <path_to_metadata>` |
| Validate task manager metadata | `python -m tools.rufas_inspector --task-metadata input/task_manager_metadata.json` |
| Run simulation with CSV export | `python -m tools.rufas_runner --task-metadata input/task_manager_metadata.json` |
| Analyze outputs and GHG | `python -m tools.rufas_analyzer --output-dir ../RuFaS/output/` |

---

## Rationalization Table & Red Flags

| Rationalization / Excuse | Reality & Correct Protocol |
|---|---|
| *"I'll edit the JSON input without checking cross-validation."* | Cross-validation rules enforce relational integrity (e.g. diet DM vs crop yields). Invalid edits cause silent or fatal simulation aborts. Run `rufas_inspector.py`. |
| *"The simulation finished, but output is empty because of a code bug."* | Check `output/output_filters/`. If no filter starts with `csv_`, variables are not exported to disk by design. |
| *"I can feed a newly harvested crop on the same day prior to feed planning."* | Feed must be received into storage, inventoried, and integrated during ration planning before it can be fed. |
| *"I can omit required blobs for modules I don't care about."* | `InputManager` enforces all 22 required blobs. Use nullable input files instead of deleting keys from scenario metadata. |

### 🚩 Red Flags - STOP and Correct
- Proposing changes to crop calendars without verifying weather date coverage.
- Modifying pen populations without adjusting manure processor capacities.
- Assuming post-simulation EEE runs inside the daily animal loop.
- Ignoring errors dumped in `output/logs/errors.txt`.

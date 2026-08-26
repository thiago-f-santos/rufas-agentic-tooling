# RuFaS Output Pools, Filter Routing, and Error Diagnostics

## 1. Data Pool Variable Hierarchy & Architecture (`OutputManager`)

RuFaS structures runtime output into two distinct pool types:

```
                  ┌──────────────────────────────────────────────┐
                  │                SimulationEngine              │
                  └──────────────────────┬───────────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
            ┌─────────────────────────┐     ┌─────────────────────────┐
            │       Data Pools        │     │     Non-Data Pools      │
            │    (variables_pool)     │     │ (logs, warnings, errors)│
            └────────────┬────────────┘     └────────────┬────────────┘
                         │                               │
         ┌───────────────┴───────────────┐               │
         ▼                               ▼               ▼
┌──────────────────┐           ┌──────────────────┐ ┌──────────────────┐
│  Chunkification  │           │ Filter Routing   │ │ Disk Dump        │
│ (In-Memory Buffer│           │  (csv_*, json_*, │ │ (output/logs/    │
│  -> Disk Chunks) │           │   graph_*, etc.) │ │  errors.txt,etc.)│
└──────────────────┘           └──────────────────┘ └──────────────────┘
```

### A. Data Pools (`variables_pool`)
- **Contents**: All time-series simulation variables registered dynamically via `OutputManager.add_variable(variable_name, value, unit, context)`.
- **Memory Optimization (Chunkification)**:
  - RuFaS models multi-year simulations (e.g. 10–30 years) generating 2,000+ daily time-series variables. Retaining all arrays entirely in RAM causes Out-Of-Memory (OOM) failures.
  - With `chunkification=True`, `OutputManager` maintains fixed-size memory buffers. When a chunk threshold is reached, intermediate buffers are serialized to temporary binary/text chunks on disk.
  - At simulation conclusion, `OutputManager` compiles and reassembles the chunked arrays into final output matrices for CSV/JSON export.
- **Export Control**: RuFaS does **not** dump variables to disk by default. Export is strictly governed by filter files residing in `output/output_filters/` matching designated filename prefixes:
  - `csv_*` $\rightarrow$ Triggers CSV variable matrix export to `output/CSVs/` (e.g. `sim_all_variables.csv`).
  - `json_*` $\rightarrow$ Triggers JSON structured export to `output/JSON/`.
  - `graph_*` $\rightarrow$ Generates graphical plots (unless `-g / --no-graphics` is set).
  - `report_*` $\rightarrow$ Generates formatted PDF/text summary reports.

### B. Non-Data Pools (`logs_pool`, `warnings_pool`, `errors_pool`)
- **Contents**: Operational trace messages, input validation notices, non-fatal warnings, and terminal exception stack traces.
- **Export**: Always written unconditionally to disk upon run termination into `output/logs/`:
  - `output/logs/errors.txt` — Fatal exception messages, traceback stack, failing module and context.
  - `output/logs/warnings.txt` — Non-fatal warnings (e.g. feed constraint boundary clamps, minor solver adjustments).
  - `output/logs/logs.txt` — Chronological execution timeline, day-by-day solver steps.
  - `output/logs/variable_names_and_contexts.txt` — Complete index of all registered variables in the simulation run.
  - `output/logs/variables_usage_counts.txt` — Frequency counters of variable read/write operations.

---

## 2. Output Filter Activation & Header Bracket Unit Extraction

### Activating Output Export
To enable full CSV variable dumping:
1. Ensure a filter file with prefix `csv_` exists in `output/output_filters/`:
   ```bash
   # Rename the template or create the filter
   cp output/output_filters/_csv_all_variables.txt output/output_filters/csv_all_variables.txt
   ```
2. Or use the automated runner flag:
   ```bash
   python -m tools.rufas_runner --task-metadata input/task_manager_metadata.json --enable-all-csv
   ```

### Header Bracket Unit Convention
RuFaS column headers adhere to a strict signature convention:
$$\text{Class}.\text{method}.\text{variable\_name}.\text{context} \; (\text{unit})$$

- **Extraction Regex**: `r"\(([^)]+)\)$"` matches the trailing unit enclosed in parentheses.
- **Common Unit Signatures**:
  - Biophysical / Yield: `kg`, `kg DM`, `kg/ha`, `mm`, `g`, `g/day`, `fraction`, `unitless`
  - Animal / Population: `animals`, `day`, `kg/cow-day`, `Mcal/kg DM`, `%`
  - Manure / Volume: `m3`, `kg N`, `kg P`, `kg K`, `kg NH4-N`, `kg VS`
  - Economic / Energy: `$`, `$/cwt`, `L`, `kWh`, `kg CO2 / kg DM`, `kg CO2e / kg FPCM`

---

## 3. Complete 2,038 Variable Taxonomy Across 5 Modular Domains

When all variables are exported (`csv_all_variables.txt`), RuFaS generates **2,038 time-series output columns** across the biophysical and socio-economic engines:

| Domain | Variable Count | Specialist Skill Reference | Primary Classes & Reporters | Key Output Categories |
|---|---|---|---|---|
| **Animal & Herd** | **865** | [`rufas-animal-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-animal-specialist/SKILL.md) | `AnimalModuleReporter`, `RationOptimizer`, `LactationCurve` | Herd demographics, parity distribution, body weights, milk yield (kg), fat/protein, DMI, NASEM/NRC nutrient supply/demands, enteric $\text{CH}_4$, excretion partitioning (fecal/urinary N, P, K, moisture, VS). |
| **Field & Soil** | **744** | [`rufas-field-soil-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-field-soil-specialist/SKILL.md) | `FieldDataReporter`, `FieldManager`, `Field`, `Crop` | Daily hydrology (transpiration, evaporation, drainage, runoff, multi-layer soil water), 5-layer soil biogeochemistry (active/slow/passive C pools, $\text{NO}_3$, $\text{NH}_4$, $\text{N}_2\text{O}$ emissions, $\text{NH}_3$ volatilization), crop phenology (GDD, biomass, root depth, harvest yield). |
| **Manure Management** | **264** | [`rufas-manure-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-manure-specialist/SKILL.md) | `Manure.SingleStreamHandler`, `ParlorCleaningHandler`, `Separator.*`, `Storage.*` | Housing alley scraping emissions ($\text{CO}_2, \text{CH}_4, \text{NH}_3$), mechanical separator partition fractions (screw press cake vs effluent), storage tanks/lagoons kinetics, composting decomposition, land application nutrient fulfillment. |
| **Feed Storage** | **134** | [`rufas-feed-storage-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-feed-storage-specialist/SKILL.md) | `FeedManager`, `PurchasedFeedStorage`, `StorageStructure.*` | Multi-structure inventory (bunkers, bags, piles, bins), degradation losses (aerobic face loss, fermentation loss, total shrinkage), commodity purchases (amounts & costs across feed IDs 44, 50, 95, 104, 110, 202, 216, 302), ration fulfillment verification (`is_ok_to_feed`). |
| **EEE & Lifecycle** | **16** + post-sim | [`rufas-eee-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-eee-specialist/SKILL.md) | `EmissionsEstimator`, `Economy`, `Energy`, `EEEManager` | Cradle-to-farm-gate purchased feed emissions ($\text{kg CO}_2 / \text{kg DM}$), land use change emissions, machinery diesel fuel (L), electricity (kWh), enterprise net farm income ($), IOFC ($/cwt), Scope 1-3 carbon footprint ($\text{kg CO}_2\text{e} / \text{kg FPCM}$). |
| **General / Weather** | **15** | Master Skill | `Weather`, simulation runtime time-series, disclaimer | Solar radiation ($\text{MJ/m}^2$), precipitation (mm), ambient temperature ($^\circ\text{C}$), irrigation (mm), timestep index, run disclaimer. |
| **Total Whole-Farm** | **2,038** | [`rufas-specialist`](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-specialist/SKILL.md) | Whole-Farm Integrated Engine | Integrated whole-farm biophysical and socio-economic simulation. |

---

## 4. Error Log Interpretation & Systematic Debugging

When a simulation encounters an error or terminates prematurely (`RuntimeError: Dump all logs from main.py`), follow this systematic diagnostic workflow:

```
                             Simulation Fails / Aborts
                                         │
                                         ▼
                             Read output/logs/errors.txt
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
      [HerdManager Exception]   [FieldManager Exception] [ManureManager Exception]
                 │                       │                       │
                 ▼                       ▼                       ▼
        Infeasible Ration LP       Soil Hydrology /        Storage Overflow /
        or Excretion Partition    Matrix Divergence       Infeasible Spreading
```

### Reading `output/logs/errors.txt`
1. Navigate directly to the bottom lines of `output/logs/errors.txt` to identify the terminal exception type and the failing module stack.
2. Cross-reference the calling method with `output/logs/logs.txt` to locate the exact simulation day/year when the error occurred.
3. Check `output/logs/warnings.txt` for preceding warning patterns (e.g. multiple days of feed shortages or extreme water stress).

### Primary Failure Modes & Remediation

#### 1. Infeasible Linear Programming Diet Formulation (`HerdManager.formulate_rations`)
- **Symptom**: `RuntimeError: Ration LP formulation failed - infeasible solution for pen X on day Y`.
- **Root Cause**: Nutritional bounds (e.g. minimum forage NDF, maximum ether extract/fat, minimum metabolisable protein) cannot be satisfied by available feedstuffs and purchased feed libraries.
- **Remediation**:
  - Inspect `input/data/feed/user_feeds.json` to verify feed prices, nutrient specs, and maximum inclusion limits.
  - Relax strict nutritional bounds in `input/data/animal/animal_general.json` or add supplemental concentrate feeds to the available feed library.

#### 2. Soil Hydrology Matrix Divergence / Negative Soil Water (`FieldManager`)
- **Symptom**: `ValueError: Negative soil water content calculated in layer L of field F`.
- **Root Cause**: Prolonged drought or excessive evapotranspiration demands exceeding available water holding capacity without irrigation or rainfall buffer.
- **Remediation**:
  - Check weather input file `input/data/weather/weather_*.json` for missing rainfall records.
  - Verify soil hydrological properties (field capacity, wilting point, saturation) in `input/data/soil/*.json`.

#### 3. Manure Storage Capacity Exceeded (`ManureManager`)
- **Symptom**: `RuntimeError: Manure storage facility 'pit_1' has exceeded maximum holding capacity`.
- **Root Cause**: Daily manure production and wash water inflow exceed storage volume without scheduled land application emptying events.
- **Remediation**:
  - Inspect `input/data/manure_management/manure_schedule_*.json` and add timely manure application events to fields.
  - Increase storage structure maximum dimensions or initial capacity in `input/data/manure_management/manure_management_*.json`.

#### 4. Feed Storage Inventory Exhaustion & Spoilage Anomaly (`FeedManager`)
- **Symptom**: `Warning: Storage empty for feed X; triggering emergency off-farm purchase`.
- **Root Cause**: Crop harvest yield was insufficient to meet herd demand, or excessive aerobic face losses / fermentation losses degraded stored inventory.
- **Remediation**:
  - Review harvest yield outputs `FieldDataReporter.harvested_yield_DM` and crop acreage.
  - Check storage packing density and face removal rates in `feed_storage_configurations.json`.

#### 5. Cross-Validation & Schema Mismatches at Startup (`CrossValidator` / `InputManager`)
- **Symptom**: `KeyError`, `ValidationError`, or cross-validation relational mismatch before daily loop begins.
- **Remediation**:
  - Run the offline inspector: `python -m tools.rufas_inspector --scenario <path_to_metadata>`
  - Ensure all 22 required file blobs exist and match schema expectations.

#### 6. Empty Output Directory / No CSV Files Generated (`OutputManager`)
- **Symptom**: Simulation completes successfully, but `output/CSVs/` is empty.
- **Root Cause**: Filter files in `output/output_filters/` do not start with `csv_`.
- **Remediation**: Activate `output/output_filters/csv_all_variables.txt` or execute with `--enable-all-csv`.


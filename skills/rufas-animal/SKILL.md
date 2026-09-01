---
name: rufas-animal
description: Use when analyzing, configuring, or debugging the RuFaS Animal and Herd module, including herd demographics, Wood/Dijkstra lactation curves, NRC 2001/NASEM 2021 nutrient requirements, linear programming ration formulation, enteric methane emissions, or excretion partitioning.
---

# RuFaS Animal & Herd Specialist Skill

## 1. Overview & Module Scope
The **RuFaS Animal Module** (`RUFAS/biophysical/animal/`) models dairy cattle herd dynamics, parity demographics (calves, growing heifers, breeding heifers, pregnant heifers, lactating cows across parities 1–4+, dry cows), physiological growth, lactation mechanics, linear programming (LP) least-cost diet optimization, NASEM 2021 enteric methane ($\text{CH}_4$) emissions, and excretion partitioning. Managed by `HerdManager`, it bridges feed consumption from `FeedManager` with daily manure streams delivered to `ManureManager` and financial/emissions accounting in `EEEManager`.

> [!IMPORTANT]
> If RuFaS tools report that RuFaS is not configured, ask the user where their RuFaS project directory is located on their machine, or suggest running `rufas-setup` / setting `RUFAS_PATH`.

## RuFaS Boundary & Source of Truth Protocol

> [!IMPORTANT]
> **Boundary Containment & Ground Truth Rules:**
> 1. **Autonomous Search Scope**: All autonomous file searches (`grep_search`, `find_by_name`, `codegraph_explore`, shell commands) MUST explicitly set `SearchPath` / `SearchDirectory` / `Cwd` to `<rufas_root>` or `<tooling_root>`. NEVER run unscoped searches across parent or sibling directories.
> 2. **Source of Truth Hierarchy**: When explaining mechanics, equations, or defaults, ground answers directly in `<rufas_root>/RUFAS/` Python code and `<rufas_root>/input/metadata/` schemas.
> 3. **Explicit External Confirmation Gate**: If an investigation requires reading files or repositories outside `<rufas_root>` / `<tooling_root>`, the agent MUST halt autonomous search and ask the user for explicit confirmation before proceeding.
> 4. **Subagent Delegation**: Any subagent spawned via `invoke_subagent` MUST explicitly receive the resolved `<rufas_root>` path and these boundary constraints in its prompt.

## 2. Capabilities & When to Use
- **Triggering Conditions**:
  - Configuring herd demographics, parity distributions, mature body weight, or culling/replacement policies.
  - Parameterizing Wood's gamma lactation curves by parity cohort or adjusting days-in-milk (DIM) profiles.
  - Formulating or diagnosing Linear Programming (LP) least-cost rations under NRC (2001) or NASEM (2021) standards.
  - Investigating diet infeasibility, dry matter intake (DMI) under/over-predictions, or unexpected milk yield declines.
  - Modeling enteric methane ($\text{CH}_4$) emissions and evaluating dietary mitigation (e.g. fat, fiber, additives).
  - Tracing fecal vs urinary excretion partitioning (N, TAN, P, K, degradable/non-degradable VS, moisture).
- **Negative Routing**:
  - Manure housing collection, storage lagoons, or digesters $\rightarrow$ `rufas-manure`.
  - Feed storage inventory, bunker spoilage, or crop receiving $\rightarrow$ `rufas-feed`.
  - Soil hydrology, nutrient uptake, and crop growth $\rightarrow$ `rufas-field`.
  - Whole-farm economics, machinery fuel, and LCA carbon intensity $\rightarrow$ `rufas-eee`.

## 3. Module Architecture & Input Configuration Blobs
- **Execution Pipeline**: `HerdManager` advances daily age/DIM $\rightarrow$ checks lactation status $\rightarrow$ updates pen nutritional requirements $\rightarrow$ solves least-cost LP diets via `RationOptimizer` $\rightarrow$ simulates digestion and enteric $\text{CH}_4$ $\rightarrow$ calculates excretion via `ManureExcretionCalculator` $\rightarrow$ reports statistics via `AnimalModuleReporter`.
- **Primary Input Blobs**:
  | Blob Key | Physical Path (Typical) | Critical Parameters |
  |---|---|---|
  | `animal` | `input/data/animal/animal_general.json` | Mature body weight, breed specs, body condition score (BCS) targets, maintenance energy. |
  | `animal_population` | `input/data/animal/animal_population_*.json` | Head counts for lactating, dry, heifer, and calf cohorts; pen occupancy limits and grouping rules. |
  | `animal_mean_phenotype` | `input/data/animal_genetics/mean_phenotype_*.json` | Base phenotypic lactation yield, milk fat %, protein %, mature body weight means. |
  | `animal_top_listing_semen` | `input/data/animal_genetics/top_listing_semen_*.json` | AI sire genetic merit, PTAM, PTAF, PTAP, calving ease indices. |
  | `lactation` | `input/data/animal/lactation_constants.json` | Wood's gamma curve parameters ($a, b, c$) by parity, persistency, peak milk DIM. |
  | `NRC_Comp` | `input/data/feed/NRC_Feed_Library.json` | NRC 2001 feed library: $NE_L$, RDP, RUP, NDF, amino acid compositions. |
  | `NASEM_Comp` | `input/data/feed/NASEM_Feed_Library.json` | NASEM 2021 feed library: dynamic digestion rates, rumen-degradable nutrients, intestinal digestibility. |
  | `user_feeds` | `input/data/feed/user_feeds.json` | Custom on-farm feeds, farm-grown silage profiles, market feed prices, and availability bounds. |

## 4. Core Biophysical Mechanics & Governing Formulas
- **Lactation Curve (Wood's Incomplete Gamma)**:
  $$Y(t) = a \cdot t^b \cdot e^{-c \cdot t}$$
  where $Y(t)$ is daily milk yield at day $t$ in milk (DIM), $a$ scales initial yield, $b$ governs incline to peak, and $c$ dictates post-peak persistency decline (parameterized separately for parity 1 vs parity 2+).
- **Linear Programming (LP) Least-Cost Ration Formulation**:
  $$\min \sum_{j} \text{Cost}_j \cdot X_j \quad \text{subject to:} \quad \text{DMI}_{\min} \le \sum X_j \le \text{DMI}_{\max}, \ \sum \text{NEL}_j X_j \ge \text{Req}_{\text{energy}}, \ \sum \text{MP}_j X_j \ge \text{Req}_{\text{protein}}, \ \sum \text{fNDF}_j X_j \ge \text{Min fNDF}, \ X_j \le \text{MaxDailyFeed}_j$$
- **Enteric Methane ($\text{CH}_4$) Kinetics (NASEM 2021)**:
  $$\text{CH}_4 \, (\text{g/day}) = f(\text{DMI}, \text{Dietary NDF}, \text{Ether Extract / Fat}, \text{Starch})$$
- **Excretion Partitioning (`ManureExcretionCalculator`)**:
  - Total Excreted N: $\text{N}_{\text{excreted}} = \text{N}_{\text{intake}} - \text{N}_{\text{milk}} - \text{N}_{\text{tissue}}$.
  - Nitrogen Split: Urinary N (primarily urea $\rightarrow \text{TAN} = \text{NH}_4^+ + \text{NH}_3$) vs Fecal N (undigested feed + metabolic organic N).
  - Volatile Solids: $\text{VS} = \text{DM}_{\text{fecal}} - \text{Ash}_{\text{fecal}}$, partitioned into degradable ($\text{DVS}$) and non-degradable ($\text{NDVS}$) pools.

## 5. Cross-Module Causal Influences & Whole-Farm Flow
- **Upstream Inflows**: Receives available feed inventories and daily supply limits (`max_daily_feeds`, `AvailableFeeds`) from `FeedManager`.
- **Downstream Outflows**:
  - `ManureManager`: Receives daily pen-level `ManureStream` (mass, feces, urine, N, TAN, P, K, DVS, NDVS, water) driving storage loading and GHG emissions.
  - `FeedManager`: Receives daily diet feed requests (`RequestedFeed`), triggering bunker drawdowns or spot purchases.
  - `EEEManager`: Receives daily milk volume and components (driving milk sales revenue) and purchased feed intake (driving Scope 3 upstream emissions).

## 6. Key Anchor Metrics & Biological Diagnostic Bounds
| Anchor Metric | Units | Diagnostic Benchmark | Anomaly Threshold & Root Cause |
|---|---|---|---|
| **Dry Matter Intake (DMI)** | kg DM/day | 20.0 – 28.5 (milking cow) | `< 18.0`: severe LP constraint conflict, excessive NDF fill, or heat stress over-penalization; `> 32.0`: unconstrained LP intake bounds. |
| **Bulk Milk Production** | kg/cow-day | 28.0 – 45.0 (Holstein) | `< 22.0`: dietary energy/protein deficit, severe negative energy balance, or miscalibrated Wood's $a$ coefficient. |
| **Milk Fat Test** | % | 3.50 – 4.20% (Holstein) | `< 3.20%`: rumen acidosis (SARA) risk or forage NDF $< 19\%$ DM; `> 4.80%`: high fat supplementation or mobilization. |
| **Enteric Methane** | g/day | 350 – 550 g $\text{CH}_4$/cow-day | `< 250`: severe underfeeding/anorexia; `> 650`: highly lignified fibrous diet without fat/additive mitigation. |
| **Nitrogen Use Efficiency (NUE)** | % | 25.0 – 35.0% ($\text{N}_{\text{milk}} / \text{N}_{\text{intake}}$) | `< 22.0%`: excessive dietary Crude Protein ($> 18.5\%$ DM) resulting in high urinary urea excretion and barn $\text{NH}_3$ spikes. |
| **Manure Total Solids (TS)** | % | 12.0 – 15.0% | `< 9.0%`: diarrhea, excessive dietary water/mineral osmotic imbalance; `> 18.0%`: severe animal dehydration. |

## 7. Dynamic Graph Brain Querying & Deep Variable Discovery
The Animal module outputs **865+ time-series variables** (e.g. `AnimalModuleReporter.*`, `RationOptimizer.*`, `LactationCurve.*`). Discover signatures, parameters, and causal connections via `tools/rufas_brain.py`:
```bash
# 1. Search animal output variable signatures, units, and categories
python -m tools.rufas_brain lookup-var --name daily_milk_production
python -m tools.rufas_brain lookup-var --name enteric_methane
python -m tools.rufas_brain lookup-var --name manure_nitrogen

# 2. Trace upstream parameter causal pathways and downstream whole-farm impacts
python -m tools.rufas_brain trace-impact --param lactation
python -m tools.rufas_brain trace-impact --param user_feeds
python -m tools.rufas_brain trace-impact --param mature_body_weight

# 3. Query biophysical causal pathways via OpenCypher
python -m tools.rufas_brain query "MATCH (p:InputParameter)-[:CAUSALLY_INFLUENCES]->(v:OutputVariable) WHERE v.module = 'animal' RETURN p.id, v.name, v.unit LIMIT 15"
```

## 8. Diagnostic Protocols & Red Flags
| Diagnostic Red Flag | Probable Root Cause | Corrective Protocol |
|---|---|---|
| **LP Infeasibility Failure** | Conflicting bounds (e.g. min forage NDF vs max DMI, exhausted feed inventory). | Inspect `RationOptimizer.handle_failed_constraints`; verify feed availability in `feed_storage_instances.json` and relax strict nutrient bounds in `user_feeds.json`. |
| **Severe Negative Energy Balance** | Lactation energy demand exceeds diet $NE_L$ density and DMI capacity. | Check Wood's peak parameter $a$; increase concentrate energy density or add rumen-inert fat. |
| **Sudden Intake Crash** | Extreme Temperature-Humidity Index (THI) heat stress or unpalatable feed blend. | Verify weather inputs in `weather_*.json` or check feed inclusion limits in `user_feeds.json`. |
| **Excessive Urinary N Excretion** | RDP/RUP imbalance or dietary CP $>18.5\%$ DM. | Rebalance rumen degradable protein and optimize amino acid profiles in `user_feeds.json` to raise NUE. |

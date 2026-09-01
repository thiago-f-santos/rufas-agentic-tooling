---
name: rufas-manure
description: Use when analyzing, configuring, or debugging the RuFaS Manure Management module, including barn collection, solid-liquid separation, storage pits/lagoons, anaerobic digestion, gaseous emissions (CH4, NH3, N2O), or field application nutrient supply.
---

# RuFaS Manure Management Specialist Skill

## 1. Overview & Module Scope

The **RuFaS Manure Module** (`RUFAS/biophysical/manure/`), coordinated by `ManureManager`, simulates dairy manure collection, transport, solid-liquid separation, storage, biological treatment (anaerobic digestion), gaseous emissions, and land application supply. It bridges daily excretion from `HerdManager` with organic nutrient delivery to `FieldManager` and Scope 1 greenhouse gas / air quality accounting in `EEEManager`.

> [!IMPORTANT]
> If RuFaS tools report that RuFaS is not configured, ask the user where their RuFaS project directory is located on their machine, or suggest running `rufas-setup` / setting `RUFAS_PATH`.

---

## RuFaS Boundary & Source of Truth Protocol

> [!IMPORTANT]
> **Boundary Containment & Ground Truth Rules:**
> 1. **Autonomous Search Scope**: All autonomous file searches (`grep_search`, `find_by_name`, `codegraph_explore`, shell commands) MUST explicitly set `SearchPath` / `SearchDirectory` / `Cwd` to `<rufas_root>` or `<tooling_root>`. NEVER run unscoped searches across parent or sibling directories.
> 2. **Source of Truth Hierarchy**: When explaining mechanics, equations, or defaults, ground answers directly in `<rufas_root>/RUFAS/` Python code and `<rufas_root>/input/metadata/` schemas.
> 3. **Explicit External Confirmation Gate**: If an investigation requires reading files or repositories outside `<rufas_root>` / `<tooling_root>`, the agent MUST halt autonomous search and ask the user for explicit confirmation before proceeding.
> 4. **Subagent Delegation**: Any subagent spawned via `invoke_subagent` MUST explicitly receive the resolved `<rufas_root>` path and these boundary constraints in its prompt.

---

## 2. Capabilities & When to Use

### Triggering Conditions & Symptoms
- Configuring housing collection: alley scrapers (mechanical/cable), flush flumes, vacuum systems, or gutters.
- Parameterizing solid-liquid separation technologies (screw press, vibrating screen) and partition efficiencies.
- Sizing and simulating storage installations: earthen storage basins, concrete slurry tanks, above-ground bolted steel tanks, or solid compost pads.
- Simulating mesophilic/thermophilic continuous stirred-tank reactor (CSTR) anaerobic digestion, biogas/methane yields, and volatile solids (VS) destruction.
- Modeling gaseous emissions: methane ($\text{CH}_4$), ammonia volatilization ($\text{NH}_3$), and nitrous oxide ($\text{N}_2\text{O}$).
- Fulfilling crop nutrient demands and preventing manure storage overflow.

### When NOT to Use
- Physiological digestion and excretion partitioning in cattle (use `rufas-animal`).
- Soil hydrology, mineralization, and crop nutrient uptake in fields (use `rufas-field`).
- Whole-farm energy, machinery fuel, and economic accounting (use `rufas-eee`).
- Deep output variable discovery, parameter tracing, or cross-run metrics (use `rufas-brain`).

---

## 3. Module Architecture & Input Configuration Blobs

`ManureManager` executes on step 7 of the daily simulation loop, coordinating `SingleStreamHandler`, `ParlorCleaningHandler`, `Separator`, `Digester`, and `Storage` units according to a defined processing graph.

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `manure_management` | `input/data/manure/manure_management_constants.json` | Housing scrape frequency, bedding type/mass per cow-day, separator partition coefficients, storage capacity ($m^3$), geometry, cover type (open, crust, impermeable, flare), digester temp ($^\circ\text{C}$), hydraulic retention time (HRT). |
| `manure_processor_connection` | `input/data/manure/manure_processor_connection.json` | Connectivity network graph routing pen excretion $\rightarrow$ collection handlers $\rightarrow$ separators $\rightarrow$ digesters $\rightarrow$ long-term storage units $\rightarrow$ field application pumps. |

---

## 4. Core Biophysical Mechanics & Governing Formulas

### 1. Housing Collection & Bedding
Receives daily `ManureStream` (feces, urine, water, TN, TAN, Org-N, TP, TK, VS) per pen from `HerdManager`. Added bedding alters dry matter (DM), moisture absorption, and C:N ratio.

### 2. Solid-Liquid Separation (`Separator`)
Partitions raw slurry into a stackable solid cake and pumpable liquid effluent:
$$\text{Mass}_{\text{liquid}} = \text{Mass}_{\text{in}} \cdot (1 - \text{Eff}_{\text{mass}}), \quad \text{DM}_{\text{solid}} = \text{DM}_{\text{in}} \cdot \text{Eff}_{\text{DM}}, \quad \text{TAN}_{\text{liquid}} = \text{TAN}_{\text{in}} \cdot (1 - \text{Eff}_{\text{TAN}})$$

### 3. Anaerobic Digestion (`Digester`)
CSTR mesophilic ($35–38^\circ\text{C}$) or thermophilic ($50–55^\circ\text{C}$) digestion with organic nitrogen mineralization to TAN:
$$\text{CH}_{4,\text{produced}} = \text{VS}_{\text{in}} \cdot B_0 \cdot \text{DestructionFraction}_{\text{VS}}$$

### 4. Storage Dynamics & Gaseous Emissions (`Storage`)
- **Methane ($\text{CH}_4$)**: $\text{CH}_4 \, (\text{kg/day}) = \text{VS}_{\text{stored}} \cdot B_0 \cdot 0.67 \cdot \text{MCF}(T)$
  $$\text{MCF}(T) = \exp\left( \frac{E_a \cdot (T - T_{\text{ref}})}{R \cdot T \cdot T_{\text{ref}}} \right) \quad (\text{Arrhenius dynamic temperature scaling})$$
- **Ammonia ($\text{NH}_3$)**: Driven by aqueous $\text{NH}_3 / \text{NH}_4^+$ equilibrium (pH, temperature), surface area, wind speed, and cover/crust resistance.
- **Nitrous Oxide ($\text{N}_2\text{O}$)**: Formed via surface crust nitrification-denitrification on liquid storage or compost piles.

### 5. Field Nutrient Delivery (`request_nutrients`)
When `FieldManager` calls `request_nutrients()`, slurry is extracted from storage, returning `ManureEventNutrientRequestResults` (mass, volume, Org-N, TAN, Org-P, Inorg-P, K, VS) and deducting mass from storage inventory.

---

## 5. Cross-Module Causal Influences & Whole-Farm Flow

- **Upstream (`HerdManager`)**: Receives daily pen-level `ManureStream`. Dietary changes in DMI, crude protein, and digestibility immediately shift manure mass, TAN:Org-N ratio, and volatile solids loading.
- **Downstream (`FieldManager`)**: Supplies requested organic nutrients for scheduled spreading events, displacing commercial synthetic fertilizers and contributing to soil organic carbon pools.
- **Downstream (`EEEManager`)**: Emits Scope 1 greenhouse gases ($\text{CH}_4, \text{N}_2\text{O}$) and air quality pollutants ($\text{NH}_3$); transfers captured biogas methane for energy offset accounting.

---

## 6. Key Anchor Metrics & Biological Diagnostic Bounds

| Anchor Metric | Units | Diagnostic Benchmark | Anomaly Threshold & Root Cause |
|---|---|---|---|
| **Slurry Wet Mass** | `kg/cow-day` | $55 - 85$ (Lactating) | $<40$ or $>100$: Excretion calculation anomaly in herd or missing wash water. |
| **Slurry Total Solids (TS)** | `%` | $8 - 14\%$ | $<6\%$: Excessive wash/flush water dilution; $>16\%$: High bedding or moisture deficit. |
| **Degradable VS (DVS)** | `kg/cow-day` | $6.0 - 9.0$ | $<4.0$: Low intake or overestimated ruminal digestion efficiency. |
| **Lagoon Methane ($\text{CH}_4$)** | `kg/day` | $0.2 - 25.0+$ (Seasonal) | Flat summer curve: Arrhenius MCF temperature scaling disabled or zero stored VS. |
| **Barn Floor $\text{NH}_3\text{-N}$** | `kg/pen-day` | $1.5 - 6.0$ ($10 - 25\%$ TAN) | $>35\%$ TAN volatilized: High barn temperatures or infrequent scraping cycles. |
| **Separator DM Capture** | `%` | $20 - 35\%$ DM in cake | $<15\%$: Ineffective separation or screen blinding. |
| **Lagoon Capacity Margin** | `%` | $15 - 50\%$ freeboard buffer | $<10\%$ or overflow: Inadequate storage sizing or missing land application events. |

---

## 7. Dynamic Graph Brain Querying & Deep Variable Discovery

The Manure module tracks **264 time-series variables** (handlers, separators, lagoons, compost, field interfaces). Query the Graph Memory Brain (`tools/rufas_brain.py`) for exact signatures, units, and causal pathways:

```bash
# 1. Lookup variable definitions, units, and reporter classes
python -m tools.rufas_brain lookup-var --name housing_ammonia
python -m tools.rufas_brain lookup-var --name storage_methane

# 2. Trace biophysical causal pathways and downstream impacts
python -m tools.rufas_brain trace-impact --param manure_management
python -m tools.rufas_brain trace-impact --param manure_processor_connection

# 3. Query biophysical relationships via OpenCypher
python -m tools.rufas_brain query "MATCH (p:InputParameter)-[:CAUSALLY_INFLUENCES]->(v:OutputVariable) WHERE v.module = 'manure' RETURN p.id, v.name, v.unit"
```

---

## 8. Diagnostic Protocols & Red Flags

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"I can route pens to unlinked storage units."* | The manure processing network must be explicitly connected in `manure_processor_connection.json`. Unlinked units cause routing errors. |
| *"Anaerobic digesters eliminate total nitrogen."* | Digestion destroys carbon (VS), but conserves total nitrogen (TN); it mineralizes organic N into ammonium ($\text{NH}_4^+$), increasing volatilization risk if uncovered. |
| *"Storage volume can exceed capacity indefinitely."* | Storage overflow triggers unmanaged nutrient loss warnings. Add scheduled field application events in `manure_schedule/*.json`. |

### 🚩 Diagnostic Red Flags
- **Storage Capacity Overflow**: Add land application events in `manure_schedule/*.json` or increase capacity in `manure_management_constants.json`.
- **Low/Zero Digester Conversion**: Verify operating temperature ($35–38^\circ\text{C}$ mesophilic) and hydraulic retention time (HRT $\ge 20\text{ days}$).
- **Negative Nutrient Balance**: Check mass balance continuity across separator solid/liquid splits and storage withdrawals.
- **Zero Ammonia Emissions from Open Lagoon**: Check slurry pH, wind speed, and surface crust/cover settings in `manure_management_constants.json`.

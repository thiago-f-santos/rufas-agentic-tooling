# Domain Specialists & Graph Memory Brain Tiered Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor all RuFaS domain specialist skills into a standardized, lean biophysical reasoning template while offloading exhaustive output variable dictionaries (2,038 variables) to the KùzuDB Graph Memory Brain.

**Architecture:** Adopt a tiered hybrid model where specialist skills (`SKILL.md`) act as domain reasoning engines (holding biophysical equations, internal architecture, cross-module causal ripple effects, primary anchor benchmarks, and diagnostic protocols), while the Graph Memory Brain (`tools/rufas_brain.py` / KùzuDB) serves as the dynamic repository for exact column signatures, parameter hierarchies, causal impact paths, and cross-run statistics.

**Tech Stack:** Python 3.10+, KùzuDB (`kuzu`), Pytest, Markdown / YAML Frontmatter

**Spec:** [`docs/superpowers/specs/2026-08-27-domain-specialists-graph-brain-architecture-design.md`](file:///home/aluno/rufas-agentic-tooling-main/docs/superpowers/specs/2026-08-27-domain-specialists-graph-brain-architecture-design.md)

## Global Constraints
- Token Efficiency: Use `rtk` prefix for CLI commands where applicable.
- Semantic Commits: Format commits following Conventional Commits (`docs:`, `feat:`, `refactor:`, `test:`, `chore:`).
- Standardized Format: Every specialist skill must strictly adhere to the 8-section standard template.

---

### Task 1: Refactor Animal & Herd Specialist Skill

**Files:**
- Modify: `skills/rufas-animal-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/rufas_brain.py` (CLI query patterns)
- Produces: Lean `rufas-animal-specialist` skill (< 140 lines) with complete biophysics, cross-module flows, anchor metrics, and graph lookup instructions.

- [ ] **Step 1: Write the updated `skills/rufas-animal-specialist/SKILL.md`**

Replace the bulky variable tables with the lean standardized 8-section template:
1. Overview & Module Scope
2. Capabilities & When to Use (and When NOT to Use)
3. Module Architecture & Input Configuration Blobs (`animal`, `animal_population`, `lactation`, `NRC_Comp`, `NASEM_Comp`, `user_feeds`)
4. Core Biophysical Mechanics & Formulas (Wood's curve $Y(t) = a \cdot t^b \cdot e^{-c \cdot t}$, LP ration optimization, NASEM 2021 enteric $\text{CH}_4$ kinetics, excretion partitioning)
5. Cross-Module Causal Influences (Upstream: `FeedManager` $\rightarrow$ Downstream: `ManureManager`, `EEEManager`)
6. Key Anchor Metrics & Biological Diagnostic Bounds (DMI, Milk Yield, Milk Fat %, Enteric $\text{CH}_4$, NUE, Excreted TS)
7. Dynamic Graph Brain Querying (`python -m tools.rufas_brain lookup-var --name daily_milk_production`, `trace-impact --param lactation`)
8. Diagnostic Protocols & Red Flags (LP infeasibility relaxation ladder, negative energy balance, sudden intake drops)

- [ ] **Step 2: Verify file syntax, YAML frontmatter, and line count**

Run: `python3 -c "import yaml; open('skills/rufas-animal-specialist/SKILL.md')"` and verify line count is under 150 lines.

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-animal-specialist/SKILL.md
git commit -m "refactor(skills): streamline animal specialist with graph brain tiering"
```

---

### Task 2: Refactor Field & Soil Specialist Skill

**Files:**
- Modify: `skills/rufas-field-soil-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/rufas_brain.py`
- Produces: Lean `rufas-field-soil-specialist` skill with hydrology, soil C/N biogeochemistry, crop kinetics, cross-module flows, and anchor metrics.

- [ ] **Step 1: Write the updated `skills/rufas-field-soil-specialist/SKILL.md`**

Implement the 8-section standard template:
1. Overview & Module Scope (Multi-layer soil physics, Century/DayCent C/N dynamics, crop growth)
2. Capabilities & When to Use (and When NOT to Use)
3. Module Architecture & Input Configuration Blobs (`crop_configurations`, `weather`, `tractor_dataset`, field definitions)
4. Core Biophysical Mechanics & Formulas (Darcy-Richards infiltration, mineralization/immobilization, nitrification/denitrification $\text{N}_2\text{O}$, crop thermal time/transpiration)
5. Cross-Module Causal Influences (Upstream: `ManureManager` slurry application $\rightarrow$ Downstream: `FeedManager` crop yields, `EEEManager` soil $\text{N}_2\text{O}$ and nitrate leaching)
6. Key Anchor Metrics & Biological Diagnostic Bounds (Soil $\text{NO}_3\text{-N}$, daily $\text{N}_2\text{O}$ emissions, crop dry matter yield, $\text{SOC}\%$, evapotranspiration)
7. Dynamic Graph Brain Querying (`python -m tools.rufas_brain lookup-var --name N2O_emissions`, `trace-impact --param crop_configurations`)
8. Diagnostic Protocols & Red Flags (extreme nitrate leaching, water table saturation, crop failure)

- [ ] **Step 2: Verify file syntax and line count**

Run: `python3 -c "import yaml; open('skills/rufas-field-soil-specialist/SKILL.md')"`

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-field-soil-specialist/SKILL.md
git commit -m "refactor(skills): streamline field-soil specialist with graph brain tiering"
```

---

### Task 3: Refactor Manure Management Specialist Skill

**Files:**
- Modify: `skills/rufas-manure-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/rufas_brain.py`
- Produces: Lean `rufas-manure-specialist` skill covering housing collection, separation, anaerobic digestion, storage emission kinetics, and field nutrient supply.

- [ ] **Step 1: Write the updated `skills/rufas-manure-specialist/SKILL.md`**

Implement the 8-section standard template:
1. Overview & Module Scope (`ManureManager`, barn collection, processing, storage, land application)
2. Capabilities & When to Use (and When NOT to Use)
3. Module Architecture & Input Configuration Blobs (`manure_management`, `manure_processor_connection`)
4. Core Biophysical Mechanics & Formulas (Separation mass balances, CSTR anaerobic digestion $\text{CH}_4$ yields, Van 't Hoff / Arrhenius temperature-dependent MCF storage emissions, TAN volatilization)
5. Cross-Module Causal Influences (Upstream: `HerdManager` $\text{ManureStream}$ $\rightarrow$ Downstream: `FieldManager` land application nutrients, `EEEManager` Scope 1 barn & lagoon emissions)
6. Key Anchor Metrics & Biological Diagnostic Bounds (Slurry Mass, Slurry TS $\%$, Degradable VS, Lagoon $\text{CH}_4$, Barn floor $\text{NH}_3\text{-N}$)
7. Dynamic Graph Brain Querying (`python -m tools.rufas_brain lookup-var --name housing_ammonia`, `trace-impact --param manure_management`)
8. Diagnostic Protocols & Red Flags (storage overflow capacity warnings, low digester biogas conversion, negative nutrient balance)

- [ ] **Step 2: Verify file syntax and line count**

Run: `python3 -c "import yaml; open('skills/rufas-manure-specialist/SKILL.md')"`

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-manure-specialist/SKILL.md
git commit -m "refactor(skills): streamline manure specialist with graph brain tiering"
```

---

### Task 4: Refactor Feed Storage Specialist Skill

**Files:**
- Modify: `skills/rufas-feed-storage-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/rufas_brain.py`
- Produces: Lean `rufas-feed-storage-specialist` skill covering bunker/silo dynamics, aerobic spoilage kinetics, inventory bounds, and purchased feed reconciliation.

- [ ] **Step 1: Write the updated `skills/rufas-feed-storage-specialist/SKILL.md`**

Implement the 8-section standard template:
1. Overview & Module Scope (`FeedManager`, bunker silos, grain bins, commodity sheds, commercial feed inventories)
2. Capabilities & When to Use (and When NOT to Use)
3. Module Architecture & Input Configuration Blobs (`feed_storage_configurations`, `feed_storage_instances`, `feed`)
4. Core Biophysical Mechanics & Formulas (Bunk face packing density and dry matter deterioration kinetics, fermentation shrinkage, leachate runoff, inventory drawdown)
5. Cross-Module Causal Influences (Upstream: `FieldManager` harvested crops $\rightarrow$ Downstream: `HerdManager` LP feed constraints, `EEEManager` purchased feed costs and Scope 3 emissions)
6. Key Anchor Metrics & Biological Diagnostic Bounds (Bunker Shrinkage $\%$, Spoilage Loss rate, Storage Capacity Utilization, Feeding Drawdown)
7. Dynamic Graph Brain Querying (`python -m tools.rufas_brain lookup-var --name storage_shrinkage`, `trace-impact --param feed_storage_configurations`)
8. Diagnostic Protocols & Red Flags (premature feed stockout, extreme spoilage $>20\%$, LP solver starvation)

- [ ] **Step 2: Verify file syntax and line count**

Run: `python3 -c "import yaml; open('skills/rufas-feed-storage-specialist/SKILL.md')"`

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-feed-storage-specialist/SKILL.md
git commit -m "refactor(skills): streamline feed storage specialist with graph brain tiering"
```

---

### Task 5: Refactor EEE & Lifecycle Specialist Skill

**Files:**
- Modify: `skills/rufas-eee-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/rufas_brain.py`
- Produces: Lean `rufas-eee-specialist` skill covering economics, energy use, Scope 1/2/3 LCA accounting, and carbon intensity metrics.

- [ ] **Step 1: Write the updated `skills/rufas-eee-specialist/SKILL.md`**

Implement the 8-section standard template:
1. Overview & Module Scope (`EEEManager`, whole-farm economics, energy/fuel consumption, Scope 1/2/3 greenhouse gas emissions, carbon intensity)
2. Capabilities & When to Use (and When NOT to Use)
3. Module Architecture & Input Configuration Blobs (`economy`, `emission`, `purchased_feeds_emissions`, `purchased_feed_land_use_change_emissions`, `EEE_constants`)
4. Core Biophysical & Economic Formulas (100-yr GWP conversions $\text{GWP}_{\text{AR5}}$, FPCM formula, Scope 1/2/3 partitioning, net enterprise profit and cash flow)
5. Cross-Module Causal Influences (Upstream: Aggregates energy/emissions/costs from Animal, Field, Manure, and Feed Storage $\rightarrow$ Downstream: Farm sustainability and economic reporting)
6. Key Anchor Metrics & Biological/Economic Bounds (Farm Carbon Intensity $\text{kg CO}_2\text{e/kg FPCM}$, Enterprise Net Return $\$ / \text{cwt}$, Scope 1 GHG mass, Diesel Fuel L/ha)
7. Dynamic Graph Brain Querying (`python -m tools.rufas_brain lookup-var --name carbon_intensity`, `trace-impact --param EEE_constants`, OpenCypher emission queries)
8. Diagnostic Protocols & Red Flags (negative profit margin anomalies, unrealistically low carbon intensity $<0.5$, Scope 3 purchased feed emission spikes)

- [ ] **Step 2: Verify file syntax and line count**

Run: `python3 -c "import yaml; open('skills/rufas-eee-specialist/SKILL.md')"`

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-eee-specialist/SKILL.md
git commit -m "refactor(skills): streamline eee specialist with graph brain tiering"
```

---

### Task 6: Update Master Specialist & Brain Specialist Skills

**Files:**
- Modify: `skills/rufas-specialist/SKILL.md`
- Modify: `skills/rufas-brain-specialist/SKILL.md`
- Test: `tests/test_tooling.py`

**Interfaces:**
- Consumes: Refactored specialist skills
- Produces: Master skill and brain specialist with synchronized cross-delegation documentation.

- [ ] **Step 1: Update `skills/rufas-specialist/SKILL.md`**

Update the master skill overview table and delegation guidelines to highlight the tiered architecture:
- Reiterate that domain biophysics and diagnostics reside in specialist skills.
- Reiterate that deep variable searches (2,038 catalog) and cross-run statistical queries route through `rufas-brain-specialist` / `tools/rufas_brain.py`.

- [ ] **Step 2: Review and verify `skills/rufas-brain-specialist/SKILL.md`**

Ensure all OpenCypher templates and CLI examples (`lookup-var`, `trace-impact`, `query`, `export-obsidian`) match the tiered workflow.

- [ ] **Step 3: Commit**

```bash
git add skills/rufas-specialist/SKILL.md skills/rufas-brain-specialist/SKILL.md
git commit -m "docs(skills): update master specialist and brain specialist with tiered routing"
```

---

### Task 7: Complete Verification & Test Suite Execution

**Files:**
- Test: `tests/test_brain.py`
- Test: `tests/test_tooling.py`

- [ ] **Step 1: Execute test suite**

Run: `pytest tests/test_brain.py tests/test_tooling.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Verify skill directory installation**

Run: `python tools/install_skills.py`
Expected: All 7 skills installed and validated.

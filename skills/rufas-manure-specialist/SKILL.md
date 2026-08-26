---
name: rufas-manure-specialist
description: Use when analyzing, configuring, or debugging the RuFaS Manure Management module, including barn collection, solid-liquid separation, storage pits/lagoons, anaerobic digestion, gaseous emissions (CH4, NH3, N2O), or field application nutrient supply.
---

# RuFaS Manure Management Specialist Skill

## Overview

The **RuFaS Manure Module** (`RUFAS/biophysical/manure/`) simulates the collection, transport, solid-liquid separation, storage, biological treatment (anaerobic digestion), gaseous emissions, and land application of dairy cattle manure.

Managed by `ManureManager`, it receives pen-level excretion streams from `HerdManager`, simulates biogeochemical transformations and gas emissions in storage, and supplies organic nutrients to `FieldManager`.

---

## When to Use

### Triggering Conditions & Symptoms
- Configuring manure housing collection: alley scraping (mechanical, cable), flush flumes, vacuum systems, or tie-stall gutters.
- Modeling solid-liquid separation technologies (screw press, vibrating screen, weeping wall) and evaluating separation efficiencies.
- Parameterizing storage installations: earthen storage basins, concrete slurry tanks, above-ground bolted steel tanks, or solid compost pads.
- Simulating anaerobic digestion: mesophilic/thermophilic continuous stirred-tank reactors (CSTR), biogas yields, methane recovery, and volatile solids (VS) destruction.
- Calculating manure-derived greenhouse gas and air quality emissions: methane ($\text{CH}_4$), ammonia volatilization ($\text{NH}_3$), and nitrous oxide ($\text{N}_2\text{O}$).
- Fulfilling nutrient application requests from `FieldManager` and preventing manure storage overflow.

### When NOT to Use
- Physiological digestion and excretion partitioning in cattle (use `rufas-animal-specialist`).
- Soil water flow and crop nutrient uptake in fields (use `rufas-field-soil-specialist`).
- Whole-farm energy and economic accounting (use `rufas-eee-specialist`).

---

## Inputs & Metadata Schemas

The Manure module is configured via 2 primary metadata blobs:

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `manure_management` | `input/data/manure/manure_management_constants.json` | Housing scrape frequency, bedding material type (straw, sawdust, recycled solids, sand) and mass per cow-day, separator partition coefficients, storage capacity ($m^3$), geometry, cover type (open, natural crust, impermeable cover, flare), digester operating temperature ($^\circ\text{C}$), hydraulic retention time (HRT). |
| `manure_processor_connection` | `input/data/manure/manure_processor_connection.json` | Connectivity graph defining the routing network from animal pens $\rightarrow$ collection handlers $\rightarrow$ separators $\rightarrow$ digesters $\rightarrow$ long-term storage units $\rightarrow$ field application pumps/tankers. |

---

## Core Biophysical Mechanics & Formulas

### 1. Housing Collection & Bedding Interaction
- Daily manure excretion (`ManureStream`) received from each pen in `HerdManager` contains:
  - Fecal dry matter, urinary dry matter, total water, Total Nitrogen (TN), Total Ammoniacal Nitrogen (TAN = $\text{NH}_4^+ + \text{NH}_3$), Organic Nitrogen (Org-N), Total Phosphorus (TP), Total Potassium (TK), and Volatile Solids (VS).
- Added bedding increases dry matter, changes C:N ratio, and contributes moisture absorption capacity based on bedding type.

### 2. Solid-Liquid Separation (`Separator`)
Separates the incoming slurry stream into a **solid cake fraction** and a **liquid effluent fraction**:
$$\text{Mass}_{\text{liquid}} = \text{Mass}_{\text{in}} \cdot (1 - \text{Eff}_{\text{mass}})$$
$$\text{DM}_{\text{solid}} = \text{DM}_{\text{in}} \cdot \text{Eff}_{\text{DM}}$$
$$\text{TAN}_{\text{liquid}} = \text{TAN}_{\text{in}} \cdot (1 - \text{Eff}_{\text{TAN}})$$
Solid fraction can be routed to solid storage or compost; liquid fraction is routed to lagoons or digesters.

### 3. Anaerobic Digestion (`Digester`)
- Modeled for continuous mesophilic ($35–38^\circ\text{C}$) or thermophilic ($50–55^\circ\text{C}$) digestion.
- **Biogas & Methane Production**:
  $$\text{CH}_{4,\text{produced}} = \text{VS}_{\text{in}} \cdot B_0 \cdot \text{DestructionFraction}_{\text{VS}}$$
  where $B_0$ is the maximum methane producing capacity ($\text{m}^3 \text{CH}_4 / \text{kg VS}$).
- **Nutrient Mineralization**: A fraction of Organic N is mineralized to TAN ($\text{NH}_4^+$), increasing plant-available nitrogen in the digested effluent.

### 4. Storage Dynamics & Gaseous Emissions (`Storage`)
- **Methane ($\text{CH}_4$) from Storage**:
  $$\text{CH}_4 \, (\text{kg/day}) = \text{VS}_{\text{stored}} \cdot B_0 \cdot 0.67 \cdot \text{MCF}(T)$$
  where $\text{MCF}(T)$ is the Methane Conversion Factor adjusted dynamically by ambient/slurry temperature via the Van 't Hoff / Arrhenius equation:
  $$\text{MCF}(T) = \exp\left( \frac{E_a \cdot (T - T_{\text{ref}})}{R \cdot T \cdot T_{\text{ref}}} \right)$$
- **Ammonia ($\text{NH}_3$) Volatilization**:
  - Dependent on surface TAN concentration, aqueous $\text{NH}_3$ fraction (driven by slurry pH and temperature), wind speed, and surface resistance (natural crust vs cover).
- **Nitrous Oxide ($\text{N}_2\text{O}$)**:
  - Generated primarily from aerobic surface crusts on liquid storage or dry solid manure piles via nitrification-denitrification.

### 5. Land Application Supply (`request_nutrients`)
- When `FieldManager` executes a scheduled manure application, it queries `ManureManager.request_nutrients(manure_request, field_name, time)`.
- `ManureManager` extracts slurry from storage, computes available N, P, K, and VS, deducts volume from storage, and returns `ManureEventNutrientRequestResults`.

---

## Outputs & Cross-Module Influence

| Output Variable / Data Structure | Receiving Module | Impact on Whole Farm |
|---|---|---|
| `ManureEventNutrientRequestResults` | `FieldManager` | Delivers organic and ammoniacal nutrients to crops, displacing synthetic fertilizer requirements. |
| Daily Manure $\text{CH}_4$, $\text{N}_2\text{O}$, $\text{NH}_3$ | `EEEManager` | Formulates 30–50% of the farm's total carbon footprint and direct air pollutant emissions. |
| Digester Biogas / Methane Output | `EEEManager` | Generates renewable energy offsets (electricity generation or natural gas credit). |
| Storage Volume & Level Trajectory | Operations Monitoring | Prevents catastrophic lagoon overflow or violation of storage capacity limits. |

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"I can route pens to unlinked storage units."* | The manure processing network must be explicitly connected in `manure_processor_connection.json`. Unlinked units cause routing errors. |
| *"Anaerobic digesters remove all nitrogen from manure."* | Digestion destroys carbon (VS), but conserves total nitrogen (TN); it converts organic N into ammonium N ($\text{NH}_4^+$), making digestate more prone to ammonia volatilization if not covered or injected. |
| *"Storage volume can exceed capacity indefinitely."* | Storage overflow triggers warnings and unmanaged nutrient discharge. Ensure scheduled field application events in `manure_schedule/*.json` match herd excretion volume. |

### 🚩 Diagnostic Red Flags
- Manure storage overflow errors $\rightarrow$ Add land application events in `manure_schedule/*.json` or expand storage capacity in `manure_management_constants.json`.
- Zero ammonia emissions from open liquid lagoon $\rightarrow$ Check slurry pH and surface crust settings in `manure_management_constants.json`.
- Missing nutrient delivery to field $\rightarrow$ Verify that the processor connectivity graph links the target storage unit to field application pumps.

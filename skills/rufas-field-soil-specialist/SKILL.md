---
name: rufas-field-soil-specialist
description: Use when analyzing, configuring, or debugging the RuFaS Field, Soil, and Crop module, including multi-layer soil water balance, nitrogen/phosphorus/carbon biogeochemistry, crop phenology (GDD, RUE), tillage, fertilizer and manure scheduling, or crop harvests.
---

# RuFaS Field, Soil & Crop Specialist Skill

## Overview

The **RuFaS Field and Soil Module** (`RUFAS/biophysical/field/`) simulates multi-layer vertical soil hydrology, heat transfer, nutrient transformations (N, P, C), crop phenology, biomass accumulation, root dynamics, and farm operational events (tillage, commercial fertilizer, manure application, and harvesting).

Managed by `FieldManager`, it produces the farm-grown biomass (`HarvestedCrop`) that feeds `FeedManager` and utilizes manure nutrients requested from `ManureManager`.

---

## When to Use

### Triggering Conditions & Symptoms
- Configuring field definitions, soil layer profiles (bulk density, sand/silt/clay fractions, organic matter), and crop rotation sequences.
- Modeling crop growth curves, radiation use efficiency (RUE), growing degree days (GDD), water stress, and nitrogen stress.
- Setting up or tuning management calendars: tillage schedules, synthetic fertilization events, manure application events, and harvest dates.
- Investigating negative soil moisture levels, divergent hydraulic potential solvers, or crop harvest failures.
- Tracking soil nitrogen balances: nitrification, denitrification, ammonia volatilization, nitrate leaching ($\text{NO}_3^-$), and direct/indirect nitrous oxide ($\text{N}_2\text{O}$) emissions.
- Tracking soil phosphorus cycling: labile, solution, active inorganic, and stable inorganic P pools.

### When NOT to Use
- Animal feed planning, inventory projection, or silo storage degradation (use `rufas-feed-storage-specialist`).
- Barn manure collection, slurry lagoons, or anaerobic digesters (use `rufas-manure-specialist`).
- Tractor fuel and machinery power calculations (use `rufas-eee-specialist`).

---

## Inputs & Metadata Schemas

The Field & Soil module utilizes the following primary configuration datasets:

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `crop_configurations` | `input/data/crop_configurations/crop_config.json` | Master mapping of fields to crop rotations, planting dates, and base management options. |
| `weather` | `input/data/weather/weather_*.json` | Daily precipitation, min/max air temp, solar radiation, wind speed, relative humidity. |
| `field_*` | `input/data/field/field_*.json` | Field area (ha), slope, drainage characteristics, soil assigned ID. |
| `soil_*` | `input/data/soil/soil_*.json` | Layer thicknesses, texture class, field capacity ($\theta_{\text{fc}}$), wilting point ($\theta_{\text{wp}}$), saturation ($\theta_{\text{sat}}$), saturated hydraulic conductivity ($K_{\text{sat}}$), initial organic C and N. |
| `crop_*` | `input/data/crop/crop_*.json` | Base GDD to maturity, optimal temperature, RUE ($\text{g/MJ}$), harvest index, root depth rate, nutrient uptake parameters (N, P, K). |
| `tillage_schedule` | `input/data/tillage_schedule/*.json` | Tillage dates, implement type (moldboard, chisel, disk, no-till), depth, and residue incorporation fraction. |
| `fertilizer_schedule` | `input/data/fertilizer_schedule/*.json` | Application date, fertilizer chemical type (urea, UAN, DAP, potash), rate ($\text{kg/ha}$), and placement depth. |
| `manure_schedule` | `input/data/manure_schedule/*.json` | Application date, target nutrient or volume rate, application method (broadcast, incorporate, shallow injection, deep injection). |

---

## Core Biophysical Mechanics & Formulas

### 1. Multi-Layer Soil Hydrology
The soil profile is divided into discrete horizontal layers. For each layer $i$:
- **Infiltration**: Modeled via Green-Ampt or SCS Curve Number from surface precipitation and snowmelt.
- **Percolation & Redistribution**: Darcy's law for unsaturated flow:
  $$q = -K(\theta) \left( \frac{\partial \psi}{\partial z} + 1 \right)$$
- **Evapotranspiration (ET)**: Potential ET computed using Penman-Monteith, partitioned into potential soil evaporation (based on canopy cover) and potential plant transpiration (extracted across root zone layers).

### 2. Soil Temperature Dynamics
Vertical heat conduction through the soil layers driven by ambient boundary temperature, solar radiation, snow cover, and soil thermal conductivity:
$$\frac{\partial T}{\partial t} = \frac{\partial}{\partial z} \left( k_{\text{thermal}} \frac{\partial T}{\partial z} \right)$$

### 3. Soil Biogeochemistry (N, P, C Cycles)
- **Carbon Pools**: Fast microbial biomass, slow active humus, and passive resistant humus.
- **Nitrogen Mineralization & Immobilization**: Microbially mediated conversions between organic N and ammonium ($\text{NH}_4^+$).
- **Nitrification**: Aerobic conversion of $\text{NH}_4^+$ to nitrate ($\text{NO}_3^-$):
  $$\text{NH}_4^+ \rightarrow \text{NO}_2^- \rightarrow \text{NO}_3^- + \text{N}_2\text{O} \text{ (byproduct)}$$
- **Denitrification**: Anaerobic reduction under high soil water-filled pore space ($\text{WFPS} > 60\%$):
  $$\text{NO}_3^- \rightarrow \text{NO}_2^- \rightarrow \text{NO} \rightarrow \text{N}_2\text{O} \rightarrow \text{N}_2$$
- **Leaching**: $\text{NO}_3^-$ transported downward with percolating water below the root zone.

### 4. Crop Growth Engine
- **Phenology**: Thermal time accumulation:
  $$\text{GDD} = \max\left( \frac{T_{\max} + T_{\min}}{2} - T_{\text{base}}, 0 \right)$$
- **Daily Biomass Accumulation**:
  $$\Delta \text{Biomass} = \text{IPAR} \cdot \text{RUE} \cdot \min(\text{Stress}_{\text{water}}, \text{Stress}_{\text{nitrogen}}, \text{Stress}_{\text{temp}})$$
- **Harvest Events**: When physiological maturity or scheduled harvest date arrives, biomass is partitioned into harvested yield (`HarvestedCrop`) and field surface residue.

---

## Outputs & Cross-Module Influence

| Output Variable / Data Structure | Receiving Module | Impact on Whole Farm |
|---|---|---|
| `harvested_crops: list[HarvestedCrop]` | `FeedManager` | Provides fresh forage/grain to storage; dictates feed availability and reduces purchased feed demand. |
| `ManureEventNutrientRequest` | `ManureManager` | Requests liquid/solid manure volume and nutrients for scheduled field applications. |
| Direct & Indirect $\text{N}_2\text{O}$ | `EEEManager` | Major contributor to farm total GHG inventory (GWP100 factor: 265–298 $\text{CO}_2\text{e}$). |
| Nitrate Leaching & P Runoff | Environmental Reporting | Water quality indicators and environmental compliance metrics. |

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"I can set planting date earlier than weather data starts."* | Weather data must strictly span `simulation_start_date` to `simulation_end_date`. Mismatches cause index crashes. |
| *"Adding more fertilizer always increases yield linearly."* | Crop models follow Liebig's law of the minimum; water stress or temperature limits yield and excess N causes severe leaching and $\text{N}_2\text{O}$ surges. |
| *"Crop roots can grow deeper than the total soil depth defined."* | Cross-validation strictly enforces $\text{MaxRootDepth} \le \sum \text{LayerThickness}_i$. |

### 🚩 Diagnostic Red Flags
- Numerical instability / negative soil water $\rightarrow$ Inspect $\theta_{\text{sat}}, \theta_{\text{fc}}, \theta_{\text{wp}}$ relationships in `soil_*.json`.
- Zero crop yield at harvest $\rightarrow$ Verify planting date vs GDD accumulation requirements in `crop_*.json`.
- Missing manure application $\rightarrow$ Check if manure storage had sufficient inventory during the scheduled window.

---
name: rufas-field
description: Use when analyzing, configuring, or debugging the RuFaS Field, Soil, and Crop module, including multi-layer soil hydrology, Century/DayCent C/N biogeochemistry, crop phenology (GDD, RUE), tillage, fertilization/manure scheduling, or harvests.
---

# RuFaS Field, Soil & Crop Specialist Skill

## 1. Overview & Module Scope
The **RuFaS Field and Soil Module** (`RUFAS/biophysical/field/`) simulates multi-layer vertical soil hydrology, heat conduction, nutrient transformations (C, N, P), crop phenology, root dynamics, and agronomic management events (tillage, synthetic fertilization, manure application, and harvesting). Managed by `FieldManager`, it produces farm-grown forage/grain biomass for `FeedManager`, utilizes organic slurry from `ManureManager`, and reports soil emissions, nitrate leaching, and field machinery fuel use to `EEEManager`.

> [!IMPORTANT]
> If RuFaS tools report that RuFaS is not configured, ask the user where their RuFaS project directory is located on their machine, or suggest running `rufas-setup` / setting `RUFAS_PATH`.

---

## 2. Capabilities & When to Use

### Triggering Conditions & Use Cases
- Parameterizing field geometry, multi-layer soil physical properties ($\theta_{\text{fc}}, \theta_{\text{wp}}, \theta_{\text{sat}}, K_{\text{sat}}$, bulk density), and crop rotations.
- Modeling crop growth curves, radiation use efficiency (RUE), growing degree days (GDD), and stress factors (water, nitrogen, temperature).
- Configuring agronomic management calendars: tillage passes, synthetic fertilizer rates, manure slurry applications, and harvest timing.
- Tracking vertical soil biogeochemistry: mineralization, nitrification, denitrification, ammonia volatilization, nitrate leaching ($\text{NO}_3^-$), and direct/indirect $\text{N}_2\text{O}$ emissions.
- Investigating soil water balance anomalies, numerical hydraulic solver convergence failures, or crop harvest yield shortfalls.

### When NOT to Use
- Animal ration formulation or feed bunk allocation (use `rufas-animal`).
- Silo/bunker storage packing, fermentation losses, or aerobic face spoilage (use `rufas-feed`).
- Barn slurry collection, solid-liquid separation, or lagoon storage gas emissions (use `rufas-manure`).
- Whole-farm enterprise accounting or Scope 1-3 lifecycle aggregation (use `rufas-eee`).
- Full variable catalog lookup or graph traversal (use `rufas-brain`).

---

## 3. Module Architecture & Input Configuration Blobs
`FieldManager` orchestrates the daily field sequence: weather processing $\rightarrow$ management schedule dispatch (tillage, fertilizer, manure requests) $\rightarrow$ multi-layer hydrology and heat conduction $\rightarrow$ SOM/nutrient turnover $\rightarrow$ crop growth $\rightarrow$ harvest cuts and transferring `HarvestedCrop` objects to `FeedManager`.

| Blob Key | Typical Physical Path | Critical Parameters |
|---|---|---|
| `crop_configurations` | `input/data/crop_configurations/crop_config.json` | Field-to-crop rotation sequences, planting/harvest windows, base management rules. |
| `weather` | `input/data/weather/weather_*.json` | Daily precipitation, solar radiation, min/max air temp, wind speed, relative humidity. |
| `field_*` / `soil_*` | `input/data/field/field_*.json`, `soil_*.json` | Field area (ha), slope; layer depths, texture, $\theta_{\text{fc}}, \theta_{\text{wp}}, \theta_{\text{sat}}, K_{\text{sat}}$, initial C and N pools. |
| `crop_*` | `input/data/crop/crop_*.json` | Base GDD to maturity, optimal temperature, RUE ($\text{g/MJ}$), harvest index, root depth rate. |
| `tillage_schedule` | `input/data/tillage_schedule/*.json` | Implement type, operation date, tillage depth, residue incorporation fraction. |
| `fertilizer_schedule`| `input/data/fertilizer_schedule/*.json` | Application date, chemical form (urea, UAN, DAP, potash), N-P-K rate ($\text{kg/ha}$), depth. |
| `manure_schedule` | `input/data/manure_schedule/*.json` | Scheduled date, target application rate/volume, application method (broadcast, injection). |
| `tractor_dataset` | `input/data/EEE/tractors.json` | Tractor horsepower, implement draft coefficients, field operating speed and efficiency. |

---

## 4. Core Biophysical Mechanics & Governing Formulas
- **Multi-Layer Hydrology (Darcy-Richards Flow)**: Infiltration via Green-Ampt/SCS Curve Number; unsaturated downward percolation and redistribution:
  $$q = -K(\theta) \left( \frac{\partial \psi}{\partial z} + 1 \right)$$
  Potential evapotranspiration (Penman-Monteith) partitioned into soil evaporation and root-layer plant transpiration ($T_{\text{act}}$).
- **Soil Organic Matter & Nitrogen Turnover (Century/DayCent)**:
  - C pools: Active microbial biomass, slow humus (20–50 yr turnover), and passive resistant humus (200–1500 yr turnover).
  - Mineralization/Immobilization: Organic $\text{N} \rightleftharpoons \text{NH}_4^+$ regulated by microbial C:N stoichiometry and soil temperature/moisture rate modifiers.
- **Nitrification & Denitrification Fluxes**:
  - Nitrification: Aerobic $\text{NH}_4^+ \rightarrow \text{NO}_2^- \rightarrow \text{NO}_3^- + \text{N}_2\text{O}\text{ (byproduct)}$.
  - Denitrification: Anaerobic reduction ($\text{WFPS} > 60\%$): $\text{NO}_3^- \rightarrow \text{NO}_2^- \rightarrow \text{NO} \rightarrow \text{N}_2\text{O} \rightarrow \text{N}_2$.
  - Leaching: Downward convective flux of soluble $\text{NO}_3^-$ with drainage water escaping below the maximum root zone.
- **Crop Growth & Phenology**:
  - Thermal accumulation: $\text{GDD} = \max\left(\frac{T_{\max} + T_{\min}}{2} - T_{\text{base}}, 0\right)$.
  - Daily biomass gain: $\Delta \text{Biomass} = \text{IPAR} \cdot \text{RUE} \cdot \min(\text{Stress}_{\text{water}}, \text{Stress}_{\text{nitrogen}}, \text{Stress}_{\text{temp}})$.

---

## 5. Cross-Module Causal Influences & Whole-Farm Flow
- **Upstream Inputs**:
  - Receives daily weather time-series (air temperature, precipitation, solar radiation, humidity).
  - Receives organic N, TAN, organic/inorganic P, potassium, and volatile solids from `ManureManager` via `request_nutrients()`.
- **Downstream Outputs**:
  - Delivers `HarvestedCrop` biomass (dry matter, moisture, CP, NDF, energy) to `FeedManager` storage inventories.
  - Passes direct soil $\text{N}_2\text{O}$ emissions, indirect $\text{N}_2\text{O}$ (from volatilized $\text{NH}_3$ and leached $\text{NO}_3^-$), and tractor diesel consumption to `EEEManager`.
- **Feedback Dynamics**: Crop yield determines farm feed self-sufficiency and purchased feed requirements; manure nutrient uptake capacity regulates whole-farm land application limits.

---

## 6. Key Anchor Metrics & Biological Diagnostic Bounds
| Anchor Metric | Units | Diagnostic Benchmark | Anomaly Threshold & Root Cause |
|---|---|---|---|
| **Soil Nitrate ($\text{NO}_3\text{-N}$)** | $\text{kg N/ha}$ | $10.0 - 60.0\text{ kg/ha}$ (topsoil) | $>100\text{ kg N/ha}$ indicates excessive fertilization or uncoupled crop uptake; $<2\text{ kg/ha}$ triggers severe N stress. |
| **Daily $\text{N}_2\text{O}$ Emissions** | $\text{kg N/ha/day}$ | $0.001 - 0.08$ (background); $0.2 - 2.5$ (peak pulse) | $>4.0\text{ kg N/ha/day}$ indicates oversaturated WFPS ($>85\%$) following high N manure/fertilizer application. |
| **Nitrate Leaching** | $\text{kg N/ha/yr}$ | $15.0 - 45.0\text{ kg N/ha/yr}$ | $>80\text{ kg N/ha/yr}$ indicates heavy drainage through coarse soil without active cover crop sink. |
| **Corn Silage Yield** | $\text{kg DM/ha}$ | $14,000 - 22,000\text{ kg DM/ha}$ | $<10,000\text{ kg DM/ha}$ indicates acute drought/N stress or misaligned GDD maturity parameters. |
| **Alfalfa Multi-Cut Yield** | $\text{kg DM/ha/yr}$ | $8,000 - 16,000\text{ kg DM/ha/yr}$ | $<6,000\text{ kg DM/ha/yr}$ indicates inadequate cutting schedule or winterkill/water deficit. |
| **Evapotranspiration (ET)** | $\text{mm/day}$ | $1.0 - 7.5\text{ mm/day}$ (active canopy) | $\text{ET}_{\text{act}} \ll \text{ET}_{\text{pot}}$ indicates severe root zone soil moisture depletion ($\theta \approx \theta_{\text{wp}}$). |
| **Soil Organic Carbon (SOC)** | $\%$ | $1.5 - 4.5\%$ (top 30 cm) | $<0.8\%$ indicates chronic carbon depletion from excessive tillage and zero residue return. |

---

## 7. Dynamic Graph Brain Querying & Deep Variable Discovery
The Field & Soil module generates **744+ time-series variables** in output pools (e.g. `FieldDataReporter.send_soil_layer_daily_variables.*`). Query the Graph Memory Brain for exact column signatures, parameters, and causal links:

```bash
# 1. Lookup exact output variable signatures and units
python -m tools.rufas_brain lookup-var --name N2O_emissions
python -m tools.rufas_brain lookup-var --name nitrate_content --json

# 2. Trace upstream parameter impacts and downstream variables
python -m tools.rufas_brain trace-impact --param crop_configurations
python -m tools.rufas_brain trace-impact --param fertilizer_schedule

# 3. Query biophysical causal pathways in KùzuDB via OpenCypher
python -m tools.rufas_brain query "MATCH (p:InputParameter)-[:CAUSALLY_INFLUENCES]->(v:OutputVariable) WHERE v.module = 'field_soil' RETURN p.id, v.name, v.unit LIMIT 20"
```

---

## 8. Diagnostic Protocols & Red Flags
| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"Planting dates can precede weather data starting dates."* | Weather data must strictly encompass `simulation_start_date` to `simulation_end_date`. Mismatches cause indexing errors. |
| *"Increasing synthetic fertilizer always produces linear yield gains."* | Crop growth follows Liebig's law; once water or temperature is limiting, excess N surges leaching and $\text{N}_2\text{O}$ without increasing yield. |
| *"Crop roots can penetrate deeper than the total soil profile depth."* | Cross-validation strictly enforces $\text{MaxRootDepth} \le \sum \text{LayerThickness}_i$. |

### 🚩 Diagnostic Red Flags - STOP and Correct
- **Hydraulic Instability / Negative Soil Water**: Check $\theta_{\text{wp}} < \theta_{\text{fc}} < \theta_{\text{sat}}$ hierarchy and $K_{\text{sat}}$ in `soil_*.json`.
- **Zero Crop Yield at Harvest**: Verify accumulated GDD vs crop maturity threshold in `crop_*.json` and check for planting date failures.
- **Runoff / Leaching Spike**: Verify SCS Curve Number ($CN_2$) calibration and check for unaligned heavy precipitation vs fertilizer events.
- **Manure Application Missing**: Ensure storage had sufficient available nutrient volume when `FieldManager` called `request_nutrients()`.

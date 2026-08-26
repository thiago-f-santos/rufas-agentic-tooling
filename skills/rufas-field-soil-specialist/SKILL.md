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

## Simulation Output Variable Dictionary & Diagnostics

The Field & Soil module generates **744+ time-series output variables** (recorded via `FieldDataReporter`, `FieldManager`, and `Field` into `RuFaS/output/CSVs/csv_all_variables.txt`). Variables are segmented by field ID (`field='<field_id>'`), soil layer index (`layer='0'` to `layer='4'`), vadose zone (`vadose_zone_layer`), and crop planting cycle (`field='<field_id>',crop='<crop_name>',planted=<day>,<year>`).

### 1. Daily Field Hydrology & Evapotranspiration

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Biophysical Description & Source Method |
|---|---|---|---|
| `FieldDataReporter.send_field_daily_variables.transpiration.field='<field_id>' (mm)` | `mm` | `0.0 - 8.0` | Actual crop transpiration extracted from soil root layers (`FieldDataReporter.send_field_daily_variables`). |
| `FieldDataReporter.send_field_daily_variables.max_transpiration.field='<field_id>' (mm)` | `mm` | `0.0 - 9.0` | Maximum potential crop transpiration under non-limiting soil moisture. |
| `FieldDataReporter.send_field_daily_variables.max_evapotranspiration.field='<field_id>' (mm)` | `mm` | `0.5 - 10.0` | Penman-Monteith potential evapotranspiration (PET) based on net solar radiation, vapor pressure deficit, and wind. |
| `FieldDataReporter.send_soil_daily_variables.water_evaporated.field='<field_id>' (mm)` | `mm` | `0.0 - 4.5` | Direct soil evaporation from topsoil layer and wet canopy intercepted water. |
| `FieldDataReporter.send_soil_daily_variables.accumulated_runoff.field='<field_id>' (mm)` | `mm` | `0.0 - 50.0+` | Daily surface runoff generated when precipitation/snowmelt rate exceeds surface infiltration capacity. |
| `FieldDataReporter.send_soil_daily_variables.infiltrated_water.field='<field_id>' (mm)` | `mm` | `0.0 - 75.0+` | Net daily water volume infiltrating into soil layer 0 after surface runoff subtraction. |
| `FieldDataReporter.send_field_daily_variables.current_residue.field='<field_id>' (kg/ha)` | `kg/ha` | `500 - 8,000` | Crop residue and surface litter dry mass providing ground cover, shielding against soil erosion and solar evaporation. |
| `FieldDataReporter.send_field_daily_variables.days_into_watering_interval.field='<field_id>' (day)` | `day` | `0 - 30` | Elapsed days since last irrigation or scheduled watering event trigger. |
| `Field._get_manure_water.manure_water.field='<field_id>' (mm)` | `mm` | `0.0 - 25.0` | Moisture volume added to surface soil through slurry or liquid manure tanker application. |
| `FieldDataReporter.send_soil_layer_daily_variables.water_content.field='<field_id>',layer='<layer_id>' (mm)` | `mm` | `15.0 - 120.0` | Volumetric soil water depth within layer; dynamic state variable bounded by $\theta_{\text{wp}}$ and $\theta_{\text{sat}}$. |
| `FieldDataReporter.send_soil_layer_daily_variables.percolated_water.field='<field_id>',layer='<layer_id>' (mm)` | `mm` | `0.0 - 40.0` | Drainage flux percolating downward from layer $i$ into layer $i+1$ via gravity unsaturated flow. |
| `FieldDataReporter.send_soil_daily_variables.snow_content.field='<field_id>' (mm)` | `mm` | `0.0 - 200.0` | Water equivalent of surface snowpack insulating soil and delaying winter infiltration. |
| `FieldDataReporter.send_soil_daily_variables.snow_melt.field='<field_id>' (mm)` | `mm` | `0.0 - 30.0` | Daily water released from snowpack melt driven by ambient air temperature and degree-day coefficients. |

### 2. Multi-Layer Soil Biogeochemistry (`layer='0'` to `layer='4'`)

RuFaS models vertical soil organic matter (SOM) dynamics across discrete layers using Century/DayCent-derived multi-pool kinetics:

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Biogeochemical Description & Pool Dynamics |
|---|---|---|---|
| `FieldDataReporter.send_soil_layer_daily_variables.slow_carbon_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `3,000 - 25,000` | Moderately resistant humus carbon pool with turnover time of 20–50 years (`slow_carbon_amount`). |
| `FieldDataReporter.send_soil_layer_daily_variables.passive_carbon_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `10,000 - 60,000` | Recalcitrant, chemically and physically stabilized organic carbon pool with turnover time of 200–1500 years. |
| `FieldDataReporter.send_soil_layer_daily_variables.active_carbon_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `200 - 2,500` | Labile microbial biomass and readily decomposable soil organic carbon (turnover: 1–5 years). |
| `FieldDataReporter.send_soil_layer_daily_variables.total_soil_carbon_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `15,000 - 80,000` | Aggregate soil organic carbon mass in layer ($\text{Active} + \text{Slow} + \text{Passive} + \text{Litter}$). |
| `FieldDataReporter.send_soil_layer_daily_variables.slow_carbon_decomposition_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.1 - 5.0` | Daily microbial decomposition of slow organic carbon pool, generating heterotrophic $\text{CO}_2$ and mineral N. |
| `FieldDataReporter.send_soil_layer_daily_variables.passive_carbon_decomposition_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.01 - 0.8` | Daily microbial decomposition of passive carbon pool. |
| `FieldDataReporter.send_soil_layer_daily_variables.active_carbon_decomposition_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.5 - 15.0` | Daily microbial decomposition of active microbial biomass. |
| `FieldDataReporter.send_soil_layer_daily_variables.soil_overall_carbon_fraction.field='<field_id>',layer='<layer_id>' (fraction)` | `fraction` | `0.005 - 0.050` | Gravimetric fraction of organic carbon relative to total layer soil mass (e.g. 0.020 = 2.0% SOC). |
| `FieldDataReporter.send_soil_layer_daily_variables.metabolic_litter_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0 - 1,500` | Readily decomposable litter fraction with low C:N ratio (high nitrogen availability). |
| `FieldDataReporter.send_soil_layer_daily_variables.structural_litter_amount.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0 - 4,000` | Lignocellulosic litter fraction with high C:N ratio, subject to microbial immobilization. |
| `FieldDataReporter.send_soil_daily_variables.profile_carbon_total.field='<field_id>' (kg/ha)` | `kg/ha` | `40,000 - 250,000` | Sum of total soil organic carbon across the entire vertical soil column. |
| `FieldDataReporter.send_soil_daily_variables.profile_carbon_emissions.field='<field_id>' (kg/ha)` | `kg/ha` | `2.0 - 45.0` | Daily profile heterotrophic soil respiration ($\text{CO}_2\text{-C}$ loss to atmosphere). |

### 3. Nitrogen & Nutrient Fluxes (Leaching, N2O, NH3, Volatilization)

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Transformation & Fate Description |
|---|---|---|---|
| `FieldDataReporter.send_soil_layer_daily_variables.nitrate_content.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `1.0 - 80.0` | Soluble nitrate nitrogen ($\text{NO}_3^-\text{-N}$) available in soil solution for plant uptake or leaching. |
| `FieldDataReporter.send_soil_layer_daily_variables.ammonium_content.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.5 - 35.0` | Exchangeable ammonium nitrogen ($\text{NH}_4^+\text{-N}$) substrate for aerobic nitrification. |
| `FieldDataReporter.send_soil_layer_daily_variables.percolated_nitrates.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.0 - 12.0` | Nitrate leached (`nitrate_leached (kg N/ha)`) downward through layer drainage flux below root zone into vadose zone. |
| `FieldDataReporter.send_soil_layer_daily_variables.nitrous_oxide_emissions.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.0001 - 0.80` | Direct soil $\text{N}_2\text{O}$ emissions (`N2O_emissions (kg N/ha)`) from nitrification and incomplete denitrification. |
| `FieldDataReporter.send_soil_layer_daily_variables.ammonia_emissions.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.0 - 15.0` | Daily ammonia volatilization (`ammonia_volatilization (kg N/ha)`) following synthetic fertilizer or manure application. |
| `FieldDataReporter.send_soil_layer_daily_variables.dinitrogen_emissions.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.001 - 5.0` | Complete denitrification to benign inert dinitrogen ($\text{N}_2$) gas under anaerobic/high WFPS conditions. |
| `FieldDataReporter.send_soil_layer_annual_variables.annual_carbon_CO2_lost.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `500 - 4,500` | Annual cumulative microbial decomposition carbon lost (`annual_carbon_CO2_lost (kg/ha)`). |
| `FieldDataReporter.send_soil_layer_annual_variables.annual_nitrous_oxide_emissions_total.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.5 - 6.5` | Annual cumulative layer nitrous oxide emissions ($\text{kg N}_2\text{O-N/ha/yr}$). |
| `FieldDataReporter.send_soil_layer_annual_variables.annual_ammonia_emissions_total.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `2.0 - 35.0` | Annual cumulative layer ammonia volatilization ($\text{kg NH}_3\text{-N/ha/yr}$). |
| `FieldDataReporter.send_soil_layer_daily_variables.labile_inorganic_phosphorus_content.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `5.0 - 60.0` | Readily plant-available orthophosphate pool in layer solution. |
| `FieldDataReporter.send_soil_layer_daily_variables.active_inorganic_phosphorus_content.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `20.0 - 180.0` | Reversibly adsorbed inorganic P buffering the labile solution pool. |
| `FieldDataReporter.send_soil_layer_daily_variables.stable_inorganic_phosphorus_content.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `100.0 - 600.0` | Occluded and mineral-bound phosphorus with very slow release kinetics. |
| `FieldDataReporter.send_soil_layer_daily_variables.percolated_phosphorus.field='<field_id>',layer='<layer_id>' (kg/ha)` | `kg/ha` | `0.0 - 0.15` | Dissolved phosphorus leached with percolating water to deeper horizons. |
| `FieldDataReporter.send_soil_daily_variables.soil_phosphorus_runoff.field='<field_id>' (kg/ha)` | `kg/ha` | `0.0 - 2.5` | Particulate and dissolved reactive phosphorus transported in surface runoff. |

### 4. Crop Growth, Phenology & Harvest Yields

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Agronomic Description & Crop Growth Engine |
|---|---|---|---|
| `FieldDataReporter.send_crop_daily_variables.accumulated_heat_units (unitless)` | `unitless` | `0 - 2,800` | Accumulated thermal time (`GDD_accumulated`) above base temperature determining phenological stage. |
| `FieldDataReporter.send_crop_daily_variables.heat_fraction (unitless)` | `unitless` | `0.0 - 1.0` | Fraction of total thermal requirement accumulated (1.0 = physiological crop maturity). |
| `FieldDataReporter.send_crop_daily_variables.biomass_growth (kg/ha)` | `kg/ha` | `0 - 350` | Daily dry matter synthesized (`daily_biomass_gain (kg DM/ha)`) modulated by RUE and active stress multipliers. |
| `FieldDataReporter.send_crop_daily_variables.biomass (kg/ha)` | `kg/ha` | `0 - 22,000` | Cumulative total standing crop dry matter per hectare (above-ground + below-ground). |
| `FieldDataReporter.send_crop_daily_variables.above_ground_biomass (kg/ha)` | `kg/ha` | `0 - 18,000` | Standing vegetative and reproductive shoot dry matter. |
| `FieldDataReporter.send_crop_daily_variables.root_biomass (kg/ha)` | `kg/ha` | `0 - 4,500` | Below-ground root dry matter distributed across soil layer root profile. |
| `FieldDataReporter.send_crop_daily_variables.root_depth (mm)` | `mm` | `50 - 1,800` | Effective maximum depth of root extraction for water and nutrients. |
| `FieldDataReporter.send_crop_daily_variables.leaf_area_index (unitless)` | `unitless` | `0.0 - 6.5` | Canopy green leaf area index (LAI, $\text{m}^2\text{ leaf / m}^2\text{ ground}$). |
| `FieldDataReporter.send_crop_daily_variables.canopy_height (m)` | `m` | `0.05 - 3.2` | Vertical canopy height governing aerodynamic roughness and canopy interception. |
| `FieldDataReporter.send_crop_daily_variables.water_stress (unitless)` | `unitless` | `0.0 - 1.0` | Water limitation factor ($1.0 = \text{no stress}$, $0.0 = \text{severe drought halt}$). |
| `FieldDataReporter.send_crop_daily_variables.nitrogen_stress (unitless)` | `unitless` | `0.0 - 1.0` | Nitrogen limitation factor scaling photosynthetic efficiency. |
| `FieldDataReporter.send_crop_daily_variables.wet_yield_collected (kg/ha)` | `kg/ha` | `5,000 - 65,000` | Fresh weight forage/grain biomass collected at harvest (`harvested_yield_DM (kg/ha)` at target moisture). |
| `FieldDataReporter.send_crop_daily_variables.cut_biomass (kg/ha)` | `kg/ha` | `2,000 - 16,000` | Dry matter harvested and transferred to `FeedManager` inventory (`HarvestedCrop`). |
| `FieldDataReporter.send_crop_daily_variables.dry_matter_yield_residue (kg/ha)` | `kg/ha` | `500 - 5,000` | Non-harvested stubble, crown, and stover uncollected and returned to surface soil residue pool. |
| `FieldDataReporter.send_crop_daily_variables.yield_nitrogen (kg/ha)` | `kg/ha` | `30 - 320` | Nitrogen content exported from field inside harvested crop biomass. |
| `FieldDataReporter.send_crop_daily_variables.yield_phosphorus (kg/ha)` | `kg/ha` | `5 - 45` | Phosphorus exported from field in harvested biomass. |

---

## Diagnostic Validation Rules & Agronomic Benchmarks

When inspecting RuFaS field and soil simulation time-series, evaluate these physical boundary criteria:

1. **Daily Evapotranspiration Boundaries**:
   - Realistic actual daily ET: `1.0 - 8.0 mm/day` during mid-season vegetative growth; `0.0 mm/day` when soil is frozen or canopy is dormant.
   - Max ET > Actual ET indicates active crop water stress (`water_stress < 1.0`). If actual ET exceeds potential ET, check Penman-Monteith parameterization.

2. **Soil Hydrology & Layer Water Balance**:
   - Soil volumetric water content must strictly remain within $\theta_{\text{wp}} \le \theta \le \theta_{\text{sat}}$ (water tension between 10–33 kPa at field capacity and 1500 kPa at permanent wilting point).
   - Percolation only occurs when layer water exceeds field capacity ($\theta > \theta_{\text{fc}}$). Persistent saturation without drainage indicates underestimated $K_{\text{sat}}$ or missing subsurface tile drainage.

3. **Nitrogen Fluxes & $\text{N}_2\text{O}$ Emission Dynamics**:
   - Baseline background daily soil $\text{N}_2\text{O}$ emissions: `0.0001 - 0.08 kg N2O-N/ha/day`.
   - Post-application / rainfall pulse events: `0.2 - 2.5 kg N2O-N/ha/day` when water-filled pore space ($\text{WFPS}$) exceeds 60–75% and nitrate availability is high.
   - Annual direct $\text{N}_2\text{O}$ emissions: Typically `1.0 - 5.0 kg N2O-N/ha/yr` (equivalent to IPCC 1% default emission factor of applied N).

4. **Nitrate Leaching Benchmarks**:
   - Annual cumulative nitrate leaching: `10 - 45 kg NO3-N/ha/yr` on medium-textured silt loam soils; `30 - 90 kg NO3-N/ha/yr` on sandy/gravelly soils.
   - Leaching exceeding `>100 kg N/ha/yr` indicates severe timing misalignment (e.g. late fall manure application without cover crop or excessive synthetic N fertilizer rate).

5. **Soil Organic Carbon (SOC) Pool Proportions**:
   - In equilibrium soils, the passive carbon pool represents **60–85%**, slow carbon represents **15–35%**, and active microbial biomass represents **1–5%** of total soil organic carbon.
   - Topsoil (0–30 cm) total soil carbon typically totals `25,000 - 65,000 kg C/ha` (1.5–4.0% SOC).

6. **Crop Biomass & Yield Expectations**:
   - Corn Silage: `14,000 - 22,000 kg DM/ha` (40–65 t/ha wet at 35% DM).
   - Alfalfa (Multi-Cut Hay/Silage): `8,000 - 16,000 kg DM/ha` annual cumulative dry matter across 3–4 harvest cuts.
   - Grass / Cover Crop: `2,000 - 6,000 kg DM/ha`.

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


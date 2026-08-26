---
name: rufas-eee-specialist
description: Use when analyzing, configuring, or debugging the RuFaS Economics, Energy, and Emissions (EEE) module, including enterprise financial accounting (IOFC, COP), ASABE tractor fuel and electricity consumption, or whole-farm Scope 1-3 greenhouse gas lifecycle accounting (GWP100, FPCM).
---

# RuFaS Economics, Energy & Emissions (EEE) Specialist Skill

## Overview

The **RuFaS EEE Module** (`RUFAS/EEE/`) provides the whole-farm synthesis of enterprise financial profitability, stationary and mobile energy consumption, and lifecycle greenhouse gas (GHG) environmental footprints.

Managed by `EEEManager` (which coordinates `Economy`, `EnergyEstimator`, and `EmissionsEstimator`), it runs during simulation and in post-simulation processing (`_post_simulation_processing`), integrating time-series data from `HerdManager`, `FieldManager`, `FeedManager`, and `ManureManager`.

---

## When to Use

### Triggering Conditions & Symptoms
- Configuring economic parameters: milk component pricing (fat, protein, solids-not-fat), livestock cull/calf values, feed prices, labor rates, and equipment depreciation.
- Evaluating farm financial performance: Net Farm Income (NFI), Income Over Feed Cost (IOFC) per hundredweight (cwt) milk, or Cost of Production (COP).
- Modeling field machinery operations: tractor-implement pairing, draft requirements, ASABE D497 diesel fuel consumption ($\text{L/ha}$), and custom hire machinery costs.
- Estimating stationary electricity consumption: milking parlor vacuum pumps, milk bulk tank refrigeration, wash water heating, barn ventilation fans, and manure agitation.
- Computing total farm greenhouse gas (GHG) emissions and carbon intensity per kilogram of Fat and Protein Corrected Milk ($\text{kg CO}_2\text{e} / \text{kg FPCM}$).
- Evaluating Scope 3 upstream emissions from purchased feeds, commercial fertilizer manufacturing, and Land Use Change (LUC).

### When NOT to Use
- Biological mechanics of enteric methane production in the cow rumen (use `rufas-animal-specialist`).
- Biological kinetics of manure storage gas emissions (use `rufas-manure-specialist`).
- Soil biogeochemical denitrification and $\text{N}_2\text{O}$ modeling in fields (use `rufas-field-soil-specialist`).

---

## Inputs & Metadata Schemas

The EEE module is configured via 5 primary metadata blobs:

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `economy` | `input/data/EEE/economy_constants.json` | Component milk prices ($\$/\text{kg fat}$, $\$/\text{kg protein}$), somatic cell count (SCC) premiums/penalties, interest rate, labor wages, machinery depreciation lifespans, land rent. |
| `emission` | `input/data/EEE/emission_constants.json` | 100-year Global Warming Potential (GWP100) factors (e.g. IPCC AR5: $\text{CH}_4=28$, $\text{N}_2\text{O}=265$; AR6: $\text{CH}_4=27.2$, $\text{N}_2\text{O}=273$), grid electricity carbon intensity. |
| `purchased_feeds_emissions` | `input/data/EEE/purchased_feed_emissions.json` | Cradle-to-farm-gate embodied emission factors ($\text{kg CO}_2\text{e}/\text{kg DM}$) for purchased grains, meals, and supplements. |
| `purchased_feed_land_use_change_emissions` | `input/data/EEE/purchased_feed_luc_emissions.json` | Land Use Change (LUC) carbon penalty factors associated with deforestation/expansion (e.g. imported soybean meal). |
| `tractor_dataset` | `input/data/EEE/tractors.json` | Tractor horsepower ratings, PTO power, implement draft coefficients, operating speed, field efficiency constants. |
| `EEE_constants` | `input/data/EEE/EEE_constants.json` | Fuel energy densities, diesel emission factors ($\text{kg CO}_2/\text{L}$), propane/natural gas emission factors. |

---

## Core Biophysical & Analytical Mechanics

### 1. Enterprise Financial Accounting (`economy.py`)
- **Gross Revenue**:
  $$\text{Revenue}_{\text{milk}} = \sum \left( \text{MilkVol} \cdot P_{\text{base}} + \text{FatMass} \cdot P_{\text{fat}} + \text{ProteinMass} \cdot P_{\text{protein}} \pm \text{Adjustment}_{\text{SCC}} \right)$$
  $$\text{Revenue}_{\text{total}} = \text{Revenue}_{\text{milk}} + \text{Revenue}_{\text{culls}} + \text{Revenue}_{\text{calves}} + \text{Revenue}_{\text{crop\_sales}}$$
- **Operating Variable Expenses**:
  $$\text{Cost}_{\text{var}} = \text{Cost}_{\text{feed}} + \text{Cost}_{\text{fertilizer}} + \text{Cost}_{\text{seed}} + \text{Cost}_{\text{fuel}} + \text{Cost}_{\text{electric}} + \text{Cost}_{\text{vet}} + \text{Cost}_{\text{labor}}$$
- **Fixed & Capital Costs**:
  $$\text{Cost}_{\text{fixed}} = \text{Depreciation}_{\text{barns}} + \text{Depreciation}_{\text{machinery}} + \text{Interest} + \text{Taxes} + \text{Insurance} + \text{Rent}$$
- **Key Performance Indicators**:
  - **Net Farm Income (NFI)**: $\text{Revenue}_{\text{total}} - \text{Cost}_{\text{var}} - \text{Cost}_{\text{fixed}}$.
  - **Income Over Feed Cost (IOFC)**: $\text{Revenue}_{\text{milk}} - \text{Cost}_{\text{feed}}$ ($\$/\text{cow-day}$ or $\$ / \text{cwt}$).
  - **Cost of Production (COP)**: $\frac{\text{Cost}_{\text{total}} - \text{Non-Milk Revenue}}{\text{Cwt Milk Produced}}$.

### 2. Machinery & Energy Consumption (`energy.py`, `tractor.py`)
- **Tractor Field Fuel Consumption (ASABE D497)**:
  - Implement draft ($D$ in $\text{N}$) computed from soil texture, implement geometry, depth, and speed:
    $$D = F_i \cdot [A + B(S) + C(S^2)] \cdot w \cdot d$$
  - Equivalent PTO Power ($P_{\text{pto}}$ in $\text{kW}$):
    $$P_{\text{pto}} = \frac{D \cdot S}{3.6 \cdot E_m} + P_{\text{rotary}}$$
  - Fuel flow rate ($Q_{\text{avg}}$ in $\text{L/h}$) based on engine load ratio $X$:
    $$Q_{\text{avg}} = (0.22 \cdot X + 0.096) \cdot P_{\text{pto,max}}$$
- **Stationary Electricity Demand**:
  - Milking vacuum pumps: $\sim 0.05–0.10 \text{ kWh / cow-day}$.
  - Milk chilling refrigeration: proportional to milk volume and temperature drop ($\Delta T$).
  - Barn ventilation & circulation fans: function of temperature-humidity index (THI) and seasonal fan staging.

### 3. Greenhouse Gas Lifecycle Accounting (`emissions.py`)
Total whole-farm emissions ($\text{CO}_2\text{e}$) integrate all farm scopes:
$$\text{GHG}_{\text{total}} = \text{GHG}_{\text{enteric}} + \text{GHG}_{\text{manure}} + \text{GHG}_{\text{soil}} + \text{GHG}_{\text{machinery}} + \text{GHG}_{\text{electricity}} + \text{GHG}_{\text{purchased\_inputs}}$$

- **Scope 1 (Direct On-Farm)**:
  - Enteric $\text{CH}_4 \times \text{GWP}_{\text{CH4}}$
  - Manure storage $\text{CH}_4 \times \text{GWP}_{\text{CH4}} + \text{N}_2\text{O} \times \text{GWP}_{\text{N2O}}$
  - Soil direct & indirect $\text{N}_2\text{O} \times \text{GWP}_{\text{N2O}}$
  - Diesel combustion $\text{CO}_2$ ($2.68 \text{ kg CO}_2 / \text{L diesel}$)
- **Scope 2 (Indirect Energy)**:
  - Purchased grid electricity $\text{kWh} \times \text{GridFactor}_{\text{CO2e}}$
- **Scope 3 (Upstream Embodied)**:
  - Purchased feeds: $\sum \text{FeedMass}_k \times (\text{EF}_{\text{production}, k} + \text{EF}_{\text{LUC}, k})$
  - Synthetic fertilizer manufacturing: $\text{kg N} \times \text{EF}_{\text{N\_fert}} + \text{kg P} \times \text{EF}_{\text{P\_fert}}$

- **Functional Unit Carbon Intensity**:
  - Normalized to Fat and Protein Corrected Milk (FPCM):
    $$\text{FPCM (kg)} = \text{Milk (kg)} \cdot (0.1226 \cdot \text{Fat\%} + 0.0776 \cdot \text{Protein\%} + 0.2534)$$
    $$\text{Carbon Intensity} = \frac{\text{GHG}_{\text{total}} (\text{kg CO}_2\text{e})}{\text{Total FPCM (kg)}}$$

---

## Simulation Output Variable Dictionary & Diagnostics

The EEE module generates **16 daily simulation time-series variables** directly in the output CSVs (via `EmissionsEstimator.calculate_purchased_feed_emissions`), alongside comprehensive post-simulation lifecycle assessment (LCA), tractor diesel accounting, and enterprise economic outputs.

### 1. Purchased Feed Scope 3 Embodied & Land Use Change (LUC) Emissions

The 16 daily time-series variables recorded by `EmissionsEstimator` across purchased feed commodities:

| Simulation Output Variable (Full Column Signature) | Units | Typical Mean (Simulation) | Feed Commodity & Lifecycle Emissions Description |
|---|---|---|---|
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.23 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `0.45` | Upstream cradle-to-gate GHG emissions from purchased Corn Silage (ID 23). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.23 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `0.00` | Direct/indirect land use change (LUC) carbon penalty for Corn Silage (ID 23). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.44 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `197.67` | Upstream cradle-to-gate GHG emissions from purchased Alfalfa Hay (ID 44). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.44 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `52.03` | Land use change (LUC) carbon emissions associated with Alfalfa Hay (ID 44). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.50 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `412.23` | Upstream cradle-to-gate GHG emissions from purchased Grass Hay (ID 50). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.50 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `18.80` | Land use change (LUC) carbon emissions associated with Grass Hay (ID 50). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.95 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `53.29` | Upstream cradle-to-gate GHG emissions from purchased Canola Meal (ID 95). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.95 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `0.00` | Land use change (LUC) emissions for Canola Meal (ID 95). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.104 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `56.70` | Upstream cradle-to-gate GHG emissions from purchased Ground Dry Corn Grain (ID 104). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.104 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `0.00` | Land use change (LUC) emissions for Corn Grain (ID 104). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.110 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `437.93` | Upstream cradle-to-gate GHG emissions from Distillers Grains with Solubles / DDGS (ID 110). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.110 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `311.51` | Land use change (LUC) carbon emissions for DDGS (ID 110). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.202 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `22.86` | Upstream cradle-to-gate GHG emissions from purchased Soybean Meal (ID 202). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.202 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `0.00` | Land use change (LUC) carbon emissions for Soybean Meal (ID 202). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.302 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `715.01` | Upstream cradle-to-gate GHG emissions from purchased Mineral/Vitamin Premix (ID 302). |
| `EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions.302 (kg CO2 / kg DM)` | `kg CO2 / kg DM` | `136.71` | Land use change (LUC) emissions for Mineral/Vitamin Premix (ID 302). |

### 2. Farm-Grown Feed LCA & Direct Resource Allocations

Calculated during post-simulation processing (`EmissionsEstimator.estimate_farmgrown_feed_emissions` and `_calculate_and_report_lca_emissions`):

| Variable Signature | Units | Category | Description & Source Method |
|---|---|---|---|
| `lca_carbon_emissions_for_feed_<feed_id>` | `kg CO2e` | LCA Footprint | Cradle-to-farm-gate embedded carbon emissions allocated to farm-grown crops fed to animals. |
| `lca_land_use_change_emissions_for_feed_<feed_id>` | `kg CO2e` | LCA Footprint | Land use change carbon penalty allocated to farm-grown feeds fed to animals. |
| `direct_n2o_nitrogen_emissions_for_feed_<feed_id>` | `kg` | Soil Emissions | Crop-specific direct soil nitrous oxide emissions allocated by harvested area and feed consumption. |
| `ammonia_nitrogen_emissions_for_feed_<feed_id>` | `kg` | Air Quality | Crop-specific soil ammonia volatilization losses allocated to the fed crop biomass. |
| `nitrogen_fertilizer_applied_for_feed_<feed_id>` | `kg` | Resource Use | Synthetic mineral nitrogen fertilizer applied to produce the fed crop fraction. |
| `phosphorus_fertilizer_applied_for_feed_<feed_id>` | `kg` | Resource Use | Synthetic mineral phosphorus ($P_2O_5$) applied to produce the fed crop fraction. |
| `potassium_fertilizer_applied_for_feed_<feed_id>` | `kg` | Resource Use | Synthetic mineral potassium ($K_2O$) applied to produce the fed crop fraction. |
| `manure_nitrogen_applied_for_feed_<feed_id>` | `kg` | Organic Nutrients | Recycled manure nitrogen applied to fields to support the fed crop growth. |

### 3. Whole-Farm Carbon Footprint & Scope 1-3 Summary

| Variable / Metric | Units | Scope | Biophysical Source & Calculation Method |
|---|---|---|---|
| `total_farm_ghg_co2e` | `kg CO2e` | Total Farm | Whole-farm gross greenhouse gas emissions aggregated across Scope 1, Scope 2, and Scope 3 lifecycle sources. |
| `carbon_intensity_fpcm` | `kg CO2e / kg FPCM` | Benchmark | Net carbon footprint normalized per kilogram of Fat and Protein Corrected Milk produced (`total_farm_ghg_co2e / total_FPCM_kg`). |
| `enteric_ch4_ghg_co2e` | `kg CO2e` | Scope 1 Direct | Cumulative rumen enteric methane emissions converted via GWP100 ($\text{CH}_4 \times 28.0$). |
| `manure_ch4_ghg_co2e` | `kg CO2e` | Scope 1 Direct | Manure housing and long-term storage methane emissions ($\text{CH}_4 \times 28.0$). |
| `manure_n2o_ghg_co2e` | `kg CO2e` | Scope 1 Direct | Direct and indirect nitrous oxide emissions from manure crusts, storage pits, and compost ($\text{N}_2\text{O} \times 265.0$). |
| `soil_n2o_ghg_co2e` | `kg CO2e` | Scope 1 Direct | Direct field soil nitrification/denitrification and indirect leaching/volatilization $\text{N}_2\text{O} \ emissions ($\text{N}_2\text{O} \times 265.0$). |
| `machinery_diesel_ghg_co2e` | `kg CO2e` | Scope 1 Direct | On-farm mobile tractor and self-propelled machinery fuel combustion ($2.68 \text{ kg CO}_2\text{/L diesel}$). |
| `purchased_electricity_ghg_co2e` | `kg CO2e` | Scope 2 Indirect | Stationary power demand for milking, cooling, and ventilation multiplied by regional grid emission factor. |
| `purchased_feed_ghg_co2e` | `kg CO2e` | Scope 3 Upstream | Total upstream cradle-to-farm-gate embedded emissions plus LUC from all purchased ration feeds (`purchased_feed_emissions + land_use_change_emissions`). |
| `fertilizer_manufacturing_ghg_co2e` | `kg CO2e` | Scope 3 Upstream | Upstream energy and chemical processing emissions from synthetic N, P, and K fertilizer production. |

### 4. Enterprise Financial Performance & Cost of Production

| Variable / Metric | Units | Economic Role & Analytical Formula |
|---|---|---|
| `annual_net_farm_income` | `$` | Whole-farm bottom-line profitability: $\text{Total Gross Revenue} - \text{Total Operating Expenses} - \text{Fixed Overhead \& Depreciation}$. |
| `IOFC_per_cwt` | `$/cwt` | Income Over Feed Cost per hundredweight ($100\text{ lbs}$) milk: $(\text{Milk Revenue} - \text{Purchased \& Farm Feed Costs}) / \text{Cwt Milk}$. |
| `total_milk_revenue` | `$` | Gross revenue from base milk volume plus butterfat, true protein, and solids-not-fat component values $\pm$ SCC adjustments. |
| `total_operating_expenses` | `$` | Sum of variable expenses: purchased feeds, fertilizer, seed, chemical crop protection, diesel fuel, electricity, veterinary/breeding, and hired labor. |
| `cost_of_production_cwt` | `$/cwt` | Full economic cost of production per hundredweight milk: $(\text{Total Expenses} - \text{Non-Milk Revenue}) / \text{Cwt Milk Produced}$. |
| `livestock_sales_revenue` | `$` | Revenue from bull calf sales, replacement heifer sales, and market cull cows. |
| `feed_expenses_total` | `$` | Aggregate cost of all purchased commercial commodities, grains, custom minerals, and purchased forages. |

### 5. Mobile Machinery & Stationary Energy Accounting

| Variable / Signature | Units | Domain | Description & Source Method |
|---|---|---|---|
| `diesel_fuel_liters_total` | `L` | Whole Farm | Total mobile tractor diesel fuel consumed across all tillage, planting, fertilization, spraying, manure haulage, and harvest passes (`EnergyEstimator`). |
| `electricity_kwh_total` | `kWh` | Whole Farm | Total stationary electric power consumed by milking vacuum pumps, bulk tank chillers, water heaters, and barn ventilation fans. |
| `annual_<field_name>_tractor_implement_diesel_consumption_for_<year>` | `L` | Field Specific | Annual fuel consumed on a specific field across all mechanization events (`annual_<field_name>_tractor_implement_diesel_consumption_for_<year>`). |
| `annual_total_tractor_implement_diesel_consumption_for_<year>` | `L` | Fleet Total | Annual aggregate diesel fuel consumed by the tractor fleet (`annual_total_tractor_implement_diesel_consumption_for_<year>`). |
| `diesel_consumption_tractor_implement_liters_per_ha` | `L/ha` | Operation Specific | Event-specific diesel fuel application rate computed using ASABE D497 draft equations. |

---

## Diagnostic Validation Rules & Environmental Benchmarks

When evaluating RuFaS EEE module outputs, verify simulation results against established dairy science and agricultural engineering benchmarks:

### 1. Carbon Footprint & Scope 1-3 Intensity
- **Whole-Farm Carbon Intensity**:
  - Typical US dairy confinement freestall systems range between **`0.80 - 1.40 kg CO2e / kg FPCM`**.
  - Intensive pasture / low-input systems: **`0.70 - 1.10 kg CO2e / kg FPCM`**.
  - Farms with high purchased feed reliance or high-LUC imported soybean meals may reach **`1.40 - 2.00+ kg CO2e / kg FPCM`**.
  - Values below `0.60 kg CO2e/kg FPCM` or above `2.50 kg CO2e/kg FPCM` indicate configuration anomalies (e.g. missing enteric methane, omitted feed purchases, or misconfigured GWP factors).
- **Emissions Source Partitioning**:
  - **Enteric Methane ($\text{CH}_4$)**: Typically accounts for **`40% - 50%`** of total farm GHG.
  - **Manure Management ($\text{CH}_4$ & $\text{N}_2\text{O}$)**: Typically accounts for **`20% - 35%`** (higher with open liquid lagoons, lower with digesters/solid separation).
  - **Soil Emissions ($\text{N}_2\text{O}$)**: Typically **`5% - 15%`**.
  - **Scope 3 Purchased Feeds & Fertilizers**: Typically **`15% - 30%`** (can exceed 40% if high Land Use Change factors are active).
  - **Direct Fuel & Electricity**: Typically **`3% - 8%`**.

### 2. Machinery Diesel & Stationary Energy
- **Field Machinery Fuel Consumption**:
  - Annual crop rotation tractor diesel consumption typically ranges between **`60 - 120 L/ha/yr`** (e.g., corn silage: `80 - 110 L/ha`, alfalfa: `50 - 90 L/ha`).
  - Single field operation diesel rates:
    - Chisel plow / subsoiling: `15 - 25 L/ha`.
    - Disk harrow / field cultivator: `6 - 12 L/ha`.
    - Planter / drill: `3 - 7 L/ha`.
    - Forage harvester (chopping corn silage): `25 - 45 L/ha`.
    - Liquid manure tanker haulage: `15 - 35 L/ha`.
- **Stationary Electricity Demand**:
  - Milking & milk cooling: **`0.08 - 0.14 kWh / kg milk produced`**.
  - Daily barn electricity: **`1.5 - 3.5 kWh / cow-day`** (depending on mechanical ventilation and lighting).

### 3. Enterprise Financial Feasibility
- **Income Over Feed Cost (IOFC)**:
  - Typical US dairy benchmark: **`$8.00 - $14.00 / cwt milk`**.
  - An IOFC below `$6.00 / cwt` suggests severe feed price inflation, diet over-supplementation, or low milk component tests.
- **Feed Cost Share**:
  - Feed expenses represent **`45% - 60%`** of total cash operating expenses on typical commercial dairy operations.

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"Scope 3 emissions from purchased feeds can be ignored."* | Purchased feeds constitute 20–40% of a dairy farm's total carbon footprint, especially when Land Use Change (LUC) factors are active for imported protein meals. |
| *"Electricity emissions are constant across regions."* | Regional grid carbon intensities vary from `<0.1 kg CO2e/kWh` (hydro/nuclear) to `>0.7 kg CO2e/kWh` (coal-heavy grids). Specify accurate grid factors in `emission_constants.json`. |
| *"Higher milk yield always guarantees higher profit."* | If marginal milk production requires expensive purchased concentrates or increases metabolic culling, IOFC and Net Farm Income may decrease. |
| *"Tractor fuel is just a flat rate per hour."* | RuFaS implements ASABE D497 physics-based draft modeling taking into account soil texture (% clay), implement width, tillage depth, and travel speed. |

### 🚩 Diagnostic Red Flags
- Negative Net Farm Income with normal milk production $\rightarrow$ Check feed price parameters in `economy_constants.json` or excessive purchased feed volumes in `feed_storage_instances.json`.
- Abnormally high tractor diesel consumption ($>180\text{ L/ha}$) $\rightarrow$ Check implement draft coefficients, excessive tillage passes, or erroneous field production size in management schedules.
- Missing farm-grown feed LCA outputs $\rightarrow$ Ensure post-simulation `EEEManager.estimate_all` executed during simulation termination.
- Carbon intensity $<0.5\text{ kg CO}_2\text{e/kg FPCM}$ $\rightarrow$ Verify that animal enteric methane and manure storage models were enabled in simulation metadata.


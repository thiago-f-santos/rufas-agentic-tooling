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

## Outputs & Synthesis

| Output Variable / Metric | Role in RuFaS |
|---|---|
| `annual_net_farm_income`, `IOFC_per_cwt` | Financial feasibility and economic viability of management scenarios. |
| `total_farm_ghg_co2e`, `carbon_intensity_fpcm` | Farm environmental footprint and decarbonization benchmark metric. |
| `diesel_fuel_liters_total`, `electricity_kwh_total` | Farm energy budget and efficiency tracking. |
| `enteric_vs_manure_vs_soil_ghg_breakdown` | Identifies major emission hotspots across the biophysical modules. |

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"Scope 3 emissions from purchased feeds can be ignored."* | Purchased feeds often constitute 20–40% of a dairy farm's total carbon footprint, especially when including Land Use Change (LUC). |
| *"Electricity emissions are constant across regions."* | Regional grid carbon intensities vary significantly. Specify accurate grid emission factors in `emission_constants.json`. |
| *"Higher milk yield always guarantees higher profit."* | If marginal milk gains require expensive purchased concentrates or increase metabolic culling, IOFC and Net Farm Income may decrease. |

### 🚩 Diagnostic Red Flags
- Negative Net Farm Income with normal milk production $\rightarrow$ Check feed price parameters in `economy_constants.json` or excessive purchased feed volumes.
- Abnormally high tractor diesel consumption $\rightarrow$ Check implement draft coefficients and field pass counts in management schedules.
- Missing farm-grown feed emissions $\rightarrow$ Ensure post-simulation `EEEManager.estimate_all` executed during simulation termination.

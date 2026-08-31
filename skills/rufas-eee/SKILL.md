---
name: rufas-eee
description: Use when analyzing, configuring, or debugging the RuFaS Economics, Energy, and Emissions (EEE) module, including enterprise financial accounting (IOFC, COP, NFI), ASABE tractor fuel and electricity consumption, or whole-farm Scope 1-3 greenhouse gas lifecycle accounting (GWP100, FPCM carbon intensity).
---

# RuFaS Economics, Energy & Emissions (EEE) Specialist Skill

## 1. Overview & Module Scope
The **RuFaS EEE Module** (`RUFAS/EEE/`) synthesizes whole-farm financial profitability, mobile machinery and stationary energy consumption, and lifecycle greenhouse gas (GHG) environmental footprints. Managed by `EEEManager` (which orchestrates `Economy`, `EnergyEstimator`, and `EmissionsEstimator`), it executes during simulation runtime (tracking daily purchased feed emissions) and during post-simulation processing (`_post_simulation_processing`), integrating time-series data from `HerdManager`, `FieldManager`, `FeedManager`, and `ManureManager` to generate farm sustainability and financial balance sheets.

## 2. Capabilities & When to Use
- **Triggering Conditions**:
  - Configuring economic parameters: milk component pricing (fat, protein, solids-not-fat), livestock cull/calf values, feed prices, labor wages, interest rates, and equipment depreciation.
  - Evaluating farm financial performance: Net Farm Income (NFI), Income Over Feed Cost (IOFC) per hundredweight ($/cwt), or Cost of Production (COP).
  - Modeling field machinery operations: ASABE D497 tractor-implement draft dynamics, diesel fuel consumption ($\text{L/ha}$), and custom hire machinery costs.
  - Estimating stationary electricity demand: milking parlor vacuum pumps, bulk tank milk refrigeration, wash water heating, and barn ventilation fans.
  - Computing whole-farm greenhouse gas (GHG) emissions and carbon intensity per kilogram of Fat and Protein Corrected Milk ($\text{kg CO}_2\text{e} / \text{kg FPCM}$).
  - Quantifying Scope 3 upstream embodied emissions from purchased feeds, synthetic fertilizer manufacturing, and Land Use Change (LUC).
- **Negative Routing**:
  - Enteric methane biological fermentation mechanics in the cow rumen $\rightarrow$ `rufas-animal`.
  - Manure storage kinetics, composting, and lagoon $\text{CH}_4/\text{NH}_3/\text{N}_2\text{O}$ emissions $\rightarrow$ `rufas-manure`.
  - Soil biogeochemical denitrification and $\text{N}_2\text{O}$ field fluxes $\rightarrow$ `rufas-field`.
  - Feed storage inventory drawdown, degradation, and bunker spoilage $\rightarrow$ `rufas-feed`.
  - Cross-module graph queries and variable catalog searches $\rightarrow$ `rufas-brain`.

## 3. Module Architecture & Input Configuration Blobs
- **Execution Pipeline**:
  - *Runtime*: `EmissionsEstimator` records daily purchased feed embedded emissions and Land Use Change (LUC) penalties (`calculate_purchased_feed_emissions`).
  - *Post-Simulation (`EEEManager.estimate_all`)*: `EnergyEstimator` computes ASABE tractor diesel and stationary electricity $\rightarrow$ `EmissionsEstimator` integrates Scope 1 (enteric, manure, soil, diesel), Scope 2 (grid electricity), and Scope 3 (purchased feeds, fertilizers, LUC) $\rightarrow$ `Economy` computes revenues, variable/fixed costs, IOFC, COP, and Net Farm Income.
- **Primary Input Blobs**:
  | Blob Key | Physical Path (Typical) | Critical Parameters |
  |---|---|---|
  | `economy` | `input/data/EEE/economy_constants.json` | Milk component prices ($\$/\text{kg fat}$, $\$/\text{kg protein}$), SCC adjustments, labor wages, interest rate, depreciation lifespans, land rent. |
  | `emission` | `input/data/EEE/emission_constants.json` | 100-year GWP factors (IPCC AR5: $\text{CH}_4=28$, $\text{N}_2\text{O}=265$; AR6: $\text{CH}_4=27.2$, $\text{N}_2\text{O}=273$), grid electricity emission factor ($\text{kg CO}_2\text{e/kWh}$). |
  | `purchased_feeds_emissions` | `input/data/EEE/purchased_feed_emissions.json` | Cradle-to-farm-gate embodied carbon emission factors ($\text{kg CO}_2\text{e/kg DM}$) for purchased feeds/supplements. |
  | `purchased_feed_land_use_change_emissions` | `input/data/EEE/purchased_feed_luc_emissions.json` | Land Use Change (LUC) carbon penalty factors ($\text{kg CO}_2\text{e/kg DM}$) for deforestation/expansion risk feeds. |
  | `EEE_constants` | `input/data/EEE/EEE_constants.json` | Fuel energy densities, diesel emission factor ($2.68\text{ kg CO}_2/\text{L}$), propane/natural gas emission factors. |
  | `tractor_dataset` | `input/data/EEE/tractors.json` | Tractor horsepower, PTO power ratings, implement draft coefficients ($A, B, C$), speed, field efficiency. |

## 4. Core Biophysical & Economic Formulas
- **100-Year Global Warming Potential (GWP100 - IPCC AR5)**:
  $$\text{GHG}_{\text{total}} (\text{kg CO}_2\text{e}) = \text{CO}_2 + 28 \cdot \text{CH}_4 + 265 \cdot \text{N}_2\text{O}$$
- **Fat and Protein Corrected Milk (FPCM) & Carbon Intensity**:
  $$\text{FPCM (kg)} = \text{Milk (kg)} \cdot (0.1226 \cdot \text{Fat\%} + 0.0776 \cdot \text{Protein\%} + 0.2534)$$
  $$\text{Farm Carbon Intensity} = \frac{\text{GHG}_{\text{total}} (\text{kg CO}_2\text{e})}{\text{Total FPCM (kg)}}$$
- **Scope 1, 2, and 3 Emissions Partitioning**:
  - **Scope 1 (Direct On-Farm)**: $\text{GHG}_{\text{enteric}} (\text{CH}_4 \times 28) + \text{GHG}_{\text{manure}} (\text{CH}_4 \times 28 + \text{N}_2\text{O} \times 265) + \text{GHG}_{\text{soil}} (\text{N}_2\text{O} \times 265) + \text{GHG}_{\text{diesel}} (\text{Diesel L} \times 2.68)$.
  - **Scope 2 (Indirect Energy)**: $\text{Electricity}_{\text{purchased}} (\text{kWh}) \times \text{GridFactor}_{\text{CO2e}}$.
  - **Scope 3 (Upstream Embodied)**: $\sum \text{FeedMass}_k \times (\text{EF}_{\text{production}, k} + \text{EF}_{\text{LUC}, k}) + \sum \text{Fertilizer}_i \times \text{EF}_{\text{fert}, i}$.
- **Machinery Diesel Fuel Consumption (ASABE D497)**:
  - Implement Draft: $D = F_i \cdot [A + B(S) + C(S^2)] \cdot w \cdot d$
  - Equivalent PTO Power: $P_{\text{pto}} = \frac{D \cdot S}{3.6 \cdot E_m} + P_{\text{rotary}}$
  - Average Fuel Flow: $Q_{\text{avg}} = (0.22 \cdot X + 0.096) \cdot P_{\text{pto,max}}$ ($X = \text{engine load ratio}$)
- **Enterprise Financial Performance & Cash Flow**:
  - **Gross Revenue**: $\text{Revenue}_{\text{milk}} (\text{Volume, Fat, Protein, SCC}) + \text{Revenue}_{\text{culls}} + \text{Revenue}_{\text{calves}} + \text{Revenue}_{\text{crops}}$.
  - **Operating Variable Expenses**: $\text{Cost}_{\text{feed}} + \text{Cost}_{\text{fertilizer/seed}} + \text{Cost}_{\text{fuel/electricity}} + \text{Cost}_{\text{vet/breeding}} + \text{Cost}_{\text{labor}}$.
  - **Fixed & Capital Costs**: $\text{Depreciation}_{\text{structures}} + \text{Depreciation}_{\text{machinery}} + \text{Interest} + \text{Taxes} + \text{Insurance} + \text{Land Rent}$.
  - **Net Farm Income (NFI)**: $\text{Gross Revenue} - \text{Operating Variable Expenses} - \text{Fixed Costs}$.
  - **Income Over Feed Cost (IOFC)**: $(\text{Revenue}_{\text{milk}} - \text{Cost}_{\text{feed}}) / \text{Cwt Milk Produced}$.
  - **Cost of Production (COP)**: $(\text{Total Expenses} - \text{Non-Milk Revenue}) / \text{Cwt Milk Produced}$.

## 5. Cross-Module Causal Influences & Whole-Farm Flow
- **Upstream Inflows (Aggregations)**:
  - `HerdManager`: Delivers daily milk volume, fat %, protein %, enteric $\text{CH}_4$, and livestock cull/calf sales.
  - `FieldManager`: Delivers tractor passes, synthetic fertilizer applications, and soil direct/indirect $\text{N}_2\text{O}$ emissions.
  - `ManureManager`: Delivers housing and storage $\text{CH}_4$, $\text{N}_2\text{O}$, and $\text{NH}_3$ emissions, plus digester biogas energy offsets.
  - `FeedManager`: Delivers purchased commercial feed quantities and farm-grown feed drawdown balances.
- **Downstream Outflows (Whole-Farm Reporting)**:
  - Synthesizes whole-farm environmental sustainability metrics (carbon intensity per kg FPCM, Scope 1–3 breakdowns).
  - Generates comprehensive farm enterprise financial statements (operating margins, net returns, IOFC/cwt, COP/cwt).

## 6. Key Anchor Metrics & Biological/Economic Sanity Bounds
| Anchor Metric | Units | Diagnostic Benchmark | Anomaly Threshold & Root Cause |
|---|---|---|---|
| **Farm Carbon Intensity** | kg CO2e / kg FPCM | 0.85 – 1.35 (US Freestall) | `< 0.50`: omitted enteric $\text{CH}_4$ or manure models; `> 1.80`: high LUC penalty or low feed efficiency. |
| **Enterprise Net Return** | $/cwt | $1.50 – $5.00 / cwt | `< -$2.00 / cwt`: feed price inflation, low component test, or excessive debt/depreciation overhead. |
| **Income Over Feed Cost (IOFC)** | $/cwt | $8.00 – $14.00 / cwt | `< $6.00 / cwt`: diet over-supplementation, emergency spot purchases, or depressed milk prices. |
| **Total Scope 1 GHG Emissions** | kg CO2e/day | Herd/acreage-scaled (~65–80% of total) | `< 50%` of total: missing livestock emission streams or disproportional Scope 3 inputs. |
| **Tractor Diesel Consumption** | L/ha/yr | 60 – 120 L/ha/yr (crop rotation) | `> 180 L/ha`: draft coefficients too high, excessive tillage passes, or erroneous field acreage. |
| **Milking & Cooling Electricity** | kWh/kg milk | 0.08 – 0.14 kWh/kg milk | `> 0.22`: oversized vacuum pumps, absent precoolers, or excessive winter ventilation fan staging. |
| **Purchased Feed Scope 3 Share** | % of total GHG | 15.0 – 30.0% | `> 45.0%`: severe feed deficit requiring massive off-farm concentrate imports with active LUC factors. |

## 7. Dynamic Graph Brain Querying & Deep Variable Discovery
The EEE module generates **16 daily simulation time-series variables** (`EmissionsEstimator.*`) alongside comprehensive post-simulation LCA, energy, and economic reporting. Discover signatures, parameters, and causal connections via `tools/rufas_brain.py`:
```bash
# 1. Search EEE output variable signatures, units, and categories
python -m tools.rufas_brain lookup-var --name carbon_intensity
python -m tools.rufas_brain lookup-var --name purchased_feed_emissions
python -m tools.rufas_brain lookup-var --name net_farm_income

# 2. Trace upstream parameter causal pathways and downstream whole-farm impacts
python -m tools.rufas_brain trace-impact --param EEE_constants
python -m tools.rufas_brain trace-impact --param economy
python -m tools.rufas_brain trace-impact --param emission

# 3. Query emission drivers and statistical correlations via OpenCypher
python -m tools.rufas_brain query "MATCH (p:InputParameter)-[r:CORRELATES_WITH]->(v:OutputVariable) WHERE v.category = 'emissions' RETURN p.id, v.name, r.pearson_r ORDER BY abs(r.pearson_r) DESC LIMIT 15"
python -m tools.rufas_brain query "MATCH (p:InputParameter)-[:CAUSALLY_INFLUENCES]->(v:OutputVariable) WHERE v.module = 'eee' RETURN p.id, v.name, v.unit"
```

## 8. Diagnostic Protocols & Red Flags
| Diagnostic Red Flag | Probable Root Cause | Corrective Protocol |
|---|---|---|
| **Unrealistically Low Carbon Intensity (<0.5 kg CO2e/kg FPCM)** | Missing enteric methane or manure storage simulation in scenario configuration. | Verify `animal` and `manure_management` execution flags in metadata; check GWP factors in `emission_constants.json`. |
| **Negative Net Farm Income / Negative Margin** | Depressed milk component prices, extreme feed purchase expenses, or oversized machinery depreciation. | Inspect price parameters in `economy_constants.json` and examine ration feed cost / storage shrink in `feed_storage_instances.json`. |
| **Scope 3 Purchased Feed Emission Spikes** | Active high Land Use Change (LUC) factors on imported protein meal or excessive spot feed purchases. | Check `purchased_feed_luc_emissions.json` and verify ration formulation bounds in `user_feeds.json`. |
| **Excessive Tractor Diesel Consumption (>180 L/ha)** | Implement draft coefficients too high or excessive tillage passes scheduled. | Inspect ASABE parameters in `tractors.json` and tillage frequency in `tillage_schedule/*.json`. |
| **Missing Post-Simulation LCA Outputs** | Simulation terminated prematurely before post-processing or filter file omitted. | Check `output/logs/errors.txt` and ensure `EEEManager.estimate_all` executed during simulation teardown. |

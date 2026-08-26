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

---

## Simulation Output Variable Dictionary & Diagnostics

The Manure Management module generates **264 time-series output variables** across collection handlers, mechanical separators, outdoor slurry storage basins, composting systems, and field nutrient delivery interfaces (exported into `RuFaS/output/CSVs/csv_all_variables.txt` via `ManureManager`).

Variables are organized by hierarchical subsystem prefixes:
- `Manure.SingleStreamHandler.<HandlerType>.<handler_id>.<variable> (<unit>)`
- `Manure.ParlorCleaningHandler.ParlorCleaningHandler.<handler_id>.<variable> (<unit>)`
- `Manure.Separator.ScrewPress.<separator_id>.<Stream>_<variable> (<unit>)`
- `Manure.Storage.SlurryStorageOutdoor.<storage_id>.<variable> (<unit>)`
- `Manure.Storage.Composting.<storage_id>.<variable> (<unit>)`

---

### 1. Housing Collection & Barn Floor Emissions

RuFaS tracks 19 daily biophysical and emission variables for each collection handler instance across animal cohorts:
- `lac_alley_scraper` (lactating cow free-stall mechanical alley scraper)
- `growing_alley_scraper` (heifer/growing barn alley scraper)
- `closeup_manual_scraper` (dry/transition cow bedded pack manual scraper)
- `calf_manual_scraper` (calf housing manual scraper)
- `parlor_cleaning_handler` (milking parlor flush / wash down system)

| Simulation Output Variable (Full Column Signature) | Units | Typical Range (Lactating Herd) | Biophysical Description & Kinetics |
|---|---|---|---|
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.housing_CO2_emissions (kg)` | `kg` | `20.0 - 50.0` | Daily carbon dioxide emissions generated from aerobic microbial respiration on barn floor surfaces. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.housing_methane_emissions (kg)` | `kg` | `0.10 - 0.50` | Anaerobic floor methane emissions from transient slurry pooling before scraper cycle. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.housing_ammonia_N_emissions (kg)` | `kg` | `1.5 - 6.0` | Volatilized ammoniacal nitrogen ($\text{NH}_3\text{-N}$) from hydrolyzed urinary urea on barn floor. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.barn_temperature (°C)` | `°C` | `2.0 - 32.0` | Modeled indoor barn ambient temperature governing urea hydrolysis and ammonia mass transfer. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_mass (kg)` | `kg` | `4,500 - 8,000` | Total wet mass of scraped manure slurry, urine, and incorporated bedding. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_water (kg)` | `kg` | `3,900 - 7,100` | Total water content of scraped slurry stream ($86 - 92\%$ of wet mass). |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_total_solids (kg)` | `kg` | `550 - 950` | Total solids dry matter (DM) collected from barn floor ($8 - 14\%$ DM). |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_total_volatile_solids (kg)` | `kg` | `450 - 800` | Total volatile solids ($\text{TVS} = \text{DVS} + \text{NDVS} + \text{Bedding VS}$) available for conversion. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_degradable_volatile_solids (kg)` | `kg` | `250 - 500` | Readily biodegradable volatile solids (DVS) accessible for rapid anaerobic methanogenesis. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_non_degradable_volatile_solids (kg)` | `kg` | `150 - 300` | Refractory/lignified volatile solids (NDVS) resistant to standard digestion. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_bedding_non_degradable_volatile_solids (kg)` | `kg` | `20 - 150` | Non-degradable volatile solids contributed by sawdust, straw, or recycled bedding materials. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_ash (kg)` | `kg` | `60 - 140` | Incombustible mineral matter (fecal ash + sand/dirt). |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_nitrogen (kg)` | `kg` | `22.0 - 42.0` | Total Nitrogen (TN = Org-N + TAN) collected daily from the housing unit. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_ammoniacal_nitrogen (kg)` | `kg` | `8.0 - 18.0` | Total Ammoniacal Nitrogen ($\text{TAN} = \text{NH}_4^+ + \text{NH}_3$) remaining after floor volatilization. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_phosphorus (kg)` | `kg` | `2.5 - 5.5` | Total elemental phosphorus (P) excreted and gathered in housing stream. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_potassium (kg)` | `kg` | `12.0 - 26.0` | Total elemental potassium (K) gathered in housing stream. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_volume (m^3)` | `m^3` | `4.5 - 8.0` | Total slurry volumetric displacement based on specific gravity ($\sim 1.00 - 1.03 \text{ kg/L}$). |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.manure_methane_production_potential (m^3/kg)` | `m^3/kg` | `0.20 - 0.28` | Ultimate biochemical methane potential coefficient ($B_0$) per kg VS. |
| `Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.total_cleaning_water_volume (m^3)` | `m^3` | `0.0 - 2.5` | Wash water or parlor flush water added during handler cleaning cycles. |
| `Manure.ParlorCleaningHandler.ParlorCleaningHandler.parlor_cleaning_handler.total_cleaning_water_volume (m^3)` | `m^3` | `1.0 - 15.0` | Milking parlor sanitation and holding pen flush volume routed into manure stream. |

---

### 2. Solid-Liquid Separation (`Manure.Separator.ScrewPress`)

Mechanical separation splits raw slurry into a stackable fiber cake (`SeparatedSolids`) and an easily pumpable liquid stream (`SeparatedLiquid`). RuFaS outputs 28 variables per separator instance (`screw_press_1`):

| Stream & Variable Signature | Units | Typical Value | Separation Mechanics & Nutrient Partitioning |
|---|---|---|---|
| `...screw_press_1.SeparatedSolids_manure_mass (kg)` | `kg` | `60 - 120` | Daily wet mass of separated solid fiber cake ($12 - 18\%$ of influent mass). |
| `...screw_press_1.SeparatedSolids_manure_total_solids (kg)` | `kg` | `20 - 40` | Total dry matter captured in solid cake ($25 - 35\%$ DM capture efficiency). |
| `...screw_press_1.SeparatedSolids_manure_water (kg)` | `kg` | `40 - 80` | Moisture retained in solid cake ($68 - 74\%$ moisture content). |
| `...screw_press_1.SeparatedSolids_manure_total_volatile_solids (kg)` | `kg` | `18 - 36` | Lignocellulosic volatile solids partitioned into compost/solid storage. |
| `...screw_press_1.SeparatedSolids_manure_nitrogen (kg)` | `kg` | `0.8 - 2.0` | Organic-bound nitrogen retained in fibrous cake. |
| `...screw_press_1.SeparatedSolids_manure_ammoniacal_nitrogen (kg)` | `kg` | `0.1 - 0.5` | Residual entrained soluble TAN ($\le 10 - 15\%$ of total TAN). |
| `...screw_press_1.SeparatedSolids_manure_phosphorus (kg)` | `kg` | `0.3 - 0.9` | Particulate phosphorus captured in solid fraction ($35 - 55\%$ of influent TP). |
| `...screw_press_1.SeparatedSolids_manure_potassium (kg)` | `kg` | `0.2 - 0.8` | Highly soluble potassium entrained in cake moisture ($<10\%$ of TK). |
| `...screw_press_1.SeparatedSolids_manure_volume (m^3)` | `m^3` | `0.08 - 0.16` | Bulk volume of solid cake routed to composting pad. |
| `...screw_press_1.SeparatedLiquid_manure_mass (kg)` | `kg` | `300 - 650` | Daily mass of liquid effluent routed to outdoor slurry storage ($82 - 88\%$ of influent). |
| `...screw_press_1.SeparatedLiquid_manure_total_solids (kg)` | `kg` | `30 - 75` | Residual fine suspended solids in liquid stream ($4 - 7\%$ DM). |
| `...screw_press_1.SeparatedLiquid_manure_water (kg)` | `kg` | `280 - 580` | Free water carrier for liquid lagoon storage and pump transfer. |
| `...screw_press_1.SeparatedLiquid_manure_nitrogen (kg)` | `kg` | `2.5 - 6.5` | Soluble and fine-colloidal nitrogen in liquid effluent. |
| `...screw_press_1.SeparatedLiquid_manure_ammoniacal_nitrogen (kg)` | `kg` | `1.5 - 4.5` | Plant-available ammoniacal nitrogen ($\ge 85 - 90\%$ of influent TAN). |
| `...screw_press_1.SeparatedLiquid_manure_phosphorus (kg)` | `kg` | `0.4 - 1.2` | Soluble orthophosphate and fine particulate P remaining in liquid. |
| `...screw_press_1.SeparatedLiquid_manure_potassium (kg)` | `kg` | `1.5 - 4.0` | Dissolved potassium cation ($\ge 90\%$ partition into liquid fraction). |
| `...screw_press_1.SeparatedLiquid_manure_volume (m^3)` | `m^3` | `0.30 - 0.65` | Liquid slurry volume entering storage basin or digester. |

---

### 3. Outdoor Slurry Storage Lagoons & Earthen Basins (`Manure.Storage.SlurryStorageOutdoor`)

RuFaS tracks complete daily dynamic mass balances and air emissions across outdoor liquid storage units (`slurry_storage_outdoor_lac`, `slurry_storage_outdoor_growing` — 47 variables each, 94 total):

#### A. Mass Balance State Triplet (Accumulated, Received, Emptied)
For every nutrient and physical parameter ($X = \text{mass, volume, water, TS, TVS, DVS, NDVS, Bedding VS, Ash, TN, TAN, TP, TK, } B_0$):
$$\text{Accumulated}_X(t) = \text{Accumulated}_X(t-1) + \text{Received}_X(t) - \text{Emptied}_X(t) - \text{Losses}_X(t)$$

| Simulation Variable (Sample Lactating Basin) | Units | Typical Range | Description & Biophysical Pool |
|---|---|---|---|
| `...slurry_storage_outdoor_lac.accumulated_manure_volume (m^3)` | `m^3` | `10.0 - 1,200.0+` | Current inventory volume of stored liquid manure; tracks headroom against storage capacity. |
| `...slurry_storage_outdoor_lac.accumulated_manure_mass (kg)` | `kg` | `10,000 - 1,200,000+` | Total wet mass stored in the basin. |
| `...slurry_storage_outdoor_lac.accumulated_manure_total_solids (kg)` | `kg` | `800 - 110,000` | Stored dry matter contributing to organic matter degradation. |
| `...slurry_storage_outdoor_lac.accumulated_manure_nitrogen (kg)` | `kg` | `40 - 5,500` | Stored total nitrogen inventory available for land application. |
| `...slurry_storage_outdoor_lac.accumulated_manure_ammoniacal_nitrogen (kg)` | `kg` | `20 - 3,200` | Readily available ammoniacal nitrogen in storage solution. |
| `...slurry_storage_outdoor_lac.accumulated_manure_phosphorus (kg)` | `kg` | `5 - 750` | Total stored elemental phosphorus inventory. |
| `...slurry_storage_outdoor_lac.accumulated_manure_potassium (kg)` | `kg` | `25 - 3,600` | Total stored elemental potassium inventory. |
| `...slurry_storage_outdoor_lac.received_manure_volume (m^3)` | `m^3` | `4.0 - 10.0` | Daily incoming liquid slurry volume from separators/handlers. |
| `...slurry_storage_outdoor_lac.emptied_manure_volume (m^3)` | `m^3` | `0.0 - 350.0` | Outflow volume pumped for field tanker application during scheduled spreading events. |

#### B. Storage Thermal Dynamics & Gaseous Emissions
| Simulation Output Variable | Units | Typical Range | Emission Mechanism & Environmental Drivers |
|---|---|---|---|
| `...slurry_storage_outdoor_lac.outdoor_storage_manure_temperature (°C)` | `°C` | `-2.0 - 28.0` | Dynamic slurry temperature driven by ambient weather, solar radiation, and storage depth. |
| `...slurry_storage_outdoor_lac.storage_methane (kg)` | `kg` | `0.2 - 25.0+` | Daily anaerobic $\text{CH}_4$ generation scaled by stored TVS, $B_0$, and temperature-dependent MCF. |
| `...slurry_storage_outdoor_lac.storage_methane_burned (kg)` | `kg` | `0.0 - 25.0` | Methane captured under impermeable covers and oxidized via flare or biogas generator. |
| `...slurry_storage_outdoor_lac.storage_ammonia_N (kg)` | `kg` | `1.0 - 18.0` | Ammonia volatilization ($\text{NH}_3\text{-N}$) from open liquid surface driven by pH, temp, and wind. |
| `...slurry_storage_outdoor_lac.storage_nitrous_oxide_N (kg)` | `kg` | `0.0 - 0.05` | Direct $\text{N}_2\text{O}$ emissions generated from aerobic surface crust nitrification-denitrification. |

---

### 4. Solid Manure Composting & Dry Storage (`Manure.Storage.Composting`)

Solid manure and separated cake piles undergo aerobic decomposition, carbon oxidation, and moisture loss (47 variables tracked for `compost`):

| Simulation Output Variable | Units | Typical Range | Biophysical Composting Mechanics |
|---|---|---|---|
| `Manure.Storage.Composting.compost.carbon_decomposition (kg)` | `kg` | `0.10 - 2.50` | Daily carbon mass oxidized to $\text{CO}_2$ by aerobic heterotrophic composting bacteria. |
| `Manure.Storage.Composting.compost.storage_ammonia_N (kg)` | `kg` | `0.20 - 2.00` | Ammonia volatilization loss during pile thermophilic composting phase. |
| `Manure.Storage.Composting.compost.storage_methane (kg)` | `kg` | `0.005 - 0.05` | Minor anaerobic pocket methane emissions within dense, un-aerated compost zones. |
| `Manure.Storage.Composting.compost.storage_nitrous_oxide_N (kg)` | `kg` | `0.002 - 0.02` | Nitrous oxide generated during aerobic/anaerobic interface nitrogen transformations. |
| `Manure.Storage.Composting.compost.storage_N_loss_from_leaching (kg)` | `kg` | `0.0 - 0.50` | Nitrate and ammonium lost via drainage percolate through unlined composting pads. |
| `Manure.Storage.Composting.compost.accumulated_manure_mass (kg)` | `kg` | `200 - 25,000` | Net standing mass of composting pile after moisture evaporation and carbon loss. |
| `Manure.Storage.Composting.compost.accumulated_manure_total_solids (kg)` | `kg` | `50 - 8,000` | Stabilized organic compost dry matter available for land application. |
| `Manure.Storage.Composting.compost.emptied_manure_mass (kg)` | `kg` | `0 - 15,000` | Solid compost mass loaded into spreaders during scheduled field application events. |

---

### 5. Field Nutrient Delivery Interface (`ManureEventNutrientRequestResults`)

When `FieldManager` triggers a scheduled manure application, `ManureManager.request_nutrients()` draws the requested volume from the designated storage basin and returns a structured `ManureEventNutrientRequestResults` object containing:

```python
@dataclass
class ManureEventNutrientRequestResults:
    organic_nitrogen: float        # kg Org-N delivered (slow mineralization in soil)
    ammoniacal_nitrogen: float     # kg TAN delivered (immediately plant-available / volatilizable)
    organic_phosphorus: float      # kg Org-P delivered to labile soil pool
    inorganic_phosphorus: float    # kg Orthophosphate-P delivered
    potassium: float               # kg Soluble K delivered to soil cation pool
    volatile_solids: float         # kg VS added to soil active carbon pool
    manure_mass: float             # Total wet weight of slurry / solid cake applied (kg)
    manure_volume: float           # Total volume extracted from storage (m^3)
```

The extracted mass and volume are immediately deducted from `accumulated_manure_*` in the storage unit, guaranteeing whole-farm nutrient conservation.

---

## Diagnostic Validation Rules & Operational Thresholds

When evaluating RuFaS manure management simulations, inspect the following physical and environmental criteria:

1. **Ammonia Volatilization Partitioning Across Subsystems**:
   - **Housing Floors**: $10 - 25\%$ of daily excreted TAN volatilizes before collection depending on scrape frequency and barn temperature ($T_{\text{barn}} > 20^\circ\text{C}$ accelerates emissions).
   - **Liquid Storage**: Open uncovered lagoons lose $10 - 30\%$ of stored TAN annually. Natural surface crusts or synthetic covers reduce $\text{NH}_3$ emissions by $60 - 90\%$.
   - **Compost Piles**: High initial ammonium or low C:N ($<20:1$) triggers elevated $\text{NH}_3$ losses ($15 - 35\%$ of initial TN).
   - **Field Application**: Surface broadcast without incorporation loses $20 - 50\%$ of applied TAN within 48 hours; shallow or deep injection reduces volatilization to $<5\%$.

2. **Lagoon Storage Volume Safety Margins**:
   - Monitored continuously via `Manure.Storage.SlurryStorageOutdoor.<id>.accumulated_manure_volume (m^3)`.
   - **Capacity Margin**: Maximum accumulated volume should never exceed $80 - 85\%$ of physical lagoon capacity, maintaining a minimum $0.5 - 1.0\text{ m}$ freeboard safety buffer against 25-year/24-hour storm precipitation.
   - **Overflow Anomaly**: If accumulated volume approaches $100\%$, add emergency pump-out application events in `input/data/manure_schedule/*.json` or expand design capacity in `manure_management_constants.json`.

3. **Solid-Liquid Separation Benchmarks**:
   - **Mass Partition**: Wet solid cake should represent $10 - 18\%$ of raw slurry mass; liquid effluent represents $82 - 90\%$.
   - **Dry Matter (DM) Capture**: Mechanical screw press must achieve $20 - 35\%$ DM separation efficiency into solid cake.
   - **Nutrient Split**: $\ge 85\%$ of TAN and $\ge 90\%$ of K must partition to the liquid effluent; $40 - 55\%$ of TP partitions to the solid cake.

4. **Composting Carbon Degradation Kinetics**:
   - Daily `carbon_decomposition (kg)` should range between $0.2 - 0.8\%$ of active volatile solids per day during active thermophilic heating ($50 - 65^\circ\text{C}$).
   - **C:N Ratio Balance**: Target initial compost C:N ratio is $25:1 - 30:1$. If $\text{C:N} < 20:1$, severe ammonia odor and N volatilization occur. If $\text{C:N} > 40:1$, microbial degradation stalls.

5. **Storage Methane Conversion Factor (MCF) Temperature Scaling**:
   - Methanogenesis follows Arrhenius temperature kinetics: in winter ($T_{\text{storage}} < 8^\circ\text{C}$), `storage_methane` drops to $<0.5\text{ kg/day}$; in peak summer ($T_{\text{storage}} > 22^\circ\text{C}$), daily emissions surge to $10 - 30+\text{ kg/day}$.
   - If biogas capture is configured, verify that `storage_methane_burned (kg)` tracks total generated methane and reduces atmospheric Scope 1 emissions in `rufas-eee-specialist`.

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

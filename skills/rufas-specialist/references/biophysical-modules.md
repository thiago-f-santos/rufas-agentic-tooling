# RuFaS Biophysical Subsystems Deep Dive

## 1. Animal / Herd Module (`RUFAS/biophysical/animal/`)

### Architecture
Managed by `HerdManager`. The herd is partitioned into cohorts and pens:
- **Lactating Cows**: High, medium, low production pens; fresh cow pens.
- **Dry Cows**: Far-off dry, close-up transition.
- **Replacement Heifers**: Pre-weaned calves, weaned heifers, breeding-age heifers, pregnant heifers.
- **Bulls / Steers**: (Optional cohorts).

### Key Physiological Mechanics
1. **Lactation Curve Modeling**: Wood's incomplete gamma curve or Dijkstra lactation models parameterized by parity (primiparous vs multiparous), days in milk (DIM), and genetic merit.
2. **Nutrition & Ration Formulation**:
   - Least-cost diet formulation via Linear Programming (LP).
   - Compliant with **NRC (2001)** and **NASEM (2021)** Dairy Cattle Nutrient Requirements.
   - Evaluates: Dry Matter Intake (DMI), Net Energy for Lactation ($NE_L$), Metabolizable Protein (MP), Rumen Degradable Protein (RDP), Rumen Undegradable Protein (RUP), neutral detergent fiber (NDF), forage NDF (fNDF), macro-minerals (Ca, P, Mg, K, Na, Cl, S).
3. **Enteric Methane ($\text{CH}_4$)**:
   - Empirically calculated based on DMI, dietary fat (EE), digestible NDF, and dietary starch using NASEM 2021 enteric equations.
4. **Excretion Calculation**:
   - `ManureExcretionCalculator` computes urinary vs fecal partition of N, P, K, volatile solids (VS), and water based on diet digestibility and animal retention.

---

## 2. Field & Soil Module (`RUFAS/biophysical/field/`)

### Architecture
Managed by `FieldManager`. Operates on individual fields with associated soil profiles, crop rotations, and operational management schedules.

### Key Components
1. **Soil Hydrology & Temperature**:
   - Multi-layer vertical soil profile (discrete depth layers).
   - Infiltration (Green-Ampt or SCS Curve Number), matrix percolation, capillary rise, evapotranspiration (Penman-Monteith).
   - Soil temperature profile driven by solar radiation, air temperature, and crop canopy cover.
2. **Soil Biogeochemistry (N, P, C Cycles)**:
   - Organic matter pools (microbial biomass, active, slow, passive humus).
   - Mineralization, immobilization, nitrification, denitrification, ammonia volatilization, and nitrate leaching.
   - Phosphorus cycling: solution P, active inorganic P, stable inorganic P, organic P.
3. **Crop Growth Engine**:
   - Species supported: Corn silage, corn grain, alfalfa, winter rye, cool-season grass, soybean.
   - Thermal time (Growing Degree Days - GDD) determines phenological development stages (emergence, vegetative, flowering, grain fill, maturity).
   - Daily biomass accumulation driven by radiation use efficiency (RUE), water stress index, nitrogen stress index, and temperature limitation.
   - Root expansion and nutrient uptake from layered soil water pools.
4. **Field Operations**:
   - Tillage operations (moldboard plow, chisel, disk, no-till) modifying soil bulk density, surface roughness, and residue cover.
   - Commercial fertilizer applications (inorganic N and P scheduling).
   - Manure injection, broadcast, and incorporation.
   - Harvest events yielding `HarvestedCrop` objects with biomass and nutrient contents.

---

## 3. Feed Storage Module (`RUFAS/biophysical/feed_storage/`)

### Architecture
Managed by `FeedManager`. Tracks feed inventory, storage facilities, degradation processes, and feed allocations.

### Key Storage Structures
- **Bunkers / Trench Silos**: High-moisture corn, corn silage, haylage.
- **Tower Silos**: Concrete / oxygen-limiting silos.
- **Silage Bags (Ag Bags)**.
- **Dry Hay Sheds / Commodity Barns**: Alfalfa hay, grain concentrates, protein meals, mineral mixes.

### Degradation & Mass Balance
- Simulates aerobic spoilage upon exposure to oxygen during feed-out phase.
- Dry matter loss percentages based on storage type, pack density, moisture content, and ambient temperature.
- In-storage fermentation and nutrient concentration changes.

---

## 4. Manure Module (`RUFAS/biophysical/manure/`)

### Architecture
Managed by `ManureManager`. Tracks manure processing from collection through treatment, storage, and land application.

### Processing Train
1. **Housing Collection**:
   - Free-stall scraping (flush, vacuum, mechanical scraper).
   - Tie-stall gutters.
   - Bedding mass addition and moisture absorption.
2. **Solid-Liquid Separation**:
   - Screw press, weeping wall, screen separator.
   - Partitions stream into solid fraction (fiber) and liquid fraction (slurry/effluent).
3. **Storage Systems**:
   - Liquid manure storage: concrete pits, earthen storage ponds, above-ground slurry stores.
   - Solid manure storage: stacked bedded pack, compost windrows.
4. **Advanced Treatment**:
   - Anaerobic digestion (mesophilic/thermophilic CSTR, plug-flow) generating biogas, reducing volatile solids, and converting organic N to ammonium N.
5. **Gaseous Emissions**:
   - Methane ($\text{CH}_4$) from anaerobic degradation of volatile solids based on temperature-dependent Van 't Hoff / Arrhenius kinetics and Methane Conversion Factors (MCF).
   - Ammonia ($\text{NH}_3$) volatilization based on pH, temperature, exposed surface area, and crust cover.
   - Nitrous oxide ($\text{N}_2\text{O}$) from crust nitrification/denitrification.

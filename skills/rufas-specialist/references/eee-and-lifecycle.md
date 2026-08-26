# RuFaS Economics, Energy, and Emissions (EEE) Reference

## 1. Overview
The EEE subsystem (`RUFAS/EEE/`) evaluates the farm-level economic balance, energy consumption (fuel, electricity), and total greenhouse gas (GHG) footprint.

---

## 2. Emissions Subsystem (`RUFAS/EEE/emissions.py`)

### Greenhouse Gas Scope & Accounting
Emissions are tracked across biophysical and upstream categories, converted to $\text{CO}_2$-equivalent ($\text{CO}_2\text{e}$) using IPCC AR5/AR6 Global Warming Potential (GWP100) metrics (e.g. $\text{CH}_4 = 28$, $\text{N}_2\text{O} = 265$):

1. **Enteric Fermentation ($\text{CH}_4$)**:
   - Calculated daily in `HerdManager` across all animal cohorts.
2. **Manure Management ($\text{CH}_4$, $\text{N}_2\text{O}$, $\text{NH}_3$)**:
   - Housing emissions (barn floor).
   - Storage emissions (slurry pits, lagoons, compost packs).
   - Solid-liquid separation and anaerobic digestion credits.
3. **Field & Soil Emissions**:
   - Direct $\text{N}_2\text{O}$ from synthetic fertilizer and manure application (IPCC Tier 1 / Tier 2 emission factors or process-based soil nitrification-denitrification).
   - Indirect $\text{N}_2\text{O}$ from ammonia volatilization ($\text{NH}_3$) and nitrate leaching ($\text{NO}_3^-$).
4. **Machinery & Fossil Fuel Combustion ($\text{CO}_2$)**:
   - Diesel fuel consumption from field operations (tillage, planting, spraying, harvesting, hauling).
   - Manure pumping, agitation, and tanker transport.
5. **Upstream / Purchased Inputs**:
   - Purchased feeds embodied emissions (production, processing, transport).
   - Land Use Change (LUC) emissions for purchased concentrates (e.g., soybean meal).
   - Purchased inorganic fertilizer embodied emissions.

---

## 3. Energy Subsystem (`RUFAS/EEE/energy.py`, `tractor.py`, `tractor_implement.py`)

### 1. Tractor & Field Machinery
- Models tractor-implement pairings (power rating, draft requirements, operating speed, field efficiency).
- Fuel consumption calculated using ASABE D497 standards based on Equivalent PTO Power and load ratio.
- Implements include:
  - Tillage (chisel plow, moldboard, disk harrow, field cultivator).
  - Planting (planters, grain drills).
  - Chemical/Fertilizer application (sprayers, spreaders, liquid manure injectors).
  - Forage harvesting (mower-conditioner, rotary rake, forage chopper, baler, combine).

### 2. Stationary Energy Consumption
- Electricity for milking parlor operations (vacuum pumps, milk cooling refrigeration, water heaters, automated washing).
- Barn ventilation fans, circulation fans, lighting, and manure scrape systems.
- Feed mixing wagons (TMR mixers) and grain augers.

---

## 4. Economics Subsystem (`RUFAS/EEE/economy.py`)

- **Revenues**:
  - Milk sales based on milk volume, fat percentage, protein percentage, and somatic cell count (SCC) premiums/penalties.
  - Cull cow sales, bull calf sales, surplus heifer sales.
  - Crop sales (if farm exports surplus forages/grains).
- **Variable Operating Costs**:
  - Purchased feed costs (concentrates, minerals, supplemental forages).
  - Crop inputs: seed, fertilizer, pesticides, fuel, custom hire machinery.
  - Veterinary, breeding/AI, bedding, and supplies.
  - Energy & utility bills (diesel, electricity, natural gas/propane).
- **Fixed Costs**:
  - Depreciation on barns, milking parlors, tractors, and field equipment.
  - Labor, land rent, insurance, and taxes.
- **Financial Metrics**:
  - Net Farm Income, Income Over Feed Cost (IOFC) per cwt milk, Cost of Production per cwt milk.

# RuFaS Simulation Flow & Orchestration Reference

## 1. Overview
`SimulationEngine` (`RUFAS/simulation_engine.py`) orchestrates the lifecycle of the simulation, advancing the simulated date step-by-step and coordinating communication between the specialized subsystem managers.

---

## 2. Simulation Types (`SimulationType`)
RuFaS supports 4 simulation modes defined in `SimulationType`:
1. `FULL_FARM`: All sub-modules active (field, feed storage, herd/animal, manure, EEE).
2. `FIELD_AND_FEED`: Simulates crop, soil, and feed storage without animals or manure.
3. `FIELD_ONLY`: Simulates soil-crop dynamics and field operations in isolation.
4. `ANIMALS_ONLY`: Simulates herd dynamics, intake, and lactation with exogenous feed supply.

---

## 3. Detailed Daily Execution Sequence (`FULL_FARM`)

Each simulation day executes in exact sequential order:

### Step 1: Daily Field Operations (`_execute_daily_field_operations`)
- **Manure Scheduling**: `FieldManager.check_manure_schedules` identifies fields with scheduled manure application events.
- **Nutrient Requests**: Requests nutrients from `ManureManager.request_nutrients` (or `FieldManureSupplier`), returning `list[ManureEventNutrientRequestResults]`.
- **Soil & Crop Daily Update**: `FieldManager.daily_update_routine(weather, time, manure_applications)` simulates soil water balance across layers, daily temperature profiles, nitrogen/phosphorus/carbon transformations, crop vegetative growth, root expansion, and potential harvest events.
- **Output**: Returns `harvested_crops: list[HarvestedCrop]`.

### Step 2: Storage Reception (`_receive_daily_harvested_crops`)
- For each `HarvestedCrop`, invokes `FeedManager.receive_crop(crop, simulation_day)` which assigns the harvested biomass, dry matter (DM), and nutrients into designated storage instances (bunkers, silos, ag bags, dry hay sheds).

### Step 3: Harvest Schedule Update (`_build_harvest_schedule`)
- Calls `FieldManager.get_next_harvest_dates` to identify anticipated upcoming harvest dates for all active crops to inform inventory horizons.

### Step 4: Feed Planning (`_execute_feed_planning`)
- Invoked on scheduled intervals or when new harvests arrive.
- `FeedManager.get_total_projected_inventory` projects available feed stock across the planning horizon.
- `HerdManager.update_all_max_daily_feeds` computes daily intake constraints (`max_daily_feeds`) for each available feed type, outputting `IdealFeeds`.
- `FeedManager.manage_planning_cycle_purchases` commits forward feed purchases.
- `FeedManager.process_degradations` models dry matter losses, fermentation quality, and spoilage.

### Step 5: Ration Planning (`_execute_ration_planning`)
- Checked against `ration_formulation_interval` or triggered by feed stock emergencies.
- `HerdManager.formulate_rations` executes linear programming (LP) to solve least-cost diets satisfying NASEM/NRC nutrient requirements for each cow group/pen, returning `RequestedFeed`.
- `FeedManager.manage_ration_interval_purchases` executes buffer purchases.

### Step 6: Animal Operations (`_execute_daily_animal_operations`)
- `HerdManager.execute_daily_routines`:
  - Feeding: Cows consume formulated ration from available storage (`FeedManager.manage_daily_feed_request`).
  - Metabolism: Digestion, nutrient absorption, growth, milk yield production (Wood's lactation curves).
  - Enteric Emissions: Models enteric methane ($\text{CH}_4$) using NASEM/IPCC equations.
  - Excretion: Calculates fecal and urinary dry matter, N, P, K, and moisture output per pen.
- **Output**: `all_manure_data: dict[str, ManureStream]` and `daily_purchased_feeds_fed`.

### Step 7: Manure Operations (`_execute_daily_manure_operations`)
- `ManureManager.run_daily_update(daily_manure_data, time, weather)`:
  - Routes pen manure streams from barn housing (free-stall, tie-stall, dry-lot) to collection gutters.
  - Simulates solid-liquid separation (screen, centrifuge, screw press).
  - Processes manure in storage facilities (earthen basins, concrete tanks, anaerobic digesters).
  - Computes daily emissions: ammonia ($\text{NH}_3$), methane ($\text{CH}_4$), nitrous oxide ($\text{N}_2\text{O}$).

### Step 8: Daily Record Keeping & EEE
- `EmissionsEstimator.calculate_purchased_feed_emissions` logs upstream emissions from purchased feeds.
- Time and weather states logged in `OutputManager`.

### Step 9: Time Advancement (`_advance_time`)
- Advances `RufasTime` to next calendar day.

---

## 4. Post-Simulation Operations (`_post_simulation_processing`)
Once the simulation time loop concludes:
- `EEEManager.estimate_all`:
  - `EnergyEstimator`: Calculates tractor fuel consumption, electricity use for milking/cooling/ventilation/pumping.
  - `EmissionsEstimator.estimate_farmgrown_feed_emissions`: Synthesizes total farm greenhouse gas footprint ($\text{CO}_2\text{e}$ via GWP100 factors).
- `OutputManager.save_results`: Routes pools through active filter files.

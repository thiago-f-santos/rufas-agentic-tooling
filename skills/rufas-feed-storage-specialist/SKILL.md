---
name: rufas-feed-storage-specialist
description: Use when analyzing, configuring, or debugging the RuFaS Feed Storage and Inventory Management module, including silo/bunker storage capacities, fermentation degradation, aerobic spoilage, feed inventory projection, purchase planning cycles, or daily feed fulfillment.
---

# RuFaS Feed Storage & Inventory Specialist Skill

## Overview

The **RuFaS Feed Storage Module** (`RUFAS/biophysical/feed_storage/`) manages on-farm feed inventory, storage facilities (bunkers, tower silos, silage bags, dry commodity sheds), storage degradation and spoilage kinetics, long-term inventory forecasting, forward feed purchasing, and daily feed allocation to the herd.

Managed by `FeedManager`, it sits directly between crop production (`FieldManager`) and herd consumption (`HerdManager`).

---

## When to Use

### Triggering Conditions & Symptoms
- Configuring feed storage structures: bunker silos, concrete tower silos, ag bags, dry hay barns, and purchased commodity bins.
- Setting up initial storage inventory levels, target moisture percentages, packing densities, and maximum capacities.
- Investigating feed inventory shortages, unexpected buffer purchases, or storage overflow errors.
- Modeling dry matter (DM) losses, aerobic face spoilage, respiration losses, and nutrient degradation over storage duration.
- Tuning planning cycle purchase horizons or debugging feed constraint limits (`max_daily_feeds`) sent to herd ration formulation.
- Tracing feed delivery fulfillment (`manage_daily_feed_request`) and emergency diet reformulation triggers.

### When NOT to Use
- Solving linear programming herd rations or NASEM nutrient requirements (use `rufas-animal-specialist`).
- Soil hydrology and crop growth modeling (use `rufas-field-soil-specialist`).
- Farm-level economic balance sheet and enterprise accounting (use `rufas-eee-specialist`).

---

## Inputs & Metadata Schemas

The Feed Storage module is parameterized by 4 primary metadata blobs:

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `feed` | `input/data/feed_management/feed_management_constants.json` | Planning cycle interval length, forward projection days, safety buffer margins, degradation calculation intervals. |
| `feed_storage_configurations` | `input/data/feed_management/feed_storage_configurations.json` | Storage unit definitions (type: bunker, tower, bag, shed), physical volume ($m^3$), packing density ($\text{kg DM}/m^3$), face removal rate ($\text{m/day}$). |
| `feed_storage_instances` | `input/data/feed_management/feed_storage_instances.json` | Initial feed assignment to storage units, initial stored DM ($\text{kg}$), initial moisture %, initial RUFAS_ID mappings. |
| `user_feeds` | `input/data/feed/user_feeds.json` | Custom feed names, baseline nutrient profiles (DM, CP, NDF, starch, EE, ash, $NE_L$), market purchase unit costs ($\$/\text{tonne}$). |

---

## Core Biophysical Mechanics & Formulas

### 1. Storage Structure Types & Classification
- **Bunkers / Trench Silos (`Silage`)**: High-capacity horizontal structures for corn silage and haylage. Susceptible to face spoilage and packing density variations.
- **Tower Silos (`Silage`)**: Vertical cylinders with top-unloading or bottom-unloading; lower surface area exposed to oxygen.
- **Silage Bags / Ag Bags (`Baleage` / `Silage`)**: Flexible sealed polyethylene tubes.
- **Dry Hay Sheds & Commodity Barns (`Hay` / `Grain` / `PurchasedFeedStorage`)**: Covered structures for dry forages ($<15\%$ moisture), grains, protein meals, and mineral mixes.

### 2. Feed Receiving & Inventory Updating (`receive_crop`)
When `FieldManager` delivers a `HarvestedCrop`:
1. `FeedManager` matches the crop configuration to the designated storage instance (`RUFAS_ID`).
2. Validates available physical storage volume. If capacity is exceeded, surplus is lost or triggers overflow warnings.
3. Blends incoming biomass, moisture, and nutrient composition into the existing storage pool using weighted mass averaging:
   $$\text{DM}_{\text{new}} = \text{DM}_{\text{current}} + \text{DM}_{\text{harvest}}$$
   $$\text{Nutrient}_{\text{blend}} = \frac{\text{DM}_{\text{current}} \cdot \text{Nutrient}_{\text{current}} + \text{DM}_{\text{harvest}} \cdot \text{Nutrient}_{\text{harvest}}}{\text{DM}_{\text{new}}}$$

### 3. In-Storage Degradation & Spoilage (`process_degradations`)
- **Primary Fermentation Losses (`fermentation_loss_DM`)**: Microbially driven volatile fatty acid (VFA) and gas production (`gaseous_dry_matter_loss`) during anaerobic ensiling (typically 2–8% DM loss).
- **Aerobic Deterioration / Face Spoilage (`aerobic_face_loss_DM`)**: Occurs at exposed bunker/silo faces when feed-out rate is slower than oxygen penetration depth:
  $$\text{Loss}_{\text{aerobic}} = f(\text{FaceRemovalRate}, \text{PackingDensity}, \text{AmbientTemperature})$$
- **Total Shrinkage (`total_shrinkage`)**: Cumulative loss tracked and subtracted from available inventory:
  $$\text{Total Shrinkage} = \text{Loss}_{\text{fermentation}} + \text{Loss}_{\text{aerobic}} + \text{Loss}_{\text{effluent}} + \text{Loss}_{\text{handling}}$$

### 4. Feed Planning & Inventory Projection (`get_total_projected_inventory`)
- Projects existing feed inventory forward until the anticipated next harvest date (`get_next_harvest_dates`).
- Computes maximum allowable daily feeding rate:
  $$\text{MaxDailyFeed}_k = \frac{\text{ProjectedInventory}_k}{\text{DaysUntilNextHarvest}_k} \cdot (1 - \text{BufferSafetyMargin})$$
- Transmits `max_daily_feeds` bounds to `HerdManager.update_all_max_daily_feeds`, returning `IdealFeeds` and `TotalInventory`.

### 5. Daily Feed Fulfillment (`manage_daily_feed_request`)
1. On each simulation day, `HerdManager` submits `RequestedFeed` (the daily diet demand).
2. `FeedManager` checks available inventory across all active storage units.
3. If feed is available: Withdraws requested mass, updates storage balances, and returns `FeedFulfillmentResults(is_ok_to_feed=True)`.
4. If feed is deficient: Executes emergency spot purchases or triggers an unscheduled emergency ration reformulation in `HerdManager`.

---

## Simulation Output Variable Dictionary & Diagnostics

The RuFaS Feed Storage module generates **134 time-series variables** categorized across purchasing procurement, storage inventories, biophysical degradation, and daily herd fulfillment.

### 1. Feed Purchasing Time-Series & Procurement Economics

Feed purchases are orchestrated by `FeedManager.purchase_feed` across three distinct scheduling horizons:
1. **`ration_interval`**: Bulk procurement at the start of each dietary formulation cycle (e.g. every 30 or 60 days) to fulfill animal requirements with buffer.
2. **`daily_feed_request`**: Real-time spot purchases triggered when daily storage inventory is depleted and runtime allowance permits.
3. **`planning_cycle`**: Long-term seasonal procurement horizons.

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Biophysical / Procurement Description |
|---|---|---|---|
| `FeedManager.purchase_feed.ration_interval_202_cost ($)` | `$` | `0.0 - 500.0` | Cost of whole milk (Feed 202) purchased at ration interval for pre-weaned calves. |
| `FeedManager.purchase_feed.ration_interval_202_amount_purchased (kg)` | `kg` | `0.0 - 1,000.0` | Dry matter mass of whole milk (Feed 202) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_216_cost ($)` | `$` | `0.0 - 800.0` | Cost of 18% CP calf starter (Feed 216) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_216_amount_purchased (kg)` | `kg` | `0.0 - 2,500.0` | Mass of calf starter (Feed 216) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_44_cost ($)` | `$` | `0.0 - 15,000.0` | Cost of yellow corn grain (Feed 44) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_44_amount_purchased (kg)` | `kg` | `0.0 - 60,000.0` | Dry matter mass of yellow corn grain (Feed 44) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_50_cost ($)` | `$` | `0.0 - 8,000.0` | Cost of purchased corn silage (Feed 50) when on-farm bunker inventory is insufficient. |
| `FeedManager.purchase_feed.ration_interval_50_amount_purchased (kg)` | `kg` | `0.0 - 120,000.0` | Mass of corn silage (Feed 50) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_95_cost ($)` | `$` | `0.0 - 4,000.0` | Cost of mature grass-legume hay (Feed 95) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_95_amount_purchased (kg)` | `kg` | `0.0 - 25,000.0` | Mass of grass-legume hay (Feed 95) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_104_cost ($)` | `$` | `0.0 - 5,000.0` | Cost of grass-legume silage (Feed 104) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_104_amount_purchased (kg)` | `kg` | `0.0 - 30,000.0` | Mass of grass-legume silage (Feed 104) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_110_cost ($)` | `$` | `0.0 - 12,000.0` | Cost of alfalfa/legume silage (Feed 110) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_110_amount_purchased (kg)` | `kg` | `0.0 - 80,000.0` | Mass of alfalfa/legume silage (Feed 110) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_301_cost ($)` | `$` | `0.0 - 2,500.0` | Cost of vitamin & mineral premix (Feed 301) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_301_amount_purchased (kg)` | `kg` | `0.0 - 6,000.0` | Mass of mineral mix (Feed 301) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_302_cost ($)` | `$` | `0.0 - 18,000.0` | Cost of Midwest by-product blend / protein meal (Feed 302) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_302_amount_purchased (kg)` | `kg` | `0.0 - 50,000.0` | Mass of by-product blend (Feed 302) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_23_cost ($)` | `$` | `0.0 - 3,000.0` | Cost of blood meal / bypass protein (Feed 23) purchased at ration interval. |
| `FeedManager.purchase_feed.ration_interval_23_amount_purchased (kg)` | `kg` | `0.0 - 5,000.0` | Mass of blood meal (Feed 23) purchased at ration interval. |
| `FeedManager.purchase_feed.daily_feed_request_<feed_id>_cost ($)` | `$` | `0.0 - 500.0` | Emergency daily spot purchase cost for feed `<feed_id>` when storage runs empty. |
| `FeedManager.purchase_feed.daily_feed_request_<feed_id>_amount_purchased (kg)` | `kg` | `0.0 - 1,000.0` | Emergency daily spot purchase mass for feed `<feed_id>`. |

### 2. Cumulative Feed Balances & Tracking

Logged daily by `FeedManager.report_feed_manager_balance` to track cumulative feed requests, purchases, and feeding:

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Description & Flow Tracking |
|---|---|---|---|
| `FeedManager.report_feed_manager_balance.feed_<feed_id>_requested_to_date (kg)` | `kg` | Cumulative ($\ge 0$) | Total cumulative dry matter of feed `<feed_id>` requested by `HerdManager` across simulation days. |
| `FeedManager.report_feed_manager_balance.purchased_feed_<feed_id>_fed_to_date (kg)` | `kg` | Cumulative ($\ge 0$) | Cumulative mass of commercial purchased feed `<feed_id>` fed to the herd. |
| `FeedManager.report_feed_manager_balance.farmgrown_feed_<feed_id>_fed_to_date (kg)` | `kg` | Cumulative ($\ge 0$) | Cumulative mass of on-farm produced crop `<feed_id>` drawn from storage and fed. |
| `FeedManager.report_feed_manager_balance.purchased_feed_<feed_id>_purchased_to_date (kg)` | `kg` | Cumulative ($\ge 0$) | Cumulative gross mass of commercial feed `<feed_id>` procured from off-farm sources. |

### 3. Storage Inventory Balances & Physical Capacity

Monitored by `PurchasedFeedStorage` and `FeedManager.report_stored_farmgrown_feeds`:

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Description & Biophysical Metric |
|---|---|---|---|
| `PurchasedFeedStorage.report_stored_purchased_feeds.stored_feed_<feed_id>.balance_storage_levels (kg)` | `kg` | `0.0 - 100,000.0` | Available dry matter inventory of purchased feed `<feed_id>` held in commodity storage. |
| `FeedManager.report_stored_farmgrown_feeds.stored_feed_<feed_id>_dm (dry kg)` | `dry kg` | `0.0 - 2,000,000.0` | Farm-grown dry matter inventory (`stored_feed_DM (kg)`) across active silos/bunkers. |
| `FeedManager.report_stored_farmgrown_feeds.stored_feed_<feed_id>_wet (kg)` | `kg` | `0.0 - 6,000,000.0` | Fresh mass inventory including forage moisture content (`moisture_content (fraction)`). |
| `Storage.available_capacity (m^3)` | `m^3` | `0.0 - 15,000.0` | Remaining unoccupied physical storage volume (`available_capacity (m^3)`). |
| `TotalInventory` | `Data Structure` | `Dict[RUFAS_ID, kg DM]` | Projected forward inventory passed to `HerdManager` for ration formulation bounds. |

### 4. In-Storage Spoilage, Degradation & Shrinkage Mechanics

Computed daily during `process_degradations` in `Storage`, `Silage`, `Hay`, and `Grain`:

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Spoilage / Degradation Description |
|---|---|---|---|
| `Storage.process_degradations.gaseous_dry_matter_loss (kg)` | `kg` | `0.0 - 250.0` | Daily volatile gaseous dry matter loss (`fermentation_loss_DM (kg)`) from anaerobic microbial fermentation. |
| `Silage.process_degradations.total_effluent_dry_matter_loss (kg)` | `kg` | `0.0 - 80.0` | Silage effluent leachate dry matter loss occurring over the first 10 days post-ensiling. |
| `Silage.process_degradations.total_effluent_moisture_loss (kg)` | `kg` | `0.0 - 700.0` | Moisture mass drained from silage stack during early compaction and ensiling. |
| `Storage.aerobic_face_loss_DM (kg/day)` | `kg/day` | `0.0 - 120.0` | Aerobic deterioration (`aerobic_face_loss_DM (kg/day)`) at bunker/pile face from oxygen exposure. |
| `Storage.total_shrinkage (kg)` | `kg` | `2.0 - 15.0%` | Aggregate dry matter shrinkage (`total_shrinkage (kg)`) combining fermentation, effluent, face spoilage, and handling. |

#### In-Storage Nutrient Concentration Adjustments
When dry matter is lost as $\text{CO}_2$ or fermentation gases, nutrient percentages concentrate according to component loss coefficients:
$$\text{Nutrient}_{\text{new}}\% = \frac{\text{DM}_{\text{old}} \cdot \text{Nutrient}_{\text{old}}\% \cdot (1 - \text{LossCoeff})}{\text{DM}_{\text{old}} - \text{DM}_{\text{gas\_lost}}}$$
Where loss coefficients default to `0.0` for non-volatile minerals (Ash, Lignin) and fractional rates for fermentable carbohydrates (Starch, Sugars).

### 5. Daily Ration Fulfillment & Allocation Tracking

Managed daily by `FeedManager.manage_daily_feed_request`:

| Simulation Output Variable (Full Column Signature) | Units | Typical Range | Daily Delivery & Fulfillment Description |
|---|---|---|---|
| `FeedManager.manage_daily_feed_request.<feed_id>_requested_amount (dry kg)` | `dry kg` | `5.0 - 15,000.0` | Daily dry matter requested by `HerdManager` for feed `<feed_id>`. |
| `FeedManager.manage_daily_feed_request.<feed_id>_available_amount (dry kg)` | `dry kg` | `0.0 - 500,000.0` | Current available dry matter inventory across all farm storages for feed `<feed_id>`. |
| `FeedManager._log_feed_deductions.purchased_feed_<feed_id>_fed.amount (dry kg)` | `dry kg` | `0.0 - 8,000.0` | Dry matter mass of commercial purchased feed `<feed_id>` deducted to fulfill daily herd diet. |
| `FeedManager._log_feed_deductions.farmgrown_feed_<feed_id>_fed.amount (dry kg)` | `dry kg` | `0.0 - 15,000.0` | Dry matter mass of farm-grown crop `<feed_id>` deducted from bunker/silo storage. |
| `FeedFulfillmentResults(is_ok_to_feed=True)` | `Status` | `True / False` | Delivery authorization flag; returns `False` if neither inventory nor purchase allowances can fulfill diet. |

---

## Diagnostic Validation Rules & Storage Performance Benchmarks

When analyzing simulation logs and output CSVs, evaluate these storage performance benchmarks:

1. **Silage Dry Matter Shrinkage Standards**:
   - **Bunker Silos (Corn Silage)**: Total DM shrinkage must fall between **8% and 15%** (fermentation: 2–5%, face spoilage: 3–8%, top surface spoilage: 1–3%).
   - **Bunker Silos (Alfalfa/Grass Haylage)**: Total DM shrinkage between **6% and 12%**.
   - **Tower Silos**: Total DM shrinkage between **5% and 10%** due to lower exposed face surface area.
   - **Silage Bags / Ag Bags**: Total DM shrinkage between **4% and 8%**.
   - **Dry Hay Sheds & Commodity Barns**: Total DM shrinkage between **2% and 5%** (respiration and handling losses).

2. **Feed Costs per Cow-Day**:
   - **Lactating Cows**: Normal dietary feed cost ranges between **$4.50 and $8.50 per cow-day** (or $8.00–$14.00/cwt milk).
   - **Dry Cows**: **$2.00 – $3.50 per cow-day**.
   - **Growing Heifers**: **$1.80 – $3.00 per heifer-day**.
   - Values exceeding `$10.00/cow-day` indicate excessive reliance on spot emergency purchases or poorly formulated concentrates.

3. **Face Removal Rate & Aerobic Spoilage Prevention**:
   - Bunker silo face removal rate should be $\ge 0.15\text{ m/day}$ (winter) and $\ge 0.30\text{ m/day}$ (summer) to prevent deep oxygen infiltration and secondary heating.
   - Insufficient face removal rate in `feed_storage_configurations.json` triggers elevated `aerobic_face_loss_DM` and rapid nutrient degradation.

4. **Storage Capacity & Overfill Protection**:
   - Total stored fresh mass must strictly satisfy $\sum \text{Mass}_{\text{stored}} \le \text{Storage Capacity} \ (m^3 \cdot \text{PackingDensity})$.
   - Overfills throw `Exceeds feed storage capacity error` or trigger unharvested crop losses in `FieldManager`.

5. **Safety Buffer Allowances**:
   - Standard forward purchase buffer margin (`buffer`) is **10% to 20%** (0.10–0.20) above net LP ration demand to account for bunk feed refusal (orts, 3–5%) and storage shrink.

---

## Outputs & Cross-Module Influence

| Output Variable / Data Structure | Receiving Module | Impact on Whole Farm |
|---|---|---|
| `TotalInventory` & `max_daily_feeds` | `HerdManager` | Constrains the linear programming diet formulation; determines whether home-grown forages suffice or purchased feeds are needed. |
| `AvailableFeeds` | `HerdManager` | Supplies the current chemical and nutrient profiles of all feedstuffs available for feeding. |
| `FeedFulfillmentResults` | `HerdManager` | Authorizes animal daily feeding routine; detects stockouts. |
| `cumulative_purchased_feeds` | `EEEManager` | Dictates annual feed purchase expenditure and upstream Scope 3 lifecycle GHG footprint. |

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"I can store more feed than the bunker volume defines."* | RuFaS validates physical volume against packing density. Overfills trigger inventory loss or validation errors. |
| *"Feed inventory can be drawn down to zero without buffer."* | Zero inventory triggers emergency spot market feed purchases at premium prices or LP diet infeasibility. |
| *"Harvested crops are instantly fed on the harvest date."* | Crops must first be received, integrated into projected inventory, and factored into the next scheduled ration formulation interval before being fed. |

### 🚩 Diagnostic Red Flags
- Infeasible ration formulation $\rightarrow$ Check if `max_daily_feeds` in feed storage are overly restrictive or inventory ran out.
- Excessive purchased feed expenses $\rightarrow$ Check storage degradation losses or crop harvest receiving alignment.
- Unrealistic bunker face spoilage $\rightarrow$ Check face removal rate and packing density parameters in `feed_storage_configurations.json`.


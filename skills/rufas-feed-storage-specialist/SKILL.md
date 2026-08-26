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
- **Primary Fermentation Losses**: Microbially driven volatile fatty acid (VFA) and gas production during anaerobic ensiling (typically 2–8% DM loss).
- **Aerobic Deterioration / Face Spoilage**: Occurs at exposed bunker/silo faces when feed-out rate is slower than oxygen penetration depth:
  $$\text{Loss}_{\text{aerobic}} = f(\text{FaceRemovalRate}, \text{PackingDensity}, \text{AmbientTemperature})$$
- **Total Shrinkage**: Cumulative loss tracked and subtracted from available inventory.

### 4. Feed Planning & Inventory Projection (`get_total_projected_inventory`)
- Projects existing feed inventory forward until the anticipated next harvest date (`get_next_harvest_dates`).
- Computes maximum allowable daily feeding rate:
  $$\text{MaxDailyFeed}_k = \frac{\text{ProjectedInventory}_k}{\text{DaysUntilNextHarvest}_k} \cdot (1 - \text{BufferSafetyMargin})$$
- Transmits `max_daily_feeds` bounds to `HerdManager.update_all_max_daily_feeds`, returning `IdealFeeds`.

### 5. Daily Feed Fulfillment (`manage_daily_feed_request`)
1. On each simulation day, `HerdManager` submits `RequestedFeed` (the daily diet demand).
2. `FeedManager` checks available inventory across all active storage units.
3. If feed is available: Withdraws requested mass, updates storage balances, and returns `FeedFulfillmentResults(is_ok_to_feed=True)`.
4. If feed is deficient: Executes emergency spot purchases or triggers an unscheduled emergency ration reformulation in `HerdManager`.

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

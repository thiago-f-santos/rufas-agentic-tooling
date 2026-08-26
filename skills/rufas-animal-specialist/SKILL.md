---
name: rufas-animal-specialist
description: Use when analyzing, configuring, or debugging the RuFaS Animal and Herd module, including herd demographics, Wood/Dijkstra lactation curves, NRC 2001/NASEM 2021 nutrient requirements, linear programming ration formulation, enteric methane emissions, or excretion partitioning.
---

# RuFaS Animal & Herd Specialist Skill

## Overview

The **RuFaS Animal Module** (`RUFAS/biophysical/animal/`) models dairy cattle herd dynamics, individual and pen-level physiological growth, reproduction, lactation mechanics, nutrient metabolism, linear programming diet formulation, enteric methane ($\text{CH}_4$) emissions, and excretion partitioning.

Managed by `HerdManager`, it bridges feed consumption from `FeedManager` with daily manure output streamed to `ManureManager`.

---

## When to Use

### Triggering Conditions & Symptoms
- Configuring herd demographics, parity distributions, genetics, or calf retention policies.
- Parameterizing lactation curves (Wood’s gamma curve, Dijkstra) or adjusting days-in-milk (DIM) profiles.
- Formulating, tuning, or troubleshooting Linear Programming (LP) least-cost rations under NRC (2001) or NASEM (2021) nutrient standards.
- Investigating infeasible diet formulations, dry matter intake (DMI) under/over-predictions, or unexpected milk yield drops.
- Quantifying enteric methane ($\text{CH}_4$) emissions and analyzing dietary mitigation strategies (e.g. fat supplementation, forage-to-concentrate ratios).
- Tracing fecal vs urinary excretion of Nitrogen (N), Phosphorus (P), Potassium (K), Volatile Solids (VS), and moisture.

### When NOT to Use
- Manure storage processing, separation, or lagoon emissions (use `rufas-manure-specialist`).
- Feed storage inventory, spoilage, or crop receiving (use `rufas-feed-storage-specialist`).
- Soil biogeochemistry and crop growth (use `rufas-field-soil-specialist`).

---

## Inputs & Metadata Schemas

The Animal module relies on 8 primary input blobs declared in scenario metadata:

| Blob Key | Physical Path (Typical) | Critical Parameters |
|---|---|---|
| `animal` | `input/data/animal/animal_general.json` | Mature body weight, breed specs, body condition score (BCS) targets, maintenance energy constants. |
| `animal_population` | `input/data/animal/animal_population_*.json` | Number of milking cows, dry cows, heifers, calves; pen occupancy limits and grouping criteria. |
| `animal_mean_phenotype` | `input/data/animal_genetics/mean_phenotype_*.json` | Base phenotypic lactation yield, milk fat %, protein %, mature size means. |
| `animal_top_listing_semen` | `input/data/animal_genetics/top_listing_semen_*.json` | AI sire genetic evaluations, PTAM, PTAF, PTAP, calving ease. |
| `lactation` | `input/data/animal/lactation_constants.json` | Wood's incomplete gamma parameters ($a, b, c$) by parity, persistency, peak milk DIM. |
| `NRC_Comp` | `input/data/feed/NRC_Feed_Library.json` | NRC 2001 chemical composition, $NE_L$, RDP, RUP, NDF, amino acid profiles. |
| `NASEM_Comp` | `input/data/feed/NASEM_Feed_Library.json` | NASEM 2021 nutrient library, dynamic digestion rates, intestinal digestibility factors. |
| `user_feeds` | `input/data/feed/user_feeds.json` | Custom on-farm feeds, farm-grown silage profiles, market feed prices and availability bounds. |

---

## Core Biophysical Mechanics & Formulas

### 1. Herd Demographics & Cohort Transitions
- **Lactating Cows**: Grouped into fresh, high, medium, and low production pens.
- **Dry Cows**: Far-off dry ($>3$ weeks pre-calving) and close-up transition ($<3$ weeks pre-calving).
- **Heifers**: Calves (pre-weaned), weaned growing heifers, breeding heifers, pregnant heifers.
- **Aging & Culling**: Animals advance daily in age and DIM. Cows are culled based on reproductive failure, involuntary health events, or low milk yield thresholds.

### 2. Lactation Modeling
Milk yield ($Y(t)$ at day $t$ in milk) follows Wood's incomplete gamma function:
$$Y(t) = a \cdot t^b \cdot e^{-c \cdot t}$$
where $a$ scales initial yield, $b$ governs rate of increase to peak, and $c$ dictates post-peak persistency decline. Separate curve coefficients are parameterized for primiparous (first lactation) vs multiparous (2+ lactations) cows.

### 3. Ration Formulation & Linear Programming (LP)
- At each `ration_formulation_interval` (or emergency shortage), `HerdManager.formulate_rations` executes an LP solver to find the least-cost blend of feeds:
  $$\min \sum_{j} \text{Cost}_j \cdot X_j$$
  Subject to:
  $$\text{DMI}_{\min} \le \sum X_j \le \text{DMI}_{\max}$$
  $$\sum \text{NEL}_j \cdot X_j \ge \text{Req}_{\text{energy}}$$
  $$\sum \text{MP}_j \cdot X_j \ge \text{Req}_{\text{protein}}$$
  $$\sum \text{fNDF}_j \cdot X_j \ge \text{Min forage NDF}$$
  $$X_j \le \text{MaxDailyFeed}_j \quad (\text{from FeedManager inventory bounds})$$

### 4. Enteric Methane ($\text{CH}_4$) Mechanics
Computed using NASEM 2021 / IPCC Tier 2 empirical models driven by dry matter intake, ether extract (fat), digestible NDF, and dietary starch:
$$\text{CH}_4 \, (\text{g/day}) = f(\text{DMI}, \text{Dietary NDF}, \text{Dietary Fat}, \text{Starch})$$

### 5. Excretion Partitioning (`ManureExcretionCalculator`)
- **Total Excreted N**: $\text{N}_{\text{excreted}} = \text{N}_{\text{intake}} - \text{N}_{\text{milk}} - \text{N}_{\text{tissue}}$.
- **Urinary N vs Fecal N**: Fecal N consists of undigested feed N and metabolic fecal N; excess absorbed N is excreted in urine as urea.
- **Volatile Solids (VS)**: Undigested dietary dry matter minus ash.
- **Moisture**: Driven by dry matter intake, dietary mineral levels, and ambient temperature.

---

## Outputs & Cross-Module Influence

| Output Variable / Data Structure | Receiving Module | Impact on Whole Farm |
|---|---|---|
| `all_manure_data: dict[str, ManureStream]` | `ManureManager` | Pen-level daily mass of feces, urine, bedding, N, P, K, and VS; dictates manure storage loading and GHG emissions. |
| `RequestedFeed` | `FeedManager` | Determines daily crop drawdown from storage and required commercial feed purchases. |
| `daily_purchased_feeds_fed` | `EEEManager` | Dictates Scope 3 upstream feed embodied emissions and daily feed purchase expenses. |
| `milk_yield_total`, `fat_kg`, `protein_kg` | `EEEManager` | Drives farm milk sales revenue and energy demand for milking/cooling. |

---

## Simulation Output Variable Dictionary & Diagnostics

In whole-farm simulations with full variable reporting (`csv_all_variables.txt`), the Animal module generates **865–912 individual time-series variables** across `AnimalModuleReporter`, `RationOptimizer`, and `LactationCurve`.

### 1. Primary Population & Demographic Metrics (`AnimalModuleReporter`)

Reported daily or at demographic census intervals, tracking herd size, parity structure, cohort ages, and body weights:

| Exact Variable Name | Unit | Diagnostic Range / Typical Value | Description |
|---|---|---|---|
| `AnimalModuleReporter.report_animal_population_statistics.population_breed` | `unitless` | e.g. `HOLSTEIN`, `JERSEY` | Base breed classification governing genetic potential and maintenance coefficients. |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows` | `animals` | Scenario-defined (e.g. 2,662) | Total adult cow population on farm (lactating + dry cows). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_lactating_cows` | `animals` | ~85–90% of total cows | Milking cow count active in milking string. |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_dry_cows` | `animals` | ~10–15% of total cows | Total non-lactating dry cows (far-off and close-up transition). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_calves` | `animals` | 0 – 500+ | Pre-weaned calf inventory (0 to ~60 days of age). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_heiferIs` | `animals` | Cohort-dependent | Post-weaning heifers (~2 to ~10 months of age). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_heiferIIs` | `animals` | Cohort-dependent | Breeding age heifers (~11 to ~15 months of age). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_heiferIIIs` | `animals` | Cohort-dependent | Confirmed pregnant replacement heifers (~16 to ~24 months of age). |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_parity_1_cows` | `animals` | ~35–45% of herd | Primiparous 1st-lactation cows. |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_parity_2_cows` | `animals` | ~25–30% of herd | Multiparous 2nd-lactation cows. |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_parity_3_cows` | `animals` | ~15–20% of herd | Multiparous 3rd-lactation cows. |
| `AnimalModuleReporter.report_animal_population_statistics.population_number_of_parity_4_cows` | `animals` | ~5–12% of herd | Multiparous 4th-lactation cows. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_calf_age` | `day` | 20 – 40 days | Mean age of active calf inventory. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_cow_age` | `day` | 1,100 – 1,400 days (~3.0–3.8 yrs) | Mean age of adult cow herd. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_calf_body_weight` | `kg` | 55 – 80 kg | Mean body weight of pre-weaned calves. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_heiferI_body_weight` | `kg` | 180 – 260 kg | Mean weight of growing heifer I cohort. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_heiferII_body_weight` | `kg` | 400 – 500 kg | Mean weight of breeding heifer II cohort. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_heiferIII_body_weight` | `kg` | 580 – 660 kg | Pre-calving springing heifer weight. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_cow_body_weight` | `kg` | 600 – 720 kg (Holstein) | Mean live body weight of milking and dry cows. |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_cow_days_in_milk` | `day` | 150 – 190 days | Herd average DIM (stable lactation indicates ~160–175 DIM). |
| `AnimalModuleReporter.report_animal_population_statistics.population_average_cow_calving_interval` | `day` | 370 – 410 days | Mean calving interval across herd. |

### 2. Daily Herd Metabolic & Production Metrics

| Exact Variable Name | Unit | Diagnostic Range | Description |
|---|---|---|---|
| `AnimalModuleReporter.report_herd_statistics_data.daily_milk_production` | `kg/day` | 28.0 – 45.0 kg/milking cow-day | Total bulk tank milk yield produced by the herd daily. |
| `AnimalModuleReporter.report_herd_statistics_data.herd_milk_fat_kg` | `kg/day` | 1.10 – 1.80 kg/cow-day | Total fat mass secreted in milk daily. |
| `AnimalModuleReporter.report_herd_statistics_data.herd_milk_fat_percent` | `unitless` / `%` | 3.50 – 4.20% (Holstein) | Bulk tank milk fat test concentration. |
| `AnimalModuleReporter.report_herd_statistics_data.herd_milk_protein_kg` | `kg/day` | 0.90 – 1.45 kg/cow-day | Total true protein mass secreted in milk daily. |
| `AnimalModuleReporter.report_herd_statistics_data.herd_milk_protein_percent` | `percent` | 3.00 – 3.40% | Bulk tank milk crude/true protein test concentration. |
| `AnimalModuleReporter.report_305_day_milk_yield.milk_305_day_yield_herd_mean` | `kg` | 10,000 – 14,000 kg | Projected/realized standardized 305-day lactation yield. |
| `AnimalModuleReporter.report_ration_per_animal.ration_per_animal_for_{pen}.dry_matter_intake_total` | `kg` | 20.0 – 28.5 kg DM (`total_DMI_kg` / head) | Individual head average dry matter intake for the specified pen (`LAC_COW_PEN_3`, `CLOSE_UP_PEN_2`, `GROWING_PEN_1`, `CALF_PEN_0`). |
| `AnimalModuleReporter.report_daily_herd_total_ration.ration_daily_feed_total_across_pens.dry_matter_intake_total` | `kg` | Herd Total DMI | Whole-farm herd daily aggregate dry matter intake. |
| `AnimalModuleReporter.report_enteric_methane_emission.enteric_methane_emission_for_{pen}` | `g` | 350 – 550 g $\text{CH}_4$/lactating cow-day | Daily pen-level enteric methane emission mass from ruminal fermentation. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_manure_mass` | `kg` | 55 – 85 kg/cow-day | Total wet manure (feces + urine) mass excreted per pen. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_urine` | `kg` | 18 – 30 kg/cow-day | Daily urinary excretion mass. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_urea` | `g/L` | 400 – 900 g/L | Urinary urea concentration index. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_total_solids` | `kg` | 7.0 – 10.5 kg/cow-day (`fecal_DM` + `urinary_DM`) | Total dry solids in excreted manure stream. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_degradable_volatile_solids` | `kg` | 6.0 – 9.0 kg/cow-day (`manure_VS`) | Anaerobically digestible volatile solids loading for manure storage. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_non_degradable_volatile_solids` | `kg` | 0.8 – 1.5 kg/cow-day | Recalcitrant fiber/lignin volatile solids portion. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_manure_nitrogen` | `kg` | 0.38 – 0.52 kg N/cow-day (`manure_nitrogen`) | Total nitrogen excreted in manure (organic + ammoniacal). |
| `AnimalModuleReporter.report_manure_excretions.{pen}_urine_nitrogen` | `kg` | 0.15 – 0.28 kg N/cow-day | Readily volatilizable urinary nitrogen mass. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_manure_total_ammoniacal_nitrogen` | `kg` | 0.15 – 0.28 kg N/cow-day | Total Ammoniacal Nitrogen (TAN = $\text{NH}_4^+ + \text{NH}_3$). |
| `AnimalModuleReporter.report_manure_excretions.{pen}_phosphorus` | `g` | 60 – 95 g P/cow-day (`manure_phosphorus`) | Total elemental phosphorus mass excreted. |
| `AnimalModuleReporter.report_manure_excretions.{pen}_potassium` | `g` | 200 – 350 g K/cow-day (`manure_potassium`) | Total elemental potassium mass excreted. |

### 3. Ration Formulation & Lactation Kinetics

#### Lactation Curve Parameters (`LactationCurve`)
Wood's incomplete gamma curve parameters ($l, m, n$) initialized per parity group:
- `LactationCurve.__init__.parity_1_lactation_curve_parameter__l (unitless)`: Scaling/initial yield factor (~0.169 for primiparous).
- `LactationCurve.__init__.parity_1_lactation_curve_parameter__m (unitless)`: Incline to peak milk yield (~0.003–0.004).
- `LactationCurve.__init__.parity_1_lactation_curve_parameter__n (unitless)`: Post-peak persistency decline (~0.002–0.003).
- `LactationCurve.__init__.parity_2_lactation_curve_parameter__l / _m / _n`: Multiparous 2nd parity coefficients (~0.201 / 0.004 / 0.003).
- `LactationCurve.__init__.parity_3_lactation_curve_parameter__l / _m / _n`: Mature 3rd+ parity coefficients (~0.218 / 0.004 / 0.003).

#### Ration Optimizer Infeasibility Diagnostics (`RationOptimizer`)
When Linear Programming ration formulation encounters bounding conflicts, `RationOptimizer.handle_failed_constraints` logs full failure traces:
- `failed_constraint_summary_for_{pen}.simulation day`: Day index of LP solver invocation failure.
- `failed_constraint_summary_for_{pen}.attempt number`: Iteration count during constraint relaxation ladder.
- `failed_constraint_summary_for_{pen}.constraints_failed_dict`: Dictionary identifying the specific unmet constraints (e.g. `min_forage_ndf`, `max_dmi`, `min_metabolizable_protein`).
- `failed_constraint_summary_for_{pen}.ration_attempted`: Exact ingredient vector attempted prior to infeasibility throw.
- `failed_constraint_summary_for_{pen}.pen requirements`: Dynamic nutrient target vector containing `maintenance_energy` (Mcal), `growth_energy` (Mcal), `pregnancy_energy` (Mcal), `lactation_energy` (Mcal), `metabolizable_protein` (g), `calcium` (g), `phosphorus` (g), `dry_matter` (kg), and `activity_energy` (Mcal).

---

### 4. Diagnostic Validation Rules & Biological Benchmark Ranges

When evaluating RuFaS Animal simulation runs, compare output time series against the following biological bounds:

| Metric | Reference Species / Cohort | Benchmark Range | Anomaly Threshold & Root Cause |
|---|---|---|---|
| **Dry Matter Intake (DMI)** | Milking Holstein Cow | 20.0 – 28.5 kg DM/day | `< 18.0` kg/day indicates severe diet infeasibility, extreme NDF bulk, or heat stress over-penalization. `> 32.0` kg/day indicates unconstrained LP intake bounds. |
| **Milk Production** | Milking Holstein Cow | 28.0 – 45.0 kg/cow-day | `< 22.0` kg/day indicates energy/protein deficit in ration or inaccurate Wood's curve $a$ parameter. |
| **Milk Fat Test** | Holstein | 3.50 – 4.20% | `< 3.20%` indicates subacute ruminal acidosis (SARA) risk or forage NDF $< 19\%$ DM. |
| **Enteric Methane** | Milking Cow | 350 – 550 g $\text{CH}_4$/day (18–24 g/kg DMI) | `> 650` g/day indicates disproportionately high structural fiber or missing fat/additive emission suppression. |
| **Nitrogen Efficiency (NUE)** | Lactating Herd | 25 – 35% ($\text{N}_{\text{milk}} / \text{N}_{\text{intake}}$) | `< 22%` indicates excessive dietary Crude Protein (> 18.5% DM) causing excessive urinary urea N loading in manure. |
| **Manure Total Solids (TS)** | Excreted Manure | 12.0 – 15.0% | `< 9.0%` indicates excessive dietary water intake or mineral osmotic imbalance. |

---

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"If LP ration fails, I'll bypass nutrient constraints."* | Infeasible LP means diet bounds (e.g. min forage NDF, max intake) are incompatible with available feeds. Inspect `user_feeds.json` or widen allowable purchase feeds. |
| *"Enteric methane is a constant emission factor."* | In RuFaS, enteric $\text{CH}_4$ dynamically responds daily to DMI, dietary forage proportion, and fat levels. |
| *"Excreted N is all identical."* | Urinary N (mostly urea) volatilizes rapidly to $\text{NH}_3$ in the barn; fecal N is organic and mineralizes slowly. |

### 🚩 Diagnostic Red Flags
- LP formulation failure in `output/logs/errors.txt` $\rightarrow$ Check feed availability bounds in `feed_storage_instances.json` and `RationOptimizer.handle_failed_constraints`.
- Negative energy balance exceeding physiological limits $\rightarrow$ Check lactation curve peak parameter or diet $NE_L$ density.
- Sudden drops in herd intake $\rightarrow$ Check ambient heat stress (THI) adjustments in weather interaction.

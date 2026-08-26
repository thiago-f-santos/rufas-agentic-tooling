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

## Red Flags & Rationalization Table

| Rationalization / Mistake | Reality & Correct Protocol |
|---|---|
| *"If LP ration fails, I'll bypass nutrient constraints."* | Infeasible LP means diet bounds (e.g. min forage NDF, max intake) are incompatible with available feeds. Inspect `user_feeds.json` or widen allowable purchase feeds. |
| *"Enteric methane is a constant emission factor."* | In RuFaS, enteric $\text{CH}_4$ dynamically responds daily to DMI, dietary forage proportion, and fat levels. |
| *"Excreted N is all identical."* | Urinary N (mostly urea) volatilizes rapidly to $\text{NH}_3$ in the barn; fecal N is organic and mineralizes slowly. |

### 🚩 Diagnostic Red Flags
- LP formulation failure in `output/logs/errors.txt` $\rightarrow$ Check feed availability bounds in `feed_storage_instances.json`.
- Negative energy balance exceeding physiological limits $\rightarrow$ Check lactation curve peak parameter or diet $NE_L$ density.
- Sudden drops in herd intake $\rightarrow$ Check ambient heat stress (THI) adjustments in weather interaction.

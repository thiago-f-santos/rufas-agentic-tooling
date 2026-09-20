# Passo 2: Cenário Piloto Brasileiro (Minas Gerais) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create, configure, validate, and execute the first operational Brazilian RuFaS pilot scenario for Minas Gerais (Patos de Minas), including weather series, Latossolo Vermelho soil, field properties, scenario metadata mapping all 22 required blobs, automated validation, and biophysical verification.

**Architecture:** A regionalized modular configuration in RuFaS (`input/`) referencing Patos de Minas, MG (IBGE `3148004`, Lat `-18.5789`, Lon `-46.5181`). Generates a 2-year daily weather series (2021-2022), parametrizes a 4-layer Latossolo Vermelho from empirical MapBiomas SoilData / Embrapa observations, wires the 22 required blobs in scenario metadata, and verifies execution and Southern Hemisphere photoperiod.

**Tech Stack:** Python 3.10+, RuFaS biophysical engine, Pandas, JSON Schema, NASA POWER API / MapBiomas SoilData, Pytest/Unittest.

**Spec:** [`rufas-agentic-tooling/docs/superpowers/specs/2026-09-19-passo-2-cenario-piloto-brasil-minas-gerais-design.md`](file:///home/thiago/Projects/rufas-agentic-tooling/docs/superpowers/specs/2026-09-19-passo-2-cenario-piloto-brasil-minas-gerais-design.md) (also mirrored in [`research/spec_passo_2_cenario_piloto_minas_gerais.md`](file:///home/thiago/Projects/research/spec_passo_2_cenario_piloto_minas_gerais.md))

## Global Constraints

- Country code: `"BRA"`, Region code: `3148004` (Patos de Minas - MG).
- Temporal period: `2021:1` to `2022:365` (2 complete calendar years, 730 days).
- Southern Hemisphere Coordinates: Latitude `-18.5789`, Longitude `-46.5181`.
- Soil vertical discretization: Layer 1 must be exactly `20 mm` deep (SurPhos requirement). Total layers = 4 (`20 mm`, `200 mm`, `600 mm`, `1500 mm`).
- Soil hydraulic hierarchy: $\theta_{wp} \le \theta_{fc} \le \theta_{sat}$.
- All 22 required blobs must be mapped in `cenario_minas_gerais_metadata.json`.

---

### Task 1: Fix Required Blob Name in RuFaS Inspector

**Files:**
- Modify: `rufas-agentic-tooling/tools/rufas_inspector.py:21-45`
- Test: `rufas-agentic-tooling/tests/test_tooling.py`

**Interfaces:**
- Consumes: `RuFaS/RUFAS/input_manager.py` (`REQUIRED_FILE_BLOBS`)
- Produces: Corrected `REQUIRED_FILE_BLOBS` in `tools.rufas_inspector` containing `"animal_mean_phenotype"` instead of `"animal_net_merit"`.

- [ ] **Step 1: Write failing test / verify existing failure**

Run: `python3 -m unittest tests/test_tooling.py`
Expected: FAIL on `test_inspector_against_example_freestall_scenario` with `missing required file blobs: ['animal_net_merit']`.

- [ ] **Step 2: Update `REQUIRED_FILE_BLOBS` in `tools/rufas_inspector.py`**

In `rufas-agentic-tooling/tools/rufas_inspector.py`, replace `"animal_net_merit"` with `"animal_mean_phenotype"` in `REQUIRED_FILE_BLOBS`:
```python
REQUIRED_FILE_BLOBS: Set[str] = {
    "config",
    "animal",
    "animal_population",
    "animal_mean_phenotype",
    "animal_top_listing_semen",
    "lactation",
    "economy",
    "emission",
    "purchased_feeds_emissions",
    "purchased_feed_land_use_change_emissions",
    "feed",
    "NRC_Comp",
    "NASEM_Comp",
    "manure_management",
    "manure_processor_connection",
    "crop_configurations",
    "weather",
    "user_feeds",
    "tractor_dataset",
    "EEE_constants",
    "feed_storage_configurations",
    "feed_storage_instances",
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_tooling.py`
Expected: PASS with 0 failures.

- [ ] **Step 4: Commit**

```bash
git add tools/rufas_inspector.py
git commit -m "fix(inspector): use animal_mean_phenotype in REQUIRED_FILE_BLOBS matching RuFaS core"
```

---

### Task 2: Weather Data Generator & Fetcher for Patos de Minas

**Files:**
- Create: `rufas-agentic-tooling/tools/rufas_weather_fetcher.py`
- Create: `RuFaS/input/data/weather/weather_minas_gerais.csv`
- Test: `rufas-agentic-tooling/tests/test_weather_generator.py`

**Interfaces:**
- Consumes: NASA POWER API (lat `-18.5789`, lon `-46.5181`, 2021-01-01 to 2022-12-31) with offline climatological fallback.
- Produces: `weather_minas_gerais.csv` with columns: `year,jday,precip,high,low,avg,Hday,irrigation` (730 rows).

- [ ] **Step 1: Write the failing test**

Create `rufas-agentic-tooling/tests/test_weather_generator.py`:
```python
import unittest
from pathlib import Path
import pandas as pd
from tools.rufas_weather_fetcher import generate_patos_de_minas_weather

class TestWeatherGenerator(unittest.TestCase):
    def test_generate_weather_file(self):
        output_csv = Path("/tmp/test_weather_mg.csv")
        if output_csv.exists():
            output_csv.unlink()
        
        generate_patos_de_minas_weather(output_csv, use_api=False)
        self.assertTrue(output_csv.exists())
        
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 730)  # 365 days * 2 years
        expected_cols = ["year", "jday", "precip", "high", "low", "avg", "Hday", "irrigation"]
        self.assertListEqual(list(df.columns), expected_cols)
        
        # Check temperature constraints
        self.assertTrue((df["high"] >= df["avg"]).all())
        self.assertTrue((df["avg"] >= df["low"]).all())
        self.assertTrue((df["precip"] >= 0.0).all())
        self.assertTrue((df["Hday"] >= 0.0).all())
        
        # Check annual rainfall is realistic for Cerrado (~1100-1600 mm/year)
        annual_rain = df.groupby("year")["precip"].sum()
        for yr, rain in annual_rain.items():
            self.assertGreater(rain, 900)
            self.assertLess(rain, 1800)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_weather_generator.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rufas_weather_fetcher'`.

- [ ] **Step 3: Implement `tools/rufas_weather_fetcher.py`**

Create `rufas-agentic-tooling/tools/rufas_weather_fetcher.py` to fetch from NASA POWER daily API or generate realistic calibrated climatological data for Patos de Minas (summer rainy season Nov-Mar, dry winter May-Aug, $T_{\text{max}} 25-33^\circ\text{C}$, $T_{\text{min}} 11-19^\circ\text{C}$, $H_{\text{day}} 14-25\text{ MJ/m}^2$, irrigation $0.0$).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_weather_generator.py`
Expected: PASS.

- [ ] **Step 5: Generate canonical `weather_minas_gerais.csv` in RuFaS**

Run: `python3 -m tools.rufas_weather_fetcher --output ../RuFaS/input/data/weather/weather_minas_gerais.csv`
Verify: File exists at `RuFaS/input/data/weather/weather_minas_gerais.csv` with 731 lines (header + 730 days).

- [ ] **Step 6: Commit**

```bash
git add tools/rufas_weather_fetcher.py tests/test_weather_generator.py
git commit -m "feat(weather): add weather generator and Patos de Minas 2021-2022 dataset"
```

---

### Task 3: Config File (`config_minas_gerais.json`)

**Files:**
- Create: `RuFaS/input/data/config/config_minas_gerais.json`
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

**Interfaces:**
- Consumes: RuFaS `config_properties` schema.
- Produces: `config_minas_gerais.json` with `country: "BRA"`, `region_code: 3148004`, `start_date: "2021:1"`, `end_date: "2022:365"`.

- [ ] **Step 1: Write test for config validation**

In `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`:
```python
import json
import unittest
from pathlib import Path
from tools.config import get_rufas_root

class TestCenarioMinasGerais(unittest.TestCase):
    def setUp(self):
        self.rufas_root = get_rufas_root()

    def test_config_minas_gerais(self):
        config_path = self.rufas_root / "input" / "data" / "config" / "config_minas_gerais.json"
        self.assertTrue(config_path.exists(), f"Missing {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("country"), "BRA")
        self.assertEqual(cfg.get("region_code"), 3148004)
        self.assertEqual(cfg.get("start_date"), "2021:1")
        self.assertEqual(cfg.get("end_date"), "2022:365")
        self.assertEqual(cfg.get("nutrient_standard"), "NASEM")
        self.assertEqual(cfg.get("simulation_type"), "full_farm")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_config_minas_gerais`
Expected: FAIL with `Missing config_minas_gerais.json`.

- [ ] **Step 3: Create `config_minas_gerais.json`**

Create `RuFaS/input/data/config/config_minas_gerais.json`:
```json
{
    "country": "BRA",
    "region_code": 3148004,
    "start_date": "2021:1",
    "end_date": "2022:365",
    "set_seed": true,
    "simulation_type": "full_farm",
    "nutrient_standard": "NASEM",
    "include_detailed_values": false
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_config_minas_gerais`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C ../RuFaS add input/data/config/config_minas_gerais.json
git -C ../RuFaS commit -m "feat(config): add Brazilian config for Patos de Minas (2021-2022)"
```

---

### Task 4: Latossolo Vermelho Soil Profile (`soil_minas_gerais.json`)

**Files:**
- Create: `RuFaS/input/data/soil/soil_minas_gerais.json`
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

**Interfaces:**
- Consumes: MapBiomas SoilData empirical observation E60/Perfil-11 for Patos de Minas - MG.
- Produces: `soil_minas_gerais.json` satisfying all SWAT/RuFaS physical, hydraulic, and biogeochemical constraints.

- [ ] **Step 1: Write test for soil physical-hydraulic constraints**

In `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`, add `test_soil_minas_gerais`:
```python
    def test_soil_minas_gerais(self):
        soil_path = self.rufas_root / "input" / "data" / "soil" / "soil_minas_gerais.json"
        self.assertTrue(soil_path.exists(), f"Missing {soil_path}")
        with open(soil_path, "r", encoding="utf-8") as f:
            soil = json.load(f)

        layers = soil.get("soil_layers", [])
        self.assertEqual(len(layers), 4)
        self.assertEqual(layers[0]["bottom_depth"], 20, "First layer must be 20mm for SurPhos")
        self.assertEqual(layers[1]["bottom_depth"], 200)
        self.assertEqual(layers[2]["bottom_depth"], 600)
        self.assertEqual(layers[3]["bottom_depth"], 1500)

        for i, lyr in enumerate(layers):
            # No nulls allowed in active profile
            for k, v in lyr.items():
                self.assertIsNotNone(v, f"Layer {i} has null for {k}")

            # Hydraulic hierarchy
            wp = lyr["wilting_point_water_concentration"]
            fc = lyr["field_capacity_water_concentration"]
            sat = lyr["saturation_point_water_concentration"]
            self.assertLessEqual(wp, fc, f"Layer {i}: wp > fc")
            self.assertLessEqual(fc, sat, f"Layer {i}: fc > sat")

            # Granulometry sums to ~1.0
            total_texture = lyr["clay_fraction"] + lyr["silt_fraction"] + lyr["sand_fraction"] + lyr["rock_fraction"]
            self.assertAlmostEqual(total_texture, 1.0, places=2)

            # Bulk density realistic for Latossolo (0.95 - 1.20)
            bd = lyr["bulk_density"]
            self.assertGreaterEqual(bd, 0.95)
            self.assertLessEqual(bd, 1.20)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_soil_minas_gerais`
Expected: FAIL with `Missing soil_minas_gerais.json`.

- [ ] **Step 3: Create `soil_minas_gerais.json`**

Create `RuFaS/input/data/soil/soil_minas_gerais.json` with the empirical parameters from MapBiomas SoilData (Patos de Minas Observation E60):
```json
{
    "second_moisture_condition_parameter": 68.0,
    "average_subbasin_slope": 0.025,
    "slope_length": 30.0,
    "manning_roughness_coefficient": 0.35,
    "albedo": 0.14,
    "soil_evaporation_compensation_coefficient": 0.95,
    "initial_residue": 500.0,
    "soil_layers": [
        {
            "bottom_depth": 20,
            "soil_water_concentration": 0.28,
            "wilting_point_water_concentration": 0.18,
            "field_capacity_water_concentration": 0.28,
            "saturation_point_water_concentration": 0.55,
            "saturated_hydraulic_conductivity": 40.0,
            "initial_temperature": 23.0,
            "bulk_density": 1.10,
            "organic_carbon_fraction": 0.025,
            "clay_fraction": 0.59,
            "silt_fraction": 0.30,
            "sand_fraction": 0.11,
            "rock_fraction": 0.0,
            "pH": 6.0,
            "initial_labile_inorganic_phosphorus_concentration": 15.0,
            "initial_soil_nitrate_concentration": 5.0,
            "initial_soil_ammonium_concentration": 2.0,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 200,
            "soil_water_concentration": 0.28,
            "wilting_point_water_concentration": 0.18,
            "field_capacity_water_concentration": 0.28,
            "saturation_point_water_concentration": 0.55,
            "saturated_hydraulic_conductivity": 40.0,
            "initial_temperature": 22.5,
            "bulk_density": 1.10,
            "organic_carbon_fraction": 0.022,
            "clay_fraction": 0.59,
            "silt_fraction": 0.30,
            "sand_fraction": 0.11,
            "rock_fraction": 0.0,
            "pH": 5.8,
            "initial_labile_inorganic_phosphorus_concentration": 10.0,
            "initial_soil_nitrate_concentration": 3.0,
            "initial_soil_ammonium_concentration": 1.0,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 600,
            "soil_water_concentration": 0.28,
            "wilting_point_water_concentration": 0.18,
            "field_capacity_water_concentration": 0.28,
            "saturation_point_water_concentration": 0.54,
            "saturated_hydraulic_conductivity": 45.0,
            "initial_temperature": 22.0,
            "bulk_density": 1.08,
            "organic_carbon_fraction": 0.015,
            "clay_fraction": 0.61,
            "silt_fraction": 0.28,
            "sand_fraction": 0.11,
            "rock_fraction": 0.0,
            "pH": 5.5,
            "initial_labile_inorganic_phosphorus_concentration": 3.0,
            "initial_soil_nitrate_concentration": 1.5,
            "initial_soil_ammonium_concentration": 0.5,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        },
        {
            "bottom_depth": 1500,
            "soil_water_concentration": 0.27,
            "wilting_point_water_concentration": 0.18,
            "field_capacity_water_concentration": 0.27,
            "saturation_point_water_concentration": 0.52,
            "saturated_hydraulic_conductivity": 50.0,
            "initial_temperature": 21.5,
            "bulk_density": 1.05,
            "organic_carbon_fraction": 0.008,
            "clay_fraction": 0.63,
            "silt_fraction": 0.26,
            "sand_fraction": 0.11,
            "rock_fraction": 0.0,
            "pH": 5.2,
            "initial_labile_inorganic_phosphorus_concentration": 1.0,
            "initial_soil_nitrate_concentration": 0.8,
            "initial_soil_ammonium_concentration": 0.2,
            "ammonium_volatilization_cation_exchange_factor": 0.45
        }
    ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_soil_minas_gerais`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C ../RuFaS add input/data/soil/soil_minas_gerais.json
git -C ../RuFaS commit -m "feat(soil): add Latossolo Vermelho profile for Patos de Minas based on MapBiomas SoilData"
```

---

### Task 5: Field Specification (`field_minas_gerais.json`)

**Files:**
- Create: `RuFaS/input/data/field/field_minas_gerais.json`
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

**Interfaces:**
- Consumes: References `"soil_specification": "soil_minas_gerais"`.
- Produces: `field_minas_gerais.json` with signed latitude `-18.5789`, `field_size: 20.0`, `minimum_daylength: 10.8`.

- [ ] **Step 1: Write test for field properties**

In `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`, add `test_field_minas_gerais`:
```python
    def test_field_minas_gerais(self):
        field_path = self.rufas_root / "input" / "data" / "field" / "field_minas_gerais.json"
        self.assertTrue(field_path.exists(), f"Missing {field_path}")
        with open(field_path, "r", encoding="utf-8") as f:
            fld = json.load(f)
        self.assertEqual(fld.get("soil_specification"), "soil_minas_gerais")
        self.assertEqual(fld.get("field_size"), 20.0)
        self.assertEqual(fld.get("latitude"), -18.5789)
        self.assertEqual(fld.get("longitude"), -46.5181)
        self.assertEqual(fld.get("minimum_daylength"), 10.8)
        self.assertFalse(fld.get("seasonal_high_water_table"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_field_minas_gerais`
Expected: FAIL with `Missing field_minas_gerais.json`.

- [ ] **Step 3: Create `field_minas_gerais.json`**

Create `RuFaS/input/data/field/field_minas_gerais.json`:
```json
{
    "soil_specification": "soil_minas_gerais",
    "crop_specification": "Corn-Silage-MG",
    "fertilizer_management_specification": "fertilizer_schedule_minas_gerais",
    "manure_management_specification": "manure_schedule_minas_gerais",
    "tillage_management_specification": "tillage_schedule_minas_gerais",
    "field_size": 20.0,
    "latitude": -18.5789,
    "longitude": -46.5181,
    "minimum_daylength": 10.8,
    "seasonal_high_water_table": false,
    "watering_amount_in_liters": 0.0,
    "watering_interval": 0,
    "simulate_water_stress": true,
    "simulate_temp_stress": true,
    "simulate_nitrogen_stress": true,
    "simulate_phosphorus_stress": true,
    "tractor_size": "medium"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_field_minas_gerais`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C ../RuFaS add input/data/field/field_minas_gerais.json
git -C ../RuFaS commit -m "feat(field): add Patos de Minas field specification with Southern Hemisphere latitude"
```

---

### Task 6: Scenario Metadata (`cenario_minas_gerais_metadata.json`) & Task Configuration

**Files:**
- Create: `RuFaS/input/metadata/cenario_minas_gerais_metadata.json`
- Create: `RuFaS/input/data/tasks/task_minas_gerais.json`
- Create: `RuFaS/input/task_manager_minas_gerais_metadata.json`
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

**Interfaces:**
- Consumes: All 22 required blobs (custom MG files + reusable base files).
- Produces: Master scenario metadata file valid under `rufas_inspector`.

- [ ] **Step 1: Write test for scenario metadata using `rufas_inspector`**

In `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`, add `test_scenario_metadata_validation`:
```python
    def test_scenario_metadata_validation(self):
        from tools.rufas_inspector import inspect_scenario_metadata, inspect_task_metadata
        scenario_meta = self.rufas_root / "input" / "metadata" / "cenario_minas_gerais_metadata.json"
        self.assertTrue(scenario_meta.exists(), f"Missing {scenario_meta}")

        valid, errors, warnings = inspect_scenario_metadata(scenario_meta, self.rufas_root)
        self.assertTrue(valid, f"Scenario validation failed: {errors}")
        self.assertEqual(len(errors), 0)

        tm_meta = self.rufas_root / "input" / "task_manager_minas_gerais_metadata.json"
        self.assertTrue(tm_meta.exists(), f"Missing {tm_meta}")
        valid_tm, tm_errors, _ = inspect_task_metadata(tm_meta, self.rufas_root)
        self.assertTrue(valid_tm, f"Task manager validation failed: {tm_errors}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_scenario_metadata_validation`
Expected: FAIL with `Missing cenario_minas_gerais_metadata.json`.

- [ ] **Step 3: Create `cenario_minas_gerais_metadata.json`**

Create `RuFaS/input/metadata/cenario_minas_gerais_metadata.json` mapping:
1. `"config"`: `input/data/config/config_minas_gerais.json`
2. `"weather"`: `input/data/weather/weather_minas_gerais.csv`
3. `"field_1"`: `input/data/field/field_minas_gerais.json`
4. `"soil_1"`: `input/data/soil/soil_minas_gerais.json`
5. `"Corn-Silage-MG"`: `input/data/crop/example_alf_corn_silage_rotation.json`
6. Reusable blobs: `animal`, `animal_population`, `animal_mean_phenotype`, `animal_top_listing_semen`, `lactation`, `economy`, `emission`, `purchased_feeds_emissions`, `purchased_feed_land_use_change_emissions`, `feed`, `NRC_Comp`, `NASEM_Comp`, `manure_management`, `manure_processor_connection`, `crop_configurations`, `user_feeds`, `tractor_dataset`, `EEE_constants`, `feed_storage_configurations`, `feed_storage_instances`, `fertilizer_schedule_minas_gerais`, `manure_schedule_minas_gerais`, `tillage_schedule_minas_gerais`.

- [ ] **Step 4: Create Task Data and Task Manager Metadata**

Create `RuFaS/input/data/tasks/task_minas_gerais.json` and `RuFaS/input/task_manager_minas_gerais_metadata.json` configured for a single simulation run of the Minas Gerais scenario.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py::TestCenarioMinasGerais::test_scenario_metadata_validation`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C ../RuFaS add input/metadata/cenario_minas_gerais_metadata.json input/data/tasks/task_minas_gerais.json input/task_manager_minas_gerais_metadata.json
git -C ../RuFaS commit -m "feat(metadata): map 22 required blobs and task metadata for Minas Gerais pilot"
```

---

### Task 7: Full Scenario Inspector & Cross-Validation Verification

**Files:**
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

**Interfaces:**
- Consumes: Complete scenario files and `tools.rufas_inspector`.
- Produces: Automated verification passing all schema and physical checks.

- [ ] **Step 1: Execute `rufas_inspector` CLI command on scenario**

Run: `python3 -m tools.rufas_inspector --scenario ../RuFaS/input/metadata/cenario_minas_gerais_metadata.json`
Expected: Output showing `Inspection Result: VALID` with 0 errors.

- [ ] **Step 2: Execute `rufas_inspector` CLI command on task manager**

Run: `python3 -m tools.rufas_inspector --task-metadata ../RuFaS/input/task_manager_minas_gerais_metadata.json`
Expected: Output showing `Task Manager Metadata Inspection Result: VALID` with 0 errors.

- [ ] **Step 3: Run all scenario unit tests**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cenario_minas_gerais.py
git commit -m "test(scenario): complete automated validation suite for Minas Gerais pilot scenario"
```

---

### Task 8: Simulation Execution & Southern Hemisphere Biophysical Verification

**Files:**
- Test/Verification: Run simulation with `rufas_runner` or `main.py`
- Verify: `RuFaS/output/logs/logs.txt`, `RuFaS/output/` variables.

**Interfaces:**
- Consumes: Task manager metadata `input/task_manager_minas_gerais_metadata.json`.
- Produces: Completed simulation run with Southern Hemisphere photoperiod and Latossolo water balance verified in logs.

- [ ] **Step 1: Execute simulation run**

Run: `python3 -m tools.rufas_runner --task-metadata input/task_manager_minas_gerais_metadata.json --output-dir output/minas_gerais_run` (or run via `python3 main.py`).
Expected: Simulation runs to completion without fatal exceptions.

- [ ] **Step 2: Verify Southern Hemisphere photoperiod in simulation logs**

Check in log output that astronomical day length peaks in December/January (>13.0 hours) and reaches its minimum in June/July (~10.8 hours), confirming Southern Hemisphere seasonality.

- [ ] **Step 3: Verify soil water balance stability in output**

Check that no hydraulic solver divergence or negative soil moisture warnings occurred, confirming the stability of the Latossolo Vermelho profile.

- [ ] **Step 4: Final verification and summary commit**

Commit any helper verification scripts or documentation notes:
```bash
git add -A
git commit -m "feat(scenario): verified end-to-end execution of Minas Gerais pilot scenario"
```

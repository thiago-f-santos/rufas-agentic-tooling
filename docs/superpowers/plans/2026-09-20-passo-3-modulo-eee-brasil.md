# Passo 3: Módulo EEE Brasil (Emissões, Energia e Economia Regionalizadas) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Regionalize RuFaS Economics, Energy, and Emissions (EEE) for Brazil / Minas Gerais, mapping GFLI/Embrapa cradle-to-farm-gate feed emissions, PAS 2050 dLUC, MCTI grid electricity emission factors, and international USD costs, verifying complete farm carbon footprint without warnings.

**Architecture:** Implements `rufas_eee_builder.py` in tooling to generate canonical EEE datasets for Minas Gerais (IBGE `3148004`, UF `31`), wires 4 regional blobs in `cenario_minas_gerais_metadata.json`, and adds automated tests in `tests/test_cenario_minas_gerais_eee.py` verifying Scope 1-3 calculations.

**Tech Stack:** Python 3.10+, RuFaS biophysical engine, GFLI v3.0, MCTI SIN factor, Unittest.

**Spec:** [`rufas-agentic-tooling/docs/superpowers/specs/2026-09-20-passo-3-modulo-eee-brasil-design.md`](../specs/2026-09-20-passo-3-modulo-eee-brasil-design.md) (also mirrored in [`research/spec_passo_3_modulo_eee_brasil.md`](file:///home/thiago/Projects/research/spec_passo_3_modulo_eee_brasil.md))

## Global Constraints

- Country code: `"BRA"`, Region code: `3148004` (Patos de Minas - MG), State code: `31`.
- Regional feed emissions: Must provide production emissions and dLUC for IDs: `23, 44, 50, 95, 104, 110, 170, 202, 216, 301, 302`.
- Electricity grid emission factor: `0.065 kg CO2e/kWh` (MCTI SIN 2021-2022 average).
- Diesel emission factor: `2.64 kg CO2e/L` (B12/B14 blend).
- Zero `Missing Regional Feed Emissions` warnings on simulation execution.
- Carbon intensity sanity benchmark: $1.00\text{ to }1.60\text{ kg CO}_2\text{e} / \text{kg FPCM}$.

---

### Task 1: Test Suite for EEE Datasets & Builder Tool

**Files:**
- Create: `rufas-agentic-tooling/tests/test_eee_builder.py`
- Test: `rufas-agentic-tooling/tests/test_eee_builder.py`

**Interfaces:**
- Consumes: `tools.rufas_eee_builder.build_minas_gerais_eee_datasets`
- Produces: Test verification for generated CSV formats, column names, region codes, and value ranges.

- [ ] **Step 1: Write the failing test**

Create `rufas-agentic-tooling/tests/test_eee_builder.py`:
```python
import csv
import tempfile
import unittest
from pathlib import Path

from tools.rufas_eee_builder import build_minas_gerais_eee_datasets


class TestEEEBuilder(unittest.TestCase):
    def test_build_minas_gerais_eee_datasets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            files = build_minas_gerais_eee_datasets(out_dir)

            expected_files = [
                "purchased_feeds_emissions_minas_gerais.csv",
                "purchased_feed_land_use_change_emissions_minas_gerais.csv",
                "default_emissions_minas_gerais.csv",
                "default_costs_minas_gerais.csv",
            ]
            for fname in expected_files:
                self.assertIn(fname, files)
                p = out_dir / fname
                self.assertTrue(p.exists(), f"File {fname} was not created")
                self.assertGreater(p.stat().st_size, 0)

            # Check purchased feeds emissions CSV format
            feed_csv = out_dir / "purchased_feeds_emissions_minas_gerais.csv"
            with open(feed_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertIn("region_code", reader.fieldnames)
                # Verify priority feed IDs exist as columns
                for fid in ["23", "44", "50", "95", "104", "110", "170", "202", "216", "301", "302"]:
                    self.assertIn(fid, reader.fieldnames)

                rows = list(reader)
                self.assertGreaterEqual(len(rows), 2)  # At least state 31 and city 3148004
                regions = [r["region_code"] for r in rows]
                self.assertIn("31", regions)
                self.assertIn("3148004", regions)

                # Check specific GFLI values
                row_mg = next(r for r in rows if r["region_code"] == "31")
                self.assertAlmostEqual(float(row_mg["44"]), 0.28, places=2)
                self.assertAlmostEqual(float(row_mg["170"]), 0.45, places=2)

            # Check LUC CSV format
            luc_csv = out_dir / "purchased_feed_land_use_change_emissions_minas_gerais.csv"
            with open(luc_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertIn("region_code", reader.fieldnames)
                rows = list(reader)
                row_mg = next(r for r in rows if r["region_code"] == "31")
                self.assertAlmostEqual(float(row_mg["170"]), 1.85, places=2)
                self.assertAlmostEqual(float(row_mg["44"]), 0.15, places=2)

            # Check costs CSV format
            costs_csv = out_dir / "default_costs_minas_gerais.csv"
            with open(costs_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)
                self.assertIn("diesel_cost_gal", row)
                self.assertIn("electricity_cost_kwh", row)
                self.assertAlmostEqual(float(row["diesel_cost_gal"]), 4.16, places=2)
                self.assertAlmostEqual(float(row["electricity_cost_kwh"]), 0.12, places=2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_eee_builder.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rufas_eee_builder'`.

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_eee_builder.py
git commit -m "test(eee): add test suite for Minas Gerais EEE dataset builder"
```

---

### Task 2: Implement `tools/rufas_eee_builder.py`

**Files:**
- Create: `rufas-agentic-tooling/tools/rufas_eee_builder.py`
- Test: `rufas-agentic-tooling/tests/test_eee_builder.py`

**Interfaces:**
- Consumes: Spec factors (GFLI v3.0, Embrapa, MCTI) and template headers from `full_feeds_emissions_July2024_interpolated_regional_average.csv`.
- Produces: `build_minas_gerais_eee_datasets(output_dir: Path) -> Dict[str, Path]`

- [ ] **Step 1: Implement `tools/rufas_eee_builder.py`**

Create `rufas-agentic-tooling/tools/rufas_eee_builder.py`:
```python
#!/usr/bin/env python3
"""
RuFaS EEE Dataset Builder for Brazil (Minas Gerais)
Generates canonical regionalized datasets for purchased feeds emissions,
direct Land Use Change (dLUC), local grid electricity, and international USD costs.
"""

import argparse
import csv
from pathlib import Path
from typing import Dict, List

from tools.config import get_rufas_root

# Scientific Factors (GFLI v3.0, Embrapa, MCTI)
# Format: {feed_id: (production_kg_co2e_per_kg_dm, dluc_kg_co2e_per_kg_dm)}
PRIORITY_FEED_FACTORS: Dict[str, tuple[float, float]] = {
    "23": (1.10, 0.00),    # Blood meal, low dRUP (GFLI / Ecoinvent BR)
    "44": (0.28, 0.15),    # Corn grain, ground, dry (GFLI Maize grain, at farm/BR)
    "50": (0.18, 0.00),    # Corn silage, immature (Embrapa Milho e Sorgo)
    "95": (0.22, 0.00),    # Grass hay, mature (Embrapa Pecuária Sudeste)
    "104": (0.22, 0.00),   # Grass-legume silage (Embrapa Pecuária Sudeste)
    "110": (0.20, 0.00),   # Legume forage silage (Embrapa Pecuária Sudeste)
    "170": (0.45, 1.85),   # Soybean meal, solvent extracted (GFLI BR PAS 2050 20-yr dLUC)
    "202": (0.90, 0.00),   # Whole milk (Embrapa Gado de Leite)
    "216": (0.55, 0.60),   # Calf starter 18% PB (Mass-balance: 65% corn, 30% soy, 5% min)
    "301": (0.75, 0.00),   # Farm ES Mineral Mix (Mass-balance: 45% dicalcium P, 25% salt, 20% lime)
    "302": (0.35, 0.10),   # Farm ES BP Blend (By-product blend: citrus pulp, wheat midds, corn)
}

REGIONS_TO_REGISTER: List[int] = [31, 3148004]


def get_base_feed_columns(rufas_root: Path) -> List[str]:
    """Reads all feed column headers from RuFaS default emissions file."""
    base_file = rufas_root / "input" / "data" / "EEE" / "full_feeds_emissions_July2024_interpolated_regional_average.csv"
    if not base_file.exists():
        # Fallback to priority feed columns if base file not found
        return ["region_code"] + list(PRIORITY_FEED_FACTORS.keys())

    with open(base_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    # Ensure region_code is the first column
    return ["region_code"] + [col for col in header if col not in ("county_code", "region_code")]


def build_minas_gerais_eee_datasets(output_dir: Path, rufas_root: Path | None = None) -> Dict[str, Path]:
    """
    Builds the 4 canonical EEE datasets for Minas Gerais.
    Returns dictionary mapping filename to Path.
    """
    if rufas_root is None:
        rufas_root = get_rufas_root()

    output_dir.mkdir(parents=True, exist_ok=True)
    all_columns = get_base_feed_columns(rufas_root)
    feed_columns = [col for col in all_columns if col != "region_code"]

    created_files: Dict[str, Path] = {}

    # 1. Purchased Feeds Emissions
    p1 = output_dir / "purchased_feeds_emissions_minas_gerais.csv"
    with open(p1, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        for reg in REGIONS_TO_REGISTER:
            row: Dict[str, str | float] = {"region_code": reg}
            for fid in feed_columns:
                prod_val = PRIORITY_FEED_FACTORS.get(str(fid), (0.0, 0.0))[0]
                row[fid] = prod_val
            writer.writerow(row)
    created_files[p1.name] = p1

    # 2. Purchased Feed Land Use Change Emissions (dLUC)
    p2 = output_dir / "purchased_feed_land_use_change_emissions_minas_gerais.csv"
    with open(p2, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        for reg in REGIONS_TO_REGISTER:
            row = {"region_code": reg}
            for fid in feed_columns:
                luc_val = PRIORITY_FEED_FACTORS.get(str(fid), (0.0, 0.0))[1]
                row[fid] = luc_val
            writer.writerow(row)
    created_files[p2.name] = p2

    # 3. Default Emissions (Tillage & Local Emissions)
    p3 = output_dir / "default_emissions_minas_gerais.csv"
    with open(p3, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["alfalfa_tillage_emissions", "corn_grain_tillage_emissions", "corn_silage_tillage_emissions"])
        writer.writerow([500, 300, 400])
    created_files[p3.name] = p3

    # 4. Default Costs (International USD equivalent for MG 2021-2022)
    p4 = output_dir / "default_costs_minas_gerais.csv"
    with open(p4, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["diesel_cost_gal", "electricity_cost_kwh", "natural_gas_cost_kwh", "water_cost_gal"])
        writer.writerow([4.16, 0.12, 0.053, 0.008])
    created_files[p4.name] = p4

    return created_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RuFaS EEE regional datasets for Minas Gerais, Brazil.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Destination directory for generated CSV files.",
    )
    args = parser.parse_args()

    rufas_root = get_rufas_root()
    dest_dir = args.output_dir if args.output_dir else (rufas_root / "input" / "data" / "EEE")

    print(f"🔨 Generating Minas Gerais EEE datasets into: {dest_dir}")
    files = build_minas_gerais_eee_datasets(dest_dir, rufas_root)
    for name, p in files.items():
        print(f"  ✓ Created {name} ({p.stat().st_size} bytes)")
    print("✅ All Minas Gerais EEE datasets generated successfully.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m unittest tests/test_eee_builder.py`  
Expected: PASS with 1 test passing.

- [ ] **Step 3: Commit**

```bash
git add tools/rufas_eee_builder.py
git commit -m "feat(eee): implement rufas_eee_builder tool with GFLI, Embrapa, and MCTI factors"
```

---

### Task 3: Generate Canonical Datasets in `RuFaS/input/data/EEE/`

**Files:**
- Create: `RuFaS/input/data/EEE/purchased_feeds_emissions_minas_gerais.csv`
- Create: `RuFaS/input/data/EEE/purchased_feed_land_use_change_emissions_minas_gerais.csv`
- Create: `RuFaS/input/data/EEE/default_emissions_minas_gerais.csv`
- Create: `RuFaS/input/data/EEE/default_costs_minas_gerais.csv`

- [ ] **Step 1: Execute generator CLI command**

Run: `python3 -m tools.rufas_eee_builder --output-dir ../RuFaS/input/data/EEE/`  
Expected: All 4 files created in `RuFaS/input/data/EEE/`.

- [ ] **Step 2: Verify file existence and non-empty size**

Run: `ls -la ../RuFaS/input/data/EEE/*minas_gerais.csv`  
Expected: 4 files listed with sizes > 0.

- [ ] **Step 3: Commit in RuFaS repository**

```bash
git -C ../RuFaS add input/data/EEE/*minas_gerais.csv
git -C ../RuFaS commit -m "feat(eee): add canonical Brazilian EEE datasets for Minas Gerais (GFLI/Embrapa/MCTI)"
```

---

### Task 4: Integrate Regional Blobs into `cenario_minas_gerais_metadata.json`

**Files:**
- Modify: `RuFaS/input/metadata/cenario_minas_gerais_metadata.json`
- Test: `rufas-agentic-tooling/tests/test_cenario_minas_gerais.py`

- [ ] **Step 1: Update `cenario_minas_gerais_metadata.json`**

In `RuFaS/input/metadata/cenario_minas_gerais_metadata.json`, update the 4 EEE blob paths:
- `"economy"`: `"path": "input/data/EEE/default_costs_minas_gerais.csv"`
- `"emission"`: `"path": "input/data/EEE/default_emissions_minas_gerais.csv"`
- `"purchased_feeds_emissions"`: `"path": "input/data/EEE/purchased_feeds_emissions_minas_gerais.csv"`
- `"purchased_feed_land_use_change_emissions"`: `"path": "input/data/EEE/purchased_feed_land_use_change_emissions_minas_gerais.csv"`

- [ ] **Step 2: Run inspector to verify metadata integrity**

Run: `python3 -m tools.rufas_inspector --scenario ../RuFaS/input/metadata/cenario_minas_gerais_metadata.json`  
Expected: `Inspection Result: VALID` with 0 errors.

- [ ] **Step 3: Run existing scenario unit tests**

Run: `python3 -m unittest tests/test_cenario_minas_gerais.py`  
Expected: PASS with all tests passing.

- [ ] **Step 4: Commit in RuFaS repository**

```bash
git -C ../RuFaS add input/metadata/cenario_minas_gerais_metadata.json
git -C ../RuFaS commit -m "feat(metadata): wire regional Minas Gerais EEE datasets into scenario metadata"
```

---

### Task 5: End-to-End Simulation Execution & Scope 1–3 Biophysical Verification

**Files:**
- Create: `rufas-agentic-tooling/tests/test_cenario_minas_gerais_eee.py`
- Test: Execute simulation and check `output/logs/Minas_Gerais_Pilot_warnings_*.json` and output CSV variables.

- [ ] **Step 1: Create integration test `test_cenario_minas_gerais_eee.py`**

Create `rufas-agentic-tooling/tests/test_cenario_minas_gerais_eee.py`:
```python
import json
import unittest
from pathlib import Path
import pandas as pd

from tools.config import get_rufas_root
from tools.rufas_runner import run_rufas_simulation


class TestCenarioMinasGeraisEEE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rufas_root = get_rufas_root()
        # Run simulation with clear output
        exit_code = run_rufas_simulation(
            rufas_root=cls.rufas_root,
            metadata_path="input/task_manager_minas_gerais_metadata.json",
            output_dir="output/",
            verbosity="warnings",
            no_graphics=True,
            clear_output=True,
        )
        assert exit_code == 0, "Simulation failed during EEE test execution"

    def test_zero_missing_feed_emissions_warnings(self):
        """Verify that Missing Regional Feed Emissions warnings are completely eliminated."""
        warning_files = sorted(self.rufas_root.glob("output/logs/Minas_Gerais_Pilot_warnings_*.json"))
        self.assertTrue(len(warning_files) > 0, "No warning logs found")
        latest_warning = warning_files[-1]

        with open(latest_warning, "r", encoding="utf-8") as f:
            data = json.load(f)

        missing_reg = "EmissionsEstimator._get_feed_emissions_data.Missing Regional Feed Emissions"
        missing_luc = "EmissionsEstimator.check_available_purchased_feed_data.Missing Land Use Change Purchased Feed Emissions Data"
        missing_data = "EmissionsEstimator.check_available_purchased_feed_data.Missing Purchased Feed Emissions Data"

        self.assertNotIn(missing_reg, data, "Missing Regional Feed Emissions warning still present")
        self.assertNotIn(missing_luc, data, "Missing LUC Purchased Feed Emissions warning still present")
        self.assertNotIn(missing_data, data, "Missing Purchased Feed Emissions warning still present")

    def test_purchased_feed_emissions_calculated(self):
        """Verify that purchased feed emissions are non-zero across the simulation."""
        csv_dir = self.rufas_root / "output" / "CSVs"
        csv_files = sorted(csv_dir.glob("Minas_Gerais_Pilot_saved_variables_csv_all_variables*.csv"))
        self.assertTrue(len(csv_files) > 0, "CSV output file not found")
        latest_csv = csv_files[-1]

        feed_co2_col = "EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_daily_co2e (kg)"
        feed_luc_col = "EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_daily_land_use_change_co2e (kg)"

        df = pd.read_csv(latest_csv, usecols=[feed_co2_col, feed_luc_col]).dropna()
        self.assertEqual(len(df), 730, "Expected 730 simulation days")

        total_feed_co2 = df[feed_co2_col].sum()
        total_feed_luc = df[feed_luc_col].sum()

        self.assertGreater(total_feed_co2, 0.0, "Total purchased feed CO2e is zero")
        self.assertGreater(total_feed_luc, 0.0, "Total purchased feed LUC CO2e is zero")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to execute simulation and verify EEE calculations**

Run: `python3 -m unittest tests/test_cenario_minas_gerais_eee.py`  
Expected: PASS with 0 warnings of missing feed emissions and positive Scope 3 emissions verified.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cenario_minas_gerais_eee.py
git commit -m "test(eee): verify zero missing feed warnings and positive Scope 3 GHG calculations in pilot scenario"
```

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tools.config import get_rufas_root


class TestCenarioMinasGerais(unittest.TestCase):
    def setUp(self):
        self.rufas_root = get_rufas_root()
        self.project_root = Path(__file__).resolve().parent.parent

    def test_config_minas_gerais(self):
        config_path = self.rufas_root / "input" / "data" / "config" / "config_minas_gerais.json"
        self.assertTrue(config_path.exists(), f"Missing {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("country"), "BRA")
        self.assertEqual(cfg.get("region_code"), 3148004)
        self.assertEqual(cfg.get("start_date"), "2021:1")
        self.assertEqual(cfg.get("end_date"), "2022:365")
        self.assertEqual(cfg.get("set_seed"), True)
        self.assertEqual(cfg.get("simulation_type"), "full_farm")
        self.assertEqual(cfg.get("nutrient_standard"), "NASEM")
        self.assertEqual(cfg.get("include_detailed_values"), False)

    def test_soil_minas_gerais(self):
        soil_path = self.rufas_root / "input" / "data" / "soil" / "soil_minas_gerais.json"
        self.assertTrue(soil_path.exists(), f"Missing {soil_path}")
        with open(soil_path, "r", encoding="utf-8") as f:
            soil = json.load(f)

        # Profile-level validation
        self.assertEqual(soil.get("second_moisture_condition_parameter"), 68.0)
        self.assertEqual(soil.get("average_subbasin_slope"), 0.025)
        self.assertEqual(soil.get("slope_length"), 30.0)
        self.assertEqual(soil.get("manning_roughness_coefficient"), 0.35)
        self.assertEqual(soil.get("albedo"), 0.14)
        self.assertEqual(soil.get("soil_evaporation_compensation_coefficient"), 0.95)
        self.assertEqual(soil.get("initial_residue"), 500.0)

        # Layers validation
        layers = soil.get("soil_layers")
        self.assertIsInstance(layers, list)
        self.assertEqual(len(layers), 4)

        # RuFaS SurPhos requirement: top layer must be 0-20 mm
        self.assertEqual(layers[0].get("bottom_depth"), 20)
        depths = [layer["bottom_depth"] for layer in layers]
        self.assertEqual(depths, [20, 200, 600, 1500])

        # Physical and hydraulic validation across all layers
        for idx, layer in enumerate(layers):
            # Hydraulic constraints
            self.assertLessEqual(
                layer["wilting_point_water_concentration"],
                layer["field_capacity_water_concentration"],
                f"Layer {idx}: wilting point > field capacity",
            )
            self.assertLessEqual(
                layer["field_capacity_water_concentration"],
                layer["saturation_point_water_concentration"],
                f"Layer {idx}: field capacity > saturation point",
            )
            self.assertGreaterEqual(
                layer["soil_water_concentration"],
                layer["wilting_point_water_concentration"],
                f"Layer {idx}: soil water < wilting point",
            )
            self.assertLessEqual(
                layer["soil_water_concentration"],
                layer["saturation_point_water_concentration"],
                f"Layer {idx}: soil water > saturation point",
            )

            # Soil texture fractions sum to 1.0 (Latossolo Vermelho)
            texture_sum = (
                layer["clay_fraction"]
                + layer["silt_fraction"]
                + layer["sand_fraction"]
                + layer["rock_fraction"]
            )
            self.assertAlmostEqual(texture_sum, 1.0, places=4, msg=f"Layer {idx}: texture fractions do not sum to 1.0")

            # Latossolo Vermelho clayey profile (clay >= 50%)
            self.assertGreaterEqual(layer["clay_fraction"], 0.50, f"Layer {idx}: clay fraction < 0.50")
            self.assertEqual(layer["rock_fraction"], 0.0, f"Layer {idx}: rock fraction should be 0.0")

            # Bulk density typical for oxisols
            self.assertGreater(layer["bulk_density"], 0.9, f"Layer {idx}: bulk density too low")
            self.assertLess(layer["bulk_density"], 1.3, f"Layer {idx}: bulk density too high")

            # High drainage / conductivity
            self.assertGreaterEqual(layer["saturated_hydraulic_conductivity"], 30.0)

            # Acidic pH
            self.assertGreaterEqual(layer["pH"], 5.0)
            self.assertLessEqual(layer["pH"], 6.5)

        # Depth gradients
        # Organic carbon decreases with depth
        oc_values = [layer["organic_carbon_fraction"] for layer in layers]
        self.assertEqual(oc_values, sorted(oc_values, reverse=True))

        # Labile phosphorus decreases with depth
        p_values = [layer["initial_labile_inorganic_phosphorus_concentration"] for layer in layers]
        self.assertEqual(p_values, sorted(p_values, reverse=True))

    def test_field_minas_gerais(self):
        field_path = self.rufas_root / "input" / "data" / "field" / "field_minas_gerais.json"
        self.assertTrue(field_path.exists(), f"Missing {field_path}")
        with open(field_path, "r", encoding="utf-8") as f:
            field = json.load(f)

        self.assertEqual(field.get("soil_specification"), "soil_minas_gerais")
        self.assertEqual(field.get("crop_specification"), "Corn-Silage-MG")
        self.assertEqual(field.get("fertilizer_management_specification"), "fertilizer_schedule_minas_gerais")
        self.assertEqual(field.get("manure_management_specification"), "manure_schedule_minas_gerais")
        self.assertEqual(field.get("tillage_management_specification"), "tillage_schedule_minas_gerais")
        self.assertEqual(field.get("field_size"), 20.0)
        self.assertEqual(field.get("latitude"), -18.5789)
        self.assertEqual(field.get("longitude"), -46.5181)
        self.assertEqual(field.get("minimum_daylength"), 10.8)
        self.assertEqual(field.get("seasonal_high_water_table"), False)
        self.assertEqual(field.get("watering_amount_in_liters"), 0.0)
        self.assertEqual(field.get("watering_interval"), 0)
        self.assertEqual(field.get("simulate_water_stress"), True)
        self.assertEqual(field.get("simulate_temp_stress"), True)
        self.assertEqual(field.get("simulate_nitrogen_stress"), True)
        self.assertEqual(field.get("simulate_phosphorus_stress"), True)
        self.assertEqual(field.get("tractor_size"), "medium")

    def test_scenario_metadata_validation(self):
        from tools.rufas_inspector import inspect_scenario_metadata

        scenario_meta = self.rufas_root / "input" / "metadata" / "cenario_minas_gerais_metadata.json"
        self.assertTrue(scenario_meta.exists(), f"Missing {scenario_meta}")

        valid, errors, warnings = inspect_scenario_metadata(scenario_meta, self.rufas_root)
        self.assertTrue(valid, f"Scenario validation failed: {errors}")
        self.assertEqual(len(errors), 0)

    def test_task_manager_validation(self):
        from tools.rufas_inspector import inspect_task_metadata

        tm_meta = self.rufas_root / "input" / "task_manager_minas_gerais_metadata.json"
        self.assertTrue(tm_meta.exists(), f"Missing {tm_meta}")

        task_path = self.rufas_root / "input" / "data" / "tasks" / "task_minas_gerais.json"
        self.assertTrue(task_path.exists(), f"Missing {task_path}")

        valid_tm, tm_errors, tm_warnings = inspect_task_metadata(tm_meta, self.rufas_root)
        self.assertTrue(valid_tm, f"Task manager validation failed: {tm_errors}")
        self.assertEqual(len(tm_errors), 0)

    def test_cli_inspector_scenario(self):
        scenario_arg = "../RuFaS/input/metadata/cenario_minas_gerais_metadata.json"
        cmd = [
            sys.executable,
            "-m",
            "tools.rufas_inspector",
            "--scenario",
            scenario_arg,
        ]
        env = {**os.environ, "PYTHONPATH": str(self.project_root)}
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"rufas_inspector CLI scenario invocation failed (code {result.returncode}):\n{result.stderr}\n{result.stdout}",
        )
        self.assertIn("PASSED", result.stdout)

    def test_cli_inspector_task_metadata(self):
        task_meta_arg = "../RuFaS/input/task_manager_minas_gerais_metadata.json"
        cmd = [
            sys.executable,
            "-m",
            "tools.rufas_inspector",
            "--task-metadata",
            task_meta_arg,
        ]
        env = {**os.environ, "PYTHONPATH": str(self.project_root)}
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"rufas_inspector CLI task metadata invocation failed (code {result.returncode}):\n{result.stderr}\n{result.stdout}",
        )
        self.assertIn("PASSED", result.stdout)

    def test_simulation_execution_and_biophysical_outputs(self):
        """
        Verifies end-to-end simulation execution for the Minas Gerais pilot scenario,
        including 730 simulated days, zero errors, Southern Hemisphere photoperiod
        seasonality, and hydraulic stability of the Latossolo Vermelho soil profile.
        """
        csv_dir = self.rufas_root / "output" / "CSVs"
        csv_files = sorted(csv_dir.glob("Minas_Gerais_Pilot_saved_variables_csv_all_variables*.csv"))

        if not csv_files:
            from tools.rufas_runner import run_rufas_simulation

            exit_code = run_rufas_simulation(
                rufas_root=self.rufas_root,
                metadata_path="input/task_manager_minas_gerais_metadata.json",
                output_dir="output/",
                verbosity="warnings",
                no_graphics=True,
            )
            self.assertEqual(exit_code, 0, "Simulation failed during test execution")
            csv_files = sorted(csv_dir.glob("Minas_Gerais_Pilot_saved_variables_csv_all_variables*.csv"))

        self.assertTrue(len(csv_files) > 0, "Output CSV not found in output/CSVs")
        latest_csv = csv_files[-1]

        # 1. Verify Error Logs
        errors_txt = self.rufas_root / "output" / "logs" / "errors.txt"
        if errors_txt.exists():
            self.assertEqual(errors_txt.stat().st_size, 0, f"errors.txt is not empty: {errors_txt.read_text()}")

        error_jsons = sorted(self.rufas_root.glob("output/logs/Minas_Gerais_Pilot_errors_*.json"))
        if error_jsons:
            with open(error_jsons[-1], "r", encoding="utf-8") as f:
                err_data = json.load(f)
            err_keys = [k for k in err_data.keys() if k != "DISCLAIMER"]
            self.assertEqual(len(err_keys), 0, f"Errors found in simulation logs: {err_keys}")

        # 2. Verify Output Variables
        import csv
        from datetime import date, timedelta

        daylength_col = "FieldManager.daily_update_routine.daylength.field='field_1' (hour)"
        w_cols = [
            f"FieldDataReporter.send_soil_layer_daily_variables.water_content.field='field_1',layer='{i}' (mm)"
            for i in range(4)
        ]

        with open(latest_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if r.get(daylength_col) is not None and r.get(daylength_col) != ""]

        self.assertEqual(len(rows), 730, f"Expected 730 simulation days across 2021-2022, got {len(rows)}")

        # 3. Verify Southern Hemisphere Photoperiod Seasonality (Patos de Minas: lat -18.5789)
        daylengths = [float(r[daylength_col]) for r in rows]
        min_dl = min(daylengths)
        max_dl = max(daylengths)

        self.assertGreater(max_dl, 13.0, f"Max day length should exceed 13.0h in Dec/Jan, got {max_dl}")
        self.assertLess(max_dl, 13.3, f"Max day length should be <= 13.3h, got {max_dl}")
        self.assertGreaterEqual(min_dl, 10.7, f"Min day length should be >= 10.7h, got {min_dl}")
        self.assertLessEqual(min_dl, 11.0, f"Min day length should be ~10.8h in Jun/Jul, got {min_dl}")

        # Seasonal alignment: Dec/Jan (summer) > Jun/Jul (winter)
        start_dt = date(2021, 1, 1)
        summer_vals = []
        winter_vals = []
        for idx, r in enumerate(rows):
            cur_dt = start_dt + timedelta(days=idx)
            dl = float(r[daylength_col])
            if cur_dt.month in (12, 1):
                summer_vals.append(dl)
            elif cur_dt.month in (6, 7):
                winter_vals.append(dl)

        summer_dl = sum(summer_vals) / len(summer_vals)
        winter_dl = sum(winter_vals) / len(winter_vals)
        self.assertGreater(
            summer_dl,
            winter_dl + 1.5,
            f"Southern Hemisphere summer day length ({summer_dl:.2f}h) must exceed winter ({winter_dl:.2f}h) by > 1.5h",
        )

        # 4. Verify Soil Water Balance Stability in Latossolo Profile
        soil_path = self.rufas_root / "input" / "data" / "soil" / "soil_minas_gerais.json"
        with open(soil_path, "r", encoding="utf-8") as f:
            soil_cfg = json.load(f)
        layers = soil_cfg["soil_layers"]
        thicknesses = [
            layers[0]["bottom_depth"],
            layers[1]["bottom_depth"] - layers[0]["bottom_depth"],
            layers[2]["bottom_depth"] - layers[1]["bottom_depth"],
            layers[3]["bottom_depth"] - layers[2]["bottom_depth"],
        ]

        eps = 1e-4
        for i in range(4):
            thick = thicknesses[i]
            wp = layers[i]["wilting_point_water_concentration"]
            sat = layers[i]["saturation_point_water_concentration"]

            for r in rows:
                val_str = r[w_cols[i]]
                self.assertIsNotNone(val_str, f"Layer {i} contains None water content")
                theta = float(val_str) / thick
                self.assertGreaterEqual(
                    theta,
                    wp - eps,
                    f"Layer {i} water content dropped below wilting point ({wp}): {theta}",
                )
                self.assertLessEqual(
                    theta,
                    sat + eps,
                    f"Layer {i} water content exceeded saturation ({sat}): {theta}",
                )


if __name__ == "__main__":
    unittest.main()




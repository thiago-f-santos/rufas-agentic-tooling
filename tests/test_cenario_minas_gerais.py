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


if __name__ == "__main__":
    unittest.main()


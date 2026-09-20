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


if __name__ == "__main__":
    unittest.main()

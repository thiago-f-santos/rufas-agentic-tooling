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
                self.assertIn("county_code", reader.fieldnames)
                # Verify priority feed IDs exist as columns
                for fid in ["23", "44", "50", "95", "104", "110", "170", "202", "216", "301", "302"]:
                    self.assertIn(fid, reader.fieldnames)

                rows = list(reader)
                self.assertGreaterEqual(len(rows), 1)
                regions = [r["county_code"] for r in rows]
                self.assertIn("3148004", regions)

                # Check specific GFLI values
                row_mg = next(r for r in rows if r["county_code"] == "3148004")
                self.assertAlmostEqual(float(row_mg["44"]), 0.28, places=2)
                self.assertAlmostEqual(float(row_mg["170"]), 0.45, places=2)

            # Check LUC CSV format
            luc_csv = out_dir / "purchased_feed_land_use_change_emissions_minas_gerais.csv"
            with open(luc_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertIn("county_code", reader.fieldnames)
                rows = list(reader)
                row_mg = next(r for r in rows if r["county_code"] == "3148004")
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

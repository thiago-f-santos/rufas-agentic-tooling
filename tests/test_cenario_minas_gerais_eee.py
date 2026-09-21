import csv
import json
import unittest
from pathlib import Path

from tools.config import get_rufas_root
from tools.rufas_runner import run_rufas_simulation


class TestCenarioMinasGeraisEEE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rufas_root = get_rufas_root()
        # Run simulation to generate fresh logs with the new regional EEE tables
        exit_code = run_rufas_simulation(
            rufas_root=cls.rufas_root,
            metadata_path="input/task_manager_minas_gerais_metadata.json",
            output_dir="output/",
            verbosity="warnings",
            no_graphics=True,
            clear_output=False,
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
        """Verify that purchased feed emissions and dLUC are non-zero across the simulation."""
        csv_dir = self.rufas_root / "output" / "CSVs"
        csv_files = sorted(csv_dir.glob("Minas_Gerais_Pilot_saved_variables_csv_all_variables*.csv"))
        self.assertTrue(len(csv_files) > 0, "CSV output file not found")
        latest_csv = csv_files[-1]

        priority_feeds = ["23", "44", "50", "95", "104", "110", "202", "216", "301", "302"]
        prefix_feed = "EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions."
        prefix_luc = "EmissionsEstimator.calculate_purchased_feed_emissions.land_use_change_emissions."

        with open(latest_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

            feed_indices = {fid: header.index(f"{prefix_feed}{fid} (kg CO2 / kg DM)") for fid in priority_feeds}
            luc_indices = {fid: header.index(f"{prefix_luc}{fid} (kg CO2 / kg DM)") for fid in priority_feeds}

            feed_totals = {fid: 0.0 for fid in priority_feeds}
            luc_totals = {fid: 0.0 for fid in priority_feeds}
            day_count = 0

            for row in reader:
                first_idx = feed_indices["44"]
                if row[first_idx] != "":
                    day_count += 1
                    for fid in priority_feeds:
                        feed_totals[fid] += float(row[feed_indices[fid]])
                        luc_totals[fid] += float(row[luc_indices[fid]])

        self.assertEqual(day_count, 730, "Expected 730 simulation days with feed emission data")

        # Verify positive emissions for all priority feeds
        for fid in priority_feeds:
            self.assertGreater(feed_totals[fid], 0.0, f"Purchased feed {fid} CO2e is zero")

        # Verify positive dLUC for feeds with land use change (corn, starter, by-product blend)
        self.assertGreater(luc_totals["44"], 0.0, "Corn grain (44) LUC CO2e is zero")
        self.assertGreater(luc_totals["216"], 0.0, "Calf starter (216) LUC CO2e is zero")
        self.assertGreater(luc_totals["302"], 0.0, "BP blend (302) LUC CO2e is zero")

        total_feed_co2 = sum(feed_totals.values())
        total_luc_co2 = sum(luc_totals.values())
        self.assertGreater(total_feed_co2, 500_000.0, "Total purchased feed CO2e unexpectedly low")
        self.assertGreater(total_luc_co2, 50_000.0, "Total purchased feed LUC CO2e unexpectedly low")


if __name__ == "__main__":
    unittest.main()

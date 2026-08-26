#!/usr/bin/env python3
"""
Unit and integration tests for RuFaS Agentic Tooling suite.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.rufas_inspector import (
    REQUIRED_FILE_BLOBS,
    inspect_scenario_metadata,
    inspect_task_metadata,
)
from tools.rufas_analyzer import (
    categorize_variable_name,
    extract_variable_unit,
    summarize_modular_variables,
    summarize_output_directory,
)


class TestRuFaSTooling(unittest.TestCase):
    def setUp(self) -> None:
        self.rufas_root = (PROJECT_ROOT.parent / "RuFaS").resolve()

    def test_required_blobs_count(self) -> None:
        """Verify all 22 required file blobs are tracked."""
        self.assertEqual(len(REQUIRED_FILE_BLOBS), 22)
        self.assertIn("animal", REQUIRED_FILE_BLOBS)
        self.assertIn("purchased_feed_land_use_change_emissions", REQUIRED_FILE_BLOBS)
        self.assertIn("weather", REQUIRED_FILE_BLOBS)

    def test_inspector_against_default_rufas_task_metadata(self) -> None:
        """Test inspector against the standard RuFaS task manager metadata."""
        if not self.rufas_root.exists():
            self.skipTest(f"RuFaS repo not found at {self.rufas_root}")

        default_task_meta = self.rufas_root / "input" / "task_manager_metadata.json"
        self.assertTrue(default_task_meta.exists())

        valid, errors, warnings = inspect_task_metadata(default_task_meta, self.rufas_root)
        self.assertTrue(valid, f"Task metadata failed validation with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_inspector_against_example_freestall_scenario(self) -> None:
        """Test inspector against the example freestall scenario metadata."""
        if not self.rufas_root.exists():
            self.skipTest(f"RuFaS repo not found at {self.rufas_root}")

        scenario_path = (
            self.rufas_root / "input" / "metadata" / "example_freestall_dairy_metadata.json"
        )
        self.assertTrue(scenario_path.exists())

        valid, errors, warnings = inspect_scenario_metadata(scenario_path, self.rufas_root)
        self.assertTrue(valid, f"Scenario metadata failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_analyzer_handles_empty_or_nonexistent_directory(self) -> None:
        """Verify analyzer handles non-existent or empty directories gracefully."""
        non_existent = PROJECT_ROOT / "temp_non_existent"
        summary = summarize_output_directory(non_existent)
        self.assertTrue(summary["errors_detected"])
        self.assertEqual(len(summary["csv_files_found"]), 0)

    def test_all_skills_sdo_compliance(self) -> None:
        """Verify all 6 RuFaS specialist skills meet strict SDO and frontmatter rules."""
        skills_dir = PROJECT_ROOT / "skills"
        self.assertTrue(skills_dir.exists())

        expected_skills = [
            "rufas-specialist",
            "rufas-animal-specialist",
            "rufas-field-soil-specialist",
            "rufas-feed-storage-specialist",
            "rufas-manure-specialist",
            "rufas-eee-specialist",
        ]

        for skill_name in expected_skills:
            skill_path = skills_dir / skill_name / "SKILL.md"
            self.assertTrue(skill_path.exists(), f"Missing SKILL.md for {skill_name}")

            content = skill_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"{skill_name} missing YAML frontmatter start")
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{skill_name} invalid frontmatter structure")

            frontmatter = parts[1]
            self.assertIn(f"name: {skill_name}", frontmatter, f"{skill_name} frontmatter name mismatch")
            self.assertIn("description:", frontmatter, f"{skill_name} missing description")

            desc_lines = [line for line in frontmatter.splitlines() if line.strip().startswith("description:")]
            self.assertTrue(len(desc_lines) > 0, f"{skill_name} missing description line")
            desc_text = desc_lines[0].replace("description:", "").strip()
            self.assertTrue(
                desc_text.startswith("Use when"),
                f"{skill_name} description must start with 'Use when...', got: {desc_text[:30]}",
            )
            self.assertLessEqual(len(desc_text), 500, f"{skill_name} description exceeds 500 chars")

    def test_rufas_analyzer_modular_categorization(self) -> None:
        """Verify variable column names are categorized into correct biophysical/economic modules."""
        self.assertEqual(
            categorize_variable_name(
                "AnimalModuleReporter.report_animal_population_statistics.population_number_of_cows (animals)"
            ),
            "animal",
        )
        self.assertEqual(
            categorize_variable_name(
                "FieldDataReporter.send_soil_daily_variables.water_evaporated.field='field_1' (mm)"
            ),
            "field_soil",
        )
        self.assertEqual(
            categorize_variable_name("FeedManager.purchase_feed.ration_interval_202_cost ($)"),
            "feed_storage",
        )
        self.assertEqual(
            categorize_variable_name(
                "Manure.SingleStreamHandler.AlleyScraper.lac_alley_scraper.housing_CO2_emissions (kg)"
            ),
            "manure",
        )
        self.assertEqual(
            categorize_variable_name(
                "EmissionsEstimator.calculate_purchased_feed_emissions.purchased_feed_emissions.44 (kg CO2 / kg DM)"
            ),
            "eee",
        )
        self.assertEqual(
            categorize_variable_name("Weather.precipitation (mm)"),
            "general",
        )

    def test_rufas_analyzer_extract_unit(self) -> None:
        """Verify extraction of unit from column names in trailing parentheses."""
        self.assertEqual(extract_variable_unit("Weather.irrigation (mm)"), "mm")
        self.assertEqual(extract_variable_unit("FeedManager.cost ($)"), "$")
        self.assertEqual(
            extract_variable_unit(
                "EmissionsEstimator.calculate_purchased_feed_emissions.44 (kg CO2 / kg DM)"
            ),
            "kg CO2 / kg DM",
        )
        self.assertIsNone(extract_variable_unit("DISCLAIMER"))

    def test_rufas_analyzer_modular_summary(self) -> None:
        """Verify summarize_modular_variables and summarize_output_directory per-module parsing."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "AnimalModuleReporter.cows (animals)": [100.0, 110.0, 120.0],
                "FieldDataReporter.drainage (mm)": [5.0, 10.0, 15.0],
                "FeedManager.feed_cost ($)": [200.0, 250.0, 300.0],
                "Manure.housing_CO2_emissions (kg)": [10.0, 20.0, 30.0],
                "EmissionsEstimator.purchased_feed_emissions (kg CO2 / kg DM)": [1.5, 2.0, 2.5],
                "Weather.precipitation (mm)": [0.0, 5.0, 2.0],
            }
        )

        mod_summary = summarize_modular_variables(df)
        self.assertEqual(mod_summary["total_variables"], 6)
        self.assertEqual(mod_summary["modules"]["animal"]["total_variables"], 1)
        self.assertEqual(mod_summary["modules"]["field_soil"]["total_variables"], 1)
        self.assertEqual(mod_summary["modules"]["feed_storage"]["total_variables"], 1)
        self.assertEqual(mod_summary["modules"]["manure"]["total_variables"], 1)
        self.assertEqual(mod_summary["modules"]["eee"]["total_variables"], 1)
        self.assertEqual(mod_summary["modules"]["general"]["total_variables"], 1)

        animal_var = mod_summary["modules"]["animal"]["variables"][0]
        self.assertEqual(animal_var["name"], "AnimalModuleReporter.cows (animals)")
        self.assertEqual(animal_var["unit"], "animals")
        self.assertEqual(animal_var["mean"], 110.0)
        self.assertEqual(animal_var["min"], 100.0)
        self.assertEqual(animal_var["max"], 120.0)
        self.assertEqual(animal_var["non_null_count"], 3)

    def test_rufas_analyzer_on_rufas_output_dir(self) -> None:
        """Verify summarize_output_directory extracts modular statistics on simulation output directory."""
        output_dir = self.rufas_root / "output"
        if not output_dir.exists():
            self.skipTest(f"RuFaS output directory not found at {output_dir}")

        summary = summarize_output_directory(output_dir)
        self.assertFalse(summary["errors_detected"])
        if summary["csv_files_found"]:
            self.assertIn("modular_summary", summary)
            mod_summary = summary["modular_summary"]
            self.assertGreater(mod_summary["total_variables"], 0)
            self.assertIn("animal", mod_summary["modules"])
            self.assertIn("field_soil", mod_summary["modules"])
            self.assertIn("feed_storage", mod_summary["modules"])
            self.assertIn("manure", mod_summary["modules"])
            self.assertIn("eee", mod_summary["modules"])


if __name__ == "__main__":
    unittest.main()



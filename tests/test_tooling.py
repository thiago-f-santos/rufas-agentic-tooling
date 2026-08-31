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
        """Verify all 7 RuFaS specialist skills meet strict SDO and frontmatter rules."""
        skills_dir = PROJECT_ROOT / "skills"
        self.assertTrue(skills_dir.exists())

        expected_skills = [
            "rufas-specialist",
            "rufas-animal-specialist",
            "rufas-field-soil-specialist",
            "rufas-feed-storage-specialist",
            "rufas-manure-specialist",
            "rufas-eee-specialist",
            "rufas-brain-specialist",
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
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed in this environment")

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

    def test_animal_specialist_output_docs(self) -> None:
        """Verify animal specialist skill documentation contains tiered architecture, formulas, anchor metrics, and graph discovery."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-animal-specialist" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        self.assertIn("Wood", content)
        self.assertIn("Linear Programming", content)
        self.assertTrue("DMI" in content or "Dry Matter Intake" in content)
        self.assertTrue("methane" in content.lower())
        self.assertIn("rufas_brain", content)
        self.assertIn("lookup-var", content)

    def test_field_soil_specialist_output_docs(self) -> None:
        """Verify field & soil specialist skill documentation contains tiered architecture, hydrology, C/N biophysics, anchor metrics, and graph discovery."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-field-soil-specialist" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue("Darcy" in content or "Richards" in content or "hydrology" in content.lower())
        self.assertTrue("Century" in content or "mineralization" in content.lower())
        self.assertTrue("N2O" in content or "nitrate" in content.lower())
        self.assertIn("rufas_brain", content)
        self.assertIn("lookup-var", content)

    def test_feed_storage_specialist_output_docs(self) -> None:
        """Verify feed storage specialist skill documentation contains tiered architecture, spoilage kinetics, anchor metrics, and graph discovery."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-feed-storage-specialist" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue("bunker" in content.lower() or "silo" in content.lower())
        self.assertTrue("spoilage" in content.lower() or "shrinkage" in content.lower())
        self.assertIn("rufas_brain", content)
        self.assertIn("lookup-var", content)

    def test_manure_specialist_output_docs(self) -> None:
        """Verify manure specialist skill documentation contains tiered architecture, separation, digestion, anchor metrics, and graph discovery."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-manure-specialist" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue("separator" in content.lower() or "separation" in content.lower())
        self.assertTrue("digester" in content.lower() or "anaerobic" in content.lower() or "methane" in content.lower())
        self.assertIn("rufas_brain", content)
        self.assertIn("lookup-var", content)

    def test_eee_specialist_output_docs(self) -> None:
        """Verify EEE specialist skill documentation contains tiered architecture, LCA formulas, carbon intensity, anchor metrics, and graph discovery."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-eee-specialist" / "SKILL.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue("GWP" in content or "FPCM" in content or "Scope" in content)
        self.assertTrue("carbon_intensity" in content or "carbon intensity" in content.lower())
        self.assertIn("rufas_brain", content)
        self.assertIn("lookup-var", content)

    def test_master_rufas_specialist_output_docs(self) -> None:
        """Verify master rufas specialist skill and reference guides contain full output hierarchy and diagnostics."""
        skill_path = PROJECT_ROOT / "skills" / "rufas-specialist" / "SKILL.md"
        ref_path = PROJECT_ROOT / "skills" / "rufas-specialist" / "references" / "output-and-diagnostics.md"
        self.assertTrue(skill_path.exists())
        self.assertTrue(ref_path.exists())

        skill_content = skill_path.read_text(encoding="utf-8")
        ref_content = ref_path.read_text(encoding="utf-8")

        # Master skill assertions
        self.assertTrue("2,038" in skill_content or "2,000+" in skill_content)
        self.assertIn("AnimalModuleReporter", skill_content)
        self.assertIn("FieldDataReporter", skill_content)
        self.assertIn("variables_pool", skill_content)
        self.assertIn("csv_all_variables.txt", skill_content)

        # Reference guide assertions
        self.assertIn("Data Pool Variable Hierarchy", ref_content)
        self.assertIn("variables_pool", ref_content)
        self.assertIn("logs_pool", ref_content)
        self.assertIn("warnings_pool", ref_content)
        self.assertIn("errors_pool", ref_content)
        self.assertIn("chunkification", ref_content)
        self.assertIn("csv_all_variables.txt", ref_content)
        self.assertIn("865", ref_content)
        self.assertIn("744", ref_content)
        self.assertIn("264", ref_content)
        self.assertIn("134", ref_content)

    def test_brain_specialist_skill_exists_and_valid(self) -> None:
        """Verify rufas-brain-specialist skill exists and contains required graph and Cypher references."""
        skill_file = PROJECT_ROOT / "skills" / "rufas-brain-specialist" / "SKILL.md"
        self.assertTrue(skill_file.exists())
        content = skill_file.read_text(encoding="utf-8")
        self.assertIn("rufas-brain-specialist", content)
        self.assertTrue("KùzuDB" in content or "OpenCypher" in content)
        self.assertIn("CAUSALLY_INFLUENCES", content)
        self.assertIn("CORRELATES_WITH", content)
        self.assertIn("rufas-brain", content)

    def test_all_skills_complete_and_valid(self) -> None:
        """Verify all 7 modular skills have valid YAML frontmatter, description, and tiered discovery documentation."""
        expected_skills = [
            "rufas-specialist",
            "rufas-animal-specialist",
            "rufas-field-soil-specialist",
            "rufas-feed-storage-specialist",
            "rufas-manure-specialist",
            "rufas-eee-specialist",
            "rufas-brain-specialist",
        ]
        skills_dir = PROJECT_ROOT / "skills"
        for skill_name in expected_skills:
            skill_file = skills_dir / skill_name / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"Missing {skill_file}")
            content = skill_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"Missing frontmatter in {skill_file}")
            self.assertTrue(
                "Dynamic Graph Brain Querying" in content or "Graph Memory Brain" in content or skill_name == "rufas-specialist",
                f"Missing Graph Brain Querying section in {skill_file}",
            )
            # Frontmatter validation
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{skill_name} invalid frontmatter structure")
            frontmatter = parts[1]
            self.assertIn(f"name: {skill_name}", frontmatter, f"{skill_name} frontmatter name mismatch")
            self.assertIn("description:", frontmatter, f"{skill_name} missing description")

    def test_install_skills_dry_run(self) -> None:
        """Verify install_skills dry run validates all 7 skills without modifying target directory."""
        import tempfile
        from tools.install_skills import SKILLS, install_skills

        skills_dir = PROJECT_ROOT / "skills"
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "test_target"
            count = install_skills(skills_dir, target_dir, dry_run=True)
            self.assertEqual(count, len(SKILLS))
            self.assertEqual(count, 7)
            self.assertFalse(target_dir.exists())


    def test_obsidian_producer_documentation(self) -> None:
        """Verify obsidian producer reference guide exists and contains setup and workflow instructions."""
        ref_file = (
            PROJECT_ROOT
            / "skills"
            / "rufas-brain-specialist"
            / "references"
            / "obsidian-knowledge-graph.md"
        )
        self.assertTrue(ref_file.exists(), "Missing obsidian-knowledge-graph.md reference guide")
        content = ref_file.read_text(encoding="utf-8")
        self.assertIn("Obsidian Knowledge Graph Production Guide", content)
        self.assertIn("rufas-brain export-obsidian", content)
        self.assertIn("Dataview", content)
        self.assertIn("Graph View", content)
        self.assertIn("Canvas", content)


if __name__ == "__main__":
    unittest.main()





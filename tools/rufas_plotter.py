#!/usr/bin/env python3
"""
RuFaS Simulation Visualization and Plotting Tool (`rufas-plot`)
Provides executive (Whole-Farm 360°) and modular diagnostic visualization
for RuFaS simulation outputs with ragged time-series alignment, selective
column reading, and scenario comparisons.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from tools.config import (
    RuFaSBoundaryError,
    RuFaSConfigError,
    assert_within_rufas_scope,
    get_rufas_root,
)


def extract_variable_unit(col_name: str) -> Optional[str]:
    """Extracts unit from variable name if present in trailing parentheses, e.g. 'foo (kg)' -> 'kg'."""
    match = re.search(r"\(([^()]+)\)\s*$", col_name)
    return match.group(1).strip() if match else None


# Canonical preset definitions mapping preset keys to panel resolution rules
PRESET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "executive": {
        "title": "Whole-Farm 360° Executive Dashboard",
        "description": "Integrated 6-panel overview of production, herd, emissions, manure, feed, and soil water.",
        "panels": {
            "milk_produced": {
                "title": "Milk Production",
                "unit": "kg/day",
                "patterns": [
                    r"report_milk\.milk_data_at_milk_update\.estimated_daily_milk_produced",
                    r"estimated_daily_milk_produced",
                    r"daily_milk_produced",
                ],
                "time_pattern": r"report_milk\.milk_data_at_milk_update\.simulation_day",
                "entity_pattern": r"report_milk\.milk_data_at_milk_update\.cow_id",
                "aggregation": "sum",
            },
            "herd_dynamics": {
                "title": "Herd Dynamics",
                "unit": "animals",
                "patterns": [
                    r"report_animal_population_statistics\.population_number_of_cows",
                    r"population_number_of_cows",
                    r"number_of_cows",
                ],
                "aggregation": "last",
            },
            "methane_emission": {
                "title": "Enteric Methane Emission",
                "unit": "g",
                "patterns": [
                    r"report_enteric_methane_emission\.enteric_methane_emission_for_.*",
                    r"report_enteric_methane_emission.*",
                    r"enteric_methane_emission.*",
                ],
                "aggregation": "sum",
            },
            "manure_excretion": {
                "title": "Manure Excretion",
                "unit": "kg",
                "patterns": [
                    r"report_manure_excretions\..*_manure_mass",
                    r"report_manure_excretions.*",
                    r".*_manure_mass",
                ],
                "aggregation": "sum",
            },
            "feed_cost": {
                "title": "Feed Cost",
                "unit": "$",
                "patterns": [
                    r"FeedManager\.purchase_feed\..*_cost",
                    r"purchase_feed.*cost",
                    r".*_cost\s*\(\$\)",
                ],
                "aggregation": "sum",
            },
            "transpiration": {
                "title": "Field Transpiration",
                "unit": "mm",
                "patterns": [
                    r"FieldDataReporter\.send_field_daily_variables\.transpiration.*",
                    r"send_field_daily_variables\.transpiration",
                    r"cumulative_transpiration",
                    r"transpiration",
                ],
                "aggregation": "mean",
            },
        },
    },
    "animal": {
        "title": "Animal & Herd Diagnostics",
        "description": "Lactation performance, solids, DIM, and herd demographics.",
        "panels": {
            "milk_produced": {
                "title": "Milk Production",
                "unit": "kg/day",
                "patterns": [
                    r"report_milk\.milk_data_at_milk_update\.estimated_daily_milk_produced",
                    r"estimated_daily_milk_produced",
                ],
                "time_pattern": r"report_milk\.milk_data_at_milk_update\.simulation_day",
                "entity_pattern": r"report_milk\.milk_data_at_milk_update\.cow_id",
                "aggregation": "sum",
            },
            "milk_solids": {
                "title": "Milk Solids Yield",
                "unit": "kg/day",
                "patterns": [
                    r"report_milk.*solid",
                    r"report_milk.*fat",
                    r"report_milk.*protein",
                ],
                "aggregation": "sum",
            },
            "days_in_milk": {
                "title": "Days in Milk (DIM)",
                "unit": "day",
                "patterns": [
                    r"population_average_cow_days_in_milk",
                    r"initial_average_cow_days_in_milk",
                    r"days_in_milk",
                ],
                "aggregation": "mean",
            },
            "herd_dynamics": {
                "title": "Herd Inventory",
                "unit": "animals",
                "patterns": [
                    r"report_animal_population_statistics\.population_number_of_cows",
                    r"population_number_of_cows",
                    r"population_number_of_calves",
                ],
                "aggregation": "last",
            },
        },
    },
    "eee": {
        "title": "Economics, Energy & Emissions (EEE)",
        "description": "GHG emissions partition, carbon intensity, feed costs, and energy usage.",
        "panels": {
            "methane_emission": {
                "title": "Enteric Methane Emission",
                "unit": "g",
                "patterns": [
                    r"report_enteric_methane_emission\.enteric_methane_emission_for_.*",
                    r"report_enteric_methane_emission.*",
                    r"enteric_methane_emission.*",
                ],
                "aggregation": "sum",
            },
            "carbon_intensity": {
                "title": "Carbon Intensity",
                "unit": "kg CO2e/kg FPCM",
                "patterns": [
                    r"carbon_intensity",
                    r"fpcm",
                    r"co2.*intensity",
                    r"emissions.*intensity",
                ],
                "aggregation": "mean",
            },
            "feed_cost": {
                "title": "Purchased Feed Cost",
                "unit": "$",
                "patterns": [
                    r"FeedManager\.purchase_feed\..*_cost",
                    r"purchase_feed.*cost",
                    r".*_cost\s*\(\$\)",
                ],
                "aggregation": "sum",
            },
            "energy_consumption": {
                "title": "Operational Energy Use",
                "unit": "kWh",
                "patterns": [
                    r"energy.*use|fuel|diesel|electricity",
                    r"tractor.*fuel",
                    r"electricity.*cost",
                ],
                "aggregation": "sum",
            },
        },
    },
    "field-crops": {
        "title": "Field, Soil & Crops Diagnostics",
        "description": "Transpiration, soil GHG emissions, manure application, and water balance.",
        "panels": {
            "transpiration": {
                "title": "Field Transpiration",
                "unit": "mm",
                "patterns": [
                    r"FieldDataReporter\.send_field_daily_variables\.transpiration.*",
                    r"send_field_daily_variables\.transpiration",
                    r"transpiration",
                ],
                "aggregation": "mean",
            },
            "soil_emissions": {
                "title": "Soil GHG Emissions",
                "unit": "kg/ha",
                "patterns": [
                    r"soil_daily_variables.*n2o|nitrous",
                    r"soilorganicmatter.*carbon",
                    r"n2o_emission",
                ],
                "aggregation": "sum",
            },
            "manure_applied": {
                "title": "Manure Applied to Field",
                "unit": "kg",
                "patterns": [
                    r"machine_manure_applied_mass.*",
                    r"manure_applied_mass.*",
                    r"machine_manure_dry_mass.*",
                ],
                "aggregation": "sum",
            },
            "soil_water": {
                "title": "Soil Water Dynamics",
                "unit": "mm",
                "patterns": [
                    r"drainage|soil_water|percolation|runoff|evapotranspiration",
                ],
                "aggregation": "mean",
            },
        },
    },
    "manure": {
        "title": "Manure Management Diagnostics",
        "description": "Excreted mass, nutrients (N, P), storage losses, and land application.",
        "panels": {
            "manure_excretion": {
                "title": "Excreted Manure Mass",
                "unit": "kg",
                "patterns": [
                    r"report_manure_excretions\..*_manure_mass",
                    r"report_manure_excretions.*",
                    r".*_manure_mass",
                ],
                "aggregation": "sum",
            },
            "manure_nutrients": {
                "title": "Manure N and P Content",
                "unit": "kg",
                "patterns": [
                    r"manure.*nitrogen|manure.*phosphorus|manure_n|manure_p",
                    r"excretion.*nitrogen",
                ],
                "aggregation": "sum",
            },
            "storage_gas_loss": {
                "title": "Storage Gas Emissions",
                "unit": "kg",
                "patterns": [
                    r"lagoon.*methane|volatilization|ammonia|gas_loss",
                    r"methane_production_potential",
                ],
                "aggregation": "sum",
            },
            "applied_manure": {
                "title": "Agronomic Application",
                "unit": "kg",
                "patterns": [
                    r"machine_manure_applied_mass.*",
                    r"manure_applied_mass.*",
                    r"on_farm_manure",
                ],
                "aggregation": "sum",
            },
        },
    },
    "custom": {
        "title": "Custom Metrics Dashboard",
        "description": "Dynamic visualization based on user-specified variable names or patterns.",
        "panels": {},
    },
}

# Alias field_crops to field-crops
PRESET_DEFINITIONS["field_crops"] = PRESET_DEFINITIONS["field-crops"]


class _PresetRegistry(dict):
    """Canonical registry mapping presets to their variable resolution definitions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: str) -> Any:
        normalized = key.strip().lower().replace("_", "-")
        if normalized in self:
            return super().__getitem__(normalized)
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            normalized = key.strip().lower().replace("_", "-")
            if super().__contains__(normalized):
                return True
        return super().__contains__(key)

    def get(self, key: str, default: Any = None) -> Any:
        normalized = key.strip().lower().replace("_", "-")
        if normalized in self:
            return super().__getitem__(normalized)
        return super().get(key, default)

    @property
    def PRESETS(self) -> List[str]:
        # Canonical unique preset names
        return ["executive", "animal", "eee", "field-crops", "manure", "custom"]

    def __call__(self, *args, **kwargs):
        return self


PresetRegistry = _PresetRegistry(PRESET_DEFINITIONS)


def _find_global_time_column(header_columns: List[str]) -> Optional[str]:
    """Finds the primary global simulation_day column in the headers."""
    # 1. Look for RufasTime.simulation_day
    for c in header_columns:
        if re.search(r"RufasTime\.simulation_day", c, re.IGNORECASE):
            return c
    # 2. Look for general simulation_day not tied to a specific sub-reporter
    for c in header_columns:
        c_lower = c.lower()
        if "simulation_day" in c_lower and not any(
            sub in c_lower for sub in ["milk", "herd", "purchased_feed", "deduction", "stream"]
        ):
            return c
    # 3. Fallback to any simulation_day
    for c in header_columns:
        if "simulation_day" in c.lower():
            return c
    return None


def resolve_columns_for_preset(
    header_columns: List[str],
    preset: str = "executive",
    custom_vars: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Identifies required columns from header inspection (`nrows=0`), pairing each
    metric with its time column (`RufasTime.simulation_day` or an entity-level `...simulation_day`).

    Parameters
    ----------
    header_columns : List[str]
        List of column headers obtained from reading CSV with nrows=0.
    preset : str
        Preset name ('executive', 'animal', 'eee', 'field-crops', 'manure', 'custom', or 'all').
    custom_vars : Optional[List[str]]
        Specific variable names or regex patterns when using 'custom' preset or extending another preset.

    Returns
    -------
    Dict[str, Any]
        Dictionary with resolved panels, required columns list, and time column mappings.
    """
    normalized_preset = preset.strip().lower().replace("_", "-")
    valid_presets = PresetRegistry.PRESETS + ["all"]

    if normalized_preset not in valid_presets and normalized_preset not in PresetRegistry:
        raise ValueError(
            f"Unknown preset: '{preset}'. Valid presets are: {', '.join(PresetRegistry.PRESETS + ['all'])}"
        )

    global_time_col = _find_global_time_column(header_columns)

    # Calendar year column if present
    calendar_year_col = None
    for c in header_columns:
        if re.search(r"RufasTime\.calendar_year", c, re.IGNORECASE):
            calendar_year_col = c
            break

    # Julian day column if present
    julian_day_col = None
    for c in header_columns:
        if re.search(r"RufasTime\.day\b", c, re.IGNORECASE):
            julian_day_col = c
            break

    resolved_panels: Dict[str, Any] = {}
    required_cols: List[str] = []

    # Include global time / calendar columns first if available
    if global_time_col:
        required_cols.append(global_time_col)
    if calendar_year_col and calendar_year_col not in required_cols:
        required_cols.append(calendar_year_col)
    if julian_day_col and julian_day_col not in required_cols:
        required_cols.append(julian_day_col)

    if normalized_preset == "custom":
        if not custom_vars:
            raise ValueError("Preset 'custom' requires 'custom_vars' to be specified.")

        for var_pattern in custom_vars:
            matches = [c for c in header_columns if c == var_pattern or re.search(var_pattern, c, re.IGNORECASE)]
            if not matches and var_pattern in header_columns:
                matches = [var_pattern]

            for m in matches:
                # Generate clean panel key
                clean_name = m.split(" ")[0].rsplit(".", 1)[-1] if "." in m else m
                panel_key = clean_name
                idx = 1
                while panel_key in resolved_panels:
                    panel_key = f"{clean_name}_{idx}"
                    idx += 1

                # Check entity-specific time column
                time_col = global_time_col
                prefix = m.rsplit(".", 1)[0] if "." in m else ""
                if prefix:
                    entity_time = [
                        c for c in header_columns if prefix in c and "simulation_day" in c.lower()
                    ]
                    if entity_time:
                        time_col = entity_time[0]

                resolved_panels[panel_key] = {
                    "value_col": m,
                    "value_cols": [m],
                    "time_col": time_col,
                    "entity_col": None,
                    "title": m.split(" ")[0],
                    "unit": extract_variable_unit(m),
                    "aggregation": "mean",
                    "available": True,
                }
                if m not in required_cols:
                    required_cols.append(m)
                if time_col and time_col not in required_cols:
                    required_cols.append(time_col)
    else:
        # Determine presets to process
        target_preset_names = (
            ["executive", "animal", "eee", "field-crops", "manure"]
            if normalized_preset == "all"
            else [normalized_preset]
        )

        for p_name in target_preset_names:
            preset_def = PresetRegistry[p_name]
            for panel_key, panel_def in preset_def["panels"].items():
                if panel_key in resolved_panels and resolved_panels[panel_key].get("available"):
                    continue

                matched_cols: List[str] = []
                for pattern in panel_def["patterns"]:
                    found = [c for c in header_columns if re.search(pattern, c, re.IGNORECASE)]
                    if found:
                        matched_cols = found
                        break

                if matched_cols:
                    val_col = matched_cols[0]

                    # Determine time column
                    time_col = None
                    if "time_pattern" in panel_def:
                        t_found = [
                            c for c in header_columns if re.search(panel_def["time_pattern"], c, re.IGNORECASE)
                        ]
                        if t_found:
                            time_col = t_found[0]

                    if not time_col:
                        # Try finding entity time column with matching namespace prefix
                        prefix = val_col.rsplit(".", 1)[0] if "." in val_col else ""
                        if prefix:
                            entity_time = [
                                c for c in header_columns if prefix in c and "simulation_day" in c.lower()
                            ]
                            if entity_time:
                                time_col = entity_time[0]

                    if not time_col:
                        time_col = global_time_col

                    # Determine entity ID column (e.g. cow_id)
                    entity_col = None
                    if "entity_pattern" in panel_def:
                        e_found = [
                            c for c in header_columns if re.search(panel_def["entity_pattern"], c, re.IGNORECASE)
                        ]
                        if e_found:
                            entity_col = e_found[0]
                    elif val_col and "." in val_col:
                        prefix = val_col.rsplit(".", 1)[0]
                        e_found = [
                            c for c in header_columns if prefix in c and ("cow_id" in c.lower() or "animal_id" in c.lower())
                        ]
                        if e_found:
                            entity_col = e_found[0]

                    unit = extract_variable_unit(val_col) or panel_def.get("unit")

                    resolved_panels[panel_key] = {
                        "value_col": val_col,
                        "value_cols": matched_cols,
                        "time_col": time_col,
                        "entity_col": entity_col,
                        "title": panel_def.get("title", panel_key),
                        "unit": unit,
                        "aggregation": panel_def.get("aggregation", "sum"),
                        "available": True,
                    }

                    # Add columns to required
                    for col in matched_cols:
                        if col not in required_cols:
                            required_cols.append(col)
                    if time_col and time_col not in required_cols:
                        required_cols.append(time_col)
                    if entity_col and entity_col not in required_cols:
                        required_cols.append(entity_col)
                else:
                    resolved_panels[panel_key] = {
                        "value_col": None,
                        "value_cols": [],
                        "time_col": None,
                        "entity_col": None,
                        "title": panel_def.get("title", panel_key),
                        "unit": panel_def.get("unit"),
                        "aggregation": panel_def.get("aggregation", "sum"),
                        "available": False,
                        "missing_reason": f"Variables for panel '{panel_key}' not found in simulation output",
                    }

        # If custom_vars also provided to extend preset
        if custom_vars:
            for var_pattern in custom_vars:
                matches = [c for c in header_columns if c == var_pattern or re.search(var_pattern, c, re.IGNORECASE)]
                for m in matches:
                    clean_name = m.split(" ")[0].rsplit(".", 1)[-1] if "." in m else m
                    panel_key = clean_name
                    idx = 1
                    while panel_key in resolved_panels:
                        panel_key = f"{clean_name}_{idx}"
                        idx += 1
                    resolved_panels[panel_key] = {
                        "value_col": m,
                        "value_cols": [m],
                        "time_col": global_time_col,
                        "entity_col": None,
                        "title": m.split(" ")[0],
                        "unit": extract_variable_unit(m),
                        "aggregation": "mean",
                        "available": True,
                    }
                    if m not in required_cols:
                        required_cols.append(m)

    return {
        "preset": preset,
        "panels": resolved_panels,
        "required_columns": list(dict.fromkeys(required_cols)),
        "global_time_col": global_time_col,
        "calendar_year_col": calendar_year_col,
    }


def main():
    """CLI entrypoint for rufas-plot."""
    parser = argparse.ArgumentParser(description="RuFaS Simulation Visualization and Plotting Tool")
    parser.add_argument("input_path", nargs="?", default=None, help="Path to simulation CSV or output directory")
    parser.add_argument(
        "-p",
        "--preset",
        choices=["executive", "animal", "eee", "field-crops", "manure", "all", "custom"],
        default="executive",
        help="Visualization preset",
    )
    parser.add_argument("-v", "--vars", dest="custom_vars", default=None, help="Custom variables / regex to plot")
    args = parser.parse_args()
    print(f"rufas-plot (preset: {args.preset})")


if __name__ == "__main__":
    main()

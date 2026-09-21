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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from tools.config import (
    RuFaSBoundaryError,
    RuFaSConfigError,
    assert_within_rufas_scope,
    get_rufas_root,
)

__all__ = [
    "AlignedSimulationData",
    "PresetRegistry",
    "PRESET_DEFINITIONS",
    "RaggedTimeSeriesLoader",
    "TemporalAligner",
    "extract_variable_unit",
    "resolve_columns_for_preset",
    "main",
]



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


def safe_header_match(pattern: str, col: str) -> bool:
    """Matches pattern against col, falling back to escaped regex or literal search if invalid regex."""
    if pattern == col:
        return True
    try:
        return bool(re.search(pattern, col, re.IGNORECASE))
    except re.error:
        try:
            return bool(re.search(re.escape(pattern), col, re.IGNORECASE))
        except re.error:
            return pattern.lower() in col.lower()


def _resolve_custom_variable(
    var_pattern: str,
    header_columns: List[str],
    global_time_col: Optional[str],
    resolved_panels: Dict[str, Any],
    required_cols: List[str],
) -> None:
    """Resolves a single custom variable or pattern into resolved_panels and required_cols."""
    matches = [c for c in header_columns if safe_header_match(var_pattern, c)]
    if not matches and var_pattern in header_columns:
        matches = [var_pattern]

    for m in matches:
        clean_name = m.split(" ")[0].rsplit(".", 1)[-1] if "." in m else m
        panel_key = clean_name
        idx = 1
        while panel_key in resolved_panels:
            panel_key = f"{clean_name}_{idx}"
            idx += 1

        time_col = global_time_col
        prefix = m.rsplit(".", 1)[0] if "." in m else ""
        entity_col = None
        if prefix:
            entity_time = [
                c for c in header_columns if prefix in c and "simulation_day" in c.lower()
            ]
            if entity_time:
                time_col = entity_time[0]
            e_found = [
                c for c in header_columns if prefix in c and ("cow_id" in c.lower() or "animal_id" in c.lower())
            ]
            if e_found:
                entity_col = e_found[0]

        resolved_panels[panel_key] = {
            "value_col": m,
            "value_cols": [m],
            "time_col": time_col,
            "entity_col": entity_col,
            "title": m.split(" ")[0],
            "unit": extract_variable_unit(m),
            "aggregation": "mean",
            "available": True,
        }
        if m not in required_cols:
            required_cols.append(m)
        if time_col and time_col not in required_cols:
            required_cols.append(time_col)
        if entity_col and entity_col not in required_cols:
            required_cols.append(entity_col)


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
        if safe_header_match(r"RufasTime\.calendar_year", c):
            calendar_year_col = c
            break

    # Julian day column if present
    julian_day_col = None
    for c in header_columns:
        if safe_header_match(r"RufasTime\.day\b", c):
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
            _resolve_custom_variable(
                var_pattern=var_pattern,
                header_columns=header_columns,
                global_time_col=global_time_col,
                resolved_panels=resolved_panels,
                required_cols=required_cols,
            )
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
                    found = [c for c in header_columns if safe_header_match(pattern, c)]
                    if found:
                        matched_cols = found
                        break

                if matched_cols:
                    val_col = matched_cols[0]

                    # Determine time column
                    time_col = None
                    if "time_pattern" in panel_def:
                        t_found = [
                            c for c in header_columns if safe_header_match(panel_def["time_pattern"], c)
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
                            c for c in header_columns if safe_header_match(panel_def["entity_pattern"], c)
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
                _resolve_custom_variable(
                    var_pattern=var_pattern,
                    header_columns=header_columns,
                    global_time_col=global_time_col,
                    resolved_panels=resolved_panels,
                    required_cols=required_cols,
                )

    return {
        "preset": preset,
        "panels": resolved_panels,
        "required_columns": list(dict.fromkeys(required_cols)),
        "global_time_col": global_time_col,
        "calendar_year_col": calendar_year_col,
        "julian_day_col": julian_day_col,
    }


@dataclass
class AlignedSimulationData:
    """
    Uniformly-indexed simulation dataset produced by TemporalAligner.

    Attributes
    ----------
    df : pd.DataFrame
        Continuous daily DataFrame indexed by simulation_day (0..T-1).
    name : str
        Name or identifier for the simulation run (defaults to 'Simulation').
    preset : str
        Preset name used to extract the metrics (defaults to 'custom').
    units : Dict[str, str]
        Dictionary mapping column names in df to their unit strings.
    panels : Dict[str, Any]
        Dictionary of panel definitions with resolution metadata and primary/rolling columns.
    calendar_years : Optional[pd.Series]
        Continuous Series of calendar years aligned to simulation_day.
    julian_days : Optional[pd.Series]
        Continuous Series of Julian days aligned to simulation_day.
    """

    df: pd.DataFrame
    name: str = "Simulation"
    preset: str = "custom"
    units: Dict[str, str] = field(default_factory=dict)
    panels: Dict[str, Any] = field(default_factory=dict)
    calendar_years: Optional[pd.Series] = None
    julian_days: Optional[pd.Series] = None

    def __len__(self) -> int:
        return len(self.df)


class TemporalAligner:
    """
    Ingests selective columns from RuFaS simulation outputs, normalizes ragged
    entity-level series (per-cow, per-pen, per-field) to daily farm aggregates,
    reindexes to a continuous simulation day range, and calculates rolling averages.
    """

    def __init__(
        self,
        csv_path: Union[str, Path],
        preset: str = "executive",
        custom_vars: Optional[List[str]] = None,
        name: Optional[str] = None,
        allow_external: bool = False,
    ):
        self.raw_path = Path(csv_path)
        self.csv_path = assert_within_rufas_scope(self.raw_path, allow_external=allow_external)

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Simulation output CSV not found: {self.csv_path}")

        self.preset = preset
        self.custom_vars = custom_vars
        self.name = name or self.csv_path.stem

    def align(self, rolling_window: int = 30) -> AlignedSimulationData:
        """
        Executes selective header resolution, loads only required columns with usecols,
        aggregates ragged series into continuous daily series, and calculates rolling means.

        Parameters
        ----------
        rolling_window : int
            Window size in days for moving average calculation (min 1, default 30).

        Returns
        -------
        AlignedSimulationData
            Normalized simulation container with continuous RangeIndex(0, max_day + 1).
        """
        rolling_window = max(1, int(rolling_window))

        # 1. Header inspection (nrows=0)
        header_df = pd.read_csv(self.csv_path, nrows=0)
        header_cols = list(header_df.columns)

        # 2. Resolve required columns
        resolved = resolve_columns_for_preset(
            header_columns=header_cols,
            preset=self.preset,
            custom_vars=self.custom_vars,
        )

        required_cols = resolved["required_columns"]
        global_time_col = resolved["global_time_col"]
        calendar_year_col = resolved["calendar_year_col"]
        julian_day_col = resolved["julian_day_col"]

        if not required_cols:
            empty_df = pd.DataFrame(index=pd.RangeIndex(0, 0))
            empty_df.index.name = "simulation_day"
            return AlignedSimulationData(
                df=empty_df,
                name=self.name,
                preset=self.preset,
                units={},
                panels=resolved["panels"],
            )

        # 3. Read ONLY required columns
        raw_df = pd.read_csv(self.csv_path, usecols=required_cols, low_memory=False)

        if len(raw_df) == 0:
            empty_df = pd.DataFrame(index=pd.RangeIndex(0, 0))
            empty_df.index.name = "simulation_day"
            return AlignedSimulationData(
                df=empty_df,
                name=self.name,
                preset=self.preset,
                units={},
                panels=resolved["panels"],
            )

        # 4. Determine timeline span (simulation_day continuous range)
        all_sim_days: List[pd.Series] = []
        if global_time_col and global_time_col in raw_df.columns:
            valid_days = pd.to_numeric(raw_df[global_time_col], errors="coerce").dropna()
            if len(valid_days) > 0:
                all_sim_days.append(valid_days)

        for p_key, p_info in resolved["panels"].items():
            if not p_info.get("available"):
                continue
            t_col = p_info.get("time_col")
            if t_col and t_col in raw_df.columns and t_col != global_time_col:
                valid_days = pd.to_numeric(raw_df[t_col], errors="coerce").dropna()
                if len(valid_days) > 0:
                    all_sim_days.append(valid_days)

        if all_sim_days:
            combined_days = pd.concat(all_sim_days)
            max_day = int(combined_days.max())
        else:
            max_day = max(0, len(raw_df) - 1)

        target_index = pd.RangeIndex(0, max_day + 1)

        # 5. Extract calendar years and Julian days if present
        calendar_years: Optional[pd.Series] = None
        if calendar_year_col and calendar_year_col in raw_df.columns:
            t_col = global_time_col or (all_sim_days[0].name if all_sim_days else None)
            if t_col and t_col in raw_df.columns:
                sub = raw_df[[t_col, calendar_year_col]].dropna()
                sub[t_col] = pd.to_numeric(sub[t_col], errors="coerce")
                sub[calendar_year_col] = pd.to_numeric(sub[calendar_year_col], errors="coerce")
                sub = sub.dropna()
                if len(sub) > 0:
                    cal_s = sub.groupby(sub[t_col].astype(int))[calendar_year_col].first()
                    calendar_years = cal_s.reindex(target_index).ffill().bfill()

        julian_days: Optional[pd.Series] = None
        if julian_day_col and julian_day_col in raw_df.columns:
            t_col = global_time_col or (all_sim_days[0].name if all_sim_days else None)
            if t_col and t_col in raw_df.columns:
                sub = raw_df[[t_col, julian_day_col]].dropna()
                sub[t_col] = pd.to_numeric(sub[t_col], errors="coerce")
                sub[julian_day_col] = pd.to_numeric(sub[julian_day_col], errors="coerce")
                sub = sub.dropna()
                if len(sub) > 0:
                    jul_s = sub.groupby(sub[t_col].astype(int))[julian_day_col].first()
                    julian_days = jul_s.reindex(target_index).ffill().bfill()

        # 6. Aggregate panels into continuous daily series
        aligned_df = pd.DataFrame(index=target_index)
        aligned_df.index.name = "simulation_day"
        units: Dict[str, str] = {}
        updated_panels: Dict[str, Any] = {}

        for panel_key, panel_info in resolved["panels"].items():
            updated_panel = dict(panel_info)
            if not panel_info.get("available"):
                updated_panel["primary"] = None
                updated_panel["rolling"] = None
                updated_panels[panel_key] = updated_panel
                continue

            time_col = panel_info.get("time_col") or global_time_col
            val_col = panel_info.get("value_col")
            val_cols = panel_info.get("value_cols") or ([val_col] if val_col else [])
            entity_col = panel_info.get("entity_col")
            agg = panel_info.get("aggregation", "sum")
            unit = panel_info.get("unit")

            present_val_cols = [c for c in val_cols if c in raw_df.columns]
            if not present_val_cols or not time_col or time_col not in raw_df.columns:
                updated_panel["available"] = False
                updated_panel["primary"] = None
                updated_panel["rolling"] = None
                updated_panel["missing_reason"] = f"Columns missing in CSV for panel '{panel_key}'"
                updated_panels[panel_key] = updated_panel
                continue

            is_entity = bool(entity_col and entity_col in raw_df.columns)

            if is_entity and val_col and val_col in raw_df.columns:
                # Entity-level series (e.g. per-cow daily milk)
                sub = raw_df[[time_col, val_col]].copy()
                sub[time_col] = pd.to_numeric(sub[time_col], errors="coerce")
                sub[val_col] = pd.to_numeric(sub[val_col], errors="coerce")
                sub = sub.dropna()

                if len(sub) > 0:
                    t_int = sub[time_col].astype(int)
                    tot_series = sub.groupby(t_int)[val_col].sum().reindex(target_index)
                    mean_series = sub.groupby(t_int)[val_col].mean().reindex(target_index)
                else:
                    tot_series = pd.Series(index=target_index, dtype=float)
                    mean_series = pd.Series(index=target_index, dtype=float)

                primary_col = f"{panel_key}_total"
                mean_col = f"{panel_key}_mean"
                aligned_df[primary_col] = tot_series
                aligned_df[mean_col] = mean_series

                if unit:
                    units[primary_col] = unit
                    units[mean_col] = f"{unit}/animal"

                updated_panel["primary"] = primary_col
                updated_panel["mean_col"] = mean_col
                updated_panel["rolling"] = f"{primary_col}_rolling"
                updated_panel["mean_rolling"] = f"{mean_col}_rolling"

            else:
                # Farm-level or aggregated multiple sub-entities (e.g. pens, fields)
                sub = raw_df[[time_col] + present_val_cols].copy()
                sub[time_col] = pd.to_numeric(sub[time_col], errors="coerce")
                for c in present_val_cols:
                    sub[c] = pd.to_numeric(sub[c], errors="coerce")
                sub = sub.dropna(subset=[time_col])

                if len(sub) > 0:
                    if len(present_val_cols) == 1:
                        c = present_val_cols[0]
                        sub_c = sub.dropna(subset=[c])
                        t_int = sub_c[time_col].astype(int)
                        if agg == "sum":
                            series = sub_c.groupby(t_int)[c].sum()
                        elif agg == "mean":
                            series = sub_c.groupby(t_int)[c].mean()
                        elif agg == "last":
                            series = sub_c.groupby(t_int)[c].last()
                        else:
                            series = sub_c.groupby(t_int)[c].sum()
                    else:
                        if agg == "sum":
                            col_series = []
                            for c in present_val_cols:
                                sub_c = sub.dropna(subset=[c])
                                col_series.append(sub_c.groupby(sub_c[time_col].astype(int))[c].sum())
                            series = pd.concat(col_series, axis=1).sum(axis=1)
                        elif agg == "mean":
                            col_series = []
                            for c in present_val_cols:
                                sub_c = sub.dropna(subset=[c])
                                col_series.append(sub_c.groupby(sub_c[time_col].astype(int))[c].mean())
                            series = pd.concat(col_series, axis=1).mean(axis=1)
                        elif agg == "last":
                            sub_c = sub.dropna(subset=[present_val_cols[0]])
                            series = sub_c.groupby(sub_c[time_col].astype(int))[present_val_cols[0]].last()
                        else:
                            col_series = []
                            for c in present_val_cols:
                                sub_c = sub.dropna(subset=[c])
                                col_series.append(sub_c.groupby(sub_c[time_col].astype(int))[c].sum())
                            series = pd.concat(col_series, axis=1).sum(axis=1)

                    series = series.reindex(target_index)
                else:
                    series = pd.Series(index=target_index, dtype=float)

                primary_col = panel_key
                aligned_df[primary_col] = series
                if unit:
                    units[primary_col] = unit

                updated_panel["primary"] = primary_col
                updated_panel["rolling"] = f"{primary_col}_rolling"

            updated_panels[panel_key] = updated_panel

        # 7. Compute rolling window averages for all numeric metric columns
        metric_columns = list(aligned_df.columns)
        for col in metric_columns:
            rolling_col = f"{col}_rolling"
            aligned_df[rolling_col] = aligned_df[col].rolling(window=rolling_window, min_periods=1).mean()
            if col in units:
                units[rolling_col] = units[col]

        return AlignedSimulationData(
            df=aligned_df,
            name=self.name,
            preset=self.preset,
            units=units,
            panels=updated_panels,
            calendar_years=calendar_years,
            julian_days=julian_days,
        )


class RaggedTimeSeriesLoader:
    """
    Convenience loader for selective inspection and temporal normalization of RuFaS simulation outputs.
    """

    def __init__(
        self,
        csv_path: Union[str, Path],
        preset: str = "executive",
        custom_vars: Optional[List[str]] = None,
        rolling_window: int = 30,
        name: Optional[str] = None,
        allow_external: bool = False,
    ):
        self.aligner = TemporalAligner(
            csv_path=csv_path,
            preset=preset,
            custom_vars=custom_vars,
            name=name,
            allow_external=allow_external,
        )
        self.rolling_window = rolling_window

    def load(self) -> AlignedSimulationData:
        """Executes alignment and returns AlignedSimulationData."""
        return self.aligner.align(rolling_window=self.rolling_window)

    @classmethod
    def load_aligned_dataframe(
        cls,
        csv_path: Union[str, Path],
        preset: str = "executive",
        custom_vars: Optional[List[str]] = None,
        rolling_window: int = 30,
        name: Optional[str] = None,
        allow_external: bool = False,
    ) -> AlignedSimulationData:
        """
        Class method to load and align simulation time-series in a single call.
        """
        aligner = TemporalAligner(
            csv_path=csv_path,
            preset=preset,
            custom_vars=custom_vars,
            name=name,
            allow_external=allow_external,
        )
        return aligner.align(rolling_window=rolling_window)

    load_aligned_series = load_aligned_dataframe


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

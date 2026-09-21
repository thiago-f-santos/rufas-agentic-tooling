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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from tools.config import (
    RuFaSBoundaryError,
    RuFaSConfigError,
    assert_within_rufas_scope,
    get_rufas_root,
)

__all__ = [
    "AlignedSimulationData",
    "MatplotlibRenderer",
    "PlotlyRenderer",
    "PresetRegistry",
    "PRESET_DEFINITIONS",
    "RaggedTimeSeriesLoader",
    "ScenarioComparator",
    "ScenarioComparisonResult",
    "ScenarioDelta",
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


@dataclass
class ScenarioDelta:
    """
    Delta comparison metrics between a scenario and baseline.

    Attributes
    ----------
    name : str
        Identifier or name of the scenario.
    data : AlignedSimulationData
        Original scenario simulation container.
    abs_deltas : pd.DataFrame
        DataFrame of absolute differences (scenario - baseline) indexed by simulation_day.
    pct_deltas : pd.DataFrame
        DataFrame of percentage differences ((scenario - baseline) / baseline * 100) indexed by simulation_day.
    kpi_summary : Dict[str, Dict[str, Any]]
        Aggregated KPI differences (totals, means, absolute and percent deltas) for this scenario.
    """

    name: str
    data: AlignedSimulationData
    abs_deltas: pd.DataFrame
    pct_deltas: pd.DataFrame
    kpi_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ScenarioComparisonResult:
    """
    Result container for multi-scenario comparative analytics.

    Attributes
    ----------
    baseline : AlignedSimulationData
        Baseline simulation dataset.
    scenarios : List[ScenarioDelta]
        List of ScenarioDelta containers for each evaluated scenario.
    common_index : pd.Index
        Common simulation_day index across baseline and all scenarios.
    summary : Dict[str, Dict[str, Dict[str, Any]]]
        Consolidated KPI summary table mapped by scenario name and metric name.
    calendar_years : Optional[pd.Series]
        Continuous Series of calendar years aligned to common_index.
    julian_days : Optional[pd.Series]
        Continuous Series of Julian days aligned to common_index.
    """

    baseline: AlignedSimulationData
    scenarios: List[ScenarioDelta] = field(default_factory=list)
    common_index: pd.Index = field(default_factory=pd.RangeIndex)
    summary: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    calendar_years: Optional[pd.Series] = None
    julian_days: Optional[pd.Series] = None

    def __len__(self) -> int:
        return len(self.common_index)

    def get_scenario(self, name: str) -> Optional[ScenarioDelta]:
        """Returns ScenarioDelta matching the given scenario name, or None."""
        for s in self.scenarios:
            if s.name == name:
                return s
        return None

    def get_names(self) -> List[str]:
        """Returns list of scenario names."""
        return [s.name for s in self.scenarios]


class _CompareCallable:
    """Descriptor that allows .compare() to work both as a classmethod and an instance method."""

    def __get__(self, instance, owner):
        if instance is None:

            def _classmethod_compare(
                baseline_data: AlignedSimulationData,
                scenario_data: Union[AlignedSimulationData, List[AlignedSimulationData]],
            ) -> ScenarioComparisonResult:
                scenarios = scenario_data if isinstance(scenario_data, list) else [scenario_data]
                return owner(baseline=baseline_data, scenarios=scenarios).compute_deltas()

            return _classmethod_compare
        else:

            def _instance_compare(
                baseline_data: Optional[AlignedSimulationData] = None,
                scenario_data: Optional[Union[AlignedSimulationData, List[AlignedSimulationData]]] = None,
            ) -> ScenarioComparisonResult:
                if baseline_data is None and scenario_data is None:
                    return instance.compute_deltas()
                scenarios = scenario_data if isinstance(scenario_data, list) else [scenario_data]
                return owner(baseline=baseline_data, scenarios=scenarios).compute_deltas()

            return _instance_compare


class ScenarioComparator:
    """
    Ingests a baseline simulation and one or more scenario simulations,
    aligns their timelines to a common index, computes absolute and percentage deltas,
    and produces consolidated KPI summary tables.
    """

    compare = _CompareCallable()

    def __init__(
        self,
        baseline: Optional[AlignedSimulationData] = None,
        scenarios: Optional[Union[AlignedSimulationData, List[AlignedSimulationData]]] = None,
        *,
        baseline_data: Optional[AlignedSimulationData] = None,
        scenario_data: Optional[Union[AlignedSimulationData, List[AlignedSimulationData]]] = None,
    ):
        base = baseline if baseline is not None else baseline_data
        if base is None or not isinstance(base, AlignedSimulationData):
            raise TypeError("baseline must be an instance of AlignedSimulationData")

        scens_raw = scenarios if scenarios is not None else scenario_data
        if scens_raw is None:
            scens: List[AlignedSimulationData] = []
        elif isinstance(scens_raw, AlignedSimulationData):
            scens = [scens_raw]
        elif isinstance(scens_raw, (list, tuple)):
            scens = list(scens_raw)
        else:
            raise TypeError("scenarios must be an AlignedSimulationData or list of AlignedSimulationData")

        for s in scens:
            if not isinstance(s, AlignedSimulationData):
                raise TypeError(f"Scenario item {s} must be an instance of AlignedSimulationData")

        self.baseline = base
        self.scenarios = scens
        self._result: Optional[ScenarioComparisonResult] = None

    def compute_deltas(self, metrics: Optional[List[str]] = None) -> ScenarioComparisonResult:
        """
        Aligns simulation timelines to a common index, computes absolute differences
        (scenario - baseline) and percentage differences ((scenario - baseline) / baseline * 100)
        with safe zero handling, and generates KPI summary statistics.

        Parameters
        ----------
        metrics : Optional[List[str]]
            Specific metrics to compute deltas for. If None, computes for all common numeric columns.

        Returns
        -------
        ScenarioComparisonResult
            Container with scenario deltas, common timeline index, and consolidated KPI summary.
        """
        # Determine common simulation day index
        common_index = self.baseline.df.index
        for s in self.scenarios:
            common_index = common_index.intersection(s.df.index)
        common_index = common_index.sort_values()

        # Identify numeric columns in baseline
        base_numeric = [
            c
            for c in self.baseline.df.columns
            if pd.api.types.is_numeric_dtype(self.baseline.df[c])
        ]

        scenario_deltas: List[ScenarioDelta] = []
        overall_summary: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for scen in self.scenarios:
            target_metrics = (
                metrics
                if metrics is not None
                else [
                    c
                    for c in base_numeric
                    if c in scen.df.columns and pd.api.types.is_numeric_dtype(scen.df[c])
                ]
            )

            abs_df = pd.DataFrame(index=common_index)
            pct_df = pd.DataFrame(index=common_index)
            abs_df.index.name = "simulation_day"
            pct_df.index.name = "simulation_day"

            scen_summary: Dict[str, Dict[str, Any]] = {}

            for m in target_metrics:
                if m not in self.baseline.df.columns or m not in scen.df.columns:
                    continue

                if len(common_index) == 0:
                    abs_series = pd.Series(index=common_index, dtype=float)
                    pct_series = pd.Series(index=common_index, dtype=float)
                    base_tot = 0.0
                    scen_tot = 0.0
                    base_mean = 0.0
                    scen_mean = 0.0
                else:
                    b_series = pd.to_numeric(self.baseline.df.loc[common_index, m], errors="coerce")
                    s_series = pd.to_numeric(scen.df.loc[common_index, m], errors="coerce")

                    abs_series = s_series - b_series

                    with np.errstate(divide="ignore", invalid="ignore"):
                        safe_base = np.where(b_series == 0, np.nan, b_series)
                        is_nan = np.isnan(b_series) | np.isnan(s_series)
                        pct_arr = np.where(
                            is_nan,
                            np.nan,
                            np.where(b_series == 0, 0.0, (s_series - b_series) / safe_base * 100.0),
                        )
                    pct_series = pd.Series(pct_arr, index=common_index, dtype=float)

                    base_tot = float(b_series.sum())
                    scen_tot = float(s_series.sum())
                    base_mean = float(b_series.mean())
                    scen_mean = float(s_series.mean())

                abs_df[m] = abs_series
                pct_df[m] = pct_series

                total_delta_abs = scen_tot - base_tot
                total_delta_pct = (
                    ((scen_tot - base_tot) / base_tot * 100.0) if base_tot != 0.0 else 0.0
                )
                mean_delta_abs = scen_mean - base_mean
                mean_delta_pct = (
                    ((scen_mean - base_mean) / base_mean * 100.0) if base_mean != 0.0 else 0.0
                )

                unit = self.baseline.units.get(m, scen.units.get(m, ""))

                scen_summary[m] = {
                    "baseline_total": base_tot,
                    "scenario_total": scen_tot,
                    "total_delta_abs": total_delta_abs,
                    "total_delta_pct": total_delta_pct,
                    "baseline_mean": base_mean,
                    "scenario_mean": scen_mean,
                    "mean_delta_abs": mean_delta_abs,
                    "mean_delta_pct": mean_delta_pct,
                    "unit": unit,
                }

            scen_delta = ScenarioDelta(
                name=scen.name,
                data=scen,
                abs_deltas=abs_df,
                pct_deltas=pct_df,
                kpi_summary=scen_summary,
            )
            scenario_deltas.append(scen_delta)
            overall_summary[scen.name] = scen_summary

        cal_years = (
            self.baseline.calendar_years.reindex(common_index)
            if self.baseline.calendar_years is not None
            else None
        )
        jul_days = (
            self.baseline.julian_days.reindex(common_index)
            if self.baseline.julian_days is not None
            else None
        )

        result = ScenarioComparisonResult(
            baseline=self.baseline,
            scenarios=scenario_deltas,
            common_index=common_index,
            summary=overall_summary,
            calendar_years=cal_years,
            julian_days=jul_days,
        )
        self._result = result
        return result

    def get_kpi_summary(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Returns consolidated KPI summary dictionary:
        {scenario_name: {metric_name: {...summary_stats...}}}
        """
        if self._result is None:
            self.compute_deltas()
        return self._result.summary

    def get_overlay_series(self, metric: str) -> Dict[str, pd.Series]:
        """
        Returns dictionary mapping dataset names to aligned series for a given metric:
        {baseline_name: baseline_series, scenario1_name: scenario1_series, ...}
        """
        if self._result is None:
            self.compute_deltas()
        idx = self._result.common_index
        series_map: Dict[str, pd.Series] = {}
        if metric in self.baseline.df.columns:
            series_map[self.baseline.name] = self.baseline.df.loc[idx, metric]
        for s in self.scenarios:
            if metric in s.df.columns:
                series_map[s.name] = s.df.loc[idx, metric]
        return series_map

    def get_common_metrics(self) -> List[str]:
        """Returns list of numeric metrics present in baseline and all scenarios."""
        metrics = [
            c
            for c in self.baseline.df.columns
            if pd.api.types.is_numeric_dtype(self.baseline.df[c])
        ]
        for s in self.scenarios:
            metrics = [
                c
                for c in metrics
                if c in s.df.columns and pd.api.types.is_numeric_dtype(s.df[c])
            ]
        return metrics


class MatplotlibRenderer:
    """
    Static multi-panel figure renderer using Matplotlib.
    Generates publication-quality figures in PNG (300 DPI) and PDF
    with clean styling, subtle grids, semantic colors, rolling average overlays,
    and optional scenario comparison delta subplots.
    """

    DEFAULT_PALETTE = [
        "#1f77b4",  # Blue
        "#2ca02c",  # Green
        "#d62728",  # Red
        "#9467bd",  # Purple
        "#ff7f0e",  # Orange
        "#8c564b",  # Brown
        "#17becf",  # Teal
        "#bcbd22",  # Yellow-green
    ]

    SEMANTIC_PANEL_COLORS = {
        "milk_produced": "#1f77b4",
        "milk": "#1f77b4",
        "milk_solids": "#17becf",
        "days_in_milk": "#3366cc",
        "herd_dynamics": "#9467bd",
        "methane_emission": "#d62728",
        "methane": "#d62728",
        "carbon_intensity": "#ff7f0e",
        "energy_consumption": "#bcbd22",
        "manure_excretion": "#8c564b",
        "manure_nutrients": "#a05d56",
        "storage_gas_loss": "#d62728",
        "manure_applied": "#8c564b",
        "applied_manure": "#8c564b",
        "feed_cost": "#e377c2",
        "transpiration": "#2ca02c",
        "transp": "#2ca02c",
        "soil_emissions": "#ff7f0e",
        "soil_water": "#1f77b4",
    }

    SCENARIO_LINESTYLES = ["--", ":", "-.", (0, (3, 1, 1, 1))]
    SCENARIO_COLORS = ["#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#17becf"]

    def __init__(self, style: str = "default", figsize: Optional[tuple] = None):
        self.style = style
        self.figsize = figsize

    def _determine_grid(self, preset: str, n_panels: int) -> tuple[int, int]:
        """Calculates (nrows, ncols) grid based on preset and number of panels."""
        norm_preset = (preset or "custom").strip().lower().replace("_", "-")
        if norm_preset == "executive":
            if n_panels <= 6:
                return (3, 2)
            ncols = 2
            return ((n_panels + ncols - 1) // ncols, ncols)
        elif norm_preset in ("animal", "eee", "field-crops", "manure"):
            if n_panels <= 4:
                return (2, 2)
            ncols = 2
            return ((n_panels + ncols - 1) // ncols, ncols)
        else:
            # Dynamic grid
            if n_panels <= 1:
                return (1, 1)
            elif n_panels == 2:
                return (1, 2)
            elif n_panels <= 4:
                return (2, 2)
            elif n_panels <= 6:
                return (3, 2)
            else:
                ncols = 2
                return ((n_panels + ncols - 1) // ncols, ncols)

    def _get_panel_color(self, panel_key: str, index: int) -> str:
        """Determines semantic color for a panel key, falling back to palette."""
        clean_key = panel_key.lower().strip()
        for k, col in self.SEMANTIC_PANEL_COLORS.items():
            if k in clean_key:
                return col
        return self.DEFAULT_PALETTE[index % len(self.DEFAULT_PALETTE)]

    def _apply_axis_styling(self, ax: Any) -> None:
        """Applies subtle publication-quality styling to a subplot axis."""
        ax.grid(True, linestyle="--", alpha=0.4, color="#cccccc")
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#666666")
        ax.spines["bottom"].set_color("#666666")
        ax.tick_params(labelsize=8)

    def render(
        self,
        data: AlignedSimulationData,
        output_path: Union[str, Path],
        comparison: Optional[ScenarioComparisonResult] = None,
        dpi: int = 300,
        title: Optional[str] = None,
    ) -> Path:
        """
        Renders multi-panel static figure to PNG or PDF.

        Parameters
        ----------
        data : AlignedSimulationData
            Aligned simulation dataset.
        output_path : Union[str, Path]
            Destination file path (.png or .pdf).
        comparison : Optional[ScenarioComparisonResult]
            Scenario comparison result with baseline, scenarios, and percentage deltas.
        dpi : int
            Image resolution in DPI (default: 300).
        title : Optional[str]
            Custom figure title.

        Returns
        -------
        Path
            Path to the saved figure file.
        """
        out_file = Path(output_path)
        if out_file.suffix.lower() not in (".png", ".pdf"):
            out_file = out_file.with_suffix(".png")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare panels
        panels_dict = dict(data.panels) if data.panels else {}
        if not panels_dict and len(data.df.columns) > 0:
            for col in data.df.columns:
                if not col.endswith("_rolling") and not col.endswith("_mean"):
                    panels_dict[col] = {
                        "primary": col,
                        "rolling": f"{col}_rolling" if f"{col}_rolling" in data.df.columns else None,
                        "title": col.replace("_", " ").title(),
                        "unit": data.units.get(col, ""),
                        "available": True,
                    }

        panels_list = list(panels_dict.items())
        n_panels = max(1, len(panels_list))
        nrows, ncols = self._determine_grid(data.preset, n_panels)

        # Calculate figsize if not explicitly provided
        if self.figsize is not None:
            fig_w, fig_h = self.figsize
        else:
            if comparison is not None:
                fig_w = max(10.0, ncols * 7.5)
                fig_h = max(6.0, nrows * 5.0)
            else:
                fig_w = max(9.0, ncols * 7.0)
                fig_h = max(5.0, nrows * 4.0)

        fig = plt.figure(figsize=(fig_w, fig_h), facecolor="white")

        try:
            if comparison is not None:
                self._render_comparison(
                    fig=fig,
                    data=data,
                    comparison=comparison,
                    panels_list=panels_list,
                    nrows=nrows,
                    ncols=ncols,
                )
            else:
                self._render_single(
                    fig=fig,
                    data=data,
                    panels_list=panels_list,
                    nrows=nrows,
                    ncols=ncols,
                )

            # Main figure title
            preset_str = data.preset or "custom"
            preset_title = PRESET_DEFINITIONS.get(preset_str, {}).get("title", preset_str.title())
            if title:
                overall_title = title
            elif comparison is not None:
                scen_names = ", ".join(comparison.get_names())
                overall_title = f"RuFaS Scenario Comparison: {comparison.baseline.name} vs {scen_names} ({preset_title})"
            else:
                overall_title = f"RuFaS Simulation: {data.name} — {preset_title}"

            fig.suptitle(overall_title, fontsize=13, fontweight="bold", y=0.98)

            top_margin = 0.94 if nrows > 1 else 0.90
            bottom_margin = 0.08 if nrows > 1 else 0.12
            left_margin = 0.08 if ncols > 1 else 0.12
            right_margin = 0.96
            fig.subplots_adjust(top=top_margin, bottom=bottom_margin, left=left_margin, right=right_margin)
            fig.savefig(str(out_file), dpi=dpi, bbox_inches="tight")


        finally:
            plt.close(fig)

        return out_file

    def _render_single(
        self,
        fig: Any,
        data: AlignedSimulationData,
        panels_list: List[tuple[str, Dict[str, Any]]],
        nrows: int,
        ncols: int,
    ) -> None:
        outer = GridSpec(nrows, ncols, figure=fig, hspace=0.35, wspace=0.25)
        total_slots = nrows * ncols

        for idx in range(total_slots):
            r = idx // ncols
            c = idx % ncols
            ax = fig.add_subplot(outer[r, c])

            if idx >= len(panels_list):
                ax.set_visible(False)
                continue

            panel_key, panel_info = panels_list[idx]
            color = self._get_panel_color(panel_key, idx)
            title = panel_info.get("title", panel_key)
            unit = panel_info.get("unit") or data.units.get(panel_info.get("primary", ""), "")
            is_avail = panel_info.get("available", True)
            primary_col = panel_info.get("primary")
            rolling_col = panel_info.get("rolling")

            self._apply_axis_styling(ax)

            if not is_avail or not primary_col or primary_col not in data.df.columns or len(data.df) == 0:
                reason = panel_info.get("missing_reason") or f"Module '{panel_key}' not configured in simulation"
                ax.text(0.5, 0.5, reason, ha="center", va="center", transform=ax.transAxes, color="#888888", style="italic", fontsize=10, wrap=True)
                ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.grid(False)
                continue

            x = data.df.index
            y_raw = data.df[primary_col]
            has_rolling = bool(rolling_col and rolling_col in data.df.columns)

            if has_rolling:
                y_roll = data.df[rolling_col]
                ax.plot(x, y_raw, color=color, alpha=0.25, linewidth=1.0, label="Daily")
                ax.plot(x, y_roll, color=color, alpha=1.0, linewidth=2.0, label="Rolling Avg")
                ax.legend(loc="upper left", frameon=True, framealpha=0.85, fontsize=8)
            else:
                ax.plot(x, y_raw, color=color, alpha=1.0, linewidth=2.0, label="Daily")

            ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
            if unit:
                ax.set_ylabel(unit, fontsize=9, fontweight="medium")
            ax.set_xlabel("Simulation Day", fontsize=9)
            if len(x) > 0:
                ax.set_xlim(left=0, right=max(1, int(x.max())))

    def _render_comparison(
        self,
        fig: Any,
        data: AlignedSimulationData,
        comparison: ScenarioComparisonResult,
        panels_list: List[tuple[str, Dict[str, Any]]],
        nrows: int,
        ncols: int,
    ) -> None:
        outer = GridSpec(nrows, ncols, figure=fig, hspace=0.35, wspace=0.25)
        total_slots = nrows * ncols
        common_x = comparison.common_index
        base_data = comparison.baseline

        for idx in range(total_slots):
            if idx >= len(panels_list):
                continue

            r = idx // ncols
            c = idx % ncols
            inner = GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[r, c], height_ratios=[3, 1], hspace=0.15)
            ax_main = fig.add_subplot(inner[0])
            ax_delta = fig.add_subplot(inner[1], sharex=ax_main)

            panel_key, panel_info = panels_list[idx]
            base_color = self._get_panel_color(panel_key, idx)
            title = panel_info.get("title", panel_key)
            unit = panel_info.get("unit") or base_data.units.get(panel_info.get("primary", ""), "")
            is_avail = panel_info.get("available", True)
            primary_col = panel_info.get("primary")
            rolling_col = panel_info.get("rolling")

            self._apply_axis_styling(ax_main)
            self._apply_axis_styling(ax_delta)

            if not is_avail or not primary_col or primary_col not in base_data.df.columns or len(common_x) == 0:
                reason = panel_info.get("missing_reason") or f"Module '{panel_key}' not configured in simulation"
                ax_main.text(0.5, 0.5, reason, ha="center", va="center", transform=ax_main.transAxes, color="#888888", style="italic", fontsize=10, wrap=True)
                ax_main.set_title(title, fontsize=11, fontweight="bold", pad=8)
                ax_main.set_xticks([])
                ax_main.set_yticks([])
                ax_main.grid(False)
                ax_delta.set_visible(False)
                continue

            # 1. Plot Baseline on ax_main
            b_raw = base_data.df.loc[common_x, primary_col]
            has_b_roll = bool(rolling_col and rolling_col in base_data.df.columns)
            if has_b_roll:
                b_roll = base_data.df.loc[common_x, rolling_col]
                ax_main.plot(common_x, b_raw, color=base_color, alpha=0.25, linewidth=0.9, linestyle="-")
                ax_main.plot(common_x, b_roll, color=base_color, alpha=1.0, linewidth=2.2, linestyle="-", label=f"{base_data.name} (Base)")
            else:
                ax_main.plot(common_x, b_raw, color=base_color, alpha=1.0, linewidth=2.2, linestyle="-", label=f"{base_data.name} (Base)")

            # 2. Plot Scenarios on ax_main and deltas on ax_delta
            for s_idx, scen_delta in enumerate(comparison.scenarios):
                scen_ls = self.SCENARIO_LINESTYLES[s_idx % len(self.SCENARIO_LINESTYLES)]
                scen_col = self.SCENARIO_COLORS[s_idx % len(self.SCENARIO_COLORS)]
                s_df = scen_delta.data.df

                # Main curve
                if primary_col in s_df.columns:
                    s_raw = s_df.loc[common_x, primary_col]
                    has_s_roll = bool(rolling_col and rolling_col in s_df.columns)
                    if has_s_roll:
                        s_roll = s_df.loc[common_x, rolling_col]
                        ax_main.plot(common_x, s_raw, color=scen_col, alpha=0.2, linewidth=0.8, linestyle=scen_ls)
                        ax_main.plot(common_x, s_roll, color=scen_col, alpha=1.0, linewidth=1.8, linestyle=scen_ls, label=scen_delta.name)
                    else:
                        ax_main.plot(common_x, s_raw, color=scen_col, alpha=1.0, linewidth=1.8, linestyle=scen_ls, label=scen_delta.name)

                # Delta curve on ax_delta
                pct_df = scen_delta.pct_deltas
                if rolling_col and rolling_col in pct_df.columns:
                    if primary_col in pct_df.columns:
                        ax_delta.plot(common_x, pct_df.loc[common_x, primary_col], color=scen_col, alpha=0.25, linewidth=0.8, linestyle=scen_ls)
                    ax_delta.plot(common_x, pct_df.loc[common_x, rolling_col], color=scen_col, alpha=1.0, linewidth=1.6, linestyle=scen_ls)
                elif primary_col in pct_df.columns:
                    ax_delta.plot(common_x, pct_df.loc[common_x, primary_col], color=scen_col, alpha=1.0, linewidth=1.6, linestyle=scen_ls)

            ax_delta.axhline(0, color="#666666", linestyle=":", linewidth=0.9, alpha=0.8)
            ax_main.set_title(title, fontsize=11, fontweight="bold", pad=6)
            if unit:
                ax_main.set_ylabel(unit, fontsize=9, fontweight="medium")
            ax_main.legend(loc="upper left", frameon=True, framealpha=0.85, fontsize=8)
            ax_main.tick_params(labelbottom=False)
            ax_main.set_xlabel("")

            ax_delta.set_ylabel("Δ (%)", fontsize=8, fontweight="medium")
            ax_delta.set_xlabel("Simulation Day", fontsize=8)
            if len(common_x) > 0:
                ax_main.set_xlim(left=0, right=max(1, int(common_x.max())))
                ax_delta.set_xlim(left=0, right=max(1, int(common_x.max())))


class PlotlyRenderer:
    """
    Interactive multi-panel dashboard renderer using Plotly.
    Generates standalone HTML dashboards with synchronized time-series subplots,
    shared zooming/panning across panels (shared_xaxes=True), range slider timeline navigation,
    rich hovertemplates with calendar dates and units, and scenario comparison overlays.
    """

    DEFAULT_PALETTE = [
        "#1f77b4",  # Blue
        "#2ca02c",  # Green
        "#d62728",  # Red
        "#9467bd",  # Purple
        "#ff7f0e",  # Orange
        "#8c564b",  # Brown
        "#17becf",  # Teal
        "#bcbd22",  # Yellow-green
    ]

    SEMANTIC_PANEL_COLORS = {
        "milk_produced": "#1f77b4",
        "milk": "#1f77b4",
        "milk_solids": "#17becf",
        "days_in_milk": "#3366cc",
        "herd_dynamics": "#9467bd",
        "methane_emission": "#d62728",
        "methane": "#d62728",
        "carbon_intensity": "#ff7f0e",
        "energy_consumption": "#bcbd22",
        "manure_excretion": "#8c564b",
        "manure_nutrients": "#a05d56",
        "storage_gas_loss": "#d62728",
        "manure_applied": "#8c564b",
        "applied_manure": "#8c564b",
        "feed_cost": "#e377c2",
        "transpiration": "#2ca02c",
        "transp": "#2ca02c",
        "soil_emissions": "#ff7f0e",
        "soil_water": "#1f77b4",
    }

    SCENARIO_COLORS = ["#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#17becf"]
    SCENARIO_DASH = ["dash", "dot", "dashdot", "longdash"]

    def __init__(self, template: str = "plotly_white"):
        self.template = template

    def _determine_grid(self, preset: Optional[str], n_panels: int) -> tuple[int, int]:
        """Calculates (nrows, ncols) grid based on preset and number of panels."""
        norm_preset = (preset or "custom").strip().lower().replace("_", "-")
        if norm_preset == "executive":
            if n_panels <= 6:
                return (3, 2)
            ncols = 2
            return ((n_panels + ncols - 1) // ncols, ncols)
        elif norm_preset in ("animal", "eee", "field-crops", "manure"):
            if n_panels <= 4:
                return (2, 2)
            ncols = 2
            return ((n_panels + ncols - 1) // ncols, ncols)
        else:
            if n_panels <= 1:
                return (1, 1)
            elif n_panels == 2:
                return (1, 2)
            elif n_panels <= 4:
                return (2, 2)
            elif n_panels <= 6:
                return (3, 2)
            else:
                ncols = 2
                return ((n_panels + ncols - 1) // ncols, ncols)

    def _get_panel_color(self, panel_key: str, index: int) -> str:
        """Determines semantic color for a panel key, falling back to palette."""
        clean_key = panel_key.lower().strip()
        for k, col in self.SEMANTIC_PANEL_COLORS.items():
            if k in clean_key:
                return col
        return self.DEFAULT_PALETTE[index % len(self.DEFAULT_PALETTE)]

    def _build_hover_config(
        self,
        data: AlignedSimulationData,
        unit: str,
        x_index: Optional[pd.Index] = None,
        pct_deltas: Optional[pd.Series] = None,
    ) -> tuple[Optional[np.ndarray], str]:
        """
        Builds customdata matrix and hovertemplate for a trace.
        """
        cal_s = (
            data.calendar_years.reindex(x_index)
            if (data.calendar_years is not None and x_index is not None)
            else data.calendar_years
        )
        jul_s = (
            data.julian_days.reindex(x_index)
            if (data.julian_days is not None and x_index is not None)
            else data.julian_days
        )
        pct_s = (
            pct_deltas.reindex(x_index)
            if (pct_deltas is not None and x_index is not None)
            else pct_deltas
        )

        has_years = cal_s is not None
        has_days = jul_s is not None
        has_pct = pct_s is not None

        unit_str = f" {unit}" if unit else ""

        if has_years and has_days:
            years = cal_s.values
            days = jul_s.values
            if has_pct:
                custom = np.column_stack([years, days, pct_s.fillna(0.0).values])
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    "Calendar: Year %{customdata[0]:.0f}, Day %{customdata[1]:.0f}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<br>"
                    "Δ: %{customdata[2]:+.1f}%<extra></extra>"
                )
            else:
                custom = np.column_stack([years, days])
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    "Calendar: Year %{customdata[0]:.0f}, Day %{customdata[1]:.0f}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<extra></extra>"
                )
        elif has_years:
            years = cal_s.values
            if has_pct:
                custom = np.column_stack([years, pct_s.fillna(0.0).values])
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    "Calendar: Year %{customdata[0]:.0f}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<br>"
                    "Δ: %{customdata[1]:+.1f}%<extra></extra>"
                )
            else:
                custom = np.column_stack([years])
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    "Calendar: Year %{customdata[0]:.0f}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<extra></extra>"
                )
        else:
            if has_pct:
                custom = np.column_stack([pct_s.fillna(0.0).values])
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<br>"
                    "Δ: %{customdata[0]:+.1f}%<extra></extra>"
                )
            else:
                custom = None
                template = (
                    "<b>%{fullData.name}</b><br>"
                    "Simulation Day: %{x}<br>"
                    f"Value: %{{y:.2f}}{unit_str}<extra></extra>"
                )

        return custom, template

    def render(
        self,
        data: AlignedSimulationData,
        output_path: Union[str, Path],
        comparison: Optional[ScenarioComparisonResult] = None,
        title: Optional[str] = None,
    ) -> Path:
        """
        Renders interactive multi-panel dashboard to standalone HTML.

        Parameters
        ----------
        data : AlignedSimulationData
            Aligned simulation dataset.
        output_path : Union[str, Path]
            Destination file path (.html).
        comparison : Optional[ScenarioComparisonResult]
            Scenario comparison result with baseline, scenarios, and percentage deltas.
        title : Optional[str]
            Custom figure title.

        Returns
        -------
        Path
            Path to the saved standalone HTML file.
        """
        out_file = Path(output_path)
        if out_file.suffix.lower() != ".html":
            out_file = out_file.with_suffix(".html")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare panels
        panels_dict = dict(data.panels) if data.panels else {}
        if not panels_dict and len(data.df.columns) > 0:
            for col in data.df.columns:
                if not col.endswith("_rolling") and not col.endswith("_mean"):
                    panels_dict[col] = {
                        "primary": col,
                        "rolling": f"{col}_rolling" if f"{col}_rolling" in data.df.columns else None,
                        "title": col.replace("_", " ").title(),
                        "unit": data.units.get(col, ""),
                        "available": True,
                    }

        panels_list = list(panels_dict.items())
        n_panels = max(1, len(panels_list))
        nrows, ncols = self._determine_grid(data.preset, n_panels)

        # Build subplot titles
        subplot_titles = []
        for idx in range(nrows * ncols):
            if idx < len(panels_list):
                _, p_info = panels_list[idx]
                subplot_titles.append(p_info.get("title", f"Panel {idx+1}"))
            else:
                subplot_titles.append("")

        fig = make_subplots(
            rows=nrows,
            cols=ncols,
            shared_xaxes=True,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.08,
        )

        if comparison is not None:
            self._render_comparison(
                fig=fig,
                comparison=comparison,
                panels_list=panels_list,
                nrows=nrows,
                ncols=ncols,
            )
        else:
            self._render_single(
                fig=fig,
                data=data,
                panels_list=panels_list,
                nrows=nrows,
                ncols=ncols,
            )

        # Synchronize all x-axes
        fig.update_xaxes(matches="x")

        # Range slider on the bottom axis for timeline navigation
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.04), row=nrows, col=1)

        # Axis styling and labels
        for idx, (p_key, p_info) in enumerate(panels_list):
            r = idx // ncols + 1
            c = idx % ncols + 1
            unit = p_info.get("unit") or data.units.get(p_info.get("primary", ""), "")
            if unit and p_info.get("available", True):
                fig.update_yaxes(title_text=unit, row=r, col=c)

        for c in range(1, ncols + 1):
            fig.update_xaxes(title_text="Simulation Day", row=nrows, col=c)

        # Hide extra empty subplots
        for extra_idx in range(len(panels_list), nrows * ncols):
            er = extra_idx // ncols + 1
            ec = extra_idx % ncols + 1
            fig.update_xaxes(visible=False, row=er, col=ec)
            fig.update_yaxes(visible=False, row=er, col=ec)

        # Overall dashboard title
        preset_str = data.preset or "custom"
        preset_title = PRESET_DEFINITIONS.get(preset_str, {}).get("title", preset_str.title())
        if title:
            overall_title = title
        elif comparison is not None:
            scen_names = ", ".join(comparison.get_names())
            overall_title = f"RuFaS Scenario Comparison: {comparison.baseline.name} vs {scen_names} ({preset_title})"
        else:
            overall_title = f"RuFaS Simulation: {data.name} — {preset_title}"

        fig_height = max(550, nrows * 360)
        fig.update_layout(
            title=dict(
                text=overall_title,
                font=dict(size=16, family="sans-serif", color="#111111"),
                x=0.5,
                xanchor="center",
            ),
            template=self.template,
            hovermode="x",
            height=fig_height,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(size=10),
            ),
            margin=dict(l=60, r=40, t=80, b=60),
        )

        fig.write_html(str(out_file), include_plotlyjs=True, full_html=True)
        return out_file

    def _render_single(
        self,
        fig: Any,
        data: AlignedSimulationData,
        panels_list: List[tuple[str, Dict[str, Any]]],
        nrows: int,
        ncols: int,
    ) -> None:
        for idx, (panel_key, panel_info) in enumerate(panels_list):
            r = idx // ncols + 1
            c = idx % ncols + 1
            color = self._get_panel_color(panel_key, idx)
            unit = panel_info.get("unit") or data.units.get(panel_info.get("primary", ""), "")
            is_avail = panel_info.get("available", True)
            primary_col = panel_info.get("primary")
            rolling_col = panel_info.get("rolling")

            if not is_avail or not primary_col or primary_col not in data.df.columns or len(data.df) == 0:
                reason = panel_info.get("missing_reason") or f"Module '{panel_key}' not configured in simulation"
                fig.add_annotation(
                    text=f"<i>{reason}</i>",
                    showarrow=False,
                    font=dict(size=11, color="#888888"),
                    row=r,
                    col=c,
                )
                fig.update_xaxes(showticklabels=False, showgrid=False, row=r, col=c)
                fig.update_yaxes(showticklabels=False, showgrid=False, row=r, col=c)
                continue

            x = data.df.index
            y_raw = data.df[primary_col]
            has_rolling = bool(rolling_col and rolling_col in data.df.columns)
            custom, template = self._build_hover_config(data, unit, x_index=x)

            if has_rolling:
                y_roll = data.df[rolling_col]
                # Daily trace (semitransparent)
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y_raw,
                        name="Daily",
                        legendgroup="Daily",
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=color, width=1.0),
                        opacity=0.35,
                        customdata=custom,
                        hovertemplate=template,
                    ),
                    row=r,
                    col=c,
                )
                # Rolling trace (solid)
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y_roll,
                        name="Rolling Avg",
                        legendgroup="Rolling Avg",
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=color, width=2.5),
                        customdata=custom,
                        hovertemplate=template,
                    ),
                    row=r,
                    col=c,
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y_raw,
                        name="Daily",
                        legendgroup="Daily",
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=color, width=2.2),
                        customdata=custom,
                        hovertemplate=template,
                    ),
                    row=r,
                    col=c,
                )

    def _render_comparison(
        self,
        fig: Any,
        comparison: ScenarioComparisonResult,
        panels_list: List[tuple[str, Dict[str, Any]]],
        nrows: int,
        ncols: int,
    ) -> None:
        common_x = comparison.common_index
        base_data = comparison.baseline

        for idx, (panel_key, panel_info) in enumerate(panels_list):
            r = idx // ncols + 1
            c = idx % ncols + 1
            base_color = self._get_panel_color(panel_key, idx)
            unit = panel_info.get("unit") or base_data.units.get(panel_info.get("primary", ""), "")
            is_avail = panel_info.get("available", True)
            primary_col = panel_info.get("primary")
            rolling_col = panel_info.get("rolling")

            if not is_avail or not primary_col or primary_col not in base_data.df.columns or len(common_x) == 0:
                reason = panel_info.get("missing_reason") or f"Module '{panel_key}' not configured in simulation"
                fig.add_annotation(
                    text=f"<i>{reason}</i>",
                    showarrow=False,
                    font=dict(size=11, color="#888888"),
                    row=r,
                    col=c,
                )
                fig.update_xaxes(showticklabels=False, showgrid=False, row=r, col=c)
                fig.update_yaxes(showticklabels=False, showgrid=False, row=r, col=c)
                continue

            # 1. Plot Baseline
            b_raw = base_data.df.loc[common_x, primary_col]
            has_b_roll = bool(rolling_col and rolling_col in base_data.df.columns)
            custom_base, template_base = self._build_hover_config(base_data, unit, x_index=common_x)

            if has_b_roll:
                b_roll = base_data.df.loc[common_x, rolling_col]
                fig.add_trace(
                    go.Scatter(
                        x=common_x,
                        y=b_raw,
                        name=f"{base_data.name} (Daily)",
                        legendgroup=base_data.name,
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=base_color, width=1.0),
                        opacity=0.25,
                        customdata=custom_base,
                        hovertemplate=template_base,
                    ),
                    row=r,
                    col=c,
                )
                fig.add_trace(
                    go.Scatter(
                        x=common_x,
                        y=b_roll,
                        name=f"{base_data.name} (Base)",
                        legendgroup=base_data.name,
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=base_color, width=2.5),
                        customdata=custom_base,
                        hovertemplate=template_base,
                    ),
                    row=r,
                    col=c,
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=common_x,
                        y=b_raw,
                        name=f"{base_data.name} (Base)",
                        legendgroup=base_data.name,
                        showlegend=(idx == 0),
                        mode="lines",
                        line=dict(color=base_color, width=2.2),
                        customdata=custom_base,
                        hovertemplate=template_base,
                    ),
                    row=r,
                    col=c,
                )

            # 2. Plot Scenarios
            for s_idx, scen_delta in enumerate(comparison.scenarios):
                scen_col = self.SCENARIO_COLORS[s_idx % len(self.SCENARIO_COLORS)]
                scen_dash = self.SCENARIO_DASH[s_idx % len(self.SCENARIO_DASH)]
                s_df = scen_delta.data.df

                if primary_col not in s_df.columns:
                    continue

                s_raw = s_df.loc[common_x, primary_col]
                has_s_roll = bool(rolling_col and rolling_col in s_df.columns)

                pct_series = (
                    scen_delta.pct_deltas.loc[common_x, primary_col]
                    if primary_col in scen_delta.pct_deltas.columns
                    else None
                )
                pct_roll_series = (
                    scen_delta.pct_deltas.loc[common_x, rolling_col]
                    if (rolling_col and rolling_col in scen_delta.pct_deltas.columns)
                    else pct_series
                )

                custom_scen_raw, template_scen_raw = self._build_hover_config(
                    scen_delta.data, unit, x_index=common_x, pct_deltas=pct_series
                )
                custom_scen_roll, template_scen_roll = self._build_hover_config(
                    scen_delta.data, unit, x_index=common_x, pct_deltas=pct_roll_series
                )

                if has_s_roll:
                    s_roll = s_df.loc[common_x, rolling_col]
                    fig.add_trace(
                        go.Scatter(
                            x=common_x,
                            y=s_raw,
                            name=f"{scen_delta.name} (Daily)",
                            legendgroup=scen_delta.name,
                            showlegend=(idx == 0),
                            mode="lines",
                            line=dict(color=scen_col, width=1.0, dash=scen_dash),
                            opacity=0.25,
                            customdata=custom_scen_raw,
                            hovertemplate=template_scen_raw,
                        ),
                        row=r,
                        col=c,
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=common_x,
                            y=s_roll,
                            name=scen_delta.name,
                            legendgroup=scen_delta.name,
                            showlegend=(idx == 0),
                            mode="lines",
                            line=dict(color=scen_col, width=2.2, dash=scen_dash),
                            customdata=custom_scen_roll,
                            hovertemplate=template_scen_roll,
                        ),
                        row=r,
                        col=c,
                    )
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=common_x,
                            y=s_raw,
                            name=scen_delta.name,
                            legendgroup=scen_delta.name,
                            showlegend=(idx == 0),
                            mode="lines",
                            line=dict(color=scen_col, width=2.2, dash=scen_dash),
                            customdata=custom_scen_raw,
                            hovertemplate=template_scen_raw,
                        ),
                        row=r,
                        col=c,
                    )


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

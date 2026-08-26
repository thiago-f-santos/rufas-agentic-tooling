#!/usr/bin/env python3
"""
RuFaS Analyzer Tool
Parses simulation output CSVs, summarizes herd performance,
greenhouse gas (GHG) emissions, field yields, and mass balance.
"""

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def extract_variable_unit(col_name: str) -> Optional[str]:
    """Extracts unit from variable name if present in trailing parentheses, e.g. 'foo (kg)' -> 'kg'."""
    match = re.search(r"\(([^()]+)\)\s*$", col_name)
    return match.group(1).strip() if match else None


def categorize_variable_name(col_name: str) -> str:
    """Categorizes a RuFaS simulation column into its biophysical/economic module."""
    parts = col_name.split(".")
    cls_name = parts[0].lower() if parts else ""
    col_lower = col_name.lower()

    # 1. First check top-level class / namespace
    if any(k in cls_name for k in ["animal", "ration", "lactation", "herd", "breeding", "cow", "heifer", "calf"]):
        return "animal"
    if any(k in cls_name for k in ["field", "soil", "crop", "tillage", "soilorganicmatter"]):
        return "field_soil"
    if any(k in cls_name for k in ["feedmanager", "purchasedfeedstorage", "feedstorage", "cropstorage"]):
        return "feed_storage"
    if any(k in cls_name for k in ["manure", "singlestream", "parlorcleaning", "alleyscraper", "lagoon", "digester", "compost", "separator"]):
        return "manure"
    if any(k in cls_name for k in ["emissionsestimator", "economy", "energy", "economic"]):
        return "eee"
    if any(k in cls_name for k in ["weather", "rufastime", "taskmanager", "disclaimer"]):
        return "general"

    # 2. Fallback to keyword matching across entire column name
    if any(k in col_lower for k in ["feedmanager", "purchasedfeedstorage", "storage_instance", "feed_cost", "feed_amount"]):
        return "feed_storage"
    if any(k in col_lower for k in ["emissionsestimator", "purchased_feed_emissions", "land_use_change_emissions", "economy", "energy_use", "tractor", "diesel", "electric"]):
        return "eee"
    if any(k in col_lower for k in ["manure", "scraper", "separator", "digester", "lagoon", "parlorcleaning"]):
        return "manure"
    if any(k in col_lower for k in ["field", "soil", "crop", "tillage", "fertiliz", "transpiration", "residue", "drainage"]):
        return "field_soil"
    if any(k in col_lower for k in ["animal", "ration", "lactation", "herd", "cow", "heifer", "calf"]):
        return "animal"
    return "general"


def summarize_modular_variables(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Summarizes columns in a RuFaS output DataFrame categorized by module.
    Returns per-module column counts, extracted units, and summary metrics for numeric columns.
    """
    modular_summary: Dict[str, Any] = {
        "modules": {
            "animal": {"total_variables": 0, "variables": []},
            "field_soil": {"total_variables": 0, "variables": []},
            "feed_storage": {"total_variables": 0, "variables": []},
            "manure": {"total_variables": 0, "variables": []},
            "eee": {"total_variables": 0, "variables": []},
            "general": {"total_variables": 0, "variables": []},
        },
        "total_variables": len(df.columns),
    }

    for col in df.columns:
        module = categorize_variable_name(col)
        unit = extract_variable_unit(col)
        var_info: Dict[str, Any] = {
            "name": col,
            "unit": unit,
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            if not df.empty:
                var_info["mean"] = float(df[col].mean()) if pd.notnull(df[col].mean()) else None
                var_info["min"] = float(df[col].min()) if pd.notnull(df[col].min()) else None
                var_info["max"] = float(df[col].max()) if pd.notnull(df[col].max()) else None
                var_info["non_null_count"] = int(df[col].count())
        modular_summary["modules"][module]["total_variables"] += 1
        modular_summary["modules"][module]["variables"].append(var_info)

    return modular_summary


def summarize_output_directory(output_dir: Path) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "output_directory": str(output_dir),
        "csv_files_found": [],
        "metrics": {},
        "errors_detected": False,
        "error_messages": [],
    }

    if not output_dir.exists():
        summary["errors_detected"] = True
        summary["error_messages"].append(f"Directory {output_dir} does not exist.")
        return summary

    # Check logs/errors
    errors_file = output_dir / "logs" / "errors.txt"
    if errors_file.exists() and errors_file.stat().st_size > 0:
        with open(errors_file, "r", encoding="utf-8") as f:
            err_content = f.read().strip()
            if err_content:
                summary["errors_detected"] = True
                summary["error_messages"].append(err_content)

    csv_files = sorted(set(list(output_dir.glob("*.csv")) + list(output_dir.glob("*/*.csv"))))
    summary["csv_files_found"] = [str(p.relative_to(output_dir)) for p in csv_files]

    # Analyze CSV data if available
    for csv_file in csv_files:
        filename = csv_file.name.lower()
        try:
            if HAS_PANDAS:
                df = pd.read_csv(csv_file, low_memory=False)
                col_names = df.columns.tolist()

                # Modular variable breakdown for simulation output files
                is_sim_csv = (
                    "saved_variables" in filename
                    or csv_file.parent.name.lower() == "csvs"
                    or len(col_names) > 50
                ) and ("usage_counts" not in filename and "metadata_properties" not in filename)

                if is_sim_csv:
                    if "modular_summary" not in summary or summary["modular_summary"]["total_variables"] < len(col_names):
                        summary["modular_summary"] = summarize_modular_variables(df)
                        summary["metrics"]["modular_variable_counts"] = {
                            mod: data["total_variables"]
                            for mod, data in summary["modular_summary"]["modules"].items()
                        }

                if "animal" in filename or "herd" in filename or "freestall" in filename or "dairy" in filename:
                    milk_cols = [c for c in col_names if "milk" in c.lower() or "yield" in c.lower()]
                    if milk_cols:
                        summary["metrics"]["milk_variables"] = {
                            c: {"mean": float(df[c].mean()), "max": float(df[c].max()), "sum": float(df[c].sum())}
                            for c in milk_cols if pd.api.types.is_numeric_dtype(df[c])
                        }

                if "emission" in filename or "ghg" in filename or "freestall" in filename:
                    ch4_cols = [c for c in col_names if "ch4" in c.lower() or "methane" in c.lower()]
                    n2o_cols = [c for c in col_names if "n2o" in c.lower() or "nitrous" in c.lower()]
                    co2_cols = [c for c in col_names if "co2" in c.lower() or "carbon" in c.lower()]

                    if ch4_cols or n2o_cols or co2_cols:
                        summary["metrics"]["emissions_summary"] = {}
                        for col in ch4_cols + n2o_cols + co2_cols:
                            if pd.api.types.is_numeric_dtype(df[col]):
                                summary["metrics"]["emissions_summary"][col] = {
                                    "total": float(df[col].sum()),
                                    "daily_mean": float(df[col].mean()),
                                }
            else:
                with open(csv_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows and reader.fieldnames:
                        summary["metrics"][csv_file.name] = {
                            "rows_count": len(rows),
                            "columns_count": len(reader.fieldnames),
                        }
        except Exception as e:
            summary["error_messages"].append(f"Error parsing CSV {csv_file.name}: {e}")

    return summary


def print_markdown_report(summary: Dict[str, Any]) -> None:
    print("\n# 📊 RuFaS Simulation Analysis Report\n")
    print(f"- **Output Directory**: `{summary['output_directory']}`")
    print(f"- **CSV Files Count**: {len(summary['csv_files_found'])}")

    if summary["errors_detected"]:
        print("\n### ⚠️ Errors / Warnings Detected in Logs")
        for err in summary["error_messages"]:
            print(f"```text\n{err}\n```")

    if summary["csv_files_found"]:
        print("\n### 📁 Output CSV Files")
        for f in summary["csv_files_found"]:
            print(f"- `{f}`")

    if "modular_summary" in summary:
        mod_data = summary["modular_summary"]["modules"]
        print("\n### 🧩 Modular Variable Taxonomy Breakdown")
        print(f"- **Total Variables Tracked**: {summary['modular_summary']['total_variables']}")
        print(f"- **Animal Module**: {mod_data.get('animal', {}).get('total_variables', 0)} variables")
        print(f"- **Field & Soil Module**: {mod_data.get('field_soil', {}).get('total_variables', 0)} variables")
        print(f"- **Feed Storage Module**: {mod_data.get('feed_storage', {}).get('total_variables', 0)} variables")
        print(f"- **Manure Module**: {mod_data.get('manure', {}).get('total_variables', 0)} variables")
        print(f"- **EEE (Economics, Emissions, Energy)**: {mod_data.get('eee', {}).get('total_variables', 0)} variables")
        print(f"- **General / System / Weather**: {mod_data.get('general', {}).get('total_variables', 0)} variables")

    metrics = summary.get("metrics", {})
    if "milk_variables" in metrics and metrics["milk_variables"]:
        print("\n### 🥛 Animal & Milk Production Summary")
        for var, stats in metrics["milk_variables"].items():
            print(f"- **{var}**: Mean = {stats['mean']:.2f}, Max = {stats['max']:.2f}, Total = {stats['sum']:.2f}")

    if "emissions_summary" in metrics and metrics["emissions_summary"]:
        print("\n### 🌍 Greenhouse Gas (GHG) & Emissions Summary")
        for var, stats in metrics["emissions_summary"].items():
            print(f"- **{var}**: Total = {stats['total']:.2f}, Daily Mean = {stats['daily_mean']:.2f}")

    if not summary["csv_files_found"] and not summary["errors_detected"]:
        print("\n> ℹ️ No CSV files found. If the simulation just ran, ensure `csv_all_variables.txt` filter is active in `output/output_filters/`.")


def main() -> None:
    parser = argparse.ArgumentParser(description="RuFaS Output Analyzer: Summarize simulation CSVs and emissions.")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="../RuFaS/output",
        help="Path to RuFaS output directory (default: ../RuFaS/output)",
    )
    args = parser.parse_args()
    out_path = Path(args.output_dir).resolve()

    summary = summarize_output_directory(out_path)
    print_markdown_report(summary)


if __name__ == "__main__":
    main()

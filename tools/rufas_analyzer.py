#!/usr/bin/env python3
"""
RuFaS Analyzer Tool
Parses simulation output CSVs, summarizes herd performance,
greenhouse gas (GHG) emissions, field yields, and mass balance.
"""

import argparse
import sys
from pathlib import Path
import csv

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


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

    csv_files = list(output_dir.glob("*.csv")) + list(output_dir.glob("*/*.csv"))
    summary["csv_files_found"] = [str(p.relative_to(output_dir)) for p in csv_files]

    # Analyze CSV data if available
    for csv_file in csv_files:
        filename = csv_file.name.lower()
        try:
            if HAS_PANDAS:
                df = pd.read_csv(csv_file)
                col_names = df.columns.tolist()

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

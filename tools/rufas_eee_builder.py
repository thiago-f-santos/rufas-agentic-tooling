#!/usr/bin/env python3
"""
RuFaS EEE Dataset Builder for Brazil (Minas Gerais)
Generates canonical regionalized datasets for purchased feeds emissions,
direct Land Use Change (dLUC), local grid electricity, and international USD costs.
"""

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Optional

from tools.config import get_rufas_root

# Scientific Factors (GFLI v3.0, Embrapa, MCTI)
# Format: {feed_id: (production_kg_co2e_per_kg_dm, dluc_kg_co2e_per_kg_dm)}
PRIORITY_FEED_FACTORS: Dict[str, tuple[float, float]] = {
    "23": (1.10, 0.00),    # Blood meal, low dRUP (GFLI / Ecoinvent BR)
    "44": (0.28, 0.15),    # Corn grain, ground, dry (GFLI Maize grain, at farm/BR)
    "50": (0.18, 0.00),    # Corn silage, immature (Embrapa Milho e Sorgo)
    "95": (0.22, 0.00),    # Grass hay, mature (Embrapa Pecuária Sudeste)
    "104": (0.22, 0.00),   # Grass-legume silage (Embrapa Pecuária Sudeste)
    "110": (0.20, 0.00),   # Legume forage silage (Embrapa Pecuária Sudeste)
    "170": (0.45, 1.85),   # Soybean meal, solvent extracted (GFLI BR PAS 2050 20-yr dLUC)
    "202": (0.90, 0.00),   # Whole milk (Embrapa Gado de Leite)
    "216": (0.55, 0.60),   # Calf starter 18% PB (Mass-balance: 65% corn, 30% soy, 5% min)
    "301": (0.75, 0.00),   # Farm ES Mineral Mix (Mass-balance: 45% dicalcium P, 25% salt, 20% lime)
    "302": (0.35, 0.10),   # Farm ES BP Blend (By-product blend: citrus pulp, wheat midds, corn)
}

REGIONS_TO_REGISTER: List[int] = [31, 3148004]


def get_base_feed_columns(rufas_root: Path) -> List[str]:
    """Reads all feed column headers from RuFaS default emissions file, ensuring priority feeds are included."""
    base_file = rufas_root / "input" / "data" / "EEE" / "full_feeds_emissions_July2024_interpolated_regional_average.csv"
    if not base_file.exists():
        # Fallback to priority feed columns if base file not found
        return ["region_code"] + list(PRIORITY_FEED_FACTORS.keys())

    with open(base_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    # Ensure region_code is the first column and priority feeds are present
    cols = ["region_code"] + [col for col in header if col not in ("county_code", "region_code")]
    for fid in PRIORITY_FEED_FACTORS.keys():
        if fid not in cols:
            cols.append(fid)
    return cols


def build_minas_gerais_eee_datasets(output_dir: Path, rufas_root: Optional[Path] = None) -> Dict[str, Path]:
    """
    Builds the 4 canonical EEE datasets for Minas Gerais.
    Returns dictionary mapping filename to Path.
    """
    if rufas_root is None:
        rufas_root = get_rufas_root()

    output_dir.mkdir(parents=True, exist_ok=True)
    all_columns = get_base_feed_columns(rufas_root)
    feed_columns = [col for col in all_columns if col != "region_code"]

    created_files: Dict[str, Path] = {}

    # 1. Purchased Feeds Emissions
    p1 = output_dir / "purchased_feeds_emissions_minas_gerais.csv"
    with open(p1, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        for reg in REGIONS_TO_REGISTER:
            row: Dict[str, str | float] = {"region_code": reg}
            for fid in feed_columns:
                prod_val = PRIORITY_FEED_FACTORS.get(str(fid), (0.0, 0.0))[0]
                row[fid] = prod_val
            writer.writerow(row)
    created_files[p1.name] = p1

    # 2. Purchased Feed Land Use Change Emissions (dLUC)
    p2 = output_dir / "purchased_feed_land_use_change_emissions_minas_gerais.csv"
    with open(p2, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        for reg in REGIONS_TO_REGISTER:
            row = {"region_code": reg}
            for fid in feed_columns:
                luc_val = PRIORITY_FEED_FACTORS.get(str(fid), (0.0, 0.0))[1]
                row[fid] = luc_val
            writer.writerow(row)
    created_files[p2.name] = p2

    # 3. Default Emissions (Tillage & Local Emissions)
    p3 = output_dir / "default_emissions_minas_gerais.csv"
    with open(p3, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["alfalfa_tillage_emissions", "corn_grain_tillage_emissions", "corn_silage_tillage_emissions"])
        writer.writerow([500, 300, 400])
    created_files[p3.name] = p3

    # 4. Default Costs (International USD equivalent for MG 2021-2022)
    p4 = output_dir / "default_costs_minas_gerais.csv"
    with open(p4, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["diesel_cost_gal", "electricity_cost_kwh", "natural_gas_cost_kwh", "water_cost_gal"])
        writer.writerow([4.16, 0.12, 0.053, 0.008])
    created_files[p4.name] = p4

    return created_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RuFaS EEE regional datasets for Minas Gerais, Brazil.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Destination directory for generated CSV files.",
    )
    args = parser.parse_args()

    rufas_root = get_rufas_root()
    dest_dir = args.output_dir if args.output_dir else (rufas_root / "input" / "data" / "EEE")

    print(f"🔨 Generating Minas Gerais EEE datasets into: {dest_dir}")
    files = build_minas_gerais_eee_datasets(dest_dir, rufas_root)
    for name, p in files.items():
        print(f"  ✓ Created {name} ({p.stat().st_size} bytes)")
    print("✅ All Minas Gerais EEE datasets generated successfully.")


if __name__ == "__main__":
    main()

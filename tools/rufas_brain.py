#!/usr/bin/env python3
"""
RuFaS Graph Memory Brain & Correlation Engine
Embedded KùzuDB property graph database for biophysical ontology, simulation history,
statistical cross-run correlations, and Obsidian knowledge graph export.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import kuzu

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("rufas_brain")

# Schema DDL Definitions
NODE_TABLES = [
    """
    CREATE NODE TABLE IF NOT EXISTS Module (
        name STRING,
        description STRING,
        manager_class STRING,
        PRIMARY KEY(name)
    );
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS ConfigBlob (
        name STRING,
        title STRING,
        file_path STRING,
        description STRING,
        format_type STRING,
        PRIMARY KEY(name)
    );
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS InputParameter (
        id STRING,
        blob_name STRING,
        param_name STRING,
        data_type STRING,
        unit STRING,
        default_value STRING,
        description STRING,
        PRIMARY KEY(id)
    );
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS OutputVariable (
        name STRING,
        module STRING,
        unit STRING,
        category STRING,
        reporter_class STRING,
        description STRING,
        PRIMARY KEY(name)
    );
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS SimulationRun (
        run_id STRING,
        scenario_name STRING,
        execution_date STRING,
        start_date STRING,
        end_date STRING,
        duration_days INT64,
        random_seed INT64,
        status STRING,
        PRIMARY KEY(run_id)
    );
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS RunMetric (
        id STRING,
        run_id STRING,
        var_name STRING,
        mean_val DOUBLE,
        min_val DOUBLE,
        max_val DOUBLE,
        sum_val DOUBLE,
        non_null_count INT64,
        PRIMARY KEY(id)
    );
    """,
]

REL_TABLES = [
    """
    CREATE REL TABLE IF NOT EXISTS CONFIG_OF (
        FROM ConfigBlob TO Module
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS CONTAINS_PARAM (
        FROM ConfigBlob TO InputParameter
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS CAUSALLY_INFLUENCES (
        FROM InputParameter TO OutputVariable,
        pathway STRING,
        mechanism STRING
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS SIMULATED_WITH (
        FROM SimulationRun TO InputParameter,
        value STRING
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS GENERATED_METRIC (
        FROM SimulationRun TO RunMetric
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS OF_VARIABLE (
        FROM RunMetric TO OutputVariable
    );
    """,
    """
    CREATE REL TABLE IF NOT EXISTS CORRELATES_WITH (
        FROM InputParameter TO OutputVariable,
        pearson_r DOUBLE,
        spearman_r DOUBLE,
        p_value DOUBLE,
        sample_size INT64
    );
    """,
]


def init_brain_database(db_path: Union[str, Path] = "data/rufas_brain.kuzu") -> kuzu.Connection:
    """
    Initialize or connect to the KùzuDB RuFaS Graph Memory Brain database.
    Creates all required node and relationship tables if they do not already exist.

    Args:
        db_path: Path to the KùzuDB database folder or ':memory:' for transient databases.

    Returns:
        kuzu.Connection instance to the initialized database.
    """
    db_path_str = str(db_path)
    if db_path_str != ":memory:":
        target_path = Path(db_path_str)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        db = kuzu.Database(db_path_str)
    else:
        db = kuzu.Database(":memory:")

    conn = kuzu.Connection(db)

    # Initialize Node Tables
    for stmt in NODE_TABLES:
        conn.execute(stmt.strip())

    # Initialize Rel Tables
    for stmt in REL_TABLES:
        conn.execute(stmt.strip())

    return conn


# Canonical Modules Definition
CANONICAL_MODULES: List[Dict[str, str]] = [
    {
        "name": "animal",
        "description": "Herd dynamics, lactation, DMI, enteric methane, excretion",
        "manager_class": "HerdManager",
    },
    {
        "name": "field_soil",
        "description": "Multi-layer hydrology, soil biogeochemistry, crop phenology, harvest",
        "manager_class": "FieldManager",
    },
    {
        "name": "feed_storage",
        "description": "Storage inventory, spoilage degradation, feed purchasing",
        "manager_class": "FeedManager",
    },
    {
        "name": "manure",
        "description": "Housing scraping, solid-liquid separation, digesters, lagoons",
        "manager_class": "ManureManager",
    },
    {
        "name": "eee",
        "description": "Economics, ASABE tractor fuel, electricity, Scope 1-3 GHG lifecycle",
        "manager_class": "EEEManager",
    },
]


def classify_config_blob_module(blob_name: str) -> str:
    """Categorizes a configuration blob into its owning biophysical or economic module."""
    blob_lower = blob_name.lower()
    if any(k in blob_lower for k in ["animal", "lactation", "semen", "phenotype", "herd"]):
        return "animal"
    if any(k in blob_lower for k in ["field", "soil", "crop", "corn", "alf", "fertilizer", "tillage", "weather"]):
        return "field_soil"
    if any(k in blob_lower for k in ["feed_storage", "feed", "nrc", "nasem", "user_feed"]):
        return "feed_storage"
    if any(k in blob_lower for k in ["manure_processor", "manure_management"]):
        return "manure"
    if "manure_schedule" in blob_lower:
        return "field_soil"
    return "eee"


def extract_variable_unit(col_name: str) -> Optional[str]:
    """Extracts unit from variable name if present in trailing parentheses, e.g. 'foo (kg)' -> 'kg'."""
    import re
    match = re.search(r"\(([^()]+)\)\s*$", col_name)
    return match.group(1).strip() if match else None


def categorize_variable_name(col_name: str) -> str:
    """Categorizes a RuFaS simulation column into its biophysical/economic module."""
    parts = col_name.split(".")
    cls_name = parts[0].lower() if parts else ""
    col_lower = col_name.lower()

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


def infer_variable_category(var_name: str, module: str) -> str:
    """Infers the functional domain category of a RuFaS output variable."""
    name_l = var_name.lower()
    if any(k in name_l for k in ["emission", "methane", "ch4", "n2o", "co2", "ghg", "ammonia"]):
        return "emissions"
    if any(k in name_l for k in ["population", "count", "number_of", "cows", "heifers", "calves", "breed"]):
        return "population"
    if any(k in name_l for k in ["milk", "yield", "harvest", "production", "produced"]):
        return "production"
    if any(k in name_l for k in ["water", "drainage", "moisture", "hydrology", "transpiration", "runoff", "evaporation", "precipitation", "percolation"]):
        return "hydrology"
    if any(k in name_l for k in ["carbon", "nitrogen", "phosphorus", "som", "pool", "manure", "ash", "dm", "dry_matter"]):
        return "biogeochemistry"
    if any(k in name_l for k in ["cost", "price", "economic", "fuel", "electricity", "energy", "diesel"]):
        return "economics_energy"
    return "general"


def flatten_config_dict(d: Any, parent_key: str = "") -> List[tuple]:
    """Recursively flattens JSON configuration dictionaries into parameter tuples (key, type_name, default_str)."""
    items = []
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else str(k)
            items.extend(flatten_config_dict(v, new_key))
    elif isinstance(d, list):
        if len(d) > 0 and all(isinstance(x, (int, float, str, bool)) for x in d):
            items.append((parent_key, type(d[0]).__name__, str(d[:5])))
        else:
            for i, elem in enumerate(d[:10]):
                items.extend(flatten_config_dict(elem, f"{parent_key}[{i}]"))
    else:
        items.append((parent_key, type(d).__name__, str(d)))
    return items


BIOPHYSICAL_CAUSAL_RULES = [
    {
        "param_pattern": "cow_num",
        "var_pattern": "daily_milk_production|population_number_of_cows|enteric_methane_emission|manure_nitrogen",
        "pathway": "Herd Dynamics & Production Scaling",
        "mechanism": "Herd size directly scales daily milk volume, animal inventory, enteric methane, and nitrogen excretion.",
    },
    {
        "param_pattern": "mature_body_weight",
        "var_pattern": "enteric_methane_emission|avg_milk_production_reduction",
        "pathway": "Body Size & Energy Partitioning",
        "mechanism": "Mature body weight governs maintenance energy demands, dry matter intake capacity, and rumen methanogenesis.",
    },
    {
        "param_pattern": "methane_mitigation|3-NOP|monensin|seaweed",
        "var_pattern": "enteric_methane_emission",
        "pathway": "Enteric Methane Mitigation",
        "mechanism": "Feed additives inhibit methanogenic archaea enzyme pathways to suppress enteric fermentation emissions.",
    },
    {
        "param_pattern": "lactation.adjustments.parity",
        "var_pattern": "daily_milk_production|estimated_daily_milk_produced",
        "pathway": "Lactation Curve Kinetics",
        "mechanism": "Parity-specific Wood curve parameters dictate lactation peak yield and persistency.",
    },
    {
        "param_pattern": "feed_storage_configurations|dm_loss_coefficient",
        "var_module": "feed_storage",
        "pathway": "Feed Storage Preservation & Spoilage",
        "mechanism": "Storage unit dimensions, dry matter content, and loss coefficients determine ensiling fermentation and aerobic face loss.",
    },
    {
        "param_pattern": "manure_management|separator|anaerobic_digester",
        "var_module": "manure",
        "pathway": "Manure Processing & Storage Kinetics",
        "mechanism": "Digester operating temperature, separator efficiency, and storage geometry govern volatile solids degradation and emissions.",
    },
    {
        "param_pattern": "soil_1|soil_2|slope",
        "var_pattern": "soil|ammonia|drainage",
        "pathway": "Soil Hydrology & Solute Transport",
        "mechanism": "Soil physical properties and layer hydrology govern water percolation, runoff, and gaseous nitrogen emissions.",
    },
    {
        "param_pattern": "fertilizer_schedule",
        "var_pattern": "ammonia_emissions|plant_metabolic_active_carbon_loss",
        "pathway": "Agronomic Nutrient Application",
        "mechanism": "Synthetic fertilizer application timing and mass drive soil mineral nitrogen pools and volatilization fluxes.",
    },
    {
        "param_pattern": "feed.feeds|EEE_constants|energy",
        "var_module": "eee",
        "pathway": "Techno-Economic & Life Cycle Assessment",
        "mechanism": "Feed purchase prices and energy constants drive whole-farm operational expenditures and Scope 1-3 GHG footprints.",
    },
]


def populate_structural_ontology(
    conn: kuzu.Connection,
    rufas_root: Union[str, Path] = "../RuFaS",
) -> Dict[str, Any]:
    """
    Populates the structural biophysical ontology into KùzuDB:
    1. 5 Canonical Modules
    2. ConfigBlobs from scenario metadata
    3. InputParameters extracted from JSON config files
    4. OutputVariables (2,038 variables) categorized with units
    5. Biophysical CAUSALLY_INFLUENCES pathways

    Args:
        conn: Initialized KùzuDB connection.
        rufas_root: Root directory of the RuFaS codebase.

    Returns:
        Summary dict containing counts of ingested entities and relationships.
    """
    import json
    import re
    import pandas as pd

    root_path = Path(rufas_root).resolve()
    logger.info("Populating structural ontology using RuFaS root: %s", root_path)

    summary = {
        "modules_ingested": 0,
        "config_blobs_ingested": 0,
        "config_of_edges": 0,
        "input_parameters_ingested": 0,
        "contains_param_edges": 0,
        "output_variables_ingested": 0,
        "causal_edges_ingested": 0,
    }

    # 1. Populate Canonical Modules
    for mod in CANONICAL_MODULES:
        conn.execute(
            "MERGE (m:Module {name: $name}) ON CREATE SET m.description = $description, m.manager_class = $manager_class",
            {"name": mod["name"], "description": mod["description"], "manager_class": mod["manager_class"]},
        )
    mod_count = conn.execute("MATCH (m:Module) RETURN count(m)").get_next()[0]
    summary["modules_ingested"] = mod_count

    # 2. Populate ConfigBlobs & CONFIG_OF relationships
    meta_path = root_path / "input/metadata/example_freestall_dairy_metadata.json"
    if not meta_path.exists():
        # Fallback to any metadata JSON in input/metadata/
        meta_candidates = list((root_path / "input/metadata").glob("*.json")) if (root_path / "input/metadata").exists() else []
        if meta_candidates:
            meta_path = meta_candidates[0]

    files_dict: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
                files_dict = meta_data.get("files", {})
        except Exception as e:
            logger.warning("Error reading metadata file %s: %e", meta_path, e)

    # Fetch existing CONFIG_OF edges for idempotency
    existing_config_of = {
        (row[0], row[1])
        for row in conn.execute("MATCH (b:ConfigBlob)-[:CONFIG_OF]->(m:Module) RETURN b.name, m.name").get_as_df().values
    }

    for blob_name, blob_info in files_dict.items():
        title = blob_info.get("title", blob_name)
        rel_file_path = blob_info.get("path", "")
        blob_desc = blob_info.get("description", "")
        format_type = blob_info.get("type", "json")

        conn.execute(
            "MERGE (b:ConfigBlob {name: $name}) ON CREATE SET b.title = $title, b.file_path = $file_path, b.description = $description, b.format_type = $format_type",
            {"name": blob_name, "title": title, "file_path": rel_file_path, "description": blob_desc, "format_type": format_type},
        )
        mod_name = classify_config_blob_module(blob_name)
        if (blob_name, mod_name) not in existing_config_of:
            conn.execute(
                "MATCH (b:ConfigBlob {name: $bname}), (m:Module {name: $mname}) CREATE (b)-[:CONFIG_OF]->(m)",
                {"bname": blob_name, "mname": mod_name},
            )
            existing_config_of.add((blob_name, mod_name))

    summary["config_blobs_ingested"] = conn.execute("MATCH (b:ConfigBlob) RETURN count(b)").get_next()[0]
    summary["config_of_edges"] = conn.execute("MATCH ()-[r:CONFIG_OF]->() RETURN count(r)").get_next()[0]

    # 3. Populate InputParameters & CONTAINS_PARAM relationships
    existing_contains_param = {
        (row[0], row[1])
        for row in conn.execute("MATCH (b:ConfigBlob)-[:CONTAINS_PARAM]->(p:InputParameter) RETURN b.name, p.id").get_as_df().values
    }

    for blob_name, blob_info in files_dict.items():
        if blob_info.get("type") == "json":
            rel_path = blob_info.get("path", "")
            json_file = root_path / rel_path
            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        config_content = json.load(jf)
                except Exception as e:
                    logger.warning("Error reading config JSON %s: %s", json_file, e)
                    continue

                param_items = flatten_config_dict(config_content, blob_name)
                for param_id, dtype, default_val in param_items:
                    parts = param_id.split(".")
                    param_name = parts[-1] if parts else param_id
                    conn.execute(
                        "MERGE (p:InputParameter {id: $id}) ON CREATE SET p.blob_name = $blob_name, p.param_name = $param_name, p.data_type = $dtype, p.unit = '', p.default_value = $def_val, p.description = ''",
                        {
                            "id": param_id,
                            "blob_name": blob_name,
                            "param_name": param_name,
                            "dtype": dtype,
                            "def_val": str(default_val)[:255],
                        },
                    )
                    if (blob_name, param_id) not in existing_contains_param:
                        conn.execute(
                            "MATCH (b:ConfigBlob {name: $bname}), (p:InputParameter {id: $pid}) CREATE (b)-[:CONTAINS_PARAM]->(p)",
                            {"bname": blob_name, "pid": param_id},
                        )
                        existing_contains_param.add((blob_name, param_id))

    summary["input_parameters_ingested"] = conn.execute("MATCH (p:InputParameter) RETURN count(p)").get_next()[0]
    summary["contains_param_edges"] = conn.execute("MATCH ()-[r:CONTAINS_PARAM]->() RETURN count(r)").get_next()[0]

    # 4. Populate OutputVariables
    var_names: List[str] = []
    # Inspect output CSV files
    csv_candidates = list((root_path / "output/CSVs").glob("*.csv")) if (root_path / "output/CSVs").exists() else []
    if not csv_candidates and (root_path / "output").exists():
        csv_candidates = list((root_path / "output").glob("*.csv"))

    for csv_file in csv_candidates:
        try:
            df_head = pd.read_csv(csv_file, nrows=1)
            if len(df_head.columns) > 50:
                var_names = df_head.columns.tolist()
                break
        except Exception as e:
            logger.warning("Error reading output CSV %s: %s", csv_file, e)

    # Fallback to output logs or filter files
    if not var_names:
        log_candidates = list((root_path / "output/logs").glob("*variable_names*.txt")) if (root_path / "output/logs").exists() else []
        for log_file in log_candidates:
            try:
                with open(log_file, "r", encoding="utf-8") as lf:
                    lines = [ln.strip() for ln in lf.readlines() if ln.strip() and not ln.startswith("Under construction") and not ln.startswith("_exclude")]
                    if len(lines) > 50:
                        var_names = lines
                        break
            except Exception as e:
                logger.warning("Error reading variable log %s: %s", log_file, e)

    for col in var_names:
        mod = categorize_variable_name(col)
        unit = extract_variable_unit(col) or ""
        cat = infer_variable_category(col, mod)
        parts = col.split(".")
        rep_cls = parts[0] if len(parts) > 1 else "General"
        description = f"Simulation output variable tracked by {rep_cls}"
        conn.execute(
            "MERGE (v:OutputVariable {name: $name}) ON CREATE SET v.module = $mod, v.unit = $unit, v.category = $cat, v.reporter_class = $rep, v.description = $description",
            {"name": col, "mod": mod, "unit": unit, "cat": cat, "rep": rep_cls, "description": description},
        )

    summary["output_variables_ingested"] = conn.execute("MATCH (v:OutputVariable) RETURN count(v)").get_next()[0]

    # 5. Populate Biophysical CAUSALLY_INFLUENCES Edges
    existing_causal = {
        (row[0], row[1])
        for row in conn.execute("MATCH (p:InputParameter)-[:CAUSALLY_INFLUENCES]->(v:OutputVariable) RETURN p.id, v.name").get_as_df().values
    }

    # Pre-fetch input parameters and output variables to perform fast domain mapping
    all_params_df = conn.execute("MATCH (p:InputParameter) RETURN p.id, p.param_name, p.blob_name").get_as_df()
    all_vars_df = conn.execute("MATCH (v:OutputVariable) RETURN v.name, v.module").get_as_df()

    if not all_params_df.empty and not all_vars_df.empty:
        for rule in BIOPHYSICAL_CAUSAL_RULES:
            p_pat = rule["param_pattern"]
            matching_pids = [
                row[0] for row in all_params_df.values
                if re.search(p_pat, str(row[0]), re.IGNORECASE) or re.search(p_pat, str(row[1]), re.IGNORECASE)
            ]

            if "var_pattern" in rule:
                v_pat = rule["var_pattern"]
                matching_vnames = [
                    row[0] for row in all_vars_df.values
                    if re.search(v_pat, str(row[0]), re.IGNORECASE)
                ]
            elif "var_module" in rule:
                v_mod = rule["var_module"]
                matching_vnames = [
                    row[0] for row in all_vars_df.values
                    if str(row[1]) == v_mod
                ]
            else:
                matching_vnames = []

            for pid in matching_pids[:30]:
                for vname in matching_vnames[:30]:
                    if (pid, vname) not in existing_causal:
                        conn.execute(
                            "MATCH (p:InputParameter {id: $pid}), (v:OutputVariable {name: $vname}) CREATE (p)-[:CAUSALLY_INFLUENCES {pathway: $pathway, mechanism: $mechanism}]->(v)",
                            {"pid": pid, "vname": vname, "pathway": rule["pathway"], "mechanism": rule["mechanism"]},
                        )
                        existing_causal.add((pid, vname))

    summary["causal_edges_ingested"] = conn.execute("MATCH ()-[r:CAUSALLY_INFLUENCES]->() RETURN count(r)").get_next()[0]
    logger.info("Ontology population completed successfully: %s", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RuFaS Graph Memory Brain & Correlation Engine CLI",
        prog="rufas-brain",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    init_parser = subparsers.add_parser("init", help="Initialize KùzuDB brain database and populate ontology")
    init_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )
    init_parser.add_argument(
        "--rufas-root",
        type=str,
        default="../RuFaS",
        help="Path to the root directory of RuFaS codebase",
    )

    args = parser.parse_args()
    if args.subcommand == "init":
        conn = init_brain_database(args.db_path)
        summary = populate_structural_ontology(conn, args.rufas_root)
        print(f"RuFaS Graph Memory Brain database initialized at {args.db_path}")
        print(f"Ontology summary: {summary}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


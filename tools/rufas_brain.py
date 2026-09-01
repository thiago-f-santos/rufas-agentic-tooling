#!/usr/bin/env python3
"""
RuFaS Graph Memory Brain & Correlation Engine
Embedded KùzuDB property graph database for biophysical ontology, simulation history,
statistical cross-run correlations, and Obsidian knowledge graph export.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import kuzu
import pandas as pd

from tools.config import RuFaSConfigError, get_rufas_root

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
    rufas_root: Optional[Union[str, Path]] = None,
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
        rufas_root: Optional root directory of the RuFaS codebase (auto-detected if None).

    Returns:
        Summary dict containing counts of ingested entities and relationships.
    """
    import json
    import re
    import pandas as pd

    root_path = get_rufas_root(cli_arg=rufas_root)
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


def ingest_simulation_run(
    conn: kuzu.Connection,
    output_dir: Union[str, Path],
    run_id: str,
    scenario_name: str = "example_freestall",
    config_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ingests a RuFaS simulation run from CSV output files into KùzuDB:
    1. Parses simulation CSV output file in output_dir.
    2. Upserts a :SimulationRun node with execution metadata and duration.
    3. Connects the run to :InputParameter nodes via SIMULATED_WITH edges.
    4. Calculates descriptive statistics (mean, min, max, sum, non_null_count) for all variables.
    5. Batch inserts :RunMetric nodes and connects GENERATED_METRIC and OF_VARIABLE edges.

    Args:
        conn: Initialized KùzuDB connection.
        output_dir: Directory containing simulation CSV outputs (e.g. output/ or output/CSVs).
        run_id: Unique string identifier for this simulation run.
        scenario_name: Name of the scenario simulated.
        config_data: Optional dictionary of parameter overrides used in this run.

    Returns:
        Summary dict containing ingestion metrics.
    """
    import re
    from datetime import datetime
    import pandas as pd

    out_path = Path(output_dir).resolve()
    logger.info("Ingesting simulation run '%s' from %s", run_id, out_path)

    # 1. Locate the main output CSV file
    csv_candidates: List[Path] = []
    if (out_path / "CSVs").exists():
        csv_candidates.extend(list((out_path / "CSVs").glob("*.csv")))
    if out_path.exists():
        csv_candidates.extend(list(out_path.glob("*.csv")))

    # Filter out secondary log CSVs if main simulation CSV is present
    filtered_candidates = [
        p for p in csv_candidates
        if not any(k in p.name for k in ["variables_reported_daily", "variables_not_reported_daily", "variables_usage_counts", "metadata_properties"])
    ]
    candidate_list = filtered_candidates if filtered_candidates else csv_candidates

    if not candidate_list:
        raise FileNotFoundError(f"No CSV output files found in {output_dir}")

    # Pick largest CSV file (highest column count / size)
    main_csv = max(candidate_list, key=lambda p: p.stat().st_size)
    logger.info("Loading output CSV: %s", main_csv)
    df = pd.read_csv(main_csv, low_memory=False)

    # 2. Extract execution metadata
    # Execution Date
    execution_date = datetime.now().isoformat()
    date_match = re.search(r"(\d{1,2}-[A-Za-z]{3}-\d{4})_[A-Za-z]{3}_(\d{2}-\d{2}-\d{2})", main_csv.name)
    if date_match:
        try:
            dt = datetime.strptime(f"{date_match.group(1)} {date_match.group(2).replace('-', ':')}", "%d-%b-%Y %H:%M:%S")
            execution_date = dt.isoformat()
        except Exception:
            pass
    elif main_csv.exists():
        execution_date = datetime.fromtimestamp(main_csv.stat().st_mtime).isoformat()

    # Start date, end date, duration_days
    start_date = "2013:1"
    end_date = f"2013:{len(df)}"
    duration_days = len(df)

    col_cal_yr = next((c for c in df.columns if "calendar_year" in c.lower()), None)
    col_day = next((c for c in df.columns if c.startswith("RufasTime.day") or "julian day" in c.lower()), None)
    col_sim_day = next((c for c in df.columns if "simulation_day" in c.lower()), None)

    if col_cal_yr and col_day:
        df_time = df[[col_cal_yr, col_day]].dropna()
        if not df_time.empty:
            cal_yr_0 = int(df_time[col_cal_yr].iloc[0])
            day_0 = int(df_time[col_day].iloc[0])
            cal_yr_n = int(df_time[col_cal_yr].iloc[-1])
            day_n = int(df_time[col_day].iloc[-1])
            start_date = f"{cal_yr_0}:{day_0}"
            end_date = f"{cal_yr_n}:{day_n}"
            duration_days = len(df_time)
    elif col_day:
        df_day = df[col_day].dropna()
        if not df_day.empty:
            start_date = f"day_{int(df_day.iloc[0])}"
            end_date = f"day_{int(df_day.iloc[-1])}"
            duration_days = len(df_day)
    elif col_sim_day:
        df_sim_day = df[col_sim_day].dropna()
        if not df_sim_day.empty:
            duration_days = int(df_sim_day.max()) + 1
            end_date = f"2013:{duration_days}"

    # Random seed & status
    random_seed = 42
    if config_data:
        if "random_seed" in config_data:
            random_seed = int(config_data["random_seed"])
        elif "seed" in config_data:
            random_seed = int(config_data["seed"])

    status = "completed" if len(df) > 0 else "failed"

    # 3. Upsert :SimulationRun node
    conn.execute(
        """
        MERGE (r:SimulationRun {run_id: $run_id})
        ON CREATE SET
            r.scenario_name = $scenario_name,
            r.execution_date = $execution_date,
            r.start_date = $start_date,
            r.end_date = $end_date,
            r.duration_days = $duration_days,
            r.random_seed = $random_seed,
            r.status = $status
        ON MATCH SET
            r.scenario_name = $scenario_name,
            r.execution_date = $execution_date,
            r.start_date = $start_date,
            r.end_date = $end_date,
            r.duration_days = $duration_days,
            r.random_seed = $random_seed,
            r.status = $status
        """,
        {
            "run_id": run_id,
            "scenario_name": scenario_name,
            "execution_date": execution_date,
            "start_date": start_date,
            "end_date": end_date,
            "duration_days": duration_days,
            "random_seed": random_seed,
            "status": status,
        },
    )

    # 4. Connect to InputParameter nodes via SIMULATED_WITH
    flat_config_lookup: Dict[str, str] = {}
    if config_data:
        if isinstance(config_data, dict):
            for k, dtype, val in flatten_config_dict(config_data):
                flat_config_lookup[str(k)] = str(val)
                flat_config_lookup[str(k).split(".")[-1]] = str(val)
            for k, v in config_data.items():
                flat_config_lookup[str(k)] = str(v)
                flat_config_lookup[str(k).split(".")[-1]] = str(v)

    params_df = conn.execute("MATCH (p:InputParameter) RETURN p.id, p.param_name, p.default_value").get_as_df()
    parameters_linked = 0

    if not params_df.empty:
        for row in params_df.values:
            p_id, p_name, p_default = str(row[0]), str(row[1]), str(row[2])
            val = flat_config_lookup.get(p_id, flat_config_lookup.get(p_name, p_default))
            conn.execute(
                """
                MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: $pid})
                MERGE (r)-[s:SIMULATED_WITH]->(p)
                ON CREATE SET s.value = $val
                ON MATCH SET s.value = $val
                """,
                {"rid": run_id, "pid": p_id, "val": str(val)},
            )
            parameters_linked += 1
    elif config_data:
        for k, v in flat_config_lookup.items():
            conn.execute(
                """
                MERGE (p:InputParameter {id: $id})
                ON CREATE SET p.blob_name = '', p.param_name = $pname, p.data_type = 'string', p.unit = '', p.default_value = $val, p.description = ''
                """,
                {"id": k, "pname": k.split(".")[-1], "val": str(v)},
            )
            conn.execute(
                """
                MATCH (r:SimulationRun {run_id: $rid}), (p:InputParameter {id: $pid})
                MERGE (r)-[s:SIMULATED_WITH]->(p)
                ON CREATE SET s.value = $val
                ON MATCH SET s.value = $val
                """,
                {"rid": run_id, "pid": k, "val": str(v)},
            )
            parameters_linked += 1

    # 5. Ensure OutputVariable nodes exist for all CSV columns
    existing_vars_df = conn.execute("MATCH (v:OutputVariable) RETURN v.name").get_as_df()
    existing_vars = set(existing_vars_df["v.name"].tolist()) if not existing_vars_df.empty else set()

    for col in df.columns:
        col_str = str(col)
        if col_str not in existing_vars:
            mod = categorize_variable_name(col_str)
            unit = extract_variable_unit(col_str) or ""
            cat = infer_variable_category(col_str, mod)
            parts = col_str.split(".")
            rep_cls = parts[0] if len(parts) > 1 else "General"
            desc = f"Simulation output variable tracked by {rep_cls}"
            conn.execute(
                """
                MERGE (v:OutputVariable {name: $name})
                ON CREATE SET v.module = $mod, v.unit = $unit, v.category = $cat, v.reporter_class = $rep, v.description = $desc
                """,
                {"name": col_str, "mod": mod, "unit": unit, "cat": cat, "rep": rep_cls, "desc": desc},
            )
            existing_vars.add(col_str)

    # 6. Calculate summary statistics & batch insert RunMetric nodes and edges
    upsert_metric_query = """
    MATCH (r:SimulationRun {run_id: $rid}), (v:OutputVariable {name: $vname})
    MERGE (rm:RunMetric {id: $mid})
    ON CREATE SET
        rm.run_id = $rid,
        rm.var_name = $vname,
        rm.mean_val = $mean,
        rm.min_val = $min,
        rm.max_val = $max,
        rm.sum_val = $sum,
        rm.non_null_count = $count
    ON MATCH SET
        rm.run_id = $rid,
        rm.var_name = $vname,
        rm.mean_val = $mean,
        rm.min_val = $min,
        rm.max_val = $max,
        rm.sum_val = $sum,
        rm.non_null_count = $count
    MERGE (r)-[:GENERATED_METRIC]->(rm)
    MERGE (rm)-[:OF_VARIABLE]->(v)
    """

    metrics_ingested = 0
    for col in df.columns:
        col_str = str(col)
        series = pd.to_numeric(df[col], errors="coerce")
        valid = series.dropna()
        cnt = int(len(valid))
        if cnt > 0:
            mean_v = float(valid.mean())
            min_v = float(valid.min())
            max_v = float(valid.max())
            sum_v = float(valid.sum())
        else:
            mean_v = 0.0
            min_v = 0.0
            max_v = 0.0
            sum_v = 0.0

        metric_id = f"{run_id}::{col_str}"
        conn.execute(
            upsert_metric_query,
            {
                "rid": run_id,
                "vname": col_str,
                "mid": metric_id,
                "mean": mean_v,
                "min": min_v,
                "max": max_v,
                "sum": sum_v,
                "count": cnt,
            },
        )
        metrics_ingested += 1

    summary = {
        "run_id": run_id,
        "scenario_name": scenario_name,
        "execution_date": execution_date,
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": duration_days,
        "random_seed": random_seed,
        "status": status,
        "metrics_ingested": metrics_ingested,
        "parameters_linked": parameters_linked,
    }
    logger.info("Simulation run ingestion completed: %s", summary)
    return summary


def compute_statistical_correlations(
    conn: kuzu.Connection,
    min_r: float = 0.5,
    max_p: float = 0.05,
    min_samples: int = 3,
) -> List[Dict[str, Any]]:
    """
    Computes Pearson and Spearman correlation statistics between InputParameters and OutputVariables
    across all ingested SimulationRun records in KùzuDB.

    Filters for statistically significant relationships (|r| >= min_r or |rho| >= min_r) with p <= max_p
    and sample_size >= min_samples, and batch-inserts/updates :CORRELATES_WITH edges into KùzuDB.

    Args:
        conn: Initialized KùzuDB connection.
        min_r: Minimum absolute correlation threshold (default: 0.5).
        max_p: Maximum p-value threshold for significance (default: 0.05).
        min_samples: Minimum number of simulation runs with valid data required (default: 3).

    Returns:
        List of correlation dicts with keys:
            - param_id (str)
            - var_name (str)
            - pearson_r (float)
            - spearman_r (float)
            - p_value (float)
            - sample_size (int)
    """
    import math
    import warnings
    import numpy as np
    import pandas as pd
    import scipy.stats as stats

    logger.info(
        "Computing statistical correlations across simulation runs (min_r=%s, max_p=%s, min_samples=%s)...",
        min_r,
        max_p,
        min_samples,
    )

    # 1. Query parameters simulated with runs
    df_params = conn.execute(
        "MATCH (r:SimulationRun)-[s:SIMULATED_WITH]->(p:InputParameter) RETURN r.run_id AS run_id, p.id AS param_id, s.value AS param_val"
    ).get_as_df()

    # 2. Query output metrics from runs
    df_metrics = conn.execute(
        "MATCH (r:SimulationRun)-[:GENERATED_METRIC]->(rm:RunMetric)-[:OF_VARIABLE]->(v:OutputVariable) RETURN r.run_id AS run_id, v.name AS var_name, rm.mean_val AS mean_val"
    ).get_as_df()

    if df_params.empty or df_metrics.empty:
        logger.info("No parameters or metrics found in database to correlate.")
        return []

    # Convert parameter values to numeric floats, dropping non-numeric/text values
    df_params["numeric_val"] = pd.to_numeric(df_params["param_val"], errors="coerce")
    df_params_clean = df_params.dropna(subset=["numeric_val"])

    if df_params_clean.empty:
        logger.info("No numeric parameter values found in database.")
        return []

    # 3. Identify parameters with variance > 0 and sample count >= min_samples
    param_groups = df_params_clean.groupby("param_id")
    varying_params: Dict[str, Dict[str, float]] = {}
    for pid, group in param_groups:
        if len(group) >= min_samples:
            vals = group["numeric_val"].to_numpy(dtype=float)
            if np.var(vals) > 1e-12 and len(np.unique(vals)) > 1:
                varying_params[pid] = dict(zip(group["run_id"], group["numeric_val"]))

    if not varying_params:
        logger.info("No varying parameters found across runs.")
        return []

    # 4. Identify variables with variance > 0 and sample count >= min_samples
    metric_groups = df_metrics.dropna(subset=["mean_val"]).groupby("var_name")
    varying_metrics: Dict[str, Dict[str, float]] = {}
    for vname, group in metric_groups:
        if len(group) >= min_samples:
            vals = group["mean_val"].to_numpy(dtype=float)
            if np.var(vals) > 1e-12 and len(np.unique(vals)) > 1:
                varying_metrics[vname] = dict(zip(group["run_id"], group["mean_val"]))

    if not varying_metrics:
        logger.info("No varying output variables found across runs.")
        return []

    logger.info(
        "Analyzing %d varying parameters against %d varying variables...",
        len(varying_params),
        len(varying_metrics),
    )

    # 5. Compute correlations for each (param, var) pair
    significant_correlations: List[Dict[str, Any]] = []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for pid, p_runs in varying_params.items():
            for vname, v_runs in varying_metrics.items():
                common_runs = set(p_runs.keys()) & set(v_runs.keys())
                if len(common_runs) < min_samples:
                    continue

                x = np.array([p_runs[r] for r in common_runs], dtype=float)
                y = np.array([v_runs[r] for r in common_runs], dtype=float)

                var_x = float(np.var(x))
                var_y = float(np.var(y))
                if var_x <= 1e-12 or var_y <= 1e-12:
                    continue

                try:
                    p_res = stats.pearsonr(x, y)
                    r_val = float(p_res.statistic)
                    p_pearson = float(p_res.pvalue)
                except Exception:
                    r_val, p_pearson = 0.0, 1.0

                try:
                    s_res = stats.spearmanr(x, y)
                    rho_val = float(s_res.statistic)
                    p_spearman = float(s_res.pvalue)
                except Exception:
                    rho_val, p_spearman = 0.0, 1.0

                if math.isnan(r_val):
                    r_val = 0.0
                    p_pearson = 1.0
                if math.isnan(rho_val):
                    rho_val = 0.0
                    p_spearman = 1.0
                if math.isnan(p_pearson):
                    p_pearson = 1.0
                if math.isnan(p_spearman):
                    p_spearman = 1.0

                pearson_sig = (abs(r_val) >= min_r) and (p_pearson <= max_p)
                spearman_sig = (abs(rho_val) >= min_r) and (p_spearman <= max_p)

                if pearson_sig or spearman_sig:
                    if pearson_sig and spearman_sig:
                        p_val = min(p_pearson, p_spearman)
                    elif pearson_sig:
                        p_val = p_pearson
                    else:
                        p_val = p_spearman

                    significant_correlations.append({
                        "param_id": pid,
                        "var_name": vname,
                        "pearson_r": r_val,
                        "spearman_r": rho_val,
                        "p_value": p_val,
                        "sample_size": len(common_runs),
                    })

    logger.info("Found %d statistically significant correlations.", len(significant_correlations))

    # 6. Batch upsert [:CORRELATES_WITH] edges into KùzuDB
    upsert_edge_query = """
    MATCH (p:InputParameter {id: $pid}), (v:OutputVariable {name: $vname})
    MERGE (p)-[c:CORRELATES_WITH]->(v)
    ON CREATE SET
        c.pearson_r = $pearson_r,
        c.spearman_r = $spearman_r,
        c.p_value = $p_value,
        c.sample_size = $sample_size
    ON MATCH SET
        c.pearson_r = $pearson_r,
        c.spearman_r = $spearman_r,
        c.p_value = $p_value,
        c.sample_size = $sample_size
    """

    for corr in significant_correlations:
        conn.execute(
            upsert_edge_query,
            {
                "pid": corr["param_id"],
                "vname": corr["var_name"],
                "pearson_r": corr["pearson_r"],
                "spearman_r": corr["spearman_r"],
                "p_value": corr["p_value"],
                "sample_size": corr["sample_size"],
            },
        )

    significant_correlations.sort(key=lambda item: abs(item["pearson_r"]), reverse=True)
    return significant_correlations


def execute_cypher_query(conn: kuzu.Connection, query: str) -> List[Dict[str, Any]]:
    """
    Executes an OpenCypher query on the KùzuDB connection and returns the results as a list of dictionaries.

    Args:
        conn: Initialized KùzuDB connection.
        query: OpenCypher query string.

    Returns:
        List of row dicts mapping column names to cell values.
    """
    logger.debug("Executing OpenCypher query: %s", query)
    result = conn.execute(query)
    try:
        df = result.get_as_df()
        return df.where(pd.notnull(df), None).to_dict(orient="records")
    except Exception:
        cols = result.get_column_names() if hasattr(result, "get_column_names") else []
        rows: List[Dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            if cols:
                rows.append(dict(zip(cols, row)))
            else:
                rows.append({"result": row})
        return rows


def trace_parameter_impact(conn: kuzu.Connection, param_query: str) -> Dict[str, Any]:
    """
    Traces the causal biophysical pathways and empirical statistical correlations for input parameters
    matching a query substring.

    Searches InputParameter nodes matching param_query (case-insensitive substring on id or param_name).
    Retrieves all causally influenced OutputVariable nodes via [:CAUSALLY_INFLUENCES].
    Retrieves all statistically correlated OutputVariable nodes via [:CORRELATES_WITH].

    Args:
        conn: Initialized KùzuDB connection.
        param_query: Parameter name or ID substring to search for.

    Returns:
        Structured dict with keys:
            - param_query: Original search string
            - matched_parameters_count: Total parameters matching query
            - parameters: Detailed list per matched parameter with:
                - id, param_name, blob_name, data_type, unit, default_value, description
                - causal_pathways: List of causally influenced output variables (with pathway & mechanism)
                - correlations: List of empirically correlated output variables (with r, rho, p_value, sample_size)
            - causal_pathways: Aggregated list of all causal pathways found across matched parameters
            - correlations: Aggregated list of all correlations found across matched parameters (sorted by |r| desc)
    """
    clean_query = param_query.strip().lower()

    # 1. Fetch matching parameters
    params_df = conn.execute(
        """
        MATCH (p:InputParameter)
        WHERE lower(p.id) CONTAINS $query OR lower(p.param_name) CONTAINS $query
        RETURN p.id AS id, p.param_name AS param_name, p.blob_name AS blob_name,
               p.data_type AS data_type, p.unit AS unit, p.default_value AS default_value,
               p.description AS description
        ORDER BY p.id
        """,
        {"query": clean_query},
    ).get_as_df()

    if params_df.empty:
        return {
            "param_query": param_query,
            "matched_parameters_count": 0,
            "parameters": [],
            "causal_pathways": [],
            "correlations": [],
        }

    parameter_list: List[Dict[str, Any]] = []
    all_causal_pathways: List[Dict[str, Any]] = []
    all_correlations: List[Dict[str, Any]] = []

    for _, row in params_df.iterrows():
        pid = str(row["id"])
        p_name = str(row["param_name"])
        blob_name = str(row["blob_name"])
        dtype = str(row["data_type"])
        unit = str(row["unit"])
        def_val = str(row["default_value"])
        desc = str(row["description"])

        # Fetch Causal Pathways
        causal_df = conn.execute(
            """
            MATCH (p:InputParameter {id: $pid})-[c:CAUSALLY_INFLUENCES]->(v:OutputVariable)
            RETURN v.name AS output_variable, v.module AS module, v.category AS category,
                   v.unit AS unit, c.pathway AS pathway, c.mechanism AS mechanism
            ORDER BY v.name
            """,
            {"pid": pid},
        ).get_as_df()

        causal_list = causal_df.to_dict(orient="records") if not causal_df.empty else []

        # Fetch Statistical Correlations
        corr_df = conn.execute(
            """
            MATCH (p:InputParameter {id: $pid})-[c:CORRELATES_WITH]->(v:OutputVariable)
            RETURN v.name AS output_variable, v.module AS module, v.category AS category,
                   v.unit AS unit, c.pearson_r AS pearson_r, c.spearman_r AS spearman_r,
                   c.p_value AS p_value, c.sample_size AS sample_size
            """,
            {"pid": pid},
        ).get_as_df()

        corr_list = corr_df.to_dict(orient="records") if not corr_df.empty else []
        corr_list.sort(key=lambda item: abs(item.get("pearson_r", 0.0)), reverse=True)

        param_dict = {
            "id": pid,
            "param_name": p_name,
            "blob_name": blob_name,
            "data_type": dtype,
            "unit": unit,
            "default_value": def_val,
            "description": desc,
            "causal_pathways": causal_list,
            "correlations": corr_list,
        }
        parameter_list.append(param_dict)

        for c_item in causal_list:
            item_with_param = dict(c_item)
            item_with_param["param_id"] = pid
            item_with_param["param_name"] = p_name
            all_causal_pathways.append(item_with_param)

        for cr_item in corr_list:
            item_with_param = dict(cr_item)
            item_with_param["param_id"] = pid
            item_with_param["param_name"] = p_name
            all_correlations.append(item_with_param)

    all_correlations.sort(key=lambda item: abs(item.get("pearson_r", 0.0)), reverse=True)

    return {
        "param_query": param_query,
        "matched_parameters_count": len(parameter_list),
        "parameters": parameter_list,
        "causal_pathways": all_causal_pathways,
        "correlations": all_correlations,
    }


def lookup_variable_info(conn: kuzu.Connection, var_query: str) -> List[Dict[str, Any]]:
    """
    Searches OutputVariable nodes matching var_query (case-insensitive substring) and returns complete
    metadata, incoming biophysical causal drivers, correlated input parameters, and latest simulation run metrics.

    Args:
        conn: Initialized KùzuDB connection.
        var_query: Output variable name or substring to search for.

    Returns:
        List of variable info dicts with keys:
            - name: Output variable full name
            - module: Owning biophysical / economic module
            - unit: Unit of measurement
            - category: Functional category
            - reporter_class: Reporter class
            - description: Description
            - causal_inputs: Incoming causal input parameters (with pathway & mechanism)
            - correlated_inputs: Empirically correlated input parameters (sorted by |r| desc)
            - run_metrics: Aggregated metrics across simulation runs (if available)
    """
    clean_query = var_query.strip().lower()

    vars_df = conn.execute(
        """
        MATCH (v:OutputVariable)
        WHERE lower(v.name) CONTAINS $query
        RETURN v.name AS name, v.module AS module, v.unit AS unit,
               v.category AS category, v.reporter_class AS reporter_class,
               v.description AS description
        ORDER BY v.name
        """,
        {"query": clean_query},
    ).get_as_df()

    if vars_df.empty:
        return []

    results: List[Dict[str, Any]] = []
    for _, row in vars_df.iterrows():
        vname = str(row["name"])
        mod = str(row["module"])
        unit = str(row["unit"])
        cat = str(row["category"])
        rep_cls = str(row["reporter_class"])
        desc = str(row["description"])

        # Fetch incoming causal input parameters
        causal_df = conn.execute(
            """
            MATCH (p:InputParameter)-[c:CAUSALLY_INFLUENCES]->(v:OutputVariable {name: $vname})
            RETURN p.id AS param_id, p.param_name AS param_name, p.blob_name AS blob_name,
                   c.pathway AS pathway, c.mechanism AS mechanism
            ORDER BY p.id
            """,
            {"vname": vname},
        ).get_as_df()
        causal_inputs = causal_df.to_dict(orient="records") if not causal_df.empty else []

        # Fetch correlated input parameters
        corr_df = conn.execute(
            """
            MATCH (p:InputParameter)-[c:CORRELATES_WITH]->(v:OutputVariable {name: $vname})
            RETURN p.id AS param_id, p.param_name AS param_name, c.pearson_r AS pearson_r,
                   c.spearman_r AS spearman_r, c.p_value AS p_value, c.sample_size AS sample_size
            """,
            {"vname": vname},
        ).get_as_df()
        correlated_inputs = corr_df.to_dict(orient="records") if not corr_df.empty else []
        correlated_inputs.sort(key=lambda item: abs(item.get("pearson_r", 0.0)), reverse=True)

        # Fetch simulation run metrics
        metrics_df = conn.execute(
            """
            MATCH (r:SimulationRun)-[:GENERATED_METRIC]->(rm:RunMetric)-[:OF_VARIABLE]->(v:OutputVariable {name: $vname})
            RETURN r.run_id AS run_id, r.scenario_name AS scenario_name, rm.mean_val AS mean_val,
                   rm.min_val AS min_val, rm.max_val AS max_val, rm.sum_val AS sum_val,
                   rm.non_null_count AS non_null_count
            ORDER BY r.run_id
            """,
            {"vname": vname},
        ).get_as_df()
        run_metrics = metrics_df.to_dict(orient="records") if not metrics_df.empty else []

        results.append({
            "name": vname,
            "module": mod,
            "unit": unit,
            "category": cat,
            "reporter_class": rep_cls,
            "description": desc,
            "causal_inputs": causal_inputs,
            "correlated_inputs": correlated_inputs,
            "run_metrics": run_metrics,
        })

    return results


MODULE_NOTE_MAP: Dict[str, str] = {
    "animal": "Animal_Module",
    "field_soil": "Field_Soil_Module",
    "feed_storage": "Feed_Storage_Module",
    "manure": "Manure_Module",
    "eee": "EEE_Module",
}

MODULE_DISPLAY_NAMES: Dict[str, str] = {
    "animal": "Animal Subsystem (Herd Dynamics & Lactation)",
    "field_soil": "Field & Soil Subsystem (Hydrology & Biogeochemistry)",
    "feed_storage": "Feed Storage Subsystem (Preservation & Spoilage)",
    "manure": "Manure Subsystem (Processing, Separation & Emissions)",
    "eee": "Economics, Energy & Emissions (EEE Subsystem)",
}


def sanitize_filename(name: str, max_len: int = 200) -> str:
    """
    Sanitizes strings for safe Obsidian note filenames and cross-platform filesystems.
    Replaces / \\ : * ? \" < > | with underscores and trims whitespace.
    Truncates overly long filenames (> max_len) with a deterministic hash.
    """
    import hashlib
    import re
    cleaned = re.sub(r'[/\\:*?"<>|]', "_", str(name)).strip()
    if not cleaned:
        return "unnamed"
    if len(cleaned) > max_len:
        h = hashlib.md5(str(name).encode("utf-8")).hexdigest()[:8]
        cleaned = f"{cleaned[:max_len-10]}_{h}"
    return cleaned


def get_module_note_name(mod_name: str) -> str:
    """Returns the canonical Obsidian note name for a module."""
    m = mod_name.lower().strip()
    if m in MODULE_NOTE_MAP:
        return MODULE_NOTE_MAP[m]
    return f"{sanitize_filename(mod_name).title()}_Module"


def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Formats a dictionary as a valid YAML frontmatter block enclosed in --- delimiters.
    Handles strings, numbers, booleans, and lists cleanly without third-party deps.
    """
    lines = ["---"]
    for k, v in metadata.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                items_str = []
                for item in v:
                    if isinstance(item, (int, float)):
                        items_str.append(str(item))
                    elif isinstance(item, bool):
                        items_str.append("true" if item else "false")
                    else:
                        s = str(item).replace('"', '\\"')
                        items_str.append(f'"{s}"')
                lines.append(f"{k}: [{', '.join(items_str)}]")
        else:
            s_val = str(v)
            if any(ch in s_val for ch in [" ", ":", "#", "@", "[", "]", "{", "}", "(", ")", "/", "\\", "\n", '"', "'", ",", "*", "&", "!", "%", "|", ">", "`", "="]):
                escaped = s_val.replace('"', '\\"')
                lines.append(f'{k}: "{escaped}"')
            else:
                lines.append(f"{k}: {s_val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def export_obsidian_vault(
    conn: kuzu.Connection,
    output_dir: Union[str, Path] = "vault",
) -> Dict[str, int]:
    """
    Exports the entire RuFaS Graph Memory Brain into an interactive Obsidian Markdown vault:
    1. 00_Dashboard.md: System index, Dataview DQL queries, module statistics, and navigation links.
    2. 01_Simulations/<run_id>.md: Detailed note for each simulation run (parameters, top metrics, links).
    3. 02_Parameters/<clean_param_id>.md: Note for input parameters (metadata, causal outputs, correlations).
    4. 03_Outputs/<clean_var_name>.md: Note for output variables (metadata, causal drivers, correlations, run metrics).
    5. 04_Correlations/Significant_Correlations.md: Summary table of all |r| >= 0.5 relationships across runs.
    6. 05_Modules/<ModuleName>.md: Notes for the 5 biophysical and economic modules.

    Args:
        conn: Initialized KùzuDB connection.
        output_dir: Destination directory path for the Obsidian vault.

    Returns:
        Dict with counts of generated notes.
    """
    import datetime
    out_path = Path(output_dir).resolve()
    logger.info("Exporting Obsidian knowledge graph vault to %s...", out_path)

    sim_dir = out_path / "01_Simulations"
    param_dir = out_path / "02_Parameters"
    outputs_dir = out_path / "03_Outputs"
    corr_dir = out_path / "04_Correlations"
    modules_dir = out_path / "05_Modules"

    for d in [out_path, sim_dir, param_dir, outputs_dir, corr_dir, modules_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Batch query all nodes and relationships from KùzuDB
    modules_df = conn.execute("MATCH (m:Module) RETURN m.name AS name, m.description AS description, m.manager_class AS manager_class ORDER BY m.name").get_as_df()
    blobs_df = conn.execute("MATCH (b:ConfigBlob) OPTIONAL MATCH (b)-[:CONFIG_OF]->(m:Module) RETURN b.name AS name, b.title AS title, b.file_path AS file_path, b.description AS description, b.format_type AS format_type, m.name AS module_name ORDER BY b.name").get_as_df()
    params_df = conn.execute("MATCH (p:InputParameter) RETURN p.id AS id, p.blob_name AS blob_name, p.param_name AS param_name, p.data_type AS data_type, p.unit AS unit, p.default_value AS default_value, p.description AS description ORDER BY p.id").get_as_df()
    vars_df = conn.execute("MATCH (v:OutputVariable) RETURN v.name AS name, v.module AS module, v.unit AS unit, v.category AS category, v.reporter_class AS reporter_class, v.description AS description ORDER BY v.name").get_as_df()
    runs_df = conn.execute("MATCH (r:SimulationRun) RETURN r.run_id AS run_id, r.scenario_name AS scenario_name, r.execution_date AS execution_date, r.start_date AS start_date, r.end_date AS end_date, r.duration_days AS duration_days, r.random_seed AS random_seed, r.status AS status ORDER BY r.run_id").get_as_df()
    sim_with_df = conn.execute("MATCH (r:SimulationRun)-[s:SIMULATED_WITH]->(p:InputParameter) RETURN r.run_id AS run_id, p.id AS param_id, p.param_name AS param_name, p.blob_name AS blob_name, s.value AS value ORDER BY p.id").get_as_df()
    metrics_df = conn.execute("MATCH (r:SimulationRun)-[:GENERATED_METRIC]->(rm:RunMetric)-[:OF_VARIABLE]->(v:OutputVariable) RETURN r.run_id AS run_id, r.scenario_name AS scenario_name, v.name AS var_name, v.module AS module, v.category AS category, v.unit AS unit, rm.mean_val AS mean_val, rm.min_val AS min_val, rm.max_val AS max_val, rm.sum_val AS sum_val, rm.non_null_count AS non_null_count ORDER BY v.name").get_as_df()
    causal_df = conn.execute("MATCH (p:InputParameter)-[c:CAUSALLY_INFLUENCES]->(v:OutputVariable) RETURN p.id AS param_id, p.param_name AS param_name, p.blob_name AS blob_name, v.name AS var_name, v.module AS module, v.unit AS unit, v.category AS category, c.pathway AS pathway, c.mechanism AS mechanism ORDER BY v.name").get_as_df()
    corr_df = conn.execute("MATCH (p:InputParameter)-[c:CORRELATES_WITH]->(v:OutputVariable) RETURN p.id AS param_id, p.param_name AS param_name, p.blob_name AS blob_name, v.name AS var_name, v.module AS module, v.unit AS unit, v.category AS category, c.pearson_r AS pearson_r, c.spearman_r AS spearman_r, c.p_value AS p_value, c.sample_size AS sample_size ORDER BY abs(c.pearson_r) DESC").get_as_df()

    # Pre-index relationships in Python memory for fast lookups
    causal_by_param: Dict[str, List[Dict[str, Any]]] = {}
    causal_by_var: Dict[str, List[Dict[str, Any]]] = {}
    if not causal_df.empty:
        for rec in causal_df.to_dict(orient="records"):
            pid = str(rec["param_id"])
            vname = str(rec["var_name"])
            causal_by_param.setdefault(pid, []).append(rec)
            causal_by_var.setdefault(vname, []).append(rec)

    corr_by_param: Dict[str, List[Dict[str, Any]]] = {}
    corr_by_var: Dict[str, List[Dict[str, Any]]] = {}
    if not corr_df.empty:
        for rec in corr_df.to_dict(orient="records"):
            pid = str(rec["param_id"])
            vname = str(rec["var_name"])
            corr_by_param.setdefault(pid, []).append(rec)
            corr_by_var.setdefault(vname, []).append(rec)

    metrics_by_var: Dict[str, List[Dict[str, Any]]] = {}
    metrics_by_run: Dict[str, List[Dict[str, Any]]] = {}
    if not metrics_df.empty:
        for rec in metrics_df.to_dict(orient="records"):
            vname = str(rec["var_name"])
            rid = str(rec["run_id"])
            metrics_by_var.setdefault(vname, []).append(rec)
            metrics_by_run.setdefault(rid, []).append(rec)

    sim_with_by_run: Dict[str, List[Dict[str, Any]]] = {}
    if not sim_with_df.empty:
        for rec in sim_with_df.to_dict(orient="records"):
            rid = str(rec["run_id"])
            sim_with_by_run.setdefault(rid, []).append(rec)

    blobs_by_module: Dict[str, List[Dict[str, Any]]] = {}
    blob_module_map: Dict[str, str] = {}
    if not blobs_df.empty:
        for rec in blobs_df.to_dict(orient="records"):
            bname = str(rec["name"])
            mname = str(rec.get("module_name") or classify_config_blob_module(bname))
            blob_module_map[bname] = mname
            blobs_by_module.setdefault(mname, []).append(rec)

    vars_by_module: Dict[str, List[Dict[str, Any]]] = {}
    if not vars_df.empty:
        for rec in vars_df.to_dict(orient="records"):
            mname = str(rec["module"])
            vars_by_module.setdefault(mname, []).append(rec)

    params_count_by_blob: Dict[str, int] = {}
    if not params_df.empty:
        for _, row in params_df.iterrows():
            bname = str(row["blob_name"])
            params_count_by_blob[bname] = params_count_by_blob.get(bname, 0) + 1

    # 2. Generate 00_Dashboard.md
    now_iso = datetime.datetime.now().isoformat()
    modules_count = len(modules_df) if not modules_df.empty else len(CANONICAL_MODULES)
    blobs_count = len(blobs_df)
    params_count = len(params_df)
    vars_count = len(vars_df)
    runs_count = len(runs_df)
    causal_count = len(causal_df)
    corr_count = len(corr_df)

    dash_frontmatter = {
        "title": "RuFaS Knowledge Graph Dashboard",
        "type": "dashboard",
        "tags": ["rufas", "graph_memory", "dashboard"],
        "generated_at": now_iso,
        "total_modules": modules_count,
        "total_config_blobs": blobs_count,
        "total_input_parameters": params_count,
        "total_output_variables": vars_count,
        "total_simulation_runs": runs_count,
        "total_causal_pathways": causal_count,
        "total_correlations": corr_count,
    }

    dash_content = format_yaml_frontmatter(dash_frontmatter)
    dash_content += f"""# 🧠 RuFaS Graph Memory & Biophysical Knowledge Dashboard

Welcome to the **RuFaS Graph Memory Brain & Correlation Engine** knowledge vault. This interactive knowledge graph connects whole-farm input configuration parameters, biophysical causal pathways, 2,038 simulation output variables, and cross-run statistical correlations.

---

## 📊 Knowledge Graph Summary

| Entity / Layer | Node Count / Relationships |
|---|---|
| **Biophysical Modules** | `{modules_count}` modules (`[[Animal_Module]]`, `[[Field_Soil_Module]]`, `[[Feed_Storage_Module]]`, `[[Manure_Module]]`, `[[EEE_Module]]`) |
| **Input Configuration Blobs** | `{blobs_count}` configuration files |
| **Input Parameters** | `{params_count}` parameters |
| **Output Variables** | `{vars_count}` variables |
| **Biophysical Causal Pathways** | `{causal_count}` direct causal mechanisms |
| **Simulation Runs Ingested** | `{runs_count}` simulation runs |
| **Significant Cross-Run Correlations** | `{corr_count}` relationships ($|r| \\ge 0.5$, $p \\le 0.05$) — [[Significant_Correlations|View Table]] |

---

## 🧭 Biophysical Subsystem Modules

- 🐮 **[[Animal_Module|Animal Subsystem]]**: Herd dynamics, lactation kinetics, DMI, enteric methane ($CH_4$), excretion.
- 🌱 **[[Field_Soil_Module|Field & Soil Subsystem]]**: Multi-layer hydrology, soil biogeochemistry (SOM, C/N pools), crop growth, harvest.
- 🌾 **[[Feed_Storage_Module|Feed Storage Subsystem]]**: Silos, bunkers, bags, dry matter spoilage, fermentation degradation, feed purchasing.
- 💩 **[[Manure_Module|Manure Subsystem]]**: Housing scraping, solid-liquid separation, anaerobic digesters, lagoons, emissions.
- ⚡ **[[EEE_Module|Economics, Energy & Emissions (EEE) Subsystem]]**: ASABE tractor fuel, electricity, whole-farm economics, Scope 1-3 GHG LCA.

---

## 🏃 Simulation Runs Ingested

```dataview
TABLE
  scenario as "Scenario",
  duration_days as "Duration (Days)",
  status as "Status",
  execution_date as "Execution Date"
FROM "01_Simulations"
SORT file.name DESC
```

---

## 🔗 Top Cross-Run Empirical Correlations

```dataview
TABLE
  input_param as "Input Parameter",
  output_variable as "Output Variable",
  pearson_r as "Pearson r",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
SORT abs(pearson_r) DESC
LIMIT 20
```

---

## 📂 Vault Navigation

- 📁 `01_Simulations/`: Individual notes for all ingested simulation runs.
- 📁 `02_Parameters/`: Parameter dictionary with default values and causal outputs.
- 📁 `03_Outputs/`: Comprehensive catalog of all output variables and latest metrics.
- 📁 `04_Correlations/`: Statistical cross-run correlation matrices ([[Significant_Correlations]]).
- 📁 `05_Modules/`: Core biophysical and economic subsystem overviews.
"""
    (out_path / "00_Dashboard.md").write_text(dash_content, encoding="utf-8")

    # 3. Generate 01_Simulations/<run_id>.md
    simulations_notes = 0
    if not runs_df.empty:
        for _, r_row in runs_df.iterrows():
            rid = str(r_row["run_id"])
            clean_rid = sanitize_filename(rid)
            scen = str(r_row["scenario_name"])
            exec_dt = str(r_row["execution_date"])
            st_dt = str(r_row["start_date"])
            end_dt = str(r_row["end_date"])
            dur = int(r_row["duration_days"])
            seed = int(r_row["random_seed"])
            status = str(r_row["status"])

            r_frontmatter = {
                "id": rid,
                "type": "simulation_run",
                "scenario": scen,
                "execution_date": exec_dt,
                "start_date": st_dt,
                "end_date": end_dt,
                "duration_days": dur,
                "random_seed": seed,
                "status": status,
                "tags": ["simulation_run", scen],
            }

            r_content = format_yaml_frontmatter(r_frontmatter)
            r_content += f"""# 🏃 Simulation Run: `{rid}`

## 📋 Run Overview

- **Scenario Name**: `{scen}`
- **Execution Date**: `{exec_dt}`
- **Simulation Time Window**: `{st_dt}` to `{end_dt}` (`{dur}` days)
- **Random Seed**: `{seed}`
- **Execution Status**: `{status}`

---

## ⚙️ Key Configured Parameters

| Parameter | Value | Blob |
|---|---|---|
"""
            run_params = sim_with_by_run.get(rid, [])
            if run_params:
                for p_rec in run_params[:40]:
                    pid = p_rec["param_id"]
                    clean_pid = sanitize_filename(pid)
                    p_name = p_rec["param_name"]
                    p_val = p_rec["value"]
                    b_name = p_rec["blob_name"]
                    r_content += f"| [[{clean_pid}|{p_name}]] | `{p_val}` | `{b_name}` |\n"
            else:
                r_content += "| *(Default configuration applied)* | - | - |\n"

            # Top Production Metrics
            r_metrics = metrics_by_run.get(rid, [])
            prod_metrics = [m for m in r_metrics if m.get("category") == "production" or any(k in m["var_name"].lower() for k in ["milk", "yield", "harvest", "produced"])]
            ghg_metrics = [m for m in r_metrics if m.get("category") == "emissions" or any(k in m["var_name"].lower() for k in ["methane", "ch4", "n2o", "co2", "emission", "ammonia"])]

            r_content += """
---

## 🥛 Top Production Metrics

| Output Variable | Module | Mean Value | Min | Max | Unit |
|---|---|---|---|---|---|
"""
            if prod_metrics:
                for pm in prod_metrics[:15]:
                    vname = pm["var_name"]
                    clean_v = sanitize_filename(vname)
                    r_content += f"| [[{clean_v}|{vname}]] | `{pm.get('module', '')}` | `{pm['mean_val']:.3f}` | `{pm['min_val']:.3f}` | `{pm['max_val']:.3f}` | `{pm.get('unit', '')}` |\n"
            else:
                r_content += "| *(No production metrics recorded)* | - | - | - | - | - |\n"

            r_content += """
---

## 🌍 Top Greenhouse Gas & Environmental Emissions Metrics

| Output Variable | Module | Mean Value | Sum Total | Unit |
|---|---|---|---|---|
"""
            if ghg_metrics:
                for gm in ghg_metrics[:15]:
                    vname = gm["var_name"]
                    clean_v = sanitize_filename(vname)
                    r_content += f"| [[{clean_v}|{vname}]] | `{gm.get('module', '')}` | `{gm['mean_val']:.3f}` | `{gm['sum_val']:.3f}` | `{gm.get('unit', '')}` |\n"
            else:
                r_content += "| *(No emissions metrics recorded)* | - | - | - |\n"

            r_content += f"""
---

## 📊 All Ingested Metric Outputs ({len(r_metrics)} variables)

```dataview
TABLE
  module as "Module",
  category as "Category",
  mean_val as "Mean Value",
  unit as "Unit"
FROM "03_Outputs"
WHERE any(contains(runs, "{rid}"))
```
"""
            (sim_dir / f"{clean_rid}.md").write_text(r_content, encoding="utf-8")
            simulations_notes += 1

    # 4. Generate 02_Parameters/<clean_param_id>.md
    parameters_notes = 0
    if not params_df.empty:
        for _, p_row in params_df.iterrows():
            pid = str(p_row["id"])
            clean_pid = sanitize_filename(pid)
            bname = str(p_row["blob_name"])
            pname = str(p_row["param_name"])
            dtype = str(p_row["data_type"])
            unit = str(p_row["unit"])
            def_val = str(p_row["default_value"])
            desc = str(p_row["description"])

            mod_name = blob_module_map.get(bname, classify_config_blob_module(bname))
            mod_note = get_module_note_name(mod_name)

            p_frontmatter = {
                "id": pid,
                "type": "input_parameter",
                "param_name": pname,
                "blob": bname,
                "module": mod_name,
                "data_type": dtype,
                "unit": unit,
                "default": def_val,
                "tags": ["input_parameter", f"{mod_name}_module"],
            }

            p_content = format_yaml_frontmatter(p_frontmatter)
            p_content += f"""# ⚙️ Input Parameter: `{pname}`

- **Full Identifier**: `{pid}`
- **Config Blob**: `{bname}`
- **Owning Module**: [[{mod_note}|{mod_name}]]
- **Data Type**: `{dtype}`
- **Unit**: `{unit or 'N/A'}`
- **Default Value**: `{def_val}`
- **Description**: {desc or 'Configurable model parameter in RuFaS.'}

---

## 🔬 Biophysical Causal Outputs

"""
            causal_outs = causal_by_param.get(pid, [])
            if causal_outs:
                for c_rec in causal_outs:
                    vname = c_rec["var_name"]
                    clean_v = sanitize_filename(vname)
                    vmod = c_rec.get("module", "")
                    vunit = c_rec.get("unit", "")
                    pway = c_rec.get("pathway", "")
                    mech = c_rec.get("mechanism", "")
                    p_content += f"- **[[{clean_v}|{vname}]]** (`{vmod}`, `{vunit or 'N/A'}`)\n"
                    p_content += f"  - **Pathway**: {pway}\n"
                    p_content += f"  - **Mechanism**: {mech}\n"
            else:
                p_content += "- *(No direct biophysical causal links registered)*\n"

            p_content += f"""
---

## 📊 Empirical Cross-Run Correlations

```dataview
TABLE
  output_variable as "Output Variable",
  pearson_r as "Pearson r",
  spearman_r as "Spearman rho",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
WHERE input_param = "{pid}"
SORT abs(pearson_r) DESC
```
"""
            param_corrs = corr_by_param.get(pid, [])
            if param_corrs:
                p_content += """
| Output Variable | Module | Pearson $r$ | Spearman $\\rho$ | $p$-value | Sample Size |
|---|---|---|---|---|---|
"""
                for cr in param_corrs:
                    vname = cr["var_name"]
                    clean_v = sanitize_filename(vname)
                    vmod = cr.get("module", "")
                    p_content += f"| [[{clean_v}|{vname}]] | `{vmod}` | `{cr['pearson_r']:.3f}` | `{cr['spearman_r']:.3f}` | `{cr['p_value']:.4e}` | `{cr['sample_size']}` |\n"

            (param_dir / f"{clean_pid}.md").write_text(p_content, encoding="utf-8")
            parameters_notes += 1

    # 5. Generate 03_Outputs/<clean_var_name>.md
    outputs_notes = 0
    if not vars_df.empty:
        for _, v_row in vars_df.iterrows():
            vname = str(v_row["name"])
            clean_vname = sanitize_filename(vname)
            mod = str(v_row["module"])
            unit = str(v_row["unit"])
            cat = str(v_row["category"])
            rep_cls = str(v_row["reporter_class"])
            desc = str(v_row["description"])
            mod_note = get_module_note_name(mod)

            v_frontmatter = {
                "name": vname,
                "type": "output_variable",
                "module": mod,
                "category": cat,
                "unit": unit,
                "reporter_class": rep_cls,
                "tags": ["output_variable", f"{mod}_module", cat],
            }

            v_content = format_yaml_frontmatter(v_frontmatter)
            v_content += f"""# 📈 Output Variable: `{vname}`

- **Owning Module**: [[{mod_note}|{mod}]]
- **Category**: `{cat}`
- **Unit**: `{unit or 'N/A'}`
- **Reporter Class**: `{rep_cls}`
- **Description**: {desc}

---

## ⚙️ Driving Input Parameters (Biophysical Causal Drivers)

"""
            causal_ins = causal_by_var.get(vname, [])
            if causal_ins:
                for c_rec in causal_ins:
                    pid = c_rec["param_id"]
                    clean_p = sanitize_filename(pid)
                    pname = c_rec.get("param_name", pid)
                    bname = c_rec.get("blob_name", "")
                    pway = c_rec.get("pathway", "")
                    mech = c_rec.get("mechanism", "")
                    v_content += f"- **[[{clean_p}|{pname}]]** (ID: `{pid}`, Blob: `{bname}`)\n"
                    v_content += f"  - **Pathway**: {pway}\n"
                    v_content += f"  - **Mechanism**: {mech}\n"
            else:
                v_content += "- *(No direct causal input parameters registered)*\n"

            v_content += f"""
---

## 📊 Empirical Correlations

```dataview
TABLE
  input_param as "Input Parameter",
  pearson_r as "Pearson r",
  spearman_r as "Spearman rho",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
WHERE output_variable = "{vname}"
SORT abs(pearson_r) DESC
```
"""
            var_corrs = corr_by_var.get(vname, [])
            if var_corrs:
                v_content += """
| Input Parameter | Pearson $r$ | Spearman $\\rho$ | $p$-value | Sample Size |
|---|---|---|---|---|
"""
                for cr in var_corrs:
                    pid = cr["param_id"]
                    clean_p = sanitize_filename(pid)
                    pname = cr.get("param_name", pid)
                    v_content += f"| [[{clean_p}|{pname}]] | `{cr['pearson_r']:.3f}` | `{cr['spearman_r']:.3f}` | `{cr['p_value']:.4e}` | `{cr['sample_size']}` |\n"

            var_metrics = metrics_by_var.get(vname, [])
            v_content += """
---

## 🏃 Simulation Run Values

| Simulation Run | Scenario | Mean Value | Min | Max | Sum Total | Valid Days |
|---|---|---|---|---|---|---|
"""
            if var_metrics:
                for vm in var_metrics:
                    rid = vm["run_id"]
                    clean_r = sanitize_filename(rid)
                    scen = vm.get("scenario_name", "")
                    v_content += f"| [[{clean_r}|{rid}]] | `{scen}` | `{vm['mean_val']:.3f}` | `{vm['min_val']:.3f}` | `{vm['max_val']:.3f}` | `{vm['sum_val']:.3f}` | `{vm['non_null_count']}` |\n"
            else:
                v_content += "| *(No run metrics ingested yet)* | - | - | - | - | - | - |\n"

            (outputs_dir / f"{clean_vname}.md").write_text(v_content, encoding="utf-8")
            outputs_notes += 1

    # 6. Generate 04_Correlations/Significant_Correlations.md
    corr_frontmatter = {
        "title": "Significant Empirical Correlations (|r| >= 0.5)",
        "type": "correlation_index",
        "tags": ["correlations", "cross_run_analysis", "rufas_brain"],
        "total_correlations": corr_count,
    }
    corr_content = format_yaml_frontmatter(corr_frontmatter)
    corr_content += """# 📊 Significant Cross-Run Correlations ($|r| \\ge 0.5$, $p \\le 0.05$)

This document indexes all empirical relationships identified across ingested RuFaS simulation runs with statistical significance ($p \\le 0.05$) and strong correlation ($|r| \\ge 0.5$ or $|\\rho| \\ge 0.5$).

---

## 📈 Top Statistically Significant Correlations

"""
    if not corr_df.empty:
        corr_content += """| Input Parameter | Output Variable | Module | Pearson $r$ | Spearman $\\rho$ | $p$-value | Sample Size ($N$) |
|---|---|---|---|---|---|---|
"""
        for cr in corr_df.to_dict(orient="records")[:100]:
            pid = str(cr["param_id"])
            clean_p = sanitize_filename(pid)
            pname = str(cr.get("param_name") or pid)
            vname = str(cr["var_name"])
            clean_v = sanitize_filename(vname)
            vmod = str(cr.get("module", ""))
            corr_content += f"| [[{clean_p}|{pname}]] | [[{clean_v}|{vname}]] | `{vmod}` | `{cr['pearson_r']:.3f}` | `{cr['spearman_r']:.3f}` | `{cr['p_value']:.4e}` | `{cr['sample_size']}` |\n"
    else:
        corr_content += "*No significant correlations computed across runs yet.*\n"

    corr_content += """
---

## 🔍 Dataview Dynamic Query

```dataview
TABLE
  input_param as "Input Parameter",
  output_variable as "Output Variable",
  pearson_r as "Pearson r",
  spearman_r as "Spearman rho",
  p_value as "p-value",
  sample_size as "Runs Analyzed"
FROM #correlation
SORT abs(pearson_r) DESC
```
"""
    (corr_dir / "Significant_Correlations.md").write_text(corr_content, encoding="utf-8")
    correlations_notes = 1

    # 7. Generate 05_Modules/<ModuleName>.md
    modules_notes = 0
    mod_list = modules_df.to_dict(orient="records") if not modules_df.empty else CANONICAL_MODULES
    for m_rec in mod_list:
        mname = str(m_rec["name"])
        note_name = get_module_note_name(mname)
        display_name = MODULE_DISPLAY_NAMES.get(mname, f"{mname.title()} Subsystem")
        mgr_cls = str(m_rec.get("manager_class", ""))
        desc = str(m_rec.get("description", ""))

        m_frontmatter = {
            "name": mname,
            "type": "biophysical_module",
            "manager_class": mgr_cls,
            "tags": ["rufas_module", mname],
        }

        m_content = format_yaml_frontmatter(m_frontmatter)
        m_content += f"""# 🧩 Module: {display_name}

- **Manager Class**: `{mgr_cls}`
- **Description**: {desc}

---

## 📦 Configuration Files & Parameter Blobs

| Config Blob | Title | Path | Parameters | Format |
|---|---|---|---|---|
"""
        mod_blobs = blobs_by_module.get(mname, [])
        if mod_blobs:
            for b_rec in mod_blobs:
                b_name = b_rec["name"]
                b_title = b_rec.get("title", b_name)
                b_path = b_rec.get("file_path", "")
                b_fmt = b_rec.get("format_type", "json")
                p_count = params_count_by_blob.get(b_name, 0)
                m_content += f"| `{b_name}` | `{b_title}` | `{b_path}` | `{p_count}` | `{b_fmt}` |\n"
        else:
            m_content += "| *(No configuration blobs registered)* | - | - | - | - |\n"

        mod_vars = vars_by_module.get(mname, [])
        m_content += f"""
---

## 📈 Core Output Variables ({len(mod_vars)} variables)

| Variable | Category | Unit | Reporter Class |
|---|---|---|---|
"""
        if mod_vars:
            for v_rec in mod_vars[:50]:
                vname = v_rec["name"]
                clean_v = sanitize_filename(vname)
                cat = v_rec.get("category", "")
                unit = v_rec.get("unit", "")
                rep_cls = v_rec.get("reporter_class", "")
                m_content += f"| [[{clean_v}|{vname}]] | `{cat}` | `{unit}` | `{rep_cls}` |\n"
            if len(mod_vars) > 50:
                m_content += f"| *(... and {len(mod_vars) - 50} more variables in `03_Outputs/`)* | - | - | - |\n"
        else:
            m_content += "| *(No output variables registered for this module)* | - | - | - |\n"

        m_content += f"""
---

## 🔍 Dataview Dynamic Query

```dataview
TABLE
  unit as "Unit",
  category as "Category",
  reporter_class as "Reporter Class"
FROM "03_Outputs"
WHERE module = "{mname}"
SORT file.name ASC
```
"""
        (modules_dir / f"{note_name}.md").write_text(m_content, encoding="utf-8")
        modules_notes += 1

    total_notes = 1 + simulations_notes + parameters_notes + outputs_notes + correlations_notes + modules_notes

    summary = {
        "notes_generated": total_notes,
        "dashboard_notes": 1,
        "simulations_notes": simulations_notes,
        "parameters_notes": parameters_notes,
        "outputs_notes": outputs_notes,
        "correlations_notes": correlations_notes,
        "modules_notes": modules_notes,
    }
    logger.info("Obsidian vault export completed successfully: %s", summary)
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
        default=None,
        help="Path to the root directory of RuFaS codebase (default: auto-detected)",
    )

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a simulation run and compute output metrics")
    ingest_parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Path to RuFaS output directory (containing CSVs)",
    )
    ingest_parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="Unique identifier for the simulation run",
    )
    ingest_parser.add_argument(
        "--scenario",
        type=str,
        default="example_freestall",
        dest="scenario_name",
        help="Scenario name for the simulation run",
    )
    ingest_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    corr_parser = subparsers.add_parser("compute-correlations", help="Compute statistical cross-run correlations")
    corr_parser.add_argument(
        "--min-r",
        type=float,
        default=0.5,
        help="Minimum absolute correlation coefficient threshold (default: 0.5)",
    )
    corr_parser.add_argument(
        "--max-p",
        type=float,
        default=0.05,
        help="Maximum p-value threshold for statistical significance (default: 0.05)",
    )
    corr_parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="Minimum number of simulation runs required (default: 3)",
    )
    corr_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    query_parser = subparsers.add_parser("query", help="Execute an OpenCypher query on the graph memory brain")
    query_parser.add_argument(
        "query",
        type=str,
        help="OpenCypher query to execute",
    )
    query_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    query_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    trace_parser = subparsers.add_parser("trace-impact", help="Trace biophysical causal pathways and statistical correlations for an input parameter")
    trace_parser.add_argument(
        "--param",
        type=str,
        required=True,
        help="Parameter name or search substring",
    )
    trace_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    trace_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    lookup_parser = subparsers.add_parser("lookup-var", help="Lookup output variable metadata, causal drivers, and correlations")
    lookup_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Variable name or search substring",
    )
    lookup_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    lookup_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    export_parser = subparsers.add_parser("export-obsidian", help="Export RuFaS knowledge graph to an Obsidian Markdown vault")
    export_parser.add_argument(
        "--output-dir",
        type=str,
        default="vault",
        help="Target directory path for the Obsidian vault (default: 'vault')",
    )
    export_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    args = parser.parse_args()
    if args.subcommand == "init":
        try:
            conn = init_brain_database(args.db_path)
            summary = populate_structural_ontology(conn, args.rufas_root)
            print(f"RuFaS Graph Memory Brain database initialized at {args.db_path}")
            print(f"Ontology summary: {summary}")
        except RuFaSConfigError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.subcommand == "ingest":
        conn = init_brain_database(args.db_path)
        summary = ingest_simulation_run(
            conn,
            output_dir=args.output_dir,
            run_id=args.run_id,
            scenario_name=args.scenario_name,
        )
        print(f"Simulation run '{args.run_id}' ingested successfully.")
        print(f"Ingestion summary: {summary}")
    elif args.subcommand == "compute-correlations":
        conn = init_brain_database(args.db_path)
        corrs = compute_statistical_correlations(
            conn,
            min_r=args.min_r,
            max_p=args.max_p,
            min_samples=args.min_samples,
        )
        print(f"Correlations computed: Found {len(corrs)} significant relationships (|r| >= {args.min_r}, p <= {args.max_p}).")
        for c in corrs[:20]:
            print(f"  • {c['param_id']} -> {c['var_name']}: Pearson r={c['pearson_r']:.3f}, Spearman rho={c['spearman_r']:.3f}, p={c['p_value']:.4e} (N={c['sample_size']})")
    elif args.subcommand == "query":
        conn = init_brain_database(args.db_path)
        rows = execute_cypher_query(conn, args.query)
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        else:
            if not rows:
                print("Query returned 0 rows.")
            else:
                df = pd.DataFrame(rows)
                print(df.to_string(index=False))
                print(f"\n({len(rows)} row(s) returned)")
    elif args.subcommand == "trace-impact":
        conn = init_brain_database(args.db_path)
        impact = trace_parameter_impact(conn, args.param)
        if args.json:
            print(json.dumps(impact, indent=2, default=str))
        else:
            print("==================================================")
            print(f"Parameter Impact Trace for: '{args.param}'")
            print(f"Matched parameters: {impact['matched_parameters_count']}")
            print("==================================================")
            if impact["matched_parameters_count"] == 0:
                print("No parameters matching query.")
            for p in impact["parameters"]:
                print(f"\n📌 Parameter: {p['id']}")
                print(f"   Name: {p['param_name']} | Blob: {p['blob_name']} | Type: {p['data_type']} | Unit: {p['unit'] or 'N/A'}")
                print(f"   Default: {p['default_value']}")
                if p["description"]:
                    print(f"   Description: {p['description']}")

                print(f"\n   🔬 Biophysical Causal Pathways ({len(p['causal_pathways'])}):")
                if not p["causal_pathways"]:
                    print("      (None identified)")
                for c in p["causal_pathways"]:
                    print(f"      • [{c.get('module', '')}] {c['output_variable']} ({c.get('unit', '')})")
                    print(f"        Pathway: {c['pathway']}")
                    print(f"        Mechanism: {c['mechanism']}")

                print(f"\n   📊 Empirical Statistical Correlations ({len(p['correlations'])}):")
                if not p["correlations"]:
                    print("      (None computed or below threshold)")
                for cr in p["correlations"]:
                    print(f"      • [{cr.get('module', '')}] {cr['output_variable']} ({cr.get('unit', '')})")
                    print(f"        Pearson r: {cr['pearson_r']:.3f} | Spearman rho: {cr['spearman_r']:.3f} | p-val: {cr['p_value']:.4e} (N={cr['sample_size']})")
    elif args.subcommand == "lookup-var":
        conn = init_brain_database(args.db_path)
        var_infos = lookup_variable_info(conn, args.name)
        if args.json:
            print(json.dumps(var_infos, indent=2, default=str))
        else:
            print("==================================================")
            print(f"Variable Lookup for: '{args.name}'")
            print(f"Matched variables: {len(var_infos)}")
            print("==================================================")
            if not var_infos:
                print("No variables matching query.")
            for v in var_infos:
                print(f"\n📈 Variable: {v['name']}")
                print(f"   Module: {v['module']} | Category: {v['category']} | Unit: {v['unit'] or 'N/A'}")
                print(f"   Reporter Class: {v['reporter_class']}")
                print(f"   Description: {v['description']}")

                print(f"\n   ⚙️  Incoming Biophysical Drivers ({len(v['causal_inputs'])}):")
                if not v["causal_inputs"]:
                    print("      (None identified)")
                for ci in v["causal_inputs"]:
                    print(f"      • {ci['param_id']} (Blob: {ci['blob_name']})")
                    print(f"        Pathway: {ci['pathway']}")
                    print(f"        Mechanism: {ci['mechanism']}")

                print(f"\n   📊 Correlated Input Parameters ({len(v['correlated_inputs'])}):")
                if not v["correlated_inputs"]:
                    print("      (None computed)")
                for cri in v["correlated_inputs"]:
                    print(f"      • {cri['param_id']}: Pearson r={cri['pearson_r']:.3f}, Spearman rho={cri['spearman_r']:.3f}, p={cri['p_value']:.4e} (N={cri['sample_size']})")

                if v["run_metrics"]:
                    print(f"\n   🏃 Simulation Run Metrics ({len(v['run_metrics'])}):")
                    for rm in v["run_metrics"]:
                        print(f"      • [{rm['run_id']}] Mean={rm['mean_val']:.3f}, Min={rm['min_val']:.3f}, Max={rm['max_val']:.3f}, Sum={rm['sum_val']:.3f} (N={rm['non_null_count']})")
    elif args.subcommand == "export-obsidian":
        conn = init_brain_database(args.db_path)
        stats = export_obsidian_vault(conn, args.output_dir)
        print(f"Obsidian knowledge graph vault exported to {args.output_dir}")
        print(f"Export statistics: {stats}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()



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

    args = parser.parse_args()
    if args.subcommand == "init":
        conn = init_brain_database(args.db_path)
        summary = populate_structural_ontology(conn, args.rufas_root)
        print(f"RuFaS Graph Memory Brain database initialized at {args.db_path}")
        print(f"Ontology summary: {summary}")
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()



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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RuFaS Graph Memory Brain & Correlation Engine CLI",
        prog="rufas-brain",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    init_parser = subparsers.add_parser("init", help="Initialize KùzuDB brain database")
    init_parser.add_argument(
        "--db-path",
        type=str,
        default="data/rufas_brain.kuzu",
        help="Path to KùzuDB database folder",
    )

    args = parser.parse_args()
    if args.subcommand == "init":
        conn = init_brain_database(args.db_path)
        print(f"RuFaS Graph Memory Brain database initialized at {args.db_path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

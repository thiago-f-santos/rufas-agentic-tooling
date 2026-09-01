#!/usr/bin/env python3
"""
RuFaS Inspector Tool
Validates metadata hierarchy, required blobs, physical file existence,
cross-validation files, and configuration consistency for RuFaS simulations.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from tools.config import (
    RuFaSBoundaryError,
    RuFaSConfigError,
    assert_within_rufas_scope,
    get_rufas_root,
)

REQUIRED_FILE_BLOBS: Set[str] = {
    "config",
    "animal",
    "animal_population",
    "animal_mean_phenotype",
    "animal_top_listing_semen",
    "lactation",
    "economy",
    "emission",
    "purchased_feeds_emissions",
    "purchased_feed_land_use_change_emissions",
    "feed",
    "NRC_Comp",
    "NASEM_Comp",
    "manure_management",
    "manure_processor_connection",
    "crop_configurations",
    "weather",
    "user_feeds",
    "tractor_dataset",
    "EEE_constants",
    "feed_storage_configurations",
    "feed_storage_instances",
}


def load_json(filepath: Path) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def inspect_scenario_metadata(
    metadata_path: Path, rufas_root: Path
) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not metadata_path.exists():
        errors.append(f"Metadata file does not exist: {metadata_path}")
        return False, errors, warnings

    try:
        data = load_json(metadata_path)
    except Exception as e:
        errors.append(f"Failed to parse JSON in {metadata_path}: {e}")
        return False, errors, warnings

    files_dict = data.get("files", {})
    if not files_dict:
        errors.append(f"Missing top-level 'files' key in {metadata_path}")
        return False, errors, warnings

    # Check required blobs
    present_blobs = set(files_dict.keys())
    missing_blobs = REQUIRED_FILE_BLOBS - present_blobs
    if missing_blobs:
        errors.append(
            f"Scenario metadata is missing required file blobs: {sorted(list(missing_blobs))}"
        )

    # Check file paths exist
    for blob_name, blob_info in files_dict.items():
        if isinstance(blob_info, dict):
            rel_path = blob_info.get("path")
            if rel_path:
                full_path = rufas_root / rel_path
                if not full_path.exists():
                    errors.append(
                        f"Blob '{blob_name}' references non-existent path: {rel_path} (full: {full_path})"
                    )
            else:
                warnings.append(f"Blob '{blob_name}' does not have a 'path' field specified.")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def inspect_task_metadata(
    task_metadata_path: Path, rufas_root: Path
) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not task_metadata_path.exists():
        errors.append(f"Task manager metadata not found: {task_metadata_path}")
        return False, errors, warnings

    try:
        tm_meta = load_json(task_metadata_path)
    except Exception as e:
        errors.append(f"Error parsing {task_metadata_path}: {e}")
        return False, errors, warnings

    tasks_info = tm_meta.get("files", {}).get("tasks", {})
    task_data_rel_path = tasks_info.get("path")
    if not task_data_rel_path:
        errors.append("No 'tasks' path specified under 'files' in task manager metadata.")
        return False, errors, warnings

    task_data_file = rufas_root / task_data_rel_path
    if not task_data_file.exists():
        errors.append(f"Task data file not found: {task_data_rel_path} ({task_data_file})")
        return False, errors, warnings

    try:
        task_data = load_json(task_data_file)
    except Exception as e:
        errors.append(f"Error parsing task data file {task_data_file}: {e}")
        return False, errors, warnings

    tasks = task_data.get("tasks", [])
    if not tasks:
        warnings.append(f"No tasks defined in {task_data_file}")

    for idx, task in enumerate(tasks):
        task_type = task.get("task_type")
        scenario_meta_rel = task.get("metadata_file_path")
        if not scenario_meta_rel:
            errors.append(f"Task #{idx} ({task_type}) missing 'metadata_file_path'")
            continue

        scenario_meta_path = rufas_root / scenario_meta_rel
        sub_valid, sub_errors, sub_warnings = inspect_scenario_metadata(
            scenario_meta_path, rufas_root
        )
        for err in sub_errors:
            errors.append(f"[Task #{idx} - {scenario_meta_rel}] {err}")
        for wrn in sub_warnings:
            warnings.append(f"[Task #{idx} - {scenario_meta_rel}] {wrn}")

        # Check cross validation files
        cv_files = task.get("cross_validation_file_paths", [])
        for cv_rel in cv_files:
            cv_path = rufas_root / cv_rel
            if not cv_path.exists():
                errors.append(f"[Task #{idx}] Cross validation file not found: {cv_rel}")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_inspector_targets(
    scenario_path: Optional[Union[str, Path]] = None,
    task_metadata_path: Optional[Union[str, Path]] = None,
    rufas_root: Optional[Union[str, Path]] = None,
    allow_external: bool = False,
) -> Optional[Path]:
    """
    Validates that scenario or task manager metadata paths reside within authorized RuFaS boundaries.
    """
    target = scenario_path or task_metadata_path
    if not target:
        return None
    p = Path(target)
    if not p.is_absolute() and rufas_root:
        p = Path(rufas_root) / p
    return assert_within_rufas_scope(p, rufas_root=rufas_root, allow_external=allow_external)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RuFaS Inspector: Validate metadata hierarchy, schemas, and file links."
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Path to scenario metadata JSON file (e.g. input/metadata/example_freestall_dairy_metadata.json)",
    )
    parser.add_argument(
        "--task-metadata",
        type=str,
        help="Path to task_manager_metadata.json (e.g. input/task_manager_metadata.json)",
    )
    parser.add_argument(
        "--rufas-root",
        type=str,
        default=None,
        help="Path to the root directory of the RuFaS repository (default: auto-detected)",
    )
    parser.add_argument(
        "--allow-external",
        action="store_true",
        default=False,
        help="Allow file access outside authorized RuFaS repository boundaries",
    )

    args = parser.parse_args()
    try:
        rufas_root = get_rufas_root(cli_arg=args.rufas_root)
        print(f"🔍 Inspecting RuFaS inputs using root: {rufas_root}")

        if args.task_metadata:
            tm_path = validate_inspector_targets(
                task_metadata_path=args.task_metadata,
                rufas_root=rufas_root,
                allow_external=args.allow_external,
            )
            print(f"📋 Checking Task Manager Metadata: {tm_path}")
            valid, errors, warnings = inspect_task_metadata(tm_path, rufas_root)
        elif args.scenario:
            sc_path = validate_inspector_targets(
                scenario_path=args.scenario,
                rufas_root=rufas_root,
                allow_external=args.allow_external,
            )
            print(f"📋 Checking Scenario Metadata: {sc_path}")
            valid, errors, warnings = inspect_scenario_metadata(sc_path, rufas_root)
        else:
            # Default check default task manager metadata
            default_tm = rufas_root / "input/task_manager_metadata.json"
            tm_path = validate_inspector_targets(
                task_metadata_path=default_tm,
                rufas_root=rufas_root,
                allow_external=args.allow_external,
            )
            print(f"📋 Checking Default Task Manager Metadata: {tm_path}")
            valid, errors, warnings = inspect_task_metadata(tm_path, rufas_root)
    except (RuFaSConfigError, RuFaSBoundaryError) as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    for wrn in warnings:
        print(f"⚠️  WARNING: {wrn}")
    for err in errors:
        print(f"❌ ERROR: {err}")

    if valid:
        print("✅ Metadata Inspection PASSED: All required blobs and referenced paths exist.")
        sys.exit(0)
    else:
        print(f"❌ Metadata Inspection FAILED with {len(errors)} error(s).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

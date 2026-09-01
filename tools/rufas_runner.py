#!/usr/bin/env python3
"""
RuFaS Runner Tool
Orchestrates RuFaS simulations, ensures output filter configuration,
executes the model, and captures structured error diagnostics.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

from tools.config import (
    RuFaSBoundaryError,
    RuFaSConfigError,
    assert_within_rufas_scope,
    get_rufas_root,
)


def setup_csv_filters(rufas_root: Path, enable_all: bool = True) -> None:
    """
    Ensures output filter files in output/output_filters/ are active.
    In standard RuFaS, renaming `_csv_all_variables.txt` to `csv_all_variables.txt`
    activates complete CSV output variable dumping.
    """
    filters_dir = rufas_root / "output" / "output_filters"
    if not filters_dir.exists():
        return

    inactive_filter = filters_dir / "_csv_all_variables.txt"
    active_filter = filters_dir / "csv_all_variables.txt"

    if enable_all and inactive_filter.exists() and not active_filter.exists():
        print("⚡ Activating csv_all_variables.txt filter for full variable export...")
        inactive_filter.rename(active_filter)


def run_rufas_simulation(
    rufas_root: Path,
    metadata_path: Optional[str] = None,
    output_dir: str = "output/",
    verbosity: str = "errors",
    no_graphics: bool = True,
    clear_output: bool = False,
    extra_args: Optional[List[str]] = None,
) -> int:
    cmd = [
        sys.executable,
        "-m",
        "RUFAS.main",
        "-o",
        output_dir,
        "-v",
        verbosity,
    ]
    if no_graphics:
        cmd.append("-g")
    if clear_output:
        cmd.append("-c")
    if metadata_path:
        cmd.extend(["-p", metadata_path])
    if extra_args:
        cmd.extend(extra_args)

    print(f"🚀 Executing RuFaS simulation command in {rufas_root}:\n  {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(rufas_root), capture_output=True, text=True)

    if result.stdout:
        print("--- Simulation Output ---")
        print(result.stdout)

    if result.returncode != 0:
        print(f"❌ Simulation exited with failure (code {result.returncode})", file=sys.stderr)
        if result.stderr:
            print("--- Standard Error / Traceback ---", file=sys.stderr)
            print(result.stderr, file=sys.stderr)

        # Inspect error logs
        logs_dir = rufas_root / output_dir / "logs"
        errors_file = logs_dir / "errors.txt"
        if errors_file.exists():
            print(f"--- Captured RuFaS Errors from {errors_file} ---", file=sys.stderr)
            with open(errors_file, "r", encoding="utf-8") as f:
                print(f.read(), file=sys.stderr)

        return result.returncode

    print("✅ RuFaS Simulation completed successfully.")
    return 0


def validate_runner_targets(
    metadata_path: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    rufas_root: Optional[Union[str, Path]] = None,
    allow_external: bool = False,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Validates that simulation metadata and output directory paths reside within authorized RuFaS boundaries.
    """
    validated_meta = None
    if metadata_path:
        meta_p = Path(metadata_path)
        if not meta_p.is_absolute() and rufas_root:
            meta_p = Path(rufas_root) / meta_p
        validated_meta = assert_within_rufas_scope(meta_p, rufas_root=rufas_root, allow_external=allow_external)
    elif rufas_root:
        default_meta = Path(rufas_root) / "input/task_manager_metadata.json"
        validated_meta = assert_within_rufas_scope(default_meta, rufas_root=rufas_root, allow_external=allow_external)

    validated_out = None
    if output_dir:
        out_p = Path(output_dir)
        if not out_p.is_absolute() and rufas_root:
            out_p = Path(rufas_root) / out_p
        validated_out = assert_within_rufas_scope(out_p, rufas_root=rufas_root, allow_external=allow_external)
    elif rufas_root:
        default_out = Path(rufas_root) / "output"
        validated_out = assert_within_rufas_scope(default_out, rufas_root=rufas_root, allow_external=allow_external)

    return validated_meta, validated_out


def main() -> None:
    parser = argparse.ArgumentParser(description="RuFaS Runner: Execute and monitor RuFaS simulations.")
    parser.add_argument(
        "--rufas-root",
        type=str,
        default=None,
        help="Path to RuFaS root directory (default: auto-detected)",
    )
    parser.add_argument(
        "--task-metadata",
        "-p",
        type=str,
        default="input/task_manager_metadata.json",
        help="Path to task manager metadata file (default: input/task_manager_metadata.json)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="output/",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--verbosity",
        "-v",
        choices=["errors", "warnings", "logs", "credits", "none"],
        default="errors",
        help="Log verbosity level (default: errors)",
    )
    parser.add_argument(
        "--no-graphics",
        "-g",
        action="store_true",
        default=True,
        help="Suppress graphical plot generation (default: True)",
    )
    parser.add_argument(
        "--clear-output",
        "-c",
        action="store_true",
        help="Clear output directory before run",
    )
    parser.add_argument(
        "--enable-all-csv",
        action="store_true",
        default=True,
        help="Ensure _csv_all_variables.txt is activated (default: True)",
    )
    parser.add_argument(
        "--allow-external",
        action="store_true",
        default=False,
        help="Allow execution and file paths outside authorized RuFaS repository boundaries",
    )

    args, unknown = parser.parse_known_args()
    try:
        rufas_root = get_rufas_root(cli_arg=args.rufas_root)
        meta_path, out_path = validate_runner_targets(
            metadata_path=args.task_metadata,
            output_dir=args.output_dir,
            rufas_root=rufas_root,
            allow_external=args.allow_external,
        )
    except (RuFaSConfigError, RuFaSBoundaryError) as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.enable_all_csv:
        setup_csv_filters(rufas_root, enable_all=True)

    exit_code = run_rufas_simulation(
        rufas_root=rufas_root,
        metadata_path=str(meta_path) if meta_path else args.task_metadata,
        output_dir=str(out_path) if out_path else args.output_dir,
        verbosity=args.verbosity,
        no_graphics=args.no_graphics,
        clear_output=args.clear_output,
        extra_args=unknown,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

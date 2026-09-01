#!/usr/bin/env python3
"""
RuFaS Onboarding & Configuration Wizard (`rufas-setup`)

Provides an interactive CLI wizard and scriptable command-line flags to:
1. Validate and configure an existing RuFaS root path.
2. Clone the upstream RuFaS git repository.
3. Persist settings locally (.rufas.json) or globally (~/.rufas/config.json).
4. Install RuFaS specialist skills into AI CLI runtime environments.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from tools.config import (
    DEFAULT_GIT_URL,
    GLOBAL_CONFIG_DIR,
    GLOBAL_CONFIG_FILE,
    LOCAL_CONFIG_NAME,
    RuFaSConfigError,
    load_config,
    save_config,
    validate_rufas_root,
)
from tools.install_skills import SKILLS, install_plugin, install_skills


def clone_rufas(
    target_dir: Union[str, Path],
    git_url: str = DEFAULT_GIT_URL,
) -> Path:
    """
    Clones upstream RuFaS repository into target_dir.

    Args:
        target_dir: Destination directory path.
        git_url: Git clone URL. Defaults to DEFAULT_GIT_URL.

    Returns:
        Path: Resolved path to the cloned RuFaS repository root.

    Raises:
        RuntimeError: If destination directory is non-empty, git clone fails,
                      or git is not available.
        RuFaSConfigError: If cloned directory does not pass RuFaS validation.
    """
    dest = Path(target_dir).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError(f"Target directory '{dest}' already exists and is not empty.")

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", git_url, str(dest)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else str(e)
        raise RuntimeError(f"Failed to clone RuFaS from {git_url}: {stderr_msg}") from e
    except FileNotFoundError as e:
        raise RuntimeError("git executable not found in PATH.") from e

    is_valid, err = validate_rufas_root(dest)
    if not is_valid:
        raise RuFaSConfigError(f"Cloned repository at {dest} is not a valid RuFaS root: {err}")

    return dest


def setup_rufas_path(
    path_str: Union[str, Path],
    scope: str = "global",
    git_url: Optional[str] = None,
) -> Path:
    """
    Validates a RuFaS path and saves it to configuration.

    Args:
        path_str: Path to RuFaS repository root.
        scope: 'global' (default, ~/.rufas/config.json) or 'local' (.rufas.json).
        git_url: Optional git repository URL.

    Returns:
        Path: Resolved valid RuFaS root path.

    Raises:
        RuFaSConfigError: If path fails RuFaS validation.
        ValueError: If scope is invalid.
    """
    target = Path(path_str).resolve()
    is_valid, err = validate_rufas_root(target)
    if not is_valid:
        raise RuFaSConfigError(f"Invalid RuFaS path '{path_str}': {err}")

    save_config(rufas_root=target, scope=scope, git_url=git_url)
    return target


def install_runtime_skills(
    runtime: str = "all",
    use_symlink: bool = True,
) -> Dict[str, Union[int, bool]]:
    """
    Installs RuFaS specialist skills into AI CLI runtime directories.

    Args:
        runtime: One of 'all', 'universal', 'claude', 'antigravity'.
        use_symlink: If True, creates symlinks; if False, copies files.

    Returns:
        Dict[str, Union[int, bool]]: Mapping of runtime name to number of skills installed or plugin status.
    """
    project_root = Path(__file__).resolve().parent.parent
    skills_source = project_root / "skills"
    home = Path.home()

    destinations = []
    if runtime in ["all", "universal"]:
        destinations.append(("skills", "universal", home / ".agents" / "skills"))
    if runtime in ["all", "claude"]:
        destinations.append(("skills", "claude", home / ".claude" / "skills"))
    if runtime in ["all", "antigravity"]:
        destinations.append(("plugin", "antigravity", home / ".gemini" / "config" / "plugins"))

    results: Dict[str, Union[int, bool]] = {}
    for kind, name, dest in destinations:
        if kind == "plugin":
            success = install_plugin(project_root, dest, use_symlink=use_symlink, dry_run=False)
            results[name] = success
        else:
            count = install_skills(skills_source, dest, use_symlink=use_symlink, dry_run=False)
            results[name] = count

    return results


def interactive_wizard() -> int:
    """
    Interactive terminal setup wizard for onboarding and configuring RuFaS.
    """
    print("\n" + "=" * 60)
    print("🐮 RuFaS Agentic Tooling - Onboarding Setup Wizard")
    print("=" * 60)
    print("Welcome! This wizard will configure your environment for RuFaS modeling.\n")

    # Step 1: RuFaS Repository Setup
    print("Step 1: RuFaS Repository Setup")
    print("--------------------------------")
    print("Do you have RuFaS already installed/cloned on your system?")
    print("  [1] Yes, configure an existing RuFaS directory path")
    print("  [2] No, clone RuFaS from GitHub for me")
    print("  [q] Quit setup")

    choice = input("\nChoice [1/2/q]: ").strip().lower()
    if choice in ["q", "quit", "exit"]:
        print("Setup aborted.")
        return 0

    rufas_root_path: Optional[Path] = None
    git_url = DEFAULT_GIT_URL

    if choice == "1":
        while True:
            raw_path = input("\nEnter path to RuFaS repository: ").strip()
            if not raw_path:
                print("❌ Path cannot be empty. Please try again.")
                continue
            expanded = Path(os.path.expanduser(raw_path)).resolve()
            is_valid, err = validate_rufas_root(expanded)
            if not is_valid:
                print(f"❌ Invalid RuFaS repository: {err}")
                retry = input("Try another path? [Y/n]: ").strip().lower()
                if retry in ["n", "no"]:
                    print("Setup aborted.")
                    return 0
                continue
            rufas_root_path = expanded
            break

    elif choice == "2":
        default_dest = (Path.cwd().parent / "RuFaS").resolve()
        raw_dest = input(f"\nEnter destination path to clone RuFaS [default: {default_dest}]: ").strip()
        target_dest = Path(os.path.expanduser(raw_dest)).resolve() if raw_dest else default_dest

        raw_url = input(f"Git repository URL [default: {DEFAULT_GIT_URL}]: ").strip()
        git_url = raw_url if raw_url else DEFAULT_GIT_URL

        print(f"\n⏳ Cloning RuFaS from {git_url} into {target_dest}...")
        try:
            rufas_root_path = clone_rufas(target_dest, git_url=git_url)
            print(f"✅ RuFaS cloned successfully to {rufas_root_path}")
        except Exception as e:
            print(f"❌ Error during cloning: {e}")
            return 1
    else:
        print("❌ Invalid selection. Setup aborted.")
        return 1

    # Scope Selection
    print("\nConfiguration scope:")
    print("  [1] Global (~/.rufas/config.json) [Default]")
    print("  [2] Local (.rufas.json in current directory)")
    scope_choice = input("Choice [1/2, default 1]: ").strip()
    scope = "local" if scope_choice == "2" else "global"

    try:
        saved_file = save_config(rufas_root_path, scope=scope, git_url=git_url)
        print(f"✅ Configuration saved ({scope}) to: {saved_file}")
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return 1

    # Step 2: AI Skills Installation
    print("\nStep 2: AI Coding Agent Skills")
    print("--------------------------------")
    print("Install RuFaS specialist skills for AI coding agents?")
    print("  [1] All AI runtimes (Universal, Claude Code, Antigravity) [Recommended]")
    print("  [2] Universal only (~/.agents/skills)")
    print("  [3] Claude Code only (~/.claude/skills)")
    print("  [4] Google Antigravity only (~/.gemini/config/plugins/rufas-agentic-tooling)")
    print("  [5] Skip skill installation")

    skills_choice = input("Choice [1-5, default 1]: ").strip()
    if skills_choice in ["1", ""]:
        results = install_runtime_skills("all", use_symlink=True)
        for rt, res in results.items():
            if rt == "antigravity":
                print("  ✅ Antigravity: plugin installed")
            else:
                print(f"  ✅ {rt.capitalize()}: {res}/{len(SKILLS)} skills installed")
    elif skills_choice == "2":
        results = install_runtime_skills("universal", use_symlink=True)
        print(f"  ✅ Universal: {results.get('universal', 0)}/{len(SKILLS)} skills installed")
    elif skills_choice == "3":
        results = install_runtime_skills("claude", use_symlink=True)
        print(f"  ✅ Claude Code: {results.get('claude', 0)}/{len(SKILLS)} skills installed")
    elif skills_choice == "4":
        results = install_runtime_skills("antigravity", use_symlink=True)
        print("  ✅ Antigravity: plugin installed")
    else:
        print("  ⏩ Skipped skills installation.")

    # Step 3: Success Summary
    print("\n" + "=" * 60)
    print("🎉 RuFaS onboarding completed successfully!")
    print("=" * 60)
    print(f"RuFaS Root: {rufas_root_path}")
    print(f"Scope:      {scope}")
    print("\nYou can now run:")
    print("  - rufas-inspect --help")
    print("  - rufas-run --help")
    print("  - rufas-analyze --help")
    print("=" * 60 + "\n")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for rufas-setup.
    """
    parser = argparse.ArgumentParser(
        description="RuFaS Onboarding & Configuration Setup Wizard."
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Directly configure path to existing RuFaS repository directory.",
    )
    parser.add_argument(
        "--clone",
        nargs="?",
        const="../RuFaS",
        default=None,
        help="Clone RuFaS repository from upstream git to specified destination [default: ../RuFaS].",
    )
    parser.add_argument(
        "--git-url",
        type=str,
        default=DEFAULT_GIT_URL,
        help=f"Git upstream URL for cloning [default: {DEFAULT_GIT_URL}].",
    )
    parser.add_argument(
        "--scope",
        choices=["global", "local"],
        default="global",
        help="Configuration scope: 'global' (~/.rufas/config.json) or 'local' (.rufas.json) [default: global].",
    )
    parser.add_argument(
        "--install-skills",
        choices=["all", "universal", "claude", "antigravity"],
        help="Install RuFaS specialist skills into AI agent runtimes.",
    )
    parser.add_argument(
        "--mode",
        choices=["symlink", "copy"],
        default="symlink",
        help="Skill & plugin installation mode: 'symlink' (default) or 'copy'.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch interactive terminal setup wizard.",
    )

    args = parser.parse_args(argv)

    # If --interactive requested, or no flags passed and running in interactive TTY
    has_action_flags = any([args.path, args.clone is not None, args.install_skills])
    if args.interactive or (not has_action_flags and (argv is None or len(argv) == 0) and sys.stdin.isatty()):
        return interactive_wizard()

    if not has_action_flags:
        parser.print_help()
        return 0

    try:
        if args.path:
            resolved = setup_rufas_path(args.path, scope=args.scope, git_url=args.git_url)
            print(f"✅ RuFaS path configured successfully ({args.scope}): {resolved}")

        if args.clone is not None:
            dest = Path(args.clone if args.clone else "../RuFaS")
            cloned = clone_rufas(dest, git_url=args.git_url)
            saved = save_config(cloned, scope=args.scope, git_url=args.git_url)
            print(f"✅ RuFaS cloned and configured successfully ({args.scope}): {cloned}")
            print(f"   Config saved to: {saved}")

        if args.install_skills:
            use_symlink = args.mode == "symlink"
            results = install_runtime_skills(args.install_skills, use_symlink=use_symlink)
            print(f"✅ Installed skills for runtime: {args.install_skills} ({args.mode} mode)")
            for rt, res in results.items():
                if rt == "antigravity":
                    print(f"   - {rt}: plugin installed")
                else:
                    print(f"   - {rt}: {res}/{len(SKILLS)} skills")

        return 0
    except (RuFaSConfigError, RuntimeError, ValueError) as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())


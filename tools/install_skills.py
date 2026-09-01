#!/usr/bin/env python3
"""
RuFaS Skills Installer
Installs all RuFaS specialist skills into recognized AI CLI runtimes:
- Universal / Cross-Runtime: ~/.agents/skills/
- Claude Code: ~/.claude/skills/
- Google Antigravity / Gemini CLI: ~/.gemini/antigravity-cli/skills/
- Project-level: .agents/skills/ in target repositories
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Union

SKILLS = [
    "rufas",
    "rufas-animal",
    "rufas-field",
    "rufas-feed",
    "rufas-manure",
    "rufas-eee",
    "rufas-brain",
]


def _safe_remove(target_path: Path) -> None:
    """Safely removes a file, symlink, or directory tree."""
    if target_path.is_symlink() or os.path.islink(target_path):
        target_path.unlink()
    elif target_path.is_file():
        target_path.unlink()
    elif target_path.is_dir():
        shutil.rmtree(target_path)


def install_plugin(
    repo_root: Path,
    target_plugins_dir: Path,
    plugin_name: str = "rufas-agentic-tooling",
    use_symlink: bool = True,
    dry_run: bool = False,
) -> bool:
    """
    Installs the full repository plugin into the target plugins directory.

    Args:
        repo_root: Path to the rufas-agentic-tooling repository root.
        target_plugins_dir: Path to plugins directory (e.g. ~/.gemini/config/plugins).
        plugin_name: Destination directory or link name.
        use_symlink: If True, creates a symbolic link; if False, copies the directory.
        dry_run: If True, only validates paths without modifying disk.

    Returns:
        bool: True if installation or validation succeeded.
    """
    resolved_root = repo_root.resolve()
    if not dry_run:
        target_plugins_dir.mkdir(parents=True, exist_ok=True)
    plugin_dest = target_plugins_dir / plugin_name

    if dry_run:
        action_verb = "Symlink" if use_symlink else "Copy"
        print(f"  [DRY-RUN] Validated ({action_verb}) plugin '{plugin_name}' -> destination: {plugin_dest}")
        return True

    if plugin_dest.is_symlink() or os.path.islink(plugin_dest) or plugin_dest.exists():
        _safe_remove(plugin_dest)

    if use_symlink:
        plugin_dest.symlink_to(resolved_root, target_is_directory=True)
    else:
        shutil.copytree(resolved_root, plugin_dest)
    return True


def install_skills(
    source_dir: Path,
    target_dir: Path,
    use_symlink: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Installs specialist skills into the target directory as symlinks or copies.

    Args:
        source_dir: Path to the repository `skills/` directory.
        target_dir: Path to runtime skills directory.
        use_symlink: If True, creates symbolic links; if False, copies directories.
        dry_run: If True, validates skills without writing to disk.

    Returns:
        int: Number of skills installed or validated.
    """
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for skill_name in SKILLS:
        skill_src = (source_dir / skill_name).resolve()
        if not skill_src.exists() or not (skill_src / "SKILL.md").exists():
            print(f"⚠️  Skill not found or invalid at: {skill_src}", file=sys.stderr)
            continue
        skill_dest = target_dir / skill_name
        if dry_run:
            action_verb = "Symlink" if use_symlink else "Copy"
            print(f"  [DRY-RUN] Validated ({action_verb}) '{skill_name}' -> destination: {skill_dest}")
        else:
            if skill_dest.is_symlink() or os.path.islink(skill_dest) or skill_dest.exists():
                _safe_remove(skill_dest)
            if use_symlink:
                skill_dest.symlink_to(skill_src, target_is_directory=True)
            else:
                shutil.copytree(skill_src, skill_dest)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install RuFaS specialist skills into AI CLI runtime directories."
    )
    parser.add_argument(
        "--runtime",
        "--target",
        dest="runtime",
        choices=["all", "universal", "claude", "antigravity", "copilot", "custom"],
        default="all",
        help="Target AI CLI runtime (default: all)",
    )
    parser.add_argument(
        "--mode",
        choices=["symlink", "copy"],
        default="symlink",
        help="Installation mode: 'symlink' (default) or 'copy'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry-run discovery and validation without copying or linking files",
    )
    parser.add_argument(
        "--custom-path",
        type=str,
        help="Custom destination directory (required if runtime is 'custom')",
    )
    parser.add_argument(
        "--project-repo",
        type=str,
        help="Target project repository root to install skills into .agents/skills/",
    )

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent
    skills_source = project_root / "skills"

    if not skills_source.exists():
        print(f"❌ Error: Skills directory not found at {skills_source}", file=sys.stderr)
        sys.exit(1)

    use_symlink = args.mode == "symlink"
    home = Path.home()
    destinations = []

    if args.runtime in ["all", "universal", "copilot"]:
        destinations.append(("skills", "Universal (~/.agents/skills)", home / ".agents" / "skills"))
    if args.runtime in ["all", "claude"]:
        destinations.append(("skills", "Claude Code (~/.claude/skills)", home / ".claude" / "skills"))
    if args.runtime in ["all", "antigravity"]:
        destinations.append(
            (
                "plugin",
                "Google Antigravity (~/.gemini/config/plugins/rufas-agentic-tooling)",
                home / ".gemini" / "config" / "plugins",
            )
        )
    if args.runtime == "custom":
        if not args.custom_path:
            print("❌ Error: --custom-path is required when --runtime=custom", file=sys.stderr)
            sys.exit(1)
        destinations.append(("skills", "Custom Path", Path(args.custom_path).resolve()))

    if args.project_repo:
        repo_path = Path(args.project_repo).resolve()
        destinations.append(("skills", f"Project Repo ({repo_path}/.agents/skills)", repo_path / ".agents" / "skills"))

    if args.dry_run:
        print(f"🔍 [DRY-RUN] Discovering and validating RuFaS Specialist Skills & Plugins ({args.mode} mode)...\n")
    else:
        print(f"🚀 Installing RuFaS Specialist Skills & Plugins ({args.mode} mode)...\n")

    for kind, name, path in destinations:
        if kind == "plugin":
            install_plugin(project_root, path, use_symlink=use_symlink, dry_run=args.dry_run)
            action_verb = "validated for" if args.dry_run else ("symlinked to" if use_symlink else "installed to")
            print(f"✅ {name}: plugin {action_verb} `{path / 'rufas-agentic-tooling'}`")
        else:
            installed = install_skills(skills_source, path, use_symlink=use_symlink, dry_run=args.dry_run)
            action_verb = "validated for" if args.dry_run else ("symlinked to" if use_symlink else "installed to")
            print(f"✅ {name}: {installed}/{len(SKILLS)} skills {action_verb} `{path}`")

    status_msg = "Skills validation complete!" if args.dry_run else "Skills installation complete!"
    print(f"\n🎉 {status_msg}")



if __name__ == "__main__":
    main()


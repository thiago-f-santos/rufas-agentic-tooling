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

SKILLS = [
    "rufas-specialist",
    "rufas-animal-specialist",
    "rufas-field-soil-specialist",
    "rufas-feed-storage-specialist",
    "rufas-manure-specialist",
    "rufas-eee-specialist",
]


def install_skills(source_dir: Path, target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for skill_name in SKILLS:
        skill_src = source_dir / skill_name
        if not skill_src.exists():
            print(f"⚠️  Skill not found at: {skill_src}", file=sys.stderr)
            continue
        skill_dest = target_dir / skill_name
        if skill_dest.exists():
            shutil.rmtree(skill_dest)
        shutil.copytree(skill_src, skill_dest)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install RuFaS specialist skills into AI CLI runtime directories."
    )
    parser.add_argument(
        "--runtime",
        choices=["all", "universal", "claude", "antigravity", "copilot", "custom"],
        default="all",
        help="Target AI CLI runtime (default: all)",
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

    home = Path.home()
    destinations = []

    if args.runtime in ["all", "universal", "copilot"]:
        destinations.append(("Universal (~/.agents/skills)", home / ".agents" / "skills"))
    if args.runtime in ["all", "claude"]:
        destinations.append(("Claude Code (~/.claude/skills)", home / ".claude" / "skills"))
    if args.runtime in ["all", "antigravity"]:
        destinations.append(
            (
                "Google Antigravity (~/.gemini/antigravity-cli/skills)",
                home / ".gemini" / "antigravity-cli" / "skills",
            )
        )
    if args.runtime == "custom":
        if not args.custom_path:
            print("❌ Error: --custom-path is required when --runtime=custom", file=sys.stderr)
            sys.exit(1)
        destinations.append(("Custom Path", Path(args.custom_path).resolve()))

    if args.project_repo:
        repo_path = Path(args.project_repo).resolve()
        destinations.append((f"Project Repo ({repo_path}/.agents/skills)", repo_path / ".agents" / "skills"))

    print("🚀 Installing RuFaS Specialist Skills Suite...\n")
    for name, path in destinations:
        installed = install_skills(skills_source, path)
        print(f"✅ {name}: {installed} skills installed to `{path}`")

    print("\n🎉 Skills installation complete!")


if __name__ == "__main__":
    main()

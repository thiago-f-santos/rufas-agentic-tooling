import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
TOOLS_DIR = PROJECT_ROOT / "tools"

DISALLOWED_PATTERNS = [
    re.compile(r"file:///home", re.IGNORECASE),
    re.compile(r"file:///Users", re.IGNORECASE),
    re.compile(r"/home/[a-zA-Z0-9_-]+/", re.IGNORECASE),
    re.compile(r"/Users/[a-zA-Z0-9_-]+/", re.IGNORECASE),
]

# Regex for Markdown links: [text](target)
# Avoid matching image links ![alt](img) or regular text, but markdown links format is [text](url)
MD_LINK_REGEX = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')

SPECIALIST_SKILLS = [
    "rufas",
    "rufas-animal",
    "rufas-brain",
    "rufas-eee",
    "rufas-feed",
    "rufas-field",
    "rufas-manure",
]


def test_no_hardcoded_machine_paths_in_skills_and_tools():
    """Verify that no file in skills/ or tools/ contains hardcoded machine paths."""
    violating_files = []

    # Check skills/
    for file_path in SKILLS_DIR.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                for pattern in DISALLOWED_PATTERNS:
                    if pattern.search(line):
                        violating_files.append(
                            f"{file_path.relative_to(PROJECT_ROOT)}:{line_idx}: {line.strip()}"
                        )

    # Check tools/
    for file_path in TOOLS_DIR.rglob("*.py"):
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                for pattern in DISALLOWED_PATTERNS:
                    if pattern.search(line):
                        violating_files.append(
                            f"{file_path.relative_to(PROJECT_ROOT)}:{line_idx}: {line.strip()}"
                        )

    assert not violating_files, (
        f"Found {len(violating_files)} hardcoded machine path(s):\n"
        + "\n".join(violating_files)
    )


def test_relative_markdown_links_resolve_in_skills():
    """Verify that all relative markdown links in skills/**/*.md resolve to existing files."""
    broken_links = []

    for md_file in SKILLS_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        # Remove code blocks so code snippets/examples aren't parsed as markdown links
        content_no_code = re.sub(r"```[\s\S]*?```", "", content)
        content_no_code = re.sub(r"`[^`]+`", "", content_no_code)

        for match in MD_LINK_REGEX.finditer(content_no_code):
            link_text = match.group(1)
            target = match.group(2).strip()

            # Ignore anchors, web URLs, mailto, etc.
            if target.startswith("#") or target.startswith("http://") or target.startswith("https://") or target.startswith("mailto:"):
                continue

            # Strip anchor if any
            target_path_str = target.split("#")[0].strip()
            if not target_path_str:
                continue

            resolved_path = (md_file.parent / target_path_str).resolve()
            if not resolved_path.exists():
                broken_links.append(
                    f"{md_file.relative_to(PROJECT_ROOT)} -> [{link_text}]({target}) "
                    f"(Resolved to: {resolved_path})"
                )

    assert not broken_links, (
        f"Found {len(broken_links)} broken relative link(s):\n"
        + "\n".join(broken_links)
    )


def test_agent_guardrail_directive_in_specialist_skills():
    """Verify that all specialist skills contain the RuFaS configuration guardrail directive."""
    missing_guardrails = []

    for skill_name in SPECIALIST_SKILLS:
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Skill file {skill_file} does not exist"

        content = skill_file.read_text(encoding="utf-8")
        # Check for presence of rufas-setup and RUFAS_PATH and configuration guidance
        if "rufas-setup" not in content or "RUFAS_PATH" not in content:
            missing_guardrails.append(f"{skill_file.relative_to(PROJECT_ROOT)}")

    assert not missing_guardrails, (
        f"The following specialist skill(s) are missing the RuFaS configuration guardrail directive:\n"
        + "\n".join(missing_guardrails)
    )

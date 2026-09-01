from pathlib import Path
import pytest

SKILL_NAMES = [
    "rufas",
    "rufas-animal",
    "rufas-field",
    "rufas-feed",
    "rufas-manure",
    "rufas-eee",
    "rufas-brain",
]

PROTOCOL_HEADER = "## RuFaS Boundary & Source of Truth Protocol"
GROUND_TRUTH_KEYWORD = "Source of Truth"
SEARCH_SCOPE_KEYWORD = "Autonomous Search Scope"
CONFIRMATION_KEYWORD = "Explicit External Confirmation Gate"
SUBAGENT_DELEGATION_KEYWORD = "Subagent Delegation"


def test_all_skills_have_boundary_protocol():
    tooling_root = Path(__file__).resolve().parent.parent
    skills_dir = tooling_root / "skills"

    for name in SKILL_NAMES:
        skill_file = skills_dir / name / "SKILL.md"
        assert skill_file.exists(), f"Missing SKILL.md for {name}"
        content = skill_file.read_text(encoding="utf-8")

        assert PROTOCOL_HEADER in content, f"{name} SKILL.md is missing '{PROTOCOL_HEADER}'"
        assert GROUND_TRUTH_KEYWORD in content, f"{name} SKILL.md is missing '{GROUND_TRUTH_KEYWORD}'"
        assert SEARCH_SCOPE_KEYWORD in content, f"{name} SKILL.md is missing '{SEARCH_SCOPE_KEYWORD}'"
        assert CONFIRMATION_KEYWORD in content, f"{name} SKILL.md is missing '{CONFIRMATION_KEYWORD}'"
        assert SUBAGENT_DELEGATION_KEYWORD in content, f"{name} SKILL.md is missing '{SUBAGENT_DELEGATION_KEYWORD}'"


def test_agents_md_has_boundary_directive():
    tooling_root = Path(__file__).resolve().parent.parent
    agents_md = tooling_root / "AGENTS.md"
    assert agents_md.exists()
    content = agents_md.read_text(encoding="utf-8")

    assert "Boundary Containment" in content or "RuFaS Boundary" in content, "AGENTS.md missing Boundary Containment directive"
    assert "Source of Truth" in content or "Ground Truth" in content, "AGENTS.md missing Source of Truth directive"
    assert "Subagent" in content, "AGENTS.md missing Subagent propagation directive"

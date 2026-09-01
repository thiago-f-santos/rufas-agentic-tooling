# RuFaS Boundary Containment Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement boundary containment guardrails, source of truth protocol, and CLI protection to prevent agents from searching outside the RuFaS repository in multi-project environments.

**Architecture:** A hybrid enforcement model comprising a Python kernel module (`tools/boundary.py`) with `RuFaSBoundaryError`, CLI path validation with `--allow-external`, standardized `## RuFaS Boundary & Source of Truth Protocol` blocks across all 7 specialist skills, and updated agent guidelines in `AGENTS.md`.

**Tech Stack:** Python 3.11+, `pathlib`, `pytest`, Markdown / AI CLI Skills.

**Spec:** [docs/superpowers/specs/2026-09-01-rufas-boundary-harness-design.md](file:///home/thiago/Projetos/rufas-agentic-tooling/docs/superpowers/specs/2026-09-01-rufas-boundary-harness-design.md)

## Global Constraints

- Never assume ambiguous parameters or paths; always verify or ask.
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
- Confine autonomous exploration exclusively to `<rufas_root>` and `<tooling_root>`.
- Require explicit user confirmation or `--allow-external` for any out-of-scope path access.
- Propagate boundary constraints and `rufas_root` to all subagents.

---

### Task 1: Boundary Kernel Module (`tools/boundary.py`) & Unit Tests

**Files:**
- Create: `tools/boundary.py`
- Test: `tests/test_boundary.py`

**Interfaces:**
- Produces:
  - `class RuFaSBoundaryError(Exception)`
  - `def get_allowed_roots(rufas_root: Optional[Union[str, Path]] = None) -> List[Path]`
  - `def is_path_in_scope(target_path: Union[str, Path], rufas_root: Optional[Union[str, Path]] = None) -> bool`
  - `def assert_within_rufas_scope(target_path: Union[str, Path], rufas_root: Optional[Union[str, Path]] = None, allow_external: bool = False) -> Path`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pathlib import Path
from tools.boundary import (
    RuFaSBoundaryError,
    get_allowed_roots,
    is_path_in_scope,
    assert_within_rufas_scope,
)


def test_get_allowed_roots(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    roots = get_allowed_roots(rufas_root=fake_rufas)
    assert fake_rufas.resolve() in roots
    tooling_root = Path(__file__).resolve().parent.parent
    assert tooling_root in roots


def test_assert_within_rufas_scope_valid(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    target_file = fake_rufas / "RUFAS" / "model.py"
    target_file.parent.mkdir(parents=True)
    target_file.touch()

    resolved = assert_within_rufas_scope(target_file, rufas_root=fake_rufas)
    assert resolved == target_file.resolve()


def test_assert_within_rufas_scope_tooling_root():
    tooling_root = Path(__file__).resolve().parent.parent
    tool_file = tooling_root / "tools" / "config.py"
    resolved = assert_within_rufas_scope(tool_file)
    assert resolved == tool_file.resolve()


def test_assert_within_rufas_scope_violation(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    outside_dir = tmp_path / "OtherProject"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.py"
    outside_file.touch()

    with pytest.raises(RuFaSBoundaryError) as exc_info:
        assert_within_rufas_scope(outside_file, rufas_root=fake_rufas)
    assert "RuFaS Boundary Violation" in str(exc_info.value)


def test_assert_within_rufas_scope_traversal_violation(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    traversal_path = fake_rufas / ".." / "outside.txt"

    with pytest.raises(RuFaSBoundaryError):
        assert_within_rufas_scope(traversal_path, rufas_root=fake_rufas)


def test_assert_within_rufas_scope_allow_external(tmp_path):
    outside_file = tmp_path / "external.json"
    outside_file.touch()
    resolved = assert_within_rufas_scope(outside_file, allow_external=True)
    assert resolved == outside_file.resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boundary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.boundary'`

- [ ] **Step 3: Write implementation in `tools/boundary.py`**

```python
"""
RuFaS Boundary Containment Module
Enforces workspace isolation and prevents out-of-bounds file access by AI agents and CLI tools.
"""

import os
from pathlib import Path
from typing import List, Optional, Union


class RuFaSBoundaryError(Exception):
    """Raised when an operation attempts to access files outside allowed RuFaS repositories."""
    pass


def get_tooling_root() -> Path:
    """Returns the root path of the rufas-agentic-tooling repository."""
    return Path(__file__).resolve().parent.parent


def get_allowed_roots(rufas_root: Optional[Union[str, Path]] = None) -> List[Path]:
    """
    Returns the list of canonical allowed root directories:
    1. Resolved rufas_root (if provided or discoverable)
    2. rufas-agentic-tooling root
    """
    roots: List[Path] = [get_tooling_root().resolve()]

    if rufas_root is not None:
        roots.append(Path(rufas_root).resolve())
    else:
        try:
            from tools.config import get_rufas_root
            discovered_root = get_rufas_root(require_valid=False)
            if discovered_root and discovered_root.exists():
                roots.append(discovered_root.resolve())
        except Exception:
            pass

    return list(dict.fromkeys(roots))


def is_path_in_scope(
    target_path: Union[str, Path],
    rufas_root: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Checks if target_path is within allowed repository boundaries without raising an exception.
    """
    if not target_path:
        return False
    resolved = Path(target_path).resolve()
    allowed_roots = get_allowed_roots(rufas_root=rufas_root)

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def assert_within_rufas_scope(
    target_path: Union[str, Path],
    rufas_root: Optional[Union[str, Path]] = None,
    allow_external: bool = False,
) -> Path:
    """
    Validates that target_path is within allowed boundaries.
    Raises RuFaSBoundaryError if the path is outside allowed roots and allow_external is False.
    """
    if not target_path:
        raise RuFaSBoundaryError("Target path cannot be empty or None.")

    resolved = Path(target_path).resolve()

    if allow_external:
        return resolved

    if is_path_in_scope(resolved, rufas_root=rufas_root):
        return resolved

    allowed_roots = get_allowed_roots(rufas_root=rufas_root)
    roots_str = "\n".join(f"  - {r}" for r in allowed_roots)

    raise RuFaSBoundaryError(
        f"❌ RuFaS Boundary Violation:\n"
        f"The path '{resolved}' is outside the authorized repository boundaries:\n"
        f"{roots_str}\n\n"
        f"Autonomous exploration outside these roots is prohibited.\n"
        f"To access external paths, provide explicit user confirmation or pass '--allow-external'."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_boundary.py -v`
Expected: PASS (all 6 tests passing)

- [ ] **Step 5: Commit**

```bash
git add tools/boundary.py tests/test_boundary.py
git commit -m "feat: implement boundary containment kernel and unit tests"
```

---

### Task 2: Integrate Boundary Validation into `tools/config.py` & CLI Tools

**Files:**
- Modify: `tools/config.py`
- Modify: `tools/rufas_inspector.py`
- Modify: `tools/rufas_analyzer.py`
- Modify: `tools/rufas_runner.py`
- Modify: `tools/rufas_brain.py`
- Test: `tests/test_boundary_cli.py`

**Interfaces:**
- Consumes: `assert_within_rufas_scope`, `RuFaSBoundaryError` from `tools.boundary`
- Produces: Updated CLI parsers accepting `--allow-external` flag and enforcing path scoping on inputs/outputs.

- [ ] **Step 1: Write integration tests for CLI boundary enforcement**

```python
import pytest
from pathlib import Path
from tools.boundary import RuFaSBoundaryError
from tools.config import get_rufas_root
from tools.rufas_inspector import validate_inspector_targets


def test_config_reexports_boundary_error():
    from tools.config import RuFaSBoundaryError as ExportedError
    assert ExportedError is RuFaSBoundaryError


def test_inspector_rejects_out_of_bounds_scenario(tmp_path):
    outside_scenario = tmp_path / "outside_scenario.json"
    outside_scenario.touch()

    with pytest.raises(RuFaSBoundaryError):
        validate_inspector_targets(
            scenario_path=outside_scenario,
            rufas_root=tmp_path / "RuFaS",
            allow_external=False,
        )


def test_inspector_allows_out_of_bounds_when_explicit(tmp_path):
    outside_scenario = tmp_path / "outside_scenario.json"
    outside_scenario.touch()

    resolved = validate_inspector_targets(
        scenario_path=outside_scenario,
        rufas_root=tmp_path / "RuFaS",
        allow_external=True,
    )
    assert resolved == outside_scenario.resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boundary_cli.py -v`
Expected: FAIL (missing imports / functions)

- [ ] **Step 3: Modify `tools/config.py` and CLI tools**

In `tools/config.py`:
- Import `RuFaSBoundaryError`, `assert_within_rufas_scope`, `is_path_in_scope`, `get_allowed_roots` from `tools.boundary`.
- Re-export them in `__all__`.

In `tools/rufas_inspector.py`:
- Add `validate_inspector_targets(scenario_path, rufas_root=None, allow_external=False) -> Path`.
- Add `--allow-external` CLI argument to parser.

In `tools/rufas_analyzer.py`:
- Add `validate_analyzer_targets(output_dir, rufas_root=None, allow_external=False) -> Path`.
- Add `--allow-external` CLI argument to parser.

In `tools/rufas_runner.py`:
- Add `validate_runner_targets(metadata_path, output_dir, rufas_root=None, allow_external=False) -> Tuple[Path, Path]`.
- Add `--allow-external` CLI argument to parser.

In `tools/rufas_brain.py`:
- Add boundary check in database / vault path resolution with `--allow-external` support.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_boundary_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/config.py tools/rufas_inspector.py tools/rufas_analyzer.py tools/rufas_runner.py tools/rufas_brain.py tests/test_boundary_cli.py
git commit -m "feat: integrate boundary validation and --allow-external into CLI tools"
```

---

### Task 3: Update All 7 Specialist Skills & `AGENTS.md` + Compliance Test

**Files:**
- Modify: `skills/rufas/SKILL.md`
- Modify: `skills/rufas-animal/SKILL.md`
- Modify: `skills/rufas-field/SKILL.md`
- Modify: `skills/rufas-feed/SKILL.md`
- Modify: `skills/rufas-manure/SKILL.md`
- Modify: `skills/rufas-eee/SKILL.md`
- Modify: `skills/rufas-brain/SKILL.md`
- Modify: `AGENTS.md`
- Test: `tests/test_skills_compliance.py`

**Interfaces:**
- Produces: Standardized `## RuFaS Boundary & Source of Truth Protocol` block in each skill and repository directives in `AGENTS.md`.

- [ ] **Step 1: Write the skill compliance test**

```python
from pathlib import Path

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


def test_agents_md_has_boundary_directive():
    tooling_root = Path(__file__).resolve().parent.parent
    agents_md = tooling_root / "AGENTS.md"
    assert agents_md.exists()
    content = agents_md.read_text(encoding="utf-8")

    assert "Boundary Containment" in content or "RuFaS Boundary" in content
    assert "Source of Truth" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skills_compliance.py -v`
Expected: FAIL (missing protocol sections in `SKILL.md` files)

- [ ] **Step 3: Update `SKILL.md` files and `AGENTS.md`**

Add the standardized protocol block:
```markdown
## RuFaS Boundary & Source of Truth Protocol

> [!IMPORTANT]
> **Boundary Containment & Ground Truth Rules:**
> 1. **Autonomous Search Scope**: All autonomous file searches (`grep_search`, `find_by_name`, `codegraph_explore`, shell commands) MUST explicitly set `SearchPath` / `SearchDirectory` / `Cwd` to `<rufas_root>` or `<tooling_root>`. NEVER run unscoped searches across parent or sibling directories.
> 2. **Source of Truth Hierarchy**: When explaining mechanics, equations, or defaults, ground answers directly in `<rufas_root>/RUFAS/` Python code and `<rufas_root>/input/metadata/` schemas.
> 3. **Explicit External Confirmation Gate**: If an investigation requires reading files or repositories outside `<rufas_root>` / `<tooling_root>`, the agent MUST halt autonomous search and ask the user for explicit confirmation before proceeding.
> 4. **Subagent Delegation**: Any subagent spawned via `invoke_subagent` MUST explicitly receive the resolved `<rufas_root>` path and these boundary constraints in its prompt.
```

Update `AGENTS.md` with:
- Boundary Containment directive
- Source of Truth Grounding directive
- Subagent Propagation directive

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skills_compliance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ AGENTS.md tests/test_skills_compliance.py
git commit -m "docs: add boundary containment and source of truth protocols to skills and AGENTS.md"
```

---

### Task 4: Skill Installer Sync & Full Suite Verification

**Files:**
- Modify: `tools/install_skills.py`
- Test: `tests/test_boundary.py`, `tests/test_boundary_cli.py`, `tests/test_skills_compliance.py`

- [ ] **Step 1: Test skill installer with `--dry-run` and `--mode symlink`**

Run: `python3 -m tools.install_skills --dry-run`
Expected: Successfully validates all 7 skills and plugins across destinations without errors.

- [ ] **Step 2: Run skill installer to update active runtimes**

Run: `python3 -m tools.install_skills --runtime antigravity`
Expected: Updates `~/.gemini/config/plugins/rufas-agentic-tooling` with updated skills and tools.

- [ ] **Step 3: Run entire pytest test suite**

Run: `pytest tests/ -v`
Expected: All unit, integration, and compliance tests pass (100% green).

- [ ] **Step 4: Commit**

```bash
git add tools/install_skills.py
git commit -m "chore: verify and synchronize updated skills and boundary tooling across runtimes"
```

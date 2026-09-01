# Onboarding, Portability & Multi-Vendor Plugin Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide zero-hardcoded-path portability, intelligent tiered RuFaS path configuration and onboarding (`rufas-setup`), and native multi-vendor plugin manifests for Google Antigravity, Claude Code, and Universal Agent Skills (`npx skills add`).

**Architecture:** A lightweight zero-dependency resolver (`tools/config.py`) manages prioritized resolution (CLI args $\to$ `RUFAS_PATH` $\to$ CWD detection $\to$ `.rufas.json` $\to$ `~/.rufas/config.json` $\to$ interactive prompt/error). An interactive onboarding tool (`rufas-setup`) provides clone and validation workflows. Plugin manifests (`plugin.json`, `.claude-plugin/plugin.json`) and portable relative markdown links enable seamless installation across all AI CLI environments.

**Tech Stack:** Python 3.11+, pytest, json, pathlib, shutil, subprocess.

**Spec:** [`docs/superpowers/specs/2026-08-31-onboarding-portability-and-plugin-ecosystem-design.md`](file:///home/thiago/Projetos/rufas-agentic-tooling/docs/superpowers/specs/2026-08-31-onboarding-portability-and-plugin-ecosystem-design.md)

## Global Constraints

- Never hardcode user machine paths or usernames (e.g. `/home/...` or `file:///home/...`).
- Never perform filesystem-wide hard drive crawling/scanning; rely strictly on explicit config, CWD, or direct user prompt.
- Default Git upstream URL for cloning RuFaS is `https://github.com/RuminantFarmSystems/RuFaS.git`.
- Follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).
- Maintain 100% backward compatibility for CLI arguments (`--rufas-root`).

---

### Task 1: Configuration & Path Resolution Subsystem (`tools/config.py`)

**Files:**
- Create: `tools/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `validate_rufas_root(path: Union[str, Path]) -> Tuple[bool, Optional[str]]`
  - `get_rufas_root(cli_arg: Optional[Union[str, Path]] = None, require_valid: bool = True) -> Path`
  - `load_config(local_first: bool = True) -> dict`
  - `save_config(rufas_root: Union[str, Path], scope: str = "local", git_url: Optional[str] = None) -> Path`

- [ ] **Step 1: Write failing test suite for configuration engine**

```python
# tests/test_config.py
import json
import os
from pathlib import Path
import pytest
from tools.config import (
    validate_rufas_root,
    get_rufas_root,
    load_config,
    save_config,
    RuFaSConfigError,
)


@pytest.fixture
def mock_rufas_repo(tmp_path):
    rufas_dir = tmp_path / "RuFaS"
    rufas_dir.mkdir()
    (rufas_dir / "RUFAS").mkdir()
    (rufas_dir / "RUFAS" / "__init__.py").write_text("# mock", encoding="utf-8")
    (rufas_dir / "input").mkdir()
    (rufas_dir / "input" / "metadata").mkdir()
    (rufas_dir / "input" / "metadata" / "schema.json").write_text("{}", encoding="utf-8")
    return rufas_dir


def test_validate_rufas_root_success(mock_rufas_repo):
    is_valid, msg = validate_rufas_root(mock_rufas_repo)
    assert is_valid is True
    assert msg is None


def test_validate_rufas_root_missing_dir(tmp_path):
    is_valid, msg = validate_rufas_root(tmp_path / "non_existent")
    assert is_valid is False
    assert "does not exist" in msg.lower()


def test_validate_rufas_root_missing_rufas_pkg(tmp_path):
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    is_valid, msg = validate_rufas_root(invalid_dir)
    assert is_valid is False
    assert "missing 'rufas'" in msg.lower()


def test_get_rufas_root_from_cli_arg(mock_rufas_repo):
    resolved = get_rufas_root(cli_arg=str(mock_rufas_repo))
    assert resolved == mock_rufas_repo.resolve()


def test_get_rufas_root_from_env_var(mock_rufas_repo, monkeypatch):
    monkeypatch.setenv("RUFAS_PATH", str(mock_rufas_repo))
    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_save_and_load_local_config(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved_path = save_config(mock_rufas_repo, scope="local")
    assert saved_path.exists()
    assert saved_path.name == ".rufas.json"

    cfg = load_config(local_first=True)
    assert cfg["rufas_root"] == str(mock_rufas_repo.resolve())

    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError or import error.

- [ ] **Step 3: Implement `tools/config.py`**

```python
# tools/config.py
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

DEFAULT_GIT_URL = "https://github.com/RuminantFarmSystems/RuFaS.git"
LOCAL_CONFIG_NAME = ".rufas.json"
GLOBAL_CONFIG_DIR = Path.home() / ".rufas"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"


class RuFaSConfigError(Exception):
    """Raised when RuFaS root path cannot be resolved or is invalid."""
    pass


def validate_rufas_root(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the target path represents a valid RuFaS repository.
    """
    if not path:
        return False, "Path is empty or None."
    p = Path(path).resolve()
    if not p.exists():
        return False, f"Directory does not exist: {p}"
    if not p.is_dir():
        return False, f"Path is not a directory: {p}"

    # Check for RUFAS python package directory
    pkg_dir = p / "RUFAS"
    if not pkg_dir.exists() or not pkg_dir.is_dir():
        return False, f"Directory is missing 'RUFAS' python package directory: {p}"

    # Check for input directory
    input_dir = p / "input"
    if not input_dir.exists() or not input_dir.is_dir():
        return False, f"Directory is missing 'input' configuration directory: {p}"

    return True, None


def load_config(local_first: bool = True) -> Dict[str, str]:
    """
    Loads saved configuration from local .rufas.json or global ~/.rufas/config.json.
    """
    # 1. Local project config
    if local_first:
        local_cfg = Path.cwd() / LOCAL_CONFIG_NAME
        if local_cfg.exists():
            try:
                with open(local_cfg, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    # 2. Global user config
    if GLOBAL_CONFIG_FILE.exists():
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {}


def save_config(
    rufas_root: Union[str, Path],
    scope: str = "local",
    git_url: Optional[str] = None,
) -> Path:
    """
    Saves RuFaS configuration either locally (.rufas.json) or globally (~/.rufas/config.json).
    """
    resolved_root = str(Path(rufas_root).resolve())
    data = {
        "rufas_root": resolved_root,
        "git_url": git_url or DEFAULT_GIT_URL,
    }

    if scope == "local":
        target = Path.cwd() / LOCAL_CONFIG_NAME
    else:
        GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        target = GLOBAL_CONFIG_FILE

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return target


def get_rufas_root(
    cli_arg: Optional[Union[str, Path]] = None,
    require_valid: bool = True,
) -> Path:
    """
    Resolves the RuFaS root path in prioritized order:
    1. CLI Argument
    2. RUFAS_PATH / RUFAS_ROOT environment variables
    3. Current Working Directory check (if running inside RuFaS)
    4. Local configuration (.rufas.json)
    5. Global configuration (~/.rufas/config.json)
    6. Common sibling folder (../RuFaS)
    """
    candidate: Optional[Path] = None

    # 1. CLI Arg
    if cli_arg:
        candidate = Path(cli_arg).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if require_valid and not is_valid:
            raise RuFaSConfigError(f"Specified --rufas-root is invalid: {err}")
        return candidate

    # 2. Environment Variables
    env_path = os.environ.get("RUFAS_PATH") or os.environ.get("RUFAS_ROOT")
    if env_path:
        candidate = Path(env_path).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if require_valid and not is_valid:
            raise RuFaSConfigError(f"RUFAS_PATH environment variable points to invalid directory: {err}")
        return candidate

    # 3. Check CWD (if run inside RuFaS repository directly)
    cwd_valid, _ = validate_rufas_root(Path.cwd())
    if cwd_valid:
        return Path.cwd()

    # 4. Config files (Local and Global)
    cfg = load_config(local_first=True)
    if "rufas_root" in cfg:
        candidate = Path(cfg["rufas_root"]).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if is_valid or not require_valid:
            return candidate

    # 5. Sibling directory fallback
    sibling = (Path.cwd().parent / "RuFaS").resolve()
    sibling_valid, _ = validate_rufas_root(sibling)
    if sibling_valid:
        return sibling

    if require_valid:
        raise RuFaSConfigError(
            "❌ RuFaS project path is not configured or found.\n\n"
            "To configure:\n"
            "  1. Run interactive setup: rufas-setup\n"
            "  2. Or set existing path: rufas-setup --path /path/to/RuFaS\n"
            "  3. Or clone upstream:   rufas-setup --clone\n"
            "  4. Or set env variable: export RUFAS_PATH=/path/to/RuFaS\n"
        )

    return Path.cwd()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/config.py tests/test_config.py
git commit -m "feat(config): add prioritized configuration resolution and validation engine"
```

---

### Task 2: Interactive & Scriptable Onboarding Wizard (`tools/rufas_setup.py`, CLI `rufas-setup`)

**Files:**
- Create: `tools/rufas_setup.py`
- Modify: `pyproject.toml`
- Test: `tests/test_setup.py`

**Interfaces:**
- Consumes: `tools/config.py` (`validate_rufas_root`, `save_config`, `DEFAULT_GIT_URL`)
- Produces: CLI script `rufas-setup` and `tools.rufas_setup:main`

- [ ] **Step 1: Write failing test suite for `rufas_setup.py`**

```python
# tests/test_setup.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from tools.rufas_setup import setup_rufas_path, main


@pytest.fixture
def mock_rufas_dir(tmp_path):
    d = tmp_path / "MyRuFaS"
    d.mkdir()
    (d / "RUFAS").mkdir()
    (d / "RUFAS" / "__init__.py").write_text("# mock", encoding="utf-8")
    (d / "input").mkdir()
    return d


def test_setup_rufas_path_direct_valid(mock_rufas_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg_file = setup_rufas_path(str(mock_rufas_dir), scope="local")
    assert cfg_file.exists()
    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["rufas_root"] == str(mock_rufas_dir.resolve())


def test_setup_rufas_path_invalid(tmp_path):
    with pytest.raises(ValueError, match="invalid"):
        setup_rufas_path(str(tmp_path / "non_existent"), scope="local")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_setup.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement `tools/rufas_setup.py`**

```python
# tools/rufas_setup.py
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from tools.config import (
    DEFAULT_GIT_URL,
    GLOBAL_CONFIG_FILE,
    LOCAL_CONFIG_NAME,
    save_config,
    validate_rufas_root,
)
from tools.install_skills import install_skills, SKILLS


def clone_rufas(
    target_dir: Path,
    git_url: str = DEFAULT_GIT_URL,
) -> Path:
    """Clones RuFaS repository from git_url into target_dir."""
    print(f"📥 Cloning RuFaS from {git_url} into {target_dir}...")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", git_url, str(target_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to clone RuFaS:\n{res.stderr}")
    print(f"✅ Successfully cloned RuFaS to {target_dir}")
    return target_dir


def setup_rufas_path(
    path_str: str,
    scope: str = "global",
    git_url: Optional[str] = None,
) -> Path:
    """Validates path and writes configuration."""
    target_path = Path(path_str).expanduser().resolve()
    is_valid, err = validate_rufas_root(target_path)
    if not is_valid:
        raise ValueError(f"Target directory is invalid: {err}")

    cfg_file = save_config(target_path, scope=scope, git_url=git_url)
    return cfg_file


def interactive_wizard() -> None:
    """Guides user interactively through onboarding setup."""
    print("=" * 60)
    print("🐄 RuFaS Agentic Tooling — Setup & Onboarding Wizard")
    print("=" * 60)
    print("\nRuFaS is required to run simulations, inspect metadata, and analyze models.\n")

    print("1. I already have RuFaS cloned on my machine.")
    print(f"2. Clone RuFaS now from official repository ({DEFAULT_GIT_URL}).")
    print("3. Exit.")

    choice = input("\nSelect an option [1-3] (default: 1): ").strip() or "1"

    if choice == "1":
        while True:
            entered_path = input("Enter the full or relative path to your RuFaS directory: ").strip()
            if not entered_path:
                print("❌ Path cannot be empty.")
                continue
            resolved = Path(entered_path).expanduser().resolve()
            is_valid, err = validate_rufas_root(resolved)
            if not is_valid:
                print(f"❌ Invalid RuFaS directory: {err}")
                retry = input("Try another path? [Y/n]: ").strip().lower()
                if retry == "n":
                    sys.exit(1)
                continue

            scope_choice = input("Save configuration globally (all projects) or locally? [global/local] (default: global): ").strip().lower() or "global"
            cfg_path = save_config(resolved, scope=scope_choice)
            print(f"✅ Configuration saved to: {cfg_path}")
            break

    elif choice == "2":
        default_dest = (Path.cwd().parent / "RuFaS").resolve()
        dest_input = input(f"Destination folder for clone (default: {default_dest}): ").strip()
        dest_path = Path(dest_input).expanduser().resolve() if dest_input else default_dest
        try:
            clone_rufas(dest_path)
            scope_choice = input("Save configuration globally or locally? [global/local] (default: global): ").strip().lower() or "global"
            cfg_path = save_config(dest_path, scope=scope_choice)
            print(f"✅ Configuration saved to: {cfg_path}")
        except Exception as e:
            print(f"❌ Error during cloning: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Setup aborted.")
        sys.exit(0)

    # Prompt skill installation
    install_prompt = input("\nWould you like to install RuFaS specialist skills into your AI CLI assistants (Claude Code, Antigravity, Universal)? [Y/n]: ").strip().lower()
    if install_prompt != "n":
        project_root = Path(__file__).resolve().parent.parent
        skills_src = project_root / "skills"
        home = Path.home()
        targets = [
            ("Universal (~/.agents/skills)", home / ".agents" / "skills"),
            ("Claude Code (~/.claude/skills)", home / ".claude" / "skills"),
            ("Antigravity (~/.gemini/antigravity-cli/skills)", home / ".gemini" / "antigravity-cli" / "skills"),
        ]
        for name, dest in targets:
            cnt = install_skills(skills_src, dest)
            print(f"✅ {name}: {cnt}/{len(SKILLS)} skills installed")

    print("\n🎉 Setup complete! You can now use 'rufas-inspect', 'rufas-run', 'rufas-analyze', and 'rufas-brain'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="RuFaS Tooling Onboarding and Configuration Setup.")
    parser.add_argument("--path", type=str, help="Path to existing RuFaS directory to configure.")
    parser.add_argument("--clone", nargs="?", const="", help="Clone RuFaS from upstream. Optional destination path.")
    parser.add_argument("--scope", choices=["global", "local"], default="global", help="Configuration scope (default: global).")
    parser.add_argument("--install-skills", choices=["all", "universal", "claude", "antigravity"], help="Install specialist skills into specified runtime.")

    args = parser.parse_args()

    if args.path:
        try:
            cfg = setup_rufas_path(args.path, scope=args.scope)
            print(f"✅ RuFaS path configured at: {args.path} (saved to {cfg})")
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.clone is not None:
        target_dir = Path(args.clone).resolve() if args.clone else (Path.cwd().parent / "RuFaS").resolve()
        try:
            clone_rufas(target_dir)
            cfg = setup_rufas_path(str(target_dir), scope=args.scope)
            print(f"✅ RuFaS cloned and configured at: {target_dir} (saved to {cfg})")
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.install_skills:
        project_root = Path(__file__).resolve().parent.parent
        skills_src = project_root / "skills"
        from tools.install_skills import main as install_main
        sys.argv = ["install_skills.py", "--runtime", args.install_skills]
        install_main()
        return

    # Interactive wizard if TTY
    if sys.stdin.isatty():
        interactive_wizard()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `pyproject.toml` to register `rufas-setup`**

```toml
[project.scripts]
rufas-setup = "tools.rufas_setup:main"
rufas-inspect = "tools.rufas_inspector:main"
rufas-run = "tools.rufas_runner:main"
rufas-analyze = "tools.rufas_analyzer:main"
rufas-brain = "tools.rufas_brain:main"
rufas-install-skills = "tools.install_skills:main"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_setup.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/rufas_setup.py tests/test_setup.py pyproject.toml
git commit -m "feat(setup): add interactive onboarding wizard and rufas-setup CLI command"
```

---

### Task 3: Integrate Config Resolver with Operational Tools

**Files:**
- Modify: `tools/rufas_inspector.py`
- Modify: `tools/rufas_runner.py`
- Modify: `tools/rufas_analyzer.py`
- Modify: `tools/rufas_brain.py`
- Modify: `tests/test_tooling.py`

**Interfaces:**
- Consumes: `tools/config.py` (`get_rufas_root`, `validate_rufas_root`, `RuFaSConfigError`)

- [ ] **Step 1: Update `tools/rufas_runner.py` to use `get_rufas_root`**

Update `main()` in `tools/rufas_runner.py` so `--rufas-root` defaults to `None`, and calls `rufas_root = get_rufas_root(cli_arg=args.rufas_root)`.

- [ ] **Step 2: Update `tools/rufas_inspector.py` to use `get_rufas_root`**

Update `main()` in `tools/rufas_inspector.py` so `--rufas-root` defaults to `None`, and calls `rufas_root = get_rufas_root(cli_arg=args.rufas_root)`.

- [ ] **Step 3: Update `tools/rufas_analyzer.py` and `tools/rufas_brain.py` to use `get_rufas_root`**

Update CLI argument parsers and callers to resolve `rufas_root` dynamically.

- [ ] **Step 4: Run test suite to verify tool integration**

Run: `pytest tests/test_tooling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/rufas_inspector.py tools/rufas_runner.py tools/rufas_analyzer.py tools/rufas_brain.py tests/test_tooling.py
git commit -m "refactor(tools): integrate unified config and path resolution across all CLI tools"
```

---

### Task 4: Sanitize Documentation & Skill Links (Zero Hardcoded Paths)

**Files:**
- Modify: `skills/rufas/SKILL.md`
- Modify: `skills/rufas-brain/SKILL.md`
- Modify: `skills/rufas/references/output-and-diagnostics.md`
- Modify: `skills/rufas-animal/SKILL.md`, `skills/rufas-field/SKILL.md`, `skills/rufas-feed/SKILL.md`, `skills/rufas-manure/SKILL.md`, `skills/rufas-eee/SKILL.md`
- Test: `tests/test_links_lint.py`

- [ ] **Step 1: Write link verification test ensuring no hardcoded machine paths**

```python
# tests/test_links_lint.py
from pathlib import Path

def test_no_hardcoded_file_urls_in_skills():
    repo_root = Path(__file__).resolve().parent.parent
    skills_dir = repo_root / "skills"
    
    violations = []
    for md_file in skills_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        if "file:///home" in content or "file:///Users" in content:
            violations.append(str(md_file.relative_to(repo_root)))
            
    assert not violations, f"Files contain hardcoded machine paths: {violations}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_links_lint.py -v`
Expected: FAIL with list of markdown files containing hardcoded paths.

- [ ] **Step 3: Replace absolute links with relative markdown links across all skill files**

Update [skills/rufas/SKILL.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas/SKILL.md), [skills/rufas-brain/SKILL.md](file:///home/thiago/Projetos/rufas-agentic-tooling/skills/rufas-brain/SKILL.md), and all reference files to use portable relative markdown links (`../rufas-animal/SKILL.md`, `references/simulation-flow.md`, etc.).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_links_lint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/ tests/test_links_lint.py
git commit -m "fix(skills): replace absolute machine links with portable relative markdown links"
```

---

### Task 5: Multi-Vendor AI CLI Plugin Manifests (`plugin.json` & `.claude-plugin/plugin.json`)

**Files:**
- Create: `plugin.json`
- Create: `.claude-plugin/plugin.json`
- Modify: `tools/install_skills.py`
- Test: `tests/test_plugins_manifest.py`

- [ ] **Step 1: Write plugin manifest verification tests**

```python
# tests/test_plugins_manifest.py
import json
from pathlib import Path

def test_antigravity_plugin_manifest():
    root = Path(__file__).resolve().parent.parent
    p_json = root / "plugin.json"
    assert p_json.exists()
    with open(p_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "rufas-agentic-tooling"
    assert "skills" in data
    assert len(data["skills"]) == 7

def test_claude_plugin_manifest():
    root = Path(__file__).resolve().parent.parent
    c_json = root / ".claude-plugin" / "plugin.json"
    assert c_json.exists()
    with open(c_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["name"] == "rufas-agentic-tooling"
    assert "skills" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_plugins_manifest.py -v`
Expected: FAIL.

- [ ] **Step 3: Create `plugin.json` and `.claude-plugin/plugin.json`**

Create Antigravity and Claude Code plugin manifests.

- [ ] **Step 4: Update `tools/install_skills.py`**

Ensure `install_skills.py` correctly detects all runtime directories and supports automated discovery.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_plugins_manifest.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add plugin.json .claude-plugin/plugin.json tools/install_skills.py tests/test_plugins_manifest.py
git commit -m "feat(plugins): add Antigravity and Claude Code plugin manifests and installer enhancements"
```

---

### Task 6: Overhaul README & Full Verification

**Files:**
- Modify: `README.md`
- Test: Full test suite (`pytest tests/ -v`)

- [ ] **Step 1: Update `README.md`**

Add 1-minute quickstart, multi-vendor CLI copy-paste commands, onboarding instructions with `rufas-setup`, path resolution explanation, and operational CLI examples.

- [ ] **Step 2: Run complete test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: overhaul README with 1-minute quickstart, vendor plugin guides, and onboarding instructions"
```

---

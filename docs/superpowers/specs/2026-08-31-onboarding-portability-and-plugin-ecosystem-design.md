# Design Specification: Onboarding, Portability & Multi-Vendor Plugin Ecosystem for RuFaS Agentic Tooling

- **Date:** 2026-08-31
- **Status:** Approved
- **Target Repository:** `rufas-agentic-tooling`

---

## 1. Executive Summary & Goals

`rufas-agentic-tooling` is an agentic engineering and domain specialist toolkit for the **RuFaS (Ruminant Farm Systems)** dairy simulation model. Previously, the project suffered from machine-specific absolute path links (`file:///home/thiago/...`), lacked automated RuFaS path discovery/onboarding, rigid default fallbacks (`../RuFaS`), and had no native plugin manifests for modern AI CLI runtimes (Claude Code, Google Antigravity, or Universal `npx skills add`).

This specification defines the architectural design to:
1. **Eliminate All Hardcoded Paths**: Replace all absolute machine URLs with portable relative markdown links.
2. **Implement Robust Configuration Resolution**: Build `tools/config.py` providing prioritized resolution (`--rufas-root` flag $\to$ `RUFAS_PATH` / `RUFAS_ROOT` $\to$ CWD detection $\to$ `.rufas.json` $\to$ `~/.rufas/config.json` $\to$ interactive prompt / actionable error).
3. **Interactive & Automated Onboarding (`rufas-setup`)**: Build a dedicated setup wizard and CLI command to configure existing RuFaS paths or clone upstream from `https://github.com/RuminantFarmSystems/RuFaS.git`.
4. **Multi-Vendor AI CLI Plugin Packaging**:
   - **Google Antigravity**: Native `plugin.json` manifest.
   - **Anthropic Claude Code**: `.claude-plugin/plugin.json` manifest.
   - **Universal Agent Skills**: Standard `skills/` metadata adhering to `agentskills.io` for `npx skills add`.
   - **Multi-Runtime Python Installer**: `install_skills.py` updated to deploy across all detected vendor environments.
5. **Polished Documentation**: Revamp `README.md` with 1-minute quickstart and per-vendor installation snippets.

---

## 2. Architecture & Components

### 2.1 Configuration & Path Resolution Engine (`tools/config.py`)

A zero-external-dependency module that resolves and validates the path to the RuFaS simulation codebase.

#### Resolution Hierarchy (Strict Priority)
1. **Explicit CLI Argument**: `--rufas-root <path>` passed to the tool.
2. **Environment Variables**: `RUFAS_PATH` or `RUFAS_ROOT`.
3. **Current Working Directory (CWD)**: If the command is run inside a valid RuFaS repository (e.g. `.` or parent directories containing `RUFAS/` and `input/metadata/`).
4. **Local Project Config**: `.rufas.json` in the current working directory or tooling root.
5. **User Global Config**: `~/.rufas/config.json` (or `$XDG_CONFIG_HOME/rufas/config.json`).
6. **Interactive Prompt (if TTY)**: Prompts user to input path or clone.
7. **Actionable Error (if Non-Interactive / Headless)**: Raises a clear error with exact remediation commands.

#### Validation Function
```python
def validate_rufas_root(path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validates whether a directory contains a valid RuFaS codebase:
    - Must exist and be a directory.
    - Must contain 'RUFAS' package directory.
    - Must contain 'input' directory with metadata or schemas.
    """
```

#### Configuration File Schema (`.rufas.json` / `~/.rufas/config.json`)
```json
{
  "rufas_root": "/path/to/RuFaS",
  "git_url": "https://github.com/RuminantFarmSystems/RuFaS.git"
}
```

---

### 2.2 Interactive Onboarding Wizard (`tools/rufas_setup.py` & CLI `rufas-setup`)

Provides an interactive setup and cloning assistant for first-time users and automated pipelines.

#### CLI Arguments
- `rufas-setup`: Runs interactive setup if TTY.
- `rufas-setup --path <path>`: Validates and saves `<path>` to configuration.
- `rufas-setup --clone [target_dir]`: Clones `https://github.com/RuminantFarmSystems/RuFaS.git` into `target_dir` (default: `../RuFaS`) and saves configuration.
- `rufas-setup --global`: Saves configuration globally to `~/.rufas/config.json` (default if outside a specific project).
- `rufas-setup --local`: Saves configuration locally to `.rufas.json`.
- `rufas-setup --install-skills [runtime]`: Installs specialist skills to AI CLI targets.

---

### 2.3 Integration with Existing Tools

All tools in `tools/` will import and use `get_rufas_root()` from `tools.config`:
- **`tools/rufas_inspector.py`**: Validates metadata against schemas located at `get_rufas_root() / "input/metadata"`.
- **`tools/rufas_runner.py`**: Executes simulation in `get_rufas_root()`.
- **`tools/rufas_analyzer.py`**: Defaults output directory relative to `get_rufas_root() / "output"`.
- **`tools/rufas_brain.py`**: Populates ontology from `get_rufas_root() / "RUFAS"` and metadata catalogs.
- **`tools/install_skills.py`**: Installs skills across runtime targets.

---

### 2.4 Multi-Vendor Plugin Manifests & Packaging

#### 1. Google Antigravity Plugin (`plugin.json`)
Located at repository root:
```json
{
  "name": "rufas-agentic-tooling",
  "version": "0.2.0",
  "description": "Agentic engineering, knowledge graph brain, and diagnostic toolkit for RuFaS whole-farm dairy modeling.",
  "skills": [
    "skills/rufas",
    "skills/rufas-animal",
    "skills/rufas-field",
    "skills/rufas-feed",
    "skills/rufas-manure",
    "skills/rufas-eee",
    "skills/rufas-brain"
  ],
  "rules": [
    "AGENTS.md"
  ]
}
```

#### 2. Anthropic Claude Code Plugin (`.claude-plugin/plugin.json`)
Located at `.claude-plugin/plugin.json`:
```json
{
  "name": "rufas-agentic-tooling",
  "version": "0.2.0",
  "description": "Specialist skills and diagnostics for RuFaS dairy simulation modeling.",
  "skills": "./skills",
  "rules": "./AGENTS.md"
}
```

#### 3. Universal Agent Skills (`npx skills add`)
All 7 specialist skills in `skills/` adhere to `agentskills.io`:
- `skills/rufas/SKILL.md`
- `skills/rufas-animal/SKILL.md`
- `skills/rufas-field/SKILL.md`
- `skills/rufas-feed/SKILL.md`
- `skills/rufas-manure/SKILL.md`
- `skills/rufas-eee/SKILL.md`
- `skills/rufas-brain/SKILL.md`

Supported invocation:
```bash
npx skills add https://github.com/thiago-f-santos/rufas-agentic-tooling
```

---

### 2.5 Skills Portability & Link Sanitization

All references formatted as `file:///home/thiago/...` will be converted to standard relative links:
- In `skills/rufas/SKILL.md`:
  - `[rufas-animal](../rufas-animal/SKILL.md)`
  - `[rufas-field](../rufas-field/SKILL.md)`
  - `[rufas-feed](../rufas-feed/SKILL.md)`
  - `[rufas-manure](../rufas-manure/SKILL.md)`
  - `[rufas-eee](../rufas-eee/SKILL.md)`
  - `[rufas-brain](../rufas-brain/SKILL.md)`
  - `[simulation-flow.md](references/simulation-flow.md)`
  - `[biophysical-modules.md](references/biophysical-modules.md)`
  - `[eee-and-lifecycle.md](references/eee-and-lifecycle.md)`
  - `[input-metadata-schema.md](references/input-metadata-schema.md)`
  - `[output-and-diagnostics.md](references/output-and-diagnostics.md)`
- In `skills/rufas/references/output-and-diagnostics.md`:
  - `[rufas-animal](../../rufas-animal/SKILL.md)`, etc.
- In `skills/rufas-brain/SKILL.md`:
  - `[rufas](../rufas/SKILL.md)`, etc.

---

### 2.6 Documentation Overhaul (`README.md`)

`README.md` will be rewritten to highlight:
1. **1-Minute Quickstart**:
   - Install via CLI vendor (`claude plugin add`, `agy plugin add`, `npx skills add`) or `pip install -e .` + `rufas-setup`.
2. **Vendor Plugin Installation Matrix**:
   - Clear tabs and copy-paste commands for Google Antigravity, Claude Code, GitHub Copilot, Cursor/Windsurf, and Universal CLI.
3. **Configuration & Onboarding Guide**:
   - How `rufas-setup` works, setting `RUFAS_PATH`, `.rufas.json`, and `~/.rufas/config.json`.
4. **CLI Tools & Skills Documentation**:
   - `rufas-inspect`, `rufas-run`, `rufas-analyze`, `rufas-brain`, `rufas-setup`, `rufas-install-skills`.

---

## 3. Verification & Testing Plan

1. **Unit Tests for Configuration (`tests/test_config.py`)**:
   - Test flag override, environment variable precedence, local config, global config, and validation failure handling.
2. **Unit Tests for Setup & Onboarding (`tests/test_setup.py`)**:
   - Test `--path`, `--clone`, `--global`, `--local`, and invalid path handling.
3. **End-to-End Tool Tests (`tests/test_tooling.py`, `tests/test_brain.py`)**:
   - Verify that all tools function seamlessly using config resolution.
4. **Lint & Link Verification**:
   - Automated test ensuring zero occurrences of `file:///home` in `skills/` and `tools/`.
   - Manifest validation for `plugin.json` and `.claude-plugin/plugin.json`.

---

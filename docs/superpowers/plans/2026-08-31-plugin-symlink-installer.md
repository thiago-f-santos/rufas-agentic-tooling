# Plugin & Specialist Skills Symlink Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform RuFaS skill and plugin installation from physical directory copying into dynamic, platform-aware symbolic links (symlinks), supporting full Antigravity plugin installation (`~/.gemini/config/plugins/rufas-agentic-tooling`) and Universal/Claude skill symlinks (`~/.agents/skills/`, `~/.claude/skills/`).

**Architecture:** Add `install_plugin` and refactor `install_skills` in `tools/install_skills.py` with safe link lifecycle management (`is_symlink()` / `unlink()` vs `rmtree()`), update `tools/rufas_setup.py` runtime installer, and provide comprehensive unit tests and documentation.

**Tech Stack:** Python 3.11+, `pathlib.Path`, `os.symlink`, `shutil`, `pytest`.

**Spec:** In-chat bounded design approved in session `4d0ff3da-9a4d-4864-92af-b57d357b1f82`.

## Global Constraints
- Target paths must be resolved to absolute paths before symlinking (`Path(...).resolve()`).
- Destructive cleanup must distinguish between existing symlinks (`unlink()`) and legacy copied directories (`shutil.rmtree()`).
- Backward compatibility: preserve `--dry-run` and add `--mode {symlink,copy}` with `symlink` as default.
- Semantic Commits format (`feat:`, `fix:`, `test:`, `docs:`).

---

### Task 1: Refactor `tools/install_skills.py` for Plugin & Skill Symlinks

**Files:**
- Modify: `tools/install_skills.py`
- Test: `tests/test_plugins_manifest.py`

**Interfaces:**
- Produces:
  - `install_plugin(repo_root: Path, target_plugins_dir: Path, plugin_name: str = "rufas-agentic-tooling", use_symlink: bool = True, dry_run: bool = False) -> bool`
  - `install_skills(source_dir: Path, target_dir: Path, use_symlink: bool = True, dry_run: bool = False) -> int`

- [x] **Step 1: Write failing tests for `install_plugin` and symlink-based `install_skills`**

```python
def test_install_plugin_symlink(temp_env):
    from tools.install_skills import install_plugin
    plugins_dir = temp_env / "plugins"
    success = install_plugin(REPO_ROOT, plugins_dir, use_symlink=True, dry_run=False)
    assert success is True
    dest = plugins_dir / "rufas-agentic-tooling"
    assert dest.is_symlink()
    assert dest.resolve() == REPO_ROOT.resolve()
```

- [x] **Step 2: Run test to verify failure**

Run: `pytest tests/test_plugins_manifest.py -k test_install_plugin_symlink`
Expected: FAIL (ImportError or AttributeError for `install_plugin`).

- [x] **Step 3: Implement safe link removal and symlink logic in `tools/install_skills.py`**
  - Implement helper `_safe_remove(target_path: Path)` handling symlinks (`unlink()`), files (`unlink()`), and real directories (`shutil.rmtree()`).
  - Implement `install_plugin(...)` with support for `use_symlink` and `dry_run`.
  - Update `install_skills(...)` to accept `use_symlink: bool = True`.
  - Update CLI arguments with `--mode {symlink,copy}`.
  - Update Antigravity destination to `home / ".gemini" / "config" / "plugins"` using `install_plugin`.

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_plugins_manifest.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add tools/install_skills.py tests/test_plugins_manifest.py
git commit -m "feat: add plugin symlink and skill symlink support in installer"
```

---

### Task 2: Update `tools/rufas_setup.py` Runtime Skills Installer

**Files:**
- Modify: `tools/rufas_setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces:
  - `install_runtime_skills(runtime: str = "all", use_symlink: bool = True) -> Dict[str, Union[int, bool]]`

- [x] **Step 1: Write failing test in `tests/test_setup.py` verifying Antigravity plugin symlink**

```python
def test_install_runtime_skills_antigravity_plugin(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    results = install_runtime_skills(runtime="antigravity", use_symlink=True)
    plugin_dest = fake_home / ".gemini" / "config" / "plugins" / "rufas-agentic-tooling"
    assert plugin_dest.is_symlink()
    assert plugin_dest.resolve() == PROJECT_ROOT.resolve()
```

- [x] **Step 2: Run test to verify failure**

Run: `pytest tests/test_setup.py -k test_install_runtime_skills_antigravity_plugin`
Expected: FAIL.

- [x] **Step 3: Update `install_runtime_skills` and `interactive_wizard` in `tools/rufas_setup.py`**
  - Integrate `install_plugin` for Antigravity runtime.
  - Support `use_symlink` parameter across `install_runtime_skills` and CLI options.
  - Add `--mode` option to `rufas-setup` CLI parser.

- [x] **Step 4: Run setup tests to verify they pass**

Run: `pytest tests/test_setup.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add tools/rufas_setup.py tests/test_setup.py
git commit -m "feat: integrate plugin and skill symlinking into rufas-setup wizard"
```

---

### Task 3: Update Documentation in `README.md`

**Files:**
- Modify: `README.md`
- Test: `tests/test_links_lint.py`

- [x] **Step 1: Update README.md with Symlink & Plugin details**
  - Clarify that Antigravity installation links the repository into `~/.gemini/config/plugins/rufas-agentic-tooling`.
  - Clarify that Universal/Claude skills are symlinked to `~/.agents/skills/` and `~/.claude/skills/`.
  - Document `--mode copy` fallback flag.

- [x] **Step 2: Run link linting tests**

Run: `pytest tests/test_links_lint.py -v`
Expected: PASS.

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document symlink-based plugin and skill installation"
```

---

### Task 4: Full Suite Verification

**Files:**
- Run all test suites

- [x] **Step 1: Execute full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS.

- [x] **Step 2: Perform CLI dry-run and live symlink verification**

Run: `python3 tools/install_skills.py --dry-run --runtime all`
Expected: Clean validation output.

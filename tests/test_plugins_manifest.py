"""
Tests for AI CLI Plugin Manifests and Installer

Validates:
- Root Antigravity plugin manifest (plugin.json)
- Claude Code plugin manifest (.claude-plugin/plugin.json)
- Skill directory and SKILL.md integrity referenced in manifests
- Rule files referenced in manifests
- tools/install_skills.py dry-run and installation workflows
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAntigravityPluginManifest:
    """Test suite for Antigravity plugin.json manifest."""

    def test_antigravity_manifest_exists_and_is_valid_json(self):
        manifest_path = REPO_ROOT / "plugin.json"
        assert manifest_path.exists(), f"plugin.json missing at {manifest_path}"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("name") == "rufas-agentic-tooling"
        assert data.get("version") == "0.2.0"
        assert "description" in data
        assert isinstance(data.get("skills"), list)
        assert len(data["skills"]) == 7
        assert isinstance(data.get("rules"), list)
        assert "AGENTS.md" in data["rules"]

    def test_antigravity_manifest_skills_exist_on_disk(self):
        manifest_path = REPO_ROOT / "plugin.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for skill_rel_path in data["skills"]:
            skill_dir = REPO_ROOT / skill_rel_path
            assert skill_dir.is_dir(), f"Skill directory not found: {skill_dir}"
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.is_file(), f"SKILL.md missing in {skill_dir}"
            assert skill_md.stat().st_size > 0

    def test_antigravity_manifest_rules_exist_on_disk(self):
        manifest_path = REPO_ROOT / "plugin.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for rule_rel_path in data["rules"]:
            rule_file = REPO_ROOT / rule_rel_path
            assert rule_file.is_file(), f"Rule file not found: {rule_file}"
            assert rule_file.stat().st_size > 0


class TestClaudePluginManifest:
    """Test suite for Claude Code .claude-plugin/plugin.json manifest."""

    def test_claude_manifest_exists_and_is_valid_json(self):
        manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
        assert manifest_path.exists(), f".claude-plugin/plugin.json missing at {manifest_path}"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("name") == "rufas-agentic-tooling"
        assert data.get("version") == "0.2.0"
        assert "description" in data
        assert data.get("skills") in ["./skills", "skills"]
        assert data.get("rules") in ["./AGENTS.md", "AGENTS.md"]

    def test_claude_manifest_paths_exist_on_disk(self):
        manifest_path = REPO_ROOT / ".claude-plugin" / "plugin.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        skills_path = (REPO_ROOT / data["skills"]).resolve()
        assert skills_path.is_dir(), f"Skills directory not found: {skills_path}"

        rules_path = (REPO_ROOT / data["rules"]).resolve()
        assert rules_path.is_file(), f"Rules file not found: {rules_path}"


class TestInstallSkillsTool:
    """Test suite for tools/install_skills.py script and module functions."""

    @pytest.fixture
    def temp_env(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_install_skills_programmatic(self, temp_env):
        from tools.install_skills import SKILLS, install_skills

        skills_source = REPO_ROOT / "skills"
        target_dir = temp_env / "target_skills"

        count = install_skills(skills_source, target_dir, dry_run=False)
        assert count == len(SKILLS)
        assert count == 7

        for skill in SKILLS:
            installed_skill = target_dir / skill
            assert installed_skill.is_dir()
            assert (installed_skill / "SKILL.md").is_file()

    def test_install_skills_dry_run(self, temp_env):
        from tools.install_skills import SKILLS, install_skills

        skills_source = REPO_ROOT / "skills"
        target_dir = temp_env / "dry_run_skills"

        count = install_skills(skills_source, target_dir, dry_run=True)
        assert count == len(SKILLS)
        assert not target_dir.exists()

    def test_cli_dry_run(self):
        installer_script = REPO_ROOT / "tools" / "install_skills.py"
        cmd = [sys.executable, str(installer_script), "--dry-run", "--runtime", "all"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0
        assert "[DRY-RUN]" in result.stdout
        assert "Skills validation complete!" in result.stdout

    def test_cli_custom_runtime(self, temp_env):
        installer_script = REPO_ROOT / "tools" / "install_skills.py"
        custom_dest = temp_env / "custom_skills"
        cmd = [
            sys.executable,
            str(installer_script),
            "--runtime",
            "custom",
            "--custom-path",
            str(custom_dest),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0
        assert "Skills installation complete!" in result.stdout
        assert custom_dest.exists()
        assert (custom_dest / "rufas" / "SKILL.md").exists()

    def test_cli_custom_runtime_missing_path_fails(self):
        installer_script = REPO_ROOT / "tools" / "install_skills.py"
        cmd = [sys.executable, str(installer_script), "--runtime", "custom"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode != 0
        assert "Error: --custom-path is required" in result.stderr

    def test_cli_project_repo_arg(self, temp_env):
        installer_script = REPO_ROOT / "tools" / "install_skills.py"
        repo_dir = temp_env / "dummy_repo"
        repo_dir.mkdir()
        cmd = [
            sys.executable,
            str(installer_script),
            "--runtime",
            "custom",
            "--custom-path",
            str(temp_env / "dummy_custom"),
            "--project-repo",
            str(repo_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0
        assert (repo_dir / ".agents" / "skills" / "rufas" / "SKILL.md").exists()

    def test_install_plugin_symlink(self, temp_env):
        from tools.install_skills import install_plugin

        plugins_dir = temp_env / "plugins"
        success = install_plugin(REPO_ROOT, plugins_dir, use_symlink=True, dry_run=False)
        assert success is True
        dest = plugins_dir / "rufas-agentic-tooling"
        assert dest.is_symlink()
        assert dest.resolve() == REPO_ROOT.resolve()

    def test_install_plugin_copy(self, temp_env):
        from tools.install_skills import install_plugin

        plugins_dir = temp_env / "plugins"
        success = install_plugin(REPO_ROOT, plugins_dir, use_symlink=False, dry_run=False)
        assert success is True
        dest = plugins_dir / "rufas-agentic-tooling"
        assert dest.is_dir()
        assert not dest.is_symlink()
        assert (dest / "plugin.json").is_file()

    def test_install_plugin_dry_run(self, temp_env):
        from tools.install_skills import install_plugin

        plugins_dir = temp_env / "plugins"
        success = install_plugin(REPO_ROOT, plugins_dir, use_symlink=True, dry_run=True)
        assert success is True
        assert not (plugins_dir / "rufas-agentic-tooling").exists()

    def test_install_plugin_idempotent_replace(self, temp_env):
        from tools.install_skills import install_plugin

        plugins_dir = temp_env / "plugins"
        dest = plugins_dir / "rufas-agentic-tooling"
        # First install as copy
        install_plugin(REPO_ROOT, plugins_dir, use_symlink=False, dry_run=False)
        assert dest.is_dir() and not dest.is_symlink()
        # Re-install as symlink (must replace safely)
        install_plugin(REPO_ROOT, plugins_dir, use_symlink=True, dry_run=False)
        assert dest.is_symlink()
        assert dest.resolve() == REPO_ROOT.resolve()

    def test_install_skills_symlink_mode(self, temp_env):
        from tools.install_skills import SKILLS, install_skills

        skills_source = REPO_ROOT / "skills"
        target_dir = temp_env / "symlink_skills"

        count = install_skills(skills_source, target_dir, use_symlink=True, dry_run=False)
        assert count == len(SKILLS)

        for skill in SKILLS:
            installed_skill = target_dir / skill
            assert installed_skill.is_symlink()
            assert installed_skill.resolve() == (skills_source / skill).resolve()

    def test_cli_mode_flag_symlink(self, temp_env):
        installer_script = REPO_ROOT / "tools" / "install_skills.py"
        custom_dest = temp_env / "custom_symlink"
        cmd = [
            sys.executable,
            str(installer_script),
            "--runtime",
            "custom",
            "--custom-path",
            str(custom_dest),
            "--mode",
            "symlink",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        assert result.returncode == 0
        assert (custom_dest / "rufas").is_symlink()


import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.config import (
    DEFAULT_GIT_URL,
    GLOBAL_CONFIG_DIR,
    GLOBAL_CONFIG_FILE,
    LOCAL_CONFIG_NAME,
    RuFaSConfigError,
    load_config,
)
from tools.rufas_setup import (
    clone_rufas,
    install_runtime_skills,
    interactive_wizard,
    main,
    setup_rufas_path,
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


# ==============================================================================
# setup_rufas_path Tests
# ==============================================================================


def test_setup_rufas_path_valid_global(mock_rufas_repo, tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    resolved = setup_rufas_path(mock_rufas_repo, scope="global")
    assert resolved == mock_rufas_repo.resolve()
    assert fake_global_file.exists()

    cfg = load_config(local_first=False)
    assert cfg["rufas_root"] == str(mock_rufas_repo.resolve())


def test_setup_rufas_path_valid_local(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = setup_rufas_path(str(mock_rufas_repo), scope="local")
    assert resolved == mock_rufas_repo.resolve()

    local_file = tmp_path / LOCAL_CONFIG_NAME
    assert local_file.exists()

    cfg = load_config(local_first=True)
    assert cfg["rufas_root"] == str(mock_rufas_repo.resolve())


def test_setup_rufas_path_with_custom_git_url(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom_url = "https://github.com/myfork/RuFaS.git"
    setup_rufas_path(mock_rufas_repo, scope="local", git_url=custom_url)

    cfg = load_config(local_first=True)
    assert cfg["git_url"] == custom_url


def test_setup_rufas_path_invalid(tmp_path):
    invalid_path = tmp_path / "non_existent"
    with pytest.raises(RuFaSConfigError, match="Invalid RuFaS path"):
        setup_rufas_path(invalid_path)


def test_setup_rufas_path_invalid_scope(mock_rufas_repo):
    with pytest.raises(ValueError, match="Invalid scope"):
        setup_rufas_path(mock_rufas_repo, scope="invalid_scope")


# ==============================================================================
# clone_rufas Tests
# ==============================================================================


def test_clone_rufas_success(tmp_path, monkeypatch):
    target_dir = tmp_path / "cloned_rufas"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        assert cmd[0] == "git"
        assert cmd[1] == "clone"
        assert cmd[2] == DEFAULT_GIT_URL
        assert cmd[3] == str(target_dir.resolve())
        # Create minimal valid structure
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "RUFAS").mkdir()
        (target_dir / "input").mkdir()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    cloned_path = clone_rufas(target_dir)
    assert cloned_path == target_dir.resolve()
    assert (cloned_path / "RUFAS").exists()
    assert (cloned_path / "input").exists()


def test_clone_rufas_custom_git_url(tmp_path, monkeypatch):
    target_dir = tmp_path / "cloned_custom"
    custom_url = "https://github.com/custom/RuFaS.git"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        assert cmd[2] == custom_url
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "RUFAS").mkdir()
        (target_dir / "input").mkdir()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    cloned_path = clone_rufas(target_dir, git_url=custom_url)
    assert cloned_path == target_dir.resolve()


def test_clone_rufas_target_exists_and_not_empty(tmp_path):
    target_dir = tmp_path / "non_empty"
    target_dir.mkdir()
    (target_dir / "somefile.txt").write_text("data", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists and is not empty"):
        clone_rufas(target_dir)


def test_clone_rufas_subprocess_error(tmp_path, monkeypatch):
    target_dir = tmp_path / "fail_dir"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=cmd,
            output="",
            stderr="fatal: remote repository not found",
        )

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(RuntimeError, match="Failed to clone RuFaS from"):
        clone_rufas(target_dir)


def test_clone_rufas_git_not_found(tmp_path, monkeypatch):
    target_dir = tmp_path / "no_git_dir"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        raise FileNotFoundError("No such file or directory: 'git'")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(RuntimeError, match="git executable not found"):
        clone_rufas(target_dir)


def test_clone_rufas_invalid_cloned_content(tmp_path, monkeypatch):
    target_dir = tmp_path / "empty_clone"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        target_dir.mkdir(parents=True, exist_ok=True)
        # Empty directory without RUFAS and input
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(RuFaSConfigError, match="not a valid RuFaS root"):
        clone_rufas(target_dir)


# ==============================================================================
# install_runtime_skills Tests
# ==============================================================================


def test_install_runtime_skills_all(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    results = install_runtime_skills(runtime="all")
    assert "universal" in results
    assert "claude" in results
    assert "antigravity" in results
    assert (fake_home / ".agents" / "skills" / "rufas").exists()
    assert (fake_home / ".claude" / "skills" / "rufas").exists()
    assert (fake_home / ".gemini" / "antigravity-cli" / "skills" / "rufas").exists()


def test_install_runtime_skills_claude(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    results = install_runtime_skills(runtime="claude")
    assert "claude" in results
    assert "universal" not in results
    assert (fake_home / ".claude" / "skills" / "rufas").exists()
    assert not (fake_home / ".agents" / "skills").exists()


# ==============================================================================
# CLI main() Tests
# ==============================================================================


def test_main_cli_path_global(mock_rufas_repo, tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    exit_code = main(["--path", str(mock_rufas_repo), "--scope", "global"])
    assert exit_code == 0
    assert fake_global_file.exists()

    captured = capsys.readouterr()
    assert "RuFaS path configured successfully" in captured.out


def test_main_cli_path_local(mock_rufas_repo, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["--path", str(mock_rufas_repo), "--scope", "local"])
    assert exit_code == 0
    assert (tmp_path / LOCAL_CONFIG_NAME).exists()

    captured = capsys.readouterr()
    assert "RuFaS path configured successfully" in captured.out


def test_main_cli_path_invalid(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--path", str(tmp_path / "non_existent")])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "Error:" in captured.err or "Invalid" in captured.err or "Error:" in captured.out


def test_main_cli_clone(tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    target_dir = tmp_path / "cloned_rufas"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "RUFAS").mkdir()
        (target_dir / "input").mkdir()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    exit_code = main(["--clone", str(target_dir), "--scope", "global"])
    assert exit_code == 0
    assert fake_global_file.exists()
    captured = capsys.readouterr()
    assert "RuFaS cloned and configured successfully" in captured.out


def test_main_cli_clone_default_dir(tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    default_target = (tmp_path / "work" / "RuFaS").resolve()
    work_dir = tmp_path / "work" / "rufas-agentic-tooling"
    work_dir.mkdir(parents=True)
    monkeypatch.chdir(work_dir)

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        dest = Path(cmd[3])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "RUFAS").mkdir()
        (dest / "input").mkdir()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    exit_code = main(["--clone", "--scope", "global"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RuFaS cloned and configured successfully" in captured.out


def test_main_cli_install_skills_arg(tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    exit_code = main(["--install-skills", "claude"])
    assert exit_code == 0
    assert (fake_home / ".claude" / "skills" / "rufas").exists()
    captured = capsys.readouterr()
    assert "skills" in captured.out.lower()


def test_main_cli_interactive_flag(monkeypatch):
    mock_wizard = MagicMock(return_value=0)
    monkeypatch.setattr("tools.rufas_setup.interactive_wizard", mock_wizard)

    exit_code = main(["--interactive"])
    assert exit_code == 0
    mock_wizard.assert_called_once()


def test_main_cli_no_args_notty(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    exit_code = main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower() or "options:" in captured.out.lower() or "help" in captured.out.lower()


def test_main_cli_no_args_tty(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    mock_wizard = MagicMock(return_value=0)
    monkeypatch.setattr("tools.rufas_setup.interactive_wizard", mock_wizard)

    exit_code = main([])
    assert exit_code == 0
    mock_wizard.assert_called_once()


# ==============================================================================
# interactive_wizard Tests
# ==============================================================================


def test_interactive_wizard_existing_path(mock_rufas_repo, tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    inputs = iter(["1", str(mock_rufas_repo), "1", "5"])  # 1=existing, path, 1=global scope, 5=skip skills
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    exit_code = interactive_wizard()
    assert exit_code == 0
    assert fake_global_file.exists()
    captured = capsys.readouterr()
    assert "RuFaS onboarding completed successfully" in captured.out


def test_interactive_wizard_clone(tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    target_dir = tmp_path / "cloned_wizard"

    def mock_subprocess_run(cmd, capture_output=True, text=True, check=True):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "RUFAS").mkdir()
        (target_dir / "input").mkdir()
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    inputs = iter(["2", str(target_dir), "", "1", "5"])  # 2=clone, dest, default git url, 1=global, 5=skip skills
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    exit_code = interactive_wizard()
    assert exit_code == 0
    assert fake_global_file.exists()
    captured = capsys.readouterr()
    assert "RuFaS onboarding completed successfully" in captured.out


def test_interactive_wizard_with_skills_installed(mock_rufas_repo, tmp_path, monkeypatch, capsys):
    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    inputs = iter(["1", str(mock_rufas_repo), "1", "1"])  # 1=existing, path, 1=global, 1=all skills
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    exit_code = interactive_wizard()
    assert exit_code == 0
    assert (fake_home / ".agents" / "skills" / "rufas").exists()
    assert (fake_home / ".claude" / "skills" / "rufas").exists()
    assert (fake_home / ".gemini" / "antigravity-cli" / "skills" / "rufas").exists()
    captured = capsys.readouterr()
    assert "RuFaS onboarding completed successfully" in captured.out


def test_interactive_wizard_quit(monkeypatch, capsys):
    inputs = iter(["q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    exit_code = interactive_wizard()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Setup aborted" in captured.out

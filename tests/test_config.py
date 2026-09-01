import json
import os
import sys
from pathlib import Path
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
    get_rufas_root,
    load_config,
    save_config,
    validate_rufas_root,
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


def test_validate_rufas_root_none_or_empty():
    is_valid, msg = validate_rufas_root(None)
    assert is_valid is False
    assert "empty or None" in msg

    is_valid, msg = validate_rufas_root("")
    assert is_valid is False
    assert "empty or None" in msg


def test_validate_rufas_root_missing_dir(tmp_path):
    is_valid, msg = validate_rufas_root(tmp_path / "non_existent")
    assert is_valid is False
    assert "does not exist" in msg.lower()


def test_validate_rufas_root_file_not_dir(tmp_path):
    dummy_file = tmp_path / "file.txt"
    dummy_file.write_text("hello", encoding="utf-8")
    is_valid, msg = validate_rufas_root(dummy_file)
    assert is_valid is False
    assert "not a directory" in msg.lower()


def test_validate_rufas_root_missing_rufas_pkg(tmp_path):
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "input").mkdir()
    is_valid, msg = validate_rufas_root(invalid_dir)
    assert is_valid is False
    assert "missing 'rufas'" in msg.lower()


def test_validate_rufas_root_missing_input_dir(tmp_path):
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "RUFAS").mkdir()
    is_valid, msg = validate_rufas_root(invalid_dir)
    assert is_valid is False
    assert "missing 'input'" in msg.lower()


def test_get_rufas_root_from_cli_arg(mock_rufas_repo):
    resolved = get_rufas_root(cli_arg=str(mock_rufas_repo))
    assert resolved == mock_rufas_repo.resolve()


def test_get_rufas_root_from_cli_arg_invalid(tmp_path):
    with pytest.raises(RuFaSConfigError, match="Specified --rufas-root is invalid"):
        get_rufas_root(cli_arg=str(tmp_path / "non_existent"))


def test_get_rufas_root_from_cli_arg_invalid_no_require(tmp_path):
    invalid_path = tmp_path / "non_existent"
    resolved = get_rufas_root(cli_arg=str(invalid_path), require_valid=False)
    assert resolved == invalid_path.resolve()


def test_get_rufas_root_from_env_rufas_path(mock_rufas_repo, monkeypatch):
    monkeypatch.setenv("RUFAS_PATH", str(mock_rufas_repo))
    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_get_rufas_root_from_env_rufas_root(mock_rufas_repo, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.setenv("RUFAS_ROOT", str(mock_rufas_repo))
    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_get_rufas_root_from_env_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("RUFAS_PATH", str(tmp_path / "invalid"))
    with pytest.raises(RuFaSConfigError, match="RUFAS_PATH environment variable points to invalid directory"):
        get_rufas_root()


def test_get_rufas_root_from_env_rufas_root_invalid(tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.setenv("RUFAS_ROOT", str(tmp_path / "invalid"))
    with pytest.raises(RuFaSConfigError, match="RUFAS_ROOT environment variable points to invalid directory"):
        get_rufas_root()


def test_get_rufas_root_from_cwd(mock_rufas_repo, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    monkeypatch.chdir(mock_rufas_repo)
    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_save_and_load_local_config(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    saved_path = save_config(mock_rufas_repo, scope="local")
    assert saved_path.exists()
    assert saved_path.name == LOCAL_CONFIG_NAME

    cfg = load_config(local_first=True)
    assert cfg["rufas_root"] == str(mock_rufas_repo.resolve())
    assert cfg["git_url"] == DEFAULT_GIT_URL

    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_save_and_load_global_config(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    fake_home = tmp_path / "fake_home"
    fake_global_dir = fake_home / ".rufas"
    fake_global_file = fake_global_dir / "config.json"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_DIR", fake_global_dir)
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_global_file)

    saved_path = save_config(mock_rufas_repo, scope="global", git_url="https://custom.git")
    assert saved_path == fake_global_file
    assert saved_path.exists()

    cfg = load_config(local_first=True)
    assert cfg["rufas_root"] == str(mock_rufas_repo.resolve())
    assert cfg["git_url"] == "https://custom.git"

    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_save_config_invalid_scope(mock_rufas_repo):
    with pytest.raises(ValueError, match="Invalid scope"):
        save_config(mock_rufas_repo, scope="unsupported_scope")


def test_get_rufas_root_from_sibling(mock_rufas_repo, tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_home / ".rufas" / "config.json")

    # Sibling structure: tmp_path / "RuFaS" (mock_rufas_repo) and tmp_path / "other_tooling"
    other_dir = tmp_path / "other_tooling"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)

    resolved = get_rufas_root()
    assert resolved == mock_rufas_repo.resolve()


def test_get_rufas_root_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_home / ".rufas" / "config.json")

    isolated_dir = tmp_path / "isolated" / "sub"
    isolated_dir.mkdir(parents=True)
    monkeypatch.chdir(isolated_dir)

    with pytest.raises(RuFaSConfigError, match="RuFaS project path is not configured or found"):
        get_rufas_root(require_valid=True)


def test_get_rufas_root_not_found_no_require(tmp_path, monkeypatch):
    monkeypatch.delenv("RUFAS_PATH", raising=False)
    monkeypatch.delenv("RUFAS_ROOT", raising=False)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_home / ".rufas" / "config.json")

    isolated_dir = tmp_path / "isolated" / "sub"
    isolated_dir.mkdir(parents=True)
    monkeypatch.chdir(isolated_dir)

    resolved = get_rufas_root(require_valid=False)
    assert resolved == isolated_dir.resolve()


def test_load_config_corrupted_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("tools.config.GLOBAL_CONFIG_FILE", fake_home / ".rufas" / "config.json")
    (tmp_path / LOCAL_CONFIG_NAME).write_text("invalid json {", encoding="utf-8")
    cfg = load_config(local_first=True)
    assert cfg == {}

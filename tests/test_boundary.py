import pytest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.boundary import (
    RuFaSBoundaryError,
    get_tooling_root,
    get_allowed_roots,
    is_path_in_scope,
    assert_within_rufas_scope,
)


def test_get_tooling_root():
    tooling_root = get_tooling_root()
    assert isinstance(tooling_root, Path)
    assert (tooling_root / "tools").is_dir()
    assert (tooling_root / "pyproject.toml").is_file()


def test_get_allowed_roots(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    roots = get_allowed_roots(rufas_root=fake_rufas)
    assert fake_rufas.resolve() in roots
    tooling_root = get_tooling_root().resolve()
    assert tooling_root in roots


def test_get_allowed_roots_none():
    roots = get_allowed_roots(rufas_root=None)
    tooling_root = get_tooling_root().resolve()
    assert tooling_root in roots


def test_is_path_in_scope(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    inside_file = fake_rufas / "model.py"
    inside_file.touch()

    assert is_path_in_scope(inside_file, rufas_root=fake_rufas) is True
    assert is_path_in_scope(inside_file.resolve(), rufas_root=fake_rufas) is True

    outside_file = tmp_path / "outside.txt"
    outside_file.touch()
    assert is_path_in_scope(outside_file, rufas_root=fake_rufas) is False

    assert is_path_in_scope(None, rufas_root=fake_rufas) is False
    assert is_path_in_scope("", rufas_root=fake_rufas) is False


def test_assert_within_rufas_scope_valid(tmp_path):
    fake_rufas = tmp_path / "RuFaS"
    fake_rufas.mkdir()
    target_file = fake_rufas / "RUFAS" / "model.py"
    target_file.parent.mkdir(parents=True)
    target_file.touch()

    resolved = assert_within_rufas_scope(target_file, rufas_root=fake_rufas)
    assert resolved == target_file.resolve()


def test_assert_within_rufas_scope_tooling_root():
    tooling_root = get_tooling_root()
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


def test_assert_within_rufas_scope_empty_or_none():
    with pytest.raises(RuFaSBoundaryError, match="Target path cannot be empty or None"):
        assert_within_rufas_scope(None)

    with pytest.raises(RuFaSBoundaryError, match="Target path cannot be empty or None"):
        assert_within_rufas_scope("")

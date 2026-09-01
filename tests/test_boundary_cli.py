import pytest
import sys
from pathlib import Path
from unittest import mock

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.boundary import RuFaSBoundaryError as CoreBoundaryError
import tools.config as config_mod
from tools.config import (
    RuFaSBoundaryError,
    assert_within_rufas_scope,
    is_path_in_scope,
    get_allowed_roots,
)
import tools.rufas_inspector as rufas_inspector
import tools.rufas_analyzer as rufas_analyzer
import tools.rufas_runner as rufas_runner
import tools.rufas_brain as rufas_brain


@pytest.fixture
def mock_rufas_repo(tmp_path):
    rufas_dir = tmp_path / "RuFaS"
    rufas_dir.mkdir()
    (rufas_dir / "RUFAS").mkdir()
    (rufas_dir / "RUFAS" / "__init__.py").write_text("# mock", encoding="utf-8")
    (rufas_dir / "input").mkdir()
    (rufas_dir / "input" / "metadata").mkdir()
    (rufas_dir / "input" / "task_manager_metadata.json").write_text('{"files": {}}', encoding="utf-8")
    (rufas_dir / "input" / "metadata" / "example_scenario.json").write_text('{"files": {}}', encoding="utf-8")
    (rufas_dir / "output").mkdir()
    return rufas_dir


# ============================================================================
# 1. Test tools/config.py Re-exports and __all__
# ============================================================================

def test_config_reexports():
    """Verify that tools/config.py properly re-exports boundary utilities."""
    assert RuFaSBoundaryError is CoreBoundaryError
    assert callable(assert_within_rufas_scope)
    assert callable(is_path_in_scope)
    assert callable(get_allowed_roots)

    assert hasattr(config_mod, "__all__")
    expected_exports = {
        "RuFaSBoundaryError",
        "assert_within_rufas_scope",
        "is_path_in_scope",
        "get_allowed_roots",
        "RuFaSConfigError",
        "get_rufas_root",
        "validate_rufas_root",
        "load_config",
        "save_config",
        "DEFAULT_GIT_URL",
        "GLOBAL_CONFIG_DIR",
        "GLOBAL_CONFIG_FILE",
        "LOCAL_CONFIG_NAME",
    }
    for item in expected_exports:
        assert item in config_mod.__all__, f"{item} missing from tools.config.__all__"


# ============================================================================
# 2. Test validate_inspector_targets
# ============================================================================

def test_validate_inspector_targets_valid(mock_rufas_repo):
    """Scenario within RuFaS root validates successfully."""
    scenario_file = mock_rufas_repo / "input" / "metadata" / "example_scenario.json"
    validated = rufas_inspector.validate_inspector_targets(
        scenario_path=scenario_file,
        rufas_root=mock_rufas_repo,
        allow_external=False,
    )
    assert validated == scenario_file.resolve()


def test_validate_inspector_targets_relative(mock_rufas_repo):
    """Relative scenario path resolved against rufas_root validates successfully."""
    validated = rufas_inspector.validate_inspector_targets(
        scenario_path="input/metadata/example_scenario.json",
        rufas_root=mock_rufas_repo,
        allow_external=False,
    )
    assert validated == (mock_rufas_repo / "input" / "metadata" / "example_scenario.json").resolve()


def test_validate_inspector_targets_violation(mock_rufas_repo, tmp_path):
    """External scenario path raises RuFaSBoundaryError when allow_external is False."""
    outside_file = tmp_path / "outside_scenario.json"
    outside_file.write_text("{}", encoding="utf-8")

    with pytest.raises(RuFaSBoundaryError):
        rufas_inspector.validate_inspector_targets(
            scenario_path=outside_file,
            rufas_root=mock_rufas_repo,
            allow_external=False,
        )


def test_validate_inspector_targets_allow_external(mock_rufas_repo, tmp_path):
    """External scenario path passes when allow_external is True."""
    outside_file = tmp_path / "outside_scenario.json"
    outside_file.write_text("{}", encoding="utf-8")

    validated = rufas_inspector.validate_inspector_targets(
        scenario_path=outside_file,
        rufas_root=mock_rufas_repo,
        allow_external=True,
    )
    assert validated == outside_file.resolve()


# ============================================================================
# 3. Test validate_analyzer_targets
# ============================================================================

def test_validate_analyzer_targets_valid(mock_rufas_repo):
    """Output directory within RuFaS root validates successfully."""
    out_dir = mock_rufas_repo / "output"
    validated = rufas_analyzer.validate_analyzer_targets(
        output_dir=out_dir,
        rufas_root=mock_rufas_repo,
        allow_external=False,
    )
    assert validated == out_dir.resolve()


def test_validate_analyzer_targets_default(mock_rufas_repo):
    """None output_dir defaults to rufas_root / output."""
    validated = rufas_analyzer.validate_analyzer_targets(
        output_dir=None,
        rufas_root=mock_rufas_repo,
        allow_external=False,
    )
    assert validated == (mock_rufas_repo / "output").resolve()


def test_validate_analyzer_targets_violation(mock_rufas_repo, tmp_path):
    """External output directory raises RuFaSBoundaryError when allow_external is False."""
    outside_dir = tmp_path / "outside_output"
    outside_dir.mkdir()

    with pytest.raises(RuFaSBoundaryError):
        rufas_analyzer.validate_analyzer_targets(
            output_dir=outside_dir,
            rufas_root=mock_rufas_repo,
            allow_external=False,
        )


def test_validate_analyzer_targets_allow_external(mock_rufas_repo, tmp_path):
    """External output directory passes when allow_external is True."""
    outside_dir = tmp_path / "outside_output"
    outside_dir.mkdir()

    validated = rufas_analyzer.validate_analyzer_targets(
        output_dir=outside_dir,
        rufas_root=mock_rufas_repo,
        allow_external=True,
    )
    assert validated == outside_dir.resolve()


# ============================================================================
# 4. Test validate_runner_targets
# ============================================================================

def test_validate_runner_targets_valid(mock_rufas_repo):
    """Metadata path and output directory within RuFaS root validate successfully."""
    meta_path = mock_rufas_repo / "input" / "task_manager_metadata.json"
    out_dir = mock_rufas_repo / "output"

    v_meta, v_out = rufas_runner.validate_runner_targets(
        metadata_path=meta_path,
        output_dir=out_dir,
        rufas_root=mock_rufas_repo,
        allow_external=False,
    )
    assert v_meta == meta_path.resolve()
    assert v_out == out_dir.resolve()


def test_validate_runner_targets_metadata_violation(mock_rufas_repo, tmp_path):
    """External metadata path raises RuFaSBoundaryError."""
    outside_meta = tmp_path / "outside_task.json"
    outside_meta.write_text("{}", encoding="utf-8")

    with pytest.raises(RuFaSBoundaryError):
        rufas_runner.validate_runner_targets(
            metadata_path=outside_meta,
            output_dir=mock_rufas_repo / "output",
            rufas_root=mock_rufas_repo,
            allow_external=False,
        )


def test_validate_runner_targets_output_violation(mock_rufas_repo, tmp_path):
    """External output directory raises RuFaSBoundaryError."""
    outside_out = tmp_path / "outside_output"
    outside_out.mkdir()

    with pytest.raises(RuFaSBoundaryError):
        rufas_runner.validate_runner_targets(
            metadata_path=mock_rufas_repo / "input" / "task_manager_metadata.json",
            output_dir=outside_out,
            rufas_root=mock_rufas_repo,
            allow_external=False,
        )


def test_validate_runner_targets_allow_external(mock_rufas_repo, tmp_path):
    """External paths pass when allow_external is True."""
    outside_meta = tmp_path / "outside_task.json"
    outside_meta.write_text("{}", encoding="utf-8")
    outside_out = tmp_path / "outside_output"
    outside_out.mkdir()

    v_meta, v_out = rufas_runner.validate_runner_targets(
        metadata_path=outside_meta,
        output_dir=outside_out,
        rufas_root=mock_rufas_repo,
        allow_external=True,
    )
    assert v_meta == outside_meta.resolve()
    assert v_out == outside_out.resolve()


# ============================================================================
# 5. CLI Tests: rufas-inspect, rufas-analyze, rufas-run, rufas-brain
# ============================================================================

def test_cli_inspector_boundary_enforcement(mock_rufas_repo, tmp_path):
    """rufas-inspect exits 1 on external scenario unless --allow-external is passed."""
    outside_scenario = tmp_path / "outside_meta.json"
    outside_scenario.write_text("{}", encoding="utf-8")

    # 1. Without --allow-external -> exit 1
    with mock.patch("sys.argv", [
        "rufas-inspect",
        "--rufas-root", str(mock_rufas_repo),
        "--scenario", str(outside_scenario),
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_inspector.main()
        assert exc.value.code == 1

    # 2. With --allow-external -> proceeds past boundary validation (no boundary error raised)
    with mock.patch("sys.argv", [
        "rufas-inspect",
        "--rufas-root", str(mock_rufas_repo),
        "--scenario", str(outside_scenario),
        "--allow-external",
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_inspector.main()
        assert exc.value.code in (0, 1)


def test_cli_analyzer_boundary_enforcement(mock_rufas_repo, tmp_path):
    """rufas-analyze exits 1 on external output dir unless --allow-external is passed."""
    outside_out = tmp_path / "outside_output"
    outside_out.mkdir()
    (outside_out / "test.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    # 1. Without --allow-external -> exit 1
    with mock.patch("sys.argv", [
        "rufas-analyze",
        "--rufas-root", str(mock_rufas_repo),
        "--output-dir", str(outside_out),
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_analyzer.main()
        assert exc.value.code == 1

    # 2. With --allow-external -> completes report
    with mock.patch("sys.argv", [
        "rufas-analyze",
        "--rufas-root", str(mock_rufas_repo),
        "--output-dir", str(outside_out),
        "--allow-external",
    ]):
        rufas_analyzer.main()


def test_cli_runner_boundary_enforcement(mock_rufas_repo, tmp_path):
    """rufas-run exits 1 on external metadata/output unless --allow-external is passed."""
    outside_meta = tmp_path / "outside_task.json"
    outside_meta.write_text("{}", encoding="utf-8")

    # 1. Without --allow-external -> exit 1
    with mock.patch("sys.argv", [
        "rufas-run",
        "--rufas-root", str(mock_rufas_repo),
        "--task-metadata", str(outside_meta),
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_runner.main()
        assert exc.value.code == 1

    # 2. With --allow-external -> proceeds to simulation run
    with mock.patch("tools.rufas_runner.run_rufas_simulation", return_value=0) as mock_sim:
        with mock.patch("sys.argv", [
            "rufas-run",
            "--rufas-root", str(mock_rufas_repo),
            "--task-metadata", str(outside_meta),
            "--allow-external",
        ]):
            with pytest.raises(SystemExit) as exc:
                rufas_runner.main()
            assert exc.value.code == 0
            mock_sim.assert_called_once()


def test_cli_brain_boundary_enforcement(mock_rufas_repo, tmp_path):
    """rufas-brain commands validate custom db-path and output-dir boundaries."""
    outside_db = tmp_path / "outside_brain.kuzu"
    outside_vault = tmp_path / "outside_vault"

    # 1. rufas-brain init with external db without --allow-external -> exits 1
    with mock.patch("sys.argv", [
        "rufas-brain",
        "init",
        "--rufas-root", str(mock_rufas_repo),
        "--db-path", str(outside_db),
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_brain.main()
        assert exc.value.code == 1

    # 2. rufas-brain export-obsidian with external output-dir without --allow-external -> exits 1
    with mock.patch("sys.argv", [
        "rufas-brain",
        "export-obsidian",
        "--output-dir", str(outside_vault),
    ]):
        with pytest.raises(SystemExit) as exc:
            rufas_brain.main()
        assert exc.value.code == 1

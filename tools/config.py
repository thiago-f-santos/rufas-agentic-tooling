import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

DEFAULT_GIT_URL = "https://github.com/RuminantFarmSystems/RuFaS.git"
LOCAL_CONFIG_NAME = ".rufas.json"
GLOBAL_CONFIG_DIR = Path.home() / ".rufas"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"


class RuFaSConfigError(Exception):
    """Raised when RuFaS root path cannot be resolved or is invalid."""
    pass


def validate_rufas_root(path: Optional[Union[str, Path]]) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the target path represents a valid RuFaS repository.

    Requirements:
    - Path must not be empty/None.
    - Directory must exist.
    - Path must be a directory.
    - Directory must contain 'RUFAS' python package directory.
    - Directory must contain 'input' configuration directory.
    """
    if not path:
        return False, "Path is empty or None."
    p = Path(path).resolve()
    if not p.exists():
        return False, f"Directory does not exist: {p}"
    if not p.is_dir():
        return False, f"Path is not a directory: {p}"

    pkg_dir = p / "RUFAS"
    if not pkg_dir.exists() or not pkg_dir.is_dir():
        return False, f"Directory is missing 'RUFAS' python package directory: {p}"

    input_dir = p / "input"
    if not input_dir.exists() or not input_dir.is_dir():
        return False, f"Directory is missing 'input' configuration directory: {p}"

    return True, None


def load_config(local_first: bool = True) -> Dict[str, str]:
    """
    Loads saved configuration from local .rufas.json or global ~/.rufas/config.json.
    """
    check_order = [Path.cwd() / LOCAL_CONFIG_NAME, GLOBAL_CONFIG_FILE]
    if not local_first:
        check_order = [GLOBAL_CONFIG_FILE, Path.cwd() / LOCAL_CONFIG_NAME]

    for cfg_path in check_order:
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
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
    if scope not in ("local", "global"):
        raise ValueError(f"Invalid scope: '{scope}'. Must be 'local' or 'global'.")

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
    1. Explicit CLI Argument (--rufas-root)
    2. Environment Variables (RUFAS_PATH or RUFAS_ROOT)
    3. Current Working Directory check (if running inside RuFaS)
    4. Configuration files (.rufas.json local, ~/.rufas/config.json global)
    5. Common sibling folder (../RuFaS)
    """
    # 1. CLI Arg
    if cli_arg:
        candidate = Path(cli_arg).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if require_valid and not is_valid:
            raise RuFaSConfigError(f"Specified --rufas-root is invalid: {err}")
        return candidate

    # 2. Environment Variables
    env_var_name = None
    env_path = None
    if "RUFAS_PATH" in os.environ and os.environ["RUFAS_PATH"]:
        env_var_name = "RUFAS_PATH"
        env_path = os.environ["RUFAS_PATH"]
    elif "RUFAS_ROOT" in os.environ and os.environ["RUFAS_ROOT"]:
        env_var_name = "RUFAS_ROOT"
        env_path = os.environ["RUFAS_ROOT"]

    if env_path:
        candidate = Path(env_path).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if require_valid and not is_valid:
            raise RuFaSConfigError(f"{env_var_name} environment variable points to invalid directory: {err}")
        return candidate

    # 3. Check CWD (if run inside RuFaS repository directly)
    cwd_valid, _ = validate_rufas_root(Path.cwd())
    if cwd_valid:
        return Path.cwd().resolve()

    # 4. Config files (Local and Global)
    cfg = load_config(local_first=True)
    if "rufas_root" in cfg and cfg["rufas_root"]:
        candidate = Path(cfg["rufas_root"]).resolve()
        is_valid, err = validate_rufas_root(candidate)
        if is_valid or not require_valid:
            return candidate

    # 5. Sibling directory fallback
    sibling = (Path.cwd().parent / "RuFaS").resolve()
    sibling_valid, _ = validate_rufas_root(sibling)
    if sibling_valid:
        return sibling

    for parent in Path.cwd().parents:
        candidate_sibling = (parent.parent / "RuFaS").resolve()
        is_valid, _ = validate_rufas_root(candidate_sibling)
        if is_valid:
            return candidate_sibling

    if require_valid:
        raise RuFaSConfigError(
            "❌ RuFaS project path is not configured or found.\n\n"
            "To configure:\n"
            "  1. Run interactive setup: rufas-setup\n"
            "  2. Or set existing path: rufas-setup --path /path/to/RuFaS\n"
            "  3. Or clone upstream:   rufas-setup --clone\n"
            "  4. Or set env variable: export RUFAS_PATH=/path/to/RuFaS\n"
        )

    return Path.cwd().resolve()

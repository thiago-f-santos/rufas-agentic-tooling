"""
RuFaS Boundary Containment Module
Enforces workspace isolation and prevents out-of-bounds file access by AI agents and CLI tools.
"""

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
    1. rufas-agentic-tooling root
    2. Resolved rufas_root (if provided or discoverable)
    """
    roots: List[Path] = [get_tooling_root().resolve()]

    if rufas_root is not None and str(rufas_root).strip():
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
    target_path: Optional[Union[str, Path]],
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
    target_path: Optional[Union[str, Path]],
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

"""Explicit external integration harness, never a private-path dependency."""
import os
from pathlib import Path
import sys
import pytest


_CONFIGURED_ROOT = os.environ.get("HERMES_PRIVACY_PLUGIN_ROOT", "")

def plugin_root():
    value = os.environ.get("HERMES_PRIVACY_PLUGIN_ROOT") or _CONFIGURED_ROOT
    if not value:
        pytest.skip("external plugin integration: set HERMES_PRIVACY_PLUGIN_ROOT to the plugins checkout")
    root = Path(value).expanduser().resolve()
    if not (root / "pii_mask_abelion" / "guard.py").is_file():
        pytest.fail("HERMES_PRIVACY_PLUGIN_ROOT must contain pii_mask_abelion/guard.py")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def guard_class():
    plugin_root()
    from pii_mask_abelion.guard import Guard
    return Guard

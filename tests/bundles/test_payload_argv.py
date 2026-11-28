"""scripts/bundles/payload.py: revision/path arguments are validated before they reach git argv."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "bundles"))

import payload


def test_plain_archive_paths_pass():
    payload._checked_archive_path("apps/desktop")
    payload._checked_archive_path("hermes_cli")
    payload._checked_archive_path("a/b/c-d_e.f")


def test_escaping_paths_are_refused():
    for bad_path in ("", "/etc/passwd", "../x", "a/../../b", "a//b", "./a"):
        with pytest.raises(ValueError):
            payload._checked_archive_path(bad_path)


def test_an_option_spelled_revision_never_reaches_git_as_an_option(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    # "-e" as the ref must be a (missing) revision after --end-of-options, not a second -e flag:
    # the probe answers False instead of erroring or consuming the flag.
    assert payload._revision_has_path(tmp_path, "-e", "apps") is False


def test_revision_has_path_validates_before_probing(tmp_path):
    with pytest.raises(ValueError):
        payload._revision_has_path(tmp_path, "9dbaa23", "../outside")

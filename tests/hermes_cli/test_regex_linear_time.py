"""Regexes that once cost quadratic time on one long run of characters stay linear and keep their meaning.

Each case feeds the module's own compiled pattern a hostile 40,000-character input (the old patterns
needed several seconds on these; the current ones need about a millisecond) and checks a few
ordinary inputs for the same answer as before.
"""
from __future__ import annotations

import time

import pytest

from agent.gemini_urls import _API_VERSION_SEGMENT
from gateway.response_filters import _strip_bracket_padding
from hermes_cli.doctor_platform import _REDIRECTION
from hermes_cli.gateway_migrate_backends_host import _ENV_FILE_ENTRY
from hermes_cli.gateway_migrate_backends_plan import _URL_USERINFO
from hermes_cli.gateway_migrate_backends_windows import _TASK_HEADER
from hermes_cli.plugins_settings.cli import humanize_key

N = 40_000
BUDGET_S = 1.0


def _fast(fn) -> None:
    start = time.perf_counter()
    fn()
    assert time.perf_counter() - start < BUDGET_S


def test_api_version_segment_long_digit_run() -> None:
    _fast(lambda: _API_VERSION_SEGMENT.match("v" + "1" * N + "!"))
    for ok in ("v1", "v1beta", "v1beta1", "V2ALPHA3", "v10"):
        assert _API_VERSION_SEGMENT.match(ok)
    for bad in ("v", "v1x", "vbeta", "v1beta1x", "beta1", "v1beta1beta"):
        assert not _API_VERSION_SEGMENT.match(bad)


def test_redirection_long_run_then_newline() -> None:
    _fast(lambda: _REDIRECTION.fullmatch("<" * N + "\n"))
    assert _REDIRECTION.fullmatch("2>/dev/null").group(1) == "/dev/null"
    assert _REDIRECTION.fullmatch(">>file").group(1) == "file"
    assert _REDIRECTION.fullmatch("<").group(1) == ""
    assert _REDIRECTION.fullmatch("abc") is None


def test_bracket_padding_long_whitespace_run() -> None:
    _fast(lambda: _strip_bracket_padding(" " * N))
    assert _strip_bracket_padding("[ SILENT ]") == "[SILENT]"
    assert _strip_bracket_padding("[SILENT ] note") == "[SILENT] note"
    assert _strip_bracket_padding("a   b") == "a   b"


def test_env_file_entry_long_word() -> None:
    _fast(lambda: _ENV_FILE_ENTRY.findall("a" * N))
    assert _ENV_FILE_ENTRY.findall("/etc/a.env (ignore_errors=no) /b.env (ignore_errors=yes)") == [
        ("/etc/a.env", "no"), ("/b.env", "yes")]


def test_url_userinfo_long_word() -> None:
    _fast(lambda: _URL_USERINFO.sub("", "a://" + "b" * N))
    assert _URL_USERINFO.sub(r"\1<redacted>@", "https://user:pw@host/x") == "https://<redacted>@host/x"
    assert _URL_USERINFO.sub(r"\1<redacted>@", "no userinfo https://host/x") == "no userinfo https://host/x"


def test_task_header_long_blank_run() -> None:
    _fast(lambda: _TASK_HEADER.search("<!--\\" + " " * N))
    parts = _TASK_HEADER.split("a<!--  \\Folder\\Task \t-->b")
    assert parts == ["a", "\\Folder\\Task", "b"]
    assert _TASK_HEADER.split("<!-- not a header -->") == ["<!-- not a header -->"]


def test_humanize_key_long_capital_run() -> None:
    _fast(lambda: humanize_key("A" * N))
    assert humanize_key("webhookURL") == "Webhook URL"
    assert humanize_key("maps_api_key") == "Maps API key"
    assert humanize_key("HTTPServer") == "HTTP server"

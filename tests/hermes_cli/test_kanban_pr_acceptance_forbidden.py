"""Tests for #147110: GraphQL FORBIDDEN on branchProtectionRule must not abort
the PR-acceptance collection when the data payload is otherwise intact.

GitHub App installation tokens lacking Administration:read receive:
  {"data": {...pr data...}, "errors": [{"type": "FORBIDDEN", "path":
  [..., "baseRef", "branchProtectionRule"]}]}
The gate falls back to REST rulesets for required checks, so this error is
tolerable — unlike any other GraphQL error.
"""
import json
import os
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli.kanban_db_connect import connect
from hermes_cli.kanban_pr_acceptance import (
    _api,
    _protection_forbidden_payload,
    collect_acceptance,
)


@contextmanager
def _gh_shim(tmp_path, monkeypatch, handler_cls, *, exit_nonzero=False):
    """Install a fake ``gh`` binary that serves HTTP from ``handler_cls``.

    ``exit_nonzero`` — when True, the shim exits with code 1 (mimicking
    ``gh``'s real behaviour when a GraphQL response carries an errors array).
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    shim = tmp_path / "bin"
    shim.mkdir()
    gh = shim / "gh"
    exit_code = 1 if exit_nonzero else 0
    gh.write_text(
        f"#!{sys.executable}\n"
        f"import sys,urllib.request\n"
        f"path=sys.argv[2]\n"
        f"u='http://127.0.0.1:{server.server_port}/'+path\n"
        f"data=urllib.request.urlopen(u).read()\n"
        f"sys.stdout.buffer.write(data)\n"
        # gh exits non-zero only when a GraphQL response carries an errors
        # array; REST endpoints exit 0 normally.
        f"sys.exit({exit_code} if path=='graphql' else 0)\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", str(shim) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    kb.init_db()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _forbidden_graphql():
    """The exact FORBIDDEN+data payload from issue #147110."""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "headRefOid": "a" * 40,
                    "baseRefName": "main",
                    "state": "OPEN",
                    "baseRef": None,
                }
            }
        },
        "errors": [
            {
                "type": "FORBIDDEN",
                "path": ["repository", "pullRequest", "baseRef", "branchProtectionRule"],
            }
        ],
    }


class _ForbiddenHandler(BaseHTTPRequestHandler):
    """Serves the FORBIDDEN payload on /graphql, rulesets + checks on REST."""

    def do_GET(self):
        sha = "a" * 40
        if self.path == "/graphql":
            value = _forbidden_graphql()
        elif "/rules/branches/" in self.path:
            # --paginate --slurp wraps pages in an outer list; one page
            # containing one rulesets rule.
            value = [[{
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [
                    {"context": "required", "integration_id": 1}]},
                "id": "rule-1",
            }]]
        elif "/check-runs" in self.path:
            value = [{
                "total_count": 1,
                "check_runs": [{
                    "id": 42, "name": "required", "head_sha": sha,
                    "app": {"id": 1}, "status": "completed", "conclusion": "success",
                    "html_url": "https://github.com/acme/repo/actions/runs/42",
                }],
            }]
        elif "/statuses" in self.path:
            value = [[]]
        elif "/pulls/" in self.path:
            value = {"head": {"sha": sha}, "base": {"ref": "main"}, "state": "open"}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def log_message(self, *args):
        pass


class _MixedErrorHandler(BaseHTTPRequestHandler):
    """Serves FORBIDDEN + INTERNAL_ERROR → must still raise."""

    def do_GET(self):
        if self.path == "/graphql":
            value = {
                "data": {"repository": {"pullRequest": {
                    "headRefOid": "a" * 40, "baseRefName": "main", "state": "OPEN",
                    "baseRef": None}}},
                "errors": [
                    {"type": "FORBIDDEN",
                     "path": ["repository", "pullRequest", "baseRef", "branchProtectionRule"]},
                    {"type": "INTERNAL_ERROR", "message": "boom"},
                ],
            }
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def log_message(self, *args):
        pass


class TestProtectionForbiddenPayload:
    """Unit tests for _protection_forbidden_payload predicate."""

    def test_true_for_pure_branchprotection_forbidden(self):
        stdout = json.dumps(_forbidden_graphql())
        partial = _protection_forbidden_payload(stdout)
        assert partial is not None
        assert partial["data"]["repository"]["pullRequest"]["headRefOid"] == "a" * 40

    def test_false_when_no_pullrequest_data(self):
        stdout = json.dumps({
            "data": {"repository": {"pullRequest": None}},
            "errors": [{"type": "FORBIDDEN",
                        "path": ["repository", "pullRequest", "baseRef", "branchProtectionRule"]}],
        })
        assert _protection_forbidden_payload(stdout) is None

    def test_false_when_not_forbidden_type(self):
        stdout = json.dumps({
            "data": {"repository": {"pullRequest": {"headRefOid": "abc"}}},
            "errors": [{"type": "NOT_FOUND",
                        "path": ["repository", "pullRequest", "baseRef", "branchProtectionRule"]}],
        })
        assert _protection_forbidden_payload(stdout) is None

    def test_false_when_path_not_branchprotectionrule(self):
        stdout = json.dumps({
            "data": {"repository": {"pullRequest": {"headRefOid": "abc"}}},
            "errors": [{"type": "FORBIDDEN",
                        "path": ["repository", "pullRequest", "somethingElse"]}],
        })
        assert _protection_forbidden_payload(stdout) is None

    def test_false_when_empty_errors(self):
        assert _protection_forbidden_payload(json.dumps({"data": {}, "errors": []})) is None

    def test_false_when_no_errors_key(self):
        assert _protection_forbidden_payload(json.dumps({"data": {}})) is None

    def test_false_mixed_errors(self):
        stdout = json.dumps({
            "data": {"repository": {"pullRequest": {"headRefOid": "abc"}}},
            "errors": [
                {"type": "FORBIDDEN",
                 "path": ["repository", "pullRequest", "baseRef", "branchProtectionRule"]},
                {"type": "INTERNAL_ERROR", "message": "boom"},
            ],
        })
        assert _protection_forbidden_payload(stdout) is None

    def test_false_when_non_json_stdout(self):
        assert _protection_forbidden_payload("not json{{{") is None

    def test_false_when_empty_stdout(self):
        assert _protection_forbidden_payload("") is None
        assert _protection_forbidden_payload(None) is None


class TestApiToleratesProtectionForbidden:
    """_api should not raise on tolerated FORBIDDEN, but should raise on others."""

    def test_tolerate_strips_errors(self, tmp_path, monkeypatch):
        """SUCCESS path: gh exits 0 but response has errors array.

        This mirrors real gh behaviour when the HTTP response is 200 with
        a GraphQL errors array — the shim exits 0, so _api's success-path
        handler must extract the partial payload.
        """
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                value = {
                    "data": {"repository": {"pullRequest": {
                        "headRefOid": "a" * 40}}},
                    "errors": [{"type": "FORBIDDEN",
                                "path": ["repository", "pullRequest", "baseRef",
                                         "branchProtectionRule"]}],
                }
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())
            def log_message(self, *args):
                pass

        with _gh_shim(tmp_path, monkeypatch, Handler, exit_nonzero=False):
            result = _api("graphql", query="test", profile_home=None,
                          tolerate_protection_forbidden=True)
            assert "data" in result
            assert result["data"]["repository"]["pullRequest"]["headRefOid"] == "a" * 40

    def test_tolerate_calledprocesserror_path(self, tmp_path, monkeypatch):
        """ERROR path: gh exits non-zero (real behaviour with GraphQL errors).

        The shim exits 1; _api's CalledProcessError handler must still
        extract the partial payload from exc.stdout.
        """
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                value = {
                    "data": {"repository": {"pullRequest": {
                        "headRefOid": "a" * 40}}},
                    "errors": [{"type": "FORBIDDEN",
                                "path": ["repository", "pullRequest", "baseRef",
                                         "branchProtectionRule"]}],
                }
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())
            def log_message(self, *args):
                pass

        with _gh_shim(tmp_path, monkeypatch, Handler, exit_nonzero=True):
            result = _api("graphql", query="test", profile_home=None,
                          tolerate_protection_forbidden=True)
            assert "data" in result
            assert result["data"]["repository"]["pullRequest"]["headRefOid"] == "a" * 40

    def test_tolerate_false_still_raises(self, tmp_path, monkeypatch):
        """When tolerate=False, the success-path errors check still raises."""
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                value = {
                    "data": {"repository": {"pullRequest": {
                        "headRefOid": "a" * 40}}},
                    "errors": [{"type": "FORBIDDEN",
                                "path": ["repository", "pullRequest", "baseRef",
                                         "branchProtectionRule"]}],
                }
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())
            def log_message(self, *args):
                pass

        with _gh_shim(tmp_path, monkeypatch, Handler):
            with pytest.raises(ValueError, match="incomplete GraphQL"):
                _api("graphql", query="test", profile_home=None,
                     tolerate_protection_forbidden=False)

    def test_mixed_errors_still_raise(self, tmp_path, monkeypatch):
        """FORBIDDEN + INTERNAL_ERROR → tolerate must NOT swallow it."""
        with _gh_shim(tmp_path, monkeypatch, _MixedErrorHandler):
            with pytest.raises(ValueError, match="incomplete GraphQL"):
                _api("graphql", query="test", profile_home=None,
                     tolerate_protection_forbidden=True)

    def test_mixed_errors_calledprocesserror_path(self, tmp_path, monkeypatch):
        """Same as above, but via the non-zero-exit (CalledProcessError) path.

        Mixed errors (FORBIDDEN + INTERNAL_ERROR) are not tolerable, so
        _protection_forbidden_payload returns None and _api re-raises
        CalledProcessError (gh exit code is neither HTTP-denied nor exit 4).
        """
        import subprocess
        with _gh_shim(tmp_path, monkeypatch, _MixedErrorHandler, exit_nonzero=True):
            with pytest.raises(subprocess.CalledProcessError):
                _api("graphql", query="test", profile_home=None,
                     tolerate_protection_forbidden=True)


class TestCollectAcceptanceToleratesForbidden:
    """End-to-end: collect_acceptance survives the FORBIDDEN payload (#147110)."""

    @pytest.mark.platforms("linux")
    def test_pr_acceptance_survives_forbidden_protection(self, tmp_path, monkeypatch):
        with _gh_shim(tmp_path, monkeypatch, _ForbiddenHandler, exit_nonzero=True):
            with connect() as conn:
                tid = kb.create_task(
                    conn, title="forged",
                    completion_contract="https://github.com/acme/repo/pull/7")
                ok = kb.complete_task(
                    conn, tid, result="done",
                    metadata={"published_pr": "https://github.com/acme/repo/pull/7"})
                receipt = json.loads(conn.execute(
                    "SELECT payload FROM task_events WHERE task_id=? AND kind='pr_acceptance'",
                    (tid,)).fetchone()[0])
                sha = "a" * 40
                assert receipt["head_sha"] == sha
                assert receipt["classification"] == "success"
                assert receipt["checks"][0]["name"] == "required"
                assert receipt["checks"][0]["classification"] == "success"
                assert ok is True
                assert kb.get_task(conn, tid).status == "done"

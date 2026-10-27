"""Turn leases for plugin-initiated mid-answer redirects (``agent/turn_redirect_lease.py``,
``ctx.request_turn_redirect``).

Mirrors ``test_side_question_lease.py``: plugins load through real discovery from a temp
``HERMES_HOME``; the parent agent is a stand-in recording ``redirect()`` calls. Covers issuance
(consented plugin, held stream, attended turn), redemption refusals (unknown/other-profile/
moved-on/not-held/no-live-request/bad text/bound), labeling, the stream-payload token, the
``origin`` plumbing in ``InterruptControlMixin.redirect`` and ``begin_iteration``'s summary
wording.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

import hermes_yaml as yaml
import pytest

import hermes_cli.plugins as plugins_mod
from agent import turn_redirect_lease
from agent.turn_redirect_lease import (
    MAX_REDIRECT_CHARS, ensure_turn_redirect_token, redeem_turn_redirect,
)
from hermes_cli.plugins import PluginContext

CAP = "turn.redirect"


def _install_plugin(name: str, *, declares: bool) -> None:
    plugin_dir = Path(os.environ["HERMES_HOME"]) / "plugins" / name
    plugin_dir.mkdir(parents=True)
    manifest = {"name": name, **({"capabilities": [CAP]} if declares else {})}
    (plugin_dir / "plugin.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (plugin_dir / "__init__.py").write_text("def register(ctx):\n    pass\n", encoding="utf-8")


def _load(enabled: list[str], granted: list[str]) -> plugins_mod.PluginManager:
    entries = {name: {"granted_capabilities": [CAP]} for name in granted}
    (Path(os.environ["HERMES_HOME"]) / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": enabled, "entries": entries}}), encoding="utf-8")
    plugins_mod._plugin_manager = plugins_mod.PluginManager()
    plugins_mod.discover_plugins(force=True)
    return plugins_mod.get_plugin_manager()


def _ctx(manager, name: str) -> PluginContext:
    return PluginContext(manager._plugins[name].manifest, manager)


class _Agent(SimpleNamespace):
    """A stand-in parent; leases hold their parent weakly, which a bare SimpleNamespace refuses.

    ``redirect`` records ``(text, origin)`` and returns ``redirect_result``; ``statuses``
    collects the diagnostic the user sees on a restart."""

    def redirect(self, text, *, origin="user"):
        self.redirect_calls.append((text, origin))
        return self.redirect_result

    def _emit_diagnostic_status(self, message):
        self.statuses.append(message)


def _agent(turn_id="turn-1", *, held=True, live=True, redirect_result=True, **overrides):
    model_active = threading.Event()
    if live:
        model_active.set()
    return _Agent(**{
        "_persist_disabled": False, "_delegate_depth": 0, "platform": "cli",
        "session_id": "sess", "_current_turn_id": turn_id,
        "_hold_stream": held, "_model_request_active": model_active,
        "redirect_calls": [], "statuses": [], "redirect_result": redirect_result,
        **overrides,
    })


@pytest.fixture(autouse=True)
def _clean_leases():
    yield
    turn_redirect_lease._leases.clear()


@pytest.fixture
def consented():
    """``watcher`` declares and is granted the capability; ``bystander`` does neither."""
    _install_plugin("watcher", declares=True)
    _install_plugin("bystander", declares=False)
    return _load(["watcher", "bystander"], granted=["watcher"])


# ── issuance ─────────────────────────────────────────────────────────────────────────────


def test_token_only_for_a_declared_and_granted_plugin():
    _install_plugin("declares-only", declares=True)
    _install_plugin("granted-only", declares=False)
    _load(["declares-only", "granted-only"], granted=["granted-only"])
    assert ensure_turn_redirect_token(_agent(), "turn-1") is None

    _load(["declares-only", "granted-only"], granted=["declares-only", "granted-only"])
    assert isinstance(ensure_turn_redirect_token(_agent(), "turn-1"), str)


def test_no_token_when_the_consented_plugin_is_disabled():
    _install_plugin("watcher", declares=True)
    _load([], granted=["watcher"])
    assert ensure_turn_redirect_token(_agent(), "turn-1") is None


def test_no_token_without_a_held_stream(consented):
    """An unheld turn may already have shown the partial answer: aborting then replaces text
    the user read, so the lease is never minted."""
    assert ensure_turn_redirect_token(_agent(held=False), "turn-1") is None


def test_no_token_for_unattended_turns(consented):
    assert ensure_turn_redirect_token(_agent(_persist_disabled=True), "turn-1") is None
    assert ensure_turn_redirect_token(_agent(platform="cron"), "turn-1") is None
    assert ensure_turn_redirect_token(_agent(_delegate_depth=1), "turn-1") is None
    assert ensure_turn_redirect_token(_agent(), "") is None


def test_token_cached_per_turn_and_reissued_on_the_next(consented):
    agent = _agent()
    first = ensure_turn_redirect_token(agent, "turn-1")
    assert ensure_turn_redirect_token(agent, "turn-1") is first  # one attribute read, no re-mint
    second = ensure_turn_redirect_token(agent, "turn-2")
    assert second is not None and second != first
    # The new turn's mint retired the old lease.
    assert redeem_turn_redirect(first, "stale try", plugin_id="watcher") is False
    assert agent.redirect_calls == []


# ── redemption ───────────────────────────────────────────────────────────────────────────


def test_happy_path_redirects_with_labeled_text_reason_and_origin(consented):
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert redeem_turn_redirect(
        token, "GPT-5.2 released 2026-10-01 (openai.com, checked 2026-10-27)",
        plugin_id="watcher", reason="stale model recommendation") is True
    [(text, origin)] = agent.redirect_calls
    assert origin == "plugin:watcher"
    assert 'Plugin "watcher" stopped this answer' in text
    assert "stale model recommendation" in text
    assert "GPT-5.2 released" in text
    # Not silent: the restart is announced on the lifecycle rail.
    assert len(agent.statuses) == 1 and "watcher" in agent.statuses[0]


def test_one_accepted_redirect_per_turn(consented):
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert redeem_turn_redirect(token, "first", plugin_id="watcher") is True
    assert redeem_turn_redirect(token, "second", plugin_id="watcher") is False
    assert [c[0] for c in agent.redirect_calls] != []


def test_unknown_and_other_profile_tokens_refused(consented):
    assert redeem_turn_redirect("nope", "x", plugin_id="watcher") is False
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert redeem_turn_redirect(token, "x", plugin_id="watcher", home="/tmp/other-profile") is False
    # A cross-profile refusal leaves the lease for its owner.
    assert redeem_turn_redirect(token, "x", plugin_id="watcher") is True


def test_refusals_do_not_spend_the_bound(consented):
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert redeem_turn_redirect(token, "", plugin_id="watcher") is False            # bad_text
    assert redeem_turn_redirect(token, "x" * (MAX_REDIRECT_CHARS + 1), plugin_id="watcher") is False
    agent._model_request_active.clear()
    assert redeem_turn_redirect(token, "ok", plugin_id="watcher") is False          # no_live_request
    agent._model_request_active.set()
    agent._hold_stream = False
    assert redeem_turn_redirect(token, "ok", plugin_id="watcher") is False          # stream_not_held
    agent._hold_stream = True
    assert redeem_turn_redirect(token, "ok", plugin_id="watcher") is True           # bound intact
    assert [len(c) for c in agent.redirect_calls] == [2]


def test_turn_moved_on_and_provider_race_refused(consented):
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    agent._current_turn_id = "turn-2"
    assert redeem_turn_redirect(token, "late", plugin_id="watcher") is False
    assert agent.redirect_calls == []

    agent = _agent(redirect_result=False)  # redirect() lost the race to the provider's final
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert redeem_turn_redirect(token, "late", plugin_id="watcher") is False
    assert agent.statuses == []  # nothing announced for a restart that did not happen


def test_an_expired_lease_is_refused(consented):
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    [lease] = turn_redirect_lease._leases.values()
    lease.expires_at = 0.0
    assert redeem_turn_redirect(token, "too late", plugin_id="watcher") is False
    assert agent.redirect_calls == []


# ── ctx surface ──────────────────────────────────────────────────────────────────────────


def test_ctx_requires_the_capability(consented):
    manager = consented
    agent = _agent()
    token = ensure_turn_redirect_token(agent, "turn-1")
    assert _ctx(manager, "bystander").request_turn_redirect(token, "ctx") is False
    assert agent.redirect_calls == []
    assert _ctx(manager, "watcher").request_turn_redirect(token, "ctx", reason="r") is True
    [(text, origin)] = agent.redirect_calls
    assert origin == "plugin:watcher" and "ctx" in text


# ── stream payload ───────────────────────────────────────────────────────────────────────


def test_stream_payload_carries_the_token_only_when_redeemable(consented):
    from agent.stream_delivery import StreamDeliveryMixin

    base = {"_api_call_count": 1, "session_id": "sess", "model": "m", "provider": "p",
            "platform": "cli", "_persist_disabled": False, "_delegate_depth": 0}
    held = _agent(**base)
    payload = StreamDeliveryMixin._stream_hook_base_payload(held)
    assert payload["turn_redirect_token"] == ensure_turn_redirect_token(held, "turn-1")

    unheld = _agent(held=False, **base)
    assert "turn_redirect_token" not in StreamDeliveryMixin._stream_hook_base_payload(unheld)


# ── origin plumbing (interrupt_control + begin_iteration) ────────────────────────────────


def _control_agent():
    from agent.interrupt_control import InterruptControlMixin

    agent = InterruptControlMixin()
    agent._pending_redirect_lock = threading.Lock()
    agent._pending_steer_lock = threading.Lock()
    agent._pending_redirect = None
    agent._pending_redirect_origin = None
    agent._interrupt_requested = False
    agent._model_request_active = threading.Event()
    agent._model_request_active.set()
    agent._execution_thread_id = None
    agent._executing_tools = False
    agent._turn_user_intervened = False
    return agent


def test_redirect_origin_defaults_to_user_and_marks_intervention():
    agent = _control_agent()
    assert agent.redirect("user words") is True
    assert agent._pending_redirect == "user words"
    assert agent._pending_redirect_origin == "user"
    assert agent._turn_user_intervened is True


def test_plugin_redirect_keeps_its_origin_and_is_not_a_user_intervention():
    agent = _control_agent()
    assert agent.redirect("plugin words", origin="plugin:watcher") is True
    assert agent._pending_redirect == "plugin words"
    assert agent._pending_redirect_origin == "plugin:watcher"
    assert agent._turn_user_intervened is False
    assert agent._drain_pending_redirect() == "plugin words"
    assert agent._drain_pending_redirect_origin() == "plugin:watcher"
    assert agent._drain_pending_redirect_origin() == "user"  # slot cleared


def test_mixed_batch_credits_the_user_only_when_a_chunk_is_theirs():
    agent = _control_agent()
    agent.redirect("plugin first", origin="plugin:watcher")
    agent.redirect("then the user")
    assert agent._pending_redirect_origin == "user"
    assert "[Additional user correction]" in agent._pending_redirect

    agent = _control_agent()
    agent.redirect("user first")
    agent.redirect("then a plugin", origin="plugin:watcher")
    assert agent._pending_redirect_origin == "user"
    assert "[Additional plugin correction]" in agent._pending_redirect


def test_clear_interrupt_drops_the_origin_with_its_redirect():
    agent = _control_agent()
    agent.redirect("plugin words", origin="plugin:watcher")
    agent.clear_interrupt()
    assert agent._pending_redirect is None
    assert agent._pending_redirect_origin is None
    agent.redirect("plugin again", origin="plugin:watcher")
    agent.clear_interrupt(preserve_redirect=True)
    assert agent._pending_redirect == "plugin again"
    assert agent._pending_redirect_origin == "plugin:watcher"


def test_begin_iteration_summarizes_a_plugin_correction_as_one(monkeypatch):
    from agent.turn_iteration_prep import begin_iteration

    monkeypatch.setattr("agent.conversation_loop._apply_active_turn_redirect", lambda *a, **k: None)
    monkeypatch.setattr("agent.conversation_loop._review_input_budget_exhausted", lambda a: False)
    agent = SimpleNamespace(
        _interrupt_requested=False, quiet_mode=True,
        _drain_pending_redirect=lambda: '[Plugin "watcher" ...]\n\nevidence',
        _drain_pending_redirect_origin=lambda: "plugin:watcher",
        _checkpoint_mgr=SimpleNamespace(new_turn=lambda: None),
        _persist_session=lambda *a, **k: None, _api_call_count=0, _budget_grace_call=False,
        session_input_tokens=0, _touch_activity=lambda *a, **k: None,
        iteration_budget=SimpleNamespace(consume=lambda: True),
    )
    verdict = begin_iteration(
        agent, messages=[], conversation_history=[], original_user_message="which model?",
        api_call_count=0, interrupted=False, _turn_exit_reason="unknown")
    assert "Plugin correction during the turn:" in verdict.original_user_message
    assert "User correction during the turn:" not in verdict.original_user_message


def test_begin_iteration_without_origin_plumbing_still_says_user(monkeypatch):
    """Partial fakes and older agents without the origin drain keep the historical wording."""
    from agent.turn_iteration_prep import begin_iteration

    monkeypatch.setattr("agent.conversation_loop._apply_active_turn_redirect", lambda *a, **k: None)
    monkeypatch.setattr("agent.conversation_loop._review_input_budget_exhausted", lambda a: False)
    agent = SimpleNamespace(
        _interrupt_requested=False, quiet_mode=True,
        _drain_pending_redirect=lambda: "use the small model",
        _checkpoint_mgr=SimpleNamespace(new_turn=lambda: None),
        _persist_session=lambda *a, **k: None, _api_call_count=0, _budget_grace_call=False,
        session_input_tokens=0, _touch_activity=lambda *a, **k: None,
        iteration_budget=SimpleNamespace(consume=lambda: True),
    )
    verdict = begin_iteration(
        agent, messages=[], conversation_history=[], original_user_message="which model?",
        api_call_count=0, interrupted=False, _turn_exit_reason="unknown")
    assert "User correction during the turn:" in verdict.original_user_message

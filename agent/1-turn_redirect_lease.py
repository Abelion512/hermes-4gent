"""Turn leases for plugin-initiated mid-answer redirects (``ctx.request_turn_redirect``).

While a turn's reply is streaming, a plugin watching the observer stream (``on_stream_delta``)
may decide the in-flight answer must be redone with new context, e.g. a freshness gate that
fetched current sources concurrently and spotted a stale claim. The observer hooks are pure
consumers and cannot act on the stream, so the turn hands them an opaque ``turn_redirect_token``
in their payloads; redeeming it through ``ctx.request_turn_redirect`` aborts the in-flight
provider call and retries the turn with the plugin's text, riding the same machinery as a user
``/redirect`` (``agent/interrupt_control.py`` → ``restart_with_redirected_messages`` →
``_apply_active_turn_redirect``).

The honesty contract, enforced here rather than left to plugin documentation:

- This is an abort + one bounded, transparent retry, NOT a token-level pause/resume. Provider
  chat APIs cannot splice new context into an in-flight completion; the partial answer is
  discarded and the model is re-called with the plugin's correction appended.
- Nothing unchecked reaches the user first: a token is only issued for turns whose replies are
  held (a loaded plugin registered ``transform_llm_output`` with ``hold_stream=True``), and the
  hold is re-checked at redemption. Without a held stream the aborted prefix may already have
  been displayed, so the lease refuses.
- Not silent: the correction lands in the transcript labeled with the plugin's id and reason
  (``_apply_active_turn_redirect`` persists it as the visible correction row), and a lifecycle
  status line announces the restart on surfaces that render one.
- Bounded: one accepted redirect per turn (``MAX_REDIRECTS_PER_TURN``); the retry loop's own
  ``restart_count`` cap bounds every restart path besides. Unattended turns (forks, cron runs,
  subagents) get no token, as with ``side_question``.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
import weakref
from dataclasses import dataclass
from typing import Any, Optional

from agent.side_question_lease import is_unattended_turn

logger = logging.getLogger(__name__)

TURN_REDIRECT_CAPABILITY = "turn.redirect"
LEASE_TTL_SECONDS = 900.0  # backstop only; the live validity check is the turn identity below
MAX_REDIRECT_CHARS = 4096
MAX_REASON_CHARS = 240
MAX_REDIRECTS_PER_TURN = 1


@dataclass
class _Lease:
    parent_ref: Any  # weakref.ref(agent)
    turn_id: str
    expires_at: float
    home_key: str  # hermes_home_key() of the profile the turn runs under
    redeemed: int = 0


_leases: dict[str, _Lease] = {}
_lock = threading.Lock()


def _consented_plugin_loaded() -> bool:
    """True when a loaded, enabled plugin declares ``turn.redirect`` AND it is granted."""
    from hermes_cli.plugin_capabilities import plugin_capability_granted
    from hermes_cli.plugins import get_plugin_manager

    return any(
        loaded.enabled
        and TURN_REDIRECT_CAPABILITY in loaded.manifest.capabilities
        and plugin_capability_granted(key, TURN_REDIRECT_CAPABILITY)
        for key, loaded in list(get_plugin_manager()._plugins.items())
    )


def _purge_locked(now: float, agent: Any = None) -> None:
    """Drop expired leases, leases whose parent is gone, and (on a new turn) ``agent``'s older ones."""
    for stale in [t for t, lease in _leases.items()
                  if lease.expires_at < now or (parent := lease.parent_ref()) is None or parent is agent]:
        del _leases[stale]


def ensure_turn_redirect_token(agent: Any, turn_id: str) -> Optional[str]:
    """The turn's redirect token, minted lazily on the first stream payload that asks; None when
    this turn may not be redirected by a plugin. Cached per turn on the agent: stream payloads
    are built per delta, so every call after the first is one attribute read."""
    cached = getattr(agent, "_turn_redirect_lease_cache", None)
    if cached is not None and cached[0] == turn_id:
        return cached[1]
    token = _issue(agent, turn_id)
    agent._turn_redirect_lease_cache = (turn_id, token)
    return token


def _issue(agent: Any, turn_id: str) -> Optional[str]:
    from hermes_constants import hermes_home_key

    if not turn_id or is_unattended_turn(agent):
        return None
    if getattr(agent, "_hold_stream", False) is not True:
        # Without a held reply the aborted prefix may already be on the user's screen: a
        # redirect then replaces text they read, so the lease is refused outright.
        return None
    if not _consented_plugin_loaded():
        return None
    token = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _lock:
        # One live lease per session agent: a new turn drops this agent's older lease.
        _purge_locked(now, agent)
        _leases[token] = _Lease(weakref.ref(agent), turn_id, now + LEASE_TTL_SECONDS, hermes_home_key())
    return token


def _redeemable(lease: Optional[_Lease], text: Any) -> Optional[str]:
    """Why the lease cannot be redeemed with ``text``, or None."""
    if lease is None:
        return "unknown_token"
    if time.monotonic() > lease.expires_at:
        return "expired"
    parent = lease.parent_ref()
    if parent is None:
        return "parent_gone"
    if getattr(parent, "_current_turn_id", None) != lease.turn_id:
        return "turn_moved_on"
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_REDIRECT_CHARS:
        return "bad_text"
    if getattr(parent, "_hold_stream", False) is not True:
        # Re-checked at redemption, not only at issue: a mid-turn plugin reload could have
        # dropped the holding transform, and an unheld prefix may already be displayed.
        return "stream_not_held"
    model_active = getattr(parent, "_model_request_active", None)
    if model_active is None or not model_active.is_set():
        # Between iterations or running tools there is no answer to abort; the plugin's
        # evidence belongs in the next turn's pre_llm_call, not a steer.
        return "no_live_request"
    return None


def _labeled_correction(plugin_id: str, reason: Any, text: str) -> str:
    """The correction row's visible text: plugin origin and reason up front, so neither the
    transcript nor the model reads it as the user's own words."""
    reason_text = str(reason).strip()[:MAX_REASON_CHARS] if reason else ""
    reason_part = f" ({reason_text})" if reason_text else ""
    header = (f'[Plugin "{plugin_id}" stopped this answer before it finished{reason_part} '
              f"and restarted it with the context below]")
    return f"{header}\n\n{text.strip()}"


def redeem_turn_redirect(token: Any, text: Any, *, plugin_id: str, home: Any = None, reason: Any = None) -> bool:
    """Spend the lease behind ``token`` on one mid-answer redirect; True when the abort + retry
    was accepted.

    ``home`` is the redeeming plugin's profile home (the active one when omitted). A lease from
    another profile is refused and left for its owner. A refusal never consumes the lease's one
    bound; only an accepted redirect does."""
    from hermes_constants import hermes_home_key

    home_key = hermes_home_key(home)
    with _lock:
        lease = _leases.get(token) if isinstance(token, str) else None
        if lease is not None and lease.home_key != home_key:
            logger.info("turn_redirect plugin=%s outcome=rejected:other_profile", plugin_id)
            return False
        _purge_locked(time.monotonic())
    rejected = _redeemable(lease, text)
    if rejected is not None:
        logger.info("turn_redirect plugin=%s outcome=rejected:%s", plugin_id, rejected)
        return False
    with _lock:
        # Reserve the turn's one redirect BEFORE aborting the request: two plugins redeeming
        # concurrently must not both pass the bound (a refusal below releases the reservation).
        if lease.redeemed >= MAX_REDIRECTS_PER_TURN:
            logger.info("turn_redirect plugin=%s outcome=rejected:bound_reached", plugin_id)
            return False
        lease.redeemed += 1
    parent = lease.parent_ref()
    labeled = _labeled_correction(plugin_id, reason, text)
    accepted = bool(parent.redirect(labeled, origin=f"plugin:{plugin_id}"))
    if not accepted:
        # Lost the race against the provider's own completion: the answer the plugin wanted
        # to replace is already final, and its held transform owns the last word instead.
        with _lock:
            lease.redeemed -= 1
        logger.info("turn_redirect plugin=%s outcome=rejected:redirect_refused", plugin_id)
        return False
    logger.info("turn_redirect plugin=%s outcome=accepted", plugin_id)
    emit = getattr(parent, "_emit_diagnostic_status", None)
    if callable(emit):
        reason_text = str(reason).strip()[:MAX_REASON_CHARS] if reason else ""
        try:
            emit(f'↻ Plugin "{plugin_id}" restarted this answer with new context'
                 + (f": {reason_text}" if reason_text else ""))
        except Exception:
            # The restart already landed; a dead status sink must not unreport it.
            logger.debug("turn_redirect status emit failed", exc_info=True)
    return True

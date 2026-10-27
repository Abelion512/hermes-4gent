"""Capability-gated ``PluginContext`` surface: ``has_capability`` probing,
``side_question`` (ask the session's own agent after a turn, ``llm.side_question``) and
``request_turn_redirect`` (abort + retry the live answer mid-stream, ``turn.redirect``)."""

from __future__ import annotations

import logging
from typing import Optional

from hermes_cli.plugin_capabilities import plugin_capability_granted
from hermes_cli.plugins_loader import _plugin_home_scope

logger = logging.getLogger(__name__)


class PluginCapabilityCtxMixin:
    """Mixed into :class:`hermes_cli.plugins.PluginContext` (``manifest``, ``_manager``, ``plugin_id``)."""

    # -- capability probing (#64228) -----------------------------------------
    def has_capability(self, capability: str) -> bool:
        """True when *capability* is live for this plugin (probe, then degrade gracefully). Bundled
        plugins are trusted for ``tools.override``; otherwise granted_capabilities or the legacy
        ``allow_*`` key decides. Unknown ids / unreadable consent -> False (fail closed)."""
        if self.manifest.source == "bundled" and capability == "tools.override":
            return True
        return plugin_capability_granted(self.plugin_id, capability)

    def side_question(self, token: str, prompt: str, *, timeout: float = 15.0) -> Optional[str]:
        """Ask the session's own agent ``prompt`` about the turn that just ended; text or None.

        ``token`` is ``post_llm_call``'s ``side_question_token``: one attempt per turn, shared by
        every plugin of the session's profile, valid for 60 s and only until the next turn starts
        (cron runs and subagent turns get no token). Same model, the whole
        session (memory included) and its warm prompt cache; tools never run and nothing is
        written to the transcript. Needs the ``llm.side_question`` capability; without it this
        returns None and leaves the attempt to a consented plugin."""
        from agent.side_question_lease import SIDE_QUESTION_CAPABILITY, redeem_side_question

        if not self._side_question_granted(SIDE_QUESTION_CAPABILITY):
            if not getattr(self, "_side_question_denial_logged", False):
                self._side_question_denial_logged = True
                logger.info("Plugin %s called ctx.side_question without the %s capability; returning None",
                            self.plugin_id, SIDE_QUESTION_CAPABILITY)
            return None
        return redeem_side_question(
            token, prompt, plugin_id=self.plugin_id, home=self._manager.home_path, timeout=timeout)

    def request_turn_redirect(self, token: str, text: str, *, reason: Optional[str] = None) -> bool:
        """Abort the live answer mid-stream and retry the turn with ``text`` as the correction;
        True when the restart was accepted.

        ``token`` is the ``turn_redirect_token`` carried by this turn's ``on_stream_*`` observer
        payloads: a consented plugin watches the stream from its observer thread, prepares its
        correction (e.g. freshly fetched sources), and redeems the token from that same thread.
        This is an abort + one bounded retry, not a pause/resume: the partial answer is
        discarded and the model is called again. Tokens are only minted while a plugin holds the
        turn's replies for rewrite (``transform_llm_output`` with ``hold_stream=True``), so no
        unchecked text reached the user first; the correction lands in the transcript labeled
        with this plugin's id and ``reason``, never as the user's own words. One accepted
        redirect per turn; refusals (turn moved on, no live request, stream not held, bound
        spent) return False and leave the turn alone. Needs the ``turn.redirect`` capability;
        without it this returns False and leaves the attempt to a consented plugin."""
        from agent.turn_redirect_lease import TURN_REDIRECT_CAPABILITY, redeem_turn_redirect

        if not self._side_question_granted(TURN_REDIRECT_CAPABILITY):
            if not getattr(self, "_turn_redirect_denial_logged", False):
                self._turn_redirect_denial_logged = True
                logger.info("Plugin %s called ctx.request_turn_redirect without the %s capability; returning False",
                            self.plugin_id, TURN_REDIRECT_CAPABILITY)
            return False
        return redeem_turn_redirect(
            token, text, plugin_id=self.plugin_id, home=self._manager.home_path, reason=reason)

    def _side_question_granted(self, capability: str) -> bool:
        """Consent read from THIS manager's profile home: plugins call from their own threads,
        where the active profile may be the launch profile's."""
        try:
            from hermes_cli.config import load_config
            with _plugin_home_scope(self._manager.home_path):
                cfg = load_config() or {}
        except Exception:  # health: allow BLE001 -- fail closed: unreadable consent state never grants
            return False
        return plugin_capability_granted(self.plugin_id, capability, config=cfg)

"""Opt-in required privacy policy for the supported Chat Completions routes.

This is accident prevention in a trusted process, not OS-level containment.
A required policy is independent of optional observer/middleware failure modes.
"""
from __future__ import annotations

import copy
import contextvars
import uuid
from contextlib import contextmanager
import queue
import threading
from typing import Any

POLICY_TIMEOUT_SECONDS = 10.0

WITHHELD = 'This response was withheld by the required local privacy guard.'


class PrivacyGuardDenied(RuntimeError):
    """Fixed, non-sensitive failure, safe to surface without request contents."""


def _required_config() -> bool:
    from hermes_cli.config_effective import load_user_config_effective
    from hermes_constants import hermes_home_key
    home = hermes_home_key()
    # Preserve native last-good recovery for profiles that did not opt in.
    # A known required profile never downgrades on an unreadable/torn file.
    try:
        config = load_user_config_effective()
        value = (config.get('security') or {}).get('require_privacy_guard', False)
        if value is True or _REQUIRED_BY_HOME.get(home) is True:
            config = load_user_config_effective(fail_closed=True)
            value = (config.get('security') or {}).get('require_privacy_guard', False)
    except Exception:  # health: allow BLE001 -- deny unreadable policy without logging secret config
        raise PrivacyGuardDenied('Local privacy policy could not be read') from None
    if not isinstance(value, bool):
        raise PrivacyGuardDenied('Local privacy policy must be a boolean')
    _REQUIRED_BY_HOME[home] = value
    return value


_REQUIRED_BY_HOME: dict[str, bool] = {}


_POLICY = contextvars.ContextVar('required_privacy_policy', default=None)
_SESSION = contextvars.ContextVar('required_privacy_session', default='')


def required() -> bool:
    policy = _POLICY.get()
    return policy[0] if policy is not None else _required_config()


def _resolve_callback():
    from hermes_cli.plugins import _delivery_manager
    from agent.safe_worker_policy import safe_worker_enabled
    if safe_worker_enabled():
        raise PrivacyGuardDenied('Required privacy policy is unavailable in safe-worker mode')
    manager = _delivery_manager()
    with manager._discovery_lock:
        callbacks = tuple(manager._middleware.get('llm_privacy', ()))
    if len(callbacks) != 1:
        raise PrivacyGuardDenied('Exactly one local privacy policy must be loaded')
    from hermes_cli.config_effective import load_user_config_effective
    expected = (load_user_config_effective(fail_closed=True).get('security') or {}).get('privacy_guard_plugin')
    if not isinstance(expected, str) or not expected or manager._privacy_policy_owners.get(str(id(callbacks[0]))) != expected:
        raise PrivacyGuardDenied('Required privacy policy owner does not match configuration')
    return callbacks[0]


@contextmanager
def turn_policy(session_id=''):
    """Freeze the opt-in and callback identity through retries, aux calls and final delivery."""
    enabled = required()
    callback = None
    if enabled:
        callback = _resolve_callback()
    token = _POLICY.set((enabled, callback))
    session_token = _SESSION.set(session_id)
    try:
        yield
    finally:
        _POLICY.reset(token)
        _SESSION.reset(session_token)


def _call(phase: str, **payload: Any) -> dict:
    policy = _POLICY.get()
    callback = policy[1] if policy is not None else _resolve_callback()
    if callback is None:
        raise PrivacyGuardDenied('Required privacy policy is unavailable')
    # Different sessions may call one policy concurrently. Its own state lock handles
    # serialization. Cap abandoned workers per callback, do not reject all normal overlap.
    with _LOCK:
        count = _RUNNING.get(callback, 0)
        if count >= 8:
            raise PrivacyGuardDenied('Local privacy policy is busy')
        _RUNNING[callback] = count + 1
    result: queue.Queue = queue.Queue(maxsize=1)
    def work():
        try:
            result.put((True, callback(phase=phase, **copy.deepcopy(payload))))
        except BaseException:  # health: allow BLE001 -- policy failure must never release raw request or log its content
            result.put((False, None))
        finally:
            with _LOCK:
                if _RUNNING.get(callback, 0) <= 1:
                    _RUNNING.pop(callback, None)
                else:
                    _RUNNING[callback] -= 1
    context = contextvars.copy_context()
    threading.Thread(target=lambda: context.run(work), daemon=True, name='required-privacy-policy').start()  # health: allow HX012 -- caller Context explicitly copied above
    try:
        ok, value = result.get(timeout=POLICY_TIMEOUT_SECONDS)
    except queue.Empty:
        raise PrivacyGuardDenied('Local privacy policy timed out') from None
    if not ok or not isinstance(value, dict) or value.get('allow') is not True:
        reason = value.get('reason') if isinstance(value, dict) else None
        if reason == 'capacity':
            raise PrivacyGuardDenied('Local privacy capacity reached. Start a fresh session or reduce input locally; no request was sent')
        raise PrivacyGuardDenied('Local privacy policy denied this operation')
    return value


_LOCK = threading.Lock()
_RUNNING: dict = {}


def protect_request(request: dict, *, client: Any, session_id: str = '', api_mode: str = 'chat_completions') -> dict:
    """Last supported SDK call seam. Unsupported clients deny before network."""
    if not required():
        return request
    from openai import OpenAI, AsyncOpenAI
    if api_mode == 'chat_completions' and _native_dispatch_client(client):
        # These concrete adapters have a second check after native conversion.
        return request
    if api_mode != 'chat_completions' or not isinstance(client, (OpenAI, AsyncOpenAI)):
        raise PrivacyGuardDenied('Required privacy policy does not support this transport')
    from agent.auxiliary_hooks import _parent_turn_identity
    identity = _parent_turn_identity()
    session_id = _SESSION.get() or identity.get('session_id') or session_id or ('auxiliary-' + uuid.uuid4().hex)
    # SDK control object, never sent as model content. Keep typed timeouts out of
    # the policy's JSON-only payload; unknown objects remain the policy's decision.
    import httpx
    timeout = request.get('timeout')
    typed_timeout = isinstance(timeout, httpx.Timeout)
    payload = {k: v for k, v in request.items() if k != 'timeout'} if typed_timeout else request
    value = _call('request', request=payload, session_id=session_id)
    protected = value.get('request')
    if not isinstance(protected, dict):
        raise PrivacyGuardDenied('Local privacy policy returned an invalid request')
    if typed_timeout:
        protected = {**protected, 'timeout': timeout}
    return protected


def check_transport(api_mode: str, provider: str = '') -> None:
    if required() and (api_mode not in {'chat_completions', 'anthropic_messages'} or provider == 'moa'):
        raise PrivacyGuardDenied('Required privacy policy does not support this transport')


def transform_required_output(response_text: str, **context: Any) -> str:
    """Host-owned held transform. Missing or failed policy never releases raw text."""
    try:
        value = _call('output', response_text=response_text, **context)
        text = value.get('response_text')
        return text if isinstance(text, str) and text else WITHHELD
    except BaseException:  # health: allow BLE001 -- final output failure withholds raw model text
        return WITHHELD


def protect_tool(tool_name: str, args: dict, *, session_id: str) -> dict:
    """Last local execution seam, after optional rewrites and before real dispatch."""
    if not required():
        return args
    value = _call('tool', tool_name=tool_name, args=args, session_id=session_id)
    protected = value.get('args')
    if not isinstance(protected, dict):
        raise PrivacyGuardDenied('Local privacy policy returned invalid tool arguments')
    return protected


def guard_sync_callback(client, callback):
    return lambda request: callback(protect_request(request, client=client))


def guard_async_callback(client, callback):
    async def guarded(request):
        import asyncio
        protected = await asyncio.to_thread(protect_request, request, client=client)
        return await callback(protected)
    return guarded


def register_owner(context, callback):
    context._track_mapping_entry('privacy_policy_owner', str(id(callback)),
                                 context._manager._privacy_policy_owners, context.manifest.name)


def check_agent_transport(agent):
    check_transport(agent.api_mode, agent.provider or '')


def _native_dispatch_client(client):
    from agent.gemini_native_adapter import GeminiNativeClient, AsyncGeminiNativeClient
    from agent.auxiliary_client import AnthropicAuxiliaryClient, AsyncAnthropicAuxiliaryClient
    return isinstance(client, (GeminiNativeClient, AsyncGeminiNativeClient,
                               AnthropicAuxiliaryClient, AsyncAnthropicAuxiliaryClient))


def protect_native_request(request, *, transport, session_id=''):
    """Check the final native JSON payload, never infer a schema from its URL."""
    if not required():
        return request
    if transport not in {'anthropic_messages', 'gemini_native', 'systemone'}:
        raise PrivacyGuardDenied('Required privacy policy does not support this transport')
    if not isinstance(request, dict):
        raise PrivacyGuardDenied('Invalid native privacy request')
    valid = ((transport == 'anthropic_messages' and isinstance(request.get('messages'), list))
             or (transport == 'gemini_native' and isinstance(request.get('contents'), list))
             or (transport == 'systemone' and 'state' in request and isinstance(request.get('questions'), dict)))
    if not valid:
        raise PrivacyGuardDenied('Invalid native privacy request')
    from agent.auxiliary_hooks import _parent_turn_identity
    identity = _parent_turn_identity()
    sid = _SESSION.get() or identity.get('session_id') or session_id or ('native-' + uuid.uuid4().hex)
    import httpx
    timeout = request.get('timeout')
    typed_timeout = isinstance(timeout, httpx.Timeout)
    payload = {k: v for k, v in request.items() if k != 'timeout'} if typed_timeout else request
    value = _call('request', request=payload, session_id=sid, transport=transport)
    protected = value.get('request')
    if not isinstance(protected, dict):
        raise PrivacyGuardDenied('Local privacy policy returned invalid native request')
    if typed_timeout:
        protected = {**protected, 'timeout': timeout}
    return protected


def prepare_anthropic_stream(request, agent):
    from agent.anthropic_adapter import sanitize_anthropic_kwargs
    final = dict(request)
    sanitize_anthropic_kwargs(final, log_prefix=getattr(agent, 'log_prefix', ''))
    return protect_native_request(final, transport='anthropic_messages', session_id=agent.session_id or '')


def protect_model_control(model, session_id=''):
    """A route identifier is checked, never masked into a different destination."""
    if not required():
        return model
    if not isinstance(model, str) or not model:
        raise PrivacyGuardDenied('Invalid native model control')
    from agent.auxiliary_hooks import _parent_turn_identity
    sid = _SESSION.get() or _parent_turn_identity().get('session_id') or session_id
    if not sid:
        raise PrivacyGuardDenied('Native model control requires a request session')
    safe = _call('request', request={'model': model}, session_id=sid)
    if safe.get('request') != {'model': model}:
        raise PrivacyGuardDenied('Local privacy policy denied native model control')
    return model

"""Behavioral contracts for the opt-in required local privacy policy."""
import asyncio
from types import SimpleNamespace
import pytest
from openai import OpenAI, AsyncOpenAI
from agent import privacy_guard as guard

@pytest.fixture
def policy(monkeypatch):
    from hermes_cli import config_effective, plugins
    from agent import safe_worker_policy
    monkeypatch.setattr(config_effective, 'load_user_config_effective', lambda **kwargs: {'security': {'require_privacy_guard': True, 'privacy_guard_plugin':'test-policy'}})
    monkeypatch.setattr(safe_worker_policy, 'safe_worker_enabled', lambda: False)
    class Owners:
        def get(self, key): return 'test-policy'
    manager = SimpleNamespace(_privacy_policy_owners=Owners(), _discovery_lock=__import__('threading').RLock(), _middleware={})
    monkeypatch.setattr(plugins, '_delivery_manager', lambda: manager)
    return manager


def test_missing_failing_invalid_and_duplicate_policy_deny(policy):
    with OpenAI(api_key='local-test', base_url='http://127.0.0.1:1/v1') as client:
        for callbacks in [[], [lambda **k: None], [lambda **k: {'allow':False}],
                          [lambda **k: {'allow':True,'request':None}],
                          [lambda **k: 1/0], [lambda **k: {}, lambda **k: {}]]:
            policy._middleware['llm_privacy'] = callbacks
            with pytest.raises(guard.PrivacyGuardDenied):
                guard.protect_request({'messages':[{'content':'secret'}]}, client=client)


def test_policy_rewrites_copy_and_keeps_context(policy):
    import contextvars
    tag = contextvars.ContextVar('tag'); tag.set('profile-A')
    def rewrite(**k):
        assert tag.get() == 'profile-A'
        k['request']['messages'][0]['content'] = 'masked'
        return {'allow':True, 'request':k['request']}
    policy._middleware['llm_privacy'] = [rewrite]
    original={'messages':[{'content':'secret'}]}
    with OpenAI(api_key='local-test') as client:
        assert guard.protect_request(original, client=client)['messages'][0]['content']=='masked'
    assert original['messages'][0]['content']=='secret'


def test_disabled_unchanged_and_unsupported_denied(policy, monkeypatch):
    with pytest.raises(guard.PrivacyGuardDenied):
        guard.check_transport('unknown_native')
    with pytest.raises(guard.PrivacyGuardDenied):
        guard.protect_request({}, client=object())
    monkeypatch.setattr(guard,'required',lambda:False)
    original={}; assert guard.protect_request(original,client=object()) is original
    guard.check_transport('unknown_native')


def test_output_never_releases_original_on_failure(policy):
    assert guard.transform_required_output('secret') == guard.WITHHELD
    policy._middleware['llm_privacy']=[lambda **k: {'allow':True,'response_text':'safe'}]
    assert guard.transform_required_output('secret')=='safe'


def test_aux_sync_async_custom_create_is_guarded(policy):
    from agent.auxiliary_client import _relay_sync_completion, _relay_async_completion
    policy._middleware['llm_privacy']=[lambda **k: {'allow':True,'request':{'model':'fake','messages':[{'role':'user','content':'safe'}]}}]
    with OpenAI(api_key='local-test') as client:
        assert _relay_sync_completion(client, {'messages':[{'content':'secret'}]},create=lambda r:r)['messages'][0]['content']=='safe'
    async def run():
        async with AsyncOpenAI(api_key='local-test') as client:
            async def callback(request): return request
            return await _relay_async_completion(client,{'messages':[{'content':'secret'}]},create=callback)
    assert asyncio.run(run())['messages'][0]['content']=='safe'


def test_timeout_denies_and_still_running_denies(policy, monkeypatch):
    import queue
    import threading
    entered=threading.Event(); release=threading.Event()
    def slow(**kwargs):
        entered.set(); release.wait(60)
        return {'allow':True,'request':kwargs['request']}
    policy._middleware['llm_privacy']=[slow]
    monkeypatch.setattr(guard,'POLICY_TIMEOUT_SECONDS',2.0)
    try:
        with OpenAI(api_key='local-test') as client:
            with pytest.raises(guard.PrivacyGuardDenied,match='timed out'):
                guard.protect_request({},client=client)
            assert entered.is_set()
            with guard._LOCK:
                guard._RUNNING[slow] = 8
            with pytest.raises(guard.PrivacyGuardDenied,match='busy'):
                guard.protect_request({},client=client)
    finally:
        release.set()


def test_safe_worker_denies_even_with_policy(policy, monkeypatch):
    from agent import safe_worker_policy
    monkeypatch.setattr(safe_worker_policy,'safe_worker_enabled',lambda:True)
    policy._middleware['llm_privacy']=[lambda **k:{'allow':True,'request':k['request']}]
    with OpenAI(api_key='local-test') as client:
        with pytest.raises(guard.PrivacyGuardDenied):
            guard.protect_request({},client=client)


def test_typed_timeout_remains_sdk_control(policy):
    import httpx
    timeout=httpx.Timeout(7)
    def rewrite(**k):
        assert 'timeout' not in k['request']
        return {'allow':True,'request':k['request']}
    policy._middleware['llm_privacy']=[rewrite]
    with OpenAI(api_key='local-test') as client:
        result=guard.protect_request({'timeout':timeout,'model':'test'},client=client)
        assert result['timeout'] is timeout


def test_codex_runtime_direct_entry_denied(policy):
    from agent.codex_runtime import run_codex_stream
    with pytest.raises(guard.PrivacyGuardDenied):
        run_codex_stream(object(), {})


def test_turn_pins_policy_across_reload_and_config_change(policy, monkeypatch):
    first=lambda **k:{'allow':True,'response_text':'first'}
    policy._middleware['llm_privacy']=[first]
    with guard.turn_policy():
        policy._middleware['llm_privacy']=[lambda **k:{'allow':True,'response_text':'second'}]
        monkeypatch.setattr(guard,'_required_config',lambda:False)
        assert guard.required() is True
        assert guard.transform_required_output('raw')=='first'
    assert guard.required() is False


def test_two_sessions_can_use_one_policy_concurrently(policy):
    import concurrent.futures, threading
    rendezvous=threading.Barrier(2)
    def callback(**kwargs):
        rendezvous.wait(timeout=5)
        return {'allow':True,'request':kwargs['request']}
    policy._middleware['llm_privacy']=[callback]
    with OpenAI(api_key='local-test') as client, concurrent.futures.ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda sid:guard.protect_request({'model':sid},client=client,session_id=sid),['A','B']))
    assert results==[{'model':'A'},{'model':'B'}]


def test_wrong_policy_owner_denies(policy):
    policy._privacy_policy_owners={}
    policy._middleware['llm_privacy']=[lambda **k:{'allow':True,'request':k['request']}]
    with OpenAI(api_key='local-test') as client:
        with pytest.raises(guard.PrivacyGuardDenied,match='owner'):
            guard.protect_request({},client=client)


def test_held_reasoning_and_text_never_reach_callbacks():
    from agent.stream_delivery import StreamDeliveryMixin
    seen=[]
    agent=SimpleNamespace(_hold_stream=True, reasoning_callback=seen.append,
                          stream_delta_callback=seen.append, _stream_callback=seen.append)
    StreamDeliveryMixin._fire_reasoning_delta(agent,'raw-canary')
    assert StreamDeliveryMixin._deliver_to_stream_callbacks(agent,'raw-canary') is False
    assert seen==[]


def test_unreadable_or_invalid_policy_does_not_downgrade(policy, monkeypatch):
    from hermes_cli import config_effective
    monkeypatch.setattr(config_effective,'load_user_config_effective',lambda **k:{'security':{'require_privacy_guard':'true'}})
    with pytest.raises(guard.PrivacyGuardDenied): guard.required()
    def broken(**k): raise ValueError('unparseable')
    monkeypatch.setattr(config_effective,'load_user_config_effective',broken)
    with pytest.raises(guard.PrivacyGuardDenied): guard.required()


def test_default_off_keeps_tolerant_read_and_known_required_is_strict(policy, monkeypatch):
    from hermes_cli import config_effective
    calls=[]
    guard._REQUIRED_BY_HOME.clear()
    def config(**kwargs):
        calls.append(kwargs)
        if kwargs.get('fail_closed'):raise ValueError('torn file')
        return {'security':{'require_privacy_guard':False}}
    monkeypatch.setattr(config_effective,'load_user_config_effective',config)
    assert guard.required() is False
    assert calls == [{}]
    from hermes_constants import hermes_home_key
    guard._REQUIRED_BY_HOME[hermes_home_key()]=True
    with pytest.raises(guard.PrivacyGuardDenied):guard.required()


def test_required_tool_denial_and_exact_policy_args(policy):
    policy._middleware['llm_privacy']=[lambda **k:{'allow':False}]
    with pytest.raises(guard.PrivacyGuardDenied):guard.protect_tool('terminal',{'command':'<HG:bad>'},session_id='A')
    policy._middleware['llm_privacy']=[lambda **k:{'allow':True,'args':{'path':'/authorized/local'}}]
    assert guard.protect_tool('read_file',{'path':'token'},session_id='A')=={'path':'/authorized/local'}

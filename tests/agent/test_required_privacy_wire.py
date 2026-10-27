"""Actual CLI + HTTP wire evidence using a synthetic plugin, no external provider."""
import json
from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, Error, write_hermes_home
from tests.e2e.core.security._helpers import run_hermes

CANARY='LocalWireOpaqueX9t7z3a5'


def _run(tmp_path, plugin_source, enabled=True, responses=None):
    home=tmp_path/'home'/'.hermes'
    if plugin_source:
        plugin=home/'plugins'/'wire_policy';plugin.mkdir(parents=True)
        (plugin/'plugin.yaml').write_text('name: wire-policy\nversion: 1.0.0\nkind: general\ndescription: local synthetic fixture\n')
        (plugin/'__init__.py').write_text(plugin_source)
    with FakeLLMServer(responses or [Text('api_key='+CANARY,reasoning='api_key='+CANARY)]) as server:
        config='security:\n  require_privacy_guard: '+('true' if enabled else 'false')+'\n  privacy_guard_plugin: wire-policy\n'
        config+='plugins:\n  enabled:\n    - wire-policy\n'
        write_hermes_home(home,server.base_url,extra_config=config)
        result=run_hermes(['chat','-q','api_key='+CANARY,'-Q'],tmp_path/'home',cwd=tmp_path,timeout=30,
                          extra_env={'HERMES_STATE_DB_GUARD_BYPASS':'0'})
        requests=list(server.requests)
    # The gateway-backed CLI can intentionally leave its idle owner running.
    # Its PID is test-owned and rooted in this temp profile.
    return result,requests


POLICY='''
import json

def policy(phase,**payload):
    if phase=='tool':return {'allow':True,'args':payload['args']}
    if phase=='request':
        request=json.loads(json.dumps(payload['request']).replace('LocalWireOpaqueX9t7z3a5','MASKED'))
        return {'allow':True,'request':request}
    return {'allow':True,'response_text':'SAFE OUTPUT'}

def register(ctx):
    ctx.register_middleware('llm_privacy',policy)
'''


def test_required_wire_masks_main_aux_and_output(tmp_path):
    result,requests=_run(tmp_path,POLICY)
    assert result.returncode==0, result.stderr[-2000:]
    assert requests and any(r['kind']=='main' for r in requests)
    assert any(r['kind']=='aux' for r in requests)
    assert CANARY not in json.dumps([r['body'] for r in requests])
    assert CANARY not in result.stdout
    assert 'SAFE OUTPUT' in result.stdout


def test_missing_policy_sends_no_model_request(tmp_path):
    result,requests=_run(tmp_path,None)
    assert not requests
    assert result.returncode != 0
    assert 'PrivacyGuardDenied:' in result.stderr
    assert CANARY not in result.stdout


def test_required_off_preserves_existing_wire(tmp_path):
    result,requests=_run(tmp_path,None,enabled=False)
    assert result.returncode==0, result.stderr[-2000:]
    assert any(CANARY in json.dumps(r['body']) for r in requests)


def test_policy_exception_sends_no_model_request(tmp_path):
    source=POLICY.replace("    if phase=='request':", "    raise RuntimeError('must never echo request')\n    if phase=='request':")
    result,requests=_run(tmp_path,source)
    assert not requests
    assert result.returncode != 0
    assert result.stdout.strip() == 'This response was withheld by the required local privacy guard.'
    assert CANARY not in result.stdout


def test_reasoning_and_interim_held_through_tool_round(tmp_path):
    result,requests=_run(tmp_path,POLICY,responses=[ToolCall('terminal',{'command':'printf ok'},text='api_key='+CANARY),Text('api_key='+CANARY,reasoning='api_key='+CANARY)])
    assert result.returncode==0, result.stderr
    assert len([r for r in requests if r['kind']=='main'])==2
    assert CANARY not in result.stdout
    assert 'SAFE OUTPUT' in result.stdout


def test_provider_error_echo_held(tmp_path):
    result,requests=_run(tmp_path,POLICY,responses=[Error(status=400,message='api_key='+CANARY)])
    assert requests
    assert result.returncode != 0
    assert CANARY not in result.stdout

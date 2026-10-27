"""Real CLI to TLS loopback native provider, synthetic profiles only."""
import json,shutil
from pathlib import Path
import pytest
from tests.e2e.core.providers import _native_helpers as nh
from tests.fakes.providers.gemini_native import GeminiFake,Text,HERMES_ENV,hermes_model

from tests.agent._privacy_plugin import plugin_root

@pytest.fixture
def plugin(monkeypatch, pytestconfig):
 root = pytestconfig.getini("privacy_plugin_root")
 if root:
  monkeypatch.setenv("HERMES_PRIVACY_PLUGIN_ROOT", root)
 return plugin_root()/"pii_mask_abelion"

@pytest.mark.live_system_guard_bypass
def test_required_native_gemini_cli(tmp_path,plugin):
 home=nh.make_home(tmp_path/'profile',hermes_model(),env_file=HERMES_ENV,extra_config={
  'security':{'require_privacy_guard':True,'privacy_guard_plugin':'pii-mask-abelion'},
  'plugins':{'enabled':['pii-mask-abelion']}})
 shutil.copytree(plugin,home.hermes_home/'plugins/pii_mask_abelion',ignore=shutil.ignore_patterns('__pycache__'))
 with GeminiFake(tmp_path/'fake' ,[Text('ordinary final')]) as fake:
  result=nh.run_chat(home,'Say hello to budi@example.com',env=fake.child_env(),timeout=60)
  requests=fake.generate_calls()
  assert result.returncode==0,result.describe()
  assert requests and 'budi@example.com' not in json.dumps([r.body for r in requests])
  assert 'ordinary final' in result.stdout

@pytest.mark.live_system_guard_bypass
def test_required_native_anthropic_cli(tmp_path,plugin):
 from tests.e2e.core.providers._anthropic_helpers import start_rig
 from tests.fakes.providers.anthropic_messages import Reply,Text as AText
 rig=start_rig(tmp_path/'anthropic',[Reply([AText('ordinary final')])],config={
  'security':{'require_privacy_guard':True,'privacy_guard_plugin':'pii-mask-abelion'},
  'plugins':{'enabled':['pii-mask-abelion']}})
 shutil.copytree(plugin,rig.hermes_home/'plugins/pii_mask_abelion',ignore=shutil.ignore_patterns('__pycache__'))
 try:
  result=rig.run('chat','-q','Say hello to budi@example.com','-Q',timeout=60)
  assert result.returncode==0,(result.stdout,result.stderr,rig.log_tail())
  requests=rig.srv.main_requests()
  assert requests and 'budi@example.com' not in json.dumps(requests)
  assert 'ordinary final' in result.stdout
 finally:rig.stop()

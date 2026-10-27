"""Native payload checks use synthetic data and local transports only."""
import json
from types import SimpleNamespace
import pytest
from agent import privacy_guard as guard
from tests.agent import test_required_privacy_guard as fixtures

@pytest.fixture
def policy(monkeypatch, pytestconfig):
 root = pytestconfig.getini("privacy_plugin_root")
 if root:
  monkeypatch.setenv("HERMES_PRIVACY_PLUGIN_ROOT", root)
 return fixtures.policy.__wrapped__(monkeypatch)

PAYLOADS = [
 ('anthropic_messages', {'model':'claude-test','messages':[{'role':'user','content':'budi@example.com'}]}),
 ('gemini_native', {'contents':[{'role':'user','parts':[{'text':'budi@example.com'}]}]}),
 ('systemone', {'model':'jev-test','state':{'email':'budi@example.com'},'questions':{'keep':{'type':'noul','instructions':'Keep?'}}}),
]

@pytest.mark.parametrize('transport,payload',PAYLOADS)
def test_native_payload_masks_before_effect(policy,transport,payload):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 safe=guard.protect_native_request(payload,transport=transport,session_id='test')
 assert 'budi@example.com' not in json.dumps(safe)
 assert 'budi@example.com' in json.dumps(payload)

@pytest.mark.parametrize('transport,payload',PAYLOADS)
def test_native_missing_failure_duplicate_deny(policy,transport,payload):
 for callbacks in [[],[lambda **k:None],[lambda **k:{'allow':False}], [lambda **k:{'allow':True,'request':None}], [lambda **k:{},lambda **k:{}]]:
  policy._middleware['llm_privacy']=callbacks
  with pytest.raises(guard.PrivacyGuardDenied):guard.protect_native_request(payload,transport=transport)

@pytest.mark.parametrize('transport,payload',PAYLOADS)
def test_native_disabled_unchanged(policy,monkeypatch,transport,payload):
 monkeypatch.setattr(guard,'required',lambda:False)
 assert guard.protect_native_request(payload,transport=transport) is payload


def test_gemini_actual_wire_nonstream(policy):
 import httpx
 from agent.gemini_native_adapter import GeminiNativeClient
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy];seen=[]
 def receive(req):
  seen.append(json.loads(req.content));return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'safe'}]},'finishReason':'STOP'}]})
 client=GeminiNativeClient(api_key='synthetic',base_url='https://local.test/v1beta')
 client._http.close();client._http=httpx.Client(transport=httpx.MockTransport(receive))
 try:
  client.chat.completions.create(model='gemini-test',messages=[{'role':'user','content':'budi@example.com'}])
  assert seen and 'budi@example.com' not in json.dumps(seen)
  policy._middleware['llm_privacy']=[]
  with pytest.raises(guard.PrivacyGuardDenied):client.chat.completions.create(messages=[{'role':'user','content':'x'}])
  assert len(seen)==1
 finally:client.close()


def test_anthropic_create_wire(policy):
 from agent.anthropic_adapter import create_anthropic_message
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy];seen=[]
 client=SimpleNamespace(messages=SimpleNamespace(create=lambda **k:seen.append(k)))
 create_anthropic_message(client,dict(PAYLOADS[0][1]),prefer_stream=False)
 assert seen and 'budi@example.com' not in json.dumps(seen)
 policy._middleware['llm_privacy']=[]
 with pytest.raises(guard.PrivacyGuardDenied):create_anthropic_message(client,dict(PAYLOADS[0][1]),prefer_stream=False)
 assert len(seen)==1


def test_jev_direct_eval_wire(policy,monkeypatch):
 from evals.compaction.jev_arm import openrouter_asker
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 import urllib.request
 policy._middleware['llm_privacy']=[Guard().required_policy];seen=[]
 class Response:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self):return b'{"answers":{}}'
 def receive(req,**kwargs):seen.append(json.loads(req.data));return Response()
 monkeypatch.setattr(urllib.request,'urlopen',receive)
 ask=openrouter_asker(api_key='synthetic')
 ask({'email':'budi@example.com'},{'keep':{'type':'noul','instructions':'Keep?'}})
 assert seen and 'budi@example.com' not in json.dumps(seen)
 policy._middleware['llm_privacy']=[]
 with pytest.raises(guard.PrivacyGuardDenied):ask('x',{'keep':{'type':'noul'}})
 assert len(seen)==1

@pytest.mark.asyncio
async def test_gemini_stream_async_wire(policy):
 import httpx
 from agent.gemini_native_adapter import GeminiNativeClient,AsyncGeminiNativeClient
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy];seen=[]
 def receive(req):
  seen.append(json.loads(req.content))
  data={'candidates':[{'content':{'parts':[{'text':'safe'}]},'finishReason':'STOP'}]}
  return httpx.Response(200,headers={'content-type':'text/event-stream'},content=('data: '+json.dumps(data)+'\n\n').encode())
 client=GeminiNativeClient(api_key='synthetic',base_url='https://local.test/v1beta');client._http.close();client._http=httpx.Client(transport=httpx.MockTransport(receive))
 wrapper=AsyncGeminiNativeClient(client)
 try:
  stream=await wrapper.chat.completions.create(model='gemini-test',messages=[{'role':'user','content':'budi@example.com'}],stream=True)
  chunks=[chunk async for chunk in stream]
  assert chunks and seen and 'budi@example.com' not in json.dumps(seen)
 finally:await wrapper.close()


def test_anthropic_shared_stream_wire(policy,monkeypatch):
 from agent import anthropic_adapter
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy];seen=[]
 def stream_final(fn,kwargs,*a):seen.append(kwargs);return 'safe'
 monkeypatch.setattr(anthropic_adapter,'_stream_final_message',stream_final)
 client=SimpleNamespace(messages=SimpleNamespace(stream=lambda **k:None))
 assert anthropic_adapter.create_anthropic_message(client,dict(PAYLOADS[0][1]))=='safe'
 assert 'budi@example.com' not in json.dumps(seen)

@pytest.mark.parametrize('transport,payload',[
 ('gemini_native',{'contents':[{'parts':[{'inlineData':{'data':'privatebase64','mimeType':'image/png'}}]}]}),
 ('anthropic_messages',{'messages':[{'role':'user','content':[{'type':'image','source':{'type':'base64','data':'x'}}]}]}),
 ('systemone',{'state':{'cookie':'x'},'questions':{'keep':{'type':'noul'}}}),
 ('gemini_native',{'contents':[{'parts':[{'text':'Cookie: sid=x'}]}]}),
])
def test_native_media_cookie_deny(policy,transport,payload):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 with pytest.raises(guard.PrivacyGuardDenied):guard.protect_native_request(payload,transport=transport)

@pytest.mark.parametrize('transport,payload',[
 ('gemini_native',{'contents':[{'parts':[{'functionCall':{'name':'read_file','args':{'path':'/tmp/demo.txt'}}}]}]}),
 ('anthropic_messages',{'messages':[{'role':'assistant','content':[{'type':'tool_use','id':'call-1','name':'read_file','input':{'path':'/tmp/demo.txt'}}]}]}),
])
def test_native_tool_args_mask_controls_preserved(policy,transport,payload):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 safe=guard.protect_native_request(payload,transport=transport,session_id='one')
 assert '/tmp/demo.txt' not in json.dumps(safe);assert 'read_file' in json.dumps(safe)


def test_native_session_pinned_for_restore(policy):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 g=Guard();policy._middleware['llm_privacy']=[g.required_policy]
 with guard.turn_policy(session_id='owner'):
  safe=guard.protect_native_request(PAYLOADS[1][1],transport='gemini_native',session_id='adapter')
  token=safe['contents'][0]['parts'][0]['text']
  assert 'owner' in g.sessions and 'adapter' not in g.sessions
  assert g.output(response_text=token,session_id='owner',platform='cli')=='budi@example.com'


def test_anthropic_sdk_http_wire(policy):
 import anthropic,httpx
 from agent.anthropic_adapter import create_anthropic_message
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 seen=[];policy._middleware['llm_privacy']=[Guard().required_policy]
 def receive(req):
  seen.append(json.loads(req.content))
  return httpx.Response(200,json={'id':'msg_test','type':'message','role':'assistant','model':'claude-test','content':[{'type':'text','text':'safe'}],'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':1,'output_tokens':1}})
 with anthropic.Anthropic(api_key='synthetic',base_url='https://local.test',http_client=httpx.Client(transport=httpx.MockTransport(receive))) as client:
  payload={**PAYLOADS[0][1],'max_tokens':20}
  response=create_anthropic_message(client,payload,prefer_stream=False)
  assert response.content[0].text=='safe' and 'budi@example.com' not in json.dumps(seen)
  policy._middleware['llm_privacy']=[]
  with pytest.raises(guard.PrivacyGuardDenied):create_anthropic_message(client,payload,prefer_stream=False)
  assert len(seen)==1


def test_gemini_retry_continuation_stays_masked(policy,monkeypatch):
 from tests.agent.test_gemini_long_decode import _scripted_stream_client,_ld_event
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 client,kwargs,seen=_scripted_stream_client(monkeypatch,[[_ld_event('one',token='checkpoint'),'DROP'],[_ld_event('two',finish='STOP')]])
 kwargs['messages']=[{'role':'user','content':'budi@example.com'}]
 assert list(client.chat.completions.create(**kwargs))
 assert len(seen)==2 and 'budi@example.com' not in json.dumps(seen)
 assert seen[1]['continuationToken']=='checkpoint'


def test_native_controls_not_silently_changed(policy):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 payload={'state':'ordinary','questions':{'a':{'type':'choice','criteria':{'budi@example.com':'private label'}}}}
 with pytest.raises(guard.PrivacyGuardDenied):guard.protect_native_request(payload,transport='systemone')


def test_jev_error_body_withheld(policy,monkeypatch):
 from evals.compaction.jev_arm import openrouter_asker
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 import urllib.request,urllib.error,io
 policy._middleware['llm_privacy']=[Guard().required_policy]
 def fail(*a,**k):raise urllib.error.HTTPError('https://local.test',400,'error',{},io.BytesIO(b'private echo'))
 monkeypatch.setattr(urllib.request,'urlopen',fail)
 with pytest.raises(RuntimeError) as err:openrouter_asker(api_key='synthetic')('ordinary',{'keep':{'type':'noul'}})
 assert 'private echo' not in str(err.value)

@pytest.mark.asyncio
async def test_native_aux_async_dispatch_reaches_final_check(policy):
 from agent.auxiliary_client import AnthropicAuxiliaryClient,AsyncAnthropicAuxiliaryClient
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 sync=AnthropicAuxiliaryClient(SimpleNamespace(),model='claude-test',api_key='synthetic',base_url='https://local.test')
 assert guard.protect_request({'messages':[]},client=sync)=={'messages':[]}
 async_client=AsyncAnthropicAuxiliaryClient(sync)
 assert guard.protect_request({'messages':[]},client=async_client)=={'messages':[]}
 assert guard._native_dispatch_client(sync)


def test_main_anthropic_stream_final_payload(policy):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 request={**PAYLOADS[0][1],'max_tokens':10}
 safe=guard.prepare_anthropic_stream(request,SimpleNamespace(session_id='owner',log_prefix=''))
 assert 'budi@example.com' not in json.dumps(safe)
 assert safe['model']=='claude-test'


def test_gemini_sensitive_model_never_reaches_url(policy):
 from agent.gemini_native_adapter import GeminiNativeClient
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 import httpx
 seen=[];policy._middleware['llm_privacy']=[Guard().required_policy]
 client=GeminiNativeClient(api_key='synthetic',http_client=httpx.Client(transport=httpx.MockTransport(lambda req:seen.append(req))))
 try:
  with pytest.raises(guard.PrivacyGuardDenied):client.chat.completions.create(model='budi@example.com',messages=[{'role':'user','content':'ordinary'}])
  assert not seen
 finally:client.close()


def test_openai_fallback_uses_pinned_session(policy):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 from openai import OpenAI
 g=Guard();policy._middleware['llm_privacy']=[g.required_policy]
 with guard.turn_policy(session_id='owner'),OpenAI(api_key='synthetic') as client:
  guard.protect_request({'model':'test','messages':[{'role':'user','content':'budi@example.com'}]},client=client)
 assert set(g.sessions)=={'owner'}


def test_turnless_gemini_over_capacity_calls_share_one_session(policy):
 import httpx
 from agent.gemini_native_adapter import GeminiNativeClient
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 g=Guard();policy._middleware['llm_privacy']=[g.required_policy];seen=[]
 def receive(req):
  seen.append(req)
  return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'safe'}]},'finishReason':'STOP'}]})
 with GeminiNativeClient(api_key='synthetic',http_client=httpx.Client(transport=httpx.MockTransport(receive))) as client:
  for _ in range(70):client.chat.completions.create(model='gemini-test',messages=[{'role':'user','content':'ordinary'}])
 assert len(seen)==70 and len(g.sessions)==1


@pytest.mark.parametrize('control',[
 {'stop_sequences':['budi@example.com']},
 {'tools':[{'name':'lookup','input_schema':{'type':'object','properties':{'x':{'type':'string','pattern':'budi@example.com'}}}}]},
 {'tools':[{'name':'lookup','input_schema':{'type':'object','properties':{'x':{'type':'string','format':'budi@example.com'}}}}]},
 {'tools':[{'name':'lookup','input_schema':{'type':'object','$ref':'https://budi@example.com/schema'}}]},
])
def test_native_schema_validation_and_stop_controls_deny(policy,control):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 payload={**PAYLOADS[0][1],**control}
 with pytest.raises(guard.PrivacyGuardDenied):guard.protect_native_request(payload,transport='anthropic_messages')


def test_native_schema_description_can_mask(policy):
 from tests.agent._privacy_plugin import guard_class
 Guard = guard_class()
 policy._middleware['llm_privacy']=[Guard().required_policy]
 payload={**PAYLOADS[0][1],'tools':[{'name':'lookup','input_schema':{'type':'object','properties':{'x':{'type':'string','description':'Contact budi@example.com'}}}}]}
 safe=guard.protect_native_request(payload,transport='anthropic_messages')
 assert 'budi@example.com' not in json.dumps(safe)

# Required local redact (opt-in test candidate)

`security.require_privacy_guard` defaults to false. When true, `security.privacy_guard_plugin` must name the host-recorded owner of exactly one `llm_privacy` callback. This generic core contract has a concrete external consumer, `pii-mask-abelion`; no product pattern rules live in core.

The callback receives `phase=request`, `request`, `session_id`; `phase=tool`, `tool_name`, `args`, `session_id`; or `phase=output`, `response_text` and final-delivery context. It must return `allow: true` and the corresponding `request`, `args`, or `response_text`. Failure, timeout, malformed result, missing owner or duplicate policy denies. The policy runs on a copied payload in the caller's copied context, bounded to 10 seconds and eight workers per callback. A turn snapshots required state and callback identity. Owner-name pinning assumes a trusted process, not a malicious same-name plugin.

Supported routes: OpenAI SDK Chat Completions main/auxiliary sync, async and
stream dispatch; native Anthropic Messages shared create/auxiliary and main
stream; native Gemini final generate/stream HTTP payloads including continuation;
and the explicit Jev compaction-evaluation Decisions request (`state`/`questions`).
Native schemas are checked after conversion, not inferred from a shared `/v1`
prefix. Required mode pins the turn session for restoration. Unknown adapters,
Bedrock, MoA and direct Codex paths remain denied at the guarded dispatch seam.
Jev is only the identified evaluation caller, not a new general chat provider.
Arbitrary other HTTP calls, plugins and direct tool/service traffic remain outside
these checks. This is not process-wide egress containment. Typed SDK timeouts stay transport controls, not model data. Provider SDK authentication is separate from payload scanning. The required local tool check follows optional rewrites/pre-hooks and precedes actual dispatch. Required output holds text/reasoning/interim delivery; progress UI, arbitrary process traffic and every remote service are not a universal boundary.

Enable only in a disposable profile with a reviewed policy plugin and the matching core. Keep `require_privacy_guard: true` plus `privacy_guard_plugin: <registered plugin name>` in the profile security config, enable that plugin, then restart and start a new session. To roll back, stop the process, set the required flag false, disable the plugin, then restart. Removing the callback while required intentionally denies. No new dependency is added.

Use `scripts/run_tests.sh tests/agent/test_required_privacy_guard.py tests/agent/test_required_privacy_wire.py` in the checkout's prepared test environment. Synthetic core tests do not substitute for the concrete plugin's tests, actual provider-wire probes, independent review or laptop validation. See the external plugin README for session mapping limits, supported restore destinations, cookie-material policy and capacity recovery.

Native tests use synthetic data, HTTP mock transports and actual CLI runs against
TLS loopback fakes. No actual provider, paid API or installed-laptop test is
claimed. The matching plugin must preserve native control/schema fields and deny
unsupported media. Do not remove unknown-client checks to claim compatibility.

### Reproducing the concrete-plugin integration tests

Core-only guard/wire tests above are self-contained. Native tests that exercise
the concrete external policy need its separate public checkout; they explicitly
skip those integration cases when the test path option below is absent. A configured
path that lacks the plugin fails, rather than silently skipping. This is a test
harness dependency, not a runtime core dependency. No private path is required.

```sh
PLUGIN_CHECKOUT="$(mktemp -d)"
git clone https://github.com/Abelion512/abelion-hermes-plugins.git "$PLUGIN_CHECKOUT"
git -C "$PLUGIN_CHECKOUT" checkout 45eaf07
scripts/run_tests.sh tests/agent/test_required_privacy_guard.py tests/agent/test_required_privacy_wire.py tests/agent/test_required_privacy_native.py tests/agent/test_required_privacy_native_cli.py -o privacy_plugin_root="$PLUGIN_CHECKOUT" -q
```

Use the reviewed PR4 head for repeatable results, not its unmodified historical
head. The plugin checkout must include its required native policy (`guard.py`).
Tests use only synthetic credentials, mocked HTTP and loopback TLS providers.

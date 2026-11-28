"""Auxiliary provider resolution must not log credentials.

The flagged ``resolve_provider_client`` debug lines only carry provider name, model id,
and a constant suffix. Drive the real resolution entry point with a synthetic key and
assert no credential reaches the log records while the provider/model diagnostic survives.
"""

from __future__ import annotations

import logging

import pytest

from providers.base import ProviderProfile

_PROBE_ENV_VAR = "AUX_SECRET_LOG_PROBE_AUTH"
_FAKE_KEY = "sk-" + "A" * 32  # synthetic, never a real credential


class _FakeNativeClient:
    HERMES_SKIP_TRANSPORT_WRAP = True
    HERMES_SKIP_ASYNC_WRAP = True

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _NativeProfile(ProviderProfile):
    def create_client(self, **kwargs):
        return _FakeNativeClient(**kwargs)


class _PassThroughProfile(ProviderProfile):
    def create_client(self, **kwargs):
        return None


def _probe_profile(cls, name: str) -> ProviderProfile:
    return cls(
        name=name,
        auth_type="api_key",
        env_vars=(_PROBE_ENV_VAR,),
        base_url="https://aux-secret-log.invalid",
        default_aux_model="probe-model",
    )


@pytest.fixture
def registered(monkeypatch):
    """Register a probe api_key profile through the real registries and secret scope."""
    import hermes_cli.auth as _auth
    from agent import secret_scope as _secret_scope
    from hermes_cli.auth_plugin_providers import register_plugin_provider
    import providers as _providers

    _providers._discover_providers()
    monkeypatch.setattr(_providers, "_REGISTRY", dict(_providers._REGISTRY))
    monkeypatch.setattr(_providers, "_ALIASES", dict(_providers._ALIASES))
    monkeypatch.setattr(_providers, "_PROVIDER_LIST_CACHE", None)
    monkeypatch.setattr(_auth, "PROVIDER_REGISTRY", dict(_auth.PROVIDER_REGISTRY))
    scope_token = _secret_scope.set_secret_scope({_PROBE_ENV_VAR: _FAKE_KEY})

    def _register(profile: ProviderProfile) -> None:
        _providers.register_provider(profile)
        register_plugin_provider(profile)

    yield _register
    _secret_scope.reset_secret_scope(scope_token)


@pytest.mark.parametrize(
    "profile_cls", [_NativeProfile, _PassThroughProfile], ids=["native-client", "standard-client"]
)
def test_resolve_provider_client_does_not_log_api_key(registered, caplog, profile_cls):
    from agent.auxiliary_client import resolve_provider_client

    name = "aux-secret-log-" + profile_cls.__name__.lower()
    registered(_probe_profile(profile_cls, name))

    with caplog.at_level(logging.DEBUG, logger="agent.auxiliary_client"):
        client, model = resolve_provider_client(name, "probe-model")

    assert client is not None
    assert model == "probe-model"
    if profile_cls is _NativeProfile:
        assert client.kwargs["api_key"] == _FAKE_KEY
    assert _FAKE_KEY not in caplog.text
    assert "resolve_provider_client:" in caplog.text

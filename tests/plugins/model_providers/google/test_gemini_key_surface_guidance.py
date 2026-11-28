"""Tests for the 403 PERMISSION_DENIED key-surface guidance (#115306).

Google issues ``AQ.`` keys for both Google AI Studio and Vertex AI express mode, and each
surface only accepts its own keys. The prefix therefore never decides routing; instead, a
403 PERMISSION_DENIED appends guidance pointing at the surface the key likely belongs to:

- an ``AQ.`` key rejected by the default generativelanguage host may be a Vertex express key
  (the explicit aiplatform base_url is its only route there), and
- any key rejected by an explicitly configured aiplatform base may be an AI Studio key.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest

from agent.gemini_urls import (
    is_gemini_openai_compat_base_url,
    is_gemini_studio_base_url,
    is_native_gemini_base_url,
    is_vertex_express_base_url,
)
from plugins.model_providers.google.native_adapter import gemini_http_error, wrong_gemini_surface_guidance

# Concatenated so the file never contains a contiguous real-format key.
_AQ_KEY = "AQ." + "C" * 24
_AIZA_KEY = "AIza" + "Sy_TEST_" + "x" * 24

_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta"
_EXPRESS_BASE = "https://aiplatform.googleapis.com/v1beta1/publishers/google"


def _mock_response(status: int, body: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}
    resp.text = body
    return resp


def _guidance_hosts(text: str) -> set[str]:
    """Hosts parsed from guidance text; compare hosts instead of URL substrings."""
    hosts = set()
    for token in text.split():
        candidate = token.strip(".,;:()[]")
        if "." not in candidate:
            continue
        parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if "." in host and host.rsplit(".", 1)[-1].isalpha():
            hosts.add(host)
    return hosts


def _permission_denied_body() -> str:
    return json.dumps({
        "error": {
            "code": 403,
            "message": "Requests to this API aiplatform.googleapis.com method "
            "google.cloud.aiplatform.v1beta1.PredictionService.StreamGenerateContent are blocked.",
            "status": "PERMISSION_DENIED",
        }
    })


class TestGeminiHostIdentity:
    """URL host checks must compare parsed hostnames, not URL substrings."""

    @pytest.mark.parametrize("base_url", [
        "https://generativelanguage.googleapis.com.evil.example/v1beta",
        "https://evil.example/generativelanguage.googleapis.com/v1beta",
        "https://api.openai.com.evil.example/v1",
    ])
    def test_studio_host_check_rejects_lookalikes(self, base_url):
        assert is_gemini_studio_base_url(base_url) is False

    @pytest.mark.parametrize("base_url", [
        "https://generativelanguage.googleapis.com/v1beta",
        "https://USER:pass@GENERATIVELANGUAGE.GOOGLEAPIS.COM.:443/v1beta",
        "generativelanguage.googleapis.com/v1beta",
    ])
    def test_studio_host_check_accepts_exact_host_variants(self, base_url):
        assert is_gemini_studio_base_url(base_url) is True

    @pytest.mark.parametrize("base_url", [
        "https://aiplatform.googleapis.com.evil.example/v1beta1",
        "https://evil.example/aiplatform.googleapis.com/v1beta1",
        "https://aiplatform.googleapis.com.evil.example/v1beta1/endpoints/openapi",
    ])
    def test_vertex_express_check_rejects_lookalikes(self, base_url):
        assert is_vertex_express_base_url(base_url) is False

    def test_vertex_express_check_accepts_credentials_port_and_trailing_dot(self):
        base = "https://user:pw@AIPLATFORM.GOOGLEAPIS.COM.:443/v1beta1"
        assert is_vertex_express_base_url(base) is True
        assert is_native_gemini_base_url(base) is True

    @pytest.mark.parametrize("check", [is_native_gemini_base_url, is_gemini_openai_compat_base_url])
    def test_other_gemini_checks_reject_studio_lookalikes(self, check):
        base = "https://generativelanguage.googleapis.com.evil.example/v1beta/openai"
        assert check(base) is False

    def test_openai_compat_check_accepts_credentials_port_and_trailing_dot(self):
        base = "https://user:pw@GENERATIVELANGUAGE.GOOGLEAPIS.COM.:443/v1beta/openai"
        assert is_gemini_openai_compat_base_url(base) is True


class TestWrongGeminiSurfaceGuidance:
    def test_aq_key_on_studio_host_points_at_express_surface(self):
        text = wrong_gemini_surface_guidance(_STUDIO_BASE, _AQ_KEY, "PERMISSION_DENIED")
        assert text and "aiplatform.googleapis.com/v1beta1" in text
        assert "Vertex" in text

    def test_key_on_express_base_points_at_studio_surface(self):
        text = wrong_gemini_surface_guidance(
            _EXPRESS_BASE, _AQ_KEY, "PERMISSION_DENIED"
        )
        hosts = _guidance_hosts(text)
        assert hosts == {"generativelanguage.googleapis.com", "aistudio.google.com"}

    def test_aq_key_on_studio_lookalike_gets_no_guidance(self):
        base = "https://generativelanguage.googleapis.com.evil.example/v1beta"
        assert wrong_gemini_surface_guidance(base, _AQ_KEY, "PERMISSION_DENIED") == ""

    def test_aq_key_on_express_lookalike_gets_no_guidance(self):
        base = "https://aiplatform.googleapis.com.evil.example/v1beta1"
        assert wrong_gemini_surface_guidance(base, _AQ_KEY, "PERMISSION_DENIED") == ""

    def test_aq_key_on_exact_studio_host_with_port_and_trailing_dot_gets_guidance(self):
        base = "https://user:pw@GENERATIVELANGUAGE.GOOGLEAPIS.COM.:443/v1beta"
        assert wrong_gemini_surface_guidance(base, _AQ_KEY, "PERMISSION_DENIED")

    def test_non_permission_denied_status_gets_no_guidance(self):
        assert (
            wrong_gemini_surface_guidance(_STUDIO_BASE, _AQ_KEY, "UNAUTHENTICATED")
            == ""
        )
        assert wrong_gemini_surface_guidance(_STUDIO_BASE, _AQ_KEY, "") == ""

    def test_aiza_key_on_studio_host_gets_no_guidance(self):
        # A legacy AIza key cannot be an express key; a bare 403 has another cause.
        assert (
            wrong_gemini_surface_guidance(_STUDIO_BASE, _AIZA_KEY, "PERMISSION_DENIED")
            == ""
        )

    def test_vertex_oauth_openapi_base_gets_no_guidance(self):
        # The .../projects/.../endpoints/openapi base is OpenAI-compatible, not the express surface.
        base = "https://aiplatform.googleapis.com/v1beta1/projects/p/locations/global/endpoints/openapi"
        assert wrong_gemini_surface_guidance(base, _AQ_KEY, "PERMISSION_DENIED") == ""


class TestGeminiHttpErrorSurfaceGuidance:
    def test_403_on_studio_host_appends_express_guidance(self):
        err = gemini_http_error(
            _mock_response(403, _permission_denied_body()),
            api_key=_AQ_KEY,
            base_url=_STUDIO_BASE,
        )
        assert "aiplatform.googleapis.com/v1beta1" in str(err)
        assert err.status_code == 403


    def test_403_without_aq_key_keeps_raw_message(self):
        body = json.dumps({
            "error": {
                "code": 403,
                "message": "Location is not found",
                "status": "PERMISSION_DENIED",
            }
        })
        err = gemini_http_error(
            _mock_response(403, body), api_key=_AIZA_KEY, base_url=_STUDIO_BASE
        )
        assert "aiplatform.googleapis.com/v1beta1" not in str(err)
        assert "aistudio.google.com" not in str(err)

"""Shared auxiliary stream request shaping, kept outside the routing facade."""
from typing import Any
from agent.local_prompt_progress import with_prompt_progress
from agent.auxiliary_managed_local import _is_managed_local_endpoint

def stream_request_plan(kwargs: dict[str, Any], client: Any = None) -> tuple[dict[str, Any], str, float]:
    """(stream kwargs, model name, total ceiling) for a streamed re-aggregation. Requests to the
    managed llama-server also ask for prompt-reading progress, which keeps the watchdogs fed
    through a long prefill."""
    from agent.auxiliary_client import _aux_stream_total_ceiling
    stream_kwargs = dict(kwargs)
    stream_kwargs["stream"] = True
    stream_kwargs["stream_options"] = {"include_usage": True}
    if _is_managed_local_endpoint(str(getattr(client, "base_url", "") or "")):
        stream_kwargs = with_prompt_progress(stream_kwargs)
    return (stream_kwargs, str(kwargs.get("model") or ""),
            _aux_stream_total_ceiling(kwargs.get("timeout")))

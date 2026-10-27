"""Physical stream identity, shared by the main transport helpers."""
from typing import Any

def relay_stream_identity(agent, name_default: str) -> dict:
    """``session_id``/``name``/``model_name`` kwargs for ``relay_llm.stream``."""
    return {"session_id": str(getattr(agent, "session_id", "") or ""),
        "name": str(getattr(agent, "provider", "") or name_default),
        "model_name": str(getattr(agent, "model", "") or "")}

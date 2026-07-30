import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from forgeai.db.tables import LLMCall
from forgeai.services.security import redact_secrets


def record_llm_call(
    db: Session,
    *,
    run_id: str,
    model: str,
    messages: dict[str, Any],
    response: dict[str, Any],
    step_id: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
) -> LLMCall:
    clean_messages = _redact_json(messages)
    clean_response = _redact_json(response)
    encoded = json.dumps(clean_messages, sort_keys=True).encode("utf-8")
    sequence = int(
        db.execute(select(func.max(LLMCall.sequence)).where(LLMCall.run_id == run_id)).scalar()
        or 0
    ) + 1
    call = LLMCall(
        run_id=run_id,
        step_id=step_id,
        sequence=sequence,
        model=model,
        messages_hash=hashlib.sha256(encoded).hexdigest(),
        messages=clean_messages,
        response=clean_response,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def _redact_json(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_json(item) for key, item in value.items()}
    return value

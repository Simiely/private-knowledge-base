"""/api/agent：对话（SSE）/ 写操作确认 / 取消 / 会话。"""

from __future__ import annotations

import json
import queue
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.safety import SafetyError
from app.agent.service import AgentDeps
from app.api.deps import get_services, require_auth
from app.schemas import ChatBody, ConfirmBody
from app.services import AppServices

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(require_auth)])


@router.post("/chat")
def chat(body: ChatBody, services: AppServices = Depends(get_services)) -> StreamingResponse:
    if not body.message.strip():
        raise HTTPException(422, "消息不能为空")
    if not services.agent.available():
        raise HTTPException(400, "LLM 未配置（检查 LLM_PROVIDER / LLM_API_KEY / OLLAMA_HOST）")
    session_id = body.sessionId or uuid.uuid4().hex[:12]
    events = services.agent.run_chat(session_id, body.message)

    def sse_gen() -> Iterator[str]:
        try:
            yield f"event: session\ndata: {json.dumps({'sessionId': session_id})}\n\n"
            while True:
                evt_type, data = events.get(timeout=180)
                yield f"event: {evt_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if evt_type == "done":
                    break
        except queue.Empty:
            yield 'event: error\ndata: {"message": "Agent 响应超时"}\n\n'
        except Exception as e:  # pragma: no cover
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_gen(), media_type="text/event-stream")


@router.post("/confirm")
def confirm(body: ConfirmBody, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    try:
        return services.agent.pending.apply(
            body.sessionId, body.opId, _deps_for(services, body.sessionId)
        )
    except SafetyError as e:
        raise HTTPException(404 if "不存在" in str(e) else 409, str(e)) from e


@router.post("/cancel")
def cancel(body: ConfirmBody, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    try:
        return services.agent.pending.discard(body.sessionId, body.opId)
    except SafetyError as e:
        raise HTTPException(404 if "不存在" in str(e) else 409, str(e)) from e


@router.get("/session")
def session(sessionId: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return services.agent.session_summary(sessionId)


def _deps_for(services: AppServices, session_id: str) -> AgentDeps:
    """构造确认所需的 AgentDeps（apply 时用）。"""
    from app.agent.service import AgentDeps

    return AgentDeps(
        vault=services.vault,
        index=services.index,
        backup=services.backup,
        settings=services.settings,
        pending=services.agent.pending,
        session_id=session_id,
        events=queue.Queue(),
    )

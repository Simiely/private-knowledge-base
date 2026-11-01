"""Agent 服务：Pydantic AI 运行器 + 工具集 + 待确认写操作（HITL）+ SSE 事件。

设计（docs/09 §4.3）：
- 工具走类型化 Python 函数（Pydantic AI 自动生成 schema）
- **写操作暂存式**：write_file 只做校验/备份/diff 并记入 pending，用户确认后才落盘
- 事件经队列转 SSE 推给前端（text / tool / done / error）
- safety.py 为业务安全层，与框架无关
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext

from app.agent.llm import build_model_id, is_configured
from app.agent.safety import SafetyError, prepare_write
from app.config import Settings
from app.core.backup import BackupEngine
from app.core.indexer.service import IndexService
from app.core.vault import Vault

logger = logging.getLogger("obsidian-agent.agent")

SYSTEM_PROMPT = """你是 Obsidian Agent，一个帮助用户在 Obsidian 笔记库中工作的 AI 助手。

规则：
1. 回答使用与用户相同的语言（默认中文）。
2. 需要查找资料时使用 search / read_file / list_tree 工具，基于真实内容回答，不要编造。
3. 修改文档时调用 write_file 工具。**write_file 只暂存变更，用户确认后才生效**，
   请明确告知用户"已暂存，等待确认"。
4. 不要尝试读取或修改 vault 之外的路径。
5. 回答保持简洁，必要时给出修改摘要。"""


@dataclass
class AgentDeps:
    """工具运行依赖（经 Pydantic AI RunContext.deps 注入）。"""

    vault: Vault
    index: IndexService
    backup: BackupEngine
    settings: Settings
    pending: PendingStore
    session_id: str
    events: queue.Queue[tuple[str, dict[str, Any]]] = field(default_factory=queue.Queue)


@dataclass
class PendingOp:
    op_id: str
    kind: str  # write
    path: str
    content: str
    backup_path: str
    diff: str
    created_at: float
    status: str = "pending"  # pending | applied | discarded


class PendingStore:
    """待确认写操作存储（会话 → 操作）。"""

    TTL_SECONDS = 30 * 60  # 30 分钟未确认自动清理

    def __init__(self) -> None:
        self._ops: dict[str, dict[str, PendingOp]] = {}
        self._lock = threading.Lock()
        self._seq = itertools.count(1)

    def stage(
        self, session_id: str, kind: str, path: str, content: str, backup_path: str, diff: str
    ) -> PendingOp:
        op = PendingOp(
            op_id=f"op-{next(self._seq)}",
            kind=kind,
            path=path,
            content=content,
            backup_path=backup_path,
            diff=diff,
            created_at=time.time(),
        )
        with self._lock:
            self._ops.setdefault(session_id, {})[op.op_id] = op
        return op

    def get(self, session_id: str, op_id: str) -> PendingOp | None:
        with self._lock:
            return self._ops.get(session_id, {}).get(op_id)

    def apply(self, session_id: str, op_id: str, deps: AgentDeps) -> dict[str, Any]:
        """确认后落盘：写入 + 增量索引。"""
        op = self.get(session_id, op_id)
        if not op:
            raise SafetyError(f"操作不存在或已过期: {op_id}")
        if op.status != "pending":
            raise SafetyError(f"操作已处理: {op.status}")
        # 落盘前再次校验（内容可能已被外部修改，重读备份）
        check = prepare_write(deps.vault, deps.settings, deps.backup, op.path, op.content)
        deps.vault.write(op.path, check["content"])
        deps.index.update_paths({op.path})
        with self._lock:
            op.status = "applied"
        return {"opId": op_id, "path": op.path, "applied": True}

    def discard(self, session_id: str, op_id: str) -> dict[str, Any]:
        op = self.get(session_id, op_id)
        if not op:
            raise SafetyError(f"操作不存在或已过期: {op_id}")
        if op.status != "pending":
            raise SafetyError(f"操作已处理: {op.status}")
        with self._lock:
            op.status = "discarded"
        return {"opId": op_id, "path": op.path, "applied": False}

    def cleanup(self) -> None:
        now = time.time()
        with self._lock:
            for sess in list(self._ops):
                for oid in list(self._ops[sess]):
                    op = self._ops[sess][oid]
                    if op.status == "pending" and now - op.created_at > self.TTL_SECONDS:
                        del self._ops[sess][oid]
                if not self._ops[sess]:
                    del self._ops[sess]


class AgentService:
    """Agent 运行器：构建、会话、SSE 事件。"""

    def __init__(
        self,
        vault: Vault,
        index: IndexService,
        backup: BackupEngine,
        settings: Settings,
        model: object | None = None,
    ) -> None:
        """model 参数用于测试注入（如 pydantic_ai TestModel），生产留 None。"""
        self.vault = vault
        self.index = index
        self.backup = backup
        self.settings = settings
        self.pending = PendingStore()
        self.sessions: dict[str, list[Any]] = {}
        self._lock = threading.Lock()
        self._agent: Agent | None = None
        if is_configured(settings) or model is not None:
            self._agent = self._build_agent(model=model)

    def available(self) -> bool:
        return self._agent is not None

    # ---------- 构建 ----------

    def _build_agent(self, model: Any | None = None) -> Agent[Any, str]:
        if model is None:
            model = build_model_id(self.settings)
        agent = Agent[Any, str](
            model=model,
            deps_type=AgentDeps,
            system_prompt=SYSTEM_PROMPT,
            model_settings={
                "temperature": self.settings.llm_temperature,
                "max_tokens": self.settings.llm_max_tokens,
            },
        )
        agent.tool(self._tool_read_file, name="read_file")  # type: ignore[call-overload]
        agent.tool(self._tool_search, name="search")  # type: ignore[call-overload]
        agent.tool(self._tool_list_tree, name="list_tree")  # type: ignore[call-overload]
        agent.tool(self._tool_write_file, name="write_file")  # type: ignore[call-overload]
        logger.info(
            "Agent 构建完成 model=%s", model if isinstance(model, str) else type(model).__name__
        )
        return agent

    # ---------- 工具（deps 注入） ----------

    @staticmethod
    async def _tool_read_file(ctx: RunContext[AgentDeps], path: str) -> str:
        """读取 vault 内一个 md 文件的完整内容。"""
        try:
            content = ctx.deps.vault.read(path)
        except Exception as e:
            return f"错误: {e}"
        text = content.text
        if len(text) > 8000:
            text = text[:8000] + f"\n...(内容过长，截断至 8000 字符，全文 {len(content.text)} 字符)"
        return text

    @staticmethod
    async def _tool_search(ctx: RunContext[AgentDeps], query: str, limit: int = 8) -> str:
        """全文检索（中文分词），返回命中文档路径与摘要片段。"""
        try:
            rows = ctx.deps.index.search_rows(query, limit=limit, offset=0)
        except Exception as e:
            return f"错误: {e}"
        if not rows:
            return f"未找到与「{query}」相关的结果"
        lines = [f"共 {ctx.deps.index.count(query)} 条结果："]
        for r in rows[:limit]:
            snippet = r.body_original[:120].replace("\n", " ")
            lines.append(f"- {r.path} | {snippet}…")
        return "\n".join(lines)

    @staticmethod
    async def _tool_list_tree(ctx: RunContext[AgentDeps], path: str = "") -> str:
        """列出 vault 目录内容（默认根目录）。"""
        try:
            nodes = ctx.deps.vault.tree(path)
        except Exception as e:
            return f"错误: {e}"
        lines = [f"目录 {path or '/'}：" if nodes else f"目录 {path or '/'} 为空"]
        for n in nodes:
            kind = "📁" if n["type"] == "dir" else "📄"
            lines.append(f"{kind} {n['name']} ({n['path']})")
        return "\n".join(lines) if nodes else lines[0]

    @staticmethod
    async def _tool_write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
        """编辑 vault 内一个已有 md 文件（覆盖内容）。写前自动备份，**暂存待用户确认**。"""
        deps = ctx.deps
        try:
            check = prepare_write(deps.vault, deps.settings, deps.backup, path, content)
        except SafetyError as e:
            return f"错误: {e}"
        except Exception as e:
            return f"错误: {e}"
        op = deps.pending.stage(
            deps.session_id,
            "write",
            path,
            content,
            check["backup_path"],
            check["diff"],
        )
        # 推送 tool 事件 → 前端确认框
        deps.events.put(
            (
                "tool",
                {
                    "name": "write_file",
                    "opId": op.op_id,
                    "path": path,
                    "diff": check["diff"],
                    "backupPath": check["backup_path"],
                },
            )
        )
        return (
            f"写入操作 #{op.op_id} 已暂存（等待用户确认）：{path}\n"
            f"变更概览：{check['old_size']} → {check['new_size']} 字符，"
            f"备份: {check['backup_path']}"
        )

    # ---------- 会话运行 ----------

    def run_chat(self, session_id: str, message: str) -> queue.Queue[tuple[str, dict[str, Any]]]:
        """在后台线程运行一轮对话，事件经队列返回（SSE 转发）。"""
        if not self.available():
            raise RuntimeError("LLM 未配置，Agent 不可用")
        events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        history = self.sessions.setdefault(session_id, [])
        deps = AgentDeps(
            vault=self.vault,
            index=self.index,
            backup=self.backup,
            settings=self.settings,
            pending=self.pending,
            session_id=session_id,
            events=events,
        )

        def _work() -> None:
            try:
                assert self._agent is not None  # available() 已校验
                result = self._agent.run_sync(message, deps=deps, message_history=history)
                with self._lock:
                    self.sessions[session_id] = result.all_messages()
                events.put(("text", {"content": result.output}))
            except Exception as e:  # pragma: no cover - LLM 异常统一上报
                logger.exception("Agent 运行失败")
                events.put(("error", {"message": str(e)}))
            events.put(("done", {}))

        threading.Thread(target=_work, daemon=True, name=f"agent-{session_id}").start()
        return events

    def session_summary(self, session_id: str) -> dict[str, Any]:
        history = self.sessions.get(session_id, [])
        return {"sessionId": session_id, "messages": len(history)}

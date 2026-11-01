"""M5 端到端验证：FunctionModel 模拟 LLM 调用 write_file → SSE 事件流 → confirm 落盘。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:/workbuddy/2026-07-31-22-14-57/obsidian-agent")

from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.agent.service import AgentDeps, AgentService
from app.config import Settings
from app.core.backup import BackupEngine
from app.core.indexer.fts5 import Fts5Index
from app.core.indexer.service import IndexService
from app.core.vault import Vault

tmp = Path(tempfile.mkdtemp())
root = tmp / "vault"
root.mkdir()
(root / "笔记.md").write_bytes("# 笔记\n\n原文内容。".encode())
(root / "日记.md").write_bytes("# 日记\n".encode())

vault = Vault(root=root)
index = IndexService(vault=vault, backend=Fts5Index(db_path=tmp / "i.db"))
index.full_rebuild()
backup = BackupEngine(vault=vault, backup_root=tmp / "backups")
settings = Settings(vault_path=root, data_dir=tmp / "data", watch_enabled=False, backup_schedule="")

# FunctionModel：第一次调用 write_file 工具（精确参数），之后返回文本
calls = {"n": 0}


def fake_model(agent_info, model_request):
    calls["n"] += 1
    if calls["n"] == 1:
        return ModelResponse(
            parts=[
                ToolCallPart(tool_name="write_file", args={"path": "笔记.md", "content": "新内容"})
            ]
        )
    return ModelResponse(parts=[TextPart(content="已修改笔记，等待你的确认。")])


svc = AgentService(vault, index, backup, settings, model=FunctionModel(fake_model))
assert svc.available(), "FunctionModel 注入失败"

events = svc.run_chat("s1", "把笔记.md 的内容改写为：新内容")
seen = {"tool": 0, "text": 0, "done": 0, "error": 0}
op_id = None
while True:
    kind, data = events.get(timeout=30)
    seen[kind] = seen.get(kind, 0) + 1
    if kind == "tool":
        op_id = data["opId"]
        print("TOOL 事件:", data["name"], data["path"], "| diff:", data["diff"].splitlines()[:2])
        assert data["path"] == "笔记.md"
        assert "原文内容" in data["diff"]
    elif kind == "text":
        print("TEXT:", data["content"][:80])
    elif kind == "done":
        break
    elif kind == "error":
        raise AssertionError(f"error: {data}")

assert seen["tool"] == 1, f"应恰有 1 次工具事件: {seen}"
assert seen["done"] == 1
# 未确认前文件不变
assert vault.read("笔记.md").text == "# 笔记\n\n原文内容。", "确认前不应落盘"

# 确认 → 落盘 + 索引
deps = AgentDeps(
    vault=vault, index=index, backup=backup, settings=settings, pending=svc.pending, session_id="s1"
)
r = svc.pending.apply("s1", op_id, deps)
print("CONFIRM:", r)
assert vault.read("笔记.md").text == "新内容"
assert index.count("新内容") == 1, "索引未同步"

# 取消路径
calls["n"] = 0
events2 = svc.run_chat("s2", "再改一次")
op2 = None
while True:
    kind, data = events2.get(timeout=30)
    if kind == "tool":
        op2 = data["opId"]
    if kind == "done":
        break
svc.pending.discard("s2", op2)
assert vault.read("笔记.md").text == "新内容", "取消后不应写入"
print("ALL PASS")

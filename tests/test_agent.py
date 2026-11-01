"""M5：Agent 测试（safety 校验 / pending 确认流 / 工具 / 未配置 LLM 守卫）。

不依赖真实 LLM：直接测业务层（safety / pending / 工具函数）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.safety import SafetyError, prepare_write, render_diff
from app.agent.service import AgentDeps, AgentService, PendingStore
from app.config import Settings
from app.core.backup import BackupEngine
from app.core.indexer.fts5 import Fts5Index
from app.core.indexer.service import IndexService
from app.core.vault import Vault


@pytest.fixture
def env(tmp_path: Path) -> dict:
    root = tmp_path / "vault"
    (root / "sub").mkdir(parents=True)
    (root / "笔记.md").write_bytes("# 笔记\n\n原文内容。".encode())
    (root / "sub" / "a.md").write_bytes("子目录文档。".encode())
    vault = Vault(root=root)
    index = IndexService(vault=vault, backend=Fts5Index(db_path=tmp_path / "i.db"))
    index.full_rebuild()
    backup = BackupEngine(vault=vault, backup_root=tmp_path / "backups")
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
    )
    return {"vault": vault, "index": index, "backup": backup, "settings": settings, "root": root}


# ---------- safety ----------


def test_prepare_write_backup_and_diff(env: dict) -> None:
    check = prepare_write(
        env["vault"], env["settings"], env["backup"], "笔记.md", "# 新标题\n\n改写内容。"
    )
    assert check["ok"]
    assert check["diff"] and "原文内容" in check["diff"]
    assert Path(check["backup_path"]).is_file()  # 写前备份已生成
    # 未落盘
    assert env["vault"].read("笔记.md").text == "# 笔记\n\n原文内容。"


def test_prepare_write_rejects_disallowed(env: dict) -> None:
    with pytest.raises(SafetyError, match="禁止写入"):
        prepare_write(env["vault"], env["settings"], env["backup"], ".obsidian/x.md", "x")


def test_prepare_write_rejects_escape(env: dict) -> None:
    with pytest.raises(SafetyError):
        prepare_write(env["vault"], env["settings"], env["backup"], "../x.md", "x")


def test_prepare_write_rejects_missing(env: dict) -> None:
    with pytest.raises(SafetyError):
        prepare_write(env["vault"], env["settings"], env["backup"], "不存在.md", "x")


def test_render_diff_truncates_long(env: dict) -> None:
    old = "\n".join(f"line{i}" for i in range(200))
    new = "\n".join(f"line{i} modified" for i in range(200))  # 每行都改 → diff 很大
    diff = render_diff(old, new, max_lines=20)
    assert "已截断" in diff
    assert len(diff.splitlines()) <= 21


# ---------- pending 确认流 ----------


def test_pending_apply_writes_and_indexes(env: dict) -> None:
    store = PendingStore()
    op = store.stage("s1", "write", "笔记.md", "# 新标题\n\n改写内容。", "/tmp/x.bak", "diff")
    deps = AgentDeps(
        vault=env["vault"],
        index=env["index"],
        backup=env["backup"],
        settings=env["settings"],
        pending=store,
        session_id="s1",
    )
    result = store.apply("s1", op.op_id, deps)
    assert result["applied"]
    assert env["vault"].read("笔记.md").text == "# 新标题\n\n改写内容。"
    assert env["index"].count("改写内容") == 1  # 索引已同步
    # 重复应用被拒
    with pytest.raises(SafetyError):
        store.apply("s1", op.op_id, deps)


def test_pending_discard_keeps_file(env: dict) -> None:
    store = PendingStore()
    op = store.stage("s1", "write", "笔记.md", "改动内容", "/tmp/x.bak", "diff")
    result = store.discard("s1", op.op_id)
    assert not result["applied"]
    assert env["vault"].read("笔记.md").text == "# 笔记\n\n原文内容。"


def test_pending_unknown_op(env: dict) -> None:
    store = PendingStore()
    with pytest.raises(SafetyError, match="不存在"):
        store.apply("s1", "op-999", None)


# ---------- 工具（直接调用，deps 注入） ----------


def test_tool_read_and_search(env: dict) -> None:
    from app.agent.service import AgentService

    store = PendingStore()
    deps = AgentDeps(
        vault=env["vault"],
        index=env["index"],
        backup=env["backup"],
        settings=env["settings"],
        pending=store,
        session_id="s1",
    )
    import asyncio

    async def main():
        text = await AgentService._tool_read_file.__wrapped__(None, deps) if False else None
        return text

    # 直接调用工具函数（绕过 RunContext：传入构造的 deps）
    async def call():
        read = AgentService._tool_read_file

        # 工具内部使用 ctx.deps，构造伪 ctx
        class FakeCtx:
            def __init__(self):
                self.deps = deps

        r = await read(FakeCtx(), "笔记.md")
        assert "原文内容" in r
        s = await AgentService._tool_search(FakeCtx(), "原文", limit=5)
        assert "笔记.md" in s
        t = await AgentService._tool_list_tree(FakeCtx(), "")
        assert "笔记.md" in t
        w = await AgentService._tool_write_file(FakeCtx(), "笔记.md", "新内容")
        assert "已暂存" in w
        # write_file 只暂存不落盘
        assert env["vault"].read("笔记.md").text == "# 笔记\n\n原文内容。"

    asyncio.run(call())


def test_agent_unavailable_without_llm(env: dict) -> None:
    svc = AgentService(env["vault"], env["index"], env["backup"], env["settings"])
    assert not svc.available()
    with pytest.raises(RuntimeError):
        svc.run_chat("s1", "hi")


def test_agent_available_with_llm_key(env: dict) -> None:
    settings = Settings(
        vault_path=env["root"],
        data_dir=env["root"].parent / "data",
        backup_dir=env["root"].parent / "backups",
        watch_enabled=False,
        backup_schedule="",
        llm_provider="deepseek",
        llm_api_key="sk-test-key",
    )
    svc = AgentService(env["vault"], env["index"], env["backup"], settings)
    assert svc.available()
    assert svc._agent is not None

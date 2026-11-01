"""一次性类型修复工具：补齐泛型参数与注解（mypy type-arg/no-untyped-def）。

用法：代码改动后可重跑；内部长字符串不做断行（E501 豁免）。
"""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app"

# (文件相对路径, [(old, new), ...])
EDITS: dict[str, list[tuple[str, str]]] = {
    "core/markdown.py": [
        (
            "def parse_frontmatter(text: str) -> tuple[dict, str]:",
            "def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:",
        ),
        ("    fm: dict = {}", "    fm: dict[str, Any] = {}"),
        ("def _coerce(value: str):", "def _coerce(value: str) -> Any:"),
    ],
    "core/backup.py": [
        ("from typing import Any\n", "from typing import Any, cast\n"),
        (
            '        return json.loads(mf.read_text(encoding="utf-8"))',
            '        return cast(dict[str, Any], json.loads(mf.read_text(encoding="utf-8")))',
        ),
        (
            '                return self.snapshot_root / s["id"] / "tree"',
            '                return self.snapshot_root / str(s["id"]) / "tree"',
        ),
        (
            "    def _write_manifest(self, snap_id: str, manifest: dict) -> None:",
            "    def _write_manifest(self, snap_id: str, manifest: dict[str, Any]) -> None:",
        ),
        (
            "        self.last: dict | None = None",
            "        self.last: dict[str, Any] | None = None",
        ),
        (
            "    def run_restore(self, snap_id: str, after: callable | None = None) -> None:  # type: ignore[name-defined]",
            "    def run_restore(self, snap_id: str, after: Callable[[], None] | None = None) -> None:",
        ),
        (
            "    def _start(self, kind: str, arg, after=None) -> None:",
            "    def _start(self, kind: str, arg: str, after: Callable[[], None] | None = None) -> None:",
        ),
        (
            "    def _work(self, kind: str, arg, after) -> None:",
            "    def _work(self, kind: str, arg: str, after: Callable[[], None] | None) -> None:",
        ),
        (
            "                if self._last_fired is None or now >= self.spec.next_run(self._last_fired):",
            "                assert self.spec is not None\n"
            "                if self._last_fired is None or now >= self.spec.next_run(self._last_fired):",
        ),
    ],
    "core/indexer/service.py": [
        (
            "from app.core.indexer.base import IndexDoc, IndexRow",
            "from app.core.indexer.base import IndexBackend, IndexDoc, IndexRow",
        ),
        (
            "    def __init__(self, vault: Vault, backend) -> None:",
            "    def __init__(self, vault: Vault, backend: IndexBackend) -> None:",
        ),
        ("            def gen():", "            def gen() -> Iterator[IndexDoc]:"),
        (
            "            body=_tokenize_fields(doc.title, doc.aliases, body),",
            "            body=_tokenize_fields(doc.title, *doc.aliases, body),",
        ),
    ],
    "agent/service.py": [
        (
            "    events: queue.Queue[tuple[str, dict]] = field(default_factory=queue.Queue)",
            "    events: queue.Queue[tuple[str, dict[str, Any]]] = field(default_factory=queue.Queue)",
        ),
        (
            "        self.sessions: dict[str, list] = {}",
            "        self.sessions: dict[str, list[Any]] = {}",
        ),
        (
            '        agent.tool(self._tool_read_file, name="read_file")',
            '        agent.tool(self._tool_read_file, name="read_file")  # type: ignore[call-overload]',
        ),
        (
            '        agent.tool(self._tool_search, name="search")',
            '        agent.tool(self._tool_search, name="search")  # type: ignore[call-overload]',
        ),
        (
            '        agent.tool(self._tool_list_tree, name="list_tree")',
            '        agent.tool(self._tool_list_tree, name="list_tree")  # type: ignore[call-overload]',
        ),
        (
            '        agent.tool(self._tool_write_file, name="write_file")',
            '        agent.tool(self._tool_write_file, name="write_file")  # type: ignore[call-overload]',
        ),
    ],
    "api/routes_agent.py": [
        (
            "from typing import Any\n",
            "from collections.abc import Iterator\n\nfrom typing import Any\n",
        ),
        ("    def sse_gen():", "    def sse_gen() -> Iterator[str]:"),
        (
            "def _deps_for(services: AppServices, session_id: str):",
            "def _deps_for(services: AppServices, session_id: str) -> AgentDeps:",
        ),
    ],
    "main.py": [
        (
            "from typing import Any\n",
            "from collections.abc import AsyncIterator\n\nfrom typing import Any\n",
        ),
        (
            "    async def lifespan(_: FastAPI):",
            "    async def lifespan(_: FastAPI) -> AsyncIterator[None]:",
        ),
    ],
}

for rel, pairs in EDITS.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            print(f"!! 未找到 {rel}: {old[:60]!r}")
            continue
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("fixed:", rel)

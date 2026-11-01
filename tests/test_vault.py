"""M1：Vault 访问核心测试（目录树 / 读写编码容错 / 忽略规则 / 路径安全 / 监听）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.vault import FileTooLarge, PathNotAllowed, Vault, VaultError, VaultWatcher


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    root = tmp_path / "vault"
    (root / "Projects" / "Obsidian").mkdir(parents=True)
    # 注意：Windows 上 Path.write_text 会做 \n→\r\n 转换，fixture 统一用 write_bytes 保证确定性
    (root / "Projects" / "Obsidian" / "插件开发.md").write_bytes("# 插件开发\n\n正文\n".encode())
    (root / "日记.md").write_bytes("# 日记\n".encode())
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "workspace.json").write_bytes(b"{}")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "x.md").write_bytes(b"x")
    (root / "附件.png").write_bytes(b"\x89PNG fake")
    (root / ".hidden.md").write_bytes(b"hidden")
    return Vault(root=root)


# ---------- 目录树 / 忽略 ----------


def test_tree_basic(vault: Vault) -> None:
    nodes = vault.tree()
    names = {n["name"] for n in nodes}
    assert "日记.md" in names
    assert "附件.png" in names
    assert "Projects" in names
    assert ".obsidian" not in names
    assert "node_modules" not in names
    assert ".hidden.md" not in names


def test_tree_nested(vault: Vault) -> None:
    proj = next(n for n in vault.tree() if n["name"] == "Projects")
    assert proj["type"] == "dir"
    obs = next(n for n in vault.tree(proj["path"]) if n["name"] == "Obsidian")
    files = {f["name"] for f in vault.tree(obs["path"])}
    assert "插件开发.md" in files


def test_walk_md_excludes_ignored(vault: Vault) -> None:
    rels = {rel for rel, _ in vault.walk_md()}
    assert "日记.md" in rels
    assert "Projects/Obsidian/插件开发.md" in rels
    assert ".obsidian/workspace.json" not in rels
    assert "node_modules/x.md" not in rels
    assert ".hidden.md" not in rels


def test_is_ignored(vault: Vault) -> None:
    assert vault.is_ignored(".obsidian/workspace.json")
    assert vault.is_ignored("node_modules/x.md")
    assert not vault.is_ignored("日记.md")
    assert not vault.is_ignored("Projects/Obsidian/插件开发.md")


# ---------- 读写与编码（坑 #6） ----------


def test_read_utf8(vault: Vault) -> None:
    content = vault.read("日记.md")
    assert content.text == "# 日记\n"
    assert content.meta.encoding == "utf-8-sig" or content.meta.encoding == "utf-8"


def test_read_utf8_bom(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "bom.md").write_bytes(b"\xef\xbb\xbf" + "# BOM 标题\n".encode())
    v = Vault(root=root)
    assert v.read("bom.md").text == "# BOM 标题\n"


def test_read_gbk(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "gbk.md").write_bytes("旧笔记：中文内容".encode("gbk"))
    v = Vault(root=root)
    assert v.read("gbk.md").text == "旧笔记：中文内容"


def test_write_preserves_crlf(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "win.md").write_bytes("# 标题\r\n第一行\r\n".encode())
    v = Vault(root=root)
    v.write("win.md", "# 新标题\n第二行")
    raw = (root / "win.md").read_bytes()
    assert raw == "# 新标题\r\n第二行".encode()  # 换行保留 CRLF
    assert b"\xef\xbb\xbf" not in raw  # 无 BOM


def test_write_rejects_non_md(vault: Vault) -> None:
    with pytest.raises(PathNotAllowed):
        vault.write("附件.png", "x")


def test_write_above_max_bytes(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    f = root / "big.md"
    f.write_bytes(b"x" * 100)
    v = Vault(root=root, max_file_bytes=50)
    with pytest.raises(FileTooLarge):
        v.write("big.md", "y")


def test_create_and_delete(vault: Vault) -> None:
    vault.create("新笔记.md", "# 新\n")
    assert (vault.root / "新笔记.md").is_file()
    with pytest.raises(FileExistsError):
        vault.create("新笔记.md")
    vault.delete("新笔记.md")
    assert not (vault.root / "新笔记.md").exists()


# ---------- 路径安全（坑 #7） ----------


@pytest.mark.parametrize(
    "bad",
    [
        "../secret.txt",
        "..\\secret.txt",
        "../../etc/passwd",
        "C:/Windows/win.ini",
        "D:\\x.md",
        "/etc/passwd",
    ],
)
def test_resolve_rejects_escape(vault: Vault, bad: str) -> None:
    with pytest.raises(PathNotAllowed):
        vault.resolve_safe_path(bad, md_only=False)


def test_resolve_ok_inside(vault: Vault) -> None:
    p = vault.resolve_safe_path("Projects/Obsidian/插件开发.md", must_exist=True)
    assert p == (vault.root / "Projects/Obsidian/插件开发.md").resolve()


def test_resolve_missing_raises(vault: Vault) -> None:
    with pytest.raises(FileNotFoundError):
        vault.resolve_safe_path("不存在.md", must_exist=True)


# ---------- 监听（debounce） ----------


def test_watcher_debounce(tmp_path: Path) -> None:
    import time

    root = tmp_path / "vault"
    root.mkdir()
    (root / "a.md").write_text("a", encoding="utf-8")
    v = Vault(root=root)
    got: list[set] = []

    def on_change(paths: set) -> None:
        got.append(paths)

    w = VaultWatcher(v, debounce_seconds=0.4, on_change=on_change)
    w.start()
    try:
        (root / "a.md").write_text("a2", encoding="utf-8")
        (root / "b.md").write_text("b", encoding="utf-8")
        deadline = time.time() + 5
        while time.time() < deadline and not got:
            time.sleep(0.1)
        assert got, "回调应被触发"
        assert len(got) == 1, "debounce 应合并为一次回调"
        assert "a.md" in got[0] and "b.md" in got[0]
    finally:
        w.stop()


def test_vault_root_must_exist(tmp_path: Path) -> None:
    with pytest.raises(VaultError):
        Vault(root=tmp_path / "nope")

# ---------- 图片资源接口（md 图片显示支持） ----------


def test_find_asset_by_name(tmp_path: Path) -> None:
    """find_asset_by_name：按文件名全库搜索图片（Obsidian wikilink 语义）。"""
    from app.core.vault import Vault

    (tmp_path / "98_附件").mkdir()
    img = tmp_path / "98_附件" / "(第 1 天) 测试.webp"
    img.write_bytes(b"fake-webp")
    vault = Vault(tmp_path)

    found = vault.find_asset_by_name("(第 1 天) 测试.webp")
    assert found == img

    # 不存在的文件名
    assert vault.find_asset_by_name("nope.webp") is None
    # 非图片扩展名不匹配
    (tmp_path / "98_附件" / "x.md").write_text("x")
    assert vault.find_asset_by_name("x.md") is None


def test_asset_endpoint(app_client) -> None:
    """GET /api/vault/asset：返回图片字节流；非法扩展名 422；越界 422。"""
    # 在测试 vault 造一张图
    from pathlib import Path

    vault_root = Path(app_client.app.state.services.settings.vault_path)
    (vault_root / "assets").mkdir(parents=True, exist_ok=True)
    img = vault_root / "assets" / "pic.webp"
    img.write_bytes(b"WEBP-FAKE-BYTES")

    r = app_client.get("/api/vault/asset", params={"path": "assets/pic.webp"})
    assert r.status_code == 200
    assert r.content == b"WEBP-FAKE-BYTES"

    # wikilink 文件名全库搜索
    r2 = app_client.get("/api/vault/asset", params={"path": "pic.webp"})
    assert r2.status_code == 200

    # 非图片扩展名（vault 内存在的 md）
    (vault_root / "a.md").write_text("# a")
    r3 = app_client.get("/api/vault/asset", params={"path": "a.md"})
    assert r3.status_code == 422

    # 路径遍历
    r4 = app_client.get("/api/vault/asset", params={"path": "../outside.png"})
    assert r4.status_code == 422


def test_find_md_by_name(tmp_path: Path) -> None:
    """find_md_by_name：按文件名全库匹配 .md（Obsidian wikilink 语义）。"""
    from app.core.vault import Vault

    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "目标文档.md").write_text("# 目标")
    vault = Vault(tmp_path)

    assert vault.find_md_by_name("目标文档") == "notes/目标文档.md"
    assert vault.find_md_by_name("目标文档.md") == "notes/目标文档.md"
    assert vault.find_md_by_name("不存在") is None


def test_resolve_md_endpoint(app_client) -> None:
    """GET /api/vault/resolve-md：按文件名解析；不存在 404。"""
    from pathlib import Path

    vault_root = Path(app_client.app.state.services.settings.vault_path)
    (vault_root / "a.md").write_text("# a")

    r = app_client.get("/api/vault/resolve-md", params={"name": "a"})
    assert r.status_code == 200
    assert r.json()["path"] == "a.md"

    r2 = app_client.get("/api/vault/resolve-md", params={"name": "nope"})
    assert r2.status_code == 404

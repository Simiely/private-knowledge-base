"""GitHub 批量上传脚本：Git Data API 单 commit 推送（避免逐文件触发 Actions）。

流程（Git Data API，一次推送 = 一个 commit = 触发一次 Actions 构建）：
  1. 取当前分支 HEAD commit sha 与其 tree sha（base_tree 保留未变文件）
  2. 为每个文件创建 blob（base64）
  3. 创建新 tree（base_tree + 变更文件；本地已删的文件置 sha=None 删除）
  4. 创建 commit（parents=[HEAD]）
  5. 更新分支 ref 指向新 commit

用法：GH_TOKEN=ghp_xxx python scripts/upload_github.py [repo_name] [private]
token 仅经环境变量传入，绝不写入任何文件。
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = os.environ["GH_TOKEN"]
ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = sys.argv[1] if len(sys.argv) > 1 else "obsidian-agent"
PRIVATE = len(sys.argv) > 2 and sys.argv[2].lower() in ("private", "true", "1")
DESCRIPTION = (
    "Dockerized Obsidian AI workspace: browse, edit, full-text search and AI agent over your vault"
)

EXCLUDE_DIRS = {
    "node_modules",
    "dist",
    "data",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
}
EXCLUDE_FILES = {".env"}
BRANCH = "main"

API = "https://api.github.com"


def req(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"message": raw.decode("utf-8", "ignore")[:200]}


def collect_files() -> list[Path]:
    out: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name in EXCLUDE_FILES:
            continue
        out.append(rel)
    return out


def get_remote_paths(owner: str, repo: str) -> set[str]:
    """拉取远端 main 分支全部文件路径（用于识别本地已删除的文件）。"""
    st, body = req("GET", f"{API}/repos/{owner}/{repo}/git/ref/heads/{BRANCH}")
    if st == 404:
        return set()  # 分支不存在（全新仓库）
    assert st == 200, f"获取分支失败: {st} {body}"
    head_sha = body["object"]["sha"]
    st, commit = req("GET", f"{API}/repos/{owner}/{repo}/git/commits/{head_sha}")
    assert st == 200, f"获取 commit 失败: {st} {commit}"
    tree_sha = commit["tree"]["sha"]
    st, tree = req("GET", f"{API}/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1")
    assert st == 200, f"获取 tree 失败: {st} {tree}"
    return {t["path"] for t in tree.get("tree", []) if t["type"] == "blob"}


def main() -> None:
    # 1. 当前用户
    st, me = req("GET", f"{API}/user")
    assert st == 200, f"无法获取用户信息: {me}"
    owner = me["login"]
    print(f"owner: {owner} ({me.get('name') or ''})")

    # 2. 创建仓库（已存在则继续）
    st, body = req(
        "POST",
        f"{API}/user/repos",
        {
            "name": REPO_NAME,
            "description": DESCRIPTION,
            "private": PRIVATE,
        },
    )
    if st in (200, 201):
        print(f"仓库已创建: {body['html_url']}")
    elif st == 422:
        print(f"仓库已存在（{body.get('message')}），继续推送")
    else:
        print(f"建仓失败: {st} {body}")

    repo_api = f"{API}/repos/{owner}/{REPO_NAME}"

    # 3. 收集本地文件 + 远端路径（识别删除）
    files = collect_files()
    local_paths = {f.as_posix() for f in files}
    remote_paths = get_remote_paths(owner, REPO_NAME)
    deleted = sorted(remote_paths - local_paths)
    print(f"待推送: {len(files)} 新增/更新 + {len(deleted)} 删除")

    # 4. 创建 blobs
    blobs: dict[str, str] = {}
    for rel in files:
        content = base64.b64encode((ROOT / rel).read_bytes()).decode()
        st, body = req(
            "POST",
            f"{repo_api}/git/blobs",
            {"content": content, "encoding": "base64"},
        )
        if st != 201:
            print(f"  FAIL blob: {rel} -> {body.get('message')}")
            sys.exit(1)
        blobs[rel.as_posix()] = body["sha"]
        time.sleep(0.05)  # 限速保护
    print(f"blobs 创建完成: {len(blobs)}")

    # 5. 构建 tree 条目（含删除标记）
    tree_entries = [
        {"path": path, "mode": "100644", "type": "blob", "sha": sha}
        for path, sha in blobs.items()
    ]
    tree_entries += [
        {"path": path, "mode": "100644", "type": "blob", "sha": None} for path in deleted
    ]

    # 6. 取当前 HEAD（存在则用 base_tree 保留未变文件；全新仓库用空 base）
    parent_sha: str | None = None
    base_tree_sha: str | None = None
    st, ref = req("GET", f"{repo_api}/git/ref/heads/{BRANCH}")
    if st == 200:
        parent_sha = ref["object"]["sha"]
        st, commit = req("GET", f"{repo_api}/git/commits/{parent_sha}")
        base_tree_sha = commit["tree"]["sha"]
        print(f"HEAD={parent_sha[:8]} base_tree={base_tree_sha[:8]}")

    body: dict = {"tree": tree_entries}
    if base_tree_sha:
        body["base_tree"] = base_tree_sha
    st, tree = req("POST", f"{repo_api}/git/trees", body)
    assert st in (200, 201), f"创建 tree 失败: {st} {tree}"
    new_tree_sha = tree["sha"]
    print(f"tree 创建完成: {new_tree_sha[:8]}")

    # 7. 创建 commit（单 commit 包含全部变更）
    commit_body: dict = {
        "message": "Sync local workspace to GitHub (single commit)",
        "tree": new_tree_sha,
    }
    if parent_sha:
        commit_body["parents"] = [parent_sha]
    st, commit = req("POST", f"{repo_api}/git/commits", commit_body)
    assert st in (200, 201), f"创建 commit 失败: {st} {commit}"
    new_commit_sha = commit["sha"]
    print(f"commit 创建完成: {new_commit_sha[:8]}")

    # 8. 更新分支 ref
    st, body = req(
        "PATCH",
        f"{repo_api}/git/refs/heads/{BRANCH}",
        {"sha": new_commit_sha, "force": False},
    )
    assert st == 200, f"更新 ref 失败: {st} {body}"
    print(f"✅ 推送完成（单 commit）: {new_commit_sha[:8]}")
    print(f"仓库地址: https://github.com/{owner}/{REPO_NAME}")


if __name__ == "__main__":
    main()

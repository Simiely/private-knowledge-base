"""M4 冒烟：真实 uvicorn 服务 + Vue dist + API 全链路（含编辑保存）。"""

import json
import re
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn

sys.path.insert(0, r"D:/workbuddy/2026-07-31-22-14-57/obsidian-agent")

from app.config import Settings
from app.main import create_app

tmp = Path(tempfile.mkdtemp())
root = tmp / "vault"
(root / "Projects").mkdir(parents=True)
note = (
    "---\ntags:\n  - docker\n---\n# Docker 部署\n\n"
    "这是关于 **中文分词** 与 ==高亮== 的测试笔记，包含 [[日记|别名链接]] 和 callout。\n\n"
    "> [!tip] 提示\n> 这是一个提示 callout。\n\n- [ ] 待办事项\n"
)
(root / "Projects" / "Docker 部署.md").write_bytes(note.encode("utf-8"))
(root / "日记.md").write_bytes("# 日记\n\n2026-07-31 的记录。".encode())

settings = Settings(
    vault_path=root, data_dir=tmp / "data", watch_enabled=False, backup_schedule="", port=8899
)
app = create_app(settings)

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8899, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()

BASE = "http://127.0.0.1:8899"
for _ in range(60):
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=1)
        break
    except Exception:
        time.sleep(0.2)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read())


def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(r, timeout=5) as resp:
        return resp.status, json.loads(resp.read() or b"{}")


# 等索引就绪
for _ in range(60):
    if get("/api/index/status")["state"] == "ready":
        break
    time.sleep(0.2)

# 前端 dist
html = urllib.request.urlopen(BASE + "/", timeout=5).read().decode()
assert '<div id="app"></div>' in html, "Vue 挂载点缺失"
assets = re.findall(r'assets/[^"]+\.js', html)
assert assets, "未找到 JS 资源"
js = urllib.request.urlopen(BASE + "/" + assets[0], timeout=5).read().decode()
assert "vue" in js.lower() or "createApp" in js, "JS 资源异常"
print("PASS 前端 dist 页面与资源")

# API 全链路
tree = get("/api/vault/tree")
assert {n["name"] for n in tree} == {"Projects", "日记.md"}
print("PASS 目录树:", [n["name"] for n in tree])

r = get("/api/search?q=" + urllib.parse.quote("中文分词"))
assert r["total"] == 1 and r["results"][0]["path"] == "Projects/Docker 部署.md"
print("PASS 中文检索命中")

r = get("/api/search?q=docker")
assert r["results"][0]["tags"] == ["docker"]
print("PASS tags:", r["results"][0]["tags"])

# 编辑保存 → 索引同步
content = get("/api/vault/file?path=" + urllib.parse.quote("Projects/Docker 部署.md"))
new_content = content["content"] + "\n新增一行：向量检索知识。\n"
st, _ = req("PUT", "/api/vault/file", {"path": "Projects/Docker 部署.md", "content": new_content})
assert st == 200
time.sleep(0.5)
r = get("/api/search?q=" + urllib.parse.quote("向量检索"))
assert r["total"] == 1, f"编辑后索引未同步: {r}"
print("PASS 编辑保存 + 增量索引同步")

# 备份快照 + 恢复
st, _ = req("POST", "/api/backup/now")
assert st == 202
for _ in range(30):
    if get("/api/backup/list")["snapshots"]:
        break
    time.sleep(0.2)
snap_id = get("/api/backup/list")["snapshots"][0]["id"]
st, _ = req(
    "POST", "/api/backup/restore-file", {"path": "Projects/Docker 部署.md", "snapshotId": snap_id}
)
assert st == 200
print("PASS 备份快照 + 单文件恢复")

server.should_exit = True
time.sleep(0.5)
print("M4 SMOKE ALL PASS")
